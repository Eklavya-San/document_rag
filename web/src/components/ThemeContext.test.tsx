import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { ThemeProvider } from "./ThemeContext";

describe("ThemeProvider", () => {
  beforeEach(() => localStorage.clear());

  it("falls back to dark for a corrupted localStorage value", () => {
    localStorage.setItem("rag_theme", "foo");
    render(<ThemeProvider><span>x</span></ThemeProvider>);
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
  });

  it("respects a valid light value", () => {
    localStorage.setItem("rag_theme", "light");
    render(<ThemeProvider><span>x</span></ThemeProvider>);
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
  });
});
