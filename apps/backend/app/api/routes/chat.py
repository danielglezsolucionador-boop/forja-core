from __future__ import annotations

import json
import unicodedata

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.creator_service import creator_service
from app.services.natural_execution_service import DEFAULT_SESSION_ID, natural_execution_service
from app.services.provider_connector_service import provider_connector_layer


router = APIRouter(prefix="/api/chat", tags=["chat"])

MAX_RAW_CONTEXT_CHARS = 200000
MAX_COMPACT_CONTEXT_CHARS = 3200
MAX_HISTORY_MESSAGES = 6
MAX_HISTORY_CHARS = 1800
MAX_PROVIDER_DETAILS_CHARS = 5600


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    app: str = Field(default="FORJA", max_length=80)
    context: str = Field(default="", max_length=MAX_RAW_CONTEXT_CHARS)
    session_id: str = Field(default=DEFAULT_SESSION_ID, max_length=120)
    input_mode: str = Field(default="text", max_length=20)


def _openrouter_state() -> str:
    try:
        snapshot = provider_connector_layer.snapshot()
    except Exception:
        return "unavailable"
    openrouter = next((provider for provider in snapshot.get("providers", []) if provider.get("provider_id") == "openrouter"), None)
    if not openrouter:
        return "unavailable"
    if openrouter.get("connector_state") == "disabled":
        try:
            snapshot = provider_connector_layer.enable_provider("openrouter")
            openrouter = next((provider for provider in snapshot.get("providers", []) if provider.get("provider_id") == "openrouter"), None)
        except Exception:
            return "disabled"
        if not openrouter:
            return "unavailable"
    if openrouter.get("connector_state") == "ready":
        return "ready"
    return str(openrouter.get("connector_state") or "unavailable")


@router.get("")
def chat_status() -> dict:
    state = _openrouter_state()
    ready = state == "ready"
    return {
        "reply": "OPENROUTER_CONFIGURED" if ready else f"OPENROUTER_{state.upper()}",
        "status": "ok" if ready else "degraded",
        "provider": "openrouter",
        "provider_state": state,
        "configured": ready,
        "mode": "natural_execution_layer",
        "conversation_persistence": True,
        "error_code": None if ready else f"OPENROUTER_{state.upper()}",
    }


@router.get("/history")
def chat_history(session_id: str = DEFAULT_SESSION_ID, limit: int = 60) -> dict:
    return natural_execution_service.history(session_id=session_id, limit=limit)


