from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from app.core.config import get_settings
from app.core.security import verify_password, create_access_token, decode_access_token

router = APIRouter()
settings = get_settings()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


class Token(BaseModel):
    access_token: str
    token_type: str


class UserOut(BaseModel):
    username: str


class AuthStatus(BaseModel):
    status: str
    auth_configured: bool
    password_hash_configured: bool
    jwt_configured: bool


@router.get("/status", response_model=AuthStatus)
async def status():
    return {
        "status": "AUTH_CONFIGURED" if settings.auth_configured else "AUTH_NOT_CONFIGURED",
        "auth_configured": settings.auth_configured,
        "password_hash_configured": bool(settings.FORJA_ADMIN_PASSWORD_HASH.strip()),
        "jwt_configured": bool(settings.JWT_SECRET_KEY.strip()),
    }


@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    if not settings.auth_configured:
        raise HTTPException(status_code=503, detail="Auth is not configured")
    if form_data.username != settings.FORJA_ADMIN_USERNAME:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    if not verify_password(form_data.password, settings.FORJA_ADMIN_PASSWORD_HASH):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    token = create_access_token({"sub": form_data.username})
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=UserOut)
async def me(token: str = Depends(oauth2_scheme)):
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Token invalido")
    return {"username": payload.get("sub")}
