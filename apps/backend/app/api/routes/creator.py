from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.creator import CreatorCommandIn, CreatorCommandRecord, CreatorConsoleState, CreatorDecisionIn, CreatorExecuteIn
from app.services.creator_service import creator_service


router = APIRouter(prefix="/creator", tags=["creator-console"])


@router.get("/console", response_model=CreatorConsoleState)
def creator_console_state(limit: int = 50) -> dict:
    return creator_service.console_state(limit)


@router.post("/commands", response_model=CreatorCommandRecord)
def create_creator_command(payload: CreatorCommandIn) -> dict:
    return creator_service.create_command(payload.model_dump())


@router.post("/commands/{command_id}/decision", response_model=CreatorCommandRecord)
def decide_creator_command(command_id: str, payload: CreatorDecisionIn) -> dict:
    record = creator_service.decide_command(command_id, payload.decision, payload.reason)
    if record is None:
        raise HTTPException(status_code=404, detail="creator_command_not_found")
    return record


@router.post("/commands/{command_id}/execute", response_model=CreatorCommandRecord)
def execute_creator_command(command_id: str, payload: CreatorExecuteIn) -> dict:
    record = creator_service.execute_command(command_id, payload.metadata_only)
    if record is None:
        raise HTTPException(status_code=404, detail="creator_command_not_found")
    return record
