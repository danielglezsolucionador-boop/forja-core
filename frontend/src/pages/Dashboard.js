import { useState, useEffect } from "react";
import { apiUrl } from "../lib/api";

function Dashboard() {
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [now, setNow] = useState(new Date().toLocaleString());

  useEffect(() => {
    fetch(apiUrl("/api/v1/health"))
      .then((res) => res.json())
      .then((data) => {
        setHealth(data);
        setLoading(false);
      })
      .catch(() => {
        setError(true);
        setLoading(false);
      });

    const interval = setInterval(() => {
      setNow(new Date().toLocaleString());
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div style={{ minHeight: "100vh", background: "#0f172a", color: "#f1f5f9", padding: "40px", fontFamily: "monospace" }}>
      <h1 style={{ fontSize: "24px", marginBottom: "8px" }}>FORJA — Dashboard</h1>
      <p style={{ color: "#64748b", marginBottom: "32px" }}>Tiempo local: {now}</p>

      <div style={{ display: "grid", gap: "16px", maxWidth: "600px" }}>

        <div style={{ background: "#1e293b", padding: "20px", borderRadius: "8px" }}>
          <p style={{ color: "#64748b", marginBottom: "8px" }}>BACKEND</p>
          {loading && <p style={{ color: "#94a3b8" }}>Conectando...</p>}
          {error && <p style={{ color: "#f87171" }}>OFFLINE</p>}
          {health && <p style={{ color: "#4ade80", fontSize: "18px" }}>ONLINE</p>}
        </div>

        <div style={{ background: "#1e293b", padding: "20px", borderRadius: "8px" }}>
          <p style={{ color: "#64748b", marginBottom: "8px" }}>ESTADO</p>
          <p style={{ color: "#f1f5f9" }}>{health ? health.status : "—"}</p>
        </div>

        <div style={{ background: "#1e293b", padding: "20px", borderRadius: "8px" }}>
          <p style={{ color: "#64748b", marginBottom: "8px" }}>VERSIÓN</p>
          <p style={{ color: "#f1f5f9" }}>{health ? health.version : "—"}</p>
        </div>

        <div style={{ background: "#1e293b", padding: "20px", borderRadius: "8px" }}>
          <p style={{ color: "#64748b", marginBottom: "8px" }}>ENTORNO</p>
          <p style={{ color: "#f1f5f9" }}>{health ? health.env : "—"}</p>
        </div>

        <div style={{ background: "#1e293b", padding: "20px", borderRadius: "8px" }}>
          <p style={{ color: "#64748b", marginBottom: "8px" }}>ÚLTIMO TIMESTAMP BACKEND</p>
          <p style={{ color: "#f1f5f9" }}>{health ? health.timestamp : "—"}</p>
        </div>

        <div style={{ background: "#1e293b", padding: "20px", borderRadius: "8px" }}>
          <p style={{ color: "#64748b", marginBottom: "8px" }}>AUTH</p>
          <p style={{ color: "#fbbf24" }}>No autenticado</p>
        </div>

      </div>
    </div>
  );
}

export default Dashboard;
