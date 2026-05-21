from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings
from app.db.session import database_status
from app.schemas.common import HealthResponse


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    db_status = await database_status()
    return HealthResponse(
        status="ok" if db_status["status"] in {"ok", "not_configured"} else "degraded",
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
            "ai_pipeline": "provider_disabled",
            "database": db_status["status"],
        },
    )
