import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getDashboardStatistics, listInspections } from "../api/endpoints";
import { StatusBadge } from "../components/StatusBadge";
import type { DashboardStatistics, InspectionSummary } from "../types";

export function DashboardPage() {
  const [stats, setStats] = useState<DashboardStatistics | null>(null);
  const [recent, setRecent] = useState<InspectionSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getDashboardStatistics().then(setStats).catch((e) => setError(e.message));
    listInspections({ limit: "8" }).then(setRecent).catch(() => {});
  }, []);

  if (error) return <p className="error-text">{error}</p>;
  if (!stats) return <p className="loading-text">Loading dashboard…</p>;

  return (
    <div>
      <h1>Dashboard</h1>
      <p className="page-subtitle">Fleet-wide view of online inspection activity and outcomes.</p>

      <div className="stat-grid">
        <div className="stat-tile">
          <div className="value">{stats.total_online_inspections}</div>
          <div className="label">Total inspections</div>
        </div>
        <div className="stat-tile">
          <div className="value" style={{ color: "var(--status-pass)" }}>{stats.passed}</div>
          <div className="label">Passed</div>
        </div>
        <div className="stat-tile">
          <div className="value" style={{ color: "var(--status-violation)" }}>{stats.potential_violations}</div>
          <div className="label">Potential violations</div>
        </div>
        <div className="stat-tile">
          <div className="value" style={{ color: "var(--status-review)" }}>{stats.needs_review}</div>
          <div className="label">Needs review</div>
        </div>
        <div className="stat-tile">
          <div className="value" style={{ color: "var(--status-unable)" }}>{stats.unable_to_verify}</div>
          <div className="label">Unable to verify</div>
        </div>
        <div className="stat-tile">
          <div className="value">{stats.review_backlog}</div>
          <div className="label">Review backlog</div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <div className="card">
          <h3>Inspections by platform</h3>
          <table>
            <tbody>
              {stats.by_platform.length === 0 && <tr><td>No data yet.</td></tr>}
              {stats.by_platform.map((row) => (
                <tr key={row.key}><td>{row.key}</td><td>{row.count}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="card">
          <h3>Inspections by category</h3>
          <table>
            <tbody>
              {stats.by_category.length === 0 && <tr><td>No data yet.</td></tr>}
              {stats.by_category.map((row) => (
                <tr key={row.key}><td>{row.key}</td><td>{row.count}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="card">
          <h3>Most common issues</h3>
          <table>
            <tbody>
              {stats.common_issues.length === 0 && <tr><td>No violations recorded yet.</td></tr>}
              {stats.common_issues.map((row) => (
                <tr key={row.key}><td>{row.key}</td><td>{row.count}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="card">
          <h3>Violations by rule</h3>
          <table>
            <tbody>
              {stats.violations_by_rule.length === 0 && <tr><td>No violations recorded yet.</td></tr>}
              {stats.violations_by_rule.map((row) => (
                <tr key={row.key}><td>{row.key}</td><td>{row.count}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <h2>Recent inspections</h2>
      <div className="card" style={{ padding: 0 }}>
        <table>
          <thead>
            <tr><th>Inspection</th><th>Platform</th><th>Status</th><th>Result</th><th>Created</th></tr>
          </thead>
          <tbody>
            {recent.map((i) => (
              <tr key={i.id}>
                <td>
                  <Link to={`/inspections/${i.id}`}>{i.inspection_number}</Link>
                  {i.is_demo && (
                    <span style={{ marginLeft: 6, fontSize: 10, fontWeight: 700, padding: "2px 6px", borderRadius: 999, background: "#7c3aed", color: "#fff" }}>
                      DEMO
                    </span>
                  )}
                </td>
                <td>{i.platform ?? "—"}</td>
                <td><StatusBadge status={i.status} /></td>
                <td><StatusBadge status={i.overall_status} /></td>
                <td>{new Date(i.created_at).toLocaleString()}</td>
              </tr>
            ))}
            {recent.length === 0 && <tr><td colSpan={5}>No inspections yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
