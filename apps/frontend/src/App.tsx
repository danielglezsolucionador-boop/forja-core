import { useEffect, useMemo, useState } from "react";
import { API_URL, fetchJson, HealthResponse, login, RuntimeStatus } from "./lib/api";
import { StatusCard } from "./components/StatusCard";

type LoadState<T> = {
  data: T | null;
  error: string | null;
  loading: boolean;
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

export default function App() {
  const [token, setToken] = useState<string | null>(null);
  const [loginError, setLoginError] = useState<string | null>(null);

  const health = useLoad<HealthResponse>(() => fetchJson("/health"), []);
  const runtime = useLoad<RuntimeStatus>(() => fetchJson("/runtime/status"), []);
  const audit = useLoad<unknown[]>(() => (token ? fetchJson("/audit/events", token) : Promise.resolve([])), [token]);

  const modules = useMemo(() => Object.entries(health.data?.modules ?? {}), [health.data]);

  async function handleLocalLogin() {
    setLoginError(null);
    try {
      const accessToken = await login("forja_admin", "forja_local_admin_change_me");
      setToken(accessToken);
    } catch (error) {
      setLoginError(error instanceof Error ? error.message : "Login failed");
    }
  }

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 bg-slate-950/95">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-6 py-6 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="text-xs font-bold uppercase tracking-[0.35em] text-blue-300">FORJA</div>
            <h1 className="mt-2 text-3xl font-black tracking-tight">Operational Factory Console</h1>
          </div>
          <div className="rounded-lg border border-slate-700 bg-slate-900 px-4 py-3 text-sm text-slate-300">
            API: <span className="font-semibold text-slate-100">{API_URL}</span>
          </div>
        </div>
      </header>

      <section className="mx-auto max-w-7xl px-6 py-8">
        <div className="grid gap-4 md:grid-cols-4">
          <StatusCard label="Backend" value={health.loading ? "checking" : health.data?.status ?? "offline"} tone={health.data?.status === "ok" ? "green" : "red"}>
            {health.error ?? `${health.data?.service ?? "-"} ${health.data?.version ?? ""}`}
          </StatusCard>
          <StatusCard label="Runtime" value={runtime.data?.status ?? (runtime.loading ? "checking" : "offline")} tone={runtime.data?.busy_loop ? "red" : "green"}>
            busy loop: {runtime.data ? String(runtime.data.busy_loop) : "-"}
          </StatusCard>
          <StatusCard label="Zero Write" value={runtime.data?.zero_write_policy ?? "-"} tone="amber">
            Factory writes require human approval.
          </StatusCard>
          <StatusCard label="Audit Events" value={runtime.data?.audit_events ?? 0} tone="blue">
            Auth required for detailed audit trail.
          </StatusCard>
        </div>

        <div className="mt-8 grid gap-6 lg:grid-cols-[1.4fr_1fr]">
          <section className="rounded-lg border border-slate-800 bg-slate-900/70 p-5">
            <h2 className="text-lg font-bold">Modules</h2>
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              {modules.map(([name, status]) => (
                <div key={name} className="flex items-center justify-between rounded-md border border-slate-800 bg-slate-950 p-3">
                  <span className="text-sm font-semibold text-slate-300">{name}</span>
                  <span className="text-xs font-bold uppercase tracking-wide text-blue-300">{status}</span>
                </div>
              ))}
              {!health.loading && modules.length === 0 ? <div className="text-sm text-slate-400">No modules reported.</div> : null}
            </div>
          </section>

          <section className="rounded-lg border border-slate-800 bg-slate-900/70 p-5">
            <h2 className="text-lg font-bold">Local Auth</h2>
            <p className="mt-2 text-sm text-slate-400">Use local bootstrap credentials only for local validation.</p>
            <button onClick={handleLocalLogin} className="mt-4 rounded-md bg-blue-500 px-4 py-2 text-sm font-bold text-white hover:bg-blue-400">
              Validate Local Login
            </button>
            <div className="mt-3 text-sm text-slate-300">{token ? "Authenticated locally." : loginError ?? "Not authenticated."}</div>
          </section>
        </div>

        <div className="mt-8 grid gap-6 lg:grid-cols-2">
          <section className="rounded-lg border border-slate-800 bg-slate-900/70 p-5">
            <h2 className="text-lg font-bold">Providers</h2>
            <div className="mt-4 space-y-3">
              {(runtime.data?.providers ?? []).map((provider) => (
                <div key={provider.id} className="rounded-md border border-slate-800 bg-slate-950 p-3">
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-semibold text-slate-200">{provider.id}</span>
                    <span className="text-xs font-bold uppercase text-amber-300">{provider.status}</span>
                  </div>
                  <p className="mt-2 text-sm text-slate-400">{provider.reason}</p>
                </div>
              ))}
            </div>
          </section>

          <section className="rounded-lg border border-slate-800 bg-slate-900/70 p-5">
            <h2 className="text-lg font-bold">Audit Preview</h2>
            <pre className="mt-4 max-h-72 overflow-auto rounded-md bg-slate-950 p-4 text-xs text-slate-300">
              {JSON.stringify(audit.data ?? [], null, 2)}
            </pre>
          </section>
        </div>
      </section>
    </main>
  );
}
