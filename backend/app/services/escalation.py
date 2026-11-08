"""
Three-tier classification, signal convergence escalation, and review priority scoring.
Rules:
1. Observation: a single factual observation
2. Inconsistency: two contradicting facts (e.g. cross-doc mismatch or internal math discrepancy)
3. Potential manipulation: REQUIRES >= 2 independent signal types converging on the same field or region
   - Single-signal findings NEVER exceed Inconsistency
   - Weak signals (ELA) alone NEVER exceed Observation
   - Terminology: "Requires investigation" (NEVER "fraud" or "forged")

Review Priority Points (from docs/REVIEW_PRIORITY_POINTS.md):
- High: >= 45 points
- Medium: 20 - 44 points
- Low: < 20 points
"""

from typing import Dict, List, Set, Tuple
from backend.app.models.contracts import (
    Finding,
    FindingStrength,
    FindingTier,
    PriorityBreakdownItem,
    ReviewPriority,
    EvidenceItem,
)

# Standard points matrix aligned with docs/REVIEW_PRIORITY_POINTS.md
RULE_POINTS_MATRIX: Dict[str, int] = {
    "salary_net_pay_calc": 25,
    "salary_credit_match": 25,
    "bank_balance_continuity": 30,
    "dob_match": 20,
    "pan_structure": 20,
    "pan_cross_match": 20,
    "name_match_conflict": 15,
    "name_match_review": 5,
    "aadhaar_qr_text_mismatch": 35,
    "aadhaar_verhoeff": 20,
    "producer_editing_tool": 10,
    "incremental_updates_flag": 10,
    "font_anomaly": 20,
    "font_size_anomaly": 15,
    "layer_ocr_mismatch": 25,
    "prompt_injection_pattern": 20,
    "microscopic_text_detected": 15,
    "white_on_white_text_detected": 20,
    "ela_discontinuity": 5,
    "missing_mandatory_field": 10,
    "duplicate_conflicting_field": 15,
    "loan_income_vs_salary": 20,
    "loan_pan_mismatch": 20,
    "loan_dob_mismatch": 20,
    "g15_income_vs_salary": 20,
    "g15_pan_mismatch": 20,
    "payment_amount_not_in_bank": 25,
    "payment_account_mismatch": 10,
    "payment_amount_invalid": 5,
    "loan_amount_invalid": 5,
    "signature_region_empty": 5,
    "signature_placement_overlap": 10,
    "baseline_alignment_anomaly": 10,
    "ai_generated_document_detected": 25,
    "synthetic_signature_detected": 20,
    "cloned_signature_replication": 30,
    "fft_spectral_discontinuity": 10,
    "double_compression_discontinuity": 10,
}

DEFAULT_POINTS = 10


def boxes_overlap_or_close(box1: List[int], box2: List[int], tolerance: int = 50) -> bool:
    """Checks whether two bounding boxes overlap or reside in close spatial proximity."""
    x_overlap = max(0, min(box1[2], box2[2]) - max(box1[0], box2[0]))
    y_overlap = max(0, min(box1[3], box2[3]) - max(box1[1], box2[1]))
    if x_overlap > 0 and y_overlap > 0:
        return True
    # Close horizontal & vertical proximity
    dx = max(0, max(box1[0], box2[0]) - min(box1[2], box2[2]))
    dy = max(0, max(box1[1], box2[1]) - min(box1[3], box2[3]))
    return dx <= tolerance and dy <= tolerance


class EscalationEngine:
    def __init__(self, points_matrix: Dict[str, int] = RULE_POINTS_MATRIX):
        self.points_matrix = points_matrix

    def escalate_findings(self, findings: List[Finding]) -> List[Finding]:
        """
        Applies strict multi-signal convergence escalation rule:
        If >= 2 independent signal types converge on the same field or coordinate region,
        escalates to POTENTIAL_MANIPULATION.
        Weak signals alone cannot escalate past Observation.
        Single signals cannot escalate past Inconsistency.
        """
        if not findings or len(findings) < 2:
            return findings

        # Group findings by document and spatial proximity
        escalated_list = [f.model_copy() for f in findings]

        for i in range(len(escalated_list)):
            f1 = escalated_list[i]
            converging_signals: Set[str] = set(f1.signals)
            converging_evidence: List[EvidenceItem] = list(f1.evidence)
            related_ids: Set[str] = set()

            for j in range(len(escalated_list)):
                if i == j:
                    continue
                f2 = escalated_list[j]

                # Check if f1 and f2 share an evidence location
                has_spatial_convergence = False
                for ev1 in f1.evidence:
                    for ev2 in f2.evidence:
                        if ev1.doc_id == ev2.doc_id and ev1.page == ev2.page:
                            if boxes_overlap_or_close(ev1.bbox, ev2.bbox):
                                has_spatial_convergence = True
                                break
                    if has_spatial_convergence:
                        break

                if has_spatial_convergence:
                    converging_signals.update(f2.signals)
                    related_ids.add(f2.finding_id)
                    for ev in f2.evidence:
                        if ev not in converging_evidence:
                            converging_evidence.append(ev)

            f1.related_finding_ids = sorted(list(related_ids))

            # Weak signals cannot be escalated by themselves
            if f1.strength == FindingStrength.WEAK and len(f1.signals) <= 1:
                continue

            # Check convergence rule: >= 2 independent signal types on same region
            if len(converging_signals) >= 2:
                # Do not escalate if only weak signals
                non_weak_signals = [s for s in converging_signals if "ela" not in s.lower()]
                if len(non_weak_signals) >= 2:
                    f1.tier = FindingTier.POTENTIAL_MANIPULATION
                    f1.strength = FindingStrength.STRONG
                    f1.signals = sorted(list(converging_signals))

        return escalated_list

    def calculate_review_priority(
        self,
        findings: List[Finding],
    ) -> Tuple[ReviewPriority, int, List[PriorityBreakdownItem]]:
        """
        Computes total points and determines Review Priority:
        High (>= 45), Medium (20 - 44), Low (< 20).
        Returns: (priority, total_score, breakdown_list)
        """
        breakdown: List[PriorityBreakdownItem] = []
        seen_rules: Set[str] = set()
        total_score = 0

        for f in findings:
            rule_id = f.rule_id
            pts = self.points_matrix.get(rule_id, DEFAULT_POINTS)

            # If escalated to potential_manipulation, add 15 bonus urgency points
            if f.tier == FindingTier.POTENTIAL_MANIPULATION:
                pts += 15

            # Deduplicate multiple hits of same rule to avoid points explosion
            if rule_id not in seen_rules:
                seen_rules.add(rule_id)
                total_score += pts
                breakdown.append(
                    PriorityBreakdownItem(
                        rule_id=rule_id,
                        title=f.title,
                        points=pts,
                        tier=f.tier,
                    )
                )

        if total_score >= 45:
            priority = ReviewPriority.HIGH
        elif total_score >= 20:
            priority = ReviewPriority.MEDIUM
        else:
            priority = ReviewPriority.LOW

        return priority, total_score, breakdown
