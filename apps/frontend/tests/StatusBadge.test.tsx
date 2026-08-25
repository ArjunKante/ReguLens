import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatusBadge } from "../src/components/StatusBadge";

describe("StatusBadge", () => {
  it("renders a readable label for a known status", () => {
    render(<StatusBadge status="POTENTIAL_NON_COMPLIANCE" />);
    expect(screen.getByText("POTENTIAL NON COMPLIANCE")).toBeInTheDocument();
  });

  it("renders a placeholder for a missing status", () => {
    render(<StatusBadge status={null} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("applies the correct badge class per status", () => {
    const { container } = render(<StatusBadge status="PASS" />);
    expect(container.querySelector(".badge-PASS")).not.toBeNull();
  });
});
