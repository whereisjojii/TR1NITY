import type { FPLayerHit } from "../lib/types";
import { cn } from "../lib/utils";

interface FPLayerBadgeProps {
  layers: FPLayerHit[];
}

const LAYER_LABEL: Record<FPLayerHit["layer"], string> = {
  L1: "Whitelist",
  L2: "Classifier",
  L3: "Suppression",
  analyst: "Analyst",
};

const LAYER_TONE: Record<FPLayerHit["layer"], string> = {
  L1: "border-amber-700/60 bg-amber-900/30 text-amber-200",
  L2: "border-sky-700/60 bg-sky-900/30 text-sky-200",
  L3: "border-violet-700/60 bg-violet-900/30 text-violet-200",
  analyst: "border-emerald-700/60 bg-emerald-900/30 text-emerald-200",
};

export function FPLayerBadge({ layers }: FPLayerBadgeProps): JSX.Element {
  if (!layers || layers.length === 0) {
    return (
      <span className="text-xs text-muted-foreground">
        No FP layer fired — using analyst feedback only.
      </span>
    );
  }

  return (
    <ul data-testid="fp-layers" className="flex flex-wrap gap-1.5">
      {layers.map((layer) => (
        <li
          key={`${layer.layer}-${JSON.stringify(layer.detail)}`}
          className={cn(
            "rounded border px-2 py-1 font-mono text-[11px]",
            LAYER_TONE[layer.layer],
          )}
          title={JSON.stringify(layer.detail)}
        >
          <span className="uppercase">{LAYER_LABEL[layer.layer]}</span>{" "}
          <span className="opacity-80">{layer.score.toFixed(2)}</span>
        </li>
      ))}
    </ul>
  );
}
