import type { Incident } from "../lib/types";
import { tacticName, techniqueName } from "../lib/attack";

interface Props {
  incident: Incident;
}

export function AttackChain({ incident }: Props): JSX.Element {
  const tactics = incident.tactic_ids ?? [];
  const techniques = incident.technique_ids ?? [];
  if (tactics.length === 0 && techniques.length === 0) {
    return (
      <div className="text-xs text-muted-foreground">
        No ATT&CK techniques observed in this incident.
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-3">
      {tactics.length > 0 ? (
        <div className="flex flex-wrap items-center gap-1">
          {tactics.map((id, idx) => (
            <span key={id} className="flex items-center gap-1">
              <span className="rounded border border-accent/40 bg-accent/10 px-2 py-0.5 font-mono text-[11px] text-accent">
                <span className="opacity-60">{id}</span> · {tacticName(id)}
              </span>
              {idx < tactics.length - 1 ? (
                <span className="text-muted-foreground">→</span>
              ) : null}
            </span>
          ))}
        </div>
      ) : null}
      {techniques.length > 0 ? (
        <ul className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
          {techniques.map((id) => (
            <li
              key={id}
              className="flex items-center justify-between rounded border border-border bg-muted/40 px-2 py-1 font-mono text-[11px]"
            >
              <span className="text-foreground">{id}</span>
              <span className="ml-2 text-muted-foreground">
                {techniqueName(id)}
              </span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
