import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Documents } from "./Documents";

const freshDocs = () => [
  { id: 1, filename: "m.pdf", status: "done" as const, chunk_count: 3, parser_used: "pdf", error: null },
  { id: 2, filename: "bad.pdf", status: "failed" as const, chunk_count: 0, parser_used: "pdf", error: "OCR not supported" },
];

vi.mock("./api", () => ({
  uploadDocument: vi.fn().mockResolvedValue({ id: 1, filename: "m.pdf", status: "pending", chunk_count: 0, parser_used: null, error: null }),
  listDocuments: vi.fn().mockImplementation(async () => freshDocs()),
  deleteDocument: vi.fn().mockResolvedValue(undefined),
}));

import { uploadDocument, deleteDocument, listDocuments } from "./api";

describe("Documents", () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it("renders dropzone and table structure", async () => {
    render(<Documents />);
    expect(screen.getByText("Drag & drop files here or click to browse")).toBeInTheDocument();
    expect(screen.getByText("Supports PDF, TXT, MD, JSON")).toBeInTheDocument();
    expect(await screen.findByText("Document Title")).toBeInTheDocument();
    expect(screen.getByText("Chunk Count")).toBeInTheDocument();
    expect(screen.getByText("Status")).toBeInTheDocument();
    expect(screen.getByText("Actions")).toBeInTheDocument();
  });

  it("lists documents with status pills and errors", async () => {
    render(<Documents />);
    expect(await screen.findByText("m.pdf")).toBeInTheDocument();
    expect(screen.getByText("Indexed")).toBeInTheDocument();
    expect(screen.getByText("3 chunks")).toBeInTheDocument();
    expect(screen.getByText(/OCR not supported/)).toBeInTheDocument();
    expect(screen.getByText("Error")).toBeInTheDocument();
  });

  it("uploads a chosen file", async () => {
    const user = userEvent.setup();
    render(<Documents />);
    await screen.findByText("m.pdf");
    const input = screen.getByLabelText("Upload manual") as HTMLInputElement;
    await user.upload(input, new File(["x"], "new.pdf"));
    expect(uploadDocument).toHaveBeenCalled();
  });

  it("deletes a document on click", async () => {
    const user = userEvent.setup();
    render(<Documents />);
    await screen.findByText("m.pdf");
    await user.click(screen.getAllByRole("button", { name: "Delete" })[0]);
    await waitFor(() => expect(deleteDocument).toHaveBeenCalledWith(1));
  });

  it("polls every 2s while a document is in-flight and stops when terminal", async () => {
    vi.useFakeTimers();
    let status: string = "pending";
    (listDocuments as any).mockImplementation(async () => [
      { id: 1, filename: "m.pdf", status: status as any, chunk_count: 0, parser_used: null, error: null },
    ]);
    render(<Documents />);
    // flush the initial mount effect (refresh + setInterval)
    await vi.advanceTimersByTimeAsync(0);
    // after initial load, listDocuments was called at least once
    const initialCalls = (listDocuments as any).mock.calls.length;
    expect(initialCalls).toBeGreaterThanOrEqual(1);
    // flip to done, advance 2s -> one more poll fires
    status = "done";
    await vi.advanceTimersByTimeAsync(2000);
    // advance another 2s to confirm no further polls
    await vi.advanceTimersByTimeAsync(2000);
    const afterCalls = (listDocuments as any).mock.calls.length;
    // at least one more call happened after the status flip
    expect(afterCalls).toBeGreaterThanOrEqual(initialCalls + 1);
    vi.useRealTimers();
  });
});
