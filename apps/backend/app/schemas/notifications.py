from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Literal


NotificationSeverity = Literal["info", "warning", "error", "critical"]


class NotificationIn(BaseModel):
    title: str
    message: str
    severity: NotificationSeverity = "info"
    channel: str = "local"
    metadata: dict[str, str] = Field(default_factory=dict)


class NotificationRecord(NotificationIn):
    id: str
    timestamp: str
    status: Literal["queued", "blocked"]
    delivery_note: str
