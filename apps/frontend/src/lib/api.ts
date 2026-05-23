export const API_URL = import.meta.env.VITE_FORJA_API_URL ?? "https://forja-core.onrender.com";

export type HealthResponse = {
  status: string;
  service: string;
  version: string;
  environment: string;
  production_ready: boolean;
  modules: Record<string, string>;
  database?: {
    status?: string;
    enabled?: boolean;
    reason?: string;
  };
  security_warnings?: string[];
};

export type RuntimeStatus = {
  status: string;
  runtime_loop: string;
  busy_loop: boolean;
  environment: string;
  zero_write_policy: boolean;
  human_in_the_loop: boolean;
  ai_pipeline: string;
  database?: {
    status?: string;
    enabled?: boolean;
    reason?: string;
  };
  security_warnings: string[];
  providers: Array<{ id: string; kind: string; status: string; reason: string; timeout_ms?: number; retry_limit?: number }>;
  audit_events: number;
  notes: string[];
};

export type CreatorSender = "user" | "cerebro" | "seo" | "system";
export type CreatorDecision = "approve" | "reject" | "hold";
export type CreatorOutputType =
  | "proposed_app_structure"
  | "api_blueprint"
  | "module_plan"
  | "workflow_plan"
  | "document_blueprint"
  | "integration_plan"
  | "blocked_action_report"
  | "execution_summary";

export type CreatorOutput = {
  id: string;
  request_id: string;
  sender: CreatorSender;
  output_type: CreatorOutputType;
  kind: string;
  name: string;
  title: string;
  status: string;
  mode: "metadata_only_output";
  summary: string;
  produced: string[];
  not_produced: string[];
  blocked: string[];
  content: Record<string, unknown>;
  downloadable: boolean;
  created_at: string;
};

export type CreatorCommand = {
  id: string;
  timestamp: string;
  sender: CreatorSender;
  reply_to_sender: CreatorSender;
  command: string;
  details: string;
  request_type: "app" | "api" | "module" | "workflow" | "document" | "integration";
  status: string;
  response: string;
  plan: string[];
  pipeline: Array<{ status: string; label: string; detail: string }>;
  governance: {
    risk_level: string;
    blocked_reason: string | null;
    required_permissions: string[];
    provider_status: string;
    approval_status: string;
  };
  timeline: Array<{ timestamp: string; event: string; detail: string }>;
  execution_logs: Array<{ timestamp: string; level: string; message: string }>;
  outputs: CreatorOutput[];
};

export type CreatorConsoleState = {
  mode: string;
  provider_state: string;
  command_statuses: string[];
  commands: CreatorCommand[];
  outputs: CreatorOutput[];
  audit_stream: Array<Record<string, unknown>>;
};

export async function fetchJson<T>(path: string, token?: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export async function postJson<T>(path: string, body: unknown, token?: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}
