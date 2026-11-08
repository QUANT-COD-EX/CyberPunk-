"""
Unified deterministic rules execution runner.
Evaluates pure D1 validation rules and within-document structural checks across all documents.
Transforms failing RuleResults into formal Finding contracts.
"""

from typing import Dict, List, Optional
from backend.app.models.contracts import (
    DocumentRecord,
    DocumentType,
    Finding,
    FindingCategory,
    FindingStatus,
    FindingStrength,
    FindingTier,
    ReviewerAction,
    RuleResult,
    RuleStatus,
)
from backend.app.services.rules.aadhaar_qr_match import validate_aadhaar_qr_against_printed
from backend.app.services.rules.bank import validate_bank_running_balance
from backend.app.services.rules.pan import validate_pan_structure
from backend.app.services.rules.salary import validate_salary_arithmetic
from backend.app.services.rules.verhoeff import validate_aadhaar_number
from backend.app.services.rules.within_doc import validate_within_document_structure
from backend.app.services.forensics.pdf_native import (
    check_pdf_metadata,
    check_incremental_updates,
    check_font_inconsistencies,
    check_hidden_text_spans,
    check_text_layer_vs_ocr_diff,
    check_signature_region,
    check_baseline_alignment,
)
from backend.app.services.forensics.image_forensics import run_image_forensics_checks
from backend.app.services.forensics.ai_generated import detect_ai_generated_document
from backend.app.services.forensics.signature_forensics import (
    analyze_signature_stroke_authenticity,
    extract_signature_crop,
)
from pathlib import Path


def execute_forensics_checks(
    doc: DocumentRecord,
    doc_file_path: Path,
    rendered_pages: List[Path],
    text_spans: Optional[List[Dict]] = None,
    ocr_words: Optional[List[Dict]] = None,
) -> List[Finding]:
    """Executes PDF-native, image-level, AI-generated, and signature forensic checks."""
    findings: List[Finding] = []
    suffix = doc_file_path.suffix.lower()

    # 1. AI-generated document and synthetic content detection
    doc_text_corpus = " ".join(f.raw_text or str(f.value) for f in doc.fields)
    ai_findings, _, _, _ = detect_ai_generated_document(
        text=doc_text_corpus,
        doc_path=doc_file_path if suffix == ".pdf" else None,
        doc_id=doc.doc_id,
    )
    findings.extend(ai_findings)

    if suffix == ".pdf":
        # 2. Metadata anomalies (editing software)
        findings.extend(check_pdf_metadata(doc_file_path, doc.doc_id))

        # 3. Incremental updates (%%EOF count)
        findings.extend(check_incremental_updates(doc_file_path, doc.doc_id))

        # 4. Font inconsistencies in sibling spans
        findings.extend(check_font_inconsistencies(doc_file_path, doc.doc_id))

        # 5. Hidden text (microscopic, white-on-white)
        hidden_results = check_hidden_text_spans(doc_file_path, doc.doc_id)
        for f, _ in hidden_results:
            findings.append(f)

        # 6. Text-layer vs OCR diff if both are available
        if text_spans and ocr_words:
            findings.extend(check_text_layer_vs_ocr_diff(text_spans, ocr_words, doc.doc_id, page_num=1))

        # 7. Signature presence and field overlap check
        findings.extend(check_signature_region(doc_file_path, doc.doc_id, rendered_pages, doc.fields))

        # 8. Baseline alignment disparity check
        findings.extend(check_baseline_alignment(doc_file_path, doc.doc_id))

    # 9. Deepfake / Synthetic Signature Stroke Analysis
    if rendered_pages and rendered_pages[0].exists():
        sig_field = next((f for f in doc.fields if "signature" in f.name.lower()), None)
        target_box = sig_field.bbox if sig_field else None
        if not target_box and doc.type.value in ("loan_application", "declaration_15g", "payment_instruction"):
            target_box = [100, 680, 450, 780]

        if target_box:
            crop = extract_signature_crop(rendered_pages[0], target_box)
            if crop is not None:
                sig_findings, _, _ = analyze_signature_stroke_authenticity(
                    crop_bgr=crop,
                    doc_id=doc.doc_id,
                    page_num=1,
                    bbox=target_box,
                )
                findings.extend(sig_findings)

    # 10. Sophisticated Image forensics (ELA, 2D FFT, noise discrepancies, copy-move)
    if rendered_pages and rendered_pages[0].exists():
        img_findings = run_image_forensics_checks(rendered_pages[0], doc.doc_id, page_num=1)
        findings.extend(img_findings)

    return findings


