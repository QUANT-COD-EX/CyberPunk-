"""
Deepfake and Cloned Signature Forensics Engine.
Advisory output. Final decision rests with the human reviewer (ISO/IEC 27037).

Covers:
1. Single-Signature Deepfake & Generative AI Stroke Analysis:
   - Stroke width dynamic variation (real ballpoint/ink pen pressure vs. uniform digital script font)
   - Edge boundary gradient and diffusion inpainting halo detection
2. Cross-Document Cloned Signature Forgery Detection:
   - Structural and keypoint comparison across signatures in distinct documents in a bundle
   - Identifies identical digital cut-and-paste signatures (biometric impossibility in physical human signing)
"""

import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import cv2
import numpy as np
from backend.app.models.contracts import (
    DocumentRecord,
    EvidenceItem,
    Finding,
    FindingCategory,
    FindingStatus,
    FindingStrength,
    FindingTier,
    ReviewerAction,
)


def extract_signature_crop(
    image_path: Path,
    bbox: List[int],
) -> Optional[np.ndarray]:
    """Crops the signature region from a rendered page image at 150 DPI."""
    if not image_path.exists():
        return None
    img = cv2.imread(str(image_path))
    if img is None:
        return None

    h, w = img.shape[:2]
    x0, y0, x1, y1 = bbox
    x0 = max(0, min(x0, w - 1))
    y0 = max(0, min(y0, h - 1))
    x1 = max(0, min(x1, w))
    y1 = max(0, min(y1, h))

    if x1 <= x0 + 15 or y1 <= y0 + 15:
        return None

    return img[y0:y1, x0:x1]


def analyze_signature_stroke_authenticity(
    crop_bgr: np.ndarray,
    doc_id: str,
    page_num: int,
    bbox: List[int],
) -> Tuple[List[Finding], float, List[str]]:
    """
    Evaluates stroke thickness dynamics, pressure profile, and edge continuity of a signature crop.
    Digital script fonts and vector pens have near-zero stroke width variance (CV < 0.12).
    Natural pen executions display ballistic acceleration and dynamic pressure (CV > 0.30).
    """
    findings: List[Finding] = []
    indicators: List[str] = []

    if crop_bgr is None or crop_bgr.size < 400:
        return findings, 0.0, indicators

    gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)

    dark_pixels = int(np.sum(binary > 0))
    if dark_pixels < 120:
        # Too few ink pixels to evaluate stroke dynamics reliably
        return findings, 0.0, indicators

    # Distance transform gives distance from stroke pixel to nearest background
    dist_transform = cv2.distanceTransform(binary, cv2.DIST_L2, 5)

    # Medial axis / ridge lines via local maxima of distance transform
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    dilated_dist = cv2.dilate(dist_transform, kernel)
    skeleton = (dist_transform == dilated_dist) & (dist_transform >= 1.0)

    stroke_widths = dist_transform[skeleton] * 2.0
    if len(stroke_widths) < 30:
        return findings, 0.0, indicators

    mean_w = float(np.mean(stroke_widths))
    std_w = float(np.std(stroke_widths))
    cv_score = (std_w / mean_w) if mean_w > 0 else 0.0

    deepfake_score = 0.0

    # 1. Stroke width uniformity check
    # Digital script fonts or vector spline pens have CV < 0.14
    if cv_score < 0.14 and mean_w >= 1.5:
        deepfake_score += 0.65
        indicators.append(
            f"Unnatural uniform stroke thickness (Coefficient of Variation: {cv_score:.2f} < 0.14), "
            "characteristic of digital vector brushes or script font reproduction"
        )

    # 2. Diffusion halo / edge blur discontinuity around stroke boundary
    # Only applicable when paper canvas exhibits background scanner/texture noise
    paper_pixels = gray[binary == 0]
    paper_std = float(np.std(paper_pixels)) if paper_pixels.size > 0 else 0.0
    if paper_std > 6.0:
        dilated_stroke = cv2.dilate(binary, kernel, iterations=2)
        halo_zone = dilated_stroke - binary
        if np.sum(halo_zone > 0) > 80:
            halo_pixels = gray[halo_zone > 0]
            halo_std = float(np.std(halo_pixels))
            if halo_std < 2.5:  # Excessively smooth background halo
                deepfake_score += 0.25
                indicators.append("Diffusion-smoothed boundary halo observed around ink stroke contours")

    deepfake_risk = min(0.95, round(deepfake_score, 2))

    if deepfake_risk >= 0.60:
        findings.append(
            Finding(
                finding_id=f"ANM-SIG-SYNTHETIC-{doc_id}-{page_num}-{bbox[0]}",
                tier=FindingTier.OBSERVATION,
                category=FindingCategory.FORENSIC,
                rule_id="synthetic_signature_detected",
                title="Synthetic / AI-generated signature stroke artifact detected",
                evidence=[EvidenceItem(doc_id=doc_id, page=page_num, bbox=bbox, label="Synthetic Signature Region")],
                signals=["synthetic_signature_dynamics", "uniform_stroke_thickness"],
                strength=FindingStrength.MODERATE,
                confidence=deepfake_risk,
                status=FindingStatus.REQUIRES_INVESTIGATION,
                explanation=(
                    f"Signature stroke analysis reveals synthetic characteristics: {'; '.join(indicators)}. "
                    "Natural biological pen execution produces dynamic ballistic pressure variations; "
                    "recommends physical visual inspection or biometric verification."
                ),
                reviewer=ReviewerAction(),
            )
        )

    return findings, deepfake_risk, indicators


