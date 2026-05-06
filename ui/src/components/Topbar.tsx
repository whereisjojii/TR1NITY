import { RefreshCcw } from "lucide-react";
import type { ReactNode } from "react";

interface Props {
  title: string;
  subtitle?: ReactNode;
  onRefresh?: () => void;
  refreshing?: boolean;
  right?: ReactNode;
}

export function Topbar({
  title,
  subtitle,
  onRefresh,
  refreshing,
  right,
}: Props): JSX.Element {
  return (
    <header className="flex h-14 items-center gap-4 border-b border-border bg-card-bg px-5">
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-semibold text-foreground">
          {title}
        </div>
        {subtitle ? (
          <div className="truncate text-xs text-muted-foreground">
            {subtitle}
          </div>
        ) : null}
      </div>
      {right}
      {onRefresh ? (
        <button
          type="button"
          onClick={onRefresh}
          className="btn"
          disabled={!!refreshing}
          aria-label="Refresh data"
        >
          <RefreshCcw
            size={14}
            className={refreshing ? "animate-spin" : undefined}
          />
          <span className="hidden md:inline">
            {refreshing ? "Refreshing…" : "Refresh"}
          </span>
          <span className="kbd hidden md:inline">r</span>
        </button>
      ) : null}
    </header>
  );
}
