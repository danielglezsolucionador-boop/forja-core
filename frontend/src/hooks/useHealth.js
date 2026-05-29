import { useEffect, useState } from "react";
import { apiUrl } from "../lib/api";

function useHealth() {
  const [state, setState] = useState({
    status: "unknown",
    app: null,
    timestamp: null,
    loading: true,
    error: false,
  });

  useEffect(() => {
    let alive = true;

    fetch(apiUrl("/api/v1/health"))
      .then((res) => {
        if (!res.ok) {
          throw new Error(`Health request failed: ${res.status}`);
        }
        return res.json();
      })
      .then((data) => {
        if (!alive) return;
        setState({
          status: data.status || "unknown",
          app: data.app || null,
          timestamp: data.timestamp || null,
          loading: false,
          error: false,
        });
      })
      .catch(() => {
        if (!alive) return;
        setState({
          status: "unavailable",
          app: null,
          timestamp: null,
          loading: false,
          error: true,
        });
      });

    return () => {
      alive = false;
    };
  }, []);

  return state;
}

export default useHealth;
