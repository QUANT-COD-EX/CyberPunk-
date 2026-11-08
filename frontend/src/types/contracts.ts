export type DocumentType =
  | 'aadhaar'
  | 'pan'
  | 'salary_slip'
  | 'bank_statement'
  | 'loan_application'
  | 'declaration_15g'
  | 'payment_instruction'
  | 'unsupported';

export type DocumentStatus =
  | 'uploaded'
  | 'processing'
  | 'processed'
  | 'unsupported'
  | 'error'
  | 'encrypted'
  | 'ocr_failed';

export type FieldSource = 'ocr' | 'text_layer' | 'qr';

export type FindingTier = 'observation' | 'inconsistency' | 'potential_manipulation';

export type FindingCategory =
  | 'within_document'
  | 'cross_document'
  | 'forensic'
  | 'injection'
  | 'system';

export type FindingStrength = 'weak' | 'moderate' | 'strong';

export type FindingStatus =
  | 'requires_investigation'
  | 'confirmed_by_reviewer'
  | 'dismissed';

export type ReviewDecision = 'confirm' | 'dismiss' | 'escalate';

export type CaseDecisionType =
  | 'rely_on_tool_output'
  | 'partially_rely'
  | 'disregard_tool_output'
  | 'needs_more_information';

export type ReviewPriority = 'low' | 'medium' | 'high';

export type BBox = [number, number, number, number]; // [x0, y0, x1, y1] at 150 DPI

export interface ExtractedField {
  field_id: string;
  doc_id: string;
  name: string;
  value: any;
  raw_text: string;
  confidence: number;
  source: FieldSource;
  page: number;
  bbox: BBox;
  unable_to_assess?: boolean;
  is_handwritten?: boolean;
  language?: string | null;
  script?: string | null;
}

export interface TamperRegion {
  bbox: BBox;
  score: number;
  technique: string;
  description: string;
}

export interface ForensicAnalysisReport {
  doc_id: string;
  page: number;
  tamper_score: number;
  is_anomalous: boolean;
  techniques_run: string[];
  regions: TamperRegion[];
  ela_mean_mse: number;
  noise_variance_delta: number;
  copy_move_matches: number;
  fft_spectral_anomaly_score?: number;
  double_compression_detected?: boolean;
  deepfake_signature_score?: number;
  ai_generation_score?: number;
  heatmap_url?: string | null;
}

export interface DocumentRecord {
  doc_id: string;
  filename: string;
  sha256: string;
  type: DocumentType;
  type_confidence: number;
  llm_type?: DocumentType | null;
  llm_accuracy?: number | null;
  llm_reasoning?: string | null;
  llm_provider?: string | null;
  is_ai_generated?: boolean;
  ai_generation_risk?: number;
  ai_generation_reasoning?: string | null;
  ai_generation_indicators?: string[];
  pages: number;
  render_dpi: number;
  status: DocumentStatus;
  error_message?: string | null;
  fields: ExtractedField[];
  primary_language?: string | null;
  detected_languages?: string[];
  scripts?: string[];
  has_handwriting?: boolean;
  handwriting_ratio?: number;
  forensic_report?: ForensicAnalysisReport | null;
}

export interface EvidenceItem {
  doc_id: string;
  field_id?: string | null;
  page: number;
  bbox: BBox;
  label?: string | null;
}

export interface ReviewerAction {
  decision?: ReviewDecision | null;
  reason?: string | null;
  by?: string | null;
  at?: string | null;
}

export interface Finding {
  finding_id: string;
  tier: FindingTier;
  category: FindingCategory;
  rule_id: string;
  title: string;
  evidence: EvidenceItem[];
  signals: string[];
  strength: FindingStrength;
  confidence: number;
  status: FindingStatus;
  explanation: string;
  reviewer: ReviewerAction;
  related_finding_ids?: string[];
}

export interface PriorityBreakdownItem {
  rule_id: string;
  title: string;
  points: number;
  tier: FindingTier;
}

export interface CaseDecision {
  decision: CaseDecisionType;
  outcome_note: string;
  decided_by: string;
  decided_at: string;
  findings_reviewed: number;
}

export interface AuditEvent {
  seq: number;
  timestamp: string;
  investigation_id: string;
  actor: string;
  action: string;
  object_id: string;
  details: Record<string, any>;
  prev_hash: string;
  entry_hash: string;
}

export interface RelationshipNode {
  id: string;
  label: string;
  type: string;
  doc_id?: string | null;
  properties?: Record<string, any>;
}

export interface RelationshipEdge {
  id: string;
  source: string;
  target: string;
  relation: string;
  confidence: number;
  status: 'consistent' | 'contradiction' | 'unverified';
  details?: string;
}

export interface CrossDocRelationshipGraph {
  nodes: RelationshipNode[];
  edges: RelationshipEdge[];
  consistency_score: number;
  total_entities: number;
  contradictions_count: number;
}

export interface ReasoningChainStep {
  step_index: number;
  title: string;
  premises: string[];
  observation: string;
  conclusion: string;
  evidence_refs: EvidenceItem[];
  confidence: number;
}

export interface AnomalyCorrelationCluster {
  cluster_id: string;
  theme: string;
  severity: FindingTier;
  finding_ids: string[];
  synthesis_rationale: string;
  recommended_inquiry: string;
  chain: ReasoningChainStep[];
}

export interface InvestigationAnalytics {
  investigation_id: string;
  total_documents: number;
  total_fields: number;
  tampering_risk_score: number;
  consistency_score: number;
  total_entities_discovered: number;
  contradictions_count: number;
  findings_by_tier: Record<string, number>;
  languages: Record<string, number>;
  scripts: Record<string, number>;
  handwriting_stats: {
    docs_with_handwriting: number;
    total_handwritten_fields: number;
    overall_handwriting_ratio: number;
  };
  correlation_clusters: AnomalyCorrelationCluster[];
}

export interface Investigation {
  investigation_id: string;
  created_at: string;
  documents: DocumentRecord[];
  review_priority: ReviewPriority;
  priority_score: number;
  priority_breakdown: PriorityBreakdownItem[];
  case_decision?: CaseDecision | null;
  relationship_graph?: CrossDocRelationshipGraph | null;
  correlation_clusters?: AnomalyCorrelationCluster[];
  tampering_risk_score?: number;
}

export interface CapabilityStatus {
  feature: string;
  status: 'implemented' | 'partial' | 'planned' | 'unsupported';
  detail: string;
}

export interface CapabilitiesReport {
  tesseract_available: boolean;
  tesseract_version?: string | null;
  tesseract_languages: string[];
  system_mode: string;
  capabilities: CapabilityStatus[];
}

export interface CrossDocComparisonField {
  field_name: string;
  status: 'match' | 'conflict' | 'needs_review' | 'not_applicable';
  score?: number | null;
  docs: Array<{
    doc_id: string;
    doc_type: DocumentType;
    value: string;
    field_id?: string;
    bbox?: BBox;
    page?: number;
  }>;
  finding_id?: string | null;
}
