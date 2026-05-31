from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any, Literal


class TelemetryEventIn(BaseModel):
    event_name: str
    source: str = "local"
    severity: Literal["debug", "info", "warning", "error"] = "info"
    metadata: dict[str, Any] = Field(default_factory=dict)


class TelemetryEvent(BaseModel):
    id: str
    timestamp: str
    event_name: str
    source: str
    severity: str
    metadata: dict[str, Any]
