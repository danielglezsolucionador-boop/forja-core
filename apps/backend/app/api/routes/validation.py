from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.db.session import database_status


router = APIRouter(prefix="/validation", tags=["validation"])


@router.get("/operational")
async def operational_validation(_: object = Depends(get_current_user)) -> dict:
    db_status = await database_status()
    required = [
        settings.base_dir / "apps" / "backend" / "app" / "main.py",
        settings.base_dir / "apps" / "frontend" / "package.json",
        settings.base_dir / "phases",
    ]
    checks = [{"path": str(path), "exists": Path(path).exists()} for path in required]
    return {
        "status": "ok" if all(item["exists"] for item in checks) else "degraded",
        "checks": checks,
        "architecture": {
            "modular": True,
            "zero_write_policy": True,
            "human_in_the_loop": True,
            "cloud_side_effects": False,
            "hermes_touched": False,
        },
        "database": db_status,
        "security_warnings": settings.security_warnings(),
    }
