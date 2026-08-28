import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import LineSidebar from "./LineSidebar";

interface NavItem {
  label: string;
  path: string;
}

// Longest-matching-path wins, so a pathname that's a prefix match for more
// than one entry (e.g. "/inspections/new" under both "/inspections" and
// "/inspections/new" itself) resolves to exactly one active tab instead of
// highlighting several at once.
function computeActiveIndex(pathname: string, navItems: NavItem[]): number | null {
  let bestIndex: number | null = null;
  let bestLength = -1;
  navItems.forEach((item, index) => {
    const matches = pathname === item.path || pathname.startsWith(`${item.path}/`);
    if (matches && item.path.length > bestLength) {
      bestIndex = index;
      bestLength = item.path.length;
    }
  });
  return bestIndex;
}

export function AppShell({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  // LineSidebar's proximity/hover effect is a desktop mouse thing — on a
  // narrow (phone-width) viewport the sidebar itself is hidden by CSS in
  // favor of this plain drawer, which is just tappable buttons, no motion
  // gimmicks needed. Kept as separate markup from LineSidebar rather than
  // trying to make one component serve both, since LineSidebar's animation
  // math assumes a mouse.
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  // A route change (including via the drawer's own links) always closes
  // the drawer — otherwise it stays open over the new page until the user
  // notices and taps the backdrop themselves.
  useEffect(() => {
    setMobileNavOpen(false);
  }, [location.pathname]);

  const navItems = useMemo<NavItem[]>(() => {
    const items: NavItem[] = [
      { label: "Dashboard", path: "/dashboard" },
      { label: "Inspection History", path: "/inspections" },
    ];
    if (user?.role === "ADMIN" || user?.role === "INSPECTOR") {
      items.push({ label: "New Inspection", path: "/inspections/new" });
    }
    items.push({ label: "Batch Scan", path: "/batches" });
    items.push({ label: "Rule Management", path: "/rules" });
    if (user?.role === "ADMIN") {
      items.push({ label: "User Management", path: "/users" });
    }
    return items;
  }, [user?.role]);

  const activeIndex = useMemo(
    () => computeActiveIndex(location.pathname, navItems),
    [location.pathname, navItems]
  );

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar__brand">
          LM-SCAN
          <small>Legal Metrology Compliance Inspection</small>
        </div>
        <div className="sidebar__nav">
          <LineSidebar
            // Remounts only when the resolved active tab actually changes
            // (route navigation via clicks, browser back/forward, or a
            // direct/refreshed URL) — keeps LineSidebar's own internal
            // active-index state, which it only reads from defaultActive
            // on mount, in sync with the real route without patching the
            // component's logic.
            key={activeIndex ?? "none"}
            items={navItems.map((item) => item.label)}
            accentColor="#5b9dff"
            textColor="#c8d2e0"
            markerColor="rgba(255,255,255,0.28)"
            showIndex={false}
            showMarker
            proximityRadius={70}
            maxShift={10}
            falloff="smooth"
            markerLength={18}
            markerGap={8}
            tickScale={0.5}
            scaleTick
            itemGap={10}
            fontSize={0.85}
            smoothing={100}
            defaultActive={activeIndex}
            onItemClick={(index) => navigate(navItems[index].path)}
          />
        </div>
        <div className="sidebar__user">
          <div>{user?.fullName}</div>
          <div style={{ opacity: 0.7 }}>{user?.role}</div>
          <button className="secondary" onClick={logout} style={{ color: "#fff", borderColor: "rgba(255,255,255,0.4)" }}>
            Log out
          </button>
        </div>
      </aside>

      {/* Phone-width nav: a top bar + slide-in drawer, CSS-hidden on wider
          screens where the real sidebar above is visible instead. */}
      <header className="mobile-topbar">
        <button
          type="button"
          className="mobile-topbar__toggle"
          aria-label={mobileNavOpen ? "Close navigation menu" : "Open navigation menu"}
          aria-expanded={mobileNavOpen}
          onClick={() => setMobileNavOpen((open) => !open)}
        >
          <span />
          <span />
          <span />
        </button>
        <span className="mobile-topbar__brand">LM-SCAN</span>
      </header>
      {mobileNavOpen && <div className="mobile-drawer__backdrop" onClick={() => setMobileNavOpen(false)} />}
      <nav className={`mobile-drawer${mobileNavOpen ? " mobile-drawer--open" : ""}`}>
        <div className="sidebar__brand">
          LM-SCAN
          <small>Legal Metrology Compliance Inspection</small>
        </div>
        <div className="mobile-drawer__nav">
          {navItems.map((item, index) => (
            <button
              key={item.path}
              type="button"
              className={`mobile-drawer__link${index === activeIndex ? " mobile-drawer__link--active" : ""}`}
              onClick={() => navigate(item.path)}
            >
              {item.label}
            </button>
          ))}
        </div>
        <div className="sidebar__user">
          <div>{user?.fullName}</div>
          <div style={{ opacity: 0.7 }}>{user?.role}</div>
          <button className="secondary" onClick={logout} style={{ color: "#fff", borderColor: "rgba(255,255,255,0.4)" }}>
            Log out
          </button>
        </div>
      </nav>

      <main className="main">{children}</main>
    </div>
  );
}
