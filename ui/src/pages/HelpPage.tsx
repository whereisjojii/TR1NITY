import { Topbar } from "../components/Topbar";

const SHORTCUTS: { keys: string; description: string }[] = [
  { keys: "j / k", description: "Move selection down / up in the queue" },
  { keys: "g g", description: "Jump to top of queue" },
  { keys: "G", description: "Jump to bottom of queue" },
  { keys: "o · Enter", description: "Open the selected incident" },
  { keys: "Esc · h", description: "Back to the queue from incident detail" },
  { keys: "1 / 2 / 3", description: "Switch tabs in the incident view" },
  { keys: "f", description: "Mark selected incident as false positive" },
  { keys: "t", description: "Mark selected incident as true positive" },
  { keys: "c", description: "Create a case from the open incident" },
  { keys: "r", description: "Trigger a correlator tick / refresh" },
  {
    keys: "1 / 2 / 3 / ?",
    description: "Navigate sidebar (Queue / ATT&CK / Cases / Help)",
  },
];

export function HelpPage(): JSX.Element {
  return (
    <>
      <Topbar
        title="Cockpit help"
        subtitle="Vim-style shortcuts, escape hatches, and Phase-3 quirks"
      />
      <div className="space-y-6 overflow-auto p-6">
        <section className="card p-4">
          <h2 className="mb-3 text-sm font-semibold text-foreground">
            Keyboard shortcuts
          </h2>
          <table className="w-full text-sm">
            <tbody>
              {SHORTCUTS.map((s) => (
                <tr key={s.keys} className="border-b border-border/60">
                  <td className="w-44 py-2 font-mono text-xs">
                    <span className="kbd">{s.keys}</span>
                  </td>
                  <td className="py-2 text-muted-foreground">
                    {s.description}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
        <section className="card p-4 text-sm text-muted-foreground">
          <h2 className="mb-2 text-sm font-semibold text-foreground">
            What ships in this Phase
          </h2>
          <ul className="list-disc space-y-1 pl-5">
            <li>
              Live alert queue with FP-score sort, severity / source filters,
              and 15s polling fallback when WebSocket is unavailable.
            </li>
            <li>
              Single-pane investigation: ATT&CK chain, threat-intel panel, event
              timeline, raw JSON, similar-incident heuristic.
            </li>
            <li>
              MITRE ATT&CK Navigator-style heatmap grouped by tactic, color
              graded by frequency.
            </li>
            <li>
              Lightweight cases: in-memory create / update / notes / status.
              Phase 4 promotes storage to Postgres.
            </li>
            <li>
              Vim-style key bindings throughout. Type-while-focused works in
              every input — shortcuts only fire when no input is focused.
            </li>
          </ul>
        </section>
      </div>
    </>
  );
}
