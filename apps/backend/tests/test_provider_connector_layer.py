from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.core.audit import read_audit_events
from app.main import app


client = TestClient(app)

SECRET_ENV_VARS = ["OPENROUTER_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "DEEPSEEK_API_KEY", "QWEN_API_KEY"]


def _clear_keys(monkeypatch) -> None:
    for key in SECRET_ENV_VARS:
        monkeypatch.delenv(key, raising=False)


def _status() -> dict:
    response = client.get("/provider-connectors/status")
    assert response.status_code == 200
    return response.json()


def _provider(snapshot: dict, provider_id: str) -> dict:
    return next(provider for provider in snapshot["providers"] if provider["provider_id"] == provider_id)


def _enable(provider_id: str) -> None:
    response = client.post(f"/provider-connectors/providers/{provider_id}/enable")
    assert response.status_code == 200


def test_provider_configured_with_safe_credential(monkeypatch) -> None:
    _clear_keys(monkeypatch)
    _enable("openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-test-provider-connector-key")
    snapshot = _status()
    provider = _provider(snapshot, "openrouter")
    assert provider["credential_configured"] is True
    assert provider["credential_state"] == "configured"
    assert provider["connector_state"] == "ready"
    assert provider["safe_initialization"] is True
    assert provider["secrets_exposed"] is False


def test_provider_missing_credentials(monkeypatch) -> None:
    _clear_keys(monkeypatch)
    _enable("anthropic")
    provider = _provider(_status(), "anthropic")
    assert provider["credential_required"] is True
    assert provider["credential_state"] == "missing"
    assert provider["connector_state"] == "missing_credentials"


def test_provider_disabled(monkeypatch) -> None:
    _clear_keys(monkeypatch)
    response = client.post("/provider-connectors/providers/openai/disable")
    assert response.status_code == 200
    provider = _provider(response.json(), "openai")
    assert provider["enabled"] is False
    assert provider["connector_state"] == "disabled"
    _enable("openai")


def test_invalid_credential_format(monkeypatch) -> None:
    _clear_keys(monkeypatch)
    _enable("gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "not-a-gemini-key")
    provider = _provider(_status(), "gemini")
    assert provider["credential_state"] == "invalid"
    assert provider["connector_state"] == "invalid_credentials"


def test_capability_mismatch(monkeypatch) -> None:
    _clear_keys(monkeypatch)
    response = client.post("/provider-connectors/validate", json={"provider_id": "local_llm", "capability_type": "frontend_generation"})
    assert response.status_code == 200
    result = response.json()
    assert result["compatible"] is False
    assert result["reason"] == "capability_not_supported"


def test_fallback_ready_for_configured_backend_providers(monkeypatch) -> None:
    _clear_keys(monkeypatch)
    _enable("openrouter")
    _enable("deepseek")
    _enable("qwen")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-openrouter-connector-test")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek-connector-test")
    monkeypatch.setenv("QWEN_API_KEY", "sk-qwen-connector-test-key")
    response = client.post("/provider-connectors/validate", json={"provider_id": "openrouter", "capability_type": "backend_generation"})
    assert response.status_code == 200
    result = response.json()
    assert result["compatible"] is True
    assert "deepseek" in result["fallback_provider_ids"]
    assert "qwen" in result["fallback_provider_ids"]


def test_local_llm_preparation(monkeypatch) -> None:
    _clear_keys(monkeypatch)
    provider = _provider(_status(), "local_llm")
    assert provider["connector_state"] == "ready"
    assert provider["credential_required"] is False
    assert provider["supports_real_connection"] is False
    assert provider["status_reason"] == "local_llm_connector_prepared_without_model_execution"


def test_provider_registry_consistency(monkeypatch) -> None:
    _clear_keys(monkeypatch)
    snapshot = _status()
    provider_ids = {provider["provider_id"] for provider in snapshot["providers"]}
    assert provider_ids == {"openrouter", "openai", "anthropic", "gemini", "deepseek", "qwen", "local_llm"}
    assert all(provider["supported_capabilities"] for provider in snapshot["providers"])
    assert snapshot["external_request_executed"] is False


def test_secret_protection(monkeypatch) -> None:
    _clear_keys(monkeypatch)
    secret = "sk-or-v1-super-secret-value-that-must-not-leak"
    monkeypatch.setenv("OPENROUTER_API_KEY", secret)
    payload = _status()
    rendered = json.dumps(payload)
    assert secret not in rendered
    assert "OPENAI_API_KEY" in rendered
    assert all(provider["secrets_exposed"] is False for provider in payload["providers"])


def test_connector_audit_events(monkeypatch) -> None:
    _clear_keys(monkeypatch)
    _enable("openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-audit-provider-connector")
    client.post("/provider-connectors/validate", json={"provider_id": "openrouter", "capability_type": "coding"})
    audit_types = [event["event_type"] for event in read_audit_events(320)]
    assert "provider_connector_loaded" in audit_types
    assert "provider_ready" in audit_types
    assert "missing_credentials_detected" in audit_types
    assert "provider_validation_failed" in audit_types or "connector_disabled" in audit_types
