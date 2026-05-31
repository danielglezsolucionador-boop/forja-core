from __future__ import annotations

from fastapi import APIRouter

from app.schemas.provider_abstraction import ProviderProfile, ProviderRoutingDecision, ProviderRoutingIn
from app.services.provider_abstraction_service import provider_abstraction_service


router = APIRouter(prefix="/provider-abstraction", tags=["provider-abstraction"])


@router.get("/profiles", response_model=list[ProviderProfile])
def list_provider_profiles() -> list[dict]:
    return provider_abstraction_service.profiles()


@router.post("/route", response_model=ProviderRoutingDecision)
def route_capability_contract(payload: ProviderRoutingIn) -> dict:
    return provider_abstraction_service.route(payload.contract.model_dump())
