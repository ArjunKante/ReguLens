interface BrandLogoProps {
  /** "sidebar" (desktop nav rail + mobile drawer header), "topbar" (mobile
   * top bar), or "auth" (sign-in card) — controls sizing only, same
   * component everywhere so the mark is never re-implemented per page. */
  variant?: "sidebar" | "topbar" | "auth";
  className?: string;
}

// The logo (public/regulens-logo.png) is a wide, landscape image — these
// are target widths, not a square badge size, so the image always renders
// at its own natural aspect ratio (height:auto in CSS) instead of being
// letterboxed into a square and wasting most of the box on white space.
const WIDTHS: Record<NonNullable<BrandLogoProps["variant"]>, number> = {
  sidebar: 176,
  topbar: 84,
  auth: 200,
};

/** The official ReguLens logo mark, reused everywhere the brand appears
 * (desktop sidebar, mobile top bar, sign-in card) instead of re-declaring
 * the <img> per page. The source asset has an opaque white background, so
 * it's given a white surface behind it — legible on both the navy
 * sidebar and the dark sign-in card without editing the supplied image
 * itself. */
export function BrandLogo({ variant = "sidebar", className }: BrandLogoProps) {
  const width = WIDTHS[variant];
  return (
    <span className={`brand-logo${className ? ` ${className}` : ""}`} style={{ width }}>
      <img src="/regulens-logo.png" alt="ReguLens" />
    </span>
  );
}
