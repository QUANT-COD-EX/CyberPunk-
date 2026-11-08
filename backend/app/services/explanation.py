"""
Deterministic Explanation and Summary Generation Engine.
Zero LLM, 100% deterministic template engine strictly bound to extracted finding data.

Security and Legal Rules:
1. May ONLY insert values present in the finding/evidence.
2. Explanations must NEVER contain forbidden accusation words:
   "fraud", "forged", "fake", "counterfeit", "confirmed fraud".
3. Every finding articulates:
   - What values/rules were evaluated
   - Where the discrepancy occurs
   - Why it matters from a compliance/forensic perspective
   - Recommended next verification steps for the human investigator
"""

import re
from typing import Any, Dict, List, Optional
from backend.app.models.contracts import (
    Finding,
    FindingTier,
    Investigation,
    ReviewPriority,
)

FORBIDDEN_WORDS = [
    r"\bfraud\b",
    r"\bforged\b",
    r"\bfake\b",
    r"\bcounterfeit\b",
    r"\bconfirmed\s+fraud\b",
    r"\bconclusive\s+forgery\b",
    r"\bcriminal\b",
]

COMPILED_FORBIDDEN_REGEX = re.compile("|".join(FORBIDDEN_WORDS), re.IGNORECASE)


EXPLANATION_TEMPLATES: Dict[str, Dict[str, str]] = {
    "salary_net_pay_calc": {
        "why_it_matters": "Payroll records must maintain exact mathematical consistency between gross earnings, itemized deductions, and final net disbursement.",
        "next_steps": "Verify original employer payroll register or bank credit records to validate whether gross or deductions were manually modified.",
    },
    "salary_credit_match": {
        "why_it_matters": "The declared net take-home salary on the payslip should correspond directly to the credited deposit in the applicant's salary bank account.",
        "next_steps": "Request supplementary bank account statements or Form 16/26AS tax credits to confirm recurring monthly payroll deposits.",
    },
    "bank_balance_continuity": {
        "why_it_matters": "A continuous double-entry ledger requires every transaction row balance to equal previous balance plus credit minus debit. A break indicates altered or omitted transactions.",
        "next_steps": "Request a bank-certified statement or verify statement digital hash directly via official net-banking portal.",
    },
    "dob_match": {
        "why_it_matters": "Official government identity documents (Aadhaar and PAN) issued to the same individual must reflect identical dates of birth.",
        "next_steps": "Examine original physical government identity cards or check UIDAI/UTIITSL online verification portals for clerical corrections.",
    },
    "pan_structure": {
        "why_it_matters": "Indian PAN numbers adhere to strict statutory structure where the 4th character denotes entity status and the 5th character represents the individual holder's surname initial.",
        "next_steps": "Verify PAN active status and registered legal name on the Income Tax Department NSDL/UTIITSL verification portal.",
    },
    "pan_cross_match": {
        "why_it_matters": "The PAN cited on the salary slip must match the applicant's official PAN card to ensure payroll tax deductions map to the correct taxpayer.",
        "next_steps": "Cross-reference employer TDS certificates (Form 16 Part A) to verify employee PAN registration.",
    },
    "name_match_conflict": {
        "why_it_matters": "Significant name divergence across identity and financial documents indicates potential applicant identity confusion or conflicting identities.",
        "next_steps": "Request gazetted name-change notifications, marriage certificates, or official one-and-the-same person affidavits.",
    },
    "name_match_review": {
        "why_it_matters": "Minor spelling variations, initials, or honorific permutations require verification to rule out clerical error.",
        "next_steps": "Confirm whether differences correspond to expanded initials, maternal/paternal prefixes, or transliteration conventions.",
    },
    "aadhaar_qr_text_mismatch": {
        "why_it_matters": "The UIDAI Secure QR code is cryptographically encoded at the time of issuance; a contradiction with printed text indicates visual alteration of document face text.",
        "next_steps": "Request live mAadhaar verification or original e-Aadhaar XML file downloaded directly from the UIDAI portal.",
    },
    "aadhaar_verhoeff": {
        "why_it_matters": "Aadhaar 12-digit numbers utilize the Verhoeff dihedral D5 checksum algorithm to prevent keystroke error and fabricated numbers.",
        "next_steps": "Verify original Aadhaar letter or e-Aadhaar PDF download.",
    },
    "producer_editing_tool": {
        "why_it_matters": "Institutional financial records from banks and payroll processors are generated via core banking servers or reporting engines, not desktop design or editing software.",
        "next_steps": "Verify statement origin with issuing branch or confirm if the customer re-saved the document via third-party PDF utilities.",
    },
    "incremental_updates_flag": {
        "why_it_matters": "Multiple %%EOF markers indicate the PDF document was edited and re-saved in multiple sessions after original file creation.",
        "next_steps": "Inspect prior document revisions using PDF revision forensic viewers.",
    },
    "font_anomaly": {
        "why_it_matters": "Automated document templates use uniform font families within tables and rows. Divergent font families suggest localized field patching.",
        "next_steps": "Perform high-magnification visual inspection of the flagged cell coordinates to inspect alignment and artifact boundaries.",
    },
    "layer_ocr_mismatch": {
        "why_it_matters": "A contradiction between invisible vector text layer and visible rasterized OCR text suggests an opaque graphical patch was placed over the original text.",
        "next_steps": "Extract individual PDF vector XObject layers to inspect covered underlying text streams.",
    },
    "prompt_injection_pattern": {
        "why_it_matters": "The presence of hidden instruction-like text attempting to steer AI review tools or command automated approval indicates intentional adversarial intent.",
        "next_steps": "Conduct thorough manual inspection of document background layers and report finding to security oversight.",
    },
    "ela_discontinuity": {
        "why_it_matters": "Error Level Analysis highlights compression rate inconsistencies, which can indicate modified image regions, but may also stem from normal re-compression.",
        "next_steps": "Treat as weak supporting indicator; require corroborating document math or font discrepancies before concluding manual tampering.",
    },
    "loan_income_vs_salary": {
        "why_it_matters": "Loan underwriting relies on verified payroll data; a discrepancy between declared income and gross payroll earnings undermines affordability assessments.",
        "next_steps": "Cross-reference employer payroll tax filings (Form 16/26AS) or bank account statements to establish verified recurring monthly compensation.",
    },
    "loan_pan_mismatch": {
        "why_it_matters": "Tax identification numbers on loan applications must match government identity cards to ensure proper credit bureau inquiry and KYC validation.",
        "next_steps": "Verify PAN card authenticity on the Income Tax Department e-filing portal and request clarification from the applicant.",
    },
    "loan_dob_mismatch": {
        "why_it_matters": "Date of birth discrepancy between application documentation and official identity records introduces identity ambiguity.",
        "next_steps": "Review physical government identity cards or municipal birth certificate to determine correct legal date of birth.",
    },
    "g15_income_vs_salary": {
        "why_it_matters": "Form 15G is a statutory self-declaration for tax exemption; understating estimated annual income below demonstrated salary earnings constitutes a compliance anomaly.",
        "next_steps": "Examine the assessee's prior year tax returns (ITR-V) and annual information statements (AIS) to evaluate tax deduction eligibility.",
    },
    "g15_pan_mismatch": {
        "why_it_matters": "Statutory self-declarations under Section 197A require the correct taxpayer identification number to link TDS exemption claims to the correct tax ledger.",
        "next_steps": "Verify active PAN records on the NSDL database and obtain a rectified declaration form if clerical error occurred.",
    },
    "payment_amount_not_in_bank": {
        "why_it_matters": "Fund transfer instructions must correspond to executed transaction debits in the associated bank account ledger to prove remittance.",
        "next_steps": "Verify whether the payment was rejected, reversed, pending clearance, or executed via an alternate bank account.",
    },
    "payment_account_mismatch": {
        "why_it_matters": "Payment orders citing accounts that differ from submitted bank account statements indicate either third-party remittance or disconnected records.",
        "next_steps": "Obtain bank statements for the specific funding account cited in the payment instruction.",
    },
    "payment_amount_invalid": {
        "why_it_matters": "Payment instructions require positive monetary values to constitute a valid financial transfer order.",
        "next_steps": "Inspect the original instruction form to determine whether the transfer amount was omitted or corrupted during document preparation.",
    },
    "loan_amount_invalid": {
        "why_it_matters": "Loan application forms require a clearly stated, positive principal borrowing amount for credit risk appraisal.",
        "next_steps": "Request a complete application form with all required numeric loan request fields populated.",
    },
    "signature_region_empty": {
        "why_it_matters": "Formal declaration and application forms require physical or digital signature execution to establish legal validity.",
        "next_steps": "Inspect the physical document or request a properly executed signed copy from the customer.",
    },
    "signature_placement_overlap": {
        "why_it_matters": "Signatures intersecting or obscuring extracted data values can indicate manual cut-and-paste manipulation or obscure critical terms.",
        "next_steps": "Review original document under magnification to confirm whether signature was digitally overlaid or naturally executed.",
    },
    "baseline_alignment_anomaly": {
        "why_it_matters": "Word spans sharing a logical line with irregular vertical baseline displacement suggest non-native text splicing or localized patching.",
        "next_steps": "Inspect vector PDF structure and high-resolution scan magnification to verify typographic flow.",
    },
    "ai_generated_document_detected": {
        "why_it_matters": "Institutional identity and financial documentation must originate from verified core banking, payroll, or governmental systems rather than generative AI or synthetic templates.",
        "next_steps": "Request primary source records directly from the issuing authority or certified portal (e.g. DigiLocker, ITD portal, or issuing bank branch).",
    },
    "synthetic_signature_detected": {
        "why_it_matters": "Natural human pen executions display ballistic acceleration and pressure fluctuations. Constant stroke thickness and diffusion halos indicate synthetic vector reproduction or digital script font rendering.",
        "next_steps": "Inspect physical document under side-lighting or request in-person signature verification at an authorized branch.",
    },
    "cloned_signature_replication": {
        "why_it_matters": "Biometric motor variability guarantees that human signatures never repeat identically down to stroke curvature and pixel geometry across distinct documents. Identical signatures confirm digital cut-and-paste manipulation.",
        "next_steps": "Compare physical wet-ink originals across all submitted application instruments and obtain fresh wet signatures witnessed by an officer.",
    },
    "fft_spectral_discontinuity": {
        "why_it_matters": "Periodic high-frequency spectral spikes in the 2D Fourier domain indicate generative neural inpainting, diffusion synthesis grids, or artificial resampling.",
        "next_steps": "Examine original uncompressed scan file or request the document in its native electronic PDF format.",
    },
    "double_compression_discontinuity": {
        "why_it_matters": "Discontinuities across 8x8 DCT block boundaries reveal that image patches were spliced from another source and subjected to secondary compression.",
        "next_steps": "Inspect localized coordinate regions under magnification for compression ghosting and color palette shifts.",
    },
}


