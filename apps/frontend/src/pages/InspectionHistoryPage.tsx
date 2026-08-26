import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listInspections } from "../api/endpoints";
import { StatusBadge } from "../components/StatusBadge";
import type { InspectionSummary } from "../types";

export function InspectionHistoryPage() {
  const [inspections, setInspections] = useState<InspectionSummary[]>([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [overallFilter, setOverallFilter] = useState("");
  const [platformFilter, setPlatformFilter] = useState("");
  const [loading, setLoading] = useState(true);

  function refresh() {
    setLoading(true);
    const params: Record<string, string> = {};
    if (statusFilter) params.status = statusFilter;
    if (overallFilter) params.overall_status = overallFilter;
    if (platformFilter) params.platform = platformFilter;
    listInspections(params)
      .then(setInspections)
      .finally(() => setLoading(false));
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(refresh, [statusFilter, overallFilter, platformFilter]);

  return (
    <div>
      <h1>Inspection History</h1>
      <p className="page-subtitle">Search and filter previous online inspections.</p>

      <div className="filters-row">
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">All pipeline statuses</option>
          <option value="CREATED">Created</option>
          <option value="IN_PROGRESS">In progress</option>
          <option value="COMPLETED">Completed</option>
          <option value="FAILED">Failed</option>
        </select>
        <select value={overallFilter} onChange={(e) => setOverallFilter(e.target.value)}>
          <option value="">All results</option>
          <option value="PASS">Pass</option>
          <option value="POTENTIAL_NON_COMPLIANCE">Potential non-compliance</option>
          <option value="NEEDS_MANUAL_REVIEW">Needs manual review</option>
          <option value="NOT_APPLICABLE">Not applicable</option>
          <option value="UNABLE_TO_VERIFY">Unable to verify</option>
        </select>
        <input
          type="text"
          placeholder="Platform (e.g. blinkit)"
          value={platformFilter}
          onChange={(e) => setPlatformFilter(e.target.value)}
        />
      </div>

      <div className="card" style={{ padding: 0 }}>
        <table>
          <thead>
            <tr>
              <th>Inspection</th><th>Product</th><th>Platform</th><th>Officer</th>
              <th>Status</th><th>Result</th><th>Created</th>
            </tr>
          </thead>
          <tbody>
            {loading && <tr><td colSpan={7} className="loading-text">Loading…</td></tr>}
            {!loading && inspections.length === 0 && <tr><td colSpan={7}>No inspections match these filters.</td></tr>}
            {inspections.map((i) => (
              <tr key={i.id}>
                <td>
                  <Link to={`/inspections/${i.id}`}>{i.inspection_number}</Link>
                  {i.is_demo && (
                    <span style={{ marginLeft: 6, fontSize: 10, fontWeight: 700, padding: "2px 6px", borderRadius: 999, background: "#7c3aed", color: "#fff" }}>
                      DEMO
                    </span>
                  )}
                </td>
                <td>{i.product_title ?? "—"}</td>
                <td>{i.platform ?? "—"}</td>
                <td>{i.officer_name ?? "—"}</td>
                <td><StatusBadge status={i.status} /></td>
                <td><StatusBadge status={i.overall_status} /></td>
                <td>{new Date(i.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
