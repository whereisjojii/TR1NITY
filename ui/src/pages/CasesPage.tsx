import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { useState } from "react";
import { Topbar } from "../components/Topbar";
import {
  addCaseNote,
  createCase,
  deleteCase,
  listCases,
  updateCase,
} from "../lib/api";
import type { CaseStatus } from "../lib/types";
import { formatTimestamp } from "../lib/utils";

const STATUSES: CaseStatus[] = [
  "open",
  "investigating",
  "containment",
  "resolved",
  "closed",
];

export function CasesPage(): JSX.Element {
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<CaseStatus | "">("");
  const [newTitle, setNewTitle] = useState<string>("");
  const [newSeverity, setNewSeverity] = useState<number>(5);
  const [activeCaseId, setActiveCaseId] = useState<string | null>(null);
  const [noteBody, setNoteBody] = useState<string>("");

  const casesQuery = useQuery({
    queryKey: ["cases", "list", statusFilter || null],
    queryFn: () =>
      listCases(
        statusFilter ? { status: statusFilter as CaseStatus } : undefined,
      ),
    refetchInterval: 20_000,
  });

  const createMutation = useMutation({
    mutationFn: () =>
      createCase({
        title: newTitle.trim() || "Untitled case",
        severity: newSeverity,
      }),
    onSuccess: () => {
      setNewTitle("");
      queryClient.invalidateQueries({ queryKey: ["cases"] });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ caseId, status }: { caseId: string; status: CaseStatus }) =>
      updateCase(caseId, { status }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["cases"] }),
  });

  const noteMutation = useMutation({
    mutationFn: ({ caseId, body }: { caseId: string; body: string }) =>
      addCaseNote(caseId, { body }),
    onSuccess: () => {
      setNoteBody("");
      queryClient.invalidateQueries({ queryKey: ["cases"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteCase,
    onSuccess: () => {
      setActiveCaseId(null);
      queryClient.invalidateQueries({ queryKey: ["cases"] });
    },
  });

  const cases = casesQuery.data?.items ?? [];
  const active = cases.find((c) => c.case_id === activeCaseId) ?? null;

  return (
    <>
      <Topbar
        title="Cases"
        subtitle={
          casesQuery.data ? `${casesQuery.data.total} cases` : "Loading…"
        }
        right={
          <select
            className="rounded border border-border bg-muted px-2 py-1 text-xs"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as CaseStatus | "")}
          >
            <option value="">All statuses</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        }
      />
      <div className="grid flex-1 grid-cols-1 gap-4 overflow-auto p-5 lg:grid-cols-[2fr_3fr]">
        <section className="card flex h-full flex-col">
          <header className="border-b border-border p-3">
            <h2 className="text-sm font-semibold text-foreground">New case</h2>
            <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-[1fr_80px_auto]">
              <input
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                placeholder="Case title"
                className="rounded border border-border bg-muted px-2 py-1 text-xs"
              />
              <input
                type="number"
                min={0}
                max={7}
                value={newSeverity}
                onChange={(e) => setNewSeverity(Number(e.target.value))}
                className="rounded border border-border bg-muted px-2 py-1 text-xs"
              />
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => createMutation.mutate()}
                disabled={!newTitle.trim() || createMutation.isPending}
              >
                Create
              </button>
            </div>
          </header>
          <ul className="flex-1 divide-y divide-border overflow-auto">
            {cases.length === 0 ? (
              <li className="p-4 text-xs text-muted-foreground">
                No cases yet — create one above or press{" "}
                <span className="kbd">c</span> from an incident.
              </li>
            ) : (
              cases.map((c) => (
                <li
                  key={c.case_id}
                  onClick={() => setActiveCaseId(c.case_id)}
                  onKeyDown={(e) =>
                    e.key === "Enter" ? setActiveCaseId(c.case_id) : undefined
                  }
                  role="button"
                  tabIndex={0}
                  className={`cursor-pointer px-3 py-2 text-sm ${
                    activeCaseId === c.case_id
                      ? "bg-muted/60"
                      : "hover:bg-muted/30"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="truncate font-medium text-foreground">
                      {c.title}
                    </span>
                    <span className="ml-2 rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] uppercase text-muted-foreground">
                      {c.status}
                    </span>
                  </div>
                  <div className="mt-0.5 truncate text-[11px] text-muted-foreground">
                    sev {c.severity} · {c.incident_ids.length} incidents ·
                    updated {formatTimestamp(c.updated_at)}
                  </div>
                </li>
              ))
            )}
          </ul>
        </section>
        <section className="card flex h-full flex-col">
          {active ? (
            <>
              <header className="flex items-start justify-between border-b border-border p-3">
                <div className="min-w-0">
                  <div className="truncate text-sm font-semibold text-foreground">
                    {active.title}
                  </div>
                  <div className="text-[11px] text-muted-foreground">
                    {active.case_id} · created{" "}
                    {formatTimestamp(active.created_at)}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <select
                    className="rounded border border-border bg-muted px-2 py-1 text-xs"
                    value={active.status}
                    onChange={(e) =>
                      updateMutation.mutate({
                        caseId: active.case_id,
                        status: e.target.value as CaseStatus,
                      })
                    }
                  >
                    {STATUSES.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    className="btn btn-danger"
                    onClick={() => deleteMutation.mutate(active.case_id)}
                    disabled={deleteMutation.isPending}
                  >
                    <Trash2 size={14} /> delete
                  </button>
                </div>
              </header>
              <div className="flex-1 overflow-auto p-3">
                <h3 className="mb-2 text-xs uppercase tracking-wider text-muted-foreground">
                  Linked incidents
                </h3>
                {active.incident_ids.length > 0 ? (
                  <ul className="mb-4 space-y-1">
                    {active.incident_ids.map((id) => (
                      <li
                        key={id}
                        className="rounded border border-border bg-muted/40 px-2 py-1 font-mono text-[11px]"
                      >
                        {id}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <div className="mb-4 text-xs text-muted-foreground">
                    No incidents linked.
                  </div>
                )}
                <h3 className="mb-2 text-xs uppercase tracking-wider text-muted-foreground">
                  Notes
                </h3>
                {active.notes.length > 0 ? (
                  <ul className="mb-3 space-y-2">
                    {active.notes.map((n, i) => (
                      <li
                        key={i}
                        className="rounded border border-border bg-muted/40 p-2"
                      >
                        <div className="flex items-center justify-between text-[10px] text-muted-foreground">
                          <span>{n.author}</span>
                          <span>{formatTimestamp(n.at)}</span>
                        </div>
                        <p className="mt-1 whitespace-pre-wrap text-xs text-foreground">
                          {n.body}
                        </p>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <div className="mb-3 text-xs text-muted-foreground">
                    No notes yet.
                  </div>
                )}
                <textarea
                  value={noteBody}
                  onChange={(e) => setNoteBody(e.target.value)}
                  placeholder="Add a note…"
                  rows={3}
                  className="w-full rounded border border-border bg-muted px-2 py-1 text-xs"
                />
                <div className="mt-2 flex justify-end">
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={!noteBody.trim() || noteMutation.isPending}
                    onClick={() =>
                      noteMutation.mutate({
                        caseId: active.case_id,
                        body: noteBody,
                      })
                    }
                  >
                    Add note
                  </button>
                </div>
              </div>
            </>
          ) : (
            <div className="flex h-full items-center justify-center p-4 text-sm text-muted-foreground">
              Select a case to view its details.
            </div>
          )}
        </section>
      </div>
    </>
  );
}
