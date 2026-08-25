import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { AppShell } from "./AppShell";
import type { RoleName } from "../types";

export function ProtectedRoute({ children, allow }: { children: ReactNode; allow?: RoleName[] }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (allow && !allow.includes(user.role)) return <Navigate to="/dashboard" replace />;
  return <AppShell>{children}</AppShell>;
}
