from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
import uuid
from typing import Any

from app.core.audit import append_audit_event, utc_now
from app.core.storage import store
from app.services.ecosystem_memory_service import ecosystem_memory_service
from app.services.local_agent_service import local_agent_service


DEFAULT_SESSION_ID = "ceo-human-cabin"
DELIVERIES_ROOT = r"D:\ECOSYSTEM\DELIVERIES"
REPORT_FILE_RE = re.compile(r"\b([A-Za-z0-9][A-Za-z0-9_.-]{0,120}\.md)\b", re.IGNORECASE)
APP_NAME_RE = re.compile(
    r"(?:app|aplicacion)\s+(?:llamada|llamado|que\s+se\s+llame|con\s+nombre)\s+['\"]?([^?!\n\r]{2,100})",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class IntentResult:
    name: str
    confidence: float
    app_name: str | None
    desired_output: str | None
    requires_local_agent: bool
    requires_confirmation: bool
    actions: list[str]

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "confidence": self.confidence,
            "app_name": self.app_name,
            "desired_output": self.desired_output,
            "requires_local_agent": self.requires_local_agent,
            "requires_confirmation": self.requires_confirmation,
            "actions": self.actions,
        }


class NaturalExecutionService:
    def __init__(self) -> None:
        self._conversation_store = store("human_cabin_conversations")

    def handle_message(
        self,
        message: str,
        *,
        session_id: str = DEFAULT_SESSION_ID,
        input_mode: str = "text",
        provider_state: str = "unknown",
        openrouter_record: dict | None = None,
    ) -> dict:
        clean_message = " ".join(message.strip().split())
        intent = self.interpret(clean_message)
        memory = ecosystem_memory_service.snapshot()
        delivery = self._delivery_for_intent(intent)
        local_agent_task = None

        if self._asks_for_last_file(clean_message):
            reply = self._last_file_reply(session_id)
            intent = IntentResult(
                "pedir_entrega",
                0.96,
                None,
                None,
                False,
                False,
                ["Ver archivo", "Revisar entregables", "Enviar otra tarea"],
            )
        elif intent.name == "generar_reporte":
            local_agent_task = self._create_local_agent_task(clean_message, intent, delivery)
            reply = self._report_task_reply(local_agent_task, delivery)
        else:
            reply = self._executive_reply(clean_message, intent, memory, delivery)

        entry = self._record_interaction(
            session_id,
            clean_message,
            reply,
            intent,
            local_agent_task,
            delivery,
            input_mode,
            provider_state,
            openrouter_record,
        )
        append_audit_event(
            "human_cabin.natural_execution_message",
            "ceo",
            {
                "session_id": session_id,
                "intent": intent.name,
                "input_mode": input_mode,
                "task_id": (local_agent_task or {}).get("task_id"),
                "delivery_path": (delivery or {}).get("path"),
            },
            risk="low",
        )
        return {
            "reply": reply,
            "status": "ok",
            "provider": "openrouter",
            "provider_state": provider_state,
            "intent": intent.as_dict(),
            "local_agent_task": local_agent_task,
            "delivery": delivery,
            "conversation": {"session_id": session_id, "persisted": True, "entry_id": entry["id"]},
            "response_received": bool(openrouter_record and openrouter_record.get("status") == "completed"),
            "openrouter_status": (openrouter_record or {}).get("status", "not_called"),
            "fallback_triggered": False,
            "secrets_exposed": False,
        }

    def interpret(self, message: str) -> IntentResult:
        normalized = self._normalize(message)
        filename = self._filename(message)
        app_name = self._app_name(message)
        actions = ["Crear tarea", "Pedir mas datos", "Guardar idea", "Preparar arquitectura", "Enviar al Local Agent"]

        if self._asks_for_last_file(message):
            return IntentResult("pedir_entrega", 0.96, app_name, filename, False, False, ["Ver archivo", "Revisar entregables"])
        if app_name and any(word in normalized for word in ["crear", "hacer", "construir", "preparar"]):
            return IntentResult("crear_app", 0.94, app_name, filename, True, True, actions)
        if filename or (any(word in normalized for word in ["genera", "generar", "crea", "crear", "prepara"]) and any(word in normalized for word in ["inventario", "reporte", "archivo", "guardar", "guardalo"])):
            return IntentResult("generar_reporte", 0.93, app_name, filename or "FORJA_LOCAL_AGENT_REPORT.md", True, False, ["Crear tarea", "Enviar al Local Agent", "Mostrar resultado"])
        if "auditar" in normalized or "auditoria" in normalized:
            return IntentResult("auditar_app", 0.86, app_name, filename, True, True, ["Preparar auditoria", "Crear tarea", "Enviar al Local Agent"])
        if any(word in normalized for word in ["modificar", "corregir", "cambiar", "implementar"]):
            return IntentResult("modificar_app", 0.86, app_name, filename, True, True, ["Preparar rama", "Crear backup", "Pedir aprobacion"])
        if "entrega" in normalized or "entregable" in normalized:
            return IntentResult("preparar_entrega", 0.82, app_name, filename, True, True, ["Preparar entrega", "Validar evidencia"])
        if any(word in normalized for word in ["aplicaciones", "apps", "ecosistema", "estado actual", "resume"]):
            return IntentResult("revisar_ecosistema", 0.82, app_name, filename, False, False, ["Ver estado", "Generar inventario"])
        if any(word in normalized for word in ["estado", "bloqueos", "activas"]):
            return IntentResult("pedir_estado", 0.78, app_name, filename, False, False, ["Ver estado", "Crear tarea si hace falta"])
        if any(word in normalized for word in ["siguiente", "que sigue", "proximo"]):
            return IntentResult("pedir_siguiente_paso", 0.78, app_name, filename, False, False, ["Ver siguiente paso", "Preparar tarea"])
        if any(word in normalized for word in ["build", "test", "prueba", "diagnostico", "tecnico"]):
            return IntentResult("pedir_construccion_tecnica", 0.78, app_name, filename, True, True, ["Crear tarea tecnica", "Pedir aprobacion"])
        if any(word in normalized for word in ["hola", "buenas", "forja"]):
            return IntentResult("saludo", 0.72, app_name, filename, False, False, ["Revisar ecosistema", "Crear tarea"])
        return IntentResult("desconocida", 0.45, app_name, filename, False, False, ["Aclarar objetivo", "Guardar idea"])

    def history(self, session_id: str = DEFAULT_SESSION_ID, limit: int = 60) -> dict:
        entries = [entry for entry in self._conversation_store.read([]) if entry.get("session_id") == session_id]
        entries = entries[-limit:]
        messages: list[dict[str, Any]] = []
        for entry in entries:
            messages.append({"role": "user", "text": entry.get("user_message", ""), "timestamp": entry.get("created_at")})
            messages.append({"role": "forja", "text": entry.get("forja_reply", ""), "timestamp": entry.get("created_at")})
        return {"session_id": session_id, "entries": entries, "messages": messages[-limit:], "persisted": True}

    def _executive_reply(self, message: str, intent: IntentResult, memory: dict, delivery: dict | None) -> str:
        app = (intent.app_name or "FORJA").upper()
        if intent.name == "crear_app":
            return (
                f"CEO, entendido. Para construir {app} necesito definir 5 cosas:\n"
                "1. objetivo\n"
                "2. usuarios\n"
                "3. entradas de datos\n"
                "4. salidas esperadas\n"
                "5. nivel de automatizacion\n\n"
                f"Puedo preparar ahora una tarea para el Local Agent para crear el primer documento tecnico de {app} "
                "y dejarlo en entregables.\n\n"
                "Acciones disponibles: Crear tarea, Pedir mas datos, Guardar idea, Preparar arquitectura, Enviar al Local Agent."
            )
        if intent.name == "saludo":
            return "CEO, aqui FORJA. Estoy lista para ordenar la obra, leer memoria real y enviar trabajo al Local Agent cuando me des una instruccion ejecutable."
        if intent.name in {"revisar_ecosistema", "pedir_estado"}:
            return self._ecosystem_reply(memory)
        if intent.name == "pedir_siguiente_paso":
            priorities = memory.get("priorities") or []
            next_step = priorities[0] if priorities else "definir una tarea verificable y enviarla al Local Agent."
            return f"CEO, el siguiente paso real es: {next_step}"
        if intent.name in {"auditar_app", "modificar_app", "preparar_entrega", "pedir_construccion_tecnica"}:
            return (
                "CEO, puedo convertir eso en una tarea gobernada para el Local Agent. "
                "Antes de ejecutar cambios necesito objetivo exacto, repositorio afectado y aprobacion humana si modifica codigo."
            )
        return "CEO, recibido. Puedo convertir tu idea en tarea, guardarla como entrega o pedirte los datos minimos para construirla sin inventar."

    def _ecosystem_reply(self, memory: dict) -> str:
        apps = self._join(memory.get("registered_apps") or [])
        active = self._join(memory.get("active_apps") or [])
        missing = self._join(memory.get("apps_missing_from_primary_memory") or [])
        construction = self._join(memory.get("construction") or [])
        priorities = self._join(memory.get("priorities") or [])
        blockers = self._join(memory.get("blockers") or [])
        return (
            f"CEO, memoria conectada. Aplicaciones registradas: {apps}. "
            f"Activas: {active}. Faltan en memoria maestra: {missing}. "
            f"Estamos construyendo: {construction}. Prioridades: {priorities}. Bloqueos: {blockers}."
        )

    def _create_local_agent_task(self, message: str, intent: IntentResult, delivery: dict | None) -> dict:
        filename = intent.desired_output or "FORJA_LOCAL_AGENT_REPORT.md"
        delivery = delivery or self._delivery_for_filename("FORJA", filename)
        task = local_agent_service.create_task(
            {
                "instruction": (
                    f"Generar {filename} usando memoria real de docs/ecosystem-memory. "
                    f"Entregar al CEO en {delivery['path']}. "
                    f"Solicitud original desde Human Cabin: {message}"
                ),
                "title": f"Generar {filename}",
                "requested_by": "ceo",
                "source": "human_cabin_chat",
                "priority": "high",
                "target": {
                    "workspace_id": "ecosystem",
                    "repo_ids": ["forja"],
                    "paths": ["docs/ecosystem-memory", filename],
                    "delivery_owner": "CEO",
                    "delivery_app": delivery["app"],
                    "delivery_root": DELIVERIES_ROOT,
                    "delivery_path": delivery["path"],
                },
                "desired_output": filename,
            }
        )
        if task.get("status") == "awaiting_human_approval" and not task.get("policy", {}).get("requires_critical_approval"):
            task = local_agent_service.approve_task(
                task["task_id"],
                {
                    "approved_by": "ceo",
                    "reason": "Aprobacion humana emitida desde Human Cabin chat para generar el reporte solicitado.",
                    "action": "report_generation",
                    "exact_target": {"filename": filename, "delivery_path": delivery["path"], "owner": "CEO"},
                },
            )
        return {
            "task_id": task.get("task_id"),
            "title": task.get("title"),
            "status": task.get("status"),
            "risk_level": task.get("risk_level"),
            "task_type": task.get("task_type"),
            "desired_output": filename,
            "delivery_path": delivery["path"],
        }

    def _report_task_reply(self, local_agent_task: dict, delivery: dict | None) -> str:
        path = (delivery or {}).get("path") or local_agent_task.get("delivery_path")
        return (
            "CEO, tarea creada. La estoy enviando al agente local. "
            f"Cuando termine, el resultado quedara visible en Human Cabin y el archivo quedara en: {path}."
        )

    def _record_interaction(
        self,
        session_id: str,
        message: str,
        reply: str,
        intent: IntentResult,
        task: dict | None,
        delivery: dict | None,
        input_mode: str,
        provider_state: str,
        openrouter_record: dict | None,
    ) -> dict:
        entry = {
            "id": f"chat-{uuid.uuid4()}",
            "session_id": session_id,
            "created_at": utc_now(),
            "input_mode": input_mode,
            "user_message": message,
            "forja_reply": reply,
            "intent": intent.as_dict(),
            "task": task,
            "delivery": delivery,
            "provider": "openrouter",
            "provider_state": provider_state,
            "openrouter_status": (openrouter_record or {}).get("status", "not_called"),
            "command_id": (openrouter_record or {}).get("id"),
        }
        self._conversation_store.update([], lambda entries: self._append_limited(entries, entry))
        return entry

    def _append_limited(self, entries: list[dict], entry: dict) -> dict:
        entries.append(entry)
        del entries[:-200]
        return entry

    def _last_file_reply(self, session_id: str) -> str:
        delivery = self._latest_delivery(session_id)
        if not delivery:
            return "CEO, no tengo un archivo entregado verificado todavia. Puedo crear una tarea para generarlo ahora."
        status = delivery.get("status")
        path = delivery.get("path")
        if status and status != "completed":
            return f"CEO, la entrega esta registrada pero aun no esta cerrada. Ruta prevista: {path}. Estado: {status}."
        return f"CEO, el archivo quedo aqui: {path}."

    def _latest_delivery(self, session_id: str) -> dict | None:
        entries = [entry for entry in self._conversation_store.read([]) if entry.get("session_id") == session_id]
        for entry in reversed(entries):
            delivery = entry.get("delivery") or {}
            task_ref = entry.get("task") or {}
            task_id = task_ref.get("task_id")
            if task_id:
                task = local_agent_service.get_task(task_id)
                if task:
                    artifact = self._visible_artifact(task)
                    if artifact:
                        return {"path": artifact.get("local_path"), "status": task.get("status"), "task_id": task_id}
                    if delivery.get("path"):
                        return {"path": delivery["path"], "status": task.get("status"), "task_id": task_id}
            if delivery.get("path"):
                return {"path": delivery["path"], "status": "pending", "task_id": task_id}
        for task in reversed(local_agent_service.list_tasks(limit=50)):
            target = task.get("target") or {}
            path = target.get("delivery_path")
            if path:
                artifact = self._visible_artifact(task)
                return {"path": (artifact or {}).get("local_path") or path, "status": task.get("status"), "task_id": task.get("task_id")}
        return None

    def _visible_artifact(self, task: dict) -> dict | None:
        artifacts = task.get("artifacts") or []
        target_path = (task.get("target") or {}).get("delivery_path")
        desired_output = task.get("desired_output")
        for artifact in artifacts:
            if not artifact.get("visible_in_human_cabin") or not artifact.get("local_path"):
                continue
            if artifact.get("local_path") == target_path or artifact.get("name") == desired_output:
                return artifact
        for artifact in reversed(artifacts):
            if artifact.get("visible_in_human_cabin") and artifact.get("local_path"):
                return artifact
        return None

    def _delivery_for_intent(self, intent: IntentResult) -> dict | None:
        if not intent.desired_output:
            return None
        return self._delivery_for_filename(intent.app_name or "FORJA", intent.desired_output)

    def _delivery_for_filename(self, app_name: str, filename: str) -> dict:
        app = self._safe_app_folder(app_name or "FORJA")
        clean_file = self._safe_filename(filename)
        return {"owner": "CEO", "app": app, "filename": clean_file, "path": f"{DELIVERIES_ROOT}\\{app}\\{clean_file}"}

    def _filename(self, message: str) -> str | None:
        match = REPORT_FILE_RE.search(message)
        if not match:
            return None
        return self._safe_filename(match.group(1))

    def _app_name(self, message: str) -> str | None:
        match = APP_NAME_RE.search(message)
        if not match:
            return None
        raw = match.group(1).strip().strip(" .'\"")
        raw = re.split(r"[.?!¡¿,\n\r]", raw, maxsplit=1)[0]
        raw = re.split(r"\s+(?:para|que|y|con|donde|cuando)\s+", raw, maxsplit=1, flags=re.IGNORECASE)[0]
        raw = raw.strip().strip(" .'\"")
        return raw[:80] if raw else None

    def _asks_for_last_file(self, message: str) -> bool:
        normalized = self._normalize(message)
        return any(phrase in normalized for phrase in ["donde quedo", "donde esta el archivo", "donde esta la entrega", "ruta del archivo"])

    def _safe_filename(self, filename: str) -> str:
        return re.sub(r"[^A-Za-z0-9_.-]", "", filename).strip(".") or "FORJA_LOCAL_AGENT_REPORT.md"

    def _safe_app_folder(self, app_name: str) -> str:
        normalized = unicodedata.normalize("NFKD", app_name).encode("ascii", "ignore").decode("ascii")
        safe = re.sub(r"[^A-Za-z0-9_-]+", "_", normalized.upper()).strip("_")
        return safe or "FORJA"

    def _normalize(self, value: str) -> str:
        folded = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
        return " ".join(folded.lower().split())

    def _join(self, items: list[str]) -> str:
        return ", ".join(items) if items else "no registrado"


natural_execution_service = NaturalExecutionService()
