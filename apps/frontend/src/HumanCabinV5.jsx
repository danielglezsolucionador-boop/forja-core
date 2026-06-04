import React, { useEffect, useMemo, useRef, useState } from "react";
import useForjaRuntime from "./hooks/useForjaRuntime";
import { apiUrl } from "./lib/humanCabinApi";

const NO_DATA = "NO DATA AVAILABLE";

const fallbackSnapshot = {
  metrics: [
    { label: "Apps en construccion", value: NO_DATA, detail: NO_DATA, status: "UNKNOWN" },
    { label: "Tareas activas", value: NO_DATA, detail: NO_DATA, status: "UNKNOWN" },
    { label: "Bloqueos", value: NO_DATA, detail: NO_DATA, status: "UNKNOWN" },
    { label: "Aprobaciones pendientes", value: NO_DATA, detail: NO_DATA, status: "UNKNOWN" },
    { label: "Entregas listas", value: NO_DATA, detail: NO_DATA, status: "UNKNOWN" },
    { label: "Ultima ejecucion", value: NO_DATA, detail: NO_DATA, status: "UNKNOWN" },
  ],
  services: [],
  constructionQueue: [],
  flow: [],
  approvals: [],
  blockers: [],
  activity: [],
  deliveries: [],
};

const navItems = [
  { id: "construction", label: "Construccion" },
  { id: "queue", label: "Cola" },
  { id: "approvals", label: "Aprobaciones" },
  { id: "blockers", label: "Bloqueos" },
  { id: "deliveries", label: "Entregas" },
  { id: "audit", label: "Auditoria" },
  { id: "traceability", label: "Trazabilidad" },
];

const promptExamples = [
  "Que diriges ahora?",
  "Que esta detenido?",
  "Que entregaste?",
  "Que debo aprobar?",
  "Que sigue?",
];

const CHAT_SESSION_ID = "ceo-human-cabin";
const CHAT_SESSION_STORAGE_KEY = "forja_human_cabin_session_id_v1";
const CHAT_STORAGE_KEY = "forja_human_cabin_chat_v1";
const DEFAULT_CHAT_MESSAGES = [
  { role: "forja", text: "CEO, aqui FORJA. Estoy lista para ordenar la obra, leer memoria real y enviar trabajo al Local Agent." },
];

