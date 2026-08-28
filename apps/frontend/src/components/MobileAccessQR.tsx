import { useEffect, useRef, useState } from "react";
import QRCode from "qrcode";

/** "Continue on phone": a button that opens a small modal with a QR code
 * encoding this deployment's own URL. Scanning it just opens the same
 * site on the phone's browser — login and everything else happens there
 * independently, there is no session hand-off (see docs/architecture.md
 * if that ever changes). Deliberately client-side only: the URL is fixed
 * per deployment, so there is no backend endpoint to generate or serve.
 */
export function MobileAccessQR() {
  const [open, setOpen] = useState(false);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [error, setError] = useState<string | null>(null);

  // window.location.origin (not a hardcoded/env-configured URL): whichever
  // domain is actually serving this page right now is the one a scan
  // should open, so this keeps working unchanged across a custom domain,
  // a Vercel preview URL, or plain localhost during development.
  const url = typeof window !== "undefined" ? window.location.origin : "";

  useEffect(() => {
    if (!open || !canvasRef.current) return;
    setError(null);
    QRCode.toCanvas(canvasRef.current, url, { width: 220, margin: 1 }, (err) => {
      if (err) setError("Couldn't generate the QR code.");
    });
  }, [open, url]);

  // Esc closes the modal, same as clicking the backdrop.
  useEffect(() => {
    if (!open) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open]);

  return (
    <>
      <button
        type="button"
        className="secondary"
        onClick={() => setOpen(true)}
        style={{ color: "#fff", borderColor: "rgba(255,255,255,0.4)", width: "100%" }}
      >
        📱 Continue on phone
      </button>
      {open && (
        <div className="qr-modal__backdrop" onClick={() => setOpen(false)}>
          <div className="qr-modal card" onClick={(e) => e.stopPropagation()}>
            <h3 style={{ marginTop: 0 }}>Scan to open on your phone</h3>
            <p style={{ fontSize: 12.5, color: "var(--color-text-muted)", marginTop: 0 }}>
              Opens this same site in your phone's browser. You'll log in there separately —
              nothing from this session is transferred.
            </p>
            <div className="qr-modal__code">
              <canvas ref={canvasRef} />
            </div>
            {error && <p className="error-text">{error}</p>}
            <p style={{ fontSize: 11.5, color: "var(--color-text-muted)", wordBreak: "break-all" }}>{url}</p>
            <button type="button" className="secondary" onClick={() => setOpen(false)}>
              Close
            </button>
          </div>
        </div>
      )}
    </>
  );
}
