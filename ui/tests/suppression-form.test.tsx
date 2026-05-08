import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SuppressionsPage } from "../src/pages/SuppressionsPage";

interface FetchCall {
  url: string;
  method: string;
  body?: string;
}

const calls: FetchCall[] = [];
let originalFetch: typeof fetch;

const stub: typeof fetch = vi.fn(async (input, init) => {
  const url = typeof input === "string" ? input : (input as Request).url;
  const method = (init?.method ?? "GET").toUpperCase();
  const body = (init?.body ?? undefined) as string | undefined;
  calls.push({ url, method, body });

  if (method === "GET" && url === "/api/suppressions") {
    return new Response(
      JSON.stringify({
        items: [],
        total: 0,
        fetched_at: new Date().toISOString(),
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    );
  }
  if (method === "POST" && url === "/api/suppressions") {
    return new Response(
      JSON.stringify({
        suppression_id: "s-1",
        name: "test-rule",
        match: { sources: ["firewall"] },
        fp_score: 0.95,
        ttl_days: 30,
        author: null,
        reason: null,
        created_at: new Date().toISOString(),
        expires_at: new Date(Date.now() + 86400000).toISOString(),
      }),
      { status: 201, headers: { "Content-Type": "application/json" } },
    );
  }
  return new Response(JSON.stringify({}), { status: 404 });
}) as unknown as typeof fetch;

beforeEach(() => {
  originalFetch = globalThis.fetch;
  calls.length = 0;
  globalThis.fetch = stub;
});

afterEach(() => {
  globalThis.fetch = originalFetch;
});

function harness(): JSX.Element {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return (
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <SuppressionsPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("SuppressionsPage", () => {
  it("submits a new suppression rule with the right body", async () => {
    const user = userEvent.setup();
    render(harness());

    const nameInput = await screen.findByPlaceholderText(/lab-vuln-scanner/i);
    await user.clear(nameInput);
    await user.type(nameInput, "test-rule");

    const submit = await screen.findByRole("button", { name: /create rule/i });
    await user.click(submit);

    await waitFor(() => {
      const post = calls.find((c) => c.method === "POST");
      expect(post).toBeDefined();
      expect(post?.url).toBe("/api/suppressions");
      const parsed = JSON.parse(post?.body ?? "{}");
      expect(parsed.name).toBe("test-rule");
      expect(parsed.match).toEqual({ sources: ["firewall"] });
      expect(parsed.fp_score).toBeCloseTo(0.95);
    });
  });

  it("shows a parse error when match JSON is invalid", async () => {
    const user = userEvent.setup();
    render(harness());

    const matchInput = await screen.findByDisplayValue(/sources/i);
    await user.clear(matchInput);
    await user.type(matchInput, "not-json");

    const submit = await screen.findByRole("button", { name: /create rule/i });
    await user.click(submit);

    await waitFor(() => {
      expect(screen.getByText(/match JSON is invalid/i)).toBeInTheDocument();
    });
  });
});
