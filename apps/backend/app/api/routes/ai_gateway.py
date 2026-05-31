from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.ai_gateway import (
    AIGatewaySnapshot,
    GatewayCapabilityLookup,
    GatewayDecisionIn,
    GatewayProviderDecision,
    ProviderHealthUpdateIn,
)
from app.services.ai_gateway_service import AIGatewayError, ai_gateway_manager


router = APIRouter(prefix="/ai-gateway", tags=["ai-gateway"])


@router.get("/status", response_model=AIGatewaySnapshot)
def ai_gateway_status() -> dict:
    return ai_gateway_manager.snapshot()


@router.get("/capabilities/{capability_type}", response_model=GatewayCapabilityLookup)
def ai_gateway_capability_lookup(capability_type: str) -> dict:
    try:
        return ai_gateway_manager.lookup_capability(capability_type)
    except AIGatewayError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/providers/{provider_id}/disable", response_model=AIGatewaySnapshot)
def disable_ai_gateway_provider(provider_id: str) -> dict:
    try:
        return ai_gateway_manager.disable_provider(provider_id)
    except AIGatewayError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/providers/{provider_id}/enable", response_model=AIGatewaySnapshot)
def enable_ai_gateway_provider(provider_id: str) -> dict:
    try:
        return ai_gateway_manager.enable_provider(provider_id)
    except AIGatewayError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/providers/{provider_id}/health", response_model=AIGatewaySnapshot)
def update_ai_gateway_provider_health(provider_id: str, payload: ProviderHealthUpdateIn) -> dict:
    try:
        return ai_gateway_manager.update_health(provider_id, payload.model_dump())
    except AIGatewayError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/decision", response_model=GatewayProviderDecision)
def ai_gateway_provider_decision(payload: GatewayDecisionIn) -> dict:
    return ai_gateway_manager.decision(payload.model_dump())
