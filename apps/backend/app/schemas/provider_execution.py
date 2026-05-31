from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.capability_contracts import CapabilityContract, CapabilityType, CostPriority, ReasoningLevel
from app.schemas.capability_routing import ExecutionMode, RoutingExecutionPlan, RoutingTimelineEvent
from app.schemas.provider_abstraction import ProviderProfile


SimulationFailureMode = Literal["none", "provider_unavailable", "timeout", "low_confidence", "provider_disabled", "forced_failure"]
ProviderExecutionState = Literal["preparing", "routing", "executing", "fallback", "completed", "degraded_mode", "failed"]
SimulatedOutputKind = Literal[
    "reasoning_summary",
    "code_generation",
    "frontend_generation",
    "backend_generation",
    "repair_findings",
    "architecture_plan",
    "documentation_draft",
    "fallback_report",
    "failure_report",
]


class ProviderExecutionSimulationIn(BaseModel):
    contract: CapabilityContract
    routing_plan: RoutingExecutionPlan | None = None
    failure_mode: SimulationFailureMode = "none"
    disabled_provider_ids: list[str] = Field(default_factory=list, max_length=12)


class SimulatedProviderOutput(BaseModel):
    kind: SimulatedOutputKind
    label: str
    summary: str
    status: str
    source: str


class ProviderExecutionAuditPreview(BaseModel):
    event_type: str
    actor: str
    risk: str
    timestamp: str


class ExecutionSimulationResult(BaseModel):
    execution_id: str
    capability_id: str
    routing_plan_id: str | None
    provider_used: ProviderProfile | None
    primary_provider_attempted: ProviderProfile | None
    fallback_provider_used: ProviderProfile | None
    fallback_chain: list[ProviderProfile]
    capability_type: CapabilityType
    execution_mode: ExecutionMode
    estimated_tokens: int
    estimated_cost: float
    estimated_duration: float
    simulated_quality: ReasoningLevel | None
    generated_summary: str
    execution_status: ProviderExecutionState
    fallback_triggered: bool
    failure_mode: SimulationFailureMode
    estimated_cost_profile: CostPriority | None
    outputs: list[SimulatedProviderOutput]
    timeline: list[RoutingTimelineEvent]
    audit_events: list[ProviderExecutionAuditPreview]
    external_request_executed: bool
    generated_at: str
