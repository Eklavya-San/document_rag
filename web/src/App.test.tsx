import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { App } from "./App";

describe("App", () => {
  it("renders the Chat tab by default", () => {
    render(<App />);
    expect(screen.getByTestId("chat-placeholder")).toBeInTheDocument();
  });

  it("switches to the Documents tab", async () => {
    const { user } = setup();
    await user.click(screen.getByText("Documents"));
    expect(screen.getByTestId("documents-placeholder")).toBeInTheDocument();
  });
});

import userEvent from "@testing-library/user-event";
function setup() {
  const user = userEvent.setup();
  return { user, ...render(<App />) };
}
