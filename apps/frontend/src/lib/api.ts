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

export type CapabilityContract = {
  capability_id: string;
  capability_type:
    | "reasoning"
    | "coding"
    | "frontend_generation"
    | "backend_generation"
    | "debugging"
    | "repair"
    | "analysis"
    | "summarization"
    | "architecture"
    | "documentation";
  reasoning_level: "low" | "medium" | "high" | "extreme";
  coding_level: "none" | "low" | "medium" | "high" | "expert";
  speed_priority: "fast" | "balanced" | "maximum_quality";
  cost_priority: "low_cost" | "balanced" | "premium_allowed";
  context_size: number;
  provider_constraints: string[];
  requires_human_approval: boolean;
  fallback_allowed: boolean;
  execution_scope: string;
  requested_by: "ceo" | "cerebro" | "user" | "seo" | "system";
  timestamp: string;
};

export type ProviderProfile = {
  provider_id: string;
  provider_name: string;
  supported_capabilities: CapabilityContract["capability_type"][];
  reasoning_strength: CapabilityContract["reasoning_level"];
  coding_strength: CapabilityContract["coding_level"];
  speed_profile: CapabilityContract["speed_priority"];
  cost_profile: CapabilityContract["cost_priority"];
  context_capacity: number;
  availability_status: string;
  fallback_priority: number;
  premium_provider: boolean;
  local_provider: boolean;
  enabled: boolean;
  notes: string;
};

export type ProviderRoutingDecision = {
  selected_provider: ProviderProfile | null;
  fallback_provider: ProviderProfile | null;
  reason: string;
  confidence: number;
  estimated_cost_profile: CapabilityContract["cost_priority"] | null;
  estimated_quality_profile: CapabilityContract["reasoning_level"] | null;
  compatible_providers: ProviderProfile[];
  scoring: Array<{
    provider_id: string;
    provider_name: string;
    quality_score: number;
    cost_score: number;
    speed_score: number;
    compatibility_score: number;
    reason: string;
  }>;
  fallback_strategy: string;
  external_request_executed: boolean;
};

export type RoutingExecutionPlan = {
  plan_id: string;
  capability_id: string;
  primary_provider: ProviderProfile | null;
  fallback_provider: ProviderProfile | null;
  fallback_tree: ProviderProfile[];
  routing_reason: string;
  estimated_quality: CapabilityContract["reasoning_level"] | null;
  estimated_cost: CapabilityContract["cost_priority"] | null;
  estimated_speed: CapabilityContract["speed_priority"] | null;
  confidence: number;
  execution_mode: "low_cost" | "balanced" | "premium" | "safe_mode" | "experimental";
  approval_required: boolean;
  risk_level: "LOW" | "MEDIUM" | "HIGH";
  provider_scores: ProviderRoutingDecision["scoring"];
  routing_factors: Record<string, string | number | boolean>;
  timeline: Array<{ timestamp: string; event: string; detail: string }>;
  external_request_executed: boolean;
  generated_at: string;
};

export type ExecutionSimulationResult = {
  execution_id: string;
  capability_id: string;
  routing_plan_id: string | null;
  provider_used: ProviderProfile | null;
  primary_provider_attempted: ProviderProfile | null;
  fallback_provider_used: ProviderProfile | null;
  fallback_chain: ProviderProfile[];
  capability_type: CapabilityContract["capability_type"];
  execution_mode: RoutingExecutionPlan["execution_mode"];
  estimated_tokens: number;
  estimated_cost: number;
  estimated_duration: number;
  simulated_quality: CapabilityContract["reasoning_level"] | null;
  generated_summary: string;
  execution_status: "preparing" | "routing" | "executing" | "fallback" | "completed" | "degraded_mode" | "failed";
  fallback_triggered: boolean;
  failure_mode: "none" | "provider_unavailable" | "timeout" | "low_confidence" | "provider_disabled" | "forced_failure";
  estimated_cost_profile: CapabilityContract["cost_priority"] | null;
  outputs: Array<{ kind: string; label: string; summary: string; status: string; source: string }>;
  timeline: Array<{ timestamp: string; event: string; detail: string }>;
  audit_events: Array<{ event_type: string; actor: string; risk: string; timestamp: string }>;
  external_request_executed: boolean;
  generated_at: string;
};

export type RealProviderExecutionResult = {
  execution_id: string;
  provider_used: string | null;
  primary_provider_attempted: string | null;
  fallback_provider_used: string | null;
  capability_type: CapabilityContract["capability_type"];
  task_type: "readme" | "summary" | "architecture_notes" | "documentation";
  execution_state:
    | "provider_connecting"
    | "provider_ready"
    | "executing_real_ai"
    | "fallback_real_ai"
    | "degraded_mode"
    | "completed"
    | "failed";
  execution_mode: "economic_low_cost" | "low_cost_safe" | "safe_mode" | "controlled_real_ai";
  estimated_tokens: number;
  estimated_cost: number;
  estimated_duration: number;
  max_tokens: number;
  max_execution_time: number;
  max_request_size: number;
  response_received: boolean;
  generated_text_preview: string;
  outputs: Array<{ kind: string; label: string; logical_path: string | null; status: string; summary: string; source: string }>;
  fallback_triggered: boolean;
  safe_mode: boolean;
  rate_limit_remaining: number;
  timeline: Array<{ timestamp: string; event: string; detail: string }>;
  audit_events: Array<{ event_type: string; actor: string; risk: string; timestamp: string }>;
  external_request_executed: boolean;
  generated_at: string;
};

