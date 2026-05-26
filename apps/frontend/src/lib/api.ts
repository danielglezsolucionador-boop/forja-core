export const API_URL = import.meta.env.VITE_FORJA_API_URL ?? "https://forja-core.onrender.com";
const REQUEST_TIMEOUT_MS = 15000;

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
export type IntentSender = "ceo" | "cerebro" | "user" | "seo" | "system";
export type IntentInterpretation = {
  sender: IntentSender;
  recipient: "forja";
  request_type: "app" | "api" | "dashboard" | "module" | "workflow" | "integration" | "repair" | "upgrade" | "analysis" | "document";
  domain: "inventario" | "ventas" | "clientes" | "financiero" | "contable" | "tributario" | "WhatsApp" | "ecommerce" | "logistica" | "RRHH" | "general";
  objective: string;
  suggested_modules: string[];
  risk_level: "LOW" | "MEDIUM" | "HIGH";
  requires_approval: boolean;
  response_target: "ceo" | "cerebro" | "seo" | "system";
  raw_input: string;
  normalized_input: string;
  confidence: number;
  timestamp: string;
};
export type ProjectBlueprint = {
  blueprint_id: string;
  source_request_id: string;
  sender: IntentSender;
  response_target: "ceo" | "cerebro" | "seo" | "system";
  project_name: string;
  project_type: IntentInterpretation["request_type"];
  domain: IntentInterpretation["domain"];
  objective: string;
  stack_recommendation: string[];
  suggested_structure: string[];
  modules: string[];
  screens: string[];
  endpoints: Array<{ method: string; path: string; purpose: string }>;
  data_model: Array<{ name: string; fields: string[]; purpose: string }>;
  risks: Array<{ level: IntentInterpretation["risk_level"]; title: string; mitigation: string }>;
  risk_level: IntentInterpretation["risk_level"];
  approval_required: boolean;
  construction_steps: string[];
  validation_criteria: string[];
  created_at: string;
};
export type ProjectWorkspace = {
  workspace_id: string;
  request_id: string;
  blueprint_id: string;
  sender: IntentSender;
  response_target: "ceo" | "cerebro" | "seo" | "system";
  project_name: string;
  project_type: IntentInterpretation["request_type"];
  domain: IntentInterpretation["domain"];
  risk_level: IntentInterpretation["risk_level"];
  approval_required: boolean;
  approval_status: "not_required" | "pending";
  status: "created" | "blocked";
  logical_path: string;
  directories: string[];
  files: string[];
  workspace_isolated: boolean;
  complex_generation_allowed: boolean;
  timeline: Array<{ timestamp: string; event: string; detail: string }>;
  created_at: string;
};
export type ProjectGeneration = {
  generation_id: string;
  request_id: string;
  workspace_id: string;
  blueprint_id: string;
  project_name: string;
  project_type: string;
  risk_level: string;
  status: "completed" | "blocked" | "duplicate_blocked";
  reason: string | null;
  approval_status: "not_required" | "approved" | "required" | "blocked";
  logical_path: string;
  generated_files: string[];
  generated_directories: string[];
  modules_created: string[];
  dangerous_files_blocked: boolean;
  workspace_isolated: boolean;
  timeline: Array<{ timestamp: string; event: string; detail: string }>;
  created_at: string;
};
export type GovernedExecution = {
  execution_id: string;
  request_id: string;
  idempotency_key: string;
  sender: IntentSender;
  recipient: "forja";
  response_target: string;
  raw_input: string;
  normalized_input: string;
  request_type: string;
  domain: string;
  project_name: string | null;
  risk_level: IntentInterpretation["risk_level"] | null;
  state:
    | "pending"
    | "interpreted"
    | "blueprint_ready"
    | "awaiting_approval"
    | "approved"
    | "generating"
    | "completed"
    | "blocked"
    | "failed"
    | "duplicate_blocked";
  reason: string | null;
  approval_required: boolean;
  approval_status: "not_required" | "requested" | "approved" | "rejected" | "blocked";
  duplicate_of: string | null;
  workspace_isolated: boolean;
  parallel_execution_blocked: boolean;
  governance_bypass_blocked: boolean;
  interpretation: IntentInterpretation | null;
  blueprint: ProjectBlueprint | null;
  workspace: ProjectWorkspace | null;
  generation: ProjectGeneration | null;
  outputs: Array<{ kind: string; label: string; logical_path: string; status: string; source: string }>;
  timeline: Array<{ timestamp: string; event: string; detail: string }>;
  audit_events: Array<{ event_type: string; actor: string; risk: string; timestamp: string }>;
  created_at: string;
  updated_at: string;
};
export type CapabilityStatus = "pending" | "approved" | "rejected" | "unavailable";
export type CapabilityKind =
  | "more_context"
  | "better_coding"
  | "ocr"
  | "image_generation"
  | "video_generation"
  | "voice"
  | "strong_reasoning"
  | "lower_cost"
  | "higher_speed"
  | "mass_processing"
  | "other";
