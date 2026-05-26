from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.capability_contracts import CapabilityType, CodingLevel, CostPriority, ReasoningLevel, SpeedPriority
from app.schemas.capability_routing import RoutingTimelineEvent


ProviderConnectorState = Literal["configured", "missing_credentials", "invalid_credentials", "ready", "disabled", "unavailable"]
CredentialState = Literal["not_required", "configured", "missing", "invalid"]


class ProviderConnectorHealthSnapshot(BaseModel):
    provider_id: str
    connector_state: ProviderConnectorState
    credential_state: CredentialState
    simulated_latency: int = Field(ge=0)
    simulated_failure_rate: float = Field(ge=0.0, le=1.0)
    last_checked: str


class ProviderConnectorRecord(BaseModel):
    provider_id: str
    provider_name: str
    connector_state: ProviderConnectorState
    credential_state: CredentialState
    credential_configured: bool
    credential_required: bool
    credential_env_var: str | None
    enabled: bool
    safe_initialization: bool
    supports_real_connection: bool
    local_provider: bool
    supported_capabilities: list[CapabilityType]
    reasoning_strength: ReasoningLevel
    coding_strength: CodingLevel
    cost_profile: CostPriority
    speed_profile: SpeedPriority
    fallback_priority: int
    compatibility_ready: bool
    status_reason: str
    health: ProviderConnectorHealthSnapshot
    secrets_exposed: bool


class ProviderConnectorSnapshot(BaseModel):
    connector_layer_status: Literal["ready", "attention_required"]
    providers: list[ProviderConnectorRecord]
    configured_provider_ids: list[str]
    missing_provider_ids: list[str]
    ready_provider_ids: list[str]
    fallback_ready: bool
    timeline: list[RoutingTimelineEvent]
    external_request_executed: bool
    generated_at: str


class ProviderCompatibilityCheckIn(BaseModel):
    provider_id: str = Field(min_length=2, max_length=80)
    capability_type: CapabilityType


class ProviderCompatibilityCheck(BaseModel):
    provider_id: str
    capability_type: CapabilityType
    compatible: bool
    connector_state: ProviderConnectorState
    credential_state: CredentialState
    fallback_provider_ids: list[str]
    reason: str
    external_request_executed: bool
    generated_at: str
