from __future__ import annotations

from fastapi import APIRouter

from app.schemas.capability_routing import CapabilityRoutingIn, RoutingExecutionPlan
from app.services.capability_routing_service import capability_routing_engine


router = APIRouter(prefix="/capability-routing", tags=["capability-routing"])


@router.post("/plan", response_model=RoutingExecutionPlan)
def create_routing_execution_plan(payload: CapabilityRoutingIn) -> dict:
    return capability_routing_engine.create_plan(payload.model_dump())
