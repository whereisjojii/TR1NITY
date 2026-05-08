import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ShieldCheck, ShieldX, Sparkles } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { AttackChain } from "../components/AttackChain";
import { EventTimeline } from "../components/EventTimeline";
import { FPLayerBadge } from "../components/FPLayerBadge";
import { IntelHits } from "../components/IntelHits";
import { RunbookPanel } from "../components/RunbookPanel";
import { Topbar } from "../components/Topbar";
import { useVimShortcuts } from "../hooks/useVimShortcuts";
import { createCase, getIncident, markFP, similarIncidents } from "../lib/api";
import type { Incident } from "../lib/types";
import {
  cn,
  formatTimestamp,
  fpScoreLabel,
  severityClass,
  severityLabel,
} from "../lib/utils";

type DetailTab = "overview" | "raw" | "timeline" | "similar" | "runbook";

const TABS: { value: DetailTab; label: string; key: string }[] = [
  { value: "overview", label: "Overview", key: "1" },
  { value: "timeline", label: "Timeline", key: "2" },
  { value: "raw", label: "Raw events", key: "3" },
  { value: "similar", label: "Similar", key: "4" },
  { value: "runbook", label: "Runbook", key: "5" },
];

export function IncidentDetailPage(): JSX.Element {
  const params = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const incidentId = params.id ?? "";

  const [tab, setTab] = useState<DetailTab>("overview");

  const incidentQuery = useQuery({
    queryKey: ["incidents", "detail", incidentId],
    queryFn: () => getIncident(incidentId),
    enabled: !!incidentId,
  });

  const similarQuery = useQuery({
    queryKey: ["incidents", "similar", incidentId],
    queryFn: () => similarIncidents(incidentId, 8),
    enabled: !!incidentId && tab === "similar",
  });

  const fpMutation = useMutation({
    mutationFn: (isFP: boolean) => markFP(incidentId, { is_fp: isFP }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["incidents"] });
    },
  });

  const caseMutation = useMutation({
    mutationFn: () =>
      createCase({
        title: incidentQuery.data?.title ?? "Untitled incident",
        summary: incidentQuery.data?.summary ?? null,
        severity: incidentQuery.data?.severity ?? 0,
        incident_ids: [incidentId],
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["cases"] });
      navigate("/cases");
    },
  });

  useVimShortcuts([
    {
      key: "Escape",
      description: "Back to queue",
      handler: () => navigate("/queue"),
    },
    {
      key: "h",
      description: "Back to queue",
      handler: () => navigate("/queue"),
    },
    {
      key: "f",
      description: "Mark false positive",
      handler: () => fpMutation.mutate(true),
    },
    {
      key: "t",
      description: "Mark true positive",
      handler: () => fpMutation.mutate(false),
    },
    {
      key: "c",
      description: "Create case from incident",
      handler: () => caseMutation.mutate(),
    },
    ...TABS.map(
      (t) =>
        ({
          key: t.key,
          description: `Switch to ${t.label}`,
          handler: () => setTab(t.value),
        }) as const,
    ),
  ]);

  if (incidentQuery.isLoading) {
    return (
      <>
        <Topbar title={`Incident ${incidentId}`} subtitle="Loading…" />
        <div className="p-6 text-sm text-muted-foreground">
          Loading incident…
        </div>
      </>
    );
  }

  if (incidentQuery.isError || !incidentQuery.data) {
    return (
      <>
        <Topbar title={`Incident ${incidentId}`} subtitle="Not found" />
        <div className="p-6">
          <p className="text-sm text-danger">
            Failed to load incident:{" "}
            {(incidentQuery.error as Error | undefined)?.message ?? "unknown"}
          </p>
          <Link to="/queue" className="btn mt-4 inline-flex">
            <ArrowLeft size={14} /> Back to queue
          </Link>
        </div>
      </>
    );
  }

  const incident: Incident = incidentQuery.data;
  const fpScore = incident.fp_score ?? 0.5;

  return (
    <>
      <Topbar
        title={incident.title}
        subtitle={
          <span>
            {incident.incident_id} · {incident.member_count} events · last seen{" "}
            {formatTimestamp(incident.last_event_at)}
          </span>
        }
        right={
          <div className="flex items-center gap-2">
            <span className={severityClass(incident.severity)}>
              {severityLabel(incident.severity)} ({incident.severity})
            </span>
            <span className="rounded bg-muted px-2 py-1 font-mono text-[11px] text-muted-foreground">
              FP {fpScoreLabel(fpScore)} ({fpScore.toFixed(2)})
            </span>
            <button
              type="button"
              className="btn btn-danger"
              onClick={() => fpMutation.mutate(true)}
              disabled={fpMutation.isPending}
            >
              <ShieldX size={14} /> Mark FP <span className="kbd">f</span>
            </button>
            <button
              type="button"
              className="btn"
              onClick={() => fpMutation.mutate(false)}
              disabled={fpMutation.isPending}
            >
              <ShieldCheck size={14} /> Mark TP <span className="kbd">t</span>
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => caseMutation.mutate()}
              disabled={caseMutation.isPending}
            >
              <Sparkles size={14} /> New case <span className="kbd">c</span>
            </button>
          </div>
        }
      />
      <div className="flex border-b border-border bg-card-bg px-4">
        {TABS.map((t) => (
          <button
            key={t.value}
            type="button"
            className={cn(
              "border-b-2 px-3 py-2 text-xs",
              tab === t.value
                ? "border-accent text-accent"
                : "border-transparent text-muted-foreground hover:text-foreground",
            )}
            onClick={() => setTab(t.value)}
          >
            {t.label} <span className="kbd ml-1">{t.key}</span>
          </button>
        ))}
      </div>
      <div className="grid flex-1 grid-cols-1 gap-4 overflow-auto p-5 lg:grid-cols-[2fr_1fr]">
        {tab === "overview" ? (
          <>
            <section className="card p-4">
              <h2 className="mb-2 text-sm font-semibold text-foreground">
                Summary
              </h2>
              <p className="text-sm text-muted-foreground">
                {incident.summary ?? "No correlator-generated summary."}
              </p>
              <div className="mt-4">
                <h3 className="mb-2 text-xs uppercase tracking-wider text-muted-foreground">
                  ATT&CK chain
                </h3>
                <AttackChain incident={incident} />
              </div>
              <div className="mt-4">
                <h3 className="mb-2 text-xs uppercase tracking-wider text-muted-foreground">
                  FP score breakdown
                </h3>
                <FPLayerBadge layers={incident.fp_layers ?? []} />
              </div>
              <div className="mt-4">
                <h3 className="mb-2 text-xs uppercase tracking-wider text-muted-foreground">
                  SIGMA matches
                </h3>
                {incident.sigma_matches && incident.sigma_matches.length > 0 ? (
                  <ul className="grid grid-cols-1 gap-1 sm:grid-cols-2">
                    {incident.sigma_matches.map((id) => (
                      <li
                        key={id}
                        className="rounded border border-border bg-muted/40 px-2 py-1 font-mono text-[11px]"
                      >
                        {id}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <div className="text-xs text-muted-foreground">
                    No SIGMA rules matched.
                  </div>
                )}
              </div>
            </section>
            <aside className="card p-4">
              <h2 className="mb-2 text-sm font-semibold text-foreground">
                Threat intel
              </h2>
              <IntelHits hits={incident.intel_hits ?? []} />
              <h2 className="mt-5 mb-2 text-sm font-semibold text-foreground">
                Sources
              </h2>
              <ul className="space-y-1">
                {incident.sources.map((s) => (
                  <li
                    key={s}
                    className="flex items-center justify-between rounded border border-border bg-muted/40 px-2 py-1 text-xs"
                  >
                    <span className="font-mono uppercase text-muted-foreground">
                      {s}
                    </span>
                    <span className="text-foreground">
                      {incident.members.filter((m) => m.source === s).length}{" "}
                      events
                    </span>
                  </li>
                ))}
              </ul>
            </aside>
          </>
        ) : null}
        {tab === "timeline" ? (
          <section className="card p-4 lg:col-span-2">
            <h2 className="mb-2 text-sm font-semibold text-foreground">
              Event timeline
            </h2>
            <EventTimeline incident={incident} />
          </section>
        ) : null}
        {tab === "raw" ? (
          <section className="card lg:col-span-2">
            <h2 className="border-b border-border px-4 py-2 text-sm font-semibold text-foreground">
              Raw incident document
            </h2>
            <pre className="max-h-[60vh] overflow-auto p-4 font-mono text-[11px] leading-snug text-foreground">
              {JSON.stringify(incident, null, 2)}
            </pre>
          </section>
        ) : null}
        {tab === "runbook" ? (
          <section className="card p-4 lg:col-span-2">
            <h2 className="mb-2 text-sm font-semibold text-foreground">
              Response runbook
            </h2>
            <p className="mb-3 text-xs text-muted-foreground">
              Auto-attached based on the primary ATT&amp;CK technique. Edit
              under <code className="font-mono">docs/runbooks/</code>.
            </p>
            {incident.technique_ids.length > 0 ? (
              <RunbookPanel techniqueId={incident.technique_ids[0]} />
            ) : (
              <div className="text-sm text-muted-foreground">
                Incident has no ATT&amp;CK technique attached.
              </div>
            )}
          </section>
        ) : null}
        {tab === "similar" ? (
          <section className="card p-4 lg:col-span-2">
            <h2 className="mb-2 text-sm font-semibold text-foreground">
              Similar past incidents
            </h2>
            <p className="mb-3 text-xs text-muted-foreground">
              Phase 3 uses a deterministic IP / technique heuristic. Phase 5
              swaps in ChromaDB cosine similarity over incident embeddings.
            </p>
            {similarQuery.isLoading ? (
              <div className="text-sm text-muted-foreground">
                Computing similarity…
              </div>
            ) : similarQuery.data?.items.length ? (
              <ul className="space-y-2">
                {similarQuery.data.items.map((sim) => (
                  <li
                    key={sim.incident_id}
                    className="flex items-center justify-between rounded border border-border bg-muted/40 px-3 py-2 text-sm"
                  >
                    <Link
                      to={`/incidents/${sim.incident_id}`}
                      className="min-w-0 flex-1 truncate text-foreground hover:text-accent"
                    >
                      {sim.title}
                    </Link>
                    <span className="ml-3 font-mono text-[11px] text-muted-foreground">
                      score {(sim.similarity_score ?? 0).toFixed(2)}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="text-xs text-muted-foreground">
                No similar incidents above the heuristic threshold.
              </div>
            )}
          </section>
        ) : null}
      </div>
    </>
  );
}
