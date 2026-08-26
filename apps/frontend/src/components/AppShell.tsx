import { useMemo, type ReactNode } from "react";
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

  const navItems = useMemo<NavItem[]>(() => {
    const items: NavItem[] = [
      { label: "Dashboard", path: "/dashboard" },
      { label: "Inspection History", path: "/inspections" },
    ];
    if (user?.role === "ADMIN" || user?.role === "INSPECTOR") {
      items.push({ label: "New Inspection", path: "/inspections/new" });
    }
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
      <main className="main">{children}</main>
    </div>
  );
}
