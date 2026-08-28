import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getBatch } from "../api/endpoints";
import { ConfidenceBar } from "../components/ConfidenceBar";
import { StatusBadge } from "../components/StatusBadge";
import type { BatchDetail } from "../types";

export function BatchDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [batch, setBatch] = useState<BatchDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  const load = useCallback(async () => {
    if (!id) return;
    try {
      const data = await getBatch(id);
      setBatch(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load batch.");
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (batch?.status !== "COMPLETED") {
      pollRef.current = window.setInterval(load, 2000);
      return () => {
        if (pollRef.current) window.clearInterval(pollRef.current);
      };
    }
    return undefined;
  }, [batch?.status, load]);

  if (error) return <p className="error-text">{error}</p>;
  if (!batch) return <p className="loading-text">Loading batch…</p>;

  return (
    <div>
      <h1>{batch.name || "Batch Scan"}</h1>
      <p className="page-subtitle">
        {batch.total_count} listing{batch.total_count === 1 ? "" : "s"} submitted by{" "}
        {batch.created_by_name ?? "—"} on {new Date(batch.created_at).toLocaleString()}. Sorted
        worst-first: most severe, most confidently-flagged results appear at the top.
      </p>

      <div className="card">
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <StatusBadge status={batch.status} />
          <strong>
            {batch.processed_count} / {batch.total_count} processed
          </strong>
          {batch.status !== "COMPLETED" && (
            <span style={{ fontSize: 12, color: "var(--color-text-muted)" }}>Refreshing every 2s…</span>
          )}
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 12 }}>
          {Object.entries(batch.outcome_counts).map(([status, count]) => (
            <span key={status} style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <StatusBadge status={status} /> × {count}
            </span>
          ))}
          {Object.keys(batch.outcome_counts).length === 0 && (
            <span style={{ fontSize: 12, color: "var(--color-text-muted)" }}>No results yet.</span>
          )}
        </div>
      </div>

      {batch.rejected_urls.length > 0 && (
        <div className="card" style={{ borderColor: "var(--color-danger, #d33)" }}>
          <h3>Rejected input ({batch.rejected_urls.length})</h3>
          <p style={{ fontSize: 12, color: "var(--color-text-muted)" }}>
            These entries were never scanned — never silently dropped, shown here so nothing is missed.
          </p>
          <ul style={{ fontSize: 13 }}>
            {batch.rejected_urls.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="card" style={{ padding: 0 }}>
        <table>
          <thead>
            <tr>
              <th>Inspection</th>
              <th>Product</th>
              <th>Platform</th>
              <th>Pipeline</th>
              <th>Result</th>
              <th>Violations</th>
              <th>Highest violation confidence</th>
            </tr>
          </thead>
          <tbody>
            {batch.items.length === 0 && (
              <tr>
                <td colSpan={7} className="loading-text">
                  No items yet.
                </td>
              </tr>
            )}
            {batch.items.map((item) => (
              <tr key={item.id}>
                <td className="nowrap">
                  <Link to={`/inspections/${item.id}`}>{item.inspection_number}</Link>
                </td>
                <td>{item.product_title ?? "—"}</td>
                <td>{item.platform ?? "—"}</td>
                <td>
                  <StatusBadge status={item.status} />
                </td>
                <td>
                  <StatusBadge status={item.overall_status} />
                </td>
                <td>
                  {item.violation_count}
                  {item.critical_violation_count > 0 && (
                    <span style={{ marginLeft: 4, fontSize: 11, color: "var(--color-danger, #d33)" }}>
                      ({item.critical_violation_count} critical)
                    </span>
                  )}
                </td>
                <td>{item.violation_count > 0 ? <ConfidenceBar confidence={item.max_violation_confidence} /> : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
