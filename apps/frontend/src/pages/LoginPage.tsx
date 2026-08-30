import { useRef, useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import { BrandLogo } from "../components/BrandLogo";
import { FloatingDotsButton } from "../components/FloatingDotsButton";
import GradientWaves from "../components/GradientWaves";
import GradualBlur from "../components/GradualBlur";
import { useAuth } from "../context/AuthContext";

// Smooth by default (the "goes down slowly" scroll into each section), but
// respects prefers-reduced-motion — and, as a side effect of that same
// check, is also immune to the one real failure mode found testing this
// live: a backgrounded/unfocused browser tab silently no-ops a smooth
// scrollIntoView for several seconds (Chrome throttles the compositor
// animation), which reduced-motion mode sidesteps entirely by not
// animating in the first place.
function scrollToSection(el: HTMLElement | null) {
  if (!el) return;
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  el.scrollIntoView({ behavior: reduceMotion ? "instant" : "smooth" });
}

export function LoginPage() {
  const { user, login, loading, error } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const aboutRef = useRef<HTMLDivElement | null>(null);
  const formRef = useRef<HTMLDivElement | null>(null);

  if (user) return <Navigate to="/dashboard" replace />;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    try {
      await login(email, password);
    } catch {
      // error is surfaced via context
    }
  }

  return (
    <div className="landing">
      <section className="hero">
        <div className="hero__waves">
          {/* Tuned to ReguLens's own navy/blue palette rather than the
              reference's purple/pink defaults — this is a compliance
              inspection tool, not a consumer product landing page. */}
          <GradientWaves
            horizonColor="#0b1830"
            waveColor="#1a3a6b"
            crestColor="#8fb8ff"
            speed={0.35}
            amplitude={2.2}
            waveScale={0.55}
            waveRatio={0.9}
            swell={30}
            turbulence={16}
            tilt={1.11}
            zoom={1.0}
            height={5.5}
            fogDepth={15}
            detail="medium"
            brightness={1.0}
            opacity={1.0}
            mouseInteraction
            parallaxStrength={0.4}
            grain
            grainIntensity={0.04}
          />
        </div>
        <div className="hero__content">
          <h1>ReguLens</h1>
          <p className="hero__tagline">AI-Assisted Online Legal Metrology Compliance Inspection</p>
          <p className="hero__subtext">
            Preliminary, AI-assisted compliance screening for packaged-commodity listings — built to help an
            authorized Legal Metrology officer inspect faster, not to replace their judgment.
          </p>
          <div className="hero__actions">
            <FloatingDotsButton type="button" onClick={() => scrollToSection(formRef.current)}>
              Get Started
            </FloatingDotsButton>
            <button type="button" className="hero__secondary-btn" onClick={() => scrollToSection(aboutRef.current)}>
              Learn more
            </button>
          </div>
        </div>
      </section>

      <section className="about" ref={aboutRef}>
        {/* Softens the seam coming down from the hero's animated background
            into this section's plain background — a blurred fade instead
            of a hard cut, without changing either section's actual color. */}
        <GradualBlur target="parent" position="top" height="5rem" strength={2} divCount={5} curve="bezier" exponential opacity={1} />
        <div className="about__inner">
          <div className="about__card">
            <h2>What ReguLens does</h2>
            <p>
              ReguLens retrieves a public product listing from a marketplace or quick-commerce platform, extracts
              declarations from the page text, structured metadata, and product images via OCR, and evaluates them
              against a source-traceable rule database derived from the Legal Metrology (Packaged Commodities)
              Rules, 2011.
            </p>
            <p>
              Every automated finding is explicitly labeled — <strong>PASS</strong>,{" "}
              <strong>POTENTIAL_NON_COMPLIANCE</strong>, <strong>NEEDS_MANUAL_REVIEW</strong>,{" "}
              <strong>NOT_APPLICABLE</strong>, or <strong>UNABLE_TO_VERIFY</strong> — with evidence and a
              confidence score, and every report carries the disclaimer{" "}
              <em>"Automated Preliminary Compliance Assessment — Subject to Verification by an Authorized Officer."</em>{" "}
              ReguLens is not a legally binding decision maker.
            </p>
          </div>

          <div className="about__card">
            <h2>How ReguLens works</h2>
            <ol className="about__steps">
              <li>
                <strong>Paste a listing URL.</strong> An inspector starts an inspection from a public
                marketplace/quick-commerce product page, or uploads photos directly when a live fetch isn't
                possible.
              </li>
              <li>
                <strong>Automatic retrieval and OCR.</strong> ReguLens fetches the page, downloads the product
                images, and reads the on-package declarations via OCR.
              </li>
              <li>
                <strong>Rule-based compliance check.</strong> Every declaration is checked against a
                source-traceable rule database derived from the Legal Metrology (Packaged Commodities) Rules,
                2011 — a deterministic rule engine, never an opaque model call.
              </li>
              <li>
                <strong>Officer review and reporting.</strong> Findings, evidence, and confidence scores are
                handed to an authorized officer to confirm, override, or request more evidence before a final
                report is generated.
              </li>
            </ol>
          </div>
        </div>
      </section>

      <section className="login-shell" ref={formRef}>
        {/* Same treatment for the about -> sign-in seam, sitting above the
            sign-in card. */}
        <GradualBlur target="parent" position="top" height="6rem" strength={2} divCount={5} curve="bezier" exponential opacity={1} />
        <div className="login-card">
          <div className="login-card__brand">
            <BrandLogo variant="auth" />
          </div>
          <h1>Sign in</h1>
          <p className="tagline">Authorized officer access only</p>
          <form onSubmit={handleSubmit}>
            <div className="form-row">
              <label htmlFor="email">Email</label>
              <input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="username"
              />
            </div>
            <div className="form-row">
              <label htmlFor="password">Password</label>
              <input
                id="password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
              />
            </div>
            <FloatingDotsButton type="submit" disabled={loading} style={{ width: "100%" }}>
              {loading ? "Signing in…" : "Sign in"}
            </FloatingDotsButton>
            {error && <p className="error-text">{error}</p>}
          </form>
        </div>
      </section>
    </div>
  );
}