def generate_finding_explanation(finding: Finding) -> str:
    """
    Produces a complete, deterministic, plain-language explanation for a Finding.
    Strictly forbids accusation terms ('fraud', 'forged', etc.).
    """
    rule_id = finding.rule_id
    template = EXPLANATION_TEMPLATES.get(rule_id, {
        "why_it_matters": "This rule validates statutory or structural consistency across identity and financial documents.",
        "next_steps": "Review original physical or digital records with the issuing authority.",
    })

    # Use finding's existing factual detail as core observation
    core_detail = finding.explanation or finding.title

    explanation = (
        f"{core_detail} "
        f"Forensic Context: {template['why_it_matters']} "
        f"Recommended Action: {template['next_steps']}"
    )

    # Sanity check: Ensure zero forbidden words
    sanitized = COMPILED_FORBIDDEN_REGEX.sub("[requires investigation]", explanation)
    return sanitized


def generate_investigation_summary(investigation: Investigation, findings: List[Finding]) -> str:
    """
    Generates a deterministic plain-text investigation summary for dossier export and overview screens.
    """
    obs_count = sum(1 for f in findings if f.tier == FindingTier.OBSERVATION)
    incons_count = sum(1 for f in findings if f.tier == FindingTier.INCONSISTENCY)
    pot_count = sum(1 for f in findings if f.tier == FindingTier.POTENTIAL_MANIPULATION)

    summary_lines = [
        f"INVESTIGATION SUMMARY ({investigation.investigation_id})",
        f"Review Priority: {investigation.review_priority.value.upper()} (Score: {investigation.priority_score})",
        f"Total Findings: {len(findings)} (Potential Manipulation: {pot_count}, Inconsistencies: {incons_count}, Observations: {obs_count})",
        f"Processed Documents: {len(investigation.documents)}",
        "",
        "AREAS REQUIRING HUMAN VERIFICATION:",
    ]

    if not findings:
        summary_lines.append("  - No discrepancies detected. All documents passed deterministic arithmetic and identity checks.")
    else:
        for f in findings:
            summary_lines.append(f"  - [{f.tier.value.upper()}] {f.title}: {f.explanation[:120]}...")

    summary_lines.extend([
        "",
        "OPERATIONAL LIMITATIONS & GOVERNANCE:",
        "  - This tool is advisory. Final case decisions rest solely with the human reviewer.",
        "  - Offline operation: UIDAI PKI cryptographic signatures are not validated against live CRLs.",
        "  - ELA and noise signals are weak indicators and require independent corroboration.",
    ])

    return "\n".join(summary_lines)
