from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.generation import FileGenerationIn, FileGenerationRecord
from app.services.file_generation_service import FileGenerationSecurityError, controlled_file_generator
from app.services.workspace_service import WorkspaceSecurityError


router = APIRouter(prefix="/generation", tags=["controlled-file-generator"])


@router.post("/files", response_model=FileGenerationRecord)
def generate_files(payload: FileGenerationIn) -> dict:
    try:
        return controlled_file_generator.generate(payload.blueprint.model_dump(), payload.workspace.model_dump(), payload.manual_approval)
    except (FileGenerationSecurityError, WorkspaceSecurityError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
