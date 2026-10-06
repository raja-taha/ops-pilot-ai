const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || "change-me-to-a-strong-secret";

export type Scenario = {
  id: string;
  title: string;
  service_name: string;
  severity: string;
  description: string;
  expected_root_cause: string;
};

export type IncidentSummary = {
  id: string;
  title: string;
  service_name: string;
  severity: string;
  status: string;
  summary: string | null;
  root_cause: string | null;
  scenario_id: string | null;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
};

export type Hypothesis = {
  id: string;
  rank: number;
  title: string;
  description: string;
  evidence_score: number;
  confidence: number;
  supporting_evidence: Array<{ type?: string; message?: string }>;
  contradicting_evidence: Array<{ type?: string; message?: string }>;
  critic_notes: string | null;
  is_primary: boolean;
};

export type RemediationAction = {
  id: string;
  action_type: string;
  title: string;
  description: string;
  target_service: string;
  payload: Record<string, unknown>;
  rollback_plan: string;
  risk_level: string;
  status: string;
  requires_approval: boolean;
  decided_by: string | null;
  decision_notes: string | null;
  executed_at: string | null;
  execution_result: Record<string, unknown>;
  created_at: string;
};

export type TimelineEvent = {
  id: string;
  event_time: string;
  source: string;
  kind: string;
  message: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
};

export type AuditLog = {
  id: string;
  actor: string;
  action: string;
  details: Record<string, unknown>;
  created_at: string;
};

export type IncidentDetail = IncidentSummary & {
  alert_payload: Record<string, unknown>;
  report_markdown: string | null;
  agent_trace: { steps?: Array<Record<string, unknown>>; errors?: string[] };
  evidence_bundle: Record<string, unknown>;
  hypotheses: Hypothesis[];
  actions: RemediationAction[];
  timeline: TimelineEvent[];
  audit_logs: AuditLog[];
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}/api/v1${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": API_KEY,
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(body || `Request failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  scenarios: () => request<Scenario[]>("/scenarios"),
  incidents: () => request<IncidentSummary[]>("/incidents"),
  incident: (id: string) => request<IncidentDetail>(`/incidents/${id}`),
  createIncident: (body: {
    scenario_id?: string;
    title?: string;
    service_name?: string;
    severity?: string;
    alert?: Record<string, unknown>;
    auto_investigate?: boolean;
  }) =>
    request<IncidentDetail>("/incidents", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  decide: (
    incidentId: string,
    actionId: string,
    body: { approved: boolean; decided_by?: string; notes?: string }
  ) =>
    request<{ action: RemediationAction; incident_status: string; message: string }>(
      `/incidents/${incidentId}/actions/${actionId}/decision`,
      { method: "POST", body: JSON.stringify(body) }
    ),
  report: (id: string) =>
    request<{ incident_id: string; markdown: string; generated_at: string }>(
      `/incidents/${id}/report`
    ),
};
