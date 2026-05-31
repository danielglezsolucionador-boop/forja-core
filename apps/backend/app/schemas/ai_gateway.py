from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.capability_contracts import CapabilityContract, CapabilityType, CodingLevel, CostPriority, ReasoningLevel, SpeedPriority
from app.schemas.capability_routing import RoutingExecutionPlan, RoutingTimelineEvent
from app.schemas.provider_abstraction import ProviderProfile


ProviderHealthState = Literal["active", "degraded", "unavailable", "disabled", "maintenance"]
GatewayStatus = Literal["active", "degraded"]


class ProviderHealthSnapshot(BaseModel):
    provider_id: str
    health_state: ProviderHealthState
    simulated_latency: int = Field(ge=0)
    simulated_failure_rate: float = Field(ge=0.0, le=1.0)
    simulated_cost_tier: CostPriority
    last_updated: str


class AIGatewayProviderRecord(BaseModel):
    provider_id: str
    provider_name: str
    enabled: bool
    availability: ProviderHealthState
    quality_profile: dict[str, ReasoningLevel | CodingLevel]
    cost_profile: CostPriority
    speed_profile: SpeedPriority
    supported_capabilities: list[CapabilityType]
    fallback_priority: int
    premium_provider: bool
    local_provider: bool
    provider_role: str
    operational_priority: int
    health: ProviderHealthSnapshot
    notes: str


class CapabilityRegistryEntry(BaseModel):
    capability_type: CapabilityType
    provider_ids: list[str]
    available_provider_ids: list[str]
    fallback_provider_ids: list[str]


class GatewayExecutionProfile(BaseModel):
    execution_mode: str
    quality_bias: str
    cost_bias: str
    speed_bias: str
    fallback_policy: str


class AIGatewaySnapshot(BaseModel):
    gateway_status: GatewayStatus
    economic_provider_id: str | None
    premium_fallback_provider_ids: list[str]
    providers: list[AIGatewayProviderRecord]
    capabilities: list[CapabilityRegistryEntry]
    health: list[ProviderHealthSnapshot]
    fallback_tree: dict[CapabilityType, list[str]]
    execution_profiles: list[GatewayExecutionProfile]
    timeline: list[RoutingTimelineEvent]
    external_request_executed: bool
    generated_at: str


class ProviderHealthUpdateIn(BaseModel):
    health_state: ProviderHealthState
    simulated_latency: int | None = Field(default=None, ge=0)
    simulated_failure_rate: float | None = Field(default=None, ge=0.0, le=1.0)


class GatewayCapabilityLookup(BaseModel):
    capability: CapabilityRegistryEntry
    providers: list[AIGatewayProviderRecord]
    fallback_tree: list[str]
    external_request_executed: bool


class GatewayDecisionIn(BaseModel):
    contract: CapabilityContract


class GatewayProviderDecision(BaseModel):
    capability_type: CapabilityType
    selected_provider: ProviderProfile | None
    fallback_provider: ProviderProfile | None
    fallback_tree: list[ProviderProfile]
    provider_health: list[ProviderHealthSnapshot]
    routing_plan: RoutingExecutionPlan
    decision_reason: str
    availability_filter: list[str]
    external_request_executed: bool
    generated_at: str