function delay(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function loadStoredChatMessages() {
  if (typeof window === "undefined") return DEFAULT_CHAT_MESSAGES;
  try {
    const stored = JSON.parse(window.localStorage.getItem(CHAT_STORAGE_KEY) || "[]");
    if (Array.isArray(stored) && stored.length) return stored.slice(-60);
  } catch {
    return DEFAULT_CHAT_MESSAGES;
  }
  return DEFAULT_CHAT_MESSAGES;
}

function loadChatSessionId() {
  if (typeof window === "undefined") return CHAT_SESSION_ID;
  const stored = window.localStorage.getItem(CHAT_SESSION_STORAGE_KEY);
  if (stored && /^[A-Za-z0-9_.-]{3,120}$/.test(stored)) return stored;
  window.localStorage.setItem(CHAT_SESSION_STORAGE_KEY, CHAT_SESSION_ID);
  return CHAT_SESSION_ID;
}

function historyMessages(payload) {
  const messages = payload?.messages;
  if (!Array.isArray(messages) || !messages.length) return [];
  return messages
    .filter((message) => message?.text && ["user", "forja"].includes(message.role))
    .map((message) => ({ role: message.role, text: message.text }))
    .slice(-60);
}

function normalizedStatus(status) {
  return String(status || "UNKNOWN").toUpperCase();
}

function chatStatusLabel(status) {
  const value = normalizedStatus(status);
  if (value === "NOT_CONFIGURED") return "OPENROUTER CHECK";
  if (value === "MISSING_CREDENTIALS") return "OPENROUTER CHECK";
  return value;
}

function toneForStatus(status) {
  const value = normalizedStatus(status);
  if (["OPERATIONAL", "READY", "OK", "COMPLETED"].includes(value)) return "good";
  if (["DEGRADED", "PENDING", "AWAITING"].includes(value)) return "warning";
  if (["BLOCKED", "ERROR", "FAILED"].includes(value)) return "danger";
  return "unknown";
}

function hasUsableMetric(metric) {
  if (!metric) return false;
  if (normalizedStatus(metric.status) === "UNKNOWN") return false;
  if (metric.value === undefined || metric.value === null || metric.value === "") return false;
  if (metric.value === "--" || metric.value === NO_DATA) return false;
  return true;
}

function metricByLabel(snapshot, label) {
  return (snapshot.metrics || []).find((metric) => metric.label === label) || null;
}

function displayMetric(metric) {
  return hasUsableMetric(metric) ? String(metric.value) : NO_DATA;
}

function humanMetricDetail(label, metric) {
  if (label.includes("Apps")) return hasUsableMetric(metric) ? "Obra registrada." : "Esperando cola real.";
  if (label.includes("Tareas")) return hasUsableMetric(metric) ? "Actividad verificada." : "Sin tarea verificable.";
  if (label.includes("Aprobaciones")) return metricIsZero(metric) ? "Sin decisiones pendientes." : "Sin registro confiable.";
  if (label.includes("Bloqueos")) return metricIsZero(metric) ? "Sin bloqueos criticos." : "Sin registro confiable.";
  return hasUsableMetric(metric) ? "Dato verificado." : NO_DATA;
}

function metricIsZero(metric) {
  return hasUsableMetric(metric) && String(metric.value) === "0";
}

function describeList(items, formatter) {
  if (!items || !items.length) return NO_DATA;
  return items.map(formatter).join(" | ");
}

function nextKnownStep(flow) {
  const actionable = (flow || []).find((item) => normalizedStatus(item.status) !== "COMPLETED");
  if (!actionable || normalizedStatus(actionable.status) === "UNKNOWN") return NO_DATA;
  return `${actionable.stage}: ${actionable.detail || actionable.status}`;
}

function buildDirectorLines(snapshot, runtime) {
  const queue = snapshot.constructionQueue || [];
  const approvals = snapshot.approvals || [];
  const blockers = snapshot.blockers || [];
  const deliveries = snapshot.deliveries || [];
  const appsMetric = metricByLabel(snapshot, "Apps en construccion");
  const tasksMetric = metricByLabel(snapshot, "Tareas activas");
  const blockersMetric = metricByLabel(snapshot, "Bloqueos");
  const approvalsMetric = metricByLabel(snapshot, "Aprobaciones pendientes");
  const deliveriesMetric = metricByLabel(snapshot, "Entregas listas");

  const constructionText = queue.length
    ? `CEO, dirijo ${describeList(queue, (item) => `${item.app || "app"}: ${item.task || NO_DATA}`)}.`
    : hasUsableMetric(tasksMetric) && String(tasksMetric.value) === "0"
      ? "CEO, sin construccion activa. Esperando cola real."
      : "CEO, esperando cola real. Aun no tengo evidencia de obra activa.";

  const deliveryText = deliveries.length
    ? `CEO, entregas listas: ${describeList(deliveries, (item) => item.name || item.path || NO_DATA)}.`
    : hasUsableMetric(deliveriesMetric) && String(deliveriesMetric.value) === "0"
      ? "Sin entregas verificadas."
      : "Sin entregas verificadas. Aun no tengo evidencia de cierre.";

  const blockerText = blockers.length
    ? `CEO, bloqueos activos: ${describeList(blockers, (item) => item.cause || item.id || NO_DATA)}.`
    : metricIsZero(blockersMetric)
      ? "Sin bloqueos criticos."
      : "Bloqueos no verificados. Falta registro confiable.";

  const approvalText = approvals.length
    ? `CEO, ${approvals.length} decision(es) esperan tu criterio: ${describeList(approvals, (item) => item.title || item.requiredDecision || NO_DATA)}.`
    : metricIsZero(approvalsMetric)
      ? "Sin decisiones pendientes por tu parte."
      : "Aprobaciones no verificadas. Falta registro confiable.";

  const nextText = nextKnownStep(snapshot.flow || []);

  return [
    { key: "build", label: "Construccion", text: constructionText, status: appsMetric?.status || tasksMetric?.status || "UNKNOWN" },
    { key: "done", label: "Entregas", text: deliveryText, status: deliveriesMetric?.status || "UNKNOWN" },
    { key: "block", label: "Bloqueos", text: blockerText, status: blockersMetric?.status || "UNKNOWN" },
    { key: "approval", label: "Aprobaciones", text: approvalText, status: approvalsMetric?.status || "UNKNOWN" },
    { key: "next", label: "Siguiente paso", text: nextText === NO_DATA ? "Esperando auditoria o cola real." : nextText, status: nextText === NO_DATA ? "UNKNOWN" : "PENDING" },
    { key: "status", label: "Estado", text: runtime.globalStatus === "OPERATIONAL" ? "Operativa. Lista para coordinar la obra." : "Esperando confirmacion del runtime.", status: runtime.globalStatus },
  ];
}

function StatusPill({ status }) {
  return <span className={`status-pill ${toneForStatus(status)}`}>{normalizedStatus(status)}</span>;
}

function MicIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" focusable="false">
      <path d="M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3Z" />
      <path d="M6 11v1a6 6 0 0 0 12 0v-1" />
      <path d="M12 18v3" />
      <path d="M9 21h6" />
    </svg>
  );
}

