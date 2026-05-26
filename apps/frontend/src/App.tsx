import { useEffect, useMemo, useRef, useState } from "react";
import {
  API_URL,
  CapabilityConsumption,
  CapabilityKind,
  CapabilityRequest,
  CreatorCommand,
  CreatorConsoleState,
  CreatorDecision,
  CreatorOutput,
  CreatorSender,
  fetchJson,
  GovernedExecution,
  HealthResponse,
  IntentInterpretation,
  postJson,
  ProjectBlueprint,
  ProjectGeneration,
  ProjectWorkspace,
  RuntimeStatus,
} from "./lib/api";

type LoadState<T> = {
  data: T | null;
  error: string | null;
  loading: boolean;
};

type Tone = "green" | "amber" | "red" | "steel";

type DetailPanel = {
  title: string;
  eyebrow: string;
  tone: Tone;
  body: string;
  rows: Array<[string, string]>;
};

function useLoad<T>(loader: () => Promise<T>, deps: unknown[]): LoadState<T> {
  const [state, setState] = useState<LoadState<T>>({ data: null, error: null, loading: true });

  useEffect(() => {
    let active = true;
    setState((current) => ({ ...current, loading: true, error: null }));
    loader()
      .then((data) => {
        if (active) setState({ data, error: null, loading: false });
      })
      .catch((error: Error) => {
        if (active) setState({ data: null, error: error.message, loading: false });
      });
    return () => {
      active = false;
    };
  }, deps);

  return state;
}

function useRuntimeData(refreshKey: number) {
  const health = useLoad<HealthResponse>(() => fetchJson("/health"), [refreshKey]);
  const runtime = useLoad<RuntimeStatus>(() => fetchJson("/runtime/status"), [refreshKey]);
  return { health, runtime };
}

function useCreatorConsole(refreshKey: number) {
  return useLoad<CreatorConsoleState>(() => fetchJson("/creator/console"), [refreshKey]);
}

function toneForStatus(status?: string | boolean): Tone {
  if (status === true) return "green";
  if (status === false) return "amber";
  const value = String(status ?? "").toLowerCase();
  if (["ok", "active", "available", "approved", "true", "connection_ok"].includes(value)) return "green";
  if (["degraded", "degraded_by_governance_blocks", "attention_required", "disabled", "pending", "not_started_by_design", "blocked_provider_disabled", "local_queue", "loading"].includes(value)) return "amber";
  if (["error", "failed", "critical", "rejected", "unavailable", "false"].includes(value)) return "red";
  return "steel";
}

function display(value: unknown, fallback = "Not reported") {
  if (value === undefined || value === null || value === "") return fallback;
  return String(value);
}

function contentList(content: Record<string, unknown>, key: string): string[] {
  const value = content[key];
  if (!Array.isArray(value)) return [];
  return value.map((item) => String(item));
}

function StatusBadge({ value, tone }: { value: string | boolean | number; tone?: Tone }) {
  const resolvedTone = tone ?? toneForStatus(typeof value === "number" ? "ok" : value);
  return <span className={`status-badge ${resolvedTone}`}>{String(value).replace(/_/g, " ")}</span>;
}

function ActionButton({
  children,
  onClick,
  href,
  variant = "primary",
  loading = false,
}: {
  children: React.ReactNode;
  onClick?: () => void;
  href?: string;
  variant?: "primary" | "ghost";
  loading?: boolean;
}) {
  const className = `forge-button ${variant}${loading ? " loading" : ""}`;
  if (href) {
    return (
      <a className={className} href={href} target="_blank" rel="noreferrer">
        {children}
      </a>
    );
  }
  return (
    <button className={className} type="button" onClick={onClick} disabled={loading}>
      {loading ? "Working..." : children}
    </button>
  );
}

function LoadingBars() {
  return (
    <div className="loading-bars" aria-label="Loading">
      <span />
      <span />
      <span />
    </div>
  );
}

function ForgeCard({
  eyebrow,
  title,
  value,
  tone,
  actionLabel,
  onAction,
  children,
}: {
  eyebrow: string;
  title: string;
  value: string | number | boolean;
  tone?: Tone;
  actionLabel?: string;
  onAction?: () => void;
  children?: React.ReactNode;
}) {
  return (
    <section className="forge-card">
      <div className="card-topline">
        <span>{eyebrow}</span>
        <StatusBadge value={value} tone={tone} />
      </div>
      <h3>{title}</h3>
      {children ? <div className="card-body">{children}</div> : null}
      {actionLabel && onAction ? (
        <div className="card-actions">
          <ActionButton variant="ghost" onClick={onAction}>
            {actionLabel}
          </ActionButton>
        </div>
      ) : null}
    </section>
  );
}

function ErrorPanel({ label, error }: { label: string; error: string }) {
  return (
    <section className="error-panel">
      <strong>{label}</strong>
      <span>{error}</span>
    </section>
  );
}

function MiniSelect({ value, onChange }: { value: CreatorSender; onChange: (value: CreatorSender) => void }) {
  return (
    <div className="sender-switch" aria-label="Command sender">
      {(["user", "cerebro", "seo", "system"] as CreatorSender[]).map((sender) => (
        <button key={sender} type="button" className={value === sender ? "active" : ""} onClick={() => onChange(sender)}>
          sender={sender}
        </button>
      ))}
    </div>
  );
}

