from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings
from app.schemas.common import HealthResponse


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.app_env,
        production_ready=settings.production_ready,
        modules={
            "backend": "active",
            "auth": "active",
            "telemetry": "active",
            "notifications": "local_queue",
            "factory": "hitl_required",
            "runtime": "local_status_only",
            "ai_pipeline": "provider_disabled",
        },
    )
