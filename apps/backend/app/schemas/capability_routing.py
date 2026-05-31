from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.capability_contracts import CapabilityContract, CostPriority, ReasoningLevel, SpeedPriority
from app.schemas.provider_abstraction import ProviderMatchScore, ProviderProfile


ExecutionMode = Literal["low_cost", "balanced", "premium", "safe_mode", "experimental"]
RoutingRiskLevel = Literal["LOW", "MEDIUM", "HIGH"]


class RoutingTimelineEvent(BaseModel):
    timestamp: str
    event: str
    detail: str


class CapabilityRoutingIn(BaseModel):
    contract: CapabilityContract
    disabled_provider_ids: list[str] = Field(default_factory=list, max_length=12)
    execution_mode_hint: ExecutionMode | None = None


class RoutingExecutionPlan(BaseModel):
    plan_id: str
    capability_id: str
    primary_provider: ProviderProfile | None
    fallback_provider: ProviderProfile | None
    fallback_tree: list[ProviderProfile]
    routing_reason: str
    estimated_quality: ReasoningLevel | None
    estimated_cost: CostPriority | None
    estimated_speed: SpeedPriority | None
    confidence: float
    execution_mode: ExecutionMode
    approval_required: bool
    risk_level: RoutingRiskLevel
    provider_scores: list[ProviderMatchScore]
    routing_factors: dict[str, str | int | bool]
    timeline: list[RoutingTimelineEvent]
    external_request_executed: bool
    generated_at: str
