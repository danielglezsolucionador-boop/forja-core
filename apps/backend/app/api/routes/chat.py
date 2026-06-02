from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.creator_service import creator_service
from app.services.natural_execution_service import DEFAULT_SESSION_ID, natural_execution_service
from app.services.provider_connector_service import provider_connector_layer


router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    app: str = Field(default="FORJA", max_length=80)
    context: str = Field(default="", max_length=12000)
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


@router.post("")
def chat(payload: ChatRequest) -> dict:
    message = payload.message.strip()
    if not message:
        return {"reply": "FORJA necesita un mensaje real para responder.", "status": "error", "provider": "validation"}
    if payload.app.upper() != "FORJA":
        return {"reply": "Este endpoint solo responde por FORJA.", "status": "error", "provider": "validation"}

    provider_state = _openrouter_state()
    command = message[:240]
    details = (
        "Responder siempre en espanol ejecutivo como Directora de Construccion. "
        "No mostrar reporte tecnico crudo. Convertir lenguaje natural del CEO en intencion, tarea o estado. "
        f"Contexto Human Cabin:\n{payload.context}"
    )
    if len(message) > 240:
        details = f"Mensaje completo: {message}\n\n{details}".strip()

    try:
        record = creator_service.create_command({"sender": "user", "command": command, "details": details})
    except Exception as exc:
        record = {"id": None, "status": "degraded", "response": "", "error": exc.__class__.__name__}

    result = natural_execution_service.handle_message(
        message,
        session_id=payload.session_id or DEFAULT_SESSION_ID,
        input_mode=payload.input_mode or "text",
        provider_state=provider_state,
        openrouter_record=record,
    )
    result["command_id"] = record.get("id")
    result["creator_status"] = record.get("status")
    return result
