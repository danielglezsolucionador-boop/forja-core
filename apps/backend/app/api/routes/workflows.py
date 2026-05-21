from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_current_user
from app.schemas.auth import CurrentUser
from app.schemas.workflow import WorkflowAdvanceIn, WorkflowIn, WorkflowRecord
from app.services.workflow_service import workflow_service


router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.post("", response_model=WorkflowRecord)
def create_workflow(payload: WorkflowIn, user: CurrentUser = Depends(get_current_user)) -> dict:
    return workflow_service.create(payload.model_dump(), user.username)


@router.post("/{workflow_id}/advance", response_model=WorkflowRecord)
def advance_workflow(workflow_id: str, payload: WorkflowAdvanceIn, user: CurrentUser = Depends(get_current_user)) -> dict:
    record = workflow_service.advance(workflow_id, payload.checkpoint_acknowledged, payload.note, user.username)
    if record is None:
        raise HTTPException(status_code=404, detail="workflow_not_found")
    return record


@router.get("", response_model=list[WorkflowRecord])
def list_workflows(limit: int = 100, _: CurrentUser = Depends(get_current_user)) -> list[dict]:
    return workflow_service.list(limit)
