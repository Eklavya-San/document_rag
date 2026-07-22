import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { CitationDrawer, CitationData } from "./CitationDrawer";

describe("CitationDrawer", () => {
  it("renders null when citation is null", () => {
    const { container } = render(<CitationDrawer citation={null} onClose={() => {}} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders filename, percentage match, chunk ID, and text when citation is provided", () => {
    const citation: CitationData = {
      filename: "user_manual.pdf",
      chunkId: "chunk-42",
      text: "This is sample text from manual chunk 42.",
      score: 0.877,
    };

    render(<CitationDrawer citation={citation} onClose={() => {}} />);

    expect(screen.getByText("Source Citation")).toBeInTheDocument();
    expect(screen.getByText("user_manual.pdf")).toBeInTheDocument();
    expect(screen.getByText("87.7% Match")).toBeInTheDocument();
    expect(screen.getByText(/chunk-42/)).toBeInTheDocument();
    expect(screen.getByText("This is sample text from manual chunk 42.")).toBeInTheDocument();
  });

  it("calls onClose when clicking the close button", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    const citation: CitationData = {
      filename: "guide.pdf",
      chunkId: "chunk-1",
      text: "Sample text.",
      score: 0.95,
    };

    render(<CitationDrawer citation={citation} onClose={onClose} />);

    const closeButton = screen.getByRole("button", { name: /close drawer/i });
    await user.click(closeButton);

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("closes on Escape", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    const citation: CitationData = { filename: "g.pdf", chunkId: "c1", text: "t", score: 0.9 };
    render(<CitationDrawer citation={citation} onClose={onClose} />);
    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("is a labelled modal dialog with a backdrop", () => {
    const citation: CitationData = { filename: "g.pdf", chunkId: "c1", text: "t", score: 0.9 };
    const { container } = render(<CitationDrawer citation={citation} onClose={() => {}} />);
    expect(screen.getByRole("dialog", { name: /source citation/i })).toBeInTheDocument();
    expect(container.querySelector(".drawer-backdrop")).toBeInTheDocument();
  });
});
