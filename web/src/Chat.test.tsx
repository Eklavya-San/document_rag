import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Chat } from "./Chat";

vi.mock("./sse", () => ({
  streamChat: vi.fn(async (_q: string, _id: number | null, onEvent: (e: any) => void, _onErr: any, signal?: AbortSignal) => {
    onEvent({ type: "session", session_id: 7 });
    onEvent({ type: "token", content: "Hel" });
    onEvent({ type: "token", content: "lo" });
    onEvent({ type: "sources", sources: [{ filename: "m.pdf", page: 3, text: "calibrate the sensor", score: 0.9, chunk_id: "c1" }] });
    onEvent({ type: "done" });
    // Yield so the Chat component has time to set abortRef.current before we resolve
    await new Promise((resolve) => setTimeout(resolve, 10));
    return signal;
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

  it("passes an AbortSignal to streamChat and aborts the previous stream on a new send", async () => {
    const user = userEvent.setup();
    render(<Chat />);
    await user.type(screen.getByPlaceholderText("Ask about the manuals…"), "q1");
    await user.click(screen.getByRole("button", { name: "Send" }));
    const firstSignal = (vi.mocked(streamChat).mock.calls[0][4] as AbortSignal);
    expect(firstSignal).toBeInstanceOf(AbortSignal);
    await waitFor(() => expect(screen.getByRole("button", { name: "Send" })).toBeEnabled());
    await user.type(screen.getByPlaceholderText("Ask about the manuals…"), "q2");
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(firstSignal.aborted).toBe(true);
  });

  it("marks the messages region as a live region", () => {
    render(<Chat />);
    const live = document.querySelector("[aria-live='polite']");
    expect(live).not.toBeNull();
  });

  it("renders markdown content as HTML", async () => {
    vi.mocked(streamChat).mockImplementationOnce(async (_q, _id, onEvent: (e: any) => void) => {
      onEvent({ type: "session", session_id: 9 });
      onEvent({ type: "token", content: "**bold**" });
      onEvent({ type: "done" });
    });
    const user = userEvent.setup();
    render(<Chat />);
    await user.type(screen.getByPlaceholderText("Ask about the manuals…"), "q");
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText("bold")).toBeInTheDocument();
  });
});
