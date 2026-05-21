from __future__ import annotations

import asyncio

from alembic import command
from alembic.config import Config

from app.core.config import settings


async def run_migrations_if_enabled() -> None:
    if not settings.database_enabled or not settings.db_auto_migrate:
        return
    await asyncio.to_thread(_run_upgrade_head)


def _run_upgrade_head() -> None:
    config = Config(str(settings.base_dir / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(config, "head")
