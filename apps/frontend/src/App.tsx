import { useEffect, useMemo, useState } from "react";
import { API_URL, fetchJson, HealthResponse, RuntimeStatus } from "./lib/api";

type LoadState<T> = {
  data: T | null;
  error: string | null;
  loading: boolean;
};

type Tone = "green" | "amber" | "red" | "steel";

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

function toneForStatus(status?: string | boolean): Tone {
  if (status === true) return "green";
  if (status === false) return "amber";
  const value = String(status ?? "").toLowerCase();
  if (["ok", "active", "available", "true", "connection_ok"].includes(value)) return "green";
  if (["degraded", "disabled", "not_started_by_design", "blocked_provider_disabled", "local_queue"].includes(value)) return "amber";
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
  children,
}: {
  eyebrow: string;
  title: string;
  value: string | number | boolean;
  tone?: Tone;
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

export default function App() {
  const health = useLoad<HealthResponse>(() => fetchJson("/health"), []);
  const runtime = useLoad<RuntimeStatus>(() => fetchJson("/runtime/status"), []);

  const modules = useMemo(() => Object.entries(health.data?.modules ?? {}), [health.data]);
  const providers = runtime.data?.providers ?? [];
  const securityWarnings = runtime.data?.security_warnings ?? health.data?.security_warnings ?? [];
  const database = runtime.data?.database ?? health.data?.database;
  const backendReady = health.data?.status === "ok" && runtime.data?.status === "active";

  return (
    <main className="forge-shell">
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
        </aside>
      </section>

      <section className="status-strip">
        <ForgeCard eyebrow="Backend" title="Health Overview" value={health.loading ? "loading" : health.data?.status ?? "error"}>
          {health.loading ? <LoadingBars /> : <p>{health.error ?? `${display(health.data?.service)} ${display(health.data?.version, "")}`}</p>}
        </ForgeCard>
        <ForgeCard eyebrow="Runtime" title="Execution State" value={runtime.loading ? "loading" : runtime.data?.status ?? "error"}>
          {runtime.loading ? <LoadingBars /> : <p>{runtime.error ?? display(runtime.data?.runtime_loop)}</p>}
        </ForgeCard>
        <ForgeCard eyebrow="Database" title="Persistence Layer" value={database?.status ?? "not reported"}>
          <p>{display(database?.reason)} · enabled: {display(database?.enabled)}</p>
        </ForgeCard>
      </section>

      {(health.error || runtime.error) ? (
        <section className="error-grid">
          {health.error ? <ErrorPanel label="Health endpoint error" error={health.error} /> : null}
          {runtime.error ? <ErrorPanel label="Runtime endpoint error" error={runtime.error} /> : null}
        </section>
      ) : null}

      <section className="dashboard-grid">
        <ForgeCard eyebrow="Governance" title="Human Control Layer" value={runtime.data?.human_in_the_loop ?? "not reported"}>
          <p>Human approval remains part of sensitive execution paths. Zero-write policy: {display(runtime.data?.zero_write_policy)}.</p>
        </ForgeCard>

        <ForgeCard eyebrow="AI Pipeline" title="Provider Boundary" value={runtime.data?.ai_pipeline ?? health.data?.modules?.ai_pipeline ?? "not reported"}>
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

        <ForgeCard eyebrow="Factory" title="Execution Forge" value={health.data?.modules?.factory ?? "not reported"}>
          <p>{runtime.data?.notes?.find((note) => note.toLowerCase().includes("factory")) ?? "Factory module not reported by runtime notes."}</p>
        </ForgeCard>

        <ForgeCard eyebrow="Workflow" title="Operational Flow" value={health.data?.modules?.workflows ?? runtime.data?.runtime_loop ?? "not reported"}>
          <p>{runtime.data?.notes?.find((note) => note.toLowerCase().includes("background")) ?? "Workflow status is not directly reported by /health."}</p>
        </ForgeCard>

        <ForgeCard eyebrow="Audit" title="Traceability Ledger" value={runtime.data?.audit_events ?? "not reported"}>
          <p>Detailed audit trail remains protected behind authenticated API routes. This panel only uses public runtime summary.</p>
        </ForgeCard>

        <ForgeCard eyebrow="Security" title="Readiness & Warnings" value={securityWarnings.length ? `${securityWarnings.length} warnings` : "clear"} tone={securityWarnings.length ? "amber" : "green"}>
          {securityWarnings.length ? (
            <ul className="warning-list">
              {securityWarnings.map((warning) => <li key={warning}>{warning}</li>)}
            </ul>
          ) : (
            <p>No security warnings reported by cloud runtime.</p>
          )}
        </ForgeCard>
      </section>

      <section className="module-matrix">
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
        <span>Endpoints: /health · /runtime/status</span>
      </footer>
    </main>
  );
}
