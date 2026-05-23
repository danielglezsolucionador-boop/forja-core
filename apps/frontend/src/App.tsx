import { useEffect, useMemo, useState } from "react";
import { API_URL, CreatorCommand, CreatorConsoleState, CreatorDecision, CreatorSender, fetchJson, HealthResponse, postJson, RuntimeStatus } from "./lib/api";

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
  if (["ok", "active", "available", "true", "connection_ok"].includes(value)) return "green";
  if (["degraded", "disabled", "not_started_by_design", "blocked_provider_disabled", "local_queue", "loading"].includes(value)) return "amber";
  if (["error", "failed", "critical", "unavailable", "false"].includes(value)) return "red";
  return "steel";
}

function display(value: unknown, fallback = "Not reported") {
  if (value === undefined || value === null || value === "") return fallback;
  return String(value);
}

function StatusBadge({ value, tone }: { value: string | boolean | number; tone?: Tone }) {
  const resolvedTone = tone ?? toneForStatus(typeof value === "number" ? "ok" : value);
  return <span className={`status-badge ${resolvedTone}`}>{String(value)}</span>;
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
      {loading ? "Refreshing..." : children}
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
      {(["user", "cerebro"] as CreatorSender[]).map((sender) => (
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
  onSender: (value: CreatorSender) => void;
  onCommand: (value: string) => void;
  onDetails: (value: string) => void;
  onSubmit: () => void;
  onSelect: (value: CreatorCommand) => void;
  onDecision: (value: CreatorDecision) => void;
  onExecute: () => void;
}) {
  const commands = state.data?.commands ?? [];
  const active = selected ?? commands[commands.length - 1] ?? null;
  const pipeline = active?.pipeline ?? (state.data?.command_statuses ?? []).map((status) => ({ status, label: status, detail: "Awaiting command input." }));
  const audit = state.data?.audit_stream ?? [];
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

        <section className="creator-card">
          <div className="card-topline">
            <span>Output panel</span>
            <StatusBadge value={active?.outputs.length ?? 0} />
          </div>
          {(active?.outputs ?? []).map((output) => (
            <div key={`${output.kind}-${output.name}`} className="output-row">
              <span>{output.kind}</span>
              <strong>{output.name}</strong>
              <StatusBadge value={output.status} tone={toneForStatus(output.status)} />
            </div>
          ))}
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

export default function App() {
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
  const submitCreatorCommand = () => {
    setCreatorBusy(true);
    setCreatorMessage(null);
    postJson<CreatorCommand>("/creator/commands", { sender: creatorSender, command: creatorCommand, details: creatorDetails })
      .then((record) => {
        setSelectedCreatorCommand(record);
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
        onSender={setCreatorSender}
        onCommand={setCreatorCommand}
        onDetails={setCreatorDetails}
        onSubmit={submitCreatorCommand}
        onSelect={setSelectedCreatorCommand}
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
