from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os

from dotenv import load_dotenv


load_dotenv()

LOCAL_ENV_NAMES = {"local", "dev", "development", "test"}
DEFAULT_JWT_SECRET = "local-forja-secret-change-before-prod"
DEFAULT_ADMIN_PASSWORD = "forja_local_admin_change_me"


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    return int(value)


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


@dataclass(frozen=True)
class Settings:
    app_name: str = field(default_factory=lambda: _env("FORJA_APP_NAME", "forja-backend"))
    app_version: str = field(default_factory=lambda: _env("FORJA_APP_VERSION", "0.1.0"))
    app_env: str = field(default_factory=lambda: _env("FORJA_APP_ENV", "local"))
    debug: bool = field(default_factory=lambda: _bool_env("FORJA_DEBUG", True))
    log_level: str = field(default_factory=lambda: _env("FORJA_LOG_LEVEL", "INFO"))
    api_prefix: str = field(default_factory=lambda: _env("FORJA_API_PREFIX", ""))
    frontend_origin: str = field(default_factory=lambda: _env("FORJA_FRONTEND_ORIGIN", "http://localhost:5173"))
    cors_origins_raw: str = field(default_factory=lambda: _env("FORJA_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"))
    jwt_secret: str = field(default_factory=lambda: _env("FORJA_JWT_SECRET", DEFAULT_JWT_SECRET))
    jwt_algorithm: str = field(default_factory=lambda: _env("FORJA_JWT_ALGORITHM", "HS256"))
    jwt_exp_minutes: int = field(default_factory=lambda: _int_env("FORJA_JWT_EXP_MINUTES", 60))
    admin_username: str = field(default_factory=lambda: _env("FORJA_ADMIN_USERNAME", "forja_admin"))
    admin_password: str = field(default_factory=lambda: _env("FORJA_ADMIN_PASSWORD", DEFAULT_ADMIN_PASSWORD))
    database_url: str = field(default_factory=lambda: _env("FORJA_DATABASE_URL", ""))
    database_ssl: bool = field(default_factory=lambda: _bool_env("FORJA_DATABASE_SSL", True))
    db_auto_migrate: bool = field(default_factory=lambda: _bool_env("FORJA_DB_AUTO_MIGRATE", False))
    local_agent_registration_token: str = field(default_factory=lambda: _env("FORJA_LOCAL_AGENT_REGISTRATION_TOKEN", ""))
    base_dir: Path = field(default_factory=lambda: Path(_env("FORJA_BASE_DIR", str(Path(__file__).resolve().parents[4]))))

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
    def is_local(self) -> bool:
        return self.app_env.lower() in LOCAL_ENV_NAMES

    @property
    def cors_origins(self) -> list[str]:
        values = [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]
        if self.frontend_origin and self.frontend_origin not in values:
            values.append(self.frontend_origin)
        return values

    @property
    def effective_database_url(self) -> str:
        database_url = self.database_url.strip()
        if database_url.startswith("postgresql://"):
            return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if database_url.startswith("postgres://"):
            return database_url.replace("postgres://", "postgresql+asyncpg://", 1)
        return database_url

    @property
    def database_enabled(self) -> bool:
        return bool(self.database_url.strip())

    @property
    def database_connect_args(self) -> dict:
        return {} if self.database_ssl else {"ssl": False}

    @property
    def production_ready(self) -> bool:
        return (
            not self.is_local
            and self.jwt_secret != DEFAULT_JWT_SECRET
            and self.admin_password != DEFAULT_ADMIN_PASSWORD
            and self.database_enabled
            and "*" not in self.cors_origins
        )

    def security_warnings(self) -> list[str]:
        warnings: list[str] = []
        if self.jwt_secret == DEFAULT_JWT_SECRET:
            warnings.append("default_jwt_secret_in_use")
        if self.admin_password == DEFAULT_ADMIN_PASSWORD:
            warnings.append("default_admin_password_in_use")
        if "*" in self.cors_origins:
            warnings.append("wildcard_cors_origin")
        if not self.database_enabled:
            warnings.append("database_url_not_configured")
        return warnings

    def diagnostic_snapshot(self) -> dict[str, str | bool | int]:
        return {
            "app_env": self.app_env,
            "debug": self.debug,
            "database_enabled": self.database_enabled,
            "database_ssl": self.database_ssl,
            "db_auto_migrate": self.db_auto_migrate,
            "cors_origins_count": len(self.cors_origins),
            "frontend_origin_configured": bool(self.frontend_origin),
            "jwt_secret_configured": bool(self.jwt_secret and self.jwt_secret != DEFAULT_JWT_SECRET),
            "admin_password_configured": bool(self.admin_password and self.admin_password != DEFAULT_ADMIN_PASSWORD),
            "base_dir": str(self.base_dir),
        }

    def validate_runtime_safety(self) -> None:
        print(f"STARTUP_RUNTIME_SAFETY_CHECK_BEGIN {self.diagnostic_snapshot()}", flush=True)
        if self.is_local:
            print("RUNTIME_SAFETY_OK local_environment", flush=True)
            return
        blockers = self.security_warnings()
        if blockers:
            print(f"RUNTIME_SAFETY_BLOCKED unsafe_non_local_configuration:{','.join(blockers)}", flush=True)
            raise RuntimeError(f"unsafe_non_local_configuration:{','.join(blockers)}")
        print("RUNTIME_SAFETY_OK", flush=True)


settings = Settings()
