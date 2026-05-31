from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user
from app.schemas.ecosystem import EcosystemIntegration
from app.services.ecosystem_service import ecosystem_service


router = APIRouter(prefix="/ecosystem", tags=["ecosystem"])


@router.get("/integrations", response_model=list[EcosystemIntegration])
def list_integrations(_: object = Depends(get_current_user)) -> list[dict]:
    return ecosystem_service.integrations()
