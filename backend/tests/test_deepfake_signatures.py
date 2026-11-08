"""
Unit tests for deepfake and cloned signature forensics.
"""

from pathlib import Path
import cv2
import numpy as np
import pytest
from backend.app.models.contracts import (
    DocumentRecord,
    DocumentStatus,
    DocumentType,
    ExtractedField,
    FieldSource,
    FindingTier,
)
from backend.app.services.forensics.signature_forensics import (
    analyze_signature_stroke_authenticity,
    detect_cloned_signatures_cross_document,
)


def create_synthetic_signature_image(uniform: bool = True) -> np.ndarray:
    """Generates a test signature crop with either uniform vector lines or variable stroke width."""
    img = np.ones((100, 250, 3), dtype=np.uint8) * 255
    if uniform:
        # Uniform 2px line thickness with zero dynamic variation (digital script font / vector)
        cv2.line(img, (20, 50), (90, 30), (20, 20, 20), 2)
        cv2.line(img, (90, 30), (120, 75), (20, 20, 20), 2)
        cv2.line(img, (120, 75), (180, 25), (20, 20, 20), 2)
        cv2.line(img, (180, 25), (230, 60), (20, 20, 20), 2)
    else:
        # Variable stroke width simulating pen pressure (thick downstrokes, thin upstrokes)
        for i in range(20, 90):
            w = 1 + int(round(3 * np.sin((i - 20) / 70.0 * np.pi)))
            cv2.circle(img, (i, 40 + int(15 * np.sin(i / 10.0))), w, (20, 20, 20), -1)
        for i in range(90, 180):
            w = 1 + int(round(4 * np.cos((i - 90) / 90.0 * np.pi / 2)))
            cv2.circle(img, (i, 60 - int(25 * np.sin((i - 90) / 30.0))), max(1, w), (20, 20, 20), -1)
    return img


def test_deepfake_signature_stroke_uniformity_detected():
    uniform_crop = create_synthetic_signature_image(uniform=True)
    findings, risk, indicators = analyze_signature_stroke_authenticity(
        uniform_crop, "DOC_SIG_TEST", 1, [100, 700, 350, 800]
    )
    assert risk >= 0.60
    assert any(f.rule_id == "synthetic_signature_detected" for f in findings)


def test_natural_signature_stroke_not_flagged():
    natural_crop = create_synthetic_signature_image(uniform=False)
    findings, risk, indicators = analyze_signature_stroke_authenticity(
        natural_crop, "DOC_SIG_NATURAL", 1, [100, 700, 350, 800]
    )
    # Natural variable width should not trigger synthetic signature finding
    assert not any(f.rule_id == "synthetic_signature_detected" for f in findings)


def test_cloned_signature_across_documents_detected(tmp_path: Path):
    rendered_dir = tmp_path / "rendered"
    rendered_dir.mkdir(parents=True, exist_ok=True)

    sig_img = create_synthetic_signature_image(uniform=True)

    # Document A
    doc_a_dir = rendered_dir / "DOC_A"
    doc_a_dir.mkdir(parents=True, exist_ok=True)
    page_a = np.ones((842, 595, 3), dtype=np.uint8) * 255
    page_a[700:800, 100:350] = sig_img
    cv2.imwrite(str(doc_a_dir / "page_1.png"), page_a)

    doc_a = DocumentRecord(
        doc_id="DOC_A",
        filename="loan_app.pdf",
        sha256="aaa",
        type=DocumentType.LOAN_APPLICATION,
        fields=[
            ExtractedField(
                field_id="F1",
                doc_id="DOC_A",
                name="applicant_signature",
                value="Executed",
                raw_text="Signature",
                confidence=0.9,
                source=FieldSource.TEXT_LAYER,
                page=1,
                bbox=[100, 700, 350, 800],
            )
        ],
    )

    # Document B with identical cloned signature
    doc_b_dir = rendered_dir / "DOC_B"
    doc_b_dir.mkdir(parents=True, exist_ok=True)
    page_b = np.ones((842, 595, 3), dtype=np.uint8) * 255
    page_b[700:800, 100:350] = sig_img
    cv2.imwrite(str(doc_b_dir / "page_1.png"), page_b)

    doc_b = DocumentRecord(
        doc_id="DOC_B",
        filename="declaration_15g.pdf",
        sha256="bbb",
        type=DocumentType.DECLARATION_15G,
        fields=[
            ExtractedField(
                field_id="F2",
                doc_id="DOC_B",
                name="declarant_signature",
                value="Executed",
                raw_text="Signature",
                confidence=0.9,
                source=FieldSource.TEXT_LAYER,
                page=1,
                bbox=[100, 700, 350, 800],
            )
        ],
    )

    findings = detect_cloned_signatures_cross_document([doc_a, doc_b], rendered_dir)
    assert any(f.rule_id == "cloned_signature_replication" for f in findings)
    cloned_finding = next(f for f in findings if f.rule_id == "cloned_signature_replication")
    assert cloned_finding.tier == FindingTier.POTENTIAL_MANIPULATION
    assert len(cloned_finding.evidence) == 2