function SidebarMetric({ label, metric, compact }) {
  return (
    <div className={`side-metric ${compact ? "mobile-visible" : ""}`}>
      <span>{label}</span>
      <strong>{displayMetric(metric)}</strong>
      <small>{humanMetricDetail(label, metric)}</small>
    </div>
  );
}

function LocalAgentStatus({ localAgent }) {
  const agents = localAgent?.agents || {};
  const tasks = localAgent?.tasks || {};
  const latestResult = (localAgent?.latest_results || [])[0];
  const online = Number(agents.online || 0);
  const stale = Number(agents.stale || 0);
  const status = online > 0 ? "OPERATIONAL" : stale > 0 ? "PENDING" : "UNKNOWN";
  const statusText = online > 0
    ? "Agente online: SI"
    : agents.status_message || "No hay agente local conectado en este momento.";

  return (
    <section className="local-agent-status" aria-label="Estado Local Agent">
      <div>
        <span>Local Agent</span>
        <strong>{statusText}</strong>
        <p>Ultimo heartbeat: {agents.last_heartbeat_at || NO_DATA}</p>
        <p>Tarea reciente: {latestResult?.title || latestResult?.task_id || "sin tarea reciente"}</p>
        <p>Cola: {tasks.queued || 0} / Running: {tasks.running || 0} / Completed: {tasks.completed || 0}</p>
      </div>
      <StatusPill status={status} />
    </section>
  );
}

function DirectorLine({ line }) {
  return (
    <article className="director-line">
      <div>
        <span>{line.label}</span>
        <strong>{line.text || NO_DATA}</strong>
      </div>
      <StatusPill status={line.status} />
    </article>
  );
}

function EmptyState({
  title = NO_DATA,
  detail = "CEO, aun no tengo evidencia real para esta vista.",
  nextStep = "Conectar datos reales antes de decidir.",
}) {
  return (
    <div className="empty-state">
      <span>FORJA dice</span>
      <strong>{title}</strong>
      <p>{detail}</p>
      <div className="next-step">
        <small>Siguiente paso recomendado</small>
        <em>{nextStep}</em>
      </div>
      <button type="button" disabled className="premium-action disabled">
        Esperando evidencia real
      </button>
    </div>
  );
}

function ExecutiveAnswer({ question, line }) {
  return (
    <article className="answer-row">
      <div>
        <span>{question}</span>
        <strong>{line?.text || NO_DATA}</strong>
      </div>
      <StatusPill status={line?.status || "UNKNOWN"} />
    </article>
  );
}