function CreatorConsole({
  state,
  selected,
  sender,
  command,
  details,
  busy,
  message,
  onSender,
  onCommand,
  onDetails,
  onSubmit,
  onSelect,
  selectedOutput,
  onSelectOutput,
  onDownloadOutput,
  capabilityKind,
  capabilityObjective,
  capabilityExplanation,
  selectedCapability,
  selectedConsumption,
  onCapabilityKind,
  onCapabilityObjective,
  onCapabilityExplanation,
  onCapabilitySubmit,
  onSelectCapability,
  onCapabilityDecision,
  onAttachCapabilityMetadata,
  onConsumeCapability,
  onSelectConsumption,
  onRegisterUsage,
  onRegisterCost,
  onRegisterProviderResponse,
  onDecision,
  onExecute,
}: {
  state: LoadState<CreatorConsoleState>;
  selected: CreatorCommand | null;
  sender: CreatorSender;
  command: string;
  details: string;
  busy: boolean;
  message: string | null;
  selectedOutput: CreatorOutput | null;
  capabilityKind: CapabilityKind;
  capabilityObjective: string;
  capabilityExplanation: string;
  selectedCapability: CapabilityRequest | null;
  selectedConsumption: CapabilityConsumption | null;
  onSender: (value: CreatorSender) => void;
  onCommand: (value: string) => void;
  onDetails: (value: string) => void;
  onSubmit: () => void;
  onSelect: (value: CreatorCommand) => void;
  onSelectOutput: (value: CreatorOutput) => void;
  onDownloadOutput: (value: CreatorOutput) => void;
  onCapabilityKind: (value: CapabilityKind) => void;
  onCapabilityObjective: (value: string) => void;
  onCapabilityExplanation: (value: string) => void;
  onCapabilitySubmit: () => void;
  onSelectCapability: (value: CapabilityRequest) => void;
  onCapabilityDecision: (value: "approve" | "reject") => void;
  onAttachCapabilityMetadata: () => void;
  onConsumeCapability: () => void;
  onSelectConsumption: (value: CapabilityConsumption) => void;
  onRegisterUsage: () => void;
  onRegisterCost: () => void;
  onRegisterProviderResponse: () => void;
  onDecision: (value: CreatorDecision) => void;
  onExecute: () => void;
}) {
  const commands = state.data?.commands ?? [];
  const active = selected ?? commands[commands.length - 1] ?? null;
  const pipeline = active?.pipeline ?? (state.data?.command_statuses ?? []).map((status) => ({ status, label: status, detail: "Awaiting command input." }));
  const audit = state.data?.audit_stream ?? [];
  const globalOutputs = state.data?.outputs ?? [];
  const activeOutputs = active?.outputs ?? [];
  const viewerOutput = selectedOutput ?? activeOutputs[activeOutputs.length - 1] ?? globalOutputs[globalOutputs.length - 1] ?? null;
  const proposedStructure = viewerOutput ? contentList(viewerOutput.content, "proposed_structure") : [];
  const capabilities = state.data?.capability_requests ?? [];
  const approvedCapabilities = state.data?.approved_capabilities ?? [];
  const consumptions = state.data?.capability_consumptions ?? [];
  const activeCapability = selectedCapability ?? capabilities[capabilities.length - 1] ?? null;
  const activeConsumption = selectedConsumption ?? consumptions[consumptions.length - 1] ?? null;
  const costAmount = activeConsumption?.cost_metadata?.amount;
  const costCurrency = activeConsumption?.cost_metadata?.currency;
  const runtimeMetrics = state.data?.capability_runtime_metrics;
  const providerHealth = state.data?.provider_health;
  const runtimeEvents = state.data?.capability_runtime_events ?? [];
  const auditSummary = state.data?.capability_audit_summary ?? {};
  const costOverview = runtimeMetrics && Object.keys(runtimeMetrics.cost_by_currency).length
    ? Object.entries(runtimeMetrics.cost_by_currency).map(([currency, amount]) => `${amount} ${currency}`).join(" / ")
    : "not reported";
  const failureEntries = runtimeMetrics ? Object.entries(runtimeMetrics.failure_classification_counts) : [];
  const escalationEntries = runtimeMetrics ? Object.entries(runtimeMetrics.governance_escalations) : [];
  const auditEventCounts = typeof auditSummary.event_counts === "object" && auditSummary.event_counts !== null
    ? Object.entries(auditSummary.event_counts as Record<string, number>)
    : [];
  return (
    <section className="creator-console" id="creator-console">
      <div className="section-heading">
        <span>FORJA Command Console</span>
        <h2>Controlled construction cabin</h2>
      </div>
      <div className="creator-layout">
        <section className="command-console-panel">
          <div className="card-topline">
            <span>Command input</span>
            <StatusBadge value={state.data?.provider_state ?? "checking"} tone="amber" />
          </div>
          <MiniSelect value={sender} onChange={onSender} />
          <input value={command} onChange={(event) => onCommand(event.target.value)} placeholder="Build, inspect, prepare or route a controlled request" />
          <textarea value={details} onChange={(event) => onDetails(event.target.value)} placeholder="Advanced context, constraints, target modules, risk notes" />
          <div className="quick-commands">
            {["Prepare dashboard module", "Route from cerebro", "Inspect governance blockers"].map((item) => (
              <button key={item} type="button" onClick={() => onCommand(item)}>
                {item}
              </button>
            ))}
          </div>
          <ActionButton onClick={onSubmit} loading={busy}>
            Submit controlled command
          </ActionButton>
          {message ? <p className="console-message">{message}</p> : null}
        </section>

        <section className="pipeline-panel">
          <div className="card-topline">
            <span>Request pipeline</span>
            <StatusBadge value={active?.status ?? "idle"} tone={toneForStatus(active?.status ?? "loading")} />
          </div>
          <div className="pipeline-rail">
            {pipeline.map((step) => (
              <div key={`${step.status}-${step.label}`} className={active?.status === step.status ? "current" : ""}>
                <span>{step.status}</span>
                <strong>{step.label}</strong>
                <p>{step.detail}</p>
              </div>
            ))}
          </div>
        </section>
      </div>

      <div className="creator-grid">
        <section className="creator-card">
          <div className="card-topline">
            <span>Multi-agent channels</span>
            <StatusBadge value={active ? `reply=${active.reply_to_sender}` : "waiting"} />
          </div>
          {active ? (
            <div className="classification-strip">
              <span>type={active.request_type}</span>
              <span>risk={active.governance.risk_level}</span>
              <span>approval={active.governance.approval_status}</span>
            </div>
          ) : null}
          <div className="channel-list">
            {commands.length ? commands.slice(-4).reverse().map((item) => (
              <button key={item.id} type="button" onClick={() => onSelect(item)} className={active?.id === item.id ? "active" : ""}>
                <strong>sender={item.sender}</strong>
                <span>{item.command}</span>
                <small>{item.response}</small>
              </button>
            )) : <p>No creator commands yet.</p>}
          </div>
        </section>

        <section className="creator-card">
          <div className="card-topline">
            <span>Governance panel</span>
            <StatusBadge value={active?.governance.risk_level ?? "not assessed"} tone="amber" />
          </div>
          <p>{active?.governance.blocked_reason ?? "No command selected."}</p>
          {active ? (
            <div className="plan-list">
              {active.plan.map((item) => <span key={item}>{item}</span>)}
            </div>
          ) : null}
          <div className="permission-list">
            {(active?.governance.required_permissions ?? ["human_approval", "allow_write=true", "provider_enabled"]).map((permission) => <span key={permission}>{permission}</span>)}
          </div>
        </section>

        <section className="creator-card">
          <div className="card-topline">
            <span>Approval center</span>
            <StatusBadge value="controlled" tone="amber" />
          </div>
          <div className="approval-actions">
            <ActionButton variant="ghost" onClick={() => onDecision("approve")}>approve</ActionButton>
            <ActionButton variant="ghost" onClick={() => onDecision("reject")}>reject</ActionButton>
            <ActionButton variant="ghost" onClick={() => onDecision("hold")}>hold</ActionButton>
            <ActionButton onClick={onExecute}>execute metadata-only</ActionButton>
          </div>
          <p>Execution is metadata-only, audited, and blocked unless human approval is recorded.</p>
        </section>

        <section className="creator-card capability-card">
          <div className="card-topline">
            <span>Requested capabilities</span>
            <StatusBadge value={activeCapability?.status ?? "pending"} tone={toneForStatus(activeCapability?.status ?? "pending")} />
          </div>
          <div className="capability-form">
            <select value={capabilityKind} onChange={(event) => onCapabilityKind(event.target.value as CapabilityKind)} aria-label="Capability kind">
              {(["more_context", "better_coding", "ocr", "image_generation", "video_generation", "voice", "strong_reasoning", "lower_cost", "higher_speed", "mass_processing", "other"] as CapabilityKind[]).map((kind) => (
                <option key={kind} value={kind}>{kind}</option>
              ))}
            </select>
            <input value={capabilityObjective} onChange={(event) => onCapabilityObjective(event.target.value)} placeholder="Capability objective" />
            <textarea value={capabilityExplanation} onChange={(event) => onCapabilityExplanation(event.target.value)} placeholder="Why FORJA needs this capability" />
            <ActionButton onClick={onCapabilitySubmit} loading={busy}>Request capability</ActionButton>
          </div>
          <div className="capability-list">
            {capabilities.length ? capabilities.slice(-4).reverse().map((item) => (
              <button key={item.id} type="button" onClick={() => onSelectCapability(item)} className={activeCapability?.id === item.id ? "active" : ""}>
                <strong>{item.requirements[0]?.kind ?? "capability"}</strong>
                <span>{item.objective}</span>
                <small>reply={item.reply_to}</small>
                <StatusBadge value={item.status} tone={toneForStatus(item.status)} />
              </button>
            )) : <p>No capability requests yet.</p>}
          </div>
          {activeCapability ? (
            <div className="capability-detail">
              <p>{activeCapability.explanation}</p>
              <div className="classification-strip">
                <span>sender={activeCapability.sender}</span>
                <span>reply={activeCapability.reply_to}</span>
                <span>response={activeCapability.response}</span>
              </div>
              <div className="permission-list">
                {(activeCapability.requirements[0]?.characteristics ?? ["technical_need"]).map((item) => <span key={item}>{item}</span>)}
              </div>
              <div className="capability-actions">
                <ActionButton variant="ghost" onClick={() => onCapabilityDecision("approve")}>approve capability</ActionButton>
                <ActionButton variant="ghost" onClick={() => onCapabilityDecision("reject")}>reject capability</ActionButton>
                <ActionButton onClick={onAttachCapabilityMetadata}>attach approved metadata</ActionButton>
              </div>
              <div className="capability-timeline">
                {activeCapability.timeline.slice(-4).map((event) => (
                  <div key={`${event.timestamp}-${event.event}`} className="timeline-row">
                    <strong>{event.event}</strong>
                    <span>{event.detail}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </section>

        <section className="creator-card timeline-card">
          <div className="card-topline">
            <span>Execution timeline</span>
            <StatusBadge value={active ? active.timeline.length : 0} />
          </div>
          {(active?.timeline ?? []).map((event) => (
            <div key={`${event.timestamp}-${event.event}`} className="timeline-row">
              <strong>{event.event}</strong>
              <span>{event.detail}</span>
            </div>
          ))}
          {(active?.execution_logs ?? []).map((event) => (
            <div key={`${event.timestamp}-${event.message}`} className="timeline-row">
              <strong>log.{event.level}</strong>
              <span>{event.message}</span>
            </div>
          ))}
        </section>

        <section className="creator-card consumption-card">
          <div className="card-topline">
            <span>Approved capabilities</span>
            <StatusBadge value={approvedCapabilities.length} tone={approvedCapabilities.length ? "green" : "steel"} />
          </div>
          <div className="approved-capability-list">
            {approvedCapabilities.length ? approvedCapabilities.slice(-4).reverse().map((item) => (
              <button key={item.id} type="button" onClick={() => onSelectCapability(item)} className={activeCapability?.id === item.id ? "active" : ""}>
                <strong>{item.requirements[0]?.kind ?? "capability"}</strong>
                <span>{item.objective}</span>
                <small>reply={item.reply_to}</small>
              </button>
            )) : <p>No approved capabilities ready for consumption.</p>}
          </div>
          <div className="consumption-status">
            <div>
              <span>Active capability</span>
              <strong>{activeCapability?.requirements[0]?.kind ?? "none"}</strong>
            </div>
            <div>
              <span>Consumption status</span>
              <strong>{activeConsumption?.status ?? "not_started"}</strong>
            </div>
            <div>
              <span>Provider status</span>
              <strong>{activeConsumption?.provider_status ?? "not_bound"}</strong>
            </div>
            <div>
              <span>Cost visibility</span>
              <strong>{costAmount ? `${costAmount} ${display(costCurrency, "")}` : "not reported"}</strong>
            </div>
          </div>
          <div className="capability-actions">
            <ActionButton onClick={onConsumeCapability}>consume approved capability</ActionButton>
            <ActionButton variant="ghost" onClick={onRegisterUsage}>register usage</ActionButton>
            <ActionButton variant="ghost" onClick={onRegisterCost}>register cost</ActionButton>
            <ActionButton variant="ghost" onClick={onRegisterProviderResponse}>register provider response metadata</ActionButton>
          </div>
          <div className="consumption-list">
            {consumptions.length ? consumptions.slice(-4).reverse().map((item) => (
              <button key={item.id} type="button" onClick={() => onSelectConsumption(item)} className={activeConsumption?.id === item.id ? "active" : ""}>
                <strong>{item.task}</strong>
                <span>{item.response}</span>
                <StatusBadge value={item.status} tone={toneForStatus(item.status)} />
              </button>
            )) : <p>No capability consumption records yet.</p>}
          </div>
          {activeConsumption ? (
            <div className="usage-timeline">
              <div className="classification-strip">
                <span>manual_approval={String(activeConsumption.manual_approval)}</span>
                <span>external_api_called={String(activeConsumption.external_api_called)}</span>
                <span>reply={activeConsumption.reply_to}</span>
              </div>
              {activeConsumption.failure_reason ? <p>{activeConsumption.failure_reason}</p> : null}
              {activeConsumption.timeline.slice(-5).map((event) => (
                <div key={`${event.timestamp}-${event.event}`} className="timeline-row">
                  <strong>{event.event}</strong>
                  <span>{event.detail}</span>
                </div>
              ))}
            </div>
          ) : null}
        </section>

        <section className="creator-card runtime-observability-card">
          <div className="card-topline">
            <span>Provider runtime dashboard</span>
            <StatusBadge value={providerHealth?.status ?? "not_bound"} tone={toneForStatus(providerHealth?.status ?? "disabled")} />
          </div>
          <div className="runtime-dashboard-grid">
            <div>
              <span>Capability health</span>
              <strong>{runtimeMetrics?.total_consumptions ?? 0} records</strong>
              <small>completed={runtimeMetrics?.status_counts.completed ?? 0} blocked={runtimeMetrics?.status_counts.blocked ?? 0} failed={runtimeMetrics?.status_counts.failed ?? 0}</small>
            </div>
            <div>
              <span>Provider health</span>
              <strong>{providerHealth?.external_provider ?? "not_selected"}</strong>
              <small>bound={String(providerHealth?.provider_bound ?? false)} calls={providerHealth?.external_api_calls ?? 0}</small>
            </div>
            <div>
              <span>Execution analytics</span>
              <strong>risk {runtimeMetrics?.risk.average ?? 0}/{runtimeMetrics?.risk.peak ?? 0}</strong>
              <small>timeouts_prevented={runtimeMetrics?.timeouts_prevented ?? 0}</small>
            </div>
            <div>
              <span>Cost overview</span>
              <strong>{costOverview}</strong>
              <small>hidden_costs=false external_api_calls={runtimeMetrics?.external_api_calls ?? 0}</small>
            </div>
          </div>
          <div className="observability-columns">
            <div>
              <strong>Provider failure viewer</strong>
              {failureEntries.length ? failureEntries.map(([name, count]) => (
                <span key={name}>{name}: {count}</span>
              )) : <span>none</span>}
            </div>
            <div>
              <strong>Governance escalation states</strong>
              {escalationEntries.length ? escalationEntries.map(([name, count]) => (
                <span key={name}>{name}: {count}</span>
              )) : <span>none</span>}
            </div>
            <div>
              <strong>Audit explorer</strong>
              {auditEventCounts.length ? auditEventCounts.slice(-5).map(([name, count]) => (
                <span key={name}>{name}: {count}</span>
              )) : <span>no capability audit events</span>}
            </div>
          </div>
          <div className="runtime-event-stream">
            {runtimeEvents.length ? runtimeEvents.slice(-6).reverse().map((event) => (
              <div key={event.id} className="timeline-row">
                <strong>{event.event_type}</strong>
                <span>{event.severity} - failure={event.failure_classification} - risk={event.risk_score} - replay={event.replay_key}</span>
              </div>
            )) : <p>No runtime events observed yet.</p>}
          </div>
          {activeConsumption ? (
            <div className="replay-metadata-panel">
              <div className="card-topline">
                <span>Execution replay metadata</span>
                <StatusBadge value={activeConsumption.governance_escalation} tone={toneForStatus(activeConsumption.status)} />
              </div>
              <div className="classification-strip">
                <span>replay={String(activeConsumption.replay_metadata.replay_key ?? "pending")}</span>
                <span>timeout_ms={activeConsumption.timeout_ms}</span>
                <span>failure={activeConsumption.failure_classification}</span>
                <span>risk={activeConsumption.risk_score}</span>
              </div>
            </div>
          ) : null}
        </section>

        <section className="creator-card output-manager-card">
          <div className="card-topline">
            <span>Output manager</span>
            <StatusBadge value={activeOutputs.length || globalOutputs.length} />
          </div>
          <div className="output-toolbar">
            <ActionButton variant="ghost" onClick={() => viewerOutput && onSelectOutput(viewerOutput)}>View execution result</ActionButton>
            <ActionButton variant="ghost" onClick={() => viewerOutput && onDownloadOutput(viewerOutput)}>Download metadata</ActionButton>
            <ActionButton variant="ghost" onClick={() => viewerOutput && onSelectOutput(viewerOutput)}>View blocked reason</ActionButton>
          </div>
          <div className="artifact-list">
            {(activeOutputs.length ? activeOutputs : globalOutputs.slice(-5)).map((output) => (
              <button key={output.id} type="button" onClick={() => onSelectOutput(output)} className={viewerOutput?.id === output.id ? "active" : ""}>
                <span>{output.output_type}</span>
                <strong>{output.title}</strong>
                <small>{output.mode}</small>
                <StatusBadge value={output.status} tone={toneForStatus(output.status)} />
              </button>
            ))}
          </div>
          {viewerOutput ? (
            <div className="result-viewer">
              <div className="card-topline">
                <span>Result viewer</span>
                <StatusBadge value={viewerOutput.sender} tone="steel" />
              </div>
              <h3>{viewerOutput.title}</h3>
              <p>{viewerOutput.summary}</p>
              <div className="result-columns">
                <div>
                  <strong>Produced</strong>
                  {(viewerOutput.produced.length ? viewerOutput.produced : ["none"]).map((item) => <span key={item}>{item}</span>)}
                </div>
                <div>
                  <strong>Not produced</strong>
                  {(viewerOutput.not_produced.length ? viewerOutput.not_produced : ["source_code"]).map((item) => <span key={item}>{item}</span>)}
                </div>
                <div>
                  <strong>Governance blocks</strong>
                  {(viewerOutput.blocked.length ? viewerOutput.blocked : ["none"]).map((item) => <span key={item}>{item}</span>)}
                </div>
              </div>
              {proposedStructure.length ? (
                <div className="structure-view">
                  <strong>Proposed structure</strong>
                  {proposedStructure.map((item) => <span key={item}>{item}</span>)}
                </div>
              ) : null}
            </div>
          ) : <p>No artifacts registered yet.</p>}
        </section>

        <section className="creator-card audit-card">
          <div className="card-topline">
            <span>Audit stream</span>
            <StatusBadge value={audit.length} />
          </div>
          {audit.slice(-6).reverse().map((event) => (
            <div key={String(event.id)} className="audit-row">
              <strong>{String(event.event_type ?? "audit.event")}</strong>
              <span>{String(event.actor ?? "system")} - {String(event.risk ?? "low")}</span>
            </div>
          ))}
        </section>
      </div>
    </section>
  );
}

function DetailModal({ panel, onClose }: { panel: DetailPanel; onClose: () => void }) {
  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <section className="detail-modal" role="dialog" aria-modal="true" aria-labelledby="detail-title" onClick={(event) => event.stopPropagation()}>
        <div className="card-topline">
          <span>{panel.eyebrow}</span>
          <StatusBadge value={panel.tone === "green" ? "available" : panel.tone === "amber" ? "controlled" : "attention"} tone={panel.tone} />
        </div>
        <h2 id="detail-title">{panel.title}</h2>
        <p>{panel.body}</p>
        <div className="detail-rows">
          {panel.rows.map(([label, value]) => (
            <div key={label}>
              <span>{label}</span>
              <strong>{value}</strong>
            </div>
          ))}
        </div>
        <div className="modal-actions">
          <ActionButton variant="ghost" onClick={onClose}>
            Close detail
          </ActionButton>
        </div>
      </section>
    </div>
  );
}

function useHashRoute() {
  const [hash, setHash] = useState(() => window.location.hash);

  useEffect(() => {
    const onHashChange = () => setHash(window.location.hash);
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  return hash;
}

function HumanConsolePreview() {
  type HumanVisualState = "IDLE" | "INTERPRETING" | "PLANNING" | "AWAITING_APPROVAL" | "GENERATING" | "VALIDATING" | "COMPLETED" | "BLOCKED" | "FAILED";
  const defaultCommand = "Quiero construir un dashboard ejecutivo para ver ventas, margen, alertas y tareas pendientes por equipo.";
  const [commandText, setCommandText] = useState(defaultCommand);
  const [visualState, setVisualState] = useState<HumanVisualState>("PLANNING");
  const [interpretation, setInterpretation] = useState<IntentInterpretation | null>(null);
  const [interpretationError, setInterpretationError] = useState<string | null>(null);
  const [interpreting, setInterpreting] = useState(false);
  const [blueprint, setBlueprint] = useState<ProjectBlueprint | null>(null);
  const [blueprintError, setBlueprintError] = useState<string | null>(null);
  const [blueprinting, setBlueprinting] = useState(false);
  const [workspace, setWorkspace] = useState<ProjectWorkspace | null>(null);
  const [workspaceError, setWorkspaceError] = useState<string | null>(null);
  const [workspacing, setWorkspacing] = useState(false);
  const [generation, setGeneration] = useState<ProjectGeneration | null>(null);
  const [generationError, setGenerationError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [execution, setExecution] = useState<GovernedExecution | null>(null);
  const [executionError, setExecutionError] = useState<string | null>(null);
  const [executing, setExecuting] = useState(false);
  const executionRequestRef = useRef({ input: "", requestId: "" });
  const [isFocused, setIsFocused] = useState(false);
  const quickActions = [
    ["Crear una app", "creame una app de inventario"],
    ["Diseñar una API", "creame una API para clientes"],
    ["Armar un dashboard", "creame un dashboard financiero"],
    ["Crear workflow", "creame un workflow WhatsApp"],
    ["Integrar sistema", "Quiero integrar mi sistema actual con un servicio externo sin romper seguridad ni trazabilidad."]
  ];
  const states: Array<[HumanVisualState, string, string]> = [
    ["IDLE", "Idle", "FORJA espera una orden humana."],
    ["INTERPRETING", "Interpreting", "La intencion entra al parser real."],
    ["PLANNING", "Planning", "Builder Core prepara blueprint y riesgo."],
    ["AWAITING_APPROVAL", "Awaiting approval", "La ejecucion espera decision humana."],
    ["GENERATING", "Generating", "Workspace y archivos se generan de forma gobernada."],
    ["VALIDATING", "Validating", "FORJA registra outputs, timeline y audit."],
    ["COMPLETED", "Completed", "La ejecucion termino con outputs reales."],
    ["BLOCKED", "Blocked", "Governance bloqueo una accion insegura."],
    ["FAILED", "Failed", "La operacion fallo de forma controlada."]
  ];
  const plan = [
    ["01", "Intent Analysis", "FORJA interpreta la orden, normaliza la entrada y fija el target de respuesta."],
    ["02", "Blueprint", "Builder Core propone stack, modulos, pantallas, endpoints y modelo de datos."],
    ["03", "Risk Evaluation", "Governance clasifica riesgo, approval y restricciones antes de escribir."],
    ["04", "Real Execution", "Workspace, archivos, outputs, timeline y audit quedan bajo control gobernado."]
  ];
  const activeState = states.find(([state]) => state === visualState) ?? states[0];

  const getExecutionRequestId = (input: string) => {
    if (executionRequestRef.current.input !== input) {
      const nonce = `${Date.now().toString(36)}-${Math.random().toString(16).slice(2, 8)}`;
      executionRequestRef.current = { input, requestId: `console-${nonce}` };
    }
    return executionRequestRef.current.requestId;
  };

  const visualStateFromExecution = (record: GovernedExecution): HumanVisualState => {
    if (record.state === "awaiting_approval") return "AWAITING_APPROVAL";
    if (record.state === "approved" || record.state === "generating") return "GENERATING";
    if (record.state === "completed") return "COMPLETED";
    if (record.state === "failed") return "FAILED";
    if (record.state === "blocked" || record.state === "duplicate_blocked") return "BLOCKED";
    if (record.state === "blueprint_ready") return "PLANNING";
    return "INTERPRETING";
  };

  const applyGovernedExecution = (record: GovernedExecution) => {
    setExecution(record);
    setVisualState(visualStateFromExecution(record));
    setExecutionError(null);
    setInterpretation(record.interpretation);
    setBlueprint(record.blueprint);
    setWorkspace(record.workspace);
    setGeneration(record.generation);
    setInterpretationError(null);
    setBlueprintError(null);
    setWorkspaceError(null);
    setGenerationError(null);
  };

  const handleCommandChange = (nextCommand: string) => {
    setCommandText(nextCommand);
    setIsFocused(true);
    setVisualState(nextCommand.trim() ? "INTERPRETING" : "IDLE");
  };

  const handleCommandFocus = () => {
    setIsFocused(true);
    if (commandText.trim()) {
      setVisualState("INTERPRETING");
    }
  };

  useEffect(() => {
    const hasIntent = commandText.trim().length > 0;
    if (!hasIntent) {
      setVisualState("IDLE");
      return;
    }
    if (!isFocused) return;
    setVisualState("INTERPRETING");
    const planningTimer = window.setTimeout(() => setVisualState("PLANNING"), 420);
    return () => {
      window.clearTimeout(planningTimer);
    };
  }, [commandText, isFocused]);

  useEffect(() => {
    const input = commandText.trim();
    if (!input) {
      setInterpretation(null);
      setInterpretationError(null);
      setInterpreting(false);
      setBlueprint(null);
      setBlueprintError(null);
      setBlueprinting(false);
      setWorkspace(null);
      setWorkspaceError(null);
      setWorkspacing(false);
      setGeneration(null);
      setGenerationError(null);
      setGenerating(false);
      setExecution(null);
      setExecutionError(null);
      setExecuting(false);
      return;
    }
    let active = true;
    const sourceRequestId = getExecutionRequestId(input);
    setInterpreting(true);
    setInterpretationError(null);
    setBlueprint(null);
    setBlueprintError(null);
    setBlueprinting(false);
    setWorkspace(null);
    setWorkspaceError(null);
    setWorkspacing(false);
    setGeneration(null);
    setGenerationError(null);
    setGenerating(false);
    setExecution(null);
    setExecutionError(null);
    setExecuting(true);
    const timer = window.setTimeout(() => {
      postJson<GovernedExecution>("/execution/start", { sender: "ceo", recipient: "forja", input, source_request_id: sourceRequestId })
        .then((result) => {
          if (!active) return;
          applyGovernedExecution(result);
        })
        .catch((error: Error) => {
          if (!active) return;
          setExecution(null);
          setExecutionError(error.message);
          setInterpretation(null);
          setInterpretationError(error.message);
          setBlueprint(null);
          setWorkspace(null);
          setGeneration(null);
        })
        .finally(() => {
          if (active) {
            setInterpreting(false);
            setBlueprinting(false);
            setWorkspacing(false);
            setExecuting(false);
          }
        });
    }, 420);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [commandText]);

  useEffect(() => {
    if (execution) {
      setBlueprinting(false);
      return;
    }
    if (!interpretation) {
      setBlueprint(null);
      setBlueprintError(null);
      setBlueprinting(false);
      setWorkspace(null);
      setWorkspaceError(null);
      setWorkspacing(false);
      setGeneration(null);
      setGenerationError(null);
      setGenerating(false);
      return;
    }
    let active = true;
    setBlueprinting(true);
    setBlueprintError(null);
    postJson<ProjectBlueprint>("/blueprint/generate", { interpretation })
      .then((result) => {
        if (!active) return;
        setBlueprint(result);
      })
      .catch((error: Error) => {
        if (!active) return;
        setBlueprint(null);
        setBlueprintError(error.message);
        setWorkspace(null);
        setGeneration(null);
      })
      .finally(() => {
        if (active) {
          setBlueprinting(false);
        }
      });
    return () => {
      active = false;
    };
  }, [interpretation, execution]);

  useEffect(() => {
    if (execution) {
      setWorkspacing(false);
      return;
    }
    if (!blueprint) {
      setWorkspace(null);
      setWorkspaceError(null);
      setWorkspacing(false);
      setGeneration(null);
      setGenerationError(null);
      setGenerating(false);
      return;
    }
    let active = true;
    setWorkspacing(true);
    setWorkspaceError(null);
    const timer = window.setTimeout(() => {
      postJson<ProjectWorkspace>("/workspace/create", { blueprint })
        .then((result) => {
          if (!active) return;
          setWorkspace(result);
        })
        .catch((error: Error) => {
          if (!active) return;
          setWorkspace(null);
          setWorkspaceError(error.message);
          setGeneration(null);
        })
        .finally(() => {
          if (active) {
            setWorkspacing(false);
          }
        });
    }, 420);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [blueprint, execution]);

  useEffect(() => {
    if (execution) {
      setGenerating(false);
      return;
    }
    setGenerating(false);
  }, [execution]);

  const chooseQuickAction = (nextCommand: string) => {
    setCommandText(nextCommand);
    setIsFocused(true);
    setVisualState("INTERPRETING");
    executionRequestRef.current = { input: "", requestId: "" };
    setExecution(null);
    setExecutionError(null);
    setGeneration(null);
    setGenerationError(null);
  };

  const runPrimaryExecutionAction = () => {
    if (!commandText.trim()) {
      setVisualState("IDLE");
      return;
    }
    if (execution?.state === "awaiting_approval") {
      setGenerating(true);
      setVisualState("GENERATING");
      setExecutionError(null);
      postJson<GovernedExecution>(`/execution/${execution.execution_id}/approval`, { decision: "approve", decided_by: "ceo" })
        .then((result) => {
          setVisualState("VALIDATING");
          applyGovernedExecution(result);
        })
        .catch((error: Error) => {
          setVisualState("FAILED");
          setExecutionError(error.message);
          setGenerationError(error.message);
        })
        .finally(() => setGenerating(false));
      return;
    }
    if (execution?.state === "completed") {
      const input = commandText.trim();
      const sourceRequestId = getExecutionRequestId(input);
      setExecuting(true);
      setVisualState("VALIDATING");
      postJson<GovernedExecution>("/execution/start", { sender: "ceo", recipient: "forja", input, source_request_id: sourceRequestId })
        .then((result) => {
          applyGovernedExecution(result);
        })
        .catch((error: Error) => {
          setVisualState("FAILED");
          setExecutionError(error.message);
        })
        .finally(() => setExecuting(false));
    }
  };

  const rejectGovernedExecution = () => {
    if (!execution || execution.state !== "awaiting_approval") return;
    setGenerating(true);
    setVisualState("VALIDATING");
    setExecutionError(null);
    postJson<GovernedExecution>(`/execution/${execution.execution_id}/approval`, { decision: "reject", decided_by: "ceo" })
      .then((result) => {
        applyGovernedExecution(result);
      })
      .catch((error: Error) => {
        setVisualState("FAILED");
        setExecutionError(error.message);
      })
      .finally(() => setGenerating(false));
  };

  const intentType = interpretation?.request_type.toUpperCase() ?? (interpreting ? "READING" : "PENDING");
  const intentDomain = interpretation?.domain.toUpperCase() ?? "GENERAL";
  const executionState = executionError ? "ERROR" : execution?.state.toUpperCase() ?? (executing ? "GOVERNING" : "PENDING");
  const intentRisk = interpretationError ? "ERROR" : execution?.risk_level ?? interpretation?.risk_level ?? "CONTROLLED";
  const intentApproval = execution ? execution.approval_status.toUpperCase() : interpretation ? (interpretation.requires_approval ? "REQUIRED" : "NOT REQUIRED") : "PENDING";
  const intentTarget = interpretation?.response_target.toUpperCase() ?? "CEO";
  const blueprintTitle = blueprint?.project_name ?? (blueprinting ? "Preparando blueprint tecnico." : "FORJA organiza la intencion como una estrategia de construccion.");
  const blueprintObjective = blueprintError
    ? `Blueprint error: ${blueprintError}`
    : blueprint?.objective ?? "Detecta el tipo de sistema, separa decisiones humanas, propone una ruta y mantiene la ejecucion real apagada hasta aprobacion futura.";
  const structurePreview = blueprint?.suggested_structure.slice(0, 4) ?? ["Entrada humana", "Blueprint", "Control", "Salida revisable"];
  const constructionPlan = blueprint?.construction_steps.slice(0, 4).map((step, index) => [
    String(index + 1).padStart(2, "0"),
    index === 0 ? "Alcance" : index === 1 ? "Estructura" : index === 2 ? "Aprobacion" : "Validacion",
    step,
  ]) ?? plan;
  const blueprintModules = blueprint?.modules.slice(0, 4) ?? [];
  const blueprintRisks = blueprint?.risks.slice(0, 2).map((risk) => `${risk.level}: ${risk.title}`) ?? [];
  const blueprintCriteria = blueprint?.validation_criteria.slice(0, 2) ?? [];
  const workspaceState = workspaceError
    ? "BLOCKED"
    : workspace?.status.toUpperCase() ?? (execution?.state === "awaiting_approval" ? "AWAITING_APPROVAL" : workspacing ? "CREATING" : "PENDING");
  const workspacePath = workspace?.logical_path ?? ".forja/workspaces/pending";
  const workspaceDirs = workspace?.directories.slice(0, 6) ?? [];
  const workspaceFiles = workspace?.files ?? [];
  const generationState = generationError
    ? "ERROR"
    : generation?.status.toUpperCase() ?? (generating ? "GENERATING" : execution?.state === "completed" ? "NOT_REQUIRED" : "AWAITING_APPROVAL");
  const generatedFiles = generation?.generated_files.slice(0, 10) ?? [];
  const generatedDirs = generation?.generated_directories.slice(0, 6) ?? [];
  const generatedModules = generation?.modules_created ?? [];
  const executionTimeline = execution?.timeline.slice(-7) ?? [];
  const executionOutputs = execution?.outputs.slice(0, 18) ?? [];
  const executionAudit = execution?.audit_events.slice(-6) ?? [];
  const generatedFileLabels = generatedFiles.map((file) => file.split("/").pop() ?? file);
  const outputLabels = executionOutputs.map((output) => output.label);
  const canApproveExecution = execution?.state === "awaiting_approval" && !generating;
  const canRejectExecution = execution?.state === "awaiting_approval" && !generating;
  const canRetryDuplicate = execution?.state === "completed" && !generating && !executing;
  const primaryActionLabel = canApproveExecution
    ? "Aprobar y construir"
    : canRetryDuplicate
      ? "Reintentar orden"
      : execution?.state === "duplicate_blocked"
        ? "Duplicado bloqueado"
        : execution?.state === "blocked"
          ? "Ejecucion bloqueada"
          : execution?.state === "failed"
            ? "Validacion fallida"
            : executing || interpreting
              ? "Analizando orden"
              : "Esperando approval";
  const operationalSections = [
    {
      title: "Intent Analysis",
      status: interpretation ? "READY" : interpreting ? "INTERPRETING" : "IDLE",
      items: [
        `TYPE: ${intentType}`,
        `DOMAIN: ${intentDomain}`,
        `CONFIDENCE: ${interpretation ? Math.round(interpretation.confidence * 100) : 0}%`,
        `TARGET: ${intentTarget}`,
      ],
    },
    {
      title: "Blueprint",
      status: blueprint ? "READY" : blueprinting ? "PLANNING" : "PENDING",
      items: [
        `PROJECT: ${blueprint?.project_name ?? "pending"}`,
        `MODULES: ${blueprint?.modules.length ?? 0}`,
        `SCREENS: ${blueprint?.screens.length ?? 0}`,
        `ENDPOINTS: ${blueprint?.endpoints.length ?? 0}`,
      ],
    },
    {
      title: "Risk Evaluation",
      status: String(intentRisk),
      items: [
        `RISK: ${intentRisk}`,
        `APPROVAL: ${intentApproval}`,
        `BYPASS: ${execution?.governance_bypass_blocked ? "BLOCKED" : "CONTROLLED"}`,
        `REASON: ${execution?.reason ?? "none"}`,
      ],
    },
    {
      title: "Approval State",
      status: execution?.approval_status.toUpperCase() ?? "PENDING",
      items: [
        `STATE: ${executionState}`,
        `REQUIRED: ${execution?.approval_required ? "YES" : "NO"}`,
        `APPROVE: ${canApproveExecution ? "AVAILABLE" : "LOCKED"}`,
        `REJECT: ${canRejectExecution ? "AVAILABLE" : "LOCKED"}`,
      ],
    },
    {
      title: "Workspace Status",
      status: workspaceState,
      items: [
        `WORKSPACE: ${workspaceState}`,
        `PATH: ${workspacePath}`,
        `FOLDERS: ${workspaceDirs.length || workspace?.directories.length || 0}`,
        `ISOLATED: ${execution?.workspace_isolated ?? workspace?.workspace_isolated ?? true}`,
      ],
    },
    {
      title: "Generated Files",
      status: generationState,
      items: generatedFileLabels.length ? generatedFileLabels.map((file) => `FILE: ${file}`) : [`FILES: ${generationState}`],
    },
    {
      title: "Timeline",
      status: executionTimeline.length ? "LIVE" : "PENDING",
      items: executionTimeline.length ? executionTimeline.map((event) => event.event) : ["request pending"],
    },
    {
      title: "Outputs",
      status: outputLabels.length ? "VISIBLE" : "PENDING",
      items: outputLabels.length ? outputLabels.map((output) => `OUTPUT: ${output}`) : ["outputs pending"],
    },
    {
      title: "Execution Status",
      status: executionState,
      items: [
        `EXECUTION: ${executionState}`,
        `LOCKING: ${execution?.parallel_execution_blocked ? "PARALLEL_BLOCKED" : "REQUEST_LOCKED"}`,
        `AUDIT: ${executionAudit.length}`,
        `UPDATED: ${execution?.updated_at ? "YES" : "NO"}`,
      ],
    },
  ];

  return (
    <main className={`human-preview-shell state-${visualState.toLowerCase()}`}>
      <nav className="human-preview-nav" aria-label="Navegacion Human Console">
        <a className="human-preview-brand" href="#dashboard" aria-label="Volver al dashboard técnico">
          <span>F</span>
          <strong>FORJA</strong>
        </a>
        <a className="human-preview-back" href="#dashboard">Volver al dashboard actual</a>
      </nav>

      <section className="human-hero" id="human-console-preview">
        <div className="human-hero-copy">
          <div className="human-operational-field" aria-hidden="true">
            <span className="human-orbit-node node-a" />
            <span className="human-orbit-node node-b" />
            <span className="human-orbit-node node-c" />
            <span className="human-orbit-line line-a" />
            <span className="human-orbit-line line-b" />
          </div>
          <span className="human-eyebrow">Núcleo operativo</span>
          <h1>Pidele a FORJA que construya.</h1>
          <p>
            Interfaz operacional real para interpretar, aprobar, construir y auditar outputs dentro del workspace seguro.
          </p>
          <div className="human-ops-status" aria-label="Estado operacional visual">
            <span><i />Núcleo activo</span>
            <span><i />Builder Core real</span>
            <span><i />Control humano</span>
          </div>
        </div>

        <section className="human-command-panel" aria-label="Entrada principal de petición">
          <div className="human-command-telemetry" aria-hidden="true">
            <span />
            <span />
            <span />
          </div>
          <div className="human-command-topline">
            <label htmlFor="human-preview-command">¿Qué quieres construir?</label>
            <span>{activeState[1]}</span>
          </div>
          <div className="human-input-orbit">
            <textarea
              id="human-preview-command"
              value={commandText}
              onChange={(event) => handleCommandChange(event.target.value)}
              onFocus={handleCommandFocus}
              onBlur={() => setIsFocused(false)}
              placeholder="Describe lo que FORJA debe construir contigo..."
            />
          </div>
          <div className="human-state-console" aria-label="Estados visuales de FORJA" aria-live="polite">
            <div className="human-state-pulse" aria-hidden="true">
              <span />
            </div>
            <div>
              <strong>{activeState[1]}</strong>
              <p>{activeState[2]}</p>
            </div>
          </div>
          <div className="human-quick-actions" aria-label="Acciones rápidas">
            {quickActions.map(([action, nextCommand]) => (
              <button type="button" key={action} onClick={() => chooseQuickAction(nextCommand)}>{action}</button>
            ))}
          </div>
          <button className="human-primary-button" type="button" onClick={runPrimaryExecutionAction} disabled={generating || executing || !commandText.trim() || (!canApproveExecution && !canRetryDuplicate)}>
            {primaryActionLabel}
          </button>
          <div className="human-quick-actions" aria-label="Controles de aprobacion">
            <button type="button" onClick={rejectGovernedExecution} disabled={!canRejectExecution}>Rechazar</button>
          </div>
        </section>
      </section>

      <section className="human-thinking-rail" aria-label="Flujo visual de pensamiento">
        {states.map(([state, label]) => (
          <span key={state} className={state === visualState ? "active" : ""}>{label}</span>
        ))}
      </section>

      <section className="human-preview-grid">
        <article className="human-response-card">
          <span className="human-eyebrow">Builder Core real</span>
          <h2>{blueprintTitle}</h2>
          <p>
            {blueprintObjective}
          </p>
          <div className="human-architecture-preview" aria-label="Arquitectura sugerida visual">
            {structurePreview.map((item) => <span key={item}>{item}</span>)}
          </div>
          <div className="human-classification">
            <span>TYPE: {intentType}</span>
            <span>DOMAIN: {intentDomain}</span>
            <span>RISK: {intentRisk}</span>
            <span>APPROVAL: {intentApproval}</span>
            <span>TARGET: {intentTarget}</span>
            <span>EXECUTION: {executionState}</span>
            {execution?.reason ? <span>REASON: {execution.reason}</span> : null}
          </div>
        </article>

        <article className="human-plan-card">
          <span className="human-eyebrow">Flujo operacional completo</span>
          <div className="human-plan-list">
            {constructionPlan.map(([number, title, body]) => (
              <div className="human-plan-step" key={number}>
                <span>{number}</span>
                <div>
                  <strong>{title}</strong>
                  <p>{body}</p>
                </div>
              </div>
            ))}
          </div>
          <div className="human-real-sections" aria-label="Secciones reales de Human Console">
            {operationalSections.map((section) => (
              <section className="human-real-section" key={section.title}>
                <div className="human-real-section-title">
                  <span>{section.title}</span>
                  <strong>{section.status}</strong>
                </div>
                <div className="human-classification">
                  {section.items.map((item) => <span key={`${section.title}-${item}`}>{item}</span>)}
                </div>
              </section>
            ))}
          </div>
          {blueprint || executionError ? (
            <>
              <div className="human-classification" aria-label="Modulos del blueprint">
                {blueprintModules.map((module) => <span key={module}>MODULE: {module}</span>)}
              </div>
              <div className="human-classification" aria-label="Riesgos del blueprint">
                {blueprintRisks.map((risk) => <span key={risk}>RISK NOTE: {risk}</span>)}
              </div>
              <div className="human-classification" aria-label="Criterios de validacion del blueprint">
                {blueprintCriteria.map((criteria) => <span key={criteria}>VALIDATION: {criteria}</span>)}
              </div>
              <div className="human-classification" aria-label="Workspace generado">
                <span>WORKSPACE: {workspaceState}</span>
                <span>PATH: {workspacePath}</span>
                {workspace ? <span>APPROVAL STATUS: {workspace.approval_status.toUpperCase()}</span> : null}
              </div>
              {workspace ? (
                <>
                  <div className="human-classification" aria-label="Carpetas del workspace">
                    {workspaceDirs.map((directory) => <span key={directory}>FOLDER: {directory}/</span>)}
                  </div>
                  <div className="human-classification" aria-label="Archivos base del workspace">
                    {workspaceFiles.map((file) => <span key={file}>FILE: {file}</span>)}
                  </div>
                  <div className="human-classification" aria-label="Generacion controlada">
                    <span>GENERATION: {generationState}</span>
                    {generation ? <span>GEN APPROVAL: {generation.approval_status.toUpperCase()}</span> : null}
                    {generation?.reason ? <span>GEN REASON: {generation.reason}</span> : null}
                  </div>
                  {generation ? (
                    <>
                      <div className="human-classification" aria-label="Modulos generados">
                        {generatedModules.map((module) => <span key={module}>CREATED MODULE: {module}</span>)}
                      </div>
                      <div className="human-classification" aria-label="Estructura generada">
                        {generatedDirs.map((directory) => <span key={directory}>GEN FOLDER: {directory}/</span>)}
                      </div>
                      <div className="human-classification" aria-label="Archivos generados">
                        {generatedFiles.map((file) => <span key={file}>GEN FILE: {file}</span>)}
                      </div>
                    </>
                  ) : null}
                </>
              ) : null}
              {execution ? (
                <>
                  <div className="human-classification" aria-label="Estado de ejecucion gobernada">
                    <span>EXEC STATE: {executionState}</span>
                    <span>LOCKING: {execution.parallel_execution_blocked ? "PARALLEL_BLOCKED" : "REQUEST_LOCKED"}</span>
                    <span>BYPASS: {execution.governance_bypass_blocked ? "BLOCKED" : "OPEN"}</span>
                  </div>
                  <div className="human-classification" aria-label="Timeline de ejecucion">
                    {executionTimeline.map((event) => <span key={`${event.timestamp}-${event.event}`}>TIMELINE: {event.event}</span>)}
                  </div>
                  <div className="human-classification" aria-label="Outputs de ejecucion">
                    {executionOutputs.map((output) => <span key={`${output.kind}-${output.logical_path}`}>OUTPUT: {output.label}</span>)}
                  </div>
                  <div className="human-classification" aria-label="Audit basico de ejecucion">
                    {executionAudit.map((event) => <span key={`${event.timestamp}-${event.event_type}`}>AUDIT: {event.event_type}</span>)}
                  </div>
                </>
              ) : null}
              {workspaceError ? (
                <div className="human-classification" aria-label="Workspace bloqueado">
                  <span>WORKSPACE ERROR: {workspaceError}</span>
                </div>
              ) : null}
              {generationError ? (
                <div className="human-classification" aria-label="Generacion bloqueada">
                  <span>GENERATION ERROR: {generationError}</span>
                </div>
              ) : null}
              {executionError ? (
                <div className="human-classification" aria-label="Ejecucion bloqueada">
                  <span>EXECUTION ERROR: {executionError}</span>
                </div>
              ) : null}
            </>
          ) : null}
        </article>
      </section>

      <section className="human-technical-drawer">
        <details>
          <summary>Panel técnico oculto para el CEO</summary>
          <div>
            <p>Runtime, providers, audit stream, output manager, capability system y execution logs quedan detrás de esta capa para no dominar la experiencia principal.</p>
            <span>Esta consola usa la ejecucion gobernada sin activar IA externa, deploys ni comandos fuera del workspace.</span>
          </div>
        </details>
      </section>
    </main>
  );
}

function TechnicalDashboard() {
  const [refreshKey, setRefreshKey] = useState(0);
  const [creatorRefreshKey, setCreatorRefreshKey] = useState(0);
  const [lastRefresh, setLastRefresh] = useState("Initial sync");
  const [panel, setPanel] = useState<DetailPanel | null>(null);
  const [creatorSender, setCreatorSender] = useState<CreatorSender>("user");
  const [creatorCommand, setCreatorCommand] = useState("Prepare governed module");
  const [creatorDetails, setCreatorDetails] = useState("Keep zero-write policy active. Metadata-only execution. No provider.");
  const [creatorBusy, setCreatorBusy] = useState(false);
  const [creatorMessage, setCreatorMessage] = useState<string | null>(null);
  const [selectedCreatorCommand, setSelectedCreatorCommand] = useState<CreatorCommand | null>(null);
  const [selectedCreatorOutput, setSelectedCreatorOutput] = useState<CreatorOutput | null>(null);
  const [capabilityKind, setCapabilityKind] = useState<CapabilityKind>("strong_reasoning");
  const [capabilityObjective, setCapabilityObjective] = useState("Request stronger reasoning capability");
  const [capabilityExplanation, setCapabilityExplanation] = useState("FORJA needs a stronger reasoning capability for advanced planning. No provider, cost, or API call is selected.");
  const [selectedCapability, setSelectedCapability] = useState<CapabilityRequest | null>(null);
  const [selectedConsumption, setSelectedConsumption] = useState<CapabilityConsumption | null>(null);
  const { health, runtime } = useRuntimeData(refreshKey);
  const creatorState = useCreatorConsole(creatorRefreshKey);

  const modules = useMemo(() => Object.entries(health.data?.modules ?? {}), [health.data]);
  const providers = runtime.data?.providers ?? [];
  const securityWarnings = runtime.data?.security_warnings ?? health.data?.security_warnings ?? [];
  const database = runtime.data?.database ?? health.data?.database;
  const backendReady = health.data?.status === "ok" && runtime.data?.status === "active";
  const refreshing = health.loading || runtime.loading;

  const openPanel = (detail: DetailPanel) => setPanel(detail);
  const refreshStatus = () => {
    setLastRefresh(`Manual refresh ${new Date().toLocaleTimeString()}`);
    setRefreshKey((key) => key + 1);
  };
  const scrollToMatrix = () => document.getElementById("module-matrix")?.scrollIntoView({ behavior: "smooth", block: "start" });
  const governanceBlocked = (title: string, body: string, rows: Array<[string, string]>) => {
    openPanel({
      title,
      eyebrow: "Governance gate",
      tone: "amber",
      body,
      rows: [["Action", "Read-only cloud console"], ["Decision", "Blocked by governance"], ...rows],
    });
  };
  const selectLatestOutput = (record: CreatorCommand) => {
    setSelectedCreatorOutput(record.outputs[record.outputs.length - 1] ?? null);
  };
  const downloadCreatorOutput = (output: CreatorOutput) => {
    window.open(`${API_URL}/creator/outputs/${output.id}/metadata`, "_blank", "noreferrer");
    setCreatorMessage(`Metadata download requested for ${output.output_type}.`);
  };
  const submitCapabilityRequest = () => {
    setCreatorBusy(true);
    setCreatorMessage(null);
    postJson<CapabilityRequest>("/creator/capabilities", {
      sender: creatorSender,
      objective: capabilityObjective,
      explanation: capabilityExplanation,
      related_command_id: selectedCreatorCommand?.id ?? null,
      requirements: [
        {
          kind: capabilityKind,
          characteristics: ["technical_need", "no_provider_selection", "no_api_consumption"],
          reason: capabilityExplanation,
          priority: capabilityKind === "mass_processing" || capabilityKind === "strong_reasoning" ? "high" : "medium",
        },
      ],
    })
      .then((record) => {
        setSelectedCapability(record);
        setCreatorMessage(`Capability request routed to ${record.reply_to}: ${record.response}`);
        setCreatorRefreshKey((key) => key + 1);
      })
      .catch((error: Error) => setCreatorMessage(error.message))
      .finally(() => setCreatorBusy(false));
  };
  const decideCapabilityRequest = (decision: "approve" | "reject") => {
    if (!selectedCapability) {
      setCreatorMessage("Select or create a capability request first.");
      return;
    }
    setCreatorBusy(true);
    postJson<CapabilityRequest>(`/creator/capabilities/${selectedCapability.id}/${decision}`, { reason: `Operator ${decision} from Requested Capabilities panel.` })
      .then((record) => {
        setSelectedCapability(record);
        setCreatorMessage(`${decision} recorded for capability request. Status: ${record.status}.`);
        setCreatorRefreshKey((key) => key + 1);
      })
      .catch((error: Error) => setCreatorMessage(error.message))
      .finally(() => setCreatorBusy(false));
  };
  const attachCapabilityMetadata = () => {
    if (!selectedCapability) {
      setCreatorMessage("Select or create a capability request before attaching metadata.");
      return;
    }
    setCreatorBusy(true);
    postJson<CapabilityRequest>(`/creator/capabilities/${selectedCapability.id}/metadata`, {
      metadata: {
        capability_scope: selectedCapability.requirements.map((item) => item.kind),
        constraints: ["metadata_only", "no_api_calls_yet", "no_secret_collection"],
        authorized_surface: "capability_request_interface",
      },
    })
      .then((record) => {
        setSelectedCapability(record);
        setCreatorMessage(`Approved capability metadata attached for ${record.reply_to}.`);
        setCreatorRefreshKey((key) => key + 1);
      })
      .catch((error: Error) => setCreatorMessage(error.message))
      .finally(() => setCreatorBusy(false));
  };
  const consumeCapability = () => {
    if (!selectedCapability) {
      setCreatorMessage("Select an approved capability before consumption.");
      return;
    }
    setCreatorBusy(true);
    postJson<CapabilityConsumption>(`/creator/capabilities/${selectedCapability.id}/consume`, {
      sender: creatorSender,
      task: `Safe-mode consumption: ${selectedCapability.objective}`,
      manual_approval: true,
      execution_mode: "safe_metadata",
      usage_metadata: { input_units: 1, unit_type: "controlled_task" },
      cost_metadata: { amount: 0, currency: "USD", units: "metadata_only", note: "No external API call performed in safe-mode smoke." },
      provider_response_metadata: { response_summary: "No provider call performed; metadata wrapper consumed approved capability." },
      result_metadata: { result_summary: "safe_mode_consumption_recorded" },
    })
      .then((record) => {
        setSelectedConsumption(record);
        setCreatorMessage(`Capability consumption routed to ${record.reply_to}: ${record.response}`);
        setCreatorRefreshKey((key) => key + 1);
      })
      .catch((error: Error) => setCreatorMessage(error.message))
      .finally(() => setCreatorBusy(false));
  };
  const registerConsumptionUsage = () => {
    if (!selectedConsumption) {
      setCreatorMessage("Select or create a consumption record before registering usage.");
      return;
    }
    setCreatorBusy(true);
    postJson<CapabilityConsumption>(`/creator/capability-consumptions/${selectedConsumption.id}/usage`, { metadata: { output_units: 1, unit_type: "controlled_task" } })
      .then((record) => {
        setSelectedConsumption(record);
        setCreatorMessage("Usage metadata registered.");
        setCreatorRefreshKey((key) => key + 1);
      })
      .catch((error: Error) => setCreatorMessage(error.message))
      .finally(() => setCreatorBusy(false));
  };
  const registerConsumptionCost = () => {
    if (!selectedConsumption) {
      setCreatorMessage("Select or create a consumption record before registering cost.");
      return;
    }
    setCreatorBusy(true);
    postJson<CapabilityConsumption>(`/creator/capability-consumptions/${selectedConsumption.id}/cost`, { metadata: { amount: 0, currency: "USD", units: "metadata_only", note: "Safe-mode UI registration did not perform external API call." } })
      .then((record) => {
        setSelectedConsumption(record);
        setCreatorMessage("Cost metadata registered.");
        setCreatorRefreshKey((key) => key + 1);
      })
      .catch((error: Error) => setCreatorMessage(error.message))
      .finally(() => setCreatorBusy(false));
  };
  const registerProviderResponseMetadata = () => {
    if (!selectedConsumption) {
      setCreatorMessage("Select or create a consumption record before registering provider response metadata.");
      return;
    }
    setCreatorBusy(true);
    postJson<CapabilityConsumption>(`/creator/capability-consumptions/${selectedConsumption.id}/provider-response`, { metadata: { response_summary: "Provider response metadata registered by operator; no secrets stored." } })
      .then((record) => {
        setSelectedConsumption(record);
        setCreatorMessage("Provider response metadata registered.");
        setCreatorRefreshKey((key) => key + 1);
      })
      .catch((error: Error) => setCreatorMessage(error.message))
      .finally(() => setCreatorBusy(false));
  };
  const submitCreatorCommand = () => {
    setCreatorBusy(true);
    setCreatorMessage(null);
    postJson<CreatorCommand>("/creator/commands", { sender: creatorSender, command: creatorCommand, details: creatorDetails })
      .then((record) => {
        setSelectedCreatorCommand(record);
        selectLatestOutput(record);
        setCreatorMessage(`FORJA replied to sender=${record.reply_to_sender}: ${record.response}`);
        setCreatorRefreshKey((key) => key + 1);
      })
      .catch((error: Error) => setCreatorMessage(error.message))
      .finally(() => setCreatorBusy(false));
  };
  const decideCreatorCommand = (decision: CreatorDecision) => {
    if (!selectedCreatorCommand) {
      setCreatorMessage("Select or submit a command before recording approval intent.");
      return;
    }
    setCreatorBusy(true);
    postJson<CreatorCommand>(`/creator/commands/${selectedCreatorCommand.id}/decision`, { decision, reason: "Operator action from Creator Console" })
      .then((record) => {
        setSelectedCreatorCommand(record);
        selectLatestOutput(record);
        setCreatorMessage(`${decision} recorded. Final status: ${record.status}.`);
        setCreatorRefreshKey((key) => key + 1);
      })
      .catch((error: Error) => setCreatorMessage(error.message))
      .finally(() => setCreatorBusy(false));
  };
  const executeCreatorCommand = () => {
    if (!selectedCreatorCommand) {
      setCreatorMessage("Select or submit a command before metadata-only execution.");
      return;
    }
    setCreatorBusy(true);
    postJson<CreatorCommand>(`/creator/commands/${selectedCreatorCommand.id}/execute`, { metadata_only: true })
      .then((record) => {
        setSelectedCreatorCommand(record);
        selectLatestOutput(record);
        setCreatorMessage(`Execution engine replied to sender=${record.reply_to_sender}: ${record.response}`);
        setCreatorRefreshKey((key) => key + 1);
      })
      .catch((error: Error) => setCreatorMessage(error.message))
      .finally(() => setCreatorBusy(false));
  };

  return (
    <main className="forge-shell">
      <CreatorConsole
        state={creatorState}
        selected={selectedCreatorCommand}
        sender={creatorSender}
        command={creatorCommand}
        details={creatorDetails}
        busy={creatorBusy}
        message={creatorMessage}
        selectedOutput={selectedCreatorOutput}
        capabilityKind={capabilityKind}
        capabilityObjective={capabilityObjective}
        capabilityExplanation={capabilityExplanation}
        selectedCapability={selectedCapability}
        selectedConsumption={selectedConsumption}
        onSender={setCreatorSender}
        onCommand={setCreatorCommand}
        onDetails={setCreatorDetails}
        onSubmit={submitCreatorCommand}
        onSelect={(record) => {
          setSelectedCreatorCommand(record);
          selectLatestOutput(record);
        }}
        onSelectOutput={setSelectedCreatorOutput}
        onDownloadOutput={downloadCreatorOutput}
        onCapabilityKind={setCapabilityKind}
        onCapabilityObjective={setCapabilityObjective}
        onCapabilityExplanation={setCapabilityExplanation}
        onCapabilitySubmit={submitCapabilityRequest}
        onSelectCapability={setSelectedCapability}
        onCapabilityDecision={decideCapabilityRequest}
        onAttachCapabilityMetadata={attachCapabilityMetadata}
        onConsumeCapability={consumeCapability}
        onSelectConsumption={setSelectedConsumption}
        onRegisterUsage={registerConsumptionUsage}
        onRegisterCost={registerConsumptionCost}
        onRegisterProviderResponse={registerProviderResponseMetadata}
        onDecision={decideCreatorCommand}
        onExecute={executeCreatorCommand}
      />

      <section className="hero">
        <div className="hero-copy">
          <div className="brand-row">
            <div className="brand-mark">F</div>
            <div>
              <span>FORJA</span>
              <strong>Enterprise Core Runtime</strong>
            </div>
          </div>
          <h1>Controlled Intelligence Infrastructure</h1>
          <p>Governance, runtime and execution core for AI systems. Built like a forge: heat contained, force directed, operations controlled.</p>
          <div className="hero-actions">
            <StatusBadge value={backendReady ? "cloud online" : "checking"} tone={backendReady ? "green" : "amber"} />
            <span className="api-chip">{API_URL}</span>
          </div>
          <div className="command-bar" aria-label="Runtime actions">
            <ActionButton onClick={refreshStatus} loading={refreshing}>Refresh status</ActionButton>
            <a className="forge-button ghost" href="#human-console-preview">Human Console</a>
            <ActionButton variant="ghost" href={API_URL}>Ver backend</ActionButton>
            <ActionButton variant="ghost" href={`${API_URL}/runtime/status`}>Ver runtime</ActionButton>
            <ActionButton variant="ghost" href={`${API_URL}/health`}>Ver health</ActionButton>
          </div>
        </div>

        <aside className="core-panel">
          <span className="panel-label">Runtime core</span>
          <div className="core-ring">
            <span />
            <strong>{runtime.loading ? "..." : display(runtime.data?.status, "offline")}</strong>
          </div>
          <div className="core-grid">
            <div>
              <span>Environment</span>
              <strong>{display(health.data?.environment ?? runtime.data?.environment)}</strong>
            </div>
            <div>
              <span>Production</span>
              <strong>{health.loading ? "checking" : display(health.data?.production_ready)}</strong>
            </div>
            <div>
              <span>Busy loop</span>
              <strong>{runtime.loading ? "checking" : display(runtime.data?.busy_loop)}</strong>
            </div>
            <div>
              <span>Audit events</span>
              <strong>{runtime.loading ? "checking" : display(runtime.data?.audit_events, "0")}</strong>
            </div>
          </div>
          <div className="sync-note">
            <span>{lastRefresh}</span>
            <strong>{refreshing ? "Syncing cloud runtime" : health.error || runtime.error ? "Sync needs attention" : "Cloud telemetry current"}</strong>
          </div>
        </aside>
      </section>

      <section className="status-strip">
        <ForgeCard eyebrow="Backend" title="Health Overview" value={health.loading ? "loading" : health.data?.status ?? "error"} actionLabel="Inspect health" onAction={() => openPanel({
          title: "Backend health",
          eyebrow: "GET /health",
          tone: toneForStatus(health.data?.status ?? (health.error ? "error" : "loading")),
          body: health.error ?? "Public health endpoint is reachable from the frontend and reporting cloud state.",
          rows: [["Service", display(health.data?.service)], ["Version", display(health.data?.version)], ["Environment", display(health.data?.environment)], ["Production ready", display(health.data?.production_ready)]],
        })}>
          {health.loading ? <LoadingBars /> : <p>{health.error ?? `${display(health.data?.service)} ${display(health.data?.version, "")}`}</p>}
        </ForgeCard>
        <ForgeCard eyebrow="Runtime" title="Execution State" value={runtime.loading ? "loading" : runtime.data?.status ?? "error"} actionLabel="Inspect runtime" onAction={() => openPanel({
          title: "Runtime execution",
          eyebrow: "GET /runtime/status",
          tone: toneForStatus(runtime.data?.status ?? (runtime.error ? "error" : "loading")),
          body: runtime.error ?? "Runtime loop, queue behavior and execution gates are reported by the live backend.",
          rows: [["Runtime loop", display(runtime.data?.runtime_loop)], ["Busy loop", display(runtime.data?.busy_loop)], ["Audit events", display(runtime.data?.audit_events, "0")], ["Zero write policy", display(runtime.data?.zero_write_policy)]],
        })}>
          {runtime.loading ? <LoadingBars /> : <p>{runtime.error ?? display(runtime.data?.runtime_loop)}</p>}
        </ForgeCard>
        <ForgeCard eyebrow="Database" title="Persistence Layer" value={database?.status ?? "not reported"} actionLabel="Database detail" onAction={() => openPanel({
          title: "Persistence layer",
          eyebrow: "Database status",
          tone: toneForStatus(database?.status),
          body: "Database status is displayed exactly as reported by FORJA cloud telemetry.",
          rows: [["Status", display(database?.status)], ["Enabled", display(database?.enabled)], ["Reason", display(database?.reason)]],
        })}>
          <p>{display(database?.reason)} - enabled: {display(database?.enabled)}</p>
        </ForgeCard>
      </section>

      {health.error || runtime.error ? (
        <section className="error-grid">
          {health.error ? <ErrorPanel label="Health endpoint error" error={health.error} /> : null}
          {runtime.error ? <ErrorPanel label="Runtime endpoint error" error={runtime.error} /> : null}
        </section>
      ) : null}

      <section className="dashboard-grid">
        <ForgeCard eyebrow="Governance" title="Human Control Layer" value={runtime.data?.human_in_the_loop ?? "not reported"} actionLabel="Revisar governance" onAction={() => governanceBlocked(
          "Human control layer",
          "Sensitive actions remain read-only from this public console. Execution changes require authenticated governance routes.",
          [["Human in the loop", display(runtime.data?.human_in_the_loop)], ["Zero write policy", display(runtime.data?.zero_write_policy)]],
        )}>
          <p>Human approval remains part of sensitive execution paths. Zero-write policy: {display(runtime.data?.zero_write_policy)}.</p>
        </ForgeCard>

        <ForgeCard eyebrow="AI Pipeline" title="Provider Boundary" value={runtime.data?.ai_pipeline ?? health.data?.modules?.ai_pipeline ?? "not reported"} actionLabel="Revisar AI pipeline" onAction={() => governanceBlocked(
          "Provider boundary",
          "External AI activation is blocked from this frontend. This panel exposes only live provider status from runtime telemetry.",
          [["Pipeline", display(runtime.data?.ai_pipeline ?? health.data?.modules?.ai_pipeline)], ["Providers", display(providers.length, "0")]],
        )}>
          {providers.length ? (
            <div className="provider-list">
              {providers.map((provider) => (
                <div key={provider.id}>
                  <strong>{provider.id}</strong>
                  <StatusBadge value={provider.status} />
                  <p>{provider.reason}</p>
                </div>
              ))}
            </div>
          ) : (
            <p>No providers reported by runtime.</p>
          )}
        </ForgeCard>

        <ForgeCard eyebrow="Factory" title="Execution Forge" value={health.data?.modules?.factory ?? "not reported"} actionLabel="Factory status" onAction={scrollToMatrix}>
          <p>{runtime.data?.notes?.find((note) => note.toLowerCase().includes("factory")) ?? "Factory module not reported by runtime notes."}</p>
        </ForgeCard>

        <ForgeCard eyebrow="Workflow" title="Operational Flow" value={health.data?.modules?.workflows ?? runtime.data?.runtime_loop ?? "not reported"} actionLabel="Revisar workflows" onAction={() => openPanel({
          title: "Operational workflows",
          eyebrow: "Workflow status",
          tone: toneForStatus(health.data?.modules?.workflows ?? runtime.data?.runtime_loop),
          body: "Workflow activity is summarized from public health and runtime status only.",
          rows: [["Module", display(health.data?.modules?.workflows)], ["Runtime loop", display(runtime.data?.runtime_loop)], ["Busy loop", display(runtime.data?.busy_loop)]],
        })}>
          <p>{runtime.data?.notes?.find((note) => note.toLowerCase().includes("background")) ?? "Workflow status is not directly reported by /health."}</p>
        </ForgeCard>

        <ForgeCard eyebrow="Audit" title="Traceability Ledger" value={runtime.data?.audit_events ?? "not reported"} actionLabel="Revisar auditoria" onAction={() => governanceBlocked(
          "Traceability ledger",
          "Detailed audit records stay behind authenticated API routes. This public surface shows only the runtime audit count.",
          [["Audit events", display(runtime.data?.audit_events, "0")]],
        )}>
          <p>Detailed audit trail remains protected behind authenticated API routes. This panel only uses public runtime summary.</p>
        </ForgeCard>

        <ForgeCard eyebrow="Security" title="Readiness & Warnings" value={securityWarnings.length ? `${securityWarnings.length} warnings` : "clear"} tone={securityWarnings.length ? "amber" : "green"} actionLabel="Ver detalles seguridad" onAction={() => openPanel({
          title: "Security readiness",
          eyebrow: "Runtime warnings",
          tone: securityWarnings.length ? "amber" : "green",
          body: securityWarnings.length ? "FORJA reports controlled security warnings from the backend." : "No security warnings are reported by the cloud runtime.",
          rows: securityWarnings.length ? securityWarnings.map((warning, index) => [`Warning ${index + 1}`, warning]) : [["Warnings", "clear"]],
        })}>
          {securityWarnings.length ? (
            <ul className="warning-list">
              {securityWarnings.map((warning) => <li key={warning}>{warning}</li>)}
            </ul>
          ) : (
            <p>No security warnings reported by cloud runtime.</p>
          )}
        </ForgeCard>
      </section>

      <section className="module-matrix" id="module-matrix">
        <div className="section-heading">
          <span>Subsystems</span>
          <h2>Enterprise module matrix</h2>
        </div>
        {health.loading ? (
          <LoadingBars />
        ) : modules.length ? (
          <div className="module-grid">
            {modules.map(([name, status]) => (
              <div key={name} className="module-row">
                <span>{name}</span>
                <StatusBadge value={status} />
              </div>
            ))}
          </div>
        ) : (
          <div className="empty-state">No modules reported by /health.</div>
        )}
      </section>

      <footer className="technical-footer">
        <span>Backend URL: {API_URL}</span>
        <span>Endpoints: /health - /runtime/status</span>
      </footer>
      {panel ? <DetailModal panel={panel} onClose={() => setPanel(null)} /> : null}
    </main>
  );
}

export default function App() {
  const hashRoute = useHashRoute();
  return hashRoute === "#human-console-preview" ? <HumanConsolePreview /> : <TechnicalDashboard />;
}
