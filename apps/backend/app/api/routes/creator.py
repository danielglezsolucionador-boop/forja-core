from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.schemas.creator import (
    CreatorCommandIn,
    CreatorCommandRecord,
    CreatorConsoleState,
    CreatorDecisionIn,
    CreatorExecuteIn,
    CreatorOutput,
    CreatorOutputAssociateIn,
    CreatorSender,
)
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


@router.get("/outputs", response_model=list[CreatorOutput])
def list_creator_outputs(sender: CreatorSender | None = None, command_id: str | None = None, limit: int = 100) -> list[dict]:
    return creator_service.list_outputs(sender=sender, command_id=command_id, limit=limit)


@router.get("/outputs/{output_id}", response_model=CreatorOutput)
def get_creator_output(output_id: str) -> dict:
    output = creator_service.get_output(output_id)
    if output is None:
        raise HTTPException(status_code=404, detail="creator_output_not_found")
    return output


@router.get("/outputs/{output_id}/metadata")
def download_creator_output_metadata(output_id: str) -> JSONResponse:
    output = creator_service.get_output(output_id)
    if output is None:
        raise HTTPException(status_code=404, detail="creator_output_not_found")
    return JSONResponse(
        output,
        headers={"Content-Disposition": f'attachment; filename="forja-{output_id}-metadata.json"'},
    )


@router.get("/commands/{command_id}/outputs", response_model=list[CreatorOutput])
def list_creator_command_outputs(command_id: str) -> list[dict]:
    outputs = creator_service.command_outputs(command_id)
    if outputs is None:
        raise HTTPException(status_code=404, detail="creator_command_not_found")
    return outputs


@router.post("/commands/{command_id}/outputs", response_model=CreatorOutput)
def associate_creator_output(command_id: str, payload: CreatorOutputAssociateIn) -> dict:
    output = creator_service.associate_output(command_id, payload.model_dump())
    if output is None:
        raise HTTPException(status_code=404, detail="creator_command_not_found")
    return output
