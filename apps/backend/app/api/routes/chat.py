from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter

from app.services.creator_service import creator_service
from app.services.provider_connector_service import provider_connector_layer


router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    app: str = Field(default="FORJA", max_length=80)
    context: str = Field(default="", max_length=12000)


def _openrouter_state() -> str:
    try:
        snapshot = provider_connector_layer.snapshot()
    except Exception:
        return "unavailable"
    openrouter = next((provider for provider in snapshot.get("providers", []) if provider.get("provider_id") == "openrouter"), None)
    if not openrouter:
        return "unavailable"
    if openrouter.get("connector_state") == "ready":
        return "ready"
    return str(openrouter.get("connector_state") or "unavailable")


@router.get("")
def chat_status() -> dict:
    state = _openrouter_state()
    return {
        "reply": "OPENROUTER_CONFIGURED" if state == "ready" else f"OPENROUTER_{state.upper()}",
        "status": "ok" if state == "ready" else "not_configured",
        "provider": "openrouter",
    }


@router.post("")
def chat(payload: ChatRequest) -> dict:
    message = payload.message.strip()
    if not message:
        return {"reply": "FORJA necesita un mensaje real para responder.", "status": "error", "provider": "validation"}
    if payload.app.upper() != "FORJA":
        return {"reply": "Este endpoint solo responde por FORJA.", "status": "error", "provider": "validation"}

    command = message[:240]
    details = payload.context
    if len(message) > 240:
        details = f"Mensaje completo: {message}\n\nContexto:\n{payload.context}".strip()

    record = creator_service.create_command({"sender": "user", "command": command, "details": details})
    return {
        "reply": record.get("response") or "FORJA no devolvio respuesta.",
        "status": "ok" if record.get("status") == "completed" else record.get("status", "unknown"),
        "provider": "openrouter",
        "command_id": record.get("id"),
        "creator_status": record.get("status"),
        "response_received": record.get("status") == "completed",
        "fallback_triggered": False,
        "secrets_exposed": False,
    }
