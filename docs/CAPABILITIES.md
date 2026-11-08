# Capabilities & System Support Matrix

This document provides a transparent accounting of all system capabilities, explicitly categorizing features as **Implemented**, **Partial**, **Planned**, or **Unsupported**.

| Feature / Subsystem | Status | Description & Limitations |
|---|---|---|
| **Two-Stage Document Classification** | Implemented | Primary supervised **XGBoost ML classifier** trained over TF-IDF character and word n-grams (99.88% 5-fold CV accuracy across 846+ training samples), backed by a deterministic heuristic/regex layout rules engine fallback. Supports 7 distinct document types. |
| **Expanded Document Types (7 types)** | Implemented | Ingests, parses, and audits **Aadhaar**, **PAN Card**, **Salary Slip**, **Bank Statement**, **Loan Application Form**, **Form 15G Declaration**, and **Payment Instruction Mandate (NEFT/RTGS)**. Unsupported document formats trigger graceful fallback and 422 validation. |
| **Multi-Format Ingestion Pipeline** | Implemented | Native support for `.pdf`, `.png`, `.jpg`, `.jpeg`, `.tiff`, `.tif`, `.bmp`, `.webp`, `.docx` (Office Word via `python-docx` + ReportLab), and `.xlsx` (Office Excel via `openpyxl` + ReportLab). All rendered server-side to 150 DPI PNGs. |
| **PDF Text-Layer Extraction** | Implemented | Direct extraction of vector text, spans, fonts, sizes, origins, and colors via PyMuPDF. |
| **Tesseract OCR (CLI)** | Implemented | Local CLI invocation (`subprocess`), TSV output parsing, word bounding boxes, normalized word confidence. Operates at 300 DPI, scaled to 150 DPI coordinate system. |
| **Aadhaar Secure QR Extraction** | Implemented | OpenCV QR detection + custom zlib decompression + big-integer demographic decoding. |
| **Aadhaar UIDAI PKI Signature Verification** | Unsupported | Unsupported by design in offline mode: requires live UIDAI certificate revocation checks and government root keys. |
| **Verhoeff Checksum (Aadhaar)** | Implemented | Pure Python implementation of Dihedral $D_5$ group multiplication and permutation tables. |
| **PAN Format & Holder Validation** | Implemented | Regex structure validation (`^[A-Z]{5}[0-9]{4}[A-Z]$`), 4th character holder-type decoding, 5th character surname initial match. |
| **Payroll Arithmetic Audit** | Implemented | Component sum to Gross, Gross minus Deductions to Net Pay. PF basic wage check reported as Observation. |
| **Bank Balance Continuity Engine** | Implemented | Row-by-row transaction continuity checking; pinpoints the exact first broken row index and balance discrepancy. |
| **Loan & Declaration Validation** | Implemented | Within-document numeric validation of requested loan amounts and payment transfer sums; cross-doc correlation of declared loan income against payslip gross, Form 15G PAN against PAN card, and Form 15G annual income against annualized salary gross ($12 \times \text{Gross}$). |
| **Payment Instruction Reconciliation** | Implemented | Verifies payment transfer account against bank statement account and cross-checks instructed debit amount against bank statement transaction debit entries. |
| **Cross-Document Field Correlation** | Implemented | Multi-entity correlation of Name, DOB, PAN, Salary Credits, Form 15G, and Payment Instructions with two-sided evidence bounding boxes and cross-document comparison matrix. |
| **In-House Name Matching** | Implemented | Pure Python Jaro-Winkler + Levenshtein + token set permutations + Indian honorifics and initials normalization. Zero external libraries. |
| **Visual Signature Presence & Placement** | Implemented | Visual ink stroke density inspection in signatory regions (`signature_region_empty`) and detection of signature strokes overlapping extracted form data fields (`signature_placement_overlap`). |
| **Deepfake & Cloned Signature Forensics** | Implemented | Biometric stroke width dynamics (measuring coefficient of variation CV of stroke thickness along distance-transform medial axis), diffusion inpainting halo detection, and cross-document cloned signature detection (ORB keypoint and SSIM structural matching across distinct documents in a bundle). |
| **AI-Generated Document Detection** | Implemented | Multi-layered detection analyzing AI boilerplates/disclaimers, template placeholder tokens (`[Insert ...]`, `{{...}}`), stylometric burstiness (sentence length uniformity), synthetic identifier patterns, and metadata generator tools (ChatGPT, Midjourney, Canva Magic, etc.) across both LLM prompts and offline semantic neural engine. |
| **Sophisticated Image Manipulation** | Implemented | Multi-signal image forensics including Error Level Analysis (ELA), 2D Fast Fourier Transform (FFT) frequency domain spectral anomaly analysis (detecting periodic grid peaks from neural inpainting and GAN/diffusion upscaling), double JPEG compression DCT block boundary grid misalignment (BBE), calibrated non-edge noise residual analysis, coherent copy-move translation clustering, and fused 4-channel tampering heatmaps. |
| **Baseline Alignment Forensics** | Implemented | Vertical baseline origin disparity inspection (`baseline_alignment_anomaly`) across row text spans to detect spliced text inserts. |
| **PDF-Native Metadata Forensics** | Implemented | Producer/Creator analysis, editing software detection, creation vs. modification date discrepancies. |
| **PDF Incremental Re-save Forensics** | Implemented | Detection and counting of multiple `%%EOF` markers. |
| **PDF Sibling Font Inconsistency** | Implemented | Detection of font family, size, or weight deviations within table rows/columns. |
| **Text-Layer vs OCR Diff Detection** | Implemented | Comparison between vector text stream and rasterized OCR text for overlaid tamper detection. |
| **Signal Convergence & Linked Findings** | Implemented | Spatial bounding box intersection detecting multi-modal signal convergence on the same field; links related findings via `related_finding_ids`. |
| **Prompt-Injection Defense** | Implemented | Scanning visible and hidden text spans for adversarial instruction patterns; isolated so adversarial text cannot alter scoring. |
| **Error Level Analysis (ELA)** | Implemented | Local OpenCV re-compression difference with calibrated thresholding. Marked as weak supporting observation under ISO/IEC 27037. |
| **Copy-Move Image Detection** | Implemented | Translation vector clustered ORB keypoint descriptor matching for cloned graphical patches, portraits, and stamps. Marked as weak supporting signal. |
| **Hash-Chained Audit Trail** | Implemented | Append-only SQLite event ledger with SHA-256 chain verification. |
| **Human Review & Decision Engine** | Implemented | Per-finding review actions (Confirm/Dismiss/Escalate) and Case Decision workflow (`rely_on_tool_output`, `partially_rely`, `disregard_tool_output`, `needs_more_information`). |
| **PII Redaction & Audited Reveal** | Implemented | Masked display of Aadhaar (`XXXX XXXX 1234`) and PAN; unmasking audited with user identity and timestamp. |
| **PS-2 Section 7 Structured Dossier** | Implemented | Comprehensive PDF export strictly conforming to PS-2 §7 headings: §7.1 Document Overview, §7.2 Extracted Information (with PII masking), §7.3 Contextual Analysis, §7.4 Visual Forensic Findings, §7.5 Evidence and Traceability (with cropped thumbnails), and §7.6 Investigation Summary. Watermarked DRAFT until a human Case Decision is recorded. |
| **Handwriting OCR** | Unsupported | Unsupported: system focuses exclusively on machine-printed typography and structured form documents. |
| **General Deep Vision Layout Model** | Unsupported | Unsupported: system relies on deterministic coordinate geometry and OCR TSV structures rather than heavy deep-learning layout transformers. |
| **Multi-Provider LLM & Intelligence** | Implemented | Hybrid architecture combining offline deterministic core with multi-provider LLM classification & authenticity inspection (Gemini, Groq, OpenAI, and Local Semantic Engine fallback). Returns accuracy score, classification type, and human-readable reasoning rationale. |
| **Cloud / SaaS API Integrations** | Unsupported | **Unsupported by design**: System operates fully offline with zero telemetry or outbound network calls. |
