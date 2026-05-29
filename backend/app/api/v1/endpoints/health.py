from fastapi import APIRouter
from datetime import datetime
from app.core.config import get_settings

router = APIRouter()
settings = get_settings()


@router.get('/health')
def health_check():
    return {
        'status': 'ok',
        'app': settings.APP_NAME,
        'version': settings.APP_VERSION,
        'env': settings.APP_ENV,
        'auth': 'configured' if settings.auth_configured else 'not_configured',
        'timestamp': datetime.utcnow().isoformat()
    }
