from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user
from app.schemas.auth import CurrentUser
from app.schemas.notifications import NotificationIn, NotificationRecord
from app.services.notification_service import notification_service


router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.post("", response_model=NotificationRecord)
def create_notification(payload: NotificationIn, user: CurrentUser = Depends(get_current_user)) -> dict:
    metadata = dict(payload.metadata)
    metadata["actor"] = user.username
    return notification_service.enqueue(payload.title, payload.message, payload.severity, payload.channel, metadata)


@router.get("", response_model=list[NotificationRecord])
def list_notifications(limit: int = 50, _: CurrentUser = Depends(get_current_user)) -> list[dict]:
    return notification_service.recent(limit)
