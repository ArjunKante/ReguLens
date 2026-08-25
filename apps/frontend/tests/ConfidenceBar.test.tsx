import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ConfidenceBar } from "../src/components/ConfidenceBar";

describe("ConfidenceBar", () => {
  it("renders the confidence as a rounded percentage", () => {
    render(<ConfidenceBar confidence={0.873} />);
    expect(screen.getByText(/87%/)).toBeInTheDocument();
  });

  it("renders 0% for zero confidence", () => {
    render(<ConfidenceBar confidence={0} />);
    expect(screen.getByText(/0%/)).toBeInTheDocument();
  });
});
