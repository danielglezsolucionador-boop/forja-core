from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


CapabilityType = Literal[
    "reasoning",
    "coding",
    "frontend_generation",
    "backend_generation",
    "debugging",
    "repair",
    "analysis",
    "summarization",
    "architecture",
    "documentation",
]
ReasoningLevel = Literal["low", "medium", "high", "extreme"]
CodingLevel = Literal["none", "low", "medium", "high", "expert"]
SpeedPriority = Literal["fast", "balanced", "maximum_quality"]
CostPriority = Literal["low_cost", "balanced", "premium_allowed"]
CapabilityRequester = Literal["ceo", "cerebro", "user", "seo", "system"]


class CapabilityContractIn(BaseModel):
    capability_type: CapabilityType
    reasoning_level: ReasoningLevel = "medium"
    coding_level: CodingLevel = "none"
    speed_priority: SpeedPriority = "balanced"
    cost_priority: CostPriority = "balanced"
    context_size: int = Field(default=32000, ge=1000, le=2000000)
    provider_constraints: list[str] = Field(default_factory=list, max_length=12)
    requires_human_approval: bool | None = None
    fallback_allowed: bool = True
    execution_scope: str = Field(default="capability_contract_only", min_length=3, max_length=120)
    requested_by: CapabilityRequester = "ceo"


class CapabilityContract(BaseModel):
    capability_id: str
    capability_type: CapabilityType
    reasoning_level: ReasoningLevel
    coding_level: CodingLevel
    speed_priority: SpeedPriority
    cost_priority: CostPriority
    context_size: int
    provider_constraints: list[str]
    requires_human_approval: bool
    fallback_allowed: bool
    execution_scope: str
    requested_by: CapabilityRequester
    timestamp: str
