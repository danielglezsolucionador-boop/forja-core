from __future__ import annotations

from contextlib import asynccontextmanager
import traceback

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import ai_pipeline, audit, auth, ecosystem, factory, governance, health, notifications, providers, runtime, telemetry, validation, workflows
from app.core.audit import append_audit_event
from app.core.config import settings
from app.core.logging import configure_logging, logger
from app.db.migrations import run_migrations_if_enabled
from app.db.session import database_status, dispose_engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        print("STARTUP_STAGE_0_LIFESPAN_ENTER", flush=True)
        configure_logging()
        print("STARTUP_STAGE_1_LOGGING_OK", flush=True)
        print(f"STARTUP_CONFIG_SNAPSHOT {settings.diagnostic_snapshot()}", flush=True)

        settings.validate_runtime_safety()
        print("STARTUP_STAGE_2_RUNTIME_SAFETY_OK", flush=True)

        settings.state_dir.mkdir(parents=True, exist_ok=True)
        settings.audit_dir.mkdir(parents=True, exist_ok=True)
        settings.outputs_dir.mkdir(parents=True, exist_ok=True)
        print(
            f"STARTUP_STAGE_3_DIRECTORIES_OK state={settings.state_dir} audit={settings.audit_dir} outputs={settings.outputs_dir}",
            flush=True,
        )

        db_status = await database_status()
        print(f"STARTUP_STAGE_4_DATABASE_STATUS {db_status}", flush=True)
        if db_status["status"] == "ok":
            print("DATABASE_CONNECTED_OK", flush=True)
        elif settings.database_enabled:
            print(f"DATABASE_CONNECTED_FAILED {db_status}", flush=True)

        print(f"STARTUP_STAGE_5_MIGRATIONS_BEGIN enabled={settings.db_auto_migrate}", flush=True)
        await run_migrations_if_enabled()
        print("STARTUP_STAGE_6_MIGRATIONS_OK", flush=True)

        append_audit_event("runtime.startup", "system", {"service": settings.app_name, "version": settings.app_version})
        print("STARTUP_STAGE_7_AUDIT_OK", flush=True)
        logger.info("FORJA backend startup complete")
        print("STARTUP_COMPLETE_OK", flush=True)
    except Exception as exc:
        print(f"STARTUP_FATAL {exc.__class__.__name__}: {exc}", flush=True)
        print(traceback.format_exc(), flush=True)
        logger.exception("FORJA startup failed")
        raise

    try:
        yield
    finally:
        append_audit_event("runtime.shutdown", "system", {"service": settings.app_name})
        await dispose_engine()
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
