from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user
from app.schemas.providers import ProviderRecord
from app.services.provider_service import provider_service


router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("", response_model=list[ProviderRecord])
def list_providers(_: object = Depends(get_current_user)) -> list[dict]:
    return provider_service.list_providers()
