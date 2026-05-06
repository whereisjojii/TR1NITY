import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { buildWebSocketUrl } from "../lib/api";
import type { Incident, WSMessage } from "../lib/types";

export type LiveStatus = "connecting" | "open" | "closed" | "error";

interface LiveResult {
  status: LiveStatus;
  lastEvent: WSMessage | null;
  reconnect: () => void;
}

const RECONNECT_DELAY_MS = 3000;

function mergeNewIncidents(
  existing: Incident[] | undefined,
  incoming: Incident[],
): Incident[] {
  const byId = new Map<string, Incident>();
  for (const inc of existing ?? []) {
    byId.set(inc.incident_id, inc);
  }
  for (const inc of incoming) {
    byId.set(inc.incident_id, inc);
  }
  // Sort by FP score ascending — same default the queue uses.
  return Array.from(byId.values()).sort((a, b) => {
    const aScore = a.fp_score ?? 0.5;
    const bScore = b.fp_score ?? 0.5;
    if (aScore !== bScore) return aScore - bScore;
    return a.incident_id.localeCompare(b.incident_id);
  });
}

/**
 * Subscribe to ``/ws/incidents`` and update the React-Query cache for
 * ``["incidents", "list"]`` whenever a snapshot or incident.new arrives.
 */
export function useIncidentsLive(): LiveResult {
  const [status, setStatus] = useState<LiveStatus>("connecting");
  const [lastEvent, setLastEvent] = useState<WSMessage | null>(null);
  const reconnectKey = useRef(0);
  const queryClient = useQueryClient();

  useEffect(() => {
    if (typeof window === "undefined") return undefined;

    let socket: WebSocket | null = null;
    let reconnectTimer: number | null = null;
    let cancelled = false;

    const connect = () => {
      try {
        socket = new WebSocket(buildWebSocketUrl());
      } catch {
        setStatus("error");
        scheduleReconnect();
        return;
      }
      setStatus("connecting");

      socket.addEventListener("open", () => {
        setStatus("open");
      });

      socket.addEventListener("message", (event: MessageEvent<string>) => {
        let parsed: WSMessage | null = null;
        try {
          parsed = JSON.parse(event.data) as WSMessage;
        } catch {
          parsed = null;
        }
        if (!parsed) return;
        setLastEvent(parsed);

        if (parsed.type === "snapshot" || parsed.type === "incident.new") {
          const incoming = parsed.incidents ?? [];
          if (incoming.length > 0) {
            queryClient.setQueriesData<{
              items: Incident[];
              total: number;
              fetched_at: string;
            }>({ queryKey: ["incidents", "list"] }, (existing) => {
              const merged = mergeNewIncidents(existing?.items, incoming);
              return {
                items: merged,
                total: merged.length,
                fetched_at: new Date().toISOString(),
              };
            });
            // Also nudge the heatmap view so analysts see new techniques flow in.
            queryClient.invalidateQueries({ queryKey: ["attack", "heatmap"] });
          }
        }
      });

      socket.addEventListener("close", () => {
        setStatus("closed");
        scheduleReconnect();
      });

      socket.addEventListener("error", () => {
        setStatus("error");
        socket?.close();
      });
    };

    const scheduleReconnect = () => {
      if (cancelled) return;
      if (reconnectTimer !== null) return;
      reconnectTimer = window.setTimeout(() => {
        reconnectTimer = null;
        connect();
      }, RECONNECT_DELAY_MS);
    };

    connect();

    return () => {
      cancelled = true;
      if (reconnectTimer !== null) {
        window.clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      socket?.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reconnectKey.current, queryClient]);

  return {
    status,
    lastEvent,
    reconnect: () => {
      reconnectKey.current += 1;
    },
  };
}
