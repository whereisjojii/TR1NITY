import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { RunbookPanel } from "../src/components/RunbookPanel";

const stubFetch = (response: unknown, ok = true): typeof fetch =>
  vi.fn().mockResolvedValue({
    ok,
    status: ok ? 200 : 404,
    statusText: ok ? "OK" : "Not Found",
    json: () => Promise.resolve(response),
    text: () => Promise.resolve(JSON.stringify(response)),
  } as unknown as Response);

let originalFetch: typeof fetch;

beforeEach(() => {
  originalFetch = globalThis.fetch;
});

afterEach(() => {
  globalThis.fetch = originalFetch;
});

function withClient(child: JSX.Element): JSX.Element {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{child}</QueryClientProvider>;
}

describe("RunbookPanel", () => {
  it("renders the runbook title and markdown body", async () => {
    globalThis.fetch = stubFetch({
      technique_id: "T1110",
      tactic_id: "TA0006",
      title: "Brute Force",
      severity: "high",
      url: "/api/runbooks/T1110",
      body: "## Triage\n\n- Inspect the firewall logs.",
      references: ["https://attack.mitre.org/techniques/T1110/"],
    });
    render(withClient(<RunbookPanel techniqueId="T1110" />));
    await waitFor(() => {
      expect(screen.getByText(/Brute Force/i)).toBeInTheDocument();
    });
    expect(screen.getByText("Triage")).toBeInTheDocument();
    expect(screen.getByText("Inspect the firewall logs.")).toBeInTheDocument();
  });

  it("falls back to a no-runbook message on 404", async () => {
    globalThis.fetch = stubFetch({ detail: "not found" }, false);
    render(withClient(<RunbookPanel techniqueId="T9999" />));
    await waitFor(() => {
      expect(
        screen.getByText(/No runbook is bundled for technique/i),
      ).toBeInTheDocument();
    });
  });
});
