import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import App from "./App";

vi.stubGlobal(
  "fetch",
  vi.fn(async () => ({
    ok: false,
    status: 401,
    statusText: "Unauthorized",
    json: async () => ({ detail: "Not signed in." })
  }))
);

describe("App", () => {
  it("renders the connector shell", async () => {
    render(<App />);
    expect(await screen.findByText("Outlook Connector")).toBeInTheDocument();
    expect(await screen.findByText("Connect Outlook")).toBeInTheDocument();
  });
});
