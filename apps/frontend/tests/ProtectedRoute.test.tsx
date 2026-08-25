import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { ProtectedRoute } from "../src/components/ProtectedRoute";
import { AuthProvider } from "../src/context/AuthContext";

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<div>Login page</div>} />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <div>Secret dashboard content</div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </AuthProvider>
    </MemoryRouter>
  );
}

describe("ProtectedRoute", () => {
  it("redirects an unauthenticated user to /login", () => {
    localStorage.clear();
    renderAt("/dashboard");
    expect(screen.getByText("Login page")).toBeInTheDocument();
    expect(screen.queryByText("Secret dashboard content")).not.toBeInTheDocument();
  });

  it("renders protected content for an authenticated user, with no login flicker", () => {
    // AuthProvider restores the session synchronously (lazy useState
    // initializer, not useEffect) specifically so this never flashes the
    // login page first — assert synchronously to guard that regression.
    localStorage.setItem(
      "lmscan_user",
      JSON.stringify({ userId: "u1", fullName: "Test User", role: "INSPECTOR" })
    );
    renderAt("/dashboard");
    expect(screen.getByText("Secret dashboard content")).toBeInTheDocument();
    expect(screen.queryByText("Login page")).not.toBeInTheDocument();
  });
});
