import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { App } from "./App";

vi.mock("./sse", () => ({
  streamChat: vi.fn(async (_q: string, _id: number | null, onEvent: (e: any) => void) => {
    onEvent({ type: "session", session_id: 7 });
    onEvent({ type: "token", content: "Hello" });
    onEvent({ type: "done" });
  }),
}));

function setup() {
  const user = userEvent.setup();
  return { user, ...render(<App />) };
}

describe("App", () => {
  it("renders the Chat tab by default", () => {
    render(<App />);
    expect(screen.getByPlaceholderText("Ask about the manuals…")).toBeInTheDocument();
  });

  it("switches to the Documents tab", async () => {
    const { user } = setup();
    await user.click(screen.getByText(/Documents/));
    expect(screen.getByLabelText("Upload manual")).toBeInTheDocument();
  });

  it("New Conversation resets the chat", async () => {
    const { user } = setup();
    // send a message to populate chat
    await user.type(screen.getByPlaceholderText("Ask about the manuals…"), "how to calibrate?");
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText("Hello")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /new conversation/i }));
    expect(screen.queryByText("Hello")).not.toBeInTheDocument();
    expect(screen.getByText("Welcome to RAG Studio")).toBeInTheDocument();
  });
});
