from __future__ import annotations
from enum import Enum
from typing import Any, List, Optional, Union
from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    AADHAAR = "aadhaar"
    PAN = "pan"
    SALARY_SLIP = "salary_slip"
    BANK_STATEMENT = "bank_statement"
    LOAN_APPLICATION = "loan_application"
    DECLARATION_15G = "declaration_15g"
    PAYMENT_INSTRUCTION = "payment_instruction"
    UNSUPPORTED = "unsupported"


class DocumentStatus(str, Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PROCESSED = "processed"
    UNSUPPORTED = "unsupported"
    ERROR = "error"
    ENCRYPTED = "encrypted"
    OCR_FAILED = "ocr_failed"


class FieldSource(str, Enum):
    OCR = "ocr"
    TEXT_LAYER = "text_layer"
    QR = "qr"


class FindingTier(str, Enum):
    OBSERVATION = "observation"
    INCONSISTENCY = "inconsistency"
    POTENTIAL_MANIPULATION = "potential_manipulation"


class FindingCategory(str, Enum):
    WITHIN_DOCUMENT = "within_document"
    CROSS_DOCUMENT = "cross_document"
    FORENSIC = "forensic"
    INJECTION = "injection"
    SYSTEM = "system"


class FindingStrength(str, Enum):
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"


class FindingStatus(str, Enum):
    REQUIRES_INVESTIGATION = "requires_investigation"
    CONFIRMED_BY_REVIEWER = "confirmed_by_reviewer"
    DISMISSED = "dismissed"


class ReviewDecision(str, Enum):
    CONFIRM = "confirm"
    DISMISS = "dismiss"
    ESCALATE = "escalate"


class CaseDecisionType(str, Enum):
    RELY_ON_TOOL_OUTPUT = "rely_on_tool_output"
    PARTIALLY_RELY = "partially_rely"
    DISREGARD_TOOL_OUTPUT = "disregard_tool_output"
    NEEDS_MORE_INFORMATION = "needs_more_information"


class ReviewPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RuleStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    NOT_APPLICABLE = "not_applicable"


# Bounding Box: [x0, y0, x1, y1] in fixed 150 DPI coordinate system, origin top-left
BBox = List[int]


class ExtractedField(BaseModel):
    field_id: str
    doc_id: str
    name: str
    value: Any
    raw_text: str
    confidence: float = Field(ge=0.0, le=1.0)
    source: FieldSource
    page: int = Field(ge=1)
    bbox: BBox
    unable_to_assess: bool = False
    is_handwritten: bool = False
    language: Optional[str] = "en"
    script: Optional[str] = "Latin"


class TamperRegion(BaseModel):
    bbox: BBox
    score: float
    technique: str  # "ela", "noise_discrepancy", "copy_move", "edge_boundary"
    description: str


class ForensicAnalysisReport(BaseModel):
    doc_id: str
    page: int = 1
    tamper_score: float = 0.0  # 0.0 to 1.0
    is_anomalous: bool = False
    techniques_run: List[str] = []
    regions: List[TamperRegion] = []
    ela_mean_mse: float = 0.0
    noise_variance_delta: float = 0.0
    copy_move_matches: int = 0
    fft_spectral_anomaly_score: float = 0.0
    double_compression_detected: bool = False
    deepfake_signature_score: float = 0.0
    ai_generation_score: float = 0.0
    heatmap_url: Optional[str] = None


class DocumentRecord(BaseModel):
    doc_id: str
    filename: str
    sha256: str
    type: DocumentType = DocumentType.UNSUPPORTED
    type_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    llm_type: Optional[DocumentType] = None
    llm_accuracy: Optional[float] = None
    llm_reasoning: Optional[str] = None
    llm_provider: Optional[str] = None
    is_ai_generated: bool = False
    ai_generation_risk: float = 0.0
    ai_generation_reasoning: Optional[str] = None
    ai_generation_indicators: List[str] = []
    pages: int = 1
    render_dpi: int = 150
    status: DocumentStatus = DocumentStatus.UPLOADED
    error_message: Optional[str] = None
    fields: List[ExtractedField] = []
    primary_language: Optional[str] = "en"
    detected_languages: List[str] = ["en"]
    scripts: List[str] = ["Latin"]
    has_handwriting: bool = False
    handwriting_ratio: float = 0.0
    forensic_report: Optional[ForensicAnalysisReport] = None


class EvidenceItem(BaseModel):
    doc_id: str
    field_id: Optional[str] = None
    page: int = Field(ge=1)
    bbox: BBox
    label: Optional[str] = None


class ReviewerAction(BaseModel):
    decision: Optional[ReviewDecision] = None
    reason: Optional[str] = None
    by: Optional[str] = None
    at: Optional[str] = None


class Finding(BaseModel):
    finding_id: str
    tier: FindingTier
    category: FindingCategory
    rule_id: str
    title: str
    evidence: List[EvidenceItem]
    signals: List[str]
    strength: FindingStrength
    confidence: float = Field(ge=0.0, le=1.0)
    status: FindingStatus = FindingStatus.REQUIRES_INVESTIGATION
    explanation: str = ""
    reviewer: ReviewerAction = Field(default_factory=ReviewerAction)
    related_finding_ids: List[str] = []


class PriorityBreakdownItem(BaseModel):
    rule_id: str
    title: str
    points: int
    tier: FindingTier


class CaseDecision(BaseModel):
    decision: CaseDecisionType
    outcome_note: str
    decided_by: str
    decided_at: str
    findings_reviewed: int


class AuditEvent(BaseModel):
    seq: int
    timestamp: str
    investigation_id: str
    actor: str
    action: str
    object_id: str
    details: dict[str, Any] = Field(default_factory=dict)
    prev_hash: str
    entry_hash: str


class RelationshipNode(BaseModel):
    id: str
    label: str
    type: str  # "document", "person", "identifier", "bank_account", "employer", "amount", "date"
    doc_id: Optional[str] = None
    properties: dict[str, Any] = Field(default_factory=dict)


class RelationshipEdge(BaseModel):
    id: str
    source: str
    target: str
    relation: str  # "OWNS", "ISSUED_BY", "EMPLOYS", "CROSS_VALIDATES", "CONTRADICTS", "CORRESPONDS_TO"
    confidence: float = 1.0
    status: str = "consistent"  # "consistent", "contradiction", "unverified"
    details: str = ""


class CrossDocRelationshipGraph(BaseModel):
    nodes: List[RelationshipNode] = []
    edges: List[RelationshipEdge] = []
    consistency_score: float = 1.0
    total_entities: int = 0
    contradictions_count: int = 0


class ReasoningChainStep(BaseModel):
    step_index: int
    title: str
    premises: List[str]
    observation: str
    conclusion: str
    evidence_refs: List[EvidenceItem] = []
    confidence: float = 0.90


class AnomalyCorrelationCluster(BaseModel):
    cluster_id: str
    theme: str  # "Identity Divergence", "Financial Discrepancy", "Document Tampering", "Temporal Inconsistency"
    severity: FindingTier
    finding_ids: List[str]
    synthesis_rationale: str
    recommended_inquiry: str
    chain: List[ReasoningChainStep] = []


class Investigation(BaseModel):
    investigation_id: str
    created_at: str
    documents: List[DocumentRecord] = []
    review_priority: ReviewPriority = ReviewPriority.LOW
    priority_score: int = 0
    priority_breakdown: List[PriorityBreakdownItem] = []
    case_decision: Optional[CaseDecision] = None
    relationship_graph: Optional[CrossDocRelationshipGraph] = None
    correlation_clusters: List[AnomalyCorrelationCluster] = []
    tampering_risk_score: float = 0.0


class RuleResult(BaseModel):
    rule_id: str
    result: RuleStatus
    field_ids_used: List[str] = []
    detail: str
    signals: List[str] = []
    evidence: List[EvidenceItem] = []
    tier: Optional[FindingTier] = None
    strength: Optional[FindingStrength] = None
    title: Optional[str] = None


class CapabilityStatus(BaseModel):
    feature: str
    status: str  # "implemented" | "partial" | "planned" | "unsupported"
    detail: str


class CapabilitiesReport(BaseModel):
    tesseract_available: bool
    tesseract_version: Optional[str]
    tesseract_languages: List[str]
    system_mode: str = "offline"
    capabilities: List[CapabilityStatus]
