import { ShieldAlert, Zap } from "lucide-react";
import type { CSSProperties } from "react";
import type { Incident } from "../lib/types";
import {
  cn,
  formatTimestamp,
  fpScoreLabel,
  severityClass,
  severityLabel,
} from "../lib/utils";

interface Props {
  incident: Incident;
  selected?: boolean;
  onSelect?: (incident: Incident) => void;
  onOpen?: (incident: Incident) => void;
  style?: CSSProperties;
}

export function IncidentRow({
  incident,
  selected,
  onSelect,
  onOpen,
  style,
}: Props): JSX.Element {
  const sev = incident.severity ?? 0;
  const fpScore = incident.fp_score ?? 0.5;
  const sourceIp = incident.members.find((m) => m.source_ip)?.source_ip;

  return (
    <button
      type="button"
      style={style}
      data-incident-id={incident.incident_id}
      onClick={() => onSelect?.(incident)}
      onDoubleClick={() => onOpen?.(incident)}
      className={cn(
        "group grid w-full grid-cols-[42px_minmax(0,1fr)_120px_140px_120px] items-center gap-3 border-b border-border/60 px-4 py-2 text-left text-sm transition-colors hover:bg-muted/40",
        selected && "row-selected",
      )}
    >
      <span className={severityClass(sev)} title={`Severity ${sev}`}>
        {severityLabel(sev).slice(0, 4)}
      </span>
      <span className="min-w-0">
        <div className="truncate font-medium text-foreground">
          {incident.title}
        </div>
        <div className="truncate text-[11px] text-muted-foreground">
          {sourceIp ? <span className="font-mono">{sourceIp}</span> : "—"}
          {incident.technique_ids.length > 0 ? (
            <span className="ml-2 font-mono text-accent">
              {incident.technique_ids.slice(0, 4).join(" · ")}
              {incident.technique_ids.length > 4 ? "…" : ""}
            </span>
          ) : null}
        </div>
      </span>
      <span className="flex flex-wrap items-center gap-1">
        {incident.sources.map((s) => (
          <span
            key={s}
            className="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] uppercase text-muted-foreground"
          >
            {s}
          </span>
        ))}
      </span>
      <span className="flex items-center gap-1.5 font-mono text-[11px] text-muted-foreground">
        <Zap size={12} />
        {fpScoreLabel(fpScore)} ({fpScore.toFixed(2)})
      </span>
      <span className="flex items-center justify-end gap-1.5 font-mono text-[11px] text-muted-foreground">
        <ShieldAlert size={12} />
        {formatTimestamp(incident.last_event_at)}
      </span>
    </button>
  );
}
