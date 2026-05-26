from __future__ import annotations

from fastapi import APIRouter

from app.schemas.provider_execution import ExecutionSimulationResult, ProviderExecutionSimulationIn
from app.services.provider_execution_service import provider_execution_simulator


router = APIRouter(prefix="/provider-execution", tags=["provider-execution"])


@router.post("/simulate", response_model=ExecutionSimulationResult)
def simulate_provider_execution(payload: ProviderExecutionSimulationIn) -> dict:
    return provider_execution_simulator.simulate(payload.model_dump())


@router.get("/latest", response_model=ExecutionSimulationResult | None)
def latest_provider_execution_simulation() -> dict | None:
    return provider_execution_simulator.latest()
