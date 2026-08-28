import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { createBatch } from "../api/endpoints";

// Soft, client-side mirror of the backend's `batch_max_urls` setting
// (default 50) — purely a heads-up before submitting; the server is the
// real, authoritative enforcement and returns exactly which URLs it
// rejected (and why) in the batch it creates.
const SOFT_MAX_URLS_HINT = 50;

function parseUrls(raw: string): string[] {
  const seen = new Set<string>();
  const urls: string[] = [];
  for (const line of raw.split("\n")) {
    const url = line.trim();
    if (!url || seen.has(url)) continue;
    seen.add(url);
    urls.push(url);
  }
  return urls;
}

export function BatchNewPage() {
  const [name, setName] = useState("");
  const [urlText, setUrlText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  const urls = parseUrls(urlText);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (urls.length === 0) {
      setError("Paste at least one product listing URL.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const batch = await createBatch(name || undefined, urls);
      navigate(`/batches/${batch.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start batch scan.");
      setSubmitting(false);
    }
  }

  return (
    <div>
      <h1>New Batch Scan</h1>
      <p className="page-subtitle">
        Paste a list of product listing URLs. LM-SCAN runs the same automatic retrieval, extraction,
        OCR, and compliance screening as a single inspection across every URL, then ranks the results
        worst-first in a triage queue instead of one inspection at a time.
      </p>

      <div className="card" style={{ maxWidth: 640 }}>
        <form onSubmit={handleSubmit}>
          <div className="form-row">
            <label htmlFor="batch-name">Batch name (optional)</label>
            <input
              id="batch-name"
              type="text"
              placeholder="e.g. Blinkit snacks sweep — Aug 2026"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div className="form-row">
            <label htmlFor="batch-urls">Product listing URLs (one per line)</label>
            <textarea
              id="batch-urls"
              rows={10}
              placeholder={"https://blinkit.com/prn/.../prid/...\nhttps://www.amazon.in/dp/...\nhttps://www.flipkart.com/.../p/..."}
              value={urlText}
              onChange={(e) => setUrlText(e.target.value)}
            />
            <p style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 4 }}>
              {urls.length} unique URL{urls.length === 1 ? "" : "s"} detected
              {urls.length > SOFT_MAX_URLS_HINT && (
                <> — this exceeds the typical per-batch limit ({SOFT_MAX_URLS_HINT}); extras will be rejected with a reason, not silently dropped.</>
              )}
            </p>
          </div>
          <button type="submit" disabled={submitting}>
            {submitting ? "Starting batch scan…" : "Start Batch Scan"}
          </button>
          {error && <p className="error-text">{error}</p>}
        </form>
      </div>
    </div>
  );
}
