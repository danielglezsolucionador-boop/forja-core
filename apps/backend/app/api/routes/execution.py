from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.execution import GovernedExecutionApprovalIn, GovernedExecutionRecord, GovernedExecutionStartIn
from app.services.execution_service import GovernedExecutionError, governed_execution_manager


router = APIRouter(prefix="/execution", tags=["governed-execution"])


@router.post("/start", response_model=GovernedExecutionRecord)
def start_governed_execution(payload: GovernedExecutionStartIn) -> dict:
    return governed_execution_manager.start(payload.model_dump())


@router.post("/{execution_id}/approval", response_model=GovernedExecutionRecord)
def decide_governed_execution(execution_id: str, payload: GovernedExecutionApprovalIn) -> dict:
    try:
        record = governed_execution_manager.decide(execution_id, payload.model_dump())
    except GovernedExecutionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if record is None:
        raise HTTPException(status_code=404, detail="execution_not_found")
    return record


@router.get("/{execution_id}", response_model=GovernedExecutionRecord)
def get_governed_execution(execution_id: str) -> dict:
    record = governed_execution_manager.get(execution_id)
    if record is None:
        raise HTTPException(status_code=404, detail="execution_not_found")
    return record
