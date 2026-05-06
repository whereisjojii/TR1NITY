import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, Filter } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { IncidentRow } from "../components/IncidentRow";
import { Topbar } from "../components/Topbar";
import { useVimShortcuts } from "../hooks/useVimShortcuts";
import { listIncidents, markFP, refreshIncidents } from "../lib/api";
import type { ListIncidentsParams as ApiParams } from "../lib/api";
import type { Incident } from "../lib/types";

const SORT_OPTIONS: { value: ApiParams["sort_by"]; label: string }[] = [
  { value: "fp_score", label: "FP score" },
  { value: "severity", label: "Severity" },
  { value: "last_event_at", label: "Last event" },
  { value: "created_at", label: "Created" },
];

const SOURCE_FILTERS: { value: string; label: string }[] = [
  { value: "wazuh", label: "Wazuh" },
  { value: "firewall", label: "Firewall" },
  { value: "waf", label: "WAF" },
];

export function QueuePage(): JSX.Element {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [sortBy, setSortBy] = useState<ApiParams["sort_by"]>("fp_score");
  const [descending, setDescending] = useState<boolean>(false);
  const [severityMin, setSeverityMin] = useState<number | undefined>(undefined);
  const [sourceFilter, setSourceFilter] = useState<string[]>([]);
  const [selectedIndex, setSelectedIndex] = useState<number>(0);

  const params: ApiParams = useMemo(
    () => ({
      sort_by: sortBy,
      descending,
      severity_min: severityMin,
      sources: sourceFilter.length ? sourceFilter : undefined,
    }),
    [sortBy, descending, severityMin, sourceFilter],
  );

  const incidentsQuery = useQuery({
    queryKey: ["incidents", "list", params],
    queryFn: () => listIncidents(params),
    refetchInterval: 15_000,
  });

  const refreshMutation = useMutation({
    mutationFn: refreshIncidents,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["incidents"] });
      queryClient.invalidateQueries({ queryKey: ["attack", "heatmap"] });
    },
  });

  const fpMutation = useMutation({
    mutationFn: ({ id, isFP }: { id: string; isFP: boolean }) =>
      markFP(id, { is_fp: isFP }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["incidents"] });
    },
  });

  const items: Incident[] = incidentsQuery.data?.items ?? [];

  useEffect(() => {
    if (selectedIndex >= items.length) {
      setSelectedIndex(Math.max(0, items.length - 1));
    }
  }, [items.length, selectedIndex]);

  const selected = items[selectedIndex];

  useVimShortcuts([
    {
      key: "j",
      description: "Next incident",
      handler: () =>
        setSelectedIndex((idx) => Math.min(idx + 1, items.length - 1)),
    },
    {
      key: "k",
      description: "Previous incident",
      handler: () => setSelectedIndex((idx) => Math.max(idx - 1, 0)),
    },
    {
      key: "g",
      follow: "g",
      description: "Jump to top",
      handler: () => setSelectedIndex(0),
    },
    {
      key: "G",
      shift: true,
      description: "Jump to bottom",
      handler: () => setSelectedIndex(Math.max(0, items.length - 1)),
    },
    {
      key: "o",
      description: "Open selected incident",
      handler: () => {
        if (selected) navigate(`/incidents/${selected.incident_id}`);
      },
    },
    {
      key: "Enter",
      description: "Open selected incident",
      handler: () => {
        if (selected) navigate(`/incidents/${selected.incident_id}`);
      },
    },
    {
      key: "f",
      description: "Mark selected as false positive",
      handler: () => {
        if (selected)
          fpMutation.mutate({ id: selected.incident_id, isFP: true });
      },
    },
    {
      key: "t",
      description: "Mark selected as true positive",
      handler: () => {
        if (selected)
          fpMutation.mutate({ id: selected.incident_id, isFP: false });
      },
    },
    {
      key: "r",
      description: "Trigger correlator tick",
      handler: () => refreshMutation.mutate(),
    },
  ]);

  return (
    <>
      <Topbar
        title="Incident queue"
        subtitle={
          incidentsQuery.data
            ? `${incidentsQuery.data.total} incidents · sorted by ${sortBy}${
                descending ? " ↓" : " ↑"
              }`
            : "Loading…"
        }
        onRefresh={() => refreshMutation.mutate()}
        refreshing={refreshMutation.isPending}
        right={
          <div className="flex items-center gap-2">
            <select
              className="rounded border border-border bg-muted px-2 py-1 text-xs"
              value={sortBy}
              onChange={(e) =>
                setSortBy(e.target.value as ApiParams["sort_by"])
              }
            >
              {SORT_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  Sort: {opt.label}
                </option>
              ))}
            </select>
            <button
              type="button"
              className="btn"
              onClick={() => setDescending((v) => !v)}
              title="Toggle sort direction"
            >
              {descending ? <ArrowDown size={14} /> : <ArrowUp size={14} />}
            </button>
          </div>
        }
      />
      <div className="flex flex-wrap items-center gap-3 border-b border-border bg-card-bg px-5 py-2 text-xs">
        <Filter size={12} className="text-muted-foreground" />
        <span className="text-muted-foreground">Sources:</span>
        {SOURCE_FILTERS.map((s) => {
          const active = sourceFilter.includes(s.value);
          return (
            <button
              key={s.value}
              type="button"
              className={`rounded px-2 py-1 font-mono text-[10px] uppercase ${
                active
                  ? "bg-accent text-accent-foreground"
                  : "bg-muted text-muted-foreground hover:bg-border"
              }`}
              onClick={() =>
                setSourceFilter((prev) =>
                  prev.includes(s.value)
                    ? prev.filter((v) => v !== s.value)
                    : [...prev, s.value],
                )
              }
            >
              {s.label}
            </button>
          );
        })}
        <span className="ml-4 text-muted-foreground">Min severity:</span>
        <select
          className="rounded border border-border bg-muted px-2 py-1 text-xs"
          value={severityMin ?? ""}
          onChange={(e) =>
            setSeverityMin(e.target.value ? Number(e.target.value) : undefined)
          }
        >
          <option value="">any</option>
          {[1, 3, 5, 7].map((v) => (
            <option key={v} value={v}>
              ≥ {v}
            </option>
          ))}
        </select>
      </div>
      <div className="flex-1 overflow-auto">
        {incidentsQuery.isLoading ? (
          <div className="p-6 text-sm text-muted-foreground">
            Loading incidents…
          </div>
        ) : incidentsQuery.isError ? (
          <div className="p-6 text-sm text-danger">
            Failed to load incidents: {(incidentsQuery.error as Error).message}
          </div>
        ) : items.length === 0 ? (
          <div className="flex h-full items-center justify-center p-10 text-sm text-muted-foreground">
            <div className="max-w-md text-center">
              <div className="mb-2 text-base font-semibold text-foreground">
                Queue is clear
              </div>
              <p>
                No incidents yet. Press <span className="kbd">r</span> to
                trigger a correlator tick or run{" "}
                <span className="font-mono">make demo</span> from the repo root.
              </p>
            </div>
          </div>
        ) : (
          <div role="list" data-testid="queue-list">
            <div className="grid grid-cols-[42px_minmax(0,1fr)_120px_140px_120px] gap-3 border-b border-border bg-muted/30 px-4 py-1.5 text-[10px] uppercase tracking-wide text-muted-foreground">
              <span>Sev</span>
              <span>Title / IP / techniques</span>
              <span>Sources</span>
              <span>FP score</span>
              <span className="text-right">Last event</span>
            </div>
            {items.map((inc, i) => (
              <IncidentRow
                key={inc.incident_id}
                incident={inc}
                selected={i === selectedIndex}
                onSelect={() => setSelectedIndex(i)}
                onOpen={() => navigate(`/incidents/${inc.incident_id}`)}
              />
            ))}
          </div>
        )}
      </div>
    </>
  );
}