def _compact_text(value: object, max_chars: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= max_chars:
        return text
    return f"{text[: max_chars - 3].rstrip()}..."


def _compact_list(items: object, limit: int = 5, item_chars: int = 220) -> list:
    if not isinstance(items, list):
        return []
    compacted = []
    for item in items[:limit]:
        if isinstance(item, dict):
            compacted.append(
                {
                    key: _compact_text(value, item_chars)
                    for key, value in item.items()
                    if key
                    in {
                        "id",
                        "task_id",
                        "label",
                        "value",
                        "status",
                        "detail",
                        "app",
                        "name",
                        "title",
                        "task",
                        "event",
                        "result",
                        "cause",
                        "path",
                        "stage",
                        "nextAction",
                    }
                }
            )
        else:
            compacted.append(_compact_text(item, item_chars))
    return compacted


def _compact_human_cabin_context(raw_context: str) -> tuple[str, bool]:
    raw = str(raw_context or "").strip()
    if not raw:
        return "sin contexto de Human Cabin", False

    compacted = len(raw) > MAX_COMPACT_CONTEXT_CHARS
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        text = _compact_text(raw, MAX_COMPACT_CONTEXT_CHARS)
        return text, compacted or len(text) < len(raw)

    if not isinstance(parsed, dict):
        text = _compact_text(parsed, MAX_COMPACT_CONTEXT_CHARS)
        return text, True

    snapshot = parsed.get("snapshot") if isinstance(parsed.get("snapshot"), dict) else {}
    memory = snapshot.get("memory") if isinstance(snapshot.get("memory"), dict) else {}
    local_agent = snapshot.get("localAgent") if isinstance(snapshot.get("localAgent"), dict) else {}
    compact = {
        "source": "human_cabin_compacted_server",
        "globalStatus": _compact_text(parsed.get("globalStatus"), 80),
        "directorLines": _compact_list(parsed.get("directorLines"), 5, 180),
        "snapshot": {
            "metrics": _compact_list(snapshot.get("metrics"), 8, 160),
            "constructionQueue": _compact_list(snapshot.get("constructionQueue"), 4, 180),
            "approvals": _compact_list(snapshot.get("approvals"), 4, 180),
            "blockers": _compact_list(snapshot.get("blockers"), 4, 180),
            "deliveries": _compact_list(snapshot.get("deliveries"), 4, 180),
            "flow": _compact_list(snapshot.get("flow"), 6, 160),
            "memory": {
                "connected": bool(memory.get("connected")),
                "primary_source": _compact_text(memory.get("primary_source"), 160),
                "registered_apps": _compact_list(memory.get("registered_apps"), 14, 80),
                "active_apps": _compact_list(memory.get("active_apps"), 14, 80),
                "apps_missing_from_primary_memory": _compact_list(memory.get("apps_missing_from_primary_memory"), 10, 80),
            },
            "localAgent": {
                "agents": local_agent.get("agents") if isinstance(local_agent.get("agents"), dict) else {},
                "tasks": local_agent.get("tasks") if isinstance(local_agent.get("tasks"), dict) else {},
                "latest_results": _compact_list(local_agent.get("latest_results"), 4, 180),
                "recent_activity": _compact_list(local_agent.get("recent_activity"), 5, 160),
            },
        },
    }
    text = json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
    if len(text) > MAX_COMPACT_CONTEXT_CHARS:
        text = _compact_text(text, MAX_COMPACT_CONTEXT_CHARS)
        compacted = True
    return text, compacted


def _recent_history_context(session_id: str, limit: int = MAX_HISTORY_MESSAGES) -> str:
    try:
        history = natural_execution_service.history(session_id=session_id, limit=limit * 2)
    except Exception:
        return ""
    messages = history.get("messages", [])[-limit:]
    lines: list[str] = []
    for item in messages:
        role = str(item.get("role") or "unknown").strip()
        text = " ".join(str(item.get("text") or "").split())
        if text:
            lines.append(f"{role}: {_compact_text(text, 360)}")
    return _compact_text("\n".join(lines), MAX_HISTORY_CHARS)


def _provider_details(parts: list[str]) -> str:
    return _compact_text("\n".join(part for part in parts if part).strip(), MAX_PROVIDER_DETAILS_CHARS)


def _normalize_chat_input(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
    return " ".join(folded.lower().split())


def _is_fast_local_greeting(message: str) -> bool:
    return _normalize_chat_input(message) in {"hola", "buenas", "buenos dias", "buenas tardes", "buenas noches"}


def _is_human_cabin_ui_context(raw_context: str) -> bool:
    raw = str(raw_context or "").strip()
    if not raw:
        return False
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return False
    if not isinstance(parsed, dict):
        return False
    return (
        parsed.get("source") == "human_cabin_v5_compact_context"
        or parsed.get("reason") == "human_cabin_context_budget"
    )


def _should_answer_locally_first(message: str, raw_context: str) -> bool:
    if _is_fast_local_greeting(message):
        return True
    if not _is_human_cabin_ui_context(raw_context):
        return False
    try:
        intent = natural_execution_service.interpret(message)
    except Exception:
        return False
    return intent.name == "preparar_marketing"


@router.post("")
def chat(payload: ChatRequest) -> dict:
    message = payload.message.strip()
    if not message:
        return {"reply": "FORJA necesita un mensaje real para responder.", "status": "error", "provider": "validation"}
    if payload.app.upper() != "FORJA":
        return {"reply": "Este endpoint solo responde por FORJA.", "status": "error", "provider": "validation"}

    provider_state = _openrouter_state()
    command = message[:240]
    session_id = payload.session_id or DEFAULT_SESSION_ID
    compact_context, context_was_compacted = _compact_human_cabin_context(payload.context)
    recent_history = _recent_history_context(session_id)
    details = _provider_details(
        [
            "Responder siempre en espanol ejecutivo como Directora de Construccion.",
            "No mostrar reporte tecnico crudo. Convertir lenguaje natural del CEO en intencion, tarea o estado.",
            "Si el CEO pide contenido, devolver estructura, ideas, calendario, primer paso y entregable sugerido.",
            "Si el CEO pide simplificar, responder usando el historial reciente.",
            f"Contexto Human Cabin compactado:\n{compact_context}",
            f"Historial conversacional persistido:\n{recent_history or 'sin historial previo'}",
        ]
    )
    if len(message) > 240:
        details = _provider_details([f"Mensaje completo: {_compact_text(message, 1400)}", details])

    record: dict = {}
    if not _should_answer_locally_first(message, payload.context):
        try:
            record = creator_service.create_command({"sender": "user", "command": command, "details": details})
        except Exception as exc:
            record = {"id": None, "status": "degraded", "response": "", "error": exc.__class__.__name__}

    result = natural_execution_service.handle_message(
        message,
        session_id=session_id,
        input_mode=payload.input_mode or "text",
        provider_state=provider_state,
        openrouter_record=record,
    )
    result["command_id"] = record.get("id")
    result["creator_status"] = record.get("status")
    result["context_compacted"] = context_was_compacted
    result["provider_payload_chars"] = len(details)
    return result
