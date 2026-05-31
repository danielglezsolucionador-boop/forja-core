from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user
from app.schemas.auth import CurrentUser
from app.schemas.telemetry import TelemetryEvent, TelemetryEventIn
from app.services.telemetry_service import telemetry_service


router = APIRouter(prefix="/telemetry", tags=["telemetry"])


@router.post("/events", response_model=TelemetryEvent)
def record_event(payload: TelemetryEventIn, user: CurrentUser = Depends(get_current_user)) -> dict:
    metadata = dict(payload.metadata)
    metadata["actor"] = user.username
    return telemetry_service.record(payload.event_name, payload.source, payload.severity, metadata)


@router.get("/events", response_model=list[TelemetryEvent])
def list_events(limit: int = 50, _: CurrentUser = Depends(get_current_user)) -> list[dict]:
    return telemetry_service.recent(limit)
