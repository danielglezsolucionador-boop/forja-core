from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.core.logging import logger
from app.api.v1.router import router as v1_router
from app.api.v1.endpoints.health import (
    ChatRequest,
    chat_status_payload,
    call_openrouter,
    health_payload,
    provenance_payload,
    runtime_payload,
)

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url='/docs' if settings.DEBUG else None,
    redoc_url='/redoc' if settings.DEBUG else None
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.ALLOWED_ORIGINS.split(',') if origin.strip()],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*']
)

app.include_router(v1_router, prefix='/api/v1')


@app.get('/health', tags=['system'])
def public_health():
    return health_payload()


@app.get('/runtime/status', tags=['system'])
def public_runtime_status():
    return runtime_payload()


@app.get('/provenance', tags=['system'])
def public_provenance():
    return provenance_payload()


@app.get('/api/chat', tags=['system'])
def public_chat_status():
    return chat_status_payload()


@app.post('/api/chat', tags=['system'])
def public_chat(request: ChatRequest):
    message = request.message.strip()
    if not message:
        return {
            'reply': 'FORJA necesita un mensaje real para responder.',
            'status': 'error',
            'provider': 'validation',
        }

    if request.app.upper() != 'FORJA':
        return {
            'reply': 'Este endpoint solo responde por FORJA.',
            'status': 'error',
            'provider': 'validation',
        }

    return call_openrouter(message, request.context)


@app.on_event('startup')
async def startup():
    logger.info(f'{settings.APP_NAME} v{settings.APP_VERSION} iniciando')


@app.on_event('shutdown')
async def shutdown():
    logger.info(f'{settings.APP_NAME} cerrando')

if __name__ == '__main__':
    import uvicorn
    uvicorn.run('main:app', host='0.0.0.0', port=8100, reload=True)