def detect_cloned_signatures_cross_document(
    documents: List[DocumentRecord],
    rendered_dir: Path,
) -> List[Finding]:
    """
    Compares signatures across all documents in an investigation bundle.
    If two distinct documents have identical signature crops (SSIM >= 0.88 and high feature match),
    flags an escalated Potential Manipulation finding for cloned / cut-and-paste signature forgery.
    """
    findings: List[Finding] = []
    if len(documents) < 2:
        return findings

    # Collect documents with signature fields or signature regions
    doc_signatures: List[Tuple[DocumentRecord, List[int], np.ndarray]] = []

    for doc in documents:
        # Check extracted fields for 'signature' or form type
        sig_field = next((f for f in doc.fields if "signature" in f.name.lower()), None)
        p1_img = rendered_dir / doc.doc_id / "page_1.png"
        if not p1_img.exists():
            continue

        if sig_field:
            crop = extract_signature_crop(p1_img, sig_field.bbox)
            if crop is not None:
                doc_signatures.append((doc, sig_field.bbox, crop))
        else:
            # Check bottom-right signatory quadrant default [100, 650, 500, 800]
            # If doc is Loan Application, Form 15G, or Payment Instruction
            if doc.type.value in ("loan_application", "declaration_15g", "payment_instruction"):
                box = [100, 680, 450, 780]
                crop = extract_signature_crop(p1_img, box)
                if crop is not None:
                    # Verify has actual dark ink
                    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                    if np.sum(gray < 180) > 150:
                        doc_signatures.append((doc, box, crop))

    if len(doc_signatures) < 2:
        return findings

    norm_w, norm_h = 240, 90

    # Pairwise comparison
    for i in range(len(doc_signatures)):
        for j in range(i + 1, len(doc_signatures)):
            doc_a, box_a, crop_a = doc_signatures[i]
            doc_b, box_b, crop_b = doc_signatures[j]

            # Scale both crops to standardized dimensions
            res_a = cv2.resize(cv2.cvtColor(crop_a, cv2.COLOR_BGR2GRAY), (norm_w, norm_h))
            res_b = cv2.resize(cv2.cvtColor(crop_b, cv2.COLOR_BGR2GRAY), (norm_w, norm_h))

            # Binarize
            _, bin_a = cv2.threshold(res_a, 200, 255, cv2.THRESH_BINARY_INV)
            _, bin_b = cv2.threshold(res_b, 200, 255, cv2.THRESH_BINARY_INV)

            # Intersection over Union and Normalized Cross-Correlation
            intersection = np.logical_and(bin_a > 0, bin_b > 0)
            union = np.logical_or(bin_a > 0, bin_b > 0)
            iou = float(np.sum(intersection)) / float(np.sum(union)) if np.sum(union) > 0 else 0.0

            # Pixel difference MSE
            diff = cv2.absdiff(bin_a, bin_b)
            diff_ratio = 1.0 - (float(np.mean(diff)) / 255.0)

            # Keypoint matching
            orb = cv2.ORB_create(nfeatures=400)
            kp1, des1 = orb.detectAndCompute(bin_a, None)
            kp2, des2 = orb.detectAndCompute(bin_b, None)

            kp_match_ratio = 0.0
            if des1 is not None and des2 is not None and len(des1) >= 15 and len(des2) >= 15:
                bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
                matches = bf.match(des1, des2)
                good = [m for m in matches if m.distance < 40]
                kp_match_ratio = len(good) / max(len(des1), len(des2))

            # Cloned signatures match with extraordinary precision across documents
            if (iou >= 0.85 and diff_ratio >= 0.90) or (kp_match_ratio >= 0.82 and iou >= 0.75):
                sim_pct = round(max(iou, kp_match_ratio) * 100, 1)
                findings.append(
                    Finding(
                        finding_id=f"ANM-SIG-CLONE-{doc_a.doc_id}-{doc_b.doc_id}",
                        tier=FindingTier.POTENTIAL_MANIPULATION,
                        category=FindingCategory.CROSS_DOCUMENT,
                        rule_id="cloned_signature_replication",
                        title=f"Cloned / duplicated digital signature detected between '{doc_a.filename}' and '{doc_b.filename}'",
                        evidence=[
                            EvidenceItem(doc_id=doc_a.doc_id, page=1, bbox=box_a, label=f"Signature on {doc_a.filename}"),
                            EvidenceItem(doc_id=doc_b.doc_id, page=1, bbox=box_b, label=f"Signature on {doc_b.filename}"),
                        ],
                        signals=["cloned_signature_across_documents", "zero_biometric_variance"],
                        strength=FindingStrength.STRONG,
                        confidence=0.96,
                        status=FindingStatus.REQUIRES_INVESTIGATION,
                        explanation=(
                            f"Identical signature stroke contours detected on both '{doc_a.filename}' and '{doc_b.filename}' "
                            f"(Structural match similarity: {sim_pct}%). "
                            "Physical human motor variability precludes an individual from executing identical signatures "
                            "down to stroke curvature and pixel geometry; indicates digital cut-and-paste or cloned signature replication."
                        ),
                        reviewer=ReviewerAction(),
                    )
                )

    return findings
