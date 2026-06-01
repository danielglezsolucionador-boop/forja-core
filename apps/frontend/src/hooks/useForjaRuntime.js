import { useEffect, useMemo, useState } from "react";
import { fetchJson } from "../lib/humanCabinApi";

const endpointConfig = {
  health: { name: "Health", path: "/health" },
  runtime: { name: "Runtime", path: "/runtime/status" },
  provenance: { name: "Provenance", path: "/provenance" },
};

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
    const controller = new AbortController();

    async function load() {
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
      setEndpoints(Object.fromEntries(entries));
      setLastSync(new Date().toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      }));
    }

    load();

    return () => {
      alive = false;
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
    return "OPERATIONAL";
  }, [endpoints]);

  return {
    endpoints,
    globalStatus,
    lastSync,
  };
}

export default useForjaRuntime;
