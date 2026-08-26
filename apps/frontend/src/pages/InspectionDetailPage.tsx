import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import {
  analyzeInspection,
  fetchReportObjectUrl,
  generateReport,
  getInspection,
  uploadScreenshots,
} from "../api/endpoints";
import AnimatedList from "../components/AnimatedList";
import { ConfidenceBar } from "../components/ConfidenceBar";
import { DisclaimerBanner } from "../components/DisclaimerBanner";
import { StatusBadge } from "../components/StatusBadge";
import { useAuth } from "../context/AuthContext";
import type { ComplianceCheck, InspectionDetail } from "../types";
import { ReviewPanel } from "../components/ReviewPanel";

const PIPELINE_STAGE_LABELS: Record<string, string> = {
  FETCH: "Fetching product page",
  PARSE: "Parsing structured page data",
  IMAGE_DOWNLOAD: "Downloading product images",
  IMAGE_QUALITY: "Assessing image quality",
  OCR: "Running OCR",
  DECLARATION_EXTRACTION: "Extracting declarations",
  CLASSIFICATION: "Classifying product",
  RULE_SELECTION: "Selecting applicable rules",
  COMPLIANCE: "Applying compliance rules",
  CONSISTENCY: "Checking cross-source consistency",
  REPORT: "Finalizing results",
};

