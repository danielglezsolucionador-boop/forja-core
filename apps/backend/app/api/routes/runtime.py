from __future__ import annotations

from fastapi import APIRouter

from app.core.audit import read_audit_events
from app.core.config import settings
from app.db.session import database_status
from app.services.provider_service import provider_service


router = APIRouter(prefix="/runtime", tags=["runtime"])


@router.get("/status")
async def runtime_status() -> dict:
    db_status = await database_status()
    return {
        "status": "active",
        "runtime_loop": "not_started_by_design",
        "busy_loop": False,
        "environment": settings.app_env,
        "zero_write_policy": True,
        "human_in_the_loop": True,
        "ai_pipeline": "blocked_provider_disabled",
        "database": db_status,
        "security_warnings": settings.security_warnings(),
        "providers": provider_service.list_providers(),
        "audit_events": len(read_audit_events(1000)),
        "notes": [
            "FORJA local runtime exposes status and controlled workflows.",
            "No background execution loop is running in this phase.",
            "Factory writes require human approval and allow_write=true.",
        ],
    }
