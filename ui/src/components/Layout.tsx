import { Activity, Layers, ListTodo, Notebook, Target } from "lucide-react";
import type { ReactNode } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useIncidentsLive } from "../hooks/useIncidentsLive";
import { useVimShortcuts } from "../hooks/useVimShortcuts";
import { cn } from "../lib/utils";

const NAV: { to: string; label: string; icon: typeof Activity; key: string }[] =
  [
    { to: "/queue", label: "Queue", icon: ListTodo, key: "1" },
    { to: "/heatmap", label: "ATT&CK", icon: Target, key: "2" },
    { to: "/cases", label: "Cases", icon: Notebook, key: "3" },
    { to: "/help", label: "Help", icon: Layers, key: "?" },
  ];

export function Layout({ children }: { children: ReactNode }): JSX.Element {
  const navigate = useNavigate();
  const live = useIncidentsLive();

  useVimShortcuts([
    {
      key: "1",
      description: "Go to queue",
      handler: () => navigate("/queue"),
    },
    {
      key: "2",
      description: "Go to ATT&CK heatmap",
      handler: () => navigate("/heatmap"),
    },
    {
      key: "3",
      description: "Go to cases",
      handler: () => navigate("/cases"),
    },
    {
      key: "?",
      shift: true,
      description: "Help",
      handler: () => navigate("/help"),
    },
  ]);

  return (
    <div className="flex h-full">
      <aside className="flex w-56 flex-col border-r border-border bg-card-bg">
        <div className="flex h-14 items-center gap-2 border-b border-border px-4">
          <span className="font-mono text-base font-bold text-accent">TR</span>
          <span className="font-mono text-base font-bold tracking-tight text-foreground">
            1NITY
          </span>
          <span className="ml-auto text-[10px] uppercase tracking-wider text-muted-foreground">
            Cockpit
          </span>
        </div>
        <nav className="flex-1 space-y-1 px-2 py-3">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                cn(
                  "flex items-center justify-between rounded px-3 py-2 text-sm",
                  "hover:bg-muted",
                  isActive && "bg-muted text-accent",
                )
              }
            >
              <span className="flex items-center gap-2">
                <item.icon size={16} />
                {item.label}
              </span>
              <span className="kbd">{item.key}</span>
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-border px-4 py-3 text-[11px] text-muted-foreground">
          <div className="flex items-center gap-2">
            <Activity size={12} />
            <span>Live: {live.status}</span>
          </div>
          <div className="mt-1 font-mono text-[10px]">v0.4.0 · Phase 3</div>
        </div>
      </aside>
      <main className="flex h-full min-w-0 flex-1 flex-col overflow-hidden">
        {children}
      </main>
    </div>
  );
}
