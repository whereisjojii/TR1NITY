import type {
  Case,
  CaseListResponse,
  CaseStatus,
  FPMarkResponse,
  HeatmapResponse,
  Incident,
  IncidentListResponse,
  IncidentRefreshResponse,
  SimilarResponse,
} from "./types";

const API_ROOT = "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${API_ROOT}${path}`, {
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });
  if (!resp.ok) {
    let detail: unknown = null;
    try {
      detail = await resp.json();
    } catch {
      detail = await resp.text();
    }
    throw new APIError(resp.status, resp.statusText, detail);
  }
  if (resp.status === 204) {
    return undefined as T;
  }
  return resp.json() as Promise<T>;
}

export class APIError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, statusText: string, detail: unknown) {
    super(`API ${status} ${statusText}`);
    this.status = status;
    this.detail = detail;
  }
}

export interface ListIncidentsParams {
  sort_by?: "fp_score" | "severity" | "created_at" | "last_event_at";
  descending?: boolean;
  severity_min?: number;
  sources?: string[];
  technique?: string;
  limit?: number;
  include_persisted?: boolean;
}

export function listIncidents(
  params: ListIncidentsParams = {},
): Promise<IncidentListResponse> {
  const query = new URLSearchParams();
  if (params.sort_by) query.set("sort_by", params.sort_by);
  if (params.descending !== undefined)
    query.set("descending", String(params.descending));
  if (params.severity_min !== undefined)
    query.set("severity_min", String(params.severity_min));
  if (params.technique) query.set("technique", params.technique);
  if (params.limit !== undefined) query.set("limit", String(params.limit));
  if (params.include_persisted !== undefined)
    query.set("include_persisted", String(params.include_persisted));
  if (params.sources && params.sources.length) {
    for (const s of params.sources) query.append("sources", s);
  }
  const qs = query.toString();
  return request<IncidentListResponse>(`/incidents${qs ? `?${qs}` : ""}`);
}

export function getIncident(id: string): Promise<Incident> {
  return request<Incident>(`/incidents/${encodeURIComponent(id)}`);
}

export function markFP(
  id: string,
  payload: { is_fp: boolean; reason?: string; submitted_by?: string },
): Promise<FPMarkResponse> {
  return request<FPMarkResponse>(
    `/incidents/${encodeURIComponent(id)}/mark-fp`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export function refreshIncidents(): Promise<IncidentRefreshResponse> {
  return request<IncidentRefreshResponse>(`/incidents/refresh`, {
    method: "POST",
  });
}

export function similarIncidents(
  id: string,
  limit = 10,
): Promise<SimilarResponse> {
  return request<SimilarResponse>(
    `/incidents/${encodeURIComponent(id)}/similar?limit=${limit}`,
  );
}

export function getHeatmap(severityMin?: number): Promise<HeatmapResponse> {
  const qs = severityMin !== undefined ? `?severity_min=${severityMin}` : "";
  return request<HeatmapResponse>(`/attack/heatmap${qs}`);
}

export function listCases(filter?: {
  status?: CaseStatus;
  assigned_to?: string;
}): Promise<CaseListResponse> {
  const query = new URLSearchParams();
  if (filter?.status) query.set("status", filter.status);
  if (filter?.assigned_to) query.set("assigned_to", filter.assigned_to);
  const qs = query.toString();
  return request<CaseListResponse>(`/cases${qs ? `?${qs}` : ""}`);
}

export function createCase(payload: {
  title: string;
  summary?: string | null;
  severity?: number;
  status?: CaseStatus;
  incident_ids?: string[];
  assigned_to?: string | null;
  tags?: string[];
}): Promise<Case> {
  return request<Case>(`/cases`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateCase(
  caseId: string,
  payload: Partial<{
    title: string;
    summary: string | null;
    severity: number;
    status: CaseStatus;
    incident_ids: string[];
    assigned_to: string | null;
    tags: string[];
  }>,
): Promise<Case> {
  return request<Case>(`/cases/${encodeURIComponent(caseId)}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function addCaseNote(
  caseId: string,
  payload: { body: string; author?: string },
): Promise<Case> {
  return request<Case>(`/cases/${encodeURIComponent(caseId)}/notes`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function deleteCase(caseId: string): Promise<void> {
  return request<void>(`/cases/${encodeURIComponent(caseId)}`, {
    method: "DELETE",
  });
}

export function buildWebSocketUrl(): string {
  if (typeof window === "undefined") return "";
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}/ws/incidents`;
}
