import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Topbar } from "../components/Topbar";
import { getHeatmap } from "../lib/api";
import { TACTIC_ORDER, tacticName, techniqueName } from "../lib/attack";

function intensityClass(count: number, max: number): string {
  if (count === 0 || max === 0) return "bg-muted/40 text-muted-foreground";
  const ratio = count / max;
  if (ratio >= 0.75) return "bg-critical/40 text-critical";
  if (ratio >= 0.5) return "bg-danger/30 text-danger";
  if (ratio >= 0.25) return "bg-warning/25 text-warning";
  return "bg-accent/20 text-accent";
}

export function HeatmapPage(): JSX.Element {
  const [severityMin, setSeverityMin] = useState<number | undefined>(undefined);
  const heatmap = useQuery({
    queryKey: ["attack", "heatmap", severityMin],
    queryFn: () => getHeatmap(severityMin),
    refetchInterval: 30_000,
  });

  const data = heatmap.data;
  const max = data?.techniques.reduce((m, t) => Math.max(m, t.count), 0) ?? 0;

  type HeatTech = NonNullable<typeof data>["techniques"][number];
  // Group techniques by primary tactic. The api emits ``tactics`` per
  // technique already; we render the canonical kill-chain order.
  const techniquesByTactic: Record<string, HeatTech[]> = {};
  if (data) {
    for (const tac of TACTIC_ORDER) {
      techniquesByTactic[tac] = [];
    }
    techniquesByTactic.UNKNOWN = [];
    for (const t of data.techniques) {
      const primary = t.tactics[0] ?? "UNKNOWN";
      const bucket = techniquesByTactic[primary] ?? techniquesByTactic.UNKNOWN;
      bucket.push(t);
    }
  }

  return (
    <>
      <Topbar
        title="MITRE ATT&CK · live heatmap"
        subtitle={
          data
            ? `${data.covered_incidents} / ${data.total_incidents} incidents map to a technique`
            : "Loading…"
        }
        onRefresh={() => heatmap.refetch()}
        refreshing={heatmap.isFetching}
        right={
          <select
            className="rounded border border-border bg-muted px-2 py-1 text-xs"
            value={severityMin ?? ""}
            onChange={(e) =>
              setSeverityMin(
                e.target.value ? Number(e.target.value) : undefined,
              )
            }
          >
            <option value="">any severity</option>
            {[3, 5, 7].map((v) => (
              <option key={v} value={v}>
                ≥ {v}
              </option>
            ))}
          </select>
        }
      />
      <div className="flex-1 overflow-auto p-5">
        {heatmap.isLoading ? (
          <div className="text-sm text-muted-foreground">
            Computing heatmap…
          </div>
        ) : heatmap.isError ? (
          <div className="text-sm text-danger">
            Failed to load: {(heatmap.error as Error).message}
          </div>
        ) : data ? (
          <div className="grid grid-cols-[repeat(auto-fit,minmax(220px,1fr))] gap-3">
            {TACTIC_ORDER.map((tacticId) => {
              const techs = techniquesByTactic[tacticId] ?? [];
              if (techs.length === 0) return null;
              return (
                <section key={tacticId} className="card flex h-full flex-col">
                  <header className="border-b border-border px-3 py-2">
                    <div className="font-mono text-[11px] uppercase tracking-wide text-muted-foreground">
                      {tacticId}
                    </div>
                    <div className="text-sm font-semibold text-foreground">
                      {tacticName(tacticId)}
                    </div>
                  </header>
                  <ul className="flex-1 space-y-1 px-2 py-2">
                    {techs.map((t) => (
                      <li
                        key={t.id}
                        className={`flex items-center justify-between rounded px-2 py-1 font-mono text-[11px] ${intensityClass(
                          t.count,
                          max,
                        )}`}
                        title={`${t.id} · ${techniqueName(t.id)}`}
                      >
                        <span className="truncate">
                          {t.id}{" "}
                          <span className="text-muted-foreground">
                            {techniqueName(t.id)}
                          </span>
                        </span>
                        <span>{t.count}</span>
                      </li>
                    ))}
                  </ul>
                </section>
              );
            })}
            {techniquesByTactic.UNKNOWN.length > 0 ? (
              <section className="card flex h-full flex-col">
                <header className="border-b border-border px-3 py-2">
                  <div className="font-mono text-[11px] uppercase tracking-wide text-muted-foreground">
                    Unmapped
                  </div>
                  <div className="text-sm font-semibold text-foreground">
                    Without primary tactic
                  </div>
                </header>
                <ul className="flex-1 space-y-1 px-2 py-2">
                  {techniquesByTactic.UNKNOWN.map((t) => (
                    <li
                      key={t.id}
                      className={`flex items-center justify-between rounded px-2 py-1 font-mono text-[11px] ${intensityClass(
                        t.count,
                        max,
                      )}`}
                    >
                      <span>{t.id}</span>
                      <span>{t.count}</span>
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}
          </div>
        ) : null}
      </div>
    </>
  );
}
