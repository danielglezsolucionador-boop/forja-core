from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_current_user
from app.core.audit import append_audit_event
from app.core.config import settings
from app.schemas.auth import CurrentUser, LoginRequest, TokenResponse
from app.services.auth_service import auth_service


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest) -> TokenResponse:
    user = auth_service.authenticate(payload.username, payload.password)
    if user is None:
        append_audit_event("auth.login_failed", payload.username, {"username": payload.username}, risk="medium")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_credentials")
    append_audit_event("auth.login_success", user.username, {"username": user.username})
    return TokenResponse(access_token=auth_service.token_for(user), expires_in_minutes=settings.jwt_exp_minutes)


@router.get("/me", response_model=CurrentUser)
def me(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    return user
