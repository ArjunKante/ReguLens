import { render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import GradientWaves from "../src/components/GradientWaves";

// jsdom (this test environment) implements HTMLCanvasElement.getContext as an
// unimplemented stub: calling it logs "Not implemented: HTMLCanvasElement.
// prototype.getContext" and returns null, and jsdom does not define the
// WebGLRenderingContext/WebGL2RenderingContext globals real browsers provide.
// GradientWaves must detect that up front and skip WebGL initialization
// entirely -- never calling getContext at all -- rather than attempting
// context creation and relying on the fallback catch block to clean up
// after it, which is what produced the repeated jsdom console warnings.
describe("GradientWaves", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("never calls HTMLCanvasElement.getContext in a WebGL-less environment", () => {
    const getContextSpy = vi.spyOn(HTMLCanvasElement.prototype, "getContext");

    const { unmount } = render(<GradientWaves />);

    expect(getContextSpy).not.toHaveBeenCalled();
    unmount();
  });

  it("renders the CSS fallback instead of a canvas when WebGL is unavailable", () => {
    const { container, unmount } = render(<GradientWaves />);

    expect(container.querySelector(".gradient-waves-container--fallback")).not.toBeNull();
    expect(container.querySelector("canvas")).toBeNull();
    unmount();
  });

  it("does not throw on mount or unmount", () => {
    expect(() => {
      const { unmount } = render(<GradientWaves />);
      unmount();
    }).not.toThrow();
  });
});
