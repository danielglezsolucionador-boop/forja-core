from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user
from app.schemas.ai_pipeline import AIPipelineRecord, AIPipelineRequestIn
from app.schemas.auth import CurrentUser
from app.services.ai_pipeline_service import ai_pipeline_service


router = APIRouter(prefix="/ai/pipeline", tags=["ai-pipeline"])


@router.post("/requests", response_model=AIPipelineRecord)
def create_ai_pipeline_request(payload: AIPipelineRequestIn, user: CurrentUser = Depends(get_current_user)) -> dict:
    return ai_pipeline_service.create_request(payload.model_dump(), user.username)


@router.get("/requests", response_model=list[AIPipelineRecord])
def list_ai_pipeline_requests(limit: int = 100, _: CurrentUser = Depends(get_current_user)) -> list[dict]:
    return ai_pipeline_service.list_requests(limit)