def rule_result_to_finding(res: RuleResult, doc_id: str, category: FindingCategory = FindingCategory.WITHIN_DOCUMENT) -> Finding:
    """Converts a failing RuleResult into a Finding contract."""
    tier = res.tier or FindingTier.INCONSISTENCY
    strength = res.strength or FindingStrength.STRONG
    finding_id = f"ANM-{res.rule_id[:8].upper()}-{doc_id}"

    return Finding(
        finding_id=finding_id,
        tier=tier,
        category=category,
        rule_id=res.rule_id,
        title=res.title or f"Rule validation failure: {res.rule_id}",
        evidence=res.evidence,
        signals=res.signals or [res.rule_id],
        strength=strength,
        confidence=0.92,
        status=FindingStatus.REQUIRES_INVESTIGATION,
        explanation=res.detail,
        reviewer=ReviewerAction(),
    )


def execute_document_rules(doc: DocumentRecord) -> List[Finding]:
    """Runs all applicable deterministic rules for a single document."""
    findings: List[Finding] = []
    fields_by_name = {f.name: f.value for f in doc.fields}
    field_records = {f.name: f for f in doc.fields}

    # 1. Within-document structural checks
    within_doc_results = validate_within_document_structure(doc.doc_id, doc.type, doc.fields)
    for r in within_doc_results:
        if r.result == RuleStatus.FAIL:
            findings.append(rule_result_to_finding(r, doc.doc_id))

    # 2. Document-specific D1 rules
    if doc.type == DocumentType.AADHAAR:
        # Verhoeff checksum
        num_f = field_records.get("aadhaar_number")
        if num_f:
            verhoeff_res = validate_aadhaar_number(
                aadhaar_number=str(num_f.value),
                field_id=num_f.field_id,
                doc_id=doc.doc_id,
                page=num_f.page,
                bbox=num_f.bbox,
            )
            if verhoeff_res.result == RuleStatus.FAIL:
                findings.append(rule_result_to_finding(verhoeff_res, doc.doc_id))

        # QR vs Printed text
        qr_f = field_records.get("aadhaar_qr_payload")
        if qr_f and isinstance(qr_f.value, dict):
            qr_res = validate_aadhaar_qr_against_printed(
                qr_payload=qr_f.value,
                printed_fields=fields_by_name,
                qr_box=qr_f.bbox,
                doc_id=doc.doc_id,
                page=qr_f.page,
            )
            if qr_res.result == RuleStatus.FAIL:
                findings.append(rule_result_to_finding(qr_res, doc.doc_id))

    elif doc.type == DocumentType.PAN:
        pan_f = field_records.get("pan_number")
        name_val = fields_by_name.get("name")
        if pan_f:
            pan_res = validate_pan_structure(
                pan_number=str(pan_f.value),
                holder_name=str(name_val) if name_val else None,
                field_id=pan_f.field_id,
                doc_id=doc.doc_id,
                page=pan_f.page,
                bbox=pan_f.bbox,
            )
            if pan_res.result == RuleStatus.FAIL:
                findings.append(rule_result_to_finding(pan_res, doc.doc_id))

    elif doc.type == DocumentType.SALARY_SLIP:
        salary_results = validate_salary_arithmetic(
            fields_dict=fields_by_name,
            field_records_map=field_records,
            doc_id=doc.doc_id,
            page=1,
        )
        for r in salary_results:
            if r.result == RuleStatus.FAIL:
                findings.append(rule_result_to_finding(r, doc.doc_id))

    elif doc.type == DocumentType.BANK_STATEMENT:
        tx_f = field_records.get("transactions")
        open_f = field_records.get("opening_balance")
        close_f = field_records.get("closing_balance")

        tx_list = tx_f.value if tx_f and isinstance(tx_f.value, list) else []
        open_val = float(open_f.value) if open_f and open_f.value is not None else None
        close_val = float(close_f.value) if close_f and close_f.value is not None else None

        if tx_list:
            bank_res = validate_bank_running_balance(
                transactions=tx_list,
                opening_balance=open_val,
                closing_balance=close_val,
                field_id=tx_f.field_id if tx_f else f"F-{doc.doc_id}-tx",
                doc_id=doc.doc_id,
                page=tx_f.page if tx_f else 1,
                table_bbox=tx_f.bbox if tx_f else [0, 0, 0, 0],
            )
            if bank_res.result == RuleStatus.FAIL:
                findings.append(rule_result_to_finding(bank_res, doc.doc_id))

    return findings
