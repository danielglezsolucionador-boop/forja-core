from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.workspace import WorkspaceCreateIn, WorkspaceCreationRecord
from app.services.workspace_service import WorkspaceAlreadyExistsError, WorkspaceSecurityError, workspace_manager


router = APIRouter(prefix="/workspace", tags=["workspace-generator"])


@router.post("/create", response_model=WorkspaceCreationRecord)
def create_workspace(payload: WorkspaceCreateIn) -> dict:
    try:
        return workspace_manager.create_workspace(payload.blueprint.model_dump())
    except WorkspaceSecurityError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except WorkspaceAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
