from fastapi import APIRouter
from app.api.v1.endpoints import health, auth

router = APIRouter()
router.include_router(health.router, tags=['system'])
router.include_router(auth.router, prefix='/auth', tags=['auth'])
