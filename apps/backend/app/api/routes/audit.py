from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user
from app.core.audit import read_audit_events


router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/events")
def audit_events(limit: int = 100, _: object = Depends(get_current_user)) -> list[dict]:
    return read_audit_events(limit)
