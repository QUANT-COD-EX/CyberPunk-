"""
Unit tests for sophisticated image forensics (2D FFT, double compression, and noise calibration).
"""

from pathlib import Path
import cv2
import numpy as np
import pytest
from backend.app.models.contracts import FindingTier
from backend.app.services.forensics.image_forensics import (
    detect_double_jpeg_compression,
    detect_fft_spectral_anomalies,
    generate_forensic_report,
    run_image_forensics_checks,
)


def test_fft_spectral_anomaly_detection():
    # Create image with high-frequency periodic artificial grid spikes (simulating GAN or inpainting grid)
    h, w = 256, 256
    img = np.ones((h, w, 3), dtype=np.uint8) * 180
    # Add high-frequency periodic grid pattern
    for y in range(0, h, 8):
        img[y, :, :] = 40
    for x in range(0, w, 8):
        img[:, x, :] = 40

    regions, max_spike = detect_fft_spectral_anomalies(img)
    assert max_spike > 4.5
    assert len(regions) > 0
    assert regions[0].technique == "fft_spectral"


def test_clean_image_no_spurious_tampering():
    # Clean white background with ordinary text lines (simulating clean PDF render)
    h, w = 600, 450
    img = np.ones((h, w, 3), dtype=np.uint8) * 255
    cv2.putText(img, "SALARY SLIP", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
    cv2.putText(img, "Gross Pay: 85000", (50, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)

    with pytest.MonkeyPatch.context() as m:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            cv2.imwrite(str(tmp_path), img)
            report = generate_forensic_report(tmp_path, "CLEAN_DOC", 1)
            assert report.is_anomalous is False

            findings = run_image_forensics_checks(tmp_path, "CLEAN_DOC", 1)
            # Must NOT produce false positive findings on clean renders
            assert len(findings) == 0
        finally:
            if tmp_path.exists():
                tmp_path.unlink()