function QueueView({ queue }) {
  if (!queue.length) {
    return (
      <EmptyState
        title="Sin construccion activa."
        detail="No hay tareas reales de construccion registradas."
        nextStep="Conectar cola real o ejecutar auditoria."
      />
    );
  }

  return (
    <div className="list-stack">
      {queue.map((item) => (
        <article className="data-row" key={`${item.app}-${item.task}`}>
          <div>
            <span>{item.app || NO_DATA}</span>
            <strong>{item.task || NO_DATA}</strong>
            <p>{item.nextAction || NO_DATA}</p>
          </div>
          <div className="row-meta">
            <StatusPill status={item.status} />
            <small>Prioridad: {item.priority || NO_DATA}</small>
            <small>Responsable: {item.owner || NO_DATA}</small>
            <small>Progreso: {item.progress || NO_DATA}</small>
            <small>Bloqueo: {item.blocker || NO_DATA}</small>
          </div>
        </article>
      ))}
    </div>
  );
}

function ApprovalsView({ approvals }) {
  if (!approvals.length) {
    return (
      <EmptyState
        title="Sin decisiones pendientes."
        detail="No hay aprobaciones humanas esperando tu criterio."
        nextStep="Crear una tarea gobernada cuando exista cola real."
      />
    );
  }

  return (
    <div className="list-stack">
      {approvals.map((approval) => (
        <article className="data-row" key={approval.id || approval.title}>
          <div>
            <span>{approval.risk || "RISK UNKNOWN"}</span>
            <strong>{approval.title || NO_DATA}</strong>
            <p>{approval.impact || NO_DATA}</p>
          </div>
          <div className="row-meta">
            <StatusPill status={approval.status || "PENDING"} />
            <small>{approval.requiredDecision || NO_DATA}</small>
          </div>
        </article>
      ))}
    </div>
  );
}

function BlockersView({ blockers, blockerMetric }) {
  if (!blockers.length) {
    const hasZeroBlockers = metricIsZero(blockerMetric);
    return (
      <EmptyState
        title={hasZeroBlockers ? "Sin bloqueos criticos." : NO_DATA}
        detail={hasZeroBlockers ? "La ruta esta despejada." : "No tengo detalle confiable de bloqueos."}
        nextStep={hasZeroBlockers ? "Mantener vigilancia." : "Conectar registro de bloqueos."}
      />
    );
  }

  return (
    <div className="list-stack">
      {blockers.map((blocker) => (
        <article className="data-row" key={blocker.id || blocker.cause}>
          <div>
            <span>{blocker.app || NO_DATA}</span>
            <strong>{blocker.id || blocker.title || NO_DATA}</strong>
            <p>{blocker.cause || NO_DATA}</p>
          </div>
          <div className="row-meta">
            <StatusPill status={blocker.severity || "BLOCKED"} />
            <small>{blocker.recommendation || NO_DATA}</small>
          </div>
        </article>
      ))}
    </div>
  );
}

function DeliveriesView({ deliveries }) {
  if (!deliveries.length) {
    return (
      <EmptyState
        title="Sin entregas verificadas."
        detail="No hay artefactos, reportes o certificaciones registradas."
        nextStep="Completar una tarea real para generar evidencia."
      />
    );
  }

  return (
    <div className="list-stack">
      {deliveries.map((delivery) => (
        <article className="data-row" key={delivery.path || delivery.name}>
          <div>
            <span>{delivery.status || "STATUS UNKNOWN"}</span>
            <strong>{delivery.name || NO_DATA}</strong>
            <p>{delivery.path || NO_DATA}</p>
          </div>
          <StatusPill status={delivery.status} />
        </article>
      ))}
    </div>
  );
}

