from __future__ import annotations

import pytest

from app.core.config import DEFAULT_ADMIN_PASSWORD, DEFAULT_JWT_SECRET, Settings


def test_non_local_environment_blocks_insecure_defaults() -> None:
    settings = Settings(app_env="production", jwt_secret=DEFAULT_JWT_SECRET, admin_password=DEFAULT_ADMIN_PASSWORD)
    with pytest.raises(RuntimeError):
        settings.validate_runtime_safety()


def test_local_environment_allows_bootstrap_but_reports_warning() -> None:
    settings = Settings(app_env="local", jwt_secret=DEFAULT_JWT_SECRET, admin_password=DEFAULT_ADMIN_PASSWORD)
    settings.validate_runtime_safety()
    assert "default_jwt_secret_in_use" in settings.security_warnings()
    assert "default_admin_password_in_use" in settings.security_warnings()


def test_cors_origins_are_environment_configured() -> None:
    settings = Settings(cors_origins_raw="http://localhost:5173,http://127.0.0.1:5173")
    assert "http://localhost:5173" in settings.cors_origins
    assert "*" not in settings.cors_origins
