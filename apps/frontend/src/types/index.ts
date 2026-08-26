// Mirrors apps/backend/app/models/enums.py and app/schemas/*.py.
// Kept as plain hand-written types (no codegen) for a V1 academic prototype —
// see docs/architecture.md for the tradeoff.

export type RoleName = "ADMIN" | "INSPECTOR" | "REVIEWER";

export type ComplianceStatus =
  | "PASS"
  | "POTENTIAL_NON_COMPLIANCE"
  | "NEEDS_MANUAL_REVIEW"
  | "NOT_APPLICABLE"
  | "UNABLE_TO_VERIFY";

export type InspectionStatus = "CREATED" | "IN_PROGRESS" | "COMPLETED" | "FAILED";

export type PipelineStage =
  | "FETCH"
  | "PARSE"
  | "IMAGE_DOWNLOAD"
  | "IMAGE_QUALITY"
  | "OCR"
  | "DECLARATION_EXTRACTION"
  | "CLASSIFICATION"
  | "RULE_SELECTION"
  | "COMPLIANCE"
  | "CONSISTENCY"
  | "REPORT"
  | "DONE";

export type PipelineStageStatus = "PENDING" | "RUNNING" | "SUCCEEDED" | "FAILED" | "SKIPPED";

export type ReviewDecisionType = "CONFIRM" | "REJECT" | "OVERRIDE" | "REQUEST_MORE_EVIDENCE";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: RoleName;
  is_active: boolean;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  role: RoleName;
  full_name: string;
  user_id: string;
}

export interface InspectionSummary {
  id: string;
  inspection_number: string;
  source_url: string | null;
  platform: string | null;
  status: InspectionStatus;
  overall_status: ComplianceStatus | null;
  officer_id: string;
  officer_name: string | null;
  product_title: string | null;
  created_at: string;
  completed_at: string | null;
  is_demo: boolean;
}

export interface PipelineEvent {
  stage: PipelineStage;
  status: PipelineStageStatus;
  message: string | null;
  duration_ms: number | null;
  created_at: string;
}

export interface Declaration {
  id: string;
  field_name: string;
  value: string | null;
  normalized_value: string | null;
  source_type: string;
  confidence: number;
  extraction_method: string | null;
  // Exposed so the UI can trace a declaration back to the exact image/OCR
  // block/webpage that produced it (rule -> evidence -> finding traceability).
  source_product_image_id: string | null;
  source_ocr_result_id: string | null;
  source_web_page_id: string | null;
}

export interface EvidenceItem {
  id: string;
  evidence_type: string;
  description: string;
  reference: Record<string, unknown>;
  declaration_id: string | null;
}

export interface Violation {
  id: string;
  severity: string;
  summary: string;
  details: string;
}

export interface ReviewDecision {
  id: string;
  reviewer_id: string;
  reviewer_name: string | null;
  decision: ReviewDecisionType;
  automated_status: ComplianceStatus;
  final_status: ComplianceStatus;
  comment: string | null;
  reason: string | null;
  created_at: string;
}

export interface RuleVersionBrief {
  rule_key: string;
  rule_reference: string;
  title: string;
  requirement: string;
  severity: string;
  source_document: string;
  source_locator: string;
  version_number: number;
}

export interface ComplianceCheck {
  id: string;
  status: ComplianceStatus;
  reason: string;
  confidence: number;
  checked_fields: string[];
  rule: RuleVersionBrief;
  violation: Violation | null;
  evidence: EvidenceItem[];
  review_decisions: ReviewDecision[];
}

export interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface OCRResultItem {
  id: string;
  engine: string;
  text: string;
  confidence: number;
  bounding_box: BoundingBox | null;
}

export interface ProductImage {
  id: string;
  source_type: string;
  original_url: string | null;
  width: number | null;
  height: number | null;
  is_blurry: boolean | null;
  contrast_score: number | null;
  glare_detected: boolean | null;
  quality_acceptable: boolean | null;
  quality_notes: string | null;
  ocr_results: OCRResultItem[];
}

export interface WebPage {
  id: string;
  url: string;
  fetch_status: string;
  http_status_code: number | null;
  error_message: string | null;
  robots_txt_allowed: boolean | null;
  scraper_name: string | null;
  fetched_at: string;
}

export interface InspectionDetail extends InspectionSummary {
  notes: string | null;
  declarations: Declaration[];
  compliance_checks: ComplianceCheck[];
  images: ProductImage[];
  web_pages: WebPage[];
  pipeline_events: PipelineEvent[];
  pipeline_duration_ms: number | null;
}

export interface DashboardStatistics {
  total_online_inspections: number;
  passed: number;
  potential_violations: number;
  needs_review: number;
  unable_to_verify: number;
  not_applicable_only: number;
  by_platform: { key: string; count: number }[];
  by_category: { key: string; count: number }[];
  violations_by_rule: { key: string; count: number }[];
  common_issues: { key: string; count: number }[];
  review_backlog: number;
  trend_last_30_days: { date: string; count: number }[];
}

export interface RuleVersionOut {
  id: string;
  version_number: number;
  rule_reference: string;
  title: string;
  description: string;
  requirement: string;
  applicability: string;
  exceptions: string | null;
  validation_type: string;
  severity: string;
  validator_config: Record<string, unknown>;
  applicable_categories: string[];
  excluded_categories: string[];
  gating_only: boolean;
  source_document: string;
  source_locator: string;
  effective_from: string | null;
  effective_until: string | null;
  notes: string | null;
  is_current: boolean;
  created_at: string;
}

export interface RuleOut {
  id: string;
  rule_key: string;
  active: boolean;
  current_version: RuleVersionOut | null;
}
