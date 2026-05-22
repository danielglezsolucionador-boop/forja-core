from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.core.config import settings


def create_engine() -> AsyncEngine | None:
    if not settings.database_enabled:
        return None
    return create_async_engine(settings.database_url, pool_pre_ping=True, future=True, connect_args=settings.database_connect_args)


engine = create_engine()
async_session = async_sessionmaker(engine, expire_on_commit=False) if engine is not None else None


async def dispose_engine() -> None:
    if engine is not None:
        await engine.dispose()


async def database_status() -> dict:
    if engine is None:
        return {
            "status": "not_configured",
            "enabled": False,
            "reason": "FORJA_DATABASE_URL is not set",
        }
    try:
        async with engine.connect() as connection:
            result = await connection.execute(text("select 1"))
            result.scalar_one()
        return {"status": "ok", "enabled": True, "reason": "connection_ok"}
    except Exception as exc:
        return {"status": "unavailable", "enabled": True, "reason": exc.__class__.__name__}
