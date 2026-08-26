import type { ButtonHTMLAttributes, ReactNode } from "react";
import "./FloatingDotsButton.css";

interface FloatingDotsButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode;
}

// Pre-seeded positions/timings (not Math.random()) so the "stream" of dots
// looks organic but is deterministic across renders — a saturated blue CTA
// with a glass highlight and a continuous stream of floating light points,
// hand-built in plain CSS/React to match this app's existing stack rather
// than pulling in the closed-source reference package (its source is
// explicitly not distributed — "Exact source is protected" per the
// ThreeUI page — so this recreates the visual/interaction idea natively
// instead of embedding it).
const DOTS = [
  { left: "12%", delay: "0s", duration: "3.2s" },
  { left: "30%", delay: "0.7s", duration: "2.8s" },
  { left: "50%", delay: "1.4s", duration: "3.6s" },
  { left: "68%", delay: "0.3s", duration: "3s" },
  { left: "84%", delay: "2s", duration: "2.6s" },
  { left: "45%", delay: "2.5s", duration: "3.4s" },
];

export function FloatingDotsButton({ children, className = "", ...rest }: FloatingDotsButtonProps) {
  return (
    <button className={`floating-dots-btn ${className}`} {...rest}>
      <span className="floating-dots-btn__dots" aria-hidden="true">
        {DOTS.map((dot, i) => (
          <span
            key={i}
            className="floating-dots-btn__dot"
            style={{ left: dot.left, animationDelay: dot.delay, animationDuration: dot.duration }}
          />
        ))}
      </span>
      <span className="floating-dots-btn__content">
        {children}
        <span className="floating-dots-btn__arrow" aria-hidden="true">
          →
        </span>
      </span>
    </button>
  );
}
