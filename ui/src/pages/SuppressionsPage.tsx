import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { useState } from "react";
import { Topbar } from "../components/Topbar";
import {
  createSuppression,
  deleteSuppression,
  listSuppressions,
} from "../lib/api";
import { formatTimestamp } from "../lib/utils";

interface FormState {
  name: string;
  matchJson: string;
  fpScore: number;
  ttlDays: number | "";
  author: string;
  reason: string;
}

const EMPTY_FORM: FormState = {
  name: "",
  matchJson: '{\n  "sources": ["firewall"]\n}',
  fpScore: 0.95,
  ttlDays: 30,
  author: "",
  reason: "",
};

export function SuppressionsPage(): JSX.Element {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [parseError, setParseError] = useState<string | null>(null);

  const query = useQuery({
    queryKey: ["suppressions"],
    queryFn: listSuppressions,
    refetchInterval: 30_000,
  });

  const createMutation = useMutation({
    mutationFn: () => {
      let match: Record<string, unknown> = {};
      try {
        match = JSON.parse(form.matchJson);
      } catch (e) {
        throw new Error(`match JSON is invalid: ${(e as Error).message}`);
      }
      if (
        !match ||
        typeof match !== "object" ||
        Object.keys(match).length === 0
      ) {
        throw new Error("match must be a non-empty JSON object");
      }
      return createSuppression({
        name: form.name.trim() || "untitled-rule",
        match,
        fp_score: form.fpScore,
        ttl_days:
          form.ttlDays === "" || form.ttlDays === null
            ? null
            : Number(form.ttlDays),
        author: form.author.trim() || null,
        reason: form.reason.trim() || null,
      });
    },
    onSuccess: () => {
      setForm(EMPTY_FORM);
      setParseError(null);
      queryClient.invalidateQueries({ queryKey: ["suppressions"] });
    },
    onError: (error: Error) => setParseError(error.message),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteSuppression,
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["suppressions"] }),
  });

  const items = query.data?.items ?? [];

  return (
    <>
      <Topbar
        title="Suppressions"
        subtitle={
          query.data
            ? `${query.data.total} active rule${
                query.data.total === 1 ? "" : "s"
              }`
            : "Loading…"
        }
      />
      <div className="grid flex-1 grid-cols-1 gap-4 overflow-auto p-5 lg:grid-cols-[2fr_3fr]">
        <section
          className="card flex h-full flex-col"
          data-testid="suppression-form"
        >
          <header className="border-b border-border p-3">
            <h2 className="text-sm font-semibold text-foreground">
              New suppression rule
            </h2>
            <p className="mt-1 text-[11px] text-muted-foreground">
              Layer 3 of the FP score. Match keys map onto the incident document
              (top-level fields, dotted paths, or member event fields). Score{" "}
              <code className="font-mono">0..1</code> — composite uses{" "}
              <code className="font-mono">max</code> across all layers.
            </p>
          </header>
          <div className="grid grid-cols-1 gap-2 p-3">
            <label className="text-[11px] uppercase tracking-wider text-muted-foreground">
              Name
              <input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="e.g. lab-vuln-scanner"
                className="mt-1 w-full rounded border border-border bg-muted px-2 py-1 text-xs text-foreground"
              />
            </label>
            <label className="text-[11px] uppercase tracking-wider text-muted-foreground">
              Match JSON
              <textarea
                value={form.matchJson}
                onChange={(e) =>
                  setForm({ ...form, matchJson: e.target.value })
                }
                rows={6}
                spellCheck={false}
                className="mt-1 w-full rounded border border-border bg-muted px-2 py-1 font-mono text-[11px] text-foreground"
              />
            </label>
            <div className="grid grid-cols-2 gap-2">
              <label className="text-[11px] uppercase tracking-wider text-muted-foreground">
                FP score
                <input
                  type="number"
                  min={0}
                  max={1}
                  step={0.05}
                  value={form.fpScore}
                  onChange={(e) =>
                    setForm({ ...form, fpScore: Number(e.target.value) })
                  }
                  className="mt-1 w-full rounded border border-border bg-muted px-2 py-1 text-xs"
                />
              </label>
              <label className="text-[11px] uppercase tracking-wider text-muted-foreground">
                TTL (days)
                <input
                  type="number"
                  min={1}
                  max={365}
                  value={form.ttlDays}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      ttlDays:
                        e.target.value === "" ? "" : Number(e.target.value),
                    })
                  }
                  placeholder="permanent"
                  className="mt-1 w-full rounded border border-border bg-muted px-2 py-1 text-xs"
                />
              </label>
            </div>
            <label className="text-[11px] uppercase tracking-wider text-muted-foreground">
              Author
              <input
                value={form.author}
                onChange={(e) => setForm({ ...form, author: e.target.value })}
                placeholder="analyst@team"
                className="mt-1 w-full rounded border border-border bg-muted px-2 py-1 text-xs"
              />
            </label>
            <label className="text-[11px] uppercase tracking-wider text-muted-foreground">
              Reason / audit note
              <input
                value={form.reason}
                onChange={(e) => setForm({ ...form, reason: e.target.value })}
                placeholder="Approved by SOC lead — ticket #1234"
                className="mt-1 w-full rounded border border-border bg-muted px-2 py-1 text-xs"
              />
            </label>
            {parseError ? (
              <div className="text-xs text-danger">{parseError}</div>
            ) : null}
            <button
              type="button"
              className="btn btn-primary mt-1"
              disabled={createMutation.isPending}
              onClick={() => createMutation.mutate()}
            >
              {createMutation.isPending ? "Saving…" : "Create rule"}
            </button>
          </div>
        </section>
        <section className="card flex h-full flex-col">
          <header className="border-b border-border p-3 text-sm font-semibold text-foreground">
            Active rules
          </header>
          <ul className="flex-1 divide-y divide-border overflow-auto">
            {items.length === 0 ? (
              <li className="p-4 text-xs text-muted-foreground">
                No active suppression rules. Layer 1 whitelist still applies
                from <code className="font-mono">whitelist.yaml</code>.
              </li>
            ) : (
              items.map((rule) => (
                <li key={rule.suppression_id} className="space-y-2 p-3 text-sm">
                  <header className="flex items-start justify-between gap-2">
                    <div>
                      <div className="font-semibold text-foreground">
                        {rule.name}
                      </div>
                      <div className="text-[11px] text-muted-foreground">
                        score {rule.fp_score.toFixed(2)} ·{" "}
                        {rule.author ?? "unknown"} ·{" "}
                        {rule.expires_at
                          ? `expires ${formatTimestamp(rule.expires_at)}`
                          : "permanent"}
                      </div>
                    </div>
                    <button
                      type="button"
                      className="btn btn-danger px-2 py-1 text-[11px]"
                      onClick={() => deleteMutation.mutate(rule.suppression_id)}
                      disabled={deleteMutation.isPending}
                      aria-label={`Delete rule ${rule.name}`}
                    >
                      <Trash2 size={12} />
                    </button>
                  </header>
                  <pre className="overflow-auto rounded bg-muted/40 p-2 font-mono text-[11px] text-foreground">
                    {JSON.stringify(rule.match, null, 2)}
                  </pre>
                  {rule.reason ? (
                    <div className="text-xs text-muted-foreground">
                      <strong>Reason:</strong> {rule.reason}
                    </div>
                  ) : null}
                </li>
              ))
            )}
          </ul>
        </section>
      </div>
    </>
  );
}
