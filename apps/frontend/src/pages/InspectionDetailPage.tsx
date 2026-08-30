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
import { DonutChart, type DonutChartDatum } from "../components/DonutChart";
import { EvidenceImage } from "../components/EvidenceImage";
import { StatusBadge } from "../components/StatusBadge";
import { useAuth } from "../context/AuthContext";
import type { ComplianceCheck, ComplianceStatus, Declaration, EvidenceItem, InspectionDetail } from "../types";
import { ReviewPanel } from "../components/ReviewPanel";

// Presentation-only metadata for the Final Results summary (donut + count
// tiles) — every number still comes straight from
// inspection.compliance_checks, this just supplies a color/label per
// existing ComplianceStatus value. Order here is "most reassuring first"
// (compliant, then issues, then not-applicable) for the summary view; the
// full Evidence tab keeps its own "most urgent first" ordering below.
const FINAL_RESULTS_STATUS_META: Record<ComplianceStatus, { label: string; shortLabel: string; color: string }> = {
  PASS: { label: "Compliant", shortLabel: "PASS", color: "var(--status-pass)" },
  POTENTIAL_NON_COMPLIANCE: { label: "Non-Compliant", shortLabel: "Potential Issue", color: "var(--status-violation)" },
  NEEDS_MANUAL_REVIEW: { label: "Review", shortLabel: "Needs Manual Review", color: "var(--status-review)" },
  UNABLE_TO_VERIFY: { label: "Unable to Verify", shortLabel: "", color: "var(--status-unable)" },
  NOT_APPLICABLE: { label: "Not Applicable", shortLabel: "", color: "var(--status-na)" },
};
const FINAL_RESULTS_STATUS_ORDER: ComplianceStatus[] = [
  "PASS",
  "POTENTIAL_NON_COMPLIANCE",
  "NEEDS_MANUAL_REVIEW",
  "UNABLE_TO_VERIFY",
  "NOT_APPLICABLE",
];

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

/** Given one finding's evidence entry, resolves which image (and, if
 * traceable to a specific OCR block, which region of it) that evidence
 * came from — the link a click uses to jump straight to the source photo
 * with the exact region highlighted (Demo Hardening: "make rule -> evidence
 * -> finding traceability obvious"). Returns null for evidence that isn't
 * image-sourced at all (e.g. WEBPAGE_TEXT/MANUAL). */
function resolveEvidenceTarget(
  ev: EvidenceItem,
  declarations: Declaration[]
): { imageId: string; ocrResultId: string | null } | null {
  const refImageId = typeof ev.reference?.product_image_id === "string" ? (ev.reference.product_image_id as string) : null;
  const decl = ev.declaration_id ? declarations.find((d) => d.id === ev.declaration_id) : undefined;
  const imageId = refImageId ?? decl?.source_product_image_id ?? null;
  if (!imageId) return null;
  return { imageId, ocrResultId: decl?.source_ocr_result_id ?? null };
}

