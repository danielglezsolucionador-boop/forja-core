from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.ecosystem_orchestration_service import (
    agent_contract_manager,
    cerebro_control_bridge,
    ecosystem_message_service,
    ecosystem_orchestration_status,
    hermes_memory_bridge,
    orchestration_log_manager,
)


router = APIRouter(prefix="/ecosystem-orchestration", tags=["ecosystem-orchestration"])


class EcosystemMessageIn(BaseModel):
    correlation_id: str | None = Field(default=None, max_length=120)
    sender: str = Field(max_length=80)
    recipient: str = Field(max_length=80)
    intent: str = Field(max_length=80)
    payload: dict = Field(default_factory=dict)
    approvals: list[dict] = Field(default_factory=list)
    capability_requirements: list[dict] = Field(default_factory=list)
    response_target: str | None = Field(default=None, max_length=80)
    audit_id: str | None = Field(default=None, max_length=120)
    priority: str = Field(default="normal", max_length=40)


class BridgePayloadIn(BaseModel):
    correlation_id: str | None = Field(default=None, max_length=120)
    request_summary: str | None = None
    blueprint_summary: str | None = None
    delivery_package_summary: str | None = None
    audit_summary: str | None = None
    workspace_manifest: dict | None = None
    final_status: str | None = None
    sender: str | None = None
    recipient: str | None = None
    intent: str | None = None
    response_target: str | None = None
    payload: dict | None = None


class OrchestrationLogIn(BaseModel):
    correlation_id: str | None = Field(default=None, max_length=120)
    sender: str = Field(default="ceo", max_length=80)
    recipient: str = Field(default="forja", max_length=80)
    request_type: str | None = Field(default=None, max_length=80)
    intent: str | None = Field(default=None, max_length=80)
    capability_used: str | None = Field(default=None, max_length=120)
    provider_used: str | None = Field(default=None, max_length=120)
    workspace_id: str | None = Field(default=None, max_length=120)
    output_id: str | None = Field(default=None, max_length=120)
    audit_id: str | None = Field(default=None, max_length=120)
    status: str = Field(default="logged", max_length=80)
    response_target: str | None = Field(default=None, max_length=80)


@router.get("/status")
def status() -> dict:
    return ecosystem_orchestration_status.status()


@router.get("/contracts")
def contracts() -> dict:
    return {"contracts": agent_contract_manager.contracts()}


@router.post("/contracts/initialize")
def initialize_contracts() -> dict:
    return agent_contract_manager.initialize()


@router.post("/messages")
def create_message(payload: EcosystemMessageIn) -> dict:
    return ecosystem_message_service.create(payload.model_dump())


@router.post("/hermes/memory")
def create_hermes_memory(payload: BridgePayloadIn) -> dict:
    return hermes_memory_bridge.save_operational_memory(payload.model_dump())


@router.post("/cerebro/order")
def create_cerebro_order(payload: BridgePayloadIn) -> dict:
    return cerebro_control_bridge.receive_order(payload.model_dump())


@router.post("/cerebro/approval")
def create_cerebro_approval(payload: BridgePayloadIn) -> dict:
    return cerebro_control_bridge.request_approval(payload.model_dump())


@router.post("/cerebro/result")
def create_cerebro_result(payload: BridgePayloadIn) -> dict:
    return cerebro_control_bridge.send_result(payload.model_dump())


@router.post("/orchestration/log")
def create_orchestration_log(payload: OrchestrationLogIn) -> dict:
    return orchestration_log_manager.log(payload.model_dump())
