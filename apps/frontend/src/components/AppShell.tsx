import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export function AppShell({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar__brand">
          LM-SCAN
          <small>Legal Metrology Compliance Inspection</small>
        </div>
        <nav>
          <NavLink to="/dashboard" className={({ isActive }) => (isActive ? "active" : "")}>
            Dashboard
          </NavLink>
          <NavLink to="/inspections" className={({ isActive }) => (isActive ? "active" : "")}>
            Inspection History
          </NavLink>
          {(user?.role === "ADMIN" || user?.role === "INSPECTOR") && (
            <NavLink to="/inspections/new" className={({ isActive }) => (isActive ? "active" : "")}>
              New Inspection
            </NavLink>
          )}
          <NavLink to="/rules" className={({ isActive }) => (isActive ? "active" : "")}>
            Rule Management
          </NavLink>
          {user?.role === "ADMIN" && (
            <NavLink to="/users" className={({ isActive }) => (isActive ? "active" : "")}>
              User Management
            </NavLink>
          )}
        </nav>
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
