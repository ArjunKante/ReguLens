import { useEffect, useState } from "react";
import { fetchImageObjectUrl } from "../api/endpoints";
import type { ProductImage } from "../types";

interface EvidenceImageProps {
  inspectionId: string;
  image: ProductImage;
  /** An OCRResult id to draw highlighted (orange, thicker) instead of the
   * default faint outline — set by clicking a finding's evidence entry, so
   * an officer can see exactly which region of which photo a declaration
   * came from (Demo Hardening: "make rule -> evidence -> finding
   * traceability obvious"). */
  highlightOcrResultId?: string | null;
}

/** Renders one evidence image with its OCR bounding boxes overlaid.
 *
 * The image bytes require auth (a plain <img src> can't carry the Bearer
 * token — same reason report downloads go through an object URL), so this
 * fetches once on mount and revokes the object URL on unmount.
 *
 * Bounding boxes are stored in the *original* image's pixel coordinates
 * (Section 8's OCR bounding-box capture). Rather than track the displayed
 * size with a resize observer, the overlay is an <svg> whose viewBox is the
 * original width/height and which itself is stretched to 100% of the
 * rendered <img> — SVG's viewBox scaling keeps every box aligned at any
 * display size for free, with no JS resize handling needed.
 */
export function EvidenceImage({ inspectionId, image, highlightOcrResultId }: EvidenceImageProps) {
  const [objectUrl, setObjectUrl] = useState<string | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let createdUrl: string | null = null;
    fetchImageObjectUrl(inspectionId, image.id)
      .then((url) => {
        if (cancelled) {
          URL.revokeObjectURL(url);
          return;
        }
        createdUrl = url;
        setObjectUrl(url);
      })
      .catch(() => !cancelled && setError(true));
    return () => {
      cancelled = true;
      if (createdUrl) URL.revokeObjectURL(createdUrl);
    };
  }, [inspectionId, image.id]);

  const boxes = image.ocr_results.filter((r) => r.bounding_box);

  return (
    <div style={{ position: "relative", width: "100%", lineHeight: 0, background: "var(--color-surface-alt, #f3f3f3)" }}>
      {objectUrl ? (
        <img src={objectUrl} alt={`Evidence — ${image.source_type}`} style={{ width: "100%", display: "block" }} />
      ) : (
        <div style={{ padding: 24, textAlign: "center", fontSize: 12.5, color: "var(--color-text-muted)" }}>
          {error ? "Could not load image." : "Loading image…"}
        </div>
      )}
      {objectUrl && image.width && image.height && boxes.length > 0 && (
        <svg
          viewBox={`0 0 ${image.width} ${image.height}`}
          preserveAspectRatio="none"
          style={{ position: "absolute", top: 0, left: 0, width: "100%", height: "100%", pointerEvents: "none" }}
        >
          {boxes.map((r) => {
            const box = r.bounding_box!;
            const isHighlighted = highlightOcrResultId === r.id;
            return (
              <rect
                key={r.id}
                x={box.x}
                y={box.y}
                width={box.width}
                height={box.height}
                fill={isHighlighted ? "rgba(230, 167, 0, 0.28)" : "transparent"}
                stroke={isHighlighted ? "#e6a700" : "rgba(59, 130, 246, 0.55)"}
                strokeWidth={(isHighlighted ? 3 : 1.5) * (image.width! / 400)}
              >
                <title>{r.text}</title>
              </rect>
            );
          })}
        </svg>
      )}
    </div>
  );
}
