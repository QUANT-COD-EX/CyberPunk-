"""
FastAPI router for investigation lifecycle, document ingestion, and processing.
Advisory output. Final decision rests with the human reviewer.
"""

import os
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, File, Header, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from backend.app.db.storage import StorageManager
from backend.app.models.contracts import (
    AuditEvent,
    CaseDecision,
    CaseDecisionType,
    DocumentRecord,
    ExtractedField,
    Finding,
    FindingStatus,
    Investigation,
    ReviewDecision,
    ReviewerAction,
    ReviewPriority,
    CrossDocRelationshipGraph,
    AnomalyCorrelationCluster,
    ForensicAnalysisReport,
)
from backend.app.services.audit import AuditService
from backend.app.services.correlation.cross_doc import CrossDocEngine
from backend.app.services.dossier import generate_dossier
from backend.app.services.escalation import EscalationEngine
from backend.app.services.explanation import generate_finding_explanation
from backend.app.services.ingestion import IngestionService
from backend.app.services.injection import scan_spans_for_injections, scan_text_for_injections
from backend.app.services.pii import mask_field_value
from backend.app.services.render import get_rendered_page_path
from backend.app.services.rules.rules_runner import execute_document_rules, execute_forensics_checks

def _resolve_data_dir() -> Path:
    # Check if running in serverless environment (Netlify Functions, AWS Lambda) or read-only filesystem
    if os.environ.get("NETLIFY") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME") or os.environ.get("LAMBDA_TASK_ROOT"):
        temp_data = Path(tempfile.gettempdir()) / "cyberpunk_data"
        temp_data.mkdir(parents=True, exist_ok=True)
        return temp_data

    target = Path("data")
    try:
        target.mkdir(parents=True, exist_ok=True)
        probe = target / ".write_probe"
        probe.touch()
        probe.unlink()
        return target
    except (OSError, PermissionError):
        temp_data = Path(tempfile.gettempdir()) / "cyberpunk_data"
        temp_data.mkdir(parents=True, exist_ok=True)
        return temp_data

# Global persistent storage initialization (adapts to serverless /tmp if read-only)
DATA_DIR = _resolve_data_dir()
DB_PATH = DATA_DIR / "app.db"
storage_mgr = StorageManager(DB_PATH, DATA_DIR)
audit_service = AuditService(DB_PATH)
ingestion_service = IngestionService(storage_mgr, audit_service)

ACCEPTED_SUFFIXES = {
    ".pdf", ".png", ".jpg", ".jpeg",
    ".docx", ".xlsx", ".xls",
    ".tiff", ".tif", ".bmp", ".webp"
}

router = APIRouter(tags=["investigations"])


@router.post("/investigations", response_model=Investigation)
def create_investigation():
    inv_id = f"INV-{uuid.uuid4().hex[:8].upper()}"
    now_iso = datetime.now(timezone.utc).isoformat()
    inv = Investigation(
        investigation_id=inv_id,
        created_at=now_iso,
        documents=[],
        review_priority=ReviewPriority.LOW,
        priority_score=0,
        priority_breakdown=[],
        case_decision=None,
    )
    storage_mgr.create_investigation(inv)
    audit_service.log_event(inv_id, "system", "investigation_created", inv_id)
    return inv


@router.get("/investigations", response_model=List[Investigation])
def list_investigations():
    """Returns all investigations in descending order of creation."""
    return storage_mgr.list_investigations()


