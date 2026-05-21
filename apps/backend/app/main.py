from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import ai_pipeline, audit, auth, ecosystem, factory, governance, health, notifications, providers, runtime, telemetry, validation, workflows
from app.core.audit import append_audit_event
from app.core.config import settings
from app.core.logging import configure_logging, logger
from app.db.migrations import run_migrations_if_enabled


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    settings.validate_runtime_safety()
    settings.state_dir.mkdir(parents=True, exist_ok=True)
    settings.audit_dir.mkdir(parents=True, exist_ok=True)
    settings.outputs_dir.mkdir(parents=True, exist_ok=True)
    await run_migrations_if_enabled()
    append_audit_event("runtime.startup", "system", {"service": settings.app_name, "version": settings.app_version})
    logger.info("FORJA backend startup complete")
    yield
    append_audit_event("runtime.shutdown", "system", {"service": settings.app_name})
    logger.info("FORJA backend shutdown complete")


app = FastAPI(title="FORJA Backend", version=settings.app_version, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(runtime.router)
app.include_router(telemetry.router)
app.include_router(notifications.router)
app.include_router(governance.router)
app.include_router(providers.router)
app.include_router(ai_pipeline.router)
app.include_router(factory.router)
app.include_router(ecosystem.router)
app.include_router(workflows.router)
app.include_router(audit.router)
app.include_router(validation.router)
