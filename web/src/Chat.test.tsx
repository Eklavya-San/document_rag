import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Chat } from "./Chat";

vi.mock("./sse", () => ({
  streamChat: vi.fn(async (_q: string, _id: number | null, onEvent: (e: any) => void) => {
    onEvent({ type: "session", session_id: 7 });
    onEvent({ type: "token", content: "Hel" });
    onEvent({ type: "token", content: "lo" });
    onEvent({ type: "sources", sources: [{ filename: "m.pdf", page: 3, text: "calibrate the sensor", score: 0.9 }] });
    onEvent({ type: "done" });
  }),
}));

import { streamChat } from "./sse";

describe("Chat", () => {
  it("displays hero welcome state with prompt suggestion chips when empty", () => {
    render(<Chat />);
    expect(screen.getByText("Welcome to RAG Studio")).toBeInTheDocument();
    expect(screen.getByText("What are the key findings in the uploaded documents?")).toBeInTheDocument();
    expect(screen.getByText("Summarize technical architecture and chunking logic")).toBeInTheDocument();
    expect(screen.getByText("Search vector database for configuration settings")).toBeInTheDocument();
  });

  it("submits query when prompt suggestion chip is clicked", async () => {
    const user = userEvent.setup();
    render(<Chat />);
    const chip = screen.getByText("What are the key findings in the uploaded documents?");
    await user.click(chip);

    expect(await screen.findByText("Hello")).toBeInTheDocument();
  });

  it("streams an answer and shows source chips", async () => {
    const user = userEvent.setup();
    render(<Chat />);
    await user.type(screen.getByPlaceholderText("Ask about the manuals…"), "how to calibrate?");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText("Hello")).toBeInTheDocument();
    expect(await screen.findByText(/m\.pdf.*p\.3/)).toBeInTheDocument();
  });

  it("reveals the source snippet when the chip is clicked", async () => {
    const user = userEvent.setup();
    render(<Chat />);
    await user.type(screen.getByPlaceholderText("Ask about the manuals…"), "how to calibrate?");
    await user.click(screen.getByRole("button", { name: "Send" }));
    const chip = await screen.findByText(/m\.pdf.*p\.3/);
    await user.click(chip);
    expect(await screen.findByText("calibrate the sensor")).toBeInTheDocument();
  });

  it("releases busy even if the stream ends without a done event", async () => {
    vi.mocked(streamChat).mockImplementationOnce(async (_q: string, _id: number | null, onEvent: (e: any) => void) => {
      onEvent({ type: "token", content: "Hi" });
    });
    const user = userEvent.setup();
    render(<Chat />);
    await user.type(screen.getByPlaceholderText("Ask about the manuals…"), "hi");
    await user.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Send" })).toBeEnabled());
  });
});