export function InspectionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const [inspection, setInspection] = useState<InspectionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [files, setFiles] = useState<FileList | null>(null);
  const [uploading, setUploading] = useState(false);
  const [reportLink, setReportLink] = useState<string | null>(null);
  const [highlight, setHighlight] = useState<{ imageId: string; ocrResultId: string | null } | null>(null);
  const [activeResultTab, setActiveResultTab] = useState<"EVIDENCE" | "FINAL_RESULTS">("FINAL_RESULTS");
  const [pendingFindingScroll, setPendingFindingScroll] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  // Deep-link from a Final Results "key finding" row to its full card in the
  // Evidence tab: switch tabs, then (once the Evidence tab's content is
  // actually in the DOM) scroll to and briefly highlight that finding. No
  // data changes hands here — both tabs render from the same `inspection`
  // state, so nothing is refetched or lost switching between them.
  useEffect(() => {
    if (activeResultTab !== "EVIDENCE" || !pendingFindingScroll) return;
    const el = document.getElementById(`finding-${pendingFindingScroll}`);
    el?.scrollIntoView({ behavior: "smooth", block: "center" });
    setPendingFindingScroll(null);
  }, [activeResultTab, pendingFindingScroll]);

  function handleJumpToFinding(checkId: string) {
    setActiveResultTab("EVIDENCE");
    setPendingFindingScroll(checkId);
  }

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

  // True for three cases: (1) an automatic fetch attempt failed outright,
  // (2) a manual-scan inspection never had a listing URL to fetch, or (3)
  // the fetch technically succeeded (HTTP 200) but extracted nothing usable
  // at all — a real failure mode a live-listing test surfaced (e.g. a
  // quick-commerce listing that requires a delivery location LM-SCAN's
  // fetcher never provides, silently returning its generic homepage
  // instead of the product page). All three need the same upload-fallback
  // card; case 3 is distinguished from a genuinely empty/UNABLE_TO_VERIFY
  // COMPLETED inspection by checking for zero declarations specifically.
  const hollowSuccess =
    inspection.status === "COMPLETED" && !!inspection.source_url && inspection.declarations.length === 0;
  const fetchFailed =
    !inspection.source_url || inspection.web_pages.some((wp) => wp.fetch_status !== "SUCCESS") || hollowSuccess;
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

  function handleTraceEvidence(ev: EvidenceItem) {
    const target = inspection && resolveEvidenceTarget(ev, inspection.declarations);
    if (!target) return;
    setHighlight(target);
    document.getElementById(`evidence-image-${target.imageId}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  const groupedChecks: Record<string, ComplianceCheck[]> = {};
  for (const check of inspection.compliance_checks) {
    (groupedChecks[check.status] ??= []).push(check);
  }
  const statusOrder = ["POTENTIAL_NON_COMPLIANCE", "NEEDS_MANUAL_REVIEW", "UNABLE_TO_VERIFY", "PASS", "NOT_APPLICABLE"];
  const sortedDeclarations = [...inspection.declarations].sort((a, b) => a.field_name.localeCompare(b.field_name));

  // Final Results tab: a summary of the same inspection.compliance_checks
  // used above — same counts, same statuses, no separate scoring system.
  const totalRulesEvaluated = inspection.compliance_checks.length;
  const donutData: DonutChartDatum[] = FINAL_RESULTS_STATUS_ORDER.map((status) => ({
    key: status,
    label: FINAL_RESULTS_STATUS_META[status].label,
    count: (groupedChecks[status] ?? []).length,
    color: FINAL_RESULTS_STATUS_META[status].color,
  }));
  // "Important findings" for the at-a-glance summary: anything that isn't a
  // clean PASS or an explicit NOT_APPLICABLE — the cases an officer actually
  // needs to look at. Full detail for each stays in the Evidence tab; this
  // is just a jump-off list.
  const keyFindings = inspection.compliance_checks.filter(
    (c) => c.status === "POTENTIAL_NON_COMPLIANCE" || c.status === "NEEDS_MANUAL_REVIEW" || c.status === "UNABLE_TO_VERIFY"
  );

  return (
    <div>
      <h1>
        {inspection.inspection_number}
        {inspection.is_demo && (
          <span
            title="Reproducible fixture data, not a live scan — see the Demo Inspection notes below."
            style={{
              marginLeft: 10, fontSize: 11, fontWeight: 700, letterSpacing: 0.5, padding: "3px 8px",
              borderRadius: 999, background: "#7c3aed", color: "#fff", verticalAlign: "middle",
            }}
          >
            DEMO
          </span>
        )}
      </h1>
      <p className="page-subtitle">
        {inspection.product_title ?? inspection.source_url ?? "Manual inspection — no listing URL"} · Platform:{" "}
        {inspection.platform ?? "unknown"}
      </p>
      {inspection.is_demo && (
        <p style={{ fontSize: 12.5, color: "#7c3aed", marginTop: -8, marginBottom: 12 }}>
          Demo Inspection — sourced from a bundled, reproducible fixture (a real listing capture) instead of a
          live fetch, so this exact result is guaranteed regardless of network conditions. Not a finding about a
          real, currently-live listing.
        </p>
      )}

      <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 16, flexWrap: "wrap" }}>
        <StatusBadge status={inspection.status} />
        <StatusBadge status={inspection.overall_status} />
        {inspection.pipeline_duration_ms != null && (
          <span style={{ fontSize: 12.5, color: "var(--color-text-muted)" }}>
            Analysis completed in {(inspection.pipeline_duration_ms / 1000).toFixed(1)}s
          </span>
        )}
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
                (hollowSuccess
                  ? "The page was fetched, but no usable product data could be extracted from it (the listing may require a delivery location or client-side rendering this fetcher couldn't complete)."
                  : "The page could not be automatically retrieved.")
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

          <div className="result-tabs" role="tablist" aria-label="Inspection result view">
            <button
              type="button"
              role="tab"
              aria-selected={activeResultTab === "EVIDENCE"}
              className={`result-tab${activeResultTab === "EVIDENCE" ? " result-tab--active" : ""}`}
              onClick={() => setActiveResultTab("EVIDENCE")}
            >
              Evidence
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={activeResultTab === "FINAL_RESULTS"}
              className={`result-tab${activeResultTab === "FINAL_RESULTS" ? " result-tab--active" : ""}`}
              onClick={() => setActiveResultTab("FINAL_RESULTS")}
            >
              Final Results
              <span className="result-tab__count">{totalRulesEvaluated}</span>
            </button>
          </div>

          {activeResultTab === "FINAL_RESULTS" && (
            <div>
              <div className="final-results__hero">
                <div>
                  <p className="final-results__hero-label">Overall Inspection Status</p>
                  <div className="final-results__hero-status">
                    <StatusBadge status={inspection.overall_status} />
                  </div>
                </div>
              </div>

              <div className="card">
                <h3>Rule Evaluation Summary</h3>
                <div className="final-results__summary">
                  <DonutChart data={donutData} total={totalRulesEvaluated} />
                  <div className="status-count-grid">
                    {FINAL_RESULTS_STATUS_ORDER.map((status) => {
                      const count = (groupedChecks[status] ?? []).length;
                      if (count === 0) return null;
                      const meta = FINAL_RESULTS_STATUS_META[status];
                      return (
                        <div key={status} className="status-count-tile">
                          <span className="status-count-tile__dot" style={{ background: meta.color }} />
                          <div>
                            <div className="status-count-tile__count">{count}</div>
                            <div className="status-count-tile__label">
                              {meta.label}
                              {meta.shortLabel ? ` · ${meta.shortLabel}` : ""}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
                <p style={{ fontSize: 12.5, color: "var(--color-text-muted)", marginTop: 14, marginBottom: 0 }}>
                  Total Rules Evaluated: <strong>{totalRulesEvaluated}</strong>
                </p>
              </div>

              <div className="card">
                <h3>Key Findings</h3>
                {keyFindings.length === 0 ? (
                  <p style={{ fontSize: 13, color: "var(--color-text-muted)" }}>
                    No potential issues or manual-review items were flagged.
                  </p>
                ) : (
                  <ul className="key-findings-list">
                    {keyFindings.map((check) => (
                      <li key={check.id}>
                        <span>
                          <StatusBadge status={check.status} /> {check.rule.title}
                        </span>
                        <button
                          type="button"
                          className="key-findings-list__jump"
                          onClick={() => handleJumpToFinding(check.id)}
                        >
                          View in Evidence →
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
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
            </div>
          )}

          {activeResultTab === "EVIDENCE" && (
            <div>
          <h2>Legal Metrology Findings</h2>
          <p style={{ fontSize: 12.5, color: "var(--color-text-muted)", marginTop: -6 }}>
            Each finding cites the rule it checks, the reasoning, and the underlying evidence — click an evidence
            line to jump to the exact photo (and OCR region, when traceable to one) it came from.
          </p>
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
                    <div id={`finding-${check.id}`} className={`card check-card status-${check.status}`}>
                      <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 6 }}>
                        <strong>{check.rule.title}</strong>
                        <ConfidenceBar confidence={check.confidence} />
                      </div>
                      <p style={{ fontSize: 12.5, color: "var(--color-text-muted)", margin: "4px 0" }}>
                        {check.rule.rule_key} — {check.rule.rule_reference} · Source: {check.rule.source_document} (
                        {check.rule.source_locator}) · v{check.rule.version_number}
                      </p>
                      <p style={{ fontSize: 13 }}>{check.reason}</p>

                      {check.evidence.length > 0 && (
                        <details open={check.status === "POTENTIAL_NON_COMPLIANCE"}>
                          <summary style={{ cursor: "pointer", fontSize: 12.5 }}>
                            View evidence ({check.evidence.length})
                          </summary>
                          {check.evidence.map((ev) => {
                            const target = resolveEvidenceTarget(ev, inspection.declarations);
                            return (
                              <div key={ev.id} className="evidence-item">
                                {target ? (
                                  <button
                                    type="button"
                                    onClick={() => handleTraceEvidence(ev)}
                                    style={{
                                      background: "none", border: "none", padding: 0, cursor: "pointer",
                                      color: "var(--color-primary)", textDecoration: "underline", fontSize: 12.5,
                                      textAlign: "left",
                                    }}
                                  >
                                    [{ev.evidence_type}] {ev.description} — view source photo ↓
                                  </button>
                                ) : (
                                  <span>
                                    [{ev.evidence_type}] {ev.description}
                                  </span>
                                )}
                              </div>
                            );
                          })}
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
                <tr><th>Field</th><th>Value</th><th>Normalized</th><th>Source</th><th>Confidence</th></tr>
              </thead>
              <tbody>
                {sortedDeclarations.map((d) => (
                  <tr key={d.id}>
                    <td>{d.field_name}</td>
                    <td>{d.value}</td>
                    <td style={{ color: "var(--color-text-muted)" }}>{d.normalized_value ?? "—"}</td>
                    <td>
                      {d.source_product_image_id ? (
                        <button
                          type="button"
                          onClick={() => {
                            setHighlight({ imageId: d.source_product_image_id!, ocrResultId: d.source_ocr_result_id });
                            document
                              .getElementById(`evidence-image-${d.source_product_image_id}`)
                              ?.scrollIntoView({ behavior: "smooth", block: "center" });
                          }}
                          style={{
                            background: "none", border: "none", padding: 0, cursor: "pointer",
                            color: "var(--color-primary)", textDecoration: "underline",
                          }}
                        >
                          <span className="tag">{d.source_type}</span>
                        </button>
                      ) : (
                        <span className="tag">{d.source_type}</span>
                      )}
                    </td>
                    <td><ConfidenceBar confidence={d.confidence} /></td>
                  </tr>
                ))}
                {inspection.declarations.length === 0 && <tr><td colSpan={5}>No declarations extracted.</td></tr>}
              </tbody>
            </table>
          </div>

          <h2>Product Images</h2>
          <p style={{ fontSize: 12.5, color: "var(--color-text-muted)", marginTop: -6 }}>
            Blue outlines mark every text region OCR detected; click an evidence or declaration source link above to
            highlight the exact region it came from.
          </p>
          <div className="image-grid">
            {inspection.images.map((img) => (
              <div key={img.id} id={`evidence-image-${img.id}`} className="image-tile" style={{ padding: 0, overflow: "hidden" }}>
                <div
                  style={
                    highlight?.imageId === img.id
                      ? { outline: "3px solid #e6a700", outlineOffset: -3 }
                      : undefined
                  }
                >
                  <EvidenceImage
                    inspectionId={inspection.id}
                    image={img}
                    highlightOcrResultId={highlight?.imageId === img.id ? highlight.ocrResultId : null}
                  />
                </div>
                <div style={{ padding: "6px 8px", fontSize: 12 }}>
                  <div>{img.source_type} · {img.width}×{img.height}</div>
                  {img.quality_acceptable === false && <div style={{ color: "var(--status-review)" }}>Low quality{img.quality_notes ? `: ${img.quality_notes}` : ""}</div>}
                </div>
              </div>
            ))}
            {inspection.images.length === 0 && <p style={{ fontSize: 13 }}>No images available.</p>}
          </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
