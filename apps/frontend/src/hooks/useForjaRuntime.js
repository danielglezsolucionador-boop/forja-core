import { useEffect, useMemo, useState } from "react";
import { fetchJson } from "../lib/humanCabinApi";

const endpointConfig = {
  health: { name: "Health", path: "/health" },
  runtime: { name: "Runtime", path: "/runtime/status" },
  provenance: { name: "Provenance", path: "/provenance" },
};
const RUNTIME_REFRESH_MS = 8000;

const initialEndpointState = Object.fromEntries(
  Object.entries(endpointConfig).map(([key, endpoint]) => [
    key,
    {
      ...endpoint,
      status: "loading",
      data: null,
      error: null,
    },
  ]),
);

function endpointStatusFromResult(result) {
  if (result.error) {
    return "error";
  }
  return "ok";
}

function useForjaRuntime() {
  const [endpoints, setEndpoints] = useState(initialEndpointState);
  const [lastSync, setLastSync] = useState(null);

  useEffect(() => {
    let alive = true;
    let controller = new AbortController();

    async function load() {
      controller.abort();
      controller = new AbortController();
      const entries = await Promise.all(
        Object.entries(endpointConfig).map(async ([key, endpoint]) => {
          try {
            const result = await fetchJson(endpoint.path, {
              signal: controller.signal,
              timeoutMs: 12000,
            });
            return [
              key,
              {
                ...endpoint,
                status: endpointStatusFromResult(result),
                data: result.data,
                error: null,
                httpStatus: result.status,
                durationMs: result.durationMs,
              },
            ];
          } catch (error) {
            return [
              key,
              {
                ...endpoint,
                status: "error",
                data: null,
                error: error.message || "Endpoint unavailable",
              },
            ];
          }
        }),
      );

      if (!alive) return;
      setEndpoints((current) => {
        const next = Object.fromEntries(entries);
        for (const [key, endpoint] of Object.entries(next)) {
          if (endpoint.status === "error" && current[key]?.data) {
            next[key] = {
              ...current[key],
              ...endpointConfig[key],
              status: "stale",
              error: endpoint.error,
              data: current[key].data,
              httpStatus: current[key].httpStatus,
              durationMs: current[key].durationMs,
            };
          }
        }
        return next;
      });
      setLastSync(new Date().toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      }));
    }

    load();
    const interval = window.setInterval(load, RUNTIME_REFRESH_MS);

    return () => {
      alive = false;
      window.clearInterval(interval);
      controller.abort();
    };
  }, []);

  const globalStatus = useMemo(() => {
    const values = Object.values(endpoints);
    if (values.some((endpoint) => endpoint.status === "loading")) {
      return "UNKNOWN";
    }
    if (values.some((endpoint) => endpoint.status === "error")) {
      return "DEGRADED";
    }
    if (values.some((endpoint) => endpoint.status === "stale")) {
      return "DEGRADED";
    }
    return "OPERATIONAL";
  }, [endpoints]);

  return {
    endpoints,
    globalStatus,
    lastSync,
  };
}

export default useForjaRuntime;
