import { useQuery } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { getRunbook } from "../lib/api";

interface RunbookPanelProps {
  techniqueId: string;
}

export function RunbookPanel({ techniqueId }: RunbookPanelProps): JSX.Element {
  const query = useQuery({
    queryKey: ["runbook", techniqueId],
    queryFn: () => getRunbook(techniqueId),
    enabled: !!techniqueId,
  });

  if (query.isLoading) {
    return (
      <div className="text-sm text-muted-foreground">Loading runbook…</div>
    );
  }

  if (query.isError || !query.data) {
    return (
      <div className="text-sm text-muted-foreground">
        No runbook is bundled for technique{" "}
        <code className="rounded bg-muted px-1 font-mono text-[11px]">
          {techniqueId}
        </code>
        .
      </div>
    );
  }

  const rb = query.data;
  return (
    <div data-testid="runbook-panel" className="space-y-3">
      <header className="flex flex-wrap items-baseline justify-between gap-2 border-b border-border pb-2">
        <div>
          <h3 className="text-sm font-semibold text-foreground">{rb.title}</h3>
          <div className="mt-0.5 text-[11px] text-muted-foreground">
            <span className="font-mono">{rb.technique_id}</span>
            {rb.tactic_id ? <span> · tactic {rb.tactic_id}</span> : null}
            <span> · severity {rb.severity}</span>
          </div>
        </div>
      </header>
      <article className="prose prose-invert max-w-none text-sm leading-relaxed text-foreground prose-headings:text-foreground prose-strong:text-foreground prose-a:text-accent prose-code:rounded prose-code:bg-muted prose-code:px-1 prose-code:py-0.5 prose-pre:rounded prose-pre:bg-muted/60">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{rb.body}</ReactMarkdown>
      </article>
      {rb.references.length > 0 ? (
        <footer className="border-t border-border pt-2">
          <h4 className="mb-1 text-[11px] uppercase tracking-wider text-muted-foreground">
            References
          </h4>
          <ul className="space-y-1">
            {rb.references.map((url) => (
              <li key={url}>
                <a
                  className="inline-flex items-center gap-1 text-xs text-accent hover:underline"
                  href={url}
                  rel="noreferrer noopener"
                  target="_blank"
                >
                  <ExternalLink size={11} />
                  {url}
                </a>
              </li>
            ))}
          </ul>
        </footer>
      ) : null}
    </div>
  );
}