function AuditView({ activity, flow }) {
  const hasActivity = activity.length > 0;
  const hasFlow = flow.length > 0;

  if (!hasActivity && !hasFlow) {
    return (
      <EmptyState
        title="Sin auditoria visible."
        detail="El runtime no entrego eventos ni flujo verificable."
        nextStep="Conectar auditoria real."
      />
    );
  }

  return (
    <div className="split-stack">
      <section>
        <h3>Flujo Auditoria / FORJA / Code</h3>
        {hasFlow ? (
          <div className="flow-list">
            {flow.map((step) => (
              <article key={step.stage}>
                <span>{step.stage}</span>
                <StatusPill status={step.status} />
                <p>{step.detail || NO_DATA}</p>
              </article>
            ))}
          </div>
        ) : (
          <EmptyState />
        )}
      </section>
      <section>
        <h3>Actividad</h3>
        {hasActivity ? (
          <div className="event-list">
            {activity.map((event) => (
              <article key={`${event.time}-${event.event}`}>
                <time>{event.time || NO_DATA}</time>
                <strong>{event.event || NO_DATA}</strong>
                <span>{event.app || NO_DATA}</span>
                <p>{event.result || NO_DATA}</p>
              </article>
            ))}
          </div>
        ) : (
          <EmptyState />
        )}
      </section>
    </div>
  );
}

function TraceabilityView({ runtime }) {
  const provenance = runtime.endpoints.provenance.data;

  if (!provenance) {
    return (
      <EmptyState
        title="Sin provenance visible."
        detail="El endpoint provenance no entrego datos para mostrar."
        nextStep="Verificar provenance antes de cualquier push o deploy."
      />
    );
  }

  return (
    <div className="trace-grid">
      <article>
        <span>Source</span>
        <strong>{provenance.source || NO_DATA}</strong>
      </article>
      <article>
        <span>Deploy target</span>
        <strong>{provenance.deployment_target || NO_DATA}</strong>
      </article>
      <article>
        <span>Governance</span>
        <strong>{provenance.governance_state || NO_DATA}</strong>
      </article>
      <article>
        <span>Data state</span>
        <strong>{provenance.data_state || NO_DATA}</strong>
      </article>
      <a className="premium-action link" href={apiUrl("/health")} target="_blank" rel="noreferrer">Abrir Health</a>
      <a className="premium-action link" href={apiUrl("/runtime/status")} target="_blank" rel="noreferrer">Abrir Runtime</a>
      <a className="premium-action link" href={apiUrl("/provenance")} target="_blank" rel="noreferrer">Abrir Provenance</a>
    </div>
  );
}

function ConstructionView({ lines }) {
  const byKey = Object.fromEntries(lines.map((line) => [line.key, line]));
  return (
    <div className="home-grid">
      <ExecutiveAnswer question="Que estoy construyendo" line={byKey.build} />
      <ExecutiveAnswer question="Que termine" line={byKey.done} />
      <ExecutiveAnswer question="Que me bloquea" line={byKey.block} />
      <ExecutiveAnswer question="Que necesito aprobar" line={byKey.approval} />
      <ExecutiveAnswer question="Que hare despues" line={byKey.next} />
    </div>
  );
}

