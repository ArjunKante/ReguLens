import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../src/context/AuthContext";
import { LoginPage } from "../src/pages/LoginPage";

vi.mock("../src/api/endpoints", () => ({
  login: vi.fn(),
}));

import { login } from "../src/api/endpoints";

describe("LoginPage", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.mocked(login).mockReset();
  });

  it("renders email and password fields", () => {
    render(
      <MemoryRouter>
        <AuthProvider>
          <LoginPage />
        </AuthProvider>
      </MemoryRouter>
    );
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
  });

  it("calls the login endpoint with entered credentials on submit", async () => {
    vi.mocked(login).mockResolvedValue({
      access_token: "fake-token",
      token_type: "bearer",
      role: "INSPECTOR",
      full_name: "Test Inspector",
      user_id: "abc-123",
    });

    render(
      <MemoryRouter>
        <AuthProvider>
          <LoginPage />
        </AuthProvider>
      </MemoryRouter>
    );

    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "inspector@lmscan.example" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "correct-password" } });
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => {
      expect(login).toHaveBeenCalledWith("inspector@lmscan.example", "correct-password");
    });
  });

  it("shows an error message when login fails", async () => {
    vi.mocked(login).mockRejectedValue(new Error("Incorrect email or password."));

    render(
      <MemoryRouter>
        <AuthProvider>
          <LoginPage />
        </AuthProvider>
      </MemoryRouter>
    );

    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "bad@lmscan.example" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "wrong" } });
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByText("Incorrect email or password.")).toBeInTheDocument();
    });
  });
});
