export const API_URL = import.meta.env.VITE_FORJA_API_URL ?? "http://127.0.0.1:8100";

export type HealthResponse = {
  status: string;
  service: string;
  version: string;
  environment: string;
  production_ready: boolean;
  modules: Record<string, string>;
};

export type RuntimeStatus = {
  status: string;
  runtime_loop: string;
  busy_loop: boolean;
  zero_write_policy: boolean;
  human_in_the_loop: boolean;
  providers: Array<{ id: string; kind: string; status: string; reason: string }>;
  audit_events: number;
  notes: string[];
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

export async function login(username: string, password: string): Promise<string> {
  const response = await fetch(`${API_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!response.ok) {
    throw new Error("Login failed");
  }
  const data = (await response.json()) as { access_token: string };
  return data.access_token;
}
