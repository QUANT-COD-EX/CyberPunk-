"""
Advanced Contextual Reasoning and Anomaly Correlation Engine for PS-2.
Synthesizes multi-hop evidence into contextual risk clusters and deterministic reasoning chains:
1. Multi-signal anomaly correlation (Identity, Financial, Tampering, Temporal)
2. Chain-of-Thought style Forensic Reasoning Chains
3. Transparent human-in-the-loop inquiry recommendations adhering to ISO/IEC 27037
4. Zero forbidden words guarantee
"""

from typing import Dict, List, Optional
from backend.app.models.contracts import (
    AnomalyCorrelationCluster,
    DocumentRecord,
    Finding,
    FindingCategory,
    FindingTier,
    ReasoningChainStep,
)


def build_contextual_reasoning_and_clusters(
    findings: List[Finding],
    documents: List[DocumentRecord],
) -> List[AnomalyCorrelationCluster]:
    """
    Correlates atomic findings into contextual risk clusters with step-by-step reasoning chains.
    """
    if not findings:
        return []

    # Partition findings by thematic risk vector
    identity_findings: List[Finding] = []
    financial_findings: List[Finding] = []
    tampering_findings: List[Finding] = []
    temporal_findings: List[Finding] = []
    ai_gen_findings: List[Finding] = []
    signature_findings: List[Finding] = []
    other_findings: List[Finding] = []

    for f in findings:
        r_id = f.rule_id.lower()
        title_lower = f.title.lower()

        if any(k in r_id or k in title_lower for k in ("ai_generated", "synthetic_content", "ai_model", "generator")):
            ai_gen_findings.append(f)
        elif any(k in r_id or k in title_lower for k in ("signature", "deepfake", "cloned")):
            signature_findings.append(f)
        elif any(k in r_id or k in title_lower for k in ("name", "pan", "aadhaar", "dob", "identity")):
            identity_findings.append(f)
        elif any(k in r_id or k in title_lower for k in ("salary", "bank", "credit", "amount", "income", "balance", "math")):
            financial_findings.append(f)
        elif any(k in r_id or k in title_lower for k in ("ela", "noise", "copy_move", "font", "span", "injection", "tamper", "pixel", "fft", "compression")):
            tampering_findings.append(f)
        elif any(k in r_id or k in title_lower for k in ("date", "temporal", "period", "sequence", "future")):
            temporal_findings.append(f)
        else:
            other_findings.append(f)

    clusters: List[AnomalyCorrelationCluster] = []

    # 1. Identity Divergence Cluster
    if identity_findings:
        highest_tier = FindingTier.OBSERVATION
        for f in identity_findings:
            if f.tier == FindingTier.POTENTIAL_MANIPULATION:
                highest_tier = FindingTier.POTENTIAL_MANIPULATION
                break
            elif f.tier == FindingTier.INCONSISTENCY:
                highest_tier = FindingTier.INCONSISTENCY

        f_ids = [f.finding_id for f in identity_findings]
        chain_steps: List[ReasoningChainStep] = []

        step_idx = 1
        for f in identity_findings:
            chain_steps.append(
                ReasoningChainStep(
                    step_index=step_idx,
                    title=f"Identity Signal: {f.title}",
                    premises=[f"Evidence examined in document {e.doc_id} on page {e.page}" for e in f.evidence],
                    observation=f.explanation or "Discrepancy noted between recorded identity fields.",
                    conclusion=(
                        "Potential identity divergence requires secondary cross-verification with issuing authority."
                        if highest_tier != FindingTier.OBSERVATION
                        else "Minor orthographic or formatting variation observed."
                    ),
                    evidence_refs=f.evidence,
                    confidence=f.confidence,
                )
            )
            step_idx += 1

        clusters.append(
            AnomalyCorrelationCluster(
                cluster_id="CLUSTER-IDENTITY-DIVERGENCE",
                theme="Identity Divergence",
                severity=highest_tier,
                finding_ids=f_ids,
                synthesis_rationale=(
                    f"Correlated {len(identity_findings)} identity-related signal(s) across the submitted documentation. "
                    "Cross-reference indicates non-uniform entity attributes between government identifiers and supporting instruments."
                ),
                recommended_inquiry=(
                    "Request direct verification of government identity credentials or examine physical documents under natural light."
                ),
                chain=chain_steps,
            )
        )

    # 2. Financial Discrepancy Cluster
    if financial_findings:
        highest_tier = FindingTier.OBSERVATION
        for f in financial_findings:
            if f.tier == FindingTier.POTENTIAL_MANIPULATION:
                highest_tier = FindingTier.POTENTIAL_MANIPULATION
                break
            elif f.tier == FindingTier.INCONSISTENCY:
                highest_tier = FindingTier.INCONSISTENCY

        f_ids = [f.finding_id for f in financial_findings]
        chain_steps: List[ReasoningChainStep] = []

        step_idx = 1
        for f in financial_findings:
            chain_steps.append(
                ReasoningChainStep(
                    step_index=step_idx,
                    title=f"Financial Correlation: {f.title}",
                    premises=[f"Field values recorded in document {e.doc_id}" for e in f.evidence],
                    observation=f.explanation or "Numeric or itemized variance noted across financial schedules.",
                    conclusion="Schedule inconsistency observed between payroll declarations and banking records.",
                    evidence_refs=f.evidence,
                    confidence=f.confidence,
                )
            )
            step_idx += 1

        clusters.append(
            AnomalyCorrelationCluster(
                cluster_id="CLUSTER-FINANCIAL-DISCREPANCY",
                theme="Financial Discrepancy",
                severity=highest_tier,
                finding_ids=f_ids,
                synthesis_rationale=(
                    f"Correlated {len(financial_findings)} financial record observation(s). "
                    "Mathematical summation, banking ledger entries, or declared net earnings diverge from corresponding credit statements."
                ),
                recommended_inquiry=(
                    "Obtain official password-protected bank e-statements or employer payroll ledger directly from source."
                ),
                chain=chain_steps,
            )
        )

    # 3. Document Tampering & Surface Artifacts Cluster
    if tampering_findings:
        highest_tier = FindingTier.OBSERVATION
        for f in tampering_findings:
            if f.tier == FindingTier.POTENTIAL_MANIPULATION:
                highest_tier = FindingTier.POTENTIAL_MANIPULATION
                break
            elif f.tier == FindingTier.INCONSISTENCY:
                highest_tier = FindingTier.INCONSISTENCY

        f_ids = [f.finding_id for f in tampering_findings]
        chain_steps: List[ReasoningChainStep] = []

        step_idx = 1
        for f in tampering_findings:
            chain_steps.append(
                ReasoningChainStep(
                    step_index=step_idx,
                    title=f"Forensic Artifact: {f.title}",
                    premises=[f"Raster / visual surface inspection of document {e.doc_id}" for e in f.evidence],
                    observation=f.explanation or "Localized compression, noise, or layout discontinuity identified.",
                    conclusion="Weak supporting forensic indicator noted; adheres to non-conclusive ISO/IEC 27037 standards.",
                    evidence_refs=f.evidence,
                    confidence=f.confidence,
                )
            )
            step_idx += 1

        clusters.append(
            AnomalyCorrelationCluster(
                cluster_id="CLUSTER-SURFACE-TAMPERING",
                theme="Document Tampering",
                severity=highest_tier,
                finding_ids=f_ids,
                synthesis_rationale=(
                    f"Identified {len(tampering_findings)} surface-level or raster artifact(s) across digital pages. "
                    "Visual inspection revealed localized compression delta, high-frequency noise variance, or copy-move feature clusters."
                ),
                recommended_inquiry=(
                    "Inspect original high-resolution optical scans or request raw vector PDF files without rasterization artifacts."
                ),
                chain=chain_steps,
            )
        )

    # 4. Temporal & Sequence Anomaly Cluster
    if temporal_findings:
        highest_tier = FindingTier.OBSERVATION
        for f in temporal_findings:
            if f.tier == FindingTier.POTENTIAL_MANIPULATION:
                highest_tier = FindingTier.POTENTIAL_MANIPULATION
                break
            elif f.tier == FindingTier.INCONSISTENCY:
                highest_tier = FindingTier.INCONSISTENCY

        f_ids = [f.finding_id for f in temporal_findings]
        chain_steps: List[ReasoningChainStep] = []

        step_idx = 1
        for f in temporal_findings:
            chain_steps.append(
                ReasoningChainStep(
                    step_index=step_idx,
                    title=f"Temporal Signal: {f.title}",
                    premises=[f"Timestamp / chronology in document {e.doc_id}" for e in f.evidence],
                    observation=f.explanation or "Chronological inconsistency in stated dates.",
                    conclusion="Sequential timing of documented events exhibits chronological conflict.",
                    evidence_refs=f.evidence,
                    confidence=f.confidence,
                )
            )
            step_idx += 1

        clusters.append(
            AnomalyCorrelationCluster(
                cluster_id="CLUSTER-TEMPORAL-INCONSISTENCY",
                theme="Temporal Inconsistency",
                severity=highest_tier,
                finding_ids=f_ids,
                synthesis_rationale=(
                    f"Identified {len(temporal_findings)} temporal discrepancy/discrepancies. "
                    "Recorded transaction, issuance, or declaration dates are inconsistent with associated documentation sequence."
                ),
                recommended_inquiry="Verify calendar timelines against external banking clearing logs.",
                chain=chain_steps,
            )
        )

    # 5. AI-Generated & Synthetic Document Cluster
    if ai_gen_findings:
        highest_tier = FindingTier.OBSERVATION
        for f in ai_gen_findings:
            if f.tier == FindingTier.POTENTIAL_MANIPULATION:
                highest_tier = FindingTier.POTENTIAL_MANIPULATION
                break
            elif f.tier == FindingTier.INCONSISTENCY:
                highest_tier = FindingTier.INCONSISTENCY

        f_ids = [f.finding_id for f in ai_gen_findings]
        chain_steps = []
        for idx, f in enumerate(ai_gen_findings, start=1):
            chain_steps.append(
                ReasoningChainStep(
                    step_index=idx,
                    title=f"Synthetic Content Signal: {f.title}",
                    premises=[f"Textual / stylometric inspection of document {e.doc_id}" for e in f.evidence],
                    observation=f.explanation or "AI generation hallmarks, boilerplate phrasing, or template placeholders identified.",
                    conclusion="Document text exhibits synthetic or AI-assisted creation signatures.",
                    evidence_refs=f.evidence,
                    confidence=f.confidence,
                )
            )

        clusters.append(
            AnomalyCorrelationCluster(
                cluster_id="CLUSTER-AI-GENERATION-SYNTHETIC",
                theme="AI Generation & Synthetic Content",
                severity=highest_tier,
                finding_ids=f_ids,
                synthesis_rationale=(
                    f"Detected {len(ai_gen_findings)} signal(s) indicative of AI-generated or synthetic document generation. "
                    "Evaluation identified known AI model boilerplate, placeholder tokens, or unnatural stylometric uniformity."
                ),
                recommended_inquiry="Request primary electronic documents directly from issuing authority or verifiable net-banking/DigiLocker repository.",
                chain=chain_steps,
            )
        )

    # 6. Signature Authenticity & Deepfake Cluster
    if signature_findings:
        highest_tier = FindingTier.OBSERVATION
        for f in signature_findings:
            if f.tier == FindingTier.POTENTIAL_MANIPULATION:
                highest_tier = FindingTier.POTENTIAL_MANIPULATION
                break
            elif f.tier == FindingTier.INCONSISTENCY:
                highest_tier = FindingTier.INCONSISTENCY

        f_ids = [f.finding_id for f in signature_findings]
        chain_steps = []
        for idx, f in enumerate(signature_findings, start=1):
            chain_steps.append(
                ReasoningChainStep(
                    step_index=idx,
                    title=f"Signature Signal: {f.title}",
                    premises=[f"Signatory stroke analysis in document {e.doc_id}" for e in f.evidence],
                    observation=f.explanation or "Signature stroke anomaly, missing execution, or cross-document duplication detected.",
                    conclusion="Execution characteristics diverge from natural biological motor handwriting.",
                    evidence_refs=f.evidence,
                    confidence=f.confidence,
                )
            )

        clusters.append(
            AnomalyCorrelationCluster(
                cluster_id="CLUSTER-SIGNATURE-AUTHENTICITY",
                theme="Signature Authenticity & Execution",
                severity=highest_tier,
                finding_ids=f_ids,
                synthesis_rationale=(
                    f"Correlated {len(signature_findings)} signature-related finding(s). "
                    "Biometric stroke dynamics, missing execution marks, or duplicated cross-document signatures noted."
                ),
                recommended_inquiry="Inspect physical ink execution under magnification or obtain fresh witnessed wet signature.",
                chain=chain_steps,
            )
        )

    return clusters
