from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_current_user
from app.schemas.auth import CurrentUser
from app.schemas.governance import ApprovalDecisionIn, ApprovalRecord, ApprovalRequestIn
from app.services.governance_service import governance_service


router = APIRouter(prefix="/governance", tags=["governance"])


@router.post("/approval-requests", response_model=ApprovalRecord)
def create_approval_request(payload: ApprovalRequestIn, user: CurrentUser = Depends(get_current_user)) -> dict:
    return governance_service.create_request(payload.model_dump(), user.username)


@router.post("/approval-requests/{request_id}/decision", response_model=ApprovalRecord)
def decide_approval_request(request_id: str, payload: ApprovalDecisionIn, user: CurrentUser = Depends(get_current_user)) -> dict:
    record = governance_service.decide(request_id, payload.decision, payload.reason, user.username)
    if record is None:
        raise HTTPException(status_code=404, detail="approval_request_not_found")
    return record


@router.get("/approval-requests", response_model=list[ApprovalRecord])
def list_approval_requests(limit: int = 100, _: CurrentUser = Depends(get_current_user)) -> list[dict]:
    return governance_service.list_requests(limit)
