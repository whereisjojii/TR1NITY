import type { IntelHit } from "../lib/types";

interface Props {
  hits: IntelHit[];
}

export function IntelHits({ hits }: Props): JSX.Element {
  if (!hits || hits.length === 0) {
    return (
      <div className="text-xs text-muted-foreground">
        No threat-intel matches.
      </div>
    );
  }
  return (
    <ul className="space-y-1.5">
      {hits.map((hit, idx) => (
        <li
          key={`${hit.source}-${idx}`}
          className="flex items-start justify-between gap-3 rounded border border-warning/30 bg-warning/5 px-3 py-2 text-xs"
        >
          <div className="min-w-0">
            <div className="font-mono text-[11px] uppercase text-warning">
              {hit.source}
              {hit.category ? ` · ${hit.category}` : ""}
            </div>
            <div className="truncate font-mono text-foreground">
              {hit.ip ??
                hit.hash ??
                JSON.stringify(hit.details ?? {}).slice(0, 80)}
            </div>
          </div>
          {hit.score !== null && hit.score !== undefined ? (
            <div className="font-mono text-[11px] text-warning">
              score {hit.score}
            </div>
          ) : null}
        </li>
      ))}
    </ul>
  );
}
