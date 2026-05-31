const LIVE_API_URL = "https://forja-core.onrender.com";

function resolveApiBaseUrl() {
  const rawApiUrl = process.env.REACT_APP_FORJA_API_URL || "";
  if (rawApiUrl.trim()) {
    return rawApiUrl.replace(/\/$/, "");
  }

  if (typeof window === "undefined") {
    return "";
  }

  const host = window.location.hostname;
  const isLocalhost = host === "localhost" || host === "127.0.0.1" || host === "::1";

  return isLocalhost ? "http://localhost:8100" : LIVE_API_URL;
}

export const API_BASE_URL = resolveApiBaseUrl();

export function apiUrl(path) {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE_URL}${normalizedPath}`;
}

export async function fetchJson(path, { timeoutMs = 10000, signal } = {}) {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);

  if (signal) {
    signal.addEventListener("abort", () => controller.abort(), { once: true });
  }

  const started = performance.now();

  try {
    const response = await fetch(apiUrl(path), {
      headers: { Accept: "application/json" },
      signal: controller.signal,
    });
    const durationMs = Math.round(performance.now() - started);

    if (!response.ok) {
      throw new Error(`${path} returned HTTP ${response.status}`);
    }

    return {
      data: await response.json(),
      status: response.status,
      durationMs,
    };
  } catch (error) {
    if (error.name === "AbortError") {
      throw new Error(`${path} timed out after ${timeoutMs}ms`);
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}
