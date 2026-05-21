from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("FORJA_APP_NAME", "forja-backend")
    app_version: str = os.getenv("FORJA_APP_VERSION", "0.1.0")
    app_env: str = os.getenv("FORJA_APP_ENV", "local")
    debug: bool = _bool_env("FORJA_DEBUG", True)
    log_level: str = os.getenv("FORJA_LOG_LEVEL", "INFO")
    api_prefix: str = os.getenv("FORJA_API_PREFIX", "")
    frontend_origin: str = os.getenv("FORJA_FRONTEND_ORIGIN", "http://localhost:5173")
    jwt_secret: str = os.getenv("FORJA_JWT_SECRET", "local-forja-secret-change-before-prod")
    jwt_algorithm: str = os.getenv("FORJA_JWT_ALGORITHM", "HS256")
    jwt_exp_minutes: int = int(os.getenv("FORJA_JWT_EXP_MINUTES", "60"))
    admin_username: str = os.getenv("FORJA_ADMIN_USERNAME", "forja_admin")
    admin_password: str = os.getenv("FORJA_ADMIN_PASSWORD", "forja_local_admin_change_me")
    base_dir: Path = Path(os.getenv("FORJA_BASE_DIR", Path(__file__).resolve().parents[4]))

    @property
    def state_dir(self) -> Path:
        return self.base_dir / ".forja" / "state"

    @property
    def audit_dir(self) -> Path:
        return self.base_dir / ".forja" / "audit"

    @property
    def outputs_dir(self) -> Path:
        return self.base_dir / ".forja" / "outputs"

    @property
    def production_ready(self) -> bool:
        return self.app_env.lower() not in {"local", "dev", "development"} and self.jwt_secret != "local-forja-secret-change-before-prod"


settings = Settings()
