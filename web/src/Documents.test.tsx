import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Documents } from "./Documents";

vi.mock("./api", () => ({
  uploadDocument: vi.fn().mockResolvedValue({ id: 1, filename: "m.pdf", status: "pending", chunk_count: 0, parser_used: null, error: null }),
  listDocuments: vi.fn().mockResolvedValue([
    { id: 1, filename: "m.pdf", status: "done", chunk_count: 3, parser_used: "pdf", error: null },
    { id: 2, filename: "bad.pdf", status: "failed", chunk_count: 0, parser_used: "pdf", error: "OCR not supported" },
  ]),
  deleteDocument: vi.fn().mockResolvedValue(undefined),
}));

import { uploadDocument, deleteDocument } from "./api";

describe("Documents", () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it("lists documents with status", async () => {
    render(<Documents />);
    expect(await screen.findByText("m.pdf")).toBeInTheDocument();
    expect(screen.getByText((c) => c.startsWith("done"))).toBeInTheDocument();
    expect(screen.getByText(/OCR not supported/)).toBeInTheDocument();
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
});