function ChatForja({ snapshot, lines }) {
  const [input, setInput] = useState("");
  const [chatStatus, setChatStatus] = useState("UNKNOWN");
  const [sending, setSending] = useState(false);
  const [listening, setListening] = useState(false);
  const [voiceStatus, setVoiceStatus] = useState("");
  const [conversationId, setConversationId] = useState(loadChatSessionId);
  const [messages, setMessages] = useState(loadStoredChatMessages);
  const chatLogRef = useRef(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(CHAT_SESSION_STORAGE_KEY, conversationId);
  }, [conversationId]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(messages.slice(-60)));
  }, [messages]);

  useEffect(() => {
    const node = chatLogRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [messages, sending]);

  useEffect(() => {
    let alive = true;
    fetch(apiUrl("/api/chat"), { headers: { Accept: "application/json" } })
      .then((response) => response.json())
      .then((data) => {
        if (alive) setChatStatus(data.status === "ok" ? "ok" : data.provider_state || data.status || data.mode || "UNKNOWN");
      })
      .catch(() => {
        if (alive) setChatStatus("error");
      });

    fetch(apiUrl(`/api/chat/history?session_id=${encodeURIComponent(conversationId)}`), { headers: { Accept: "application/json" } })
      .then((response) => response.json())
      .then((data) => {
        const serverMessages = historyMessages(data);
        if (alive && serverMessages.length) {
          setMessages(serverMessages);
        }
      })
      .catch(() => {});

    return () => {
      alive = false;
    };
  }, [conversationId]);

  function contextPayload() {
    return JSON.stringify({
      globalStatus: normalizedStatus(lines.find((line) => line.key === "status")?.status),
      directorLines: lines.map((line) => ({
        label: line.label,
        status: line.status,
        text: line.text,
      })),
      snapshot: {
        constructionQueue: snapshot.constructionQueue || [],
        approvals: snapshot.approvals || [],
        blockers: snapshot.blockers || [],
        deliveries: snapshot.deliveries || [],
        flow: snapshot.flow || [],
        memory: snapshot.memory || {},
        localAgent: snapshot.localAgent || {},
      },
    });
  }

  function replyFromPayload(data) {
    if (data?.reply) return data.reply;
    if (data?.response) return data.response;
    if (data?.detail) return `FORJA no pudo completar la peticion: ${JSON.stringify(data.detail)}`;
    return "FORJA recibio la peticion, pero el backend no devolvio una respuesta conversacional.";
  }

  async function pollLocalAgentTask(taskId) {
    for (let attempt = 0; attempt < 18; attempt += 1) {
      await delay(5000);
      try {
        const response = await fetch(apiUrl(`/local-agent/tasks/${taskId}`), {
          headers: { Accept: "application/json" },
        });
      if (!response.ok) continue;
      const task = await response.json();
      if (["completed", "failed", "blocked", "cancelled", "rolled_back"].includes(task.status)) {
          const artifactPaths = (task.artifacts || [])
            .map((artifact) => artifact.local_path || artifact.name)
            .filter(Boolean)
            .join(", ");
          const result = task.result?.human_cabin_summary || task.result?.summary || `Tarea ${task.status}.`;
          setMessages((current) => [
            ...current,
            {
              role: "forja",
              text: `Local Agent ${task.status}: ${result}${artifactPaths ? ` Entregable: ${artifactPaths}.` : ""}`,
            },
          ]);
          return;
        }
      } catch {
        return;
      }
    }
  }

  async function submitPrompt(prompt, inputMode = "text") {
    const cleanPrompt = prompt.trim();
    if (!cleanPrompt) return;
    setMessages((current) => [...current, { role: "user", text: cleanPrompt }]);
    setInput("");
    setSending(true);
    try {
      const response = await fetch(apiUrl("/api/chat"), {
        method: "POST",
        headers: {
          "Accept": "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: cleanPrompt,
          app: "FORJA",
          session_id: conversationId,
          input_mode: inputMode,
          context: contextPayload(),
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(replyFromPayload(data));
      }
      setChatStatus(data.status === "ok" ? "ok" : data.provider_state || data.status || "UNKNOWN");
      setMessages((current) => [
        ...current,
        { role: "forja", text: replyFromPayload(data) },
      ]);
      if (data.conversation?.session_id && data.conversation.session_id !== conversationId) {
        setConversationId(data.conversation.session_id);
      }
      if (data.local_agent_task?.task_id) {
        pollLocalAgentTask(data.local_agent_task.task_id);
      }
    } catch (error) {
      setChatStatus("error");
      setMessages((current) => [
        ...current,
        { role: "forja", text: error.message || "FORJA no pudo contactar el backend de chat." },
      ]);
    } finally {
      setSending(false);
    }
  }

  function startVoiceInput() {
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Recognition) {
      setVoiceStatus("Microfono no disponible. Sigue por texto.");
      setMessages((current) => [
        ...current,
        { role: "forja", text: "Microfono no disponible en este navegador. Escribe el mensaje y sigo por texto." },
      ]);
      return;
    }
    if (listening) return;
    const recognition = new Recognition();
    recognition.lang = "es-ES";
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    recognition.onstart = () => {
      setListening(true);
      setVoiceStatus("Escuchando...");
    };
    recognition.onend = () => {
      setListening(false);
      setVoiceStatus("");
    };
    recognition.onerror = () => {
      setListening(false);
      setVoiceStatus("No pude tomar audio. Sigue por texto.");
      setMessages((current) => [
        ...current,
        { role: "forja", text: "No pude tomar audio ahora. Escribe el mensaje y sigo por texto." },
      ]);
    };
    recognition.onresult = (event) => {
      const transcript = event.results?.[0]?.[0]?.transcript || "";
      if (transcript.trim()) {
        setVoiceStatus("Mensaje de voz recibido.");
        submitPrompt(transcript, "voice");
      }
    };
    recognition.start();
  }

  return (
    <section className="chat-panel">
      <div className="chat-heading">
        <div className="forja-presence" aria-hidden="true">
          <span />
        </div>
        <div>
          <span>FORJA habla</span>
          <strong>Directora de construccion del ecosistema</strong>
        </div>
        <small>{chatStatusLabel(chatStatus)}</small>
      </div>
      <div className="director-feed">
        {lines.slice(0, 3).map((line) => (
          <DirectorLine key={line.key} line={line} />
        ))}
      </div>
      <div className="prompt-grid">
        {promptExamples.map((prompt) => (
          <button type="button" key={prompt} onClick={() => submitPrompt(prompt)}>
            {prompt}
          </button>
        ))}
      </div>
      <div className="chat-log" aria-live="polite" ref={chatLogRef}>
        {messages.slice(-20).map((message, index) => (
          <div className={`chat-message ${message.role}`} key={`${message.role}-${index}`}>
            {message.text}
          </div>
        ))}
      </div>
      <form
        className="chat-form"
        onSubmit={(event) => {
          event.preventDefault();
          submitPrompt(input);
        }}
      >
        <input value={input} onChange={(event) => setInput(event.target.value)} placeholder="Pregunta a FORJA" />
        <button
          type="button"
          className="voice-button"
          onClick={startVoiceInput}
          disabled={sending || listening}
          title="Dictar mensaje a FORJA"
          aria-label="Dictar mensaje a FORJA"
        >
          {listening ? "..." : <MicIcon />}
        </button>
        <button type="submit" disabled={!input.trim() || sending}>{sending ? "..." : "Enviar"}</button>
      </form>
      {voiceStatus ? <div className="voice-status" role="status">{voiceStatus}</div> : null}
    </section>
  );
}

function ActiveView({ activeView, snapshot, runtime, lines }) {
  const blockerMetric = metricByLabel(snapshot, "Bloqueos");
  const titles = {
    construction: ["Construccion", "FORJA dirige la obra del ecosistema"],
    queue: ["Cola", "Construcciones preparadas o en espera"],
    approvals: ["Aprobaciones", "Decisiones que requieren tu criterio"],
    blockers: ["Bloqueos", "Riesgos que detienen la obra"],
    deliveries: ["Entregas", "Evidencia verificable lista"],
    audit: ["Auditoria", "Flujo y actividad registrada"],
    traceability: ["Trazabilidad", "Origen, limites y evidencia"],
  };

  const [eyebrow, title] = titles[activeView] || titles.construction;

  return (
    <section className="workspace-panel">
      <header className="workspace-heading">
        <span>{eyebrow}</span>
        <h1>{title}</h1>
      </header>
      {activeView === "construction" ? <ConstructionView lines={lines} /> : null}
      {activeView === "queue" ? <QueueView queue={snapshot.constructionQueue || []} /> : null}
      {activeView === "approvals" ? <ApprovalsView approvals={snapshot.approvals || []} /> : null}
      {activeView === "blockers" ? <BlockersView blockers={snapshot.blockers || []} blockerMetric={blockerMetric} /> : null}
      {activeView === "deliveries" ? <DeliveriesView deliveries={snapshot.deliveries || []} /> : null}
      {activeView === "audit" ? <AuditView activity={snapshot.activity || []} flow={snapshot.flow || []} /> : null}
      {activeView === "traceability" ? <TraceabilityView runtime={runtime} /> : null}
    </section>
  );
}

function App() {
  const runtime = useForjaRuntime();
  const [activeView, setActiveView] = useState("construction");
  const snapshot = runtime.endpoints.runtime.data?.snapshot || fallbackSnapshot;
  const appsMetric = metricByLabel(snapshot, "Apps en construccion");
  const tasksMetric = metricByLabel(snapshot, "Tareas activas");
  const blockersMetric = metricByLabel(snapshot, "Bloqueos");
  const approvalsMetric = metricByLabel(snapshot, "Aprobaciones pendientes");
  const lines = useMemo(() => buildDirectorLines(snapshot, runtime), [snapshot, runtime]);

  const globalCopy = useMemo(() => {
    if (runtime.globalStatus === "OPERATIONAL") return "Operativa y en guardia. Lista para ordenar la obra.";
    if (runtime.globalStatus === "DEGRADED") return "Disponible, con sincronizacion parcial.";
    return "Estoy esperando confirmacion completa del runtime antes de dirigir la obra.";
  }, [runtime.globalStatus]);

  return (
    <div className="forja-v5-shell" data-ui-state="LOCKED_UI_APPROVED" data-approved-commit="75cf0b7">
      <aside className="cabin-sidebar">
        <div className="brand-block">
          <div className="brand-mark">F</div>
          <div>
            <span>FORJA</span>
            <strong>Directora de Construccion</strong>
          </div>
        </div>

        <section className="global-card">
          <div>
            <span>Estado Global</span>
            <strong>{runtime.globalStatus}</strong>
            <p>{globalCopy}</p>
          </div>
          <StatusPill status={runtime.globalStatus} />
        </section>

        <div className="mobile-director-inline">
          <ChatForja snapshot={snapshot} lines={lines} />
        </div>

        <div className="side-metrics">
          <SidebarMetric label="Apps activas" metric={appsMetric} compact />
          <SidebarMetric label="Tareas activas" metric={tasksMetric} />
          <SidebarMetric label="Aprobaciones" metric={approvalsMetric} compact />
          <SidebarMetric label="Bloqueos" metric={blockersMetric} compact />
        </div>

        <LocalAgentStatus localAgent={snapshot.localAgent || {}} />

        <nav className="cabin-nav" aria-label="Navegacion FORJA">
          {navItems.map((item) => (
            <button
              type="button"
              key={item.id}
              className={activeView === item.id ? "active" : ""}
              onClick={() => setActiveView(item.id)}
            >
              {item.label}
            </button>
          ))}
        </nav>

        <details className="mobile-nav">
          <summary>Vistas</summary>
          <div>
            {navItems.map((item) => (
              <button
                type="button"
                key={item.id}
                className={activeView === item.id ? "active" : ""}
                onClick={() => setActiveView(item.id)}
              >
                {item.label}
              </button>
            ))}
          </div>
        </details>
      </aside>

      <main className="cabin-main">
        <div className="topline">
          <span>Revision local</span>
          <strong>{runtime.lastSync ? `Sync ${runtime.lastSync}` : "Sync pendiente"}</strong>
        </div>
        <ActiveView activeView={activeView} snapshot={snapshot} runtime={runtime} lines={lines} />
      </main>

      <aside className="director-panel">
        <ChatForja snapshot={snapshot} lines={lines} />
      </aside>

      <details className="mobile-workspace">
        <summary>Abrir vista activa: {navItems.find((item) => item.id === activeView)?.label}</summary>
        <ActiveView activeView={activeView} snapshot={snapshot} runtime={runtime} lines={lines} />
      </details>
    </div>
  );
}

export default App;