@router.get("/investigations/{inv_id}", response_model=Investigation)
def get_investigation(inv_id: str):
    inv = storage_mgr.get_investigation(inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return inv


@router.post("/investigations/{inv_id}/documents", response_model=List[DocumentRecord])
async def upload_documents(
    inv_id: str,
    files: List[UploadFile] = File(...),
):
    inv = storage_mgr.get_investigation(inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")

    ingested_docs = []
    for file in files:
        suffix = Path(file.filename or "file.pdf").suffix.lower()
        if suffix not in ACCEPTED_SUFFIXES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unsupported file format '{suffix}'. Supported formats: {', '.join(sorted(ACCEPTED_SUFFIXES))}",
            )
        doc_id = f"DOC-{uuid.uuid4().hex[:6].upper()}"

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp_path = Path(tmp.name)
            content = await file.read()
            tmp.write(content)

        try:
            doc_rec = ingestion_service.ingest_file(
                investigation_id=inv_id,
                doc_id=doc_id,
                source_path=tmp_path,
                original_filename=file.filename or "uploaded_file",
            )
            ingested_docs.append(doc_rec)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    return ingested_docs


@router.post("/investigations/{inv_id}/process", response_model=Investigation)
def process_investigation(inv_id: str, x_llm_api_key: Optional[str] = Header(None)):
    inv = storage_mgr.get_investigation(inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")

    docs = storage_mgr.get_documents(inv_id)
    for doc in docs:
        ingestion_service.process_document(inv_id, doc.doc_id, llm_api_key=x_llm_api_key)

    # Re-fetch processed documents with extracted fields
    updated_docs = storage_mgr.get_documents(inv_id)

    all_findings: List[Finding] = []

    # 1. Execute within-document rules & forensics
    for doc in updated_docs:
        doc_findings = execute_document_rules(doc)
        all_findings.extend(doc_findings)

        file_path = storage_mgr.get_document_file_path(doc.doc_id)
        if file_path and file_path.exists():
            rendered_pages = [get_rendered_page_path(storage_mgr.rendered_dir, doc.doc_id, p) for p in range(1, doc.pages + 1)]
            forensic_findings = execute_forensics_checks(
                doc=doc,
                doc_file_path=file_path,
                rendered_pages=[p for p in rendered_pages if p.exists()],
            )
            all_findings.extend(forensic_findings)

            # Scan for prompt-injections in PDF text spans
            if file_path.suffix.lower() == ".pdf":
                try:
                    import fitz
                    pdoc = fitz.open(file_path)
                except (ImportError, Exception):
                    pdoc = None  # fitz unavailable or file unreadable
                if pdoc is not None:
                    try:
                        for pnum, page in enumerate(pdoc, start=1):
                            pdict = page.get_text("dict")
                            spans = []
                            for b in pdict.get("blocks", []):
                                for l in b.get("lines", []):
                                    spans.extend(l.get("spans", []))
                            inject_findings = scan_spans_for_injections(spans, doc.doc_id, page_num=pnum)
                            all_findings.extend(inject_findings)
                    finally:
                        pdoc.close()

    # 2. Execute cross-document correlation
    cross_engine = CrossDocEngine()
    cross_findings, _ = cross_engine.correlate_investigation(inv_id, updated_docs)
    all_findings.extend(cross_findings)

    # Cross-document cloned deepfake signature detection
    try:
        from backend.app.services.forensics.signature_forensics import detect_cloned_signatures_cross_document
        cloned_sig_findings = detect_cloned_signatures_cross_document(updated_docs, storage_mgr.rendered_dir)
        all_findings.extend(cloned_sig_findings)
    except Exception:
        pass

    # 3. Apply three-tier escalation logic
    escalation_engine = EscalationEngine()
    escalated_findings = escalation_engine.escalate_findings(all_findings)

    # 4. Generate deterministic explanations (zero forbidden words)
    for f in escalated_findings:
        f.explanation = generate_finding_explanation(f)

    # 5. Calculate transparent Review Priority
    priority, score, breakdown = escalation_engine.calculate_review_priority(escalated_findings)
    storage_mgr.update_investigation_priority(inv_id, priority, score, breakdown)

    # Save findings
    storage_mgr.save_findings(inv_id, escalated_findings)

    # 6. Build Intelligent Cross-Document Relationship Discovery Graph
    from backend.app.services.correlation.relationship_discovery import build_cross_document_relationship_graph
    rel_graph = build_cross_document_relationship_graph(updated_docs, escalated_findings)

    # 7. Build Advanced Contextual Reasoning & Anomaly Correlation Clusters
    from backend.app.services.correlation.contextual_reasoning import build_contextual_reasoning_and_clusters
    corr_clusters = build_contextual_reasoning_and_clusters(escalated_findings, updated_docs)

    # 8. Compute overall tampering risk score
    tamper_scores = [d.forensic_report.tamper_score for d in updated_docs if d.forensic_report]
    overall_tamper_score = max(tamper_scores) if tamper_scores else 0.0

    # 9. Save relationship graph and correlation clusters
    storage_mgr.save_investigation_analytics(
        investigation_id=inv_id,
        relationship_graph=rel_graph,
        correlation_clusters=corr_clusters,
        tampering_risk_score=overall_tamper_score,
    )

    # Log findings creation
    for f in escalated_findings:
        audit_service.log_event(
            investigation_id=inv_id,
            actor="system",
            action="finding_created",
            object_id=f.finding_id,
            details={"rule_id": f.rule_id, "tier": f.tier.value, "title": f.title},
        )

    updated_inv = storage_mgr.get_investigation(inv_id)
    return updated_inv


@router.get("/investigations/{inv_id}/relationships", response_model=CrossDocRelationshipGraph)
def get_investigation_relationships(inv_id: str):
    """
    Returns the interactive Cross-Document Relationship Network Graph,
    including canonical entities, ownership linkages, and cross-document contradictions.
    """
    inv = storage_mgr.get_investigation(inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")

    if inv.relationship_graph:
        return inv.relationship_graph

    # If not pre-computed, compute on the fly
    from backend.app.services.correlation.relationship_discovery import build_cross_document_relationship_graph
    docs = storage_mgr.get_documents(inv_id)
    findings = storage_mgr.get_findings(inv_id)
    graph = build_cross_document_relationship_graph(docs, findings)
    return graph


@router.get("/investigations/{inv_id}/analytics")
def get_investigation_analytics(inv_id: str):
    """
    Returns comprehensive investigation analytics:
    - Tampering risk score
    - Cross-document consistency index
    - Anomaly correlation clusters with step-by-step reasoning chains
    - Multilingual and handwriting distribution statistics
    """
    inv = storage_mgr.get_investigation(inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")

    docs = storage_mgr.get_documents(inv_id)
    findings = storage_mgr.get_findings(inv_id)

    # Multilingual & Handwriting distribution
    total_docs = len(docs)
    total_fields = sum(len(d.fields) for d in docs)
    hw_fields = sum(1 for d in docs for f in d.fields if f.is_handwritten)

    all_scripts: dict[str, int] = {}
    for d in docs:
        for s in d.scripts:
            all_scripts[s] = all_scripts.get(s, 0) + 1

    all_langs: dict[str, int] = {}
    for d in docs:
        for l in d.detected_languages:
            all_langs[l] = all_langs.get(l, 0) + 1

    tier_counts = {"observation": 0, "inconsistency": 0, "potential_manipulation": 0}
    for f in findings:
        tier_counts[f.tier.value] = tier_counts.get(f.tier.value, 0) + 1

    graph = inv.relationship_graph
    if not graph:
        from backend.app.services.correlation.relationship_discovery import build_cross_document_relationship_graph
        graph = build_cross_document_relationship_graph(docs, findings)

    clusters = inv.correlation_clusters
    if not clusters:
        from backend.app.services.correlation.contextual_reasoning import build_contextual_reasoning_and_clusters
        clusters = build_contextual_reasoning_and_clusters(findings, docs)

    return {
        "investigation_id": inv_id,
        "total_documents": total_docs,
        "total_fields": total_fields,
        "tampering_risk_score": inv.tampering_risk_score,
        "consistency_score": graph.consistency_score if graph else 1.0,
        "total_entities_discovered": graph.total_entities if graph else 0,
        "contradictions_count": graph.contradictions_count if graph else 0,
        "findings_by_tier": tier_counts,
        "languages": all_langs,
        "scripts": all_scripts,
        "handwriting_stats": {
            "docs_with_handwriting": sum(1 for d in docs if d.has_handwriting),
            "total_handwritten_fields": hw_fields,
            "overall_handwriting_ratio": round(hw_fields / max(1, total_fields), 3),
        },
        "correlation_clusters": [c.model_dump() for c in clusters],
    }


@router.get("/documents/{doc_id}/pages/{page_num}/forensics", response_model=ForensicAnalysisReport)
def get_document_page_forensics(doc_id: str, page_num: int):
    """
    Returns detailed image forensics analysis for tampering localization (ELA, noise, copy-move).
    """
    doc = storage_mgr.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    page_path = get_rendered_page_path(storage_mgr.rendered_dir, doc_id, page_num)
    if not page_path.exists():
        raise HTTPException(status_code=404, detail="Page render image not found")

    from backend.app.services.forensics.image_forensics import generate_forensic_report
    report = generate_forensic_report(page_path, doc_id, page_num=page_num)
    report.heatmap_url = f"/documents/{doc_id}/pages/{page_num}/forensics/heatmap"
    return report


@router.get("/documents/{doc_id}/pages/{page_num}/forensics/heatmap")
def get_document_tamper_heatmap(doc_id: str, page_num: int):
    """
    Returns visual tampering localization heatmap PNG (blended ELA and noise residuals).
    """
    heatmap_path = storage_mgr.rendered_dir / doc_id / f"forensic_heatmap_{page_num}.png"
    if not heatmap_path.exists():
        # Generate on the fly if needed
        page_path = get_rendered_page_path(storage_mgr.rendered_dir, doc_id, page_num)
        if not page_path.exists():
            raise HTTPException(status_code=404, detail="Original page image not found")
        from backend.app.services.forensics.image_forensics import generate_tamper_heatmap
        generate_tamper_heatmap(page_path, heatmap_path)

    if not heatmap_path.exists():
        raise HTTPException(status_code=500, detail="Failed to render tampering heatmap")

    return FileResponse(str(heatmap_path), media_type="image/png")


@router.get("/investigations/{inv_id}/findings", response_model=List[Finding])
def get_investigation_findings(inv_id: str):
    return storage_mgr.get_findings(inv_id)


@router.get("/findings/{finding_id}", response_model=Finding)
def get_finding_by_id(finding_id: str):
    finding = storage_mgr.get_finding(finding_id)
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
    return finding


@router.get("/investigations/{inv_id}/comparison")
def get_investigation_cross_comparison(inv_id: str):
    inv = storage_mgr.get_investigation(inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")

    docs = storage_mgr.get_documents(inv_id)
    cross_engine = CrossDocEngine()
    _, matrix = cross_engine.correlate_investigation(inv_id, docs)
    return matrix


@router.get("/investigations/{inv_id}/status")
def get_investigation_status(inv_id: str):
    inv = storage_mgr.get_investigation(inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")

    doc_statuses = [{"doc_id": d.doc_id, "filename": d.filename, "status": d.status.value, "type": d.type.value} for d in inv.documents]
    all_processed = all(d.status.value in ("processed", "unsupported", "error", "encrypted", "ocr_failed") for d in inv.documents)

    return {
        "investigation_id": inv_id,
        "is_complete": all_processed,
        "total_documents": len(inv.documents),
        "documents": doc_statuses,
    }


@router.get("/documents/{doc_id}", response_model=DocumentRecord)
def get_document_details(doc_id: str):
    doc = storage_mgr.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.get("/documents/{doc_id}/pages/{page_num}/image")
def get_document_page_image(doc_id: str, page_num: int):
    page_path = get_rendered_page_path(storage_mgr.rendered_dir, doc_id, page_num)
    if not page_path.exists():
        raise HTTPException(status_code=404, detail=f"Page {page_num} image not found for document {doc_id}")
    return FileResponse(str(page_path), media_type="image/png")


@router.get("/documents/{doc_id}/fields", response_model=List[ExtractedField])
def get_document_fields(doc_id: str):
    fields = storage_mgr.get_fields(doc_id)
    # Mask PII values by default
    masked_fields = []
    for f in fields:
        copy_f = f.model_copy()
        if copy_f.name in ("aadhaar_number", "pan_number") and isinstance(copy_f.value, str):
            copy_f.value = mask_field_value(copy_f.name, copy_f.value)
            copy_f.raw_text = mask_field_value(copy_f.name, copy_f.raw_text)
        masked_fields.append(copy_f)
    return masked_fields


@router.post("/fields/{field_id}/reveal")
def reveal_pii_field(field_id: str, user_id: str = "OFFICER-DEFAULT"):
    """
    Explicitly reveals the unmasked value of a PII field.
    Audit logs the reveal event.
    """
    target = storage_mgr.get_field_by_id(field_id)
    if not target:
        raise HTTPException(status_code=404, detail="Field not found")

    doc_id = target.doc_id
    # Log audit event
    audit_service.log_event(
        investigation_id="GLOBAL",
        actor=user_id,
        action="pii_revealed",
        object_id=field_id,
        details={"field_name": target.name, "doc_id": doc_id},
    )

    return {
        "field_id": field_id,
        "name": target.name,
        "unmasked_value": target.value,
        "unmasked_raw_text": target.raw_text,
    }


@router.get("/investigations/{inv_id}/audit", response_model=List[AuditEvent])
def get_investigation_audit_trail(inv_id: str):
    return audit_service.get_events(inv_id)


@router.get("/investigations/{inv_id}/audit/verify")
def verify_audit_trail(inv_id: str):
    is_valid, broken_seq = audit_service.verify_chain(inv_id)
    return {
        "investigation_id": inv_id,
        "chain_valid": is_valid,
        "broken_at_seq": broken_seq,
        "status": "valid" if is_valid else f"broken at seq {broken_seq}",
    }



# --------------------------------------------------------------------------
# Phase 5: Human Review & Case Decision endpoints
# --------------------------------------------------------------------------

from pydantic import BaseModel as _PydanticBase


class _FindingReviewRequest(_PydanticBase):
    decision: ReviewDecision
    reason: str = ""
    reviewer_id: str = "OFFICER-DEFAULT"


class _CaseDecisionRequest(_PydanticBase):
    decision: CaseDecisionType
    outcome_note: str
    decided_by: str = "OFFICER-DEFAULT"


@router.post("/findings/{finding_id}/review")
def review_finding(finding_id: str, body: _FindingReviewRequest):
    """
    Human reviewer records a decision on a single finding.
    - confirm: marks as confirmed_by_reviewer
    - dismiss: must include a reason
    - escalate: keeps status as requires_investigation (reviewer noted intent)
    """
    finding = storage_mgr.get_finding(finding_id)
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    if body.decision == ReviewDecision.DISMISS and not body.reason.strip():
        raise HTTPException(status_code=422, detail="Dismiss requires a reason.")

    now_iso = datetime.now(timezone.utc).isoformat()

    # Map decision to status
    if body.decision == ReviewDecision.CONFIRM:
        new_status = FindingStatus.CONFIRMED_BY_REVIEWER
    elif body.decision == ReviewDecision.DISMISS:
        new_status = FindingStatus.DISMISSED
    else:  # escalate — keep requiring investigation
        new_status = FindingStatus.REQUIRES_INVESTIGATION

    reviewer_action = ReviewerAction(
        decision=body.decision,
        reason=body.reason,
        by=body.reviewer_id,
        at=now_iso,
    )

    storage_mgr.update_finding_review(finding_id, new_status, reviewer_action)

    # Audit trail
    inv_id = storage_mgr.get_investigation_id_for_finding(finding_id) or "UNKNOWN"
    audit_service.log_event(
        investigation_id=inv_id,
        actor=body.reviewer_id,
        action="finding_reviewed",
        object_id=finding_id,
        details={
            "decision": body.decision.value,
            "reason": body.reason,
            "new_status": new_status.value,
        },
    )

    updated = storage_mgr.get_finding(finding_id)
    return updated


@router.post("/investigations/{inv_id}/decision")
def record_case_decision(inv_id: str, body: _CaseDecisionRequest):
    """
    Human investigator records a final case decision.
    The human may choose to rely on, partially rely on, or disregard tool output entirely.
    """
    inv = storage_mgr.get_investigation(inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")

    now_iso = datetime.now(timezone.utc).isoformat()
    findings = storage_mgr.get_findings(inv_id)

    case_decision = CaseDecision(
        decision=body.decision,
        outcome_note=body.outcome_note,
        decided_by=body.decided_by,
        decided_at=now_iso,
        findings_reviewed=len(findings),
    )
    storage_mgr.update_case_decision(inv_id, case_decision)

    audit_service.log_event(
        investigation_id=inv_id,
        actor=body.decided_by,
        action="case_decision_recorded",
        object_id=inv_id,
        details={
            "decision": body.decision.value,
            "outcome_note": body.outcome_note,
            "findings_reviewed": len(findings),
        },
    )

    return storage_mgr.get_investigation(inv_id)


# --------------------------------------------------------------------------
# Phase 5: Dossier PDF generation & download
# --------------------------------------------------------------------------

@router.get("/investigations/{inv_id}/dossier")
def download_dossier(inv_id: str):
    """
    Generates and returns the investigation dossier PDF.
    DRAFT watermark until a case decision is recorded.
    """
    inv = storage_mgr.get_investigation(inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")

    findings = storage_mgr.get_findings(inv_id)
    audit_events = audit_service.get_events(inv_id)

    dossier_path = generate_dossier(
        investigation=inv,
        findings=findings,
        audit_events=audit_events,
        rendered_dir=storage_mgr.rendered_dir,
        output_dir=DATA_DIR / "dossiers",
    )

    audit_service.log_event(
        investigation_id=inv_id,
        actor="system",
        action="dossier_generated",
        object_id=inv_id,
        details={"is_draft": inv.case_decision is None},
    )

    return FileResponse(
        str(dossier_path),
        media_type="application/pdf",
        filename=f"dossier_{inv_id}.pdf",
    )


class _LlmClassifyRequest(_PydanticBase):
    api_key: Optional[str] = None
    provider: Optional[str] = "auto"


@router.post("/documents/{doc_id}/classify-llm", response_model=DocumentRecord)
def classify_document_llm(doc_id: str, body: Optional[_LlmClassifyRequest] = None):
    """
    Classifies a specific document using an LLM (Gemini, Groq, or Local Semantic Engine).
    Updates and returns the document with classification type, accuracy score, and explanatory reasoning.
    """
    doc = storage_mgr.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    file_path = storage_mgr.get_document_file_path(doc_id)
    inv_id = storage_mgr.get_investigation_id_for_document(doc_id) or "GLOBAL"

    text = ""
    if file_path and file_path.exists():
        suffix = file_path.suffix.lower()
        if suffix == ".pdf":
            from backend.app.services.extraction.text_layer import extract_pdf_text_layer
            pages = extract_pdf_text_layer(file_path)
            text = "\n".join(p.get("full_text", "") for p in pages)
        elif suffix == ".docx":
            from backend.app.services.extraction.office_text import extract_docx_text
            pages = extract_docx_text(file_path)
            text = "\n".join(p.get("full_text", "") for p in pages)
        elif suffix in (".xlsx", ".xls"):
            from backend.app.services.extraction.office_text import extract_xlsx_text
            pages = extract_xlsx_text(file_path)
            text = "\n".join(p.get("full_text", "") for p in pages)

    if not text.strip():
        # Fallback to fields text
        fields = storage_mgr.get_fields(doc_id)
        text = " ".join(f"{f.name}: {f.value}" for f in fields)

    api_key = body.api_key if body else None
    provider = body.provider if body else "auto"

    from backend.app.services.llm_classification import classify_document_with_llm
    llm_res = classify_document_with_llm(text, api_key=api_key, provider=provider)

    doc.llm_type = llm_res.classification_type
    doc.llm_accuracy = llm_res.accuracy
    doc.llm_reasoning = llm_res.reasoning
    doc.llm_provider = llm_res.provider

    # Also update primary type if primary was unsupported but LLM confidence is high
    if doc.type == DocumentType.UNSUPPORTED and llm_res.classification_type != DocumentType.UNSUPPORTED and llm_res.accuracy >= 0.85:
        doc.type = llm_res.classification_type
        doc.type_confidence = llm_res.accuracy
        doc.status = DocumentStatus.PROCESSED
        doc.error_message = None

    storage_mgr.save_document(inv_id, doc, str(file_path or ""))
    return doc


@router.post("/investigations/{inv_id}/classify-llm", response_model=Investigation)
def classify_investigation_documents_llm(inv_id: str, body: Optional[_LlmClassifyRequest] = None):
    """
    Runs LLM classification across all documents in an investigation.
    """
    inv = storage_mgr.get_investigation(inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")

    docs = storage_mgr.get_documents(inv_id)
    for doc in docs:
        classify_document_llm(doc.doc_id, body=body)

    return storage_mgr.get_investigation(inv_id)

