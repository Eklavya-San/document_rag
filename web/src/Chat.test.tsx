import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
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

describe("Chat", () => {
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
});
