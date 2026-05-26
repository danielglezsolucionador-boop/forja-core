from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.capability_contracts import CapabilityRequester, CapabilityType
from app.schemas.capability_routing import RoutingTimelineEvent
from app.schemas.provider_execution import ProviderExecutionAuditPreview


RealProviderExecutionState = Literal[
    "provider_connecting",
    "provider_ready",
    "executing_real_ai",
    "fallback_real_ai",
    "degraded_mode",
    "completed",
    "failed",
]
RealProviderExecutionMode = Literal["economic_low_cost", "low_cost_safe", "safe_mode", "controlled_real_ai"]
RealAITaskType = Literal["readme", "summary", "architecture_notes", "documentation"]
RealAIOutputKind = Literal["generated_readme", "generated_summary", "architecture_notes", "technical_documentation", "failure_report"]
RealAIOutputStatus = Literal["generated", "blocked", "failed", "degraded"]


class RealProviderExecutionIn(BaseModel):
    capability_type: CapabilityType = "documentation"
    task_type: RealAITaskType = "summary"
    objective: str = Field(min_length=8, max_length=1800)
    requested_by: CapabilityRequester = "ceo"
    provider_id: str | None = Field(default=None, min_length=2, max_length=80)
    fallback_provider_id: str | None = Field(default=None, min_length=2, max_length=80)
    workspace_id: str | None = Field(default=None, min_length=3, max_length=80)
    max_tokens: int = Field(default=300, ge=64, le=700)
    timeout_seconds: int = Field(default=20, ge=3, le=45)
    safe_mode: bool = True
    fallback_allowed: bool = True
    allow_real_request: bool = True


class RealAIOutput(BaseModel):
    kind: RealAIOutputKind
    label: str
    logical_path: str | None
    status: RealAIOutputStatus
    summary: str
    source: str


class RealProviderExecutionResult(BaseModel):
    execution_id: str
    provider_used: str | None
    primary_provider_attempted: str | None
    fallback_provider_used: str | None
    capability_type: CapabilityType
    task_type: RealAITaskType
    execution_state: RealProviderExecutionState
    execution_mode: RealProviderExecutionMode
    estimated_tokens: int
    estimated_cost: float
    estimated_duration: float
    max_tokens: int
    max_execution_time: int
    max_request_size: int
    response_received: bool
    generated_text_preview: str
    outputs: list[RealAIOutput]
    fallback_triggered: bool
    safe_mode: bool
    rate_limit_remaining: int
    timeline: list[RoutingTimelineEvent]
    audit_events: list[ProviderExecutionAuditPreview]
    external_request_executed: bool
    generated_at: str
