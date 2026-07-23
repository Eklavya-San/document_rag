import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { Header } from "./Header";
import { ThemeProvider } from "./ThemeContext";

vi.mock("../api", () => ({ fetchHealth: vi.fn() }));
import { fetchHealth } from "../api";

function renderWithTheme(ui: React.ReactElement) {
  return render(<ThemeProvider>{ui}</ThemeProvider>);
}

describe("Header", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows Ollama as unreachable when /health reports it down", async () => {
    (fetchHealth as any).mockResolvedValue({ status: "ok", config: {}, dependencies: { ollama: "unreachable", qdrant: "ok" } });
    renderWithTheme(<Header activeTab="chat" />);
    await waitFor(() => expect(screen.getByText(/Ollama LLM/)).toHaveClass("status-pill"));
    expect(screen.getByText(/Ollama LLM/).querySelector(".dot")).toHaveClass("dot-error");
    expect(screen.getByText(/Qdrant DB/).querySelector(".dot")).toHaveClass("dot-success");
  });

  it("shows both green when both dependencies are ok", async () => {
    (fetchHealth as any).mockResolvedValue({ status: "ok", config: {}, dependencies: { ollama: "ok", qdrant: "ok" } });
    renderWithTheme(<Header activeTab="chat" />);
    await waitFor(() => expect(screen.getByText(/Ollama LLM/).querySelector(".dot")).toHaveClass("dot-success"));
  });
});
