import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listBatches } from "../api/endpoints";
import { StatusBadge } from "../components/StatusBadge";
import { useAuth } from "../context/AuthContext";
import type { BatchSummary } from "../types";

export function BatchHistoryPage() {
  const { user } = useAuth();
  const [batches, setBatches] = useState<BatchSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listBatches()
      .then(setBatches)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 12 }}>
        <div>
          <h1>Batch Scans</h1>
          <p className="page-subtitle">Past and in-progress bulk scans — each links to its triage queue.</p>
        </div>
        {(user?.role === "ADMIN" || user?.role === "INSPECTOR") && (
          <Link to="/batches/new">
            <button type="button">New Batch Scan</button>
          </Link>
        )}
      </div>

      <div className="card" style={{ padding: 0 }}>
        <table>
          <thead>
            <tr>
              <th>Batch</th>
              <th>Status</th>
              <th>Progress</th>
              <th>Started by</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={5} className="loading-text">
                  Loading…
                </td>
              </tr>
            )}
            {!loading && batches.length === 0 && (
              <tr>
                <td colSpan={5}>No batch scans yet.</td>
              </tr>
            )}
            {batches.map((b) => (
              <tr key={b.id}>
                <td>
                  <Link to={`/batches/${b.id}`}>{b.name || `Batch ${b.id.slice(0, 8)}`}</Link>
                </td>
                <td>
                  <StatusBadge status={b.status} />
                </td>
                <td>
                  {b.processed_count} / {b.total_count}
                </td>
                <td>{b.created_by_name ?? "—"}</td>
                <td>{new Date(b.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