export function InspectionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const [inspection, setInspection] = useState<InspectionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [files, setFiles] = useState<FileList | null>(null);
  const [uploading, setUploading] = useState(false);
  const [reportLink, setReportLink] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  const load = useCallback(async () => {
    if (!id) return;
    try {
      const data = await getInspection(id);
      setInspection(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load inspection.");
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (inspection?.status === "IN_PROGRESS" || inspection?.status === "CREATED") {
      pollRef.current = window.setInterval(load, 2000);
      return () => {
        if (pollRef.current) window.clearInterval(pollRef.current);
      };
    }
    return undefined;
  }, [inspection?.status, load]);

  if (error) return <p className="error-text">{error}</p>;
  if (!inspection) return <p className="loading-text">Loading inspection…</p>;

  // True both for the original case (an automatic fetch attempt failed) and
  // for a manual-scan inspection (no listing URL was ever provided, so
  // there was never a fetch to attempt) — either way the officer needs the
  // upload-screenshots card below.
  const fetchFailed = !inspection.source_url || inspection.web_pages.some((wp) => wp.fetch_status !== "SUCCESS");
  const canAct = user?.role === "ADMIN" || user?.role === "INSPECTOR";
  const canReview = user?.role === "ADMIN" || user?.role === "REVIEWER";

  async function handleUpload() {
    if (!files || !id) return;
    setUploading(true);
    try {
      await uploadScreenshots(id, Array.from(files));
      await analyzeInspection(id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setUploading(false);
    }
  }

  async function handleReport(fmt: "PDF" | "HTML") {
    if (!id) return;
    const result = await generateReport(id, fmt);
    // The download endpoint requires the Bearer token, so we fetch it
    // through the authenticated API client and hand the browser a local
    // object URL rather than linking directly to the API (which a plain
    // <a href> would hit unauthenticated and get a 401 from).
    const objectUrl = await fetchReportObjectUrl(result.report_id);
    setReportLink(objectUrl);
  }

  const groupedChecks: Record<string, ComplianceCheck[]> = {};
  for (const check of inspection.compliance_checks) {
    (groupedChecks[check.status] ??= []).push(check);
  }
  const statusOrder = ["POTENTIAL_NON_COMPLIANCE", "NEEDS_MANUAL_REVIEW", "UNABLE_TO_VERIFY", "PASS", "NOT_APPLICABLE"];

  return (
    <div>
      <h1>{inspection.inspection_number}</h1>
      <p className="page-subtitle">
        {inspection.product_title ?? inspection.source_url ?? "Manual inspection — no listing URL"} · Platform:{" "}
        {inspection.platform ?? "unknown"}
      </p>

      <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 16 }}>
        <StatusBadge status={inspection.status} />
        <StatusBadge status={inspection.overall_status} />
        {inspection.source_url && (
          <a href={inspection.source_url} target="_blank" rel="noreferrer" style={{ fontSize: 12.5 }}>
            View original listing ↗
          </a>
        )}
      </div>

      {(inspection.status === "IN_PROGRESS" || inspection.status === "CREATED") && (
        <div className="card">
          <h3>Analysis progress</h3>
          <ul className="pipeline-list">
            {Object.keys(PIPELINE_STAGE_LABELS).map((stage) => {
              const events = inspection.pipeline_events.filter((e) => e.stage === stage);
              const latest = events[events.length - 1];
              return (
                <li key={stage}>
                  <span className={`pipeline-dot ${latest?.status ?? "PENDING"}`} />
                  {PIPELINE_STAGE_LABELS[stage]}
                  {latest?.message && <span style={{ color: "var(--color-text-muted)" }}> — {latest.message}</span>}
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {fetchFailed && canAct && (
        <div className="card">
          <h3>{inspection.source_url ? "Automatic page extraction unavailable" : "Manual scan — upload or take photos"}</h3>
          <p style={{ fontSize: 13 }}>
            {inspection.source_url
              ? inspection.web_pages.find((wp) => wp.fetch_status !== "SUCCESS")?.error_message ??
                "The page could not be automatically retrieved."
              : "No listing URL was provided for this inspection."}{" "}
            Upload or take photos of the product listing/label to continue this inspection.
          </p>
          <input
            type="file"
            multiple
            accept="image/png,image/jpeg,image/webp"
            capture="environment"
            onChange={(e) => setFiles(e.target.files)}
          />
          <button onClick={handleUpload} disabled={!files || uploading} style={{ marginLeft: 10 }}>
            {uploading ? "Uploading…" : "Upload screenshots & re-analyze"}
          </button>
        </div>
      )}

      {inspection.status === "COMPLETED" && (
        <>
          <DisclaimerBanner />

          <h2>Legal Metrology Findings</h2>
          {statusOrder.map((status) => {
            const checks = groupedChecks[status] ?? [];
            if (checks.length === 0) return null;
            return (
              <div key={status} style={{ marginBottom: 18 }}>
                <h3>
                  <StatusBadge status={status} /> ({checks.length})
                </h3>
                <AnimatedList
                  items={checks}
                  showGradients
                  // Off, not just guarded: with up to five of these lists on
                  // one page (one per status group), each would otherwise
                  // register its own global Tab/Arrow listener and fight
                  // over the keystroke. The findings cards below also embed
                  // real form controls (ReviewPanel), so hijacking Tab site-
                  // wide the moment this mounts would break normal focus
                  // navigation through them — the entrance/hover animation
                  // is what's actually wanted here, not list keynav.
                  enableArrowNavigation={false}
                  displayScrollbar={checks.length > 3}
                  initialSelectedIndex={null}
                  renderItem={(check: ComplianceCheck) => (
                    <div className={`card check-card status-${check.status}`}>
                      <div style={{ display: "flex", justifyContent: "space-between" }}>
                        <strong>{check.rule.title}</strong>
                        <ConfidenceBar confidence={check.confidence} />
                      </div>
                      <p style={{ fontSize: 12.5, color: "var(--color-text-muted)", margin: "4px 0" }}>
                        {check.rule.rule_key} — {check.rule.rule_reference} · Source: {check.rule.source_document} (
                        {check.rule.source_locator}) · v{check.rule.version_number}
                      </p>
                      <p style={{ fontSize: 13 }}>{check.reason}</p>

                      {check.evidence.length > 0 && (
                        <details>
                          <summary style={{ cursor: "pointer", fontSize: 12.5 }}>
                            View evidence ({check.evidence.length})
                          </summary>
                          {check.evidence.map((ev) => (
                            <div key={ev.id} className="evidence-item">
                              [{ev.evidence_type}] {ev.description}
                            </div>
                          ))}
                        </details>
                      )}

                      {canReview && <ReviewPanel inspectionId={inspection.id} check={check} onReviewed={load} />}
                      {!canReview && check.review_decisions.length > 0 && (
                        <div style={{ marginTop: 8, fontSize: 12.5 }}>
                          {check.review_decisions.map((rd) => (
                            <div key={rd.id}>
                              Reviewer decision: <strong>{rd.decision}</strong> → {rd.final_status} by {rd.reviewer_name}
                              {rd.comment ? `: ${rd.comment}` : ""}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                />
              </div>
            );
          })}

          <h2>Extracted Declarations</h2>
          <div className="card" style={{ padding: 0 }}>
            <table>
              <thead>
                <tr><th>Field</th><th>Value</th><th>Source</th><th>Confidence</th></tr>
              </thead>
              <tbody>
                {inspection.declarations.map((d) => (
                  <tr key={d.id}>
                    <td>{d.field_name}</td>
                    <td>{d.value}</td>
                    <td><span className="tag">{d.source_type}</span></td>
                    <td><ConfidenceBar confidence={d.confidence} /></td>
                  </tr>
                ))}
                {inspection.declarations.length === 0 && <tr><td colSpan={4}>No declarations extracted.</td></tr>}
              </tbody>
            </table>
          </div>

          <h2>Product Images</h2>
          <div className="image-grid">
            {inspection.images.map((img) => (
              <div key={img.id} className="image-tile">
                <div>{img.source_type}</div>
                <div>{img.width}×{img.height}</div>
                {img.quality_acceptable === false && <div style={{ color: "var(--status-review)" }}>Low quality</div>}
              </div>
            ))}
            {inspection.images.length === 0 && <p style={{ fontSize: 13 }}>No images available.</p>}
          </div>

          <h2>Generate Report</h2>
          <div className="card">
            <button onClick={() => handleReport("PDF")}>Generate PDF report</button>
            <button className="secondary" onClick={() => handleReport("HTML")} style={{ marginLeft: 8 }}>
              Generate HTML report
            </button>
            {reportLink && (
              <p style={{ marginTop: 10 }}>
                <a href={reportLink} target="_blank" rel="noreferrer">Download report ↗</a>
              </p>
            )}
          </div>
        </>
      )}
    </div>
  );
}
