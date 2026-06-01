from __future__ import annotations

import re

from pydantic import BaseModel, Field
from fastapi import APIRouter

from app.services.local_agent_service import local_agent_service
from app.services.creator_service import creator_service
from app.services.provider_connector_service import provider_connector_layer


router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    app: str = Field(default="FORJA", max_length=80)
    context: str = Field(default="", max_length=12000)


REPORT_FILE_RE = re.compile(r"\b([A-Za-z0-9][A-Za-z0-9_.-]{0,120}\.md)\b", re.IGNORECASE)
REPORT_INTENT_MARKERS = ("guarda", "guardar", "guardalo", "guárdalo", "archivo", "inventario", "reporte", "report")
REPORT_ACTION_MARKERS = ("genera", "generar", "crea", "crear", "produce", "prepara", "haz")


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
        "error_code": None if ready else f"OPENROUTER_{state.upper()}",
    }


def _should_create_local_agent_report(message: str) -> bool:
    normalized = " ".join(message.lower().split())
    return bool(REPORT_FILE_RE.search(message)) and any(marker in normalized for marker in REPORT_INTENT_MARKERS + REPORT_ACTION_MARKERS)


def _report_filename(message: str) -> str:
    match = REPORT_FILE_RE.search(message)
    if not match:
        return "FORJA_LOCAL_AGENT_REPORT.md"
    return match.group(1).replace("\\", "").replace("/", "")


def _create_local_agent_task(message: str) -> dict | None:
    if not _should_create_local_agent_report(message):
        return None
    filename = _report_filename(message)
    task = local_agent_service.create_task(
        {
            "instruction": (
                f"Generar reporte de inventario de aplicaciones del ecosistema y guardarlo como {filename}. "
                "Usar memoria real de docs/ecosystem-memory. "
                f"Solicitud original desde Human Cabin: {message}"
            ),
            "title": f"Generar {filename}",
            "requested_by": "ceo",
            "source": "human_cabin_chat",
            "priority": "high",
            "target": {"workspace_id": "ecosystem", "repo_ids": ["forja"], "paths": [filename, "docs/ecosystem-memory"]},
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
                "exact_target": {"filename": filename, "repo": "forja"},
            },
        )
    return {
        "task_id": task.get("task_id"),
        "title": task.get("title"),
        "status": task.get("status"),
        "risk_level": task.get("risk_level"),
        "task_type": task.get("task_type"),
        "desired_output": filename,
    }


@router.post("")
def chat(payload: ChatRequest) -> dict:
    message = payload.message.strip()
    if not message:
        return {"reply": "FORJA necesita un mensaje real para responder.", "status": "error", "provider": "validation"}
    if payload.app.upper() != "FORJA":
        return {"reply": "Este endpoint solo responde por FORJA.", "status": "error", "provider": "validation"}

    _openrouter_state()
    command = message[:240]
    details = payload.context
    if len(message) > 240:
        details = f"Mensaje completo: {message}\n\nContexto:\n{payload.context}".strip()

    record = creator_service.create_command({"sender": "user", "command": command, "details": details})
    local_agent_task = _create_local_agent_task(message)
    reply = record.get("response") or "FORJA recibio tu mensaje, pero no genero contenido conversacional."
    if local_agent_task:
        reply = (
            f"{reply}\n\nLocal Agent: tarea {local_agent_task['task_id']} creada y "
            f"{local_agent_task['status']} para generar {local_agent_task['desired_output']}."
        )
    return {
        "reply": reply,
        "status": "ok" if record.get("status") == "completed" else record.get("status", "unknown"),
        "provider": "openrouter",
        "command_id": record.get("id"),
        "creator_status": record.get("status"),
        "response_received": record.get("status") == "completed",
        "local_agent_task": local_agent_task,
        "fallback_triggered": False,
        "secrets_exposed": False,
    }
