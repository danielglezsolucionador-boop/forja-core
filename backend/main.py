from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.core.logging import logger
from app.api.v1.router import router as v1_router

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url='/docs' if settings.DEBUG else None,
    redoc_url='/redoc' if settings.DEBUG else None
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS.split(','),
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*']
)

app.include_router(v1_router, prefix='/api/v1')


@app.on_event('startup')
async def startup():
    logger.info(f'{settings.APP_NAME} v{settings.APP_VERSION} iniciando')


@app.on_event('shutdown')
async def shutdown():
    logger.info(f'{settings.APP_NAME} cerrando')

if __name__ == '__main__':
    import uvicorn
    uvicorn.run('main:app', host='0.0.0.0', port=8100, reload=True)
