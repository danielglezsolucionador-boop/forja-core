from __future__ import annotations

from fastapi import APIRouter

from app.schemas.blueprint import ProjectBlueprint, ProjectBlueprintIn
from app.services.blueprint_service import project_blueprint_service


router = APIRouter(prefix="/blueprint", tags=["project-blueprint"])


@router.post("/generate", response_model=ProjectBlueprint)
def generate_project_blueprint(payload: ProjectBlueprintIn) -> dict:
    return project_blueprint_service.generate(payload.model_dump())
