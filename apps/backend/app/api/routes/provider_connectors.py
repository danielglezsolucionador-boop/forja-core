from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.provider_connectors import ProviderCompatibilityCheck, ProviderCompatibilityCheckIn, ProviderConnectorSnapshot
from app.services.provider_connector_service import ProviderConnectorError, provider_connector_layer


router = APIRouter(prefix="/provider-connectors", tags=["provider-connectors"])


@router.get("/status", response_model=ProviderConnectorSnapshot)
def provider_connector_status() -> dict:
    return provider_connector_layer.snapshot()


@router.post("/validate", response_model=ProviderCompatibilityCheck)
def validate_provider_connector(payload: ProviderCompatibilityCheckIn) -> dict:
    try:
        return provider_connector_layer.validate(payload.model_dump())
    except ProviderConnectorError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/providers/{provider_id}/disable", response_model=ProviderConnectorSnapshot)
def disable_provider_connector(provider_id: str) -> dict:
    try:
        return provider_connector_layer.disable_provider(provider_id)
    except ProviderConnectorError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/providers/{provider_id}/enable", response_model=ProviderConnectorSnapshot)
def enable_provider_connector(provider_id: str) -> dict:
    try:
        return provider_connector_layer.enable_provider(provider_id)
    except ProviderConnectorError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
