from __future__ import annotations

from pydantic import BaseModel

from app.schemas.capability_contracts import CapabilityContract, CapabilityType, CodingLevel, CostPriority, ReasoningLevel, SpeedPriority


ProviderAvailabilityStatus = str


class ProviderProfile(BaseModel):
    provider_id: str
    provider_name: str
    supported_capabilities: list[CapabilityType]
    reasoning_strength: ReasoningLevel
    coding_strength: CodingLevel
    speed_profile: SpeedPriority
    cost_profile: CostPriority
    context_capacity: int
    availability_status: ProviderAvailabilityStatus
    fallback_priority: int
    premium_provider: bool
    local_provider: bool
    enabled: bool
    notes: str


class ProviderMatchScore(BaseModel):
    provider_id: str
    provider_name: str
    quality_score: float
    cost_score: float
    speed_score: float
    compatibility_score: float
    reason: str


class ProviderRoutingIn(BaseModel):
    contract: CapabilityContract


class ProviderRoutingDecision(BaseModel):
    selected_provider: ProviderProfile | None
    fallback_provider: ProviderProfile | None
    reason: str
    confidence: float
    estimated_cost_profile: CostPriority | None
    estimated_quality_profile: ReasoningLevel | None
    compatible_providers: list[ProviderProfile]
    scoring: list[ProviderMatchScore]
    fallback_strategy: str
    external_request_executed: bool