export type AIGatewayProviderHealthState = "active" | "degraded" | "unavailable" | "disabled" | "maintenance";
export type ProviderHealthSnapshot = {
  provider_id: string;
  health_state: AIGatewayProviderHealthState;
  simulated_latency: number;
  simulated_failure_rate: number;
  simulated_cost_tier: CapabilityContract["cost_priority"];
  last_updated: string;
};
export type AIGatewayProviderRecord = {
  provider_id: string;
  provider_name: string;
  enabled: boolean;
  availability: AIGatewayProviderHealthState;
  quality_profile: Record<string, string>;
  cost_profile: CapabilityContract["cost_priority"];
  speed_profile: CapabilityContract["speed_priority"];
  supported_capabilities: CapabilityContract["capability_type"][];
  fallback_priority: number;
  premium_provider: boolean;
  local_provider: boolean;
  provider_role: string;
  operational_priority: number;
  health: ProviderHealthSnapshot;
  notes: string;
};
export type CapabilityRegistryEntry = {
  capability_type: CapabilityContract["capability_type"];
  provider_ids: string[];
  available_provider_ids: string[];
  fallback_provider_ids: string[];
};
export type AIGatewaySnapshot = {
  gateway_status: "active" | "degraded";
  economic_provider_id: string | null;
  premium_fallback_provider_ids: string[];
  providers: AIGatewayProviderRecord[];
  capabilities: CapabilityRegistryEntry[];
  health: ProviderHealthSnapshot[];
  fallback_tree: Record<string, string[]>;
  execution_profiles: Array<{ execution_mode: string; quality_bias: string; cost_bias: string; speed_bias: string; fallback_policy: string }>;
  timeline: Array<{ timestamp: string; event: string; detail: string }>;
  external_request_executed: boolean;
  generated_at: string;
};

export type ProviderConnectorState = "configured" | "missing_credentials" | "invalid_credentials" | "ready" | "disabled" | "unavailable";
export type ProviderConnectorRecord = {
  provider_id: string;
  provider_name: string;
  connector_state: ProviderConnectorState;
  credential_state: "not_required" | "configured" | "missing" | "invalid";
  credential_configured: boolean;
  credential_required: boolean;
  credential_env_var: string | null;
  enabled: boolean;
  safe_initialization: boolean;
  supports_real_connection: boolean;
  local_provider: boolean;
  supported_capabilities: CapabilityContract["capability_type"][];
  reasoning_strength: CapabilityContract["reasoning_level"];
  coding_strength: CapabilityContract["coding_level"];
  cost_profile: CapabilityContract["cost_priority"];
  speed_profile: CapabilityContract["speed_priority"];
  fallback_priority: number;
  compatibility_ready: boolean;
  status_reason: string;
  health: {
    provider_id: string;
    connector_state: ProviderConnectorState;
    credential_state: "not_required" | "configured" | "missing" | "invalid";
    simulated_latency: number;
    simulated_failure_rate: number;
    last_checked: string;
  };
  secrets_exposed: boolean;
};
export type ProviderConnectorSnapshot = {
  connector_layer_status: "ready" | "attention_required";
  providers: ProviderConnectorRecord[];
  configured_provider_ids: string[];
  missing_provider_ids: string[];
  ready_provider_ids: string[];
  fallback_ready: boolean;
  timeline: Array<{ timestamp: string; event: string; detail: string }>;
  external_request_executed: boolean;
  generated_at: string;
};

export type OperationalLoopStatus = {
  status: string;
  build_loop: {
    manager: string;
    available_states: string[];
    latest_build: Record<string, unknown> | null;
    safe_workspace_root: string;
    external_commands_enabled: boolean;
    generated_at: string;
  };
  validation_loop: Record<string, unknown> | null;
  correction_loop: Record<string, unknown> | null;
  retry_policy: Record<string, unknown> | null;
  delivery_package: Record<string, unknown> | null;
  external_commands_enabled: boolean;
};

export type EcosystemOrchestrationStatus = {
  status: string;
  mode: "mock_only" | string;
  contracts: Array<Record<string, unknown>>;
  latest_message: Record<string, unknown> | null;
  hermes_bridge: Record<string, unknown>;
  cerebro_bridge: Record<string, unknown>;
  orchestration_latest: Record<string, unknown> | null;
  real_hermes_connection: boolean;
  real_cerebro_connection: boolean;
  audit_events: Array<{ event_type: string; actor: string; risk: string; timestamp: string }>;
  generated_at: string;
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
