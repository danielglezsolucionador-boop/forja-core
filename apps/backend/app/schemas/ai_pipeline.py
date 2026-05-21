from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Literal


PipelineStatus = Literal["blocked_provider_disabled", "queued", "completed", "failed"]


class AIPipelineRequestIn(BaseModel):
    objective: str
    input_summary: str
    constraints: list[str] = Field(default_factory=list)


class AIPipelineRecord(AIPipelineRequestIn):
    id: str
    timestamp: str
    requested_by: str
    status: PipelineStatus
    provider_id: str
    explanation: str
