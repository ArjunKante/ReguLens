import { api } from "./client";
import type {
  DashboardStatistics,
  InspectionDetail,
  InspectionSummary,
  LoginResponse,
  ProductImage,
  ReviewDecision,
  RuleOut,
  User,
} from "../types";

export function login(email: string, password: string) {
  return api.post<LoginResponse>("/auth/login", { email, password });
}

export function listInspections(params: Record<string, string> = {}) {
  const query = new URLSearchParams(params).toString();
  return api.get<InspectionSummary[]>(`/inspections${query ? `?${query}` : ""}`);
}

export function getInspection(id: string) {
  return api.get<InspectionDetail>(`/inspections/${id}`);
}

export function createInspection(sourceUrl: string, notes?: string) {
  return api.post<InspectionSummary>("/inspections", { source_url: sourceUrl, notes });
}

export function scanUrl(id: string) {
  return api.post<{ status: string }>(`/inspections/${id}/scan-url`, {});
}

export function analyzeInspection(id: string) {
  return api.post<{ status: string }>(`/inspections/${id}/analyze`, {});
}

export function uploadScreenshots(id: string, files: File[]) {
  const formData = new FormData();
  for (const file of files) formData.append("files", file);
  return api.postForm<ProductImage[]>(`/inspections/${id}/screenshots`, formData);
}

export function submitReview(
  inspectionId: string,
  complianceCheckId: string,
  decision: string,
  finalStatus: string | null,
  comment: string,
  reason: string
) {
  return api.post<ReviewDecision>(`/inspections/${inspectionId}/review`, {
    compliance_check_id: complianceCheckId,
    decision,
    final_status: finalStatus,
    comment,
    reason,
  });
}

export function generateReport(id: string, fmt: "PDF" | "HTML") {
  return api.post<{ report_id: string; download_url: string; format: string }>(
    `/inspections/${id}/report?fmt=${fmt}`
  );
}

/** The download endpoint requires the Bearer token, so a plain <a href> to it
 * would 401 — this fetches it through the authenticated client and returns an
 * object URL the caller can open/assign to a link. */
export async function fetchReportObjectUrl(reportId: string): Promise<string> {
  const blob = await api.getBlob(`/reports/${reportId}/download`);
  return URL.createObjectURL(blob);
}

export function getDashboardStatistics() {
  return api.get<DashboardStatistics>("/dashboard/statistics");
}

export function listRules() {
  return api.get<RuleOut[]>("/rules");
}

export function listUsers() {
  return api.get<User[]>("/users");
}

export function createUser(email: string, password: string, fullName: string, role: string) {
  return api.post<User>("/users", { email, password, full_name: fullName, role });
}

export function addManualDeclaration(inspectionId: string, fieldName: string, value: string) {
  return api.post(`/inspections/${inspectionId}/declarations`, { field_name: fieldName, value });
}
