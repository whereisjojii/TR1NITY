import type { Incident } from "../lib/types";
import { formatTimestamp, severityClass, severityLabel } from "../lib/utils";

interface Props {
  incident: Incident;
}

export function EventTimeline({ incident }: Props): JSX.Element {
  const members = [...incident.members].sort(
    (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime(),
  );
  if (members.length === 0) {
    return (
      <div className="text-xs text-muted-foreground">
        No member events on this incident.
      </div>
    );
  }
  return (
    <ol className="space-y-2">
      {members.map((m, idx) => (
        <li
          key={m.event_id ?? idx}
          className="grid grid-cols-[120px_minmax(0,1fr)] gap-3 rounded border border-border bg-muted/30 px-3 py-2"
        >
          <div className="font-mono text-[11px] text-muted-foreground">
            {formatTimestamp(m.timestamp)}
          </div>
          <div className="min-w-0 space-y-0.5">
            <div className="flex items-center gap-2 text-xs">
              <span className={severityClass(m.severity)}>
                {severityLabel(m.severity).slice(0, 4)}
              </span>
              <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] uppercase text-muted-foreground">
                {m.source}
              </span>
              {m.source_ip ? (
                <span className="font-mono text-[11px] text-foreground">
                  {m.source_ip}
                </span>
              ) : null}
              {m.user ? (
                <span className="font-mono text-[11px] text-muted-foreground">
                  user: {m.user}
                </span>
              ) : null}
            </div>
            <div className="truncate text-xs text-foreground">
              {m.message ?? "—"}
            </div>
            {m.technique_ids && m.technique_ids.length > 0 ? (
              <div className="flex flex-wrap gap-1 pt-0.5">
                {m.technique_ids.map((t) => (
                  <span
                    key={t}
                    className="rounded border border-accent/40 bg-accent/10 px-1.5 py-0.5 font-mono text-[10px] text-accent"
                  >
                    {t}
                  </span>
                ))}
              </div>
            ) : null}
          </div>
        </li>
      ))}
    </ol>
  );
}
