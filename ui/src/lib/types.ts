// Mirrors the Pydantic models in services/api. Kept in this single file
// so it's obvious where to add fields when the API surface evolves.

export type EventSource = "wazuh" | "firewall" | "waf" | string;

export interface IncidentMember {
  event_id?: string;
  timestamp: string;
  source: EventSource;
  severity: number;
  source_ip?: string | null;
  destination_ip?: string | null;
  user?: string | null;
  message?: string | null;
  technique_ids?: string[];
  sigma_matches?: string[];
  raw?: Record<string, unknown> | null;
}

export interface IntelHit {
  source: string;
  ip?: string | null;
  hash?: string | null;
  category?: string | null;
  score?: number | null;
  details?: Record<string, unknown> | null;
}

export interface FPFeedback {
  incident_id: string;
  is_fp: boolean;
  reason: string | null;
  source: "analyst" | "whitelist" | "classifier";
  submitted_by: string;
  submitted_at: string;
}

export interface Incident {
  incident_id: string;
  title: string;
  summary?: string | null;
  severity: number;
  status: "open" | "triaging" | "resolved" | "false_positive" | "suppressed";
  grouping_key: string;
  sources: string[];
  technique_ids: string[];
  tactic_ids: string[];
  members: IncidentMember[];
  created_at: string;
  first_event_at: string;
  last_event_at: string;
  member_count: number;
  intel_hits: IntelHit[];
  sigma_matches: string[];
  fp_score?: number | null;
  fp_feedback?: FPFeedback | null;
  similarity_score?: number | null;
}

export interface IncidentListResponse {
  items: Incident[];
  total: number;
  fetched_at: string;
}

export interface FPMarkResponse {
  incident_id: string;
  fp_score: number;
  feedback: FPFeedback;
}

export interface SimilarResponse {
  target_id: string;
  items: Incident[];
  total: number;
  method: string;
  fetched_at: string;
}

export interface HeatmapTechnique {
  id: string;
  count: number;
  tactics: string[];
}

export interface HeatmapTactic {
  id: string;
  count: number;
}

export interface HeatmapResponse {
  techniques: HeatmapTechnique[];
  tactics: HeatmapTactic[];
  total_incidents: number;
  covered_incidents: number;
  fetched_at: string;
}

export type CaseStatus =
  | "open"
  | "investigating"
  | "containment"
  | "resolved"
  | "closed";

export interface CaseNote {
  author: string;
  body: string;
  at: string;
}

export interface Case {
  case_id: string;
  title: string;
  severity: number;
  status: CaseStatus;
  summary?: string | null;
  incident_ids: string[];
  assigned_to?: string | null;
  tags: string[];
  notes: CaseNote[];
  created_at: string;
  updated_at: string;
}

export interface CaseListResponse {
  items: Case[];
  total: number;
  fetched_at: string;
}

export interface IncidentRefreshResponse {
  triggered: boolean;
  incident_count: number;
  sinks: {
    sink: string;
    accepted?: number;
    rejected?: number;
    errors?: string[];
  }[];
}

export type WSMessage =
  | { type: "hello"; service: string; channel: string; ts: string }
  | { type: "snapshot"; ts: string; incidents: Incident[] }
  | { type: "incident.new"; ts: string; incidents: Incident[] }
  | { type: "ping"; ts?: string };
