import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { createInspection, scanUrl } from "../api/endpoints";

const PLATFORM_HINTS: { match: RegExp; label: string }[] = [
  { match: /blinkit\.com/i, label: "Blinkit" },
  { match: /zeptonow\.com/i, label: "Zepto" },
  { match: /bigbasket\.com/i, label: "BigBasket" },
  { match: /amazon\.in/i, label: "Amazon" },
  { match: /flipkart\.com/i, label: "Flipkart" },
];

export function NewInspectionPage() {
  const [url, setUrl] = useState("");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  const detectedPlatform = PLATFORM_HINTS.find((p) => p.match.test(url))?.label;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const inspection = await createInspection(url, notes || undefined);
      await scanUrl(inspection.id);
      navigate(`/inspections/${inspection.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start inspection.");
      setSubmitting(false);
    }
  }

  // No listing URL at all — the officer inspects entirely from photos they
  // take/upload themselves. Deliberately skips scanUrl(): there is nothing
  // to fetch, and the inspection detail page's upload card (which already
  // exists for the "automatic fetch failed" case) is now reachable directly
  // from here instead of only after a failed URL scan.
  async function handleManualScan() {
    setSubmitting(true);
    setError(null);
    try {
      const inspection = await createInspection(undefined, notes || undefined);
      navigate(`/inspections/${inspection.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start manual inspection.");
      setSubmitting(false);
    }
  }

  return (
    <div>
      <h1>New Online Inspection</h1>
      <p className="page-subtitle">
        Paste a product listing URL from a quick-commerce or e-commerce marketplace. LM-SCAN will
        attempt automatic retrieval, extraction, OCR, and rule-based compliance screening.
      </p>

      <div className="card" style={{ maxWidth: 560 }}>
        <form onSubmit={handleSubmit}>
          <div className="form-row">
            <label htmlFor="url">Product listing URL</label>
            <input
              id="url"
              type="url"
              required
              placeholder="https://blinkit.com/prn/.../prid/..."
              value={url}
              onChange={(e) => setUrl(e.target.value)}
            />
            {detectedPlatform && (
              <p style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 4 }}>
                Detected platform: <strong>{detectedPlatform}</strong>
              </p>
            )}
            <p style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 6 }}>
              Don't have a URL?{" "}
              <button
                type="button"
                onClick={handleManualScan}
                disabled={submitting}
                style={{ fontSize: 12, padding: 0, border: "none", background: "none", color: "var(--color-primary)", textDecoration: "underline", cursor: "pointer" }}
              >
                Scan manually — take or upload photos instead
              </button>
            </p>
          </div>
          <div className="form-row">
            <label htmlFor="notes">Notes (optional)</label>
            <textarea id="notes" rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} />
          </div>
          <button type="submit" disabled={submitting}>
            {submitting ? "Starting scan…" : "Start scan"}
          </button>
          {error && <p className="error-text">{error}</p>}
        </form>
      </div>

      <div className="card" style={{ maxWidth: 560 }}>
        <h3>If automatic retrieval fails</h3>
        <p style={{ fontSize: 13, color: "var(--color-text-muted)" }}>
          Some marketplace pages cannot be automatically retrieved (access restrictions, anti-bot
          protection, or robots.txt). If that happens, the inspection page will show{" "}
          <em>"Automatic page extraction unavailable"</em> and let you upload screenshots instead —
          the analysis pipeline (OCR, declaration extraction, compliance checks) runs the same way
          either way. Or skip straight to that by using "Scan manually" above if you never had a
          URL to begin with.
        </p>
      </div>
    </div>
  );
}
