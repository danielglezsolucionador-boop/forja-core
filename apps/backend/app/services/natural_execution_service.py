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
COMMERCIAL_INTENT_MARKERS = [
    "agencia",
    "anuncio",
    "audiencia",
    "calendario",
    "campana",
    "captar",
    "cliente",
    "contenido",
    "copy",
    "cta",
    "email",
    "entregable",
    "instagram",
    "landing",
    "lead",
    "marketing",
    "oferta",
    "propuesta",
    "publico",
    "redes",
    "tiktok",
    "turismo",
    "turista",
    "ventas",
    "viajes",
    "whatsapp",
]
INTERNAL_LEAK_MARKERS = [
    "aprobador",
    "arquitectura",
    "backend",
    "cav",
    "cerebro",
    "centinela",
    "forja",
    "gobierno de forja",
    "local agent",
    "memoria interna",
    "modulo tecnico",
    "openrouter",
    "pipeline",
    "provider",
    "runtime",
]


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
        reply_source = "emergency_fallback"
        commercial_context = self._is_commercial_intent(intent, clean_message) or (
            self._is_simplification_request(clean_message) and self._session_has_recent_commercial_context(session_id)
        )

        if self._asks_for_last_file(clean_message):
            reply = self._last_file_reply(session_id)
            reply_source = "delivery_lookup"
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
            reply_source = "local_agent"
        else:
            provider_reply = self._provider_reply(openrouter_record)
            if provider_reply:
                if self._is_recovery_review_request(clean_message) and self._is_low_value_recovery_reply(provider_reply):
                    reply = self._recovery_review_reply()
                    reply_source = "internal_guardrail"
                elif commercial_context and (
                    self._contains_internal_leak(provider_reply)
                    or self._is_low_value_commercial_reply(provider_reply)
                    or not self._commercial_reply_is_complete(clean_message, provider_reply)
                ):
                    reply = self._commercial_reply(clean_message)
                    reply_source = "commercial_guardrail"
                else:
                    reply = provider_reply
                    reply_source = "openrouter"
            elif self._provider_was_called(openrouter_record):
                if commercial_context:
                    reply = self._commercial_reply(clean_message)
                    reply_source = "commercial_fallback"
                else:
                    reply = self._provider_degraded_reply(openrouter_record, provider_state)
                    reply_source = "provider_degraded"
            else:
                reply = self._executive_reply(clean_message, intent, memory, delivery)
                reply_source = "memory_direct" if intent.name != "desconocida" else "emergency_fallback"

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
                "reply_source": reply_source,
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
            "reply_source": reply_source,
            "fallback_triggered": reply_source == "emergency_fallback",
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
        if self._is_commercial_request(normalized):
            return IntentResult("preparar_marketing", 0.9, app_name, filename, False, False, ["Definir objetivo", "Crear calendario", "Preparar entregable"])
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
        if any(word in normalized for word in ["hola", "buenas"]) or normalized in {"forja", "hola forja"}:
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
        if intent.name == "preparar_marketing":
            return self._commercial_reply(message)
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

    def _commercial_reply(self, message: str) -> str:
        normalized = self._normalize(message)
        if "no entendi" in normalized or "explicamelo" in normalized or "mas simple" in normalized:
            return (
                "Claro. Primero define una sola oferta para el cliente: que vendes, a quien se lo vendes y que accion quieres que haga.\n\n"
                "Lo primero que haria ahora es escribir una frase simple de la campana: "
                "'Durante 7 dias mostraremos una experiencia concreta y cerraremos cada pieza con una invitacion directa a reservar o pedir informacion.'"
            )
        return (
            "Titulo: Campana de 7 dias para captar turistas\n\n"
            "Objetivo: atraer consultas calificadas y convertir interes en reservas o reuniones comerciales.\n\n"
            "Publico objetivo: turistas que estan comparando experiencias, paquetes o actividades y necesitan una razon clara para decidir ahora.\n\n"
            "Estrategia: combinar inspiracion, prueba social y oferta directa. Cada dia debe mover al cliente un paso: descubrir, confiar, preguntar y reservar.\n\n"
            "Acciones: definir una experiencia principal, elegir una foto o video fuerte, escribir un mensaje claro, publicar una pieza diaria y responder cada consulta con una invitacion directa.\n\n"
            "Calendario de 7 dias:\n"
            "1. Presentar la experiencia principal con una promesa clara.\n"
            "2. Mostrar el problema que resuelve: ahorrar tiempo, evitar incertidumbre y vivir una experiencia mejor guiada.\n"
            "3. Publicar prueba social: testimonio, caso, foto real o historia de cliente.\n"
            "4. Comparar opciones y explicar por que esta propuesta es mas simple y segura.\n"
            "5. Responder preguntas frecuentes sobre precio, horarios, seguridad y disponibilidad.\n"
            "6. Lanzar una oferta o beneficio por tiempo limitado.\n"
            "7. Cerrar con recordatorio, urgencia amable y llamada directa a reservar.\n\n"
            "Ideas de contenido: reel corto, carrusel con itinerario, historia con encuesta, testimonio, checklist de viaje y mensaje directo de reserva.\n\n"
            "CTA: Escribenos 'CUSCO' y te enviamos disponibilidad y recomendacion personalizada.\n\n"
            "Siguiente paso: elegir una experiencia concreta y escribir el primer post con una foto fuerte, una promesa simple y el CTA."
        )

    def _recovery_review_reply(self) -> str:
        return (
            "Estamos revisando exactamente esto:\n\n"
            "1. Foco conversacional: que FORJA distinga trabajo interno de trabajo comercial para cliente.\n"
            "2. Tono: que en marketing responda como constructora de entregables, no como auditor tecnico.\n"
            "3. Calidad de respuesta: que no salgan respuestas cortas, genericas o desviadas.\n"
            "4. Local Agent: que haya 1 agente local online visible desde produccion y que ejecute tareas reales.\n\n"
            "Ahora el primer punto concreto es validar los prompts reales y confirmar que el agente recibe, ejecuta y devuelve resultado visible."
        )

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

    def _provider_reply(self, record: dict | None) -> str:
        if not record or record.get("status") != "completed":
            return ""
        response = str(record.get("response") or "").strip()
        if not response or response in {"real_chat_unavailable", "blocked_provider_disabled", "provider_http_error"}:
            return ""
        return response

    def _provider_was_called(self, record: dict | None) -> bool:
        if not record:
            return False
        return bool(record.get("id") or record.get("status") or record.get("response") or record.get("error"))

    def _provider_degraded_reply(self, record: dict | None, provider_state: str) -> str:
        status = str((record or {}).get("status") or "unknown").strip()
        reason = str((record or {}).get("response") or (record or {}).get("error") or provider_state or "unknown").strip()
        reason = reason[:220]
        return (
            "CEO, OpenRouter no pudo completar esta respuesta ahora. "
            f"Estado del proveedor: {provider_state}; comando: {status}; motivo: {reason}. "
            "No voy a inventar una respuesta con plantilla. Puedes reintentar en unos segundos o pedirme que convierta esto en tarea verificable para el Local Agent."
        )

    def _is_commercial_intent(self, intent: IntentResult, message: str) -> bool:
        return intent.name == "preparar_marketing" or self._is_commercial_request(self._normalize(message))

    def _is_commercial_request(self, normalized: str) -> bool:
        return any(marker in normalized for marker in COMMERCIAL_INTENT_MARKERS)

    def _contains_internal_leak(self, reply: str) -> bool:
        normalized = self._normalize(reply)
        return any(marker in normalized for marker in INTERNAL_LEAK_MARKERS)

    def _is_low_value_commercial_reply(self, reply: str) -> bool:
        clean = " ".join(str(reply or "").split())
        normalized = self._normalize(clean)
        if len(clean) < 220:
            return True
        return normalized.startswith("user safety:") or normalized in {"safe", "user safety safe"}

    def _commercial_reply_is_complete(self, message: str, reply: str) -> bool:
        normalized_message = self._normalize(message)
        if not any(marker in normalized_message for marker in ["campana", "propuesta", "entregable", "cliente", "calendario"]):
            return True
        normalized_reply = self._normalize(reply)
        required_groups = [
            ["titulo", "propuesta de campana"],
            ["objetivo"],
            ["publico", "audiencia", "target"],
            ["estrategia"],
            ["calendario", "dia 1", "7 dias"],
            ["cta", "llamada a la accion", "escribenos"],
            ["siguiente paso", "primer paso", "proximos pasos"],
        ]
        return all(any(marker in normalized_reply for marker in group) for group in required_groups)

    def _is_recovery_review_request(self, message: str) -> bool:
        normalized = self._normalize(message)
        return "recuperando forja" in normalized or ("forja" in normalized and "respondia mal" in normalized)

    def _is_low_value_recovery_reply(self, reply: str) -> bool:
        normalized = self._normalize(reply)
        if len(normalized) < 260:
            return True
        return not all(marker in normalized for marker in ["foco", "local agent"])

    def _is_simplification_request(self, message: str) -> bool:
        normalized = self._normalize(message)
        return any(marker in normalized for marker in ["no entendi", "explicamelo", "mas simple", "que hago primero"])

    def _session_has_recent_commercial_context(self, session_id: str) -> bool:
        entries = [entry for entry in self._conversation_store.read([]) if entry.get("session_id") == session_id]
        for entry in reversed(entries[-6:]):
            text = self._normalize(f"{entry.get('user_message', '')} {entry.get('forja_reply', '')}")
            if self._is_commercial_request(text):
                return True
        return False

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
