import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import userEvent from "@testing-library/user-event";
import { App } from "./App";

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
    await user.click(screen.getByText("Documents"));
    expect(screen.getByLabelText("Upload manual")).toBeInTheDocument();
  });
});
