from __future__ import annotations

from fastapi import APIRouter

from app.schemas.real_provider_execution import RealProviderExecutionIn, RealProviderExecutionResult
from app.services.real_provider_execution_service import real_provider_execution_engine


router = APIRouter(prefix="/real-provider-execution", tags=["real-provider-execution"])


@router.post("/run", response_model=RealProviderExecutionResult)
def run_real_provider_execution(payload: RealProviderExecutionIn) -> dict:
    return real_provider_execution_engine.execute(payload.model_dump())


@router.get("/latest", response_model=RealProviderExecutionResult | None)
def latest_real_provider_execution() -> dict | None:
    return real_provider_execution_engine.latest()


@router.get("/status")
def real_provider_execution_status() -> dict:
    return real_provider_execution_engine.status()
