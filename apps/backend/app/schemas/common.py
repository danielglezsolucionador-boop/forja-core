from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any, Literal


RiskLevel = Literal["low", "medium", "high", "critical"]


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"] = "ok"
    service: str
    version: str
    environment: str
    production_ready: bool
    modules: dict[str, str] = Field(default_factory=dict)
    database: dict[str, Any] = Field(default_factory=dict)
    security_warnings: list[str] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    detail: str
    context: dict[str, Any] = Field(default_factory=dict)
