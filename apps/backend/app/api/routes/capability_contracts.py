from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.capability_contracts import CapabilityContract, CapabilityContractIn
from app.services.capability_contract_service import CapabilityContractError, capability_contract_service


router = APIRouter(prefix="/capability-contracts", tags=["capability-contracts"])


@router.post("", response_model=CapabilityContract)
def create_capability_contract(payload: CapabilityContractIn) -> dict:
    try:
        return capability_contract_service.create_contract(payload.model_dump())
    except CapabilityContractError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("", response_model=list[CapabilityContract])
def list_capability_contracts(limit: int = 100) -> list[dict]:
    return capability_contract_service.list_contracts(limit)


@router.get("/latest", response_model=CapabilityContract | None)
def latest_capability_contract() -> dict | None:
    return capability_contract_service.latest_contract()
