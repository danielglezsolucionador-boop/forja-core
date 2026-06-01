from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings
from app.db.session import database_status
from app.schemas.common import HealthResponse
from app.services.provider_connector_service import provider_connector_layer


router = APIRouter(tags=["health"])


def _overall_health_status(db_status: dict) -> str:
    if db_status["status"] in {"ok", "not_configured"}:
        return "ok"
    if settings.is_local and db_status["status"] == "unavailable":
        return "ok"
    return "degraded"


def _ai_pipeline_status() -> str:
    try:
        snapshot = provider_connector_layer.snapshot()
    except Exception:
        return "openrouter_unavailable"
    openrouter = next((provider for provider in snapshot.get("providers", []) if provider.get("provider_id") == "openrouter"), None)
    if openrouter and openrouter.get("connector_state") == "ready":
        return "openrouter_ready"
    if openrouter and openrouter.get("connector_state"):
        return f"openrouter_{openrouter['connector_state']}"
    return "openrouter_unavailable"


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    db_status = await database_status()
    return HealthResponse(
        status=_overall_health_status(db_status),
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.app_env,
        production_ready=settings.production_ready,
        database=db_status,
        security_warnings=settings.security_warnings(),
        modules={
            "backend": "active",
            "auth": "active",
            "telemetry": "active",
            "notifications": "local_queue",
            "factory": "hitl_required",
            "runtime": "local_status_only",
            "ai_pipeline": _ai_pipeline_status(),
            "database": db_status["status"],
        },
    )