export type CapabilityRequest = {
  id: string;
  timestamp: string;
  sender: CreatorSender;
  reply_to: "ceo" | "cerebro" | "seo" | "system";
  related_command_id: string | null;
  objective: string;
  explanation: string;
  status: CapabilityStatus;
  response: string;
  requirements: Array<{
    id: string;
    kind: CapabilityKind;
    characteristics: string[];
    reason: string;
    priority: "low" | "medium" | "high" | "critical";
  }>;
  governance: Record<string, unknown>;
  timeline: Array<{ timestamp: string; event: string; detail: string }>;
  approved_metadata: Record<string, unknown> | null;
};
export type CapabilityConsumption = {
  id: string;
  capability_request_id: string;
  timestamp: string;
  sender: CreatorSender;
  reply_to: "ceo" | "cerebro" | "seo" | "system";
  task: string;
  status: "blocked" | "running" | "completed" | "failed";
  response: string;
  failure_reason: string | null;
  manual_approval: boolean;
  execution_mode: "safe_metadata";
  timeout_ms: number;
  provider_status: "not_bound" | "approved_metadata_only" | "provider_response_metadata_registered" | "failed_metadata_registered";
  external_api_called: boolean;
  failure_classification: string;
  risk_score: number;
  governance_escalation: string;
  usage_metadata: Record<string, unknown>;
  cost_metadata: Record<string, unknown>;
  provider_response_metadata: Record<string, unknown>;
  result_metadata: Record<string, unknown>;
  replay_metadata: Record<string, unknown>;
  governance: Record<string, unknown>;
  timeline: Array<{ timestamp: string; event: string; detail: string }>;
};

export type CapabilityRuntimeMetrics = {
  generated_at: string;
  mode: string;
  total_consumptions: number;
  status_counts: Record<string, number>;
  provider_status_counts: Record<string, number>;
  failure_classification_counts: Record<string, number>;
  governance_escalations: Record<string, number>;
  manual_approval: Record<string, number>;
  external_api_calls: number;
  timeouts_prevented: number;
  cost_by_currency: Record<string, number>;
  risk: { average: number; peak: number; scored_records: number };
  controls: Record<string, unknown>;
};

export type CapabilityRuntimeEvent = {
  id: string;
  timestamp: string;
  event_type: string;
  severity: "info" | "warning" | "error";
  capability_request_id: string;
  consumption_id: string;
  sender: CreatorSender;
  reply_to: "ceo" | "cerebro" | "seo" | "system";
  status: string;
  provider_status: string;
  failure_classification: string;
  risk_score: number;
  governance_escalation: string;
  external_api_called: boolean;
  timeout_ms: number;
  replay_key: string;
  detail: string;
};

export type ProviderHealthState = {
  id: string;
  name: string;
  status: string;
  provider_bound: boolean;
  external_provider: string;
  external_api_calls_enabled: boolean;
  external_api_calls: number;
  monitored_consumptions: number;
  blocked_or_failed: number;
  timeouts_prevented: number;
  last_event_at: string | null;
  detail: string;
};
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
  capability_requests: CapabilityRequest[];
  approved_capabilities: CapabilityRequest[];
  capability_consumptions: CapabilityConsumption[];
  capability_runtime_metrics: CapabilityRuntimeMetrics;
  capability_runtime_events: CapabilityRuntimeEvent[];
  provider_health: ProviderHealthState;
  capability_audit_summary: Record<string, unknown>;
  audit_stream: Array<Record<string, unknown>>;
};

export async function fetchJson<T>(path: string, token?: string): Promise<T> {
  return withTimeout(async (signal) => {
    const response = await fetch(`${API_URL}${path}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      signal,
    });
    if (!response.ok) {
      throw new Error(`${response.status} ${response.statusText}`);
    }
    return response.json() as Promise<T>;
  });
}

export async function postJson<T>(path: string, body: unknown, token?: string): Promise<T> {
  return withTimeout(async (signal) => {
    const response = await fetch(`${API_URL}${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(body),
      signal,
    });
    if (!response.ok) {
      throw new Error(`${response.status} ${response.statusText}`);
    }
    return response.json() as Promise<T>;
  });
}

async function withTimeout<T>(operation: (signal: AbortSignal) => Promise<T>): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    return await operation(controller.signal);
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error("Request timed out");
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}
