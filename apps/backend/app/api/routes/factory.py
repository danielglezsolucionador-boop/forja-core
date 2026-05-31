from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_current_user
from app.schemas.auth import CurrentUser
from app.schemas.factory import FactoryExecuteIn, FactoryExecutionRecord, FactoryPlan, FactoryRequestIn, FactoryRequestRecord
from app.services.factory_service import factory_service


router = APIRouter(prefix="/factory", tags=["factory"])


@router.post("/requests", response_model=FactoryRequestRecord)
def create_factory_request(payload: FactoryRequestIn, user: CurrentUser = Depends(get_current_user)) -> dict:
    return factory_service.create_request(payload.model_dump(), user.username)


@router.get("/requests", response_model=list[FactoryRequestRecord])
def list_factory_requests(limit: int = 100, _: CurrentUser = Depends(get_current_user)) -> list[dict]:
    return factory_service.list_requests(limit)


@router.get("/requests/{request_id}/plan", response_model=FactoryPlan)
def get_factory_plan(request_id: str, _: CurrentUser = Depends(get_current_user)) -> dict:
    plan = factory_service.build_plan(request_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="factory_request_not_found")
    return plan


@router.post("/requests/{request_id}/execute", response_model=FactoryExecutionRecord)
def execute_factory_request(request_id: str, payload: FactoryExecuteIn, _: CurrentUser = Depends(get_current_user)) -> dict:
    execution = factory_service.execute(request_id, payload.approval_request_id, payload.allow_write)
    if execution is None:
        raise HTTPException(status_code=404, detail="factory_request_not_found")
    return execution


@router.get("/executions", response_model=list[FactoryExecutionRecord])
def list_factory_executions(limit: int = 100, _: CurrentUser = Depends(get_current_user)) -> list[dict]:
    return factory_service.list_executions(limit)
