from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.audit import read_audit_events
from app.main import app


client = TestClient(app)


def _contract(**overrides) -> dict:
    payload = {
        "capability_type": "coding",
        "reasoning_level": "medium",
        "coding_level": "high",
        "speed_priority": "balanced",
        "cost_priority": "low_cost",
        "context_size": 64000,
        "provider_constraints": ["provider_agnostic"],
        "requires_human_approval": True,
        "fallback_allowed": True,
        "execution_scope": "ai_gateway_foundation_test",
        "requested_by": "ceo",
    }
    payload.update(overrides)
    response = client.post("/capability-contracts", json=payload)
    assert response.status_code == 200
    return response.json()


def _status() -> dict:
    response = client.get("/ai-gateway/status")
    assert response.status_code == 200
    return response.json()


def _provider(snapshot: dict, provider_id: str) -> dict:
    return next(provider for provider in snapshot["providers"] if provider["provider_id"] == provider_id)


def _enable(*provider_ids: str) -> None:
    for provider_id in provider_ids:
        response = client.post(f"/ai-gateway/providers/{provider_id}/enable")
        assert response.status_code == 200


def _decision(contract: dict) -> dict:
    response = client.post("/ai-gateway/decision", json={"contract": contract})
    assert response.status_code == 200
    return response.json()


def test_provider_registry_loads_mock_providers() -> None:
    snapshot = _status()
    provider_ids = {provider["provider_id"] for provider in snapshot["providers"]}
    assert {"openai", "anthropic", "gemini", "deepseek", "qwen", "local_llm"}.issubset(provider_ids)
    assert _provider(snapshot, "openai")["enabled"] is True
    assert _provider(snapshot, "openai")["fallback_priority"] == 1
    assert snapshot["external_request_executed"] is False


def test_capability_registry_loads_required_capabilities() -> None:
    snapshot = _status()
    capabilities = {capability["capability_type"] for capability in snapshot["capabilities"]}
    assert {
        "reasoning",
        "coding",
        "frontend_generation",
        "backend_generation",
        "debugging",
        "repair",
        "architecture",
        "analysis",
        "summarization",
        "documentation",
    }.issubset(capabilities)


def test_provider_disable_updates_registry_and_audit() -> None:
    response = client.post("/ai-gateway/providers/deepseek/disable")
    assert response.status_code == 200
    provider = _provider(response.json(), "deepseek")
    assert provider["enabled"] is False
    assert provider["availability"] == "disabled"

    audit_types = [event["event_type"] for event in read_audit_events(260)]
    assert "provider_disabled" in audit_types


def test_provider_enable_restores_active_state() -> None:
    client.post("/ai-gateway/providers/deepseek/disable")
    response = client.post("/ai-gateway/providers/deepseek/enable")
    assert response.status_code == 200
    provider = _provider(response.json(), "deepseek")
    assert provider["enabled"] is True
    assert provider["availability"] == "active"


def test_degraded_provider_remains_available_but_gateway_is_degraded() -> None:
    _enable("gemini")
    response = client.post("/ai-gateway/providers/gemini/health", json={"health_state": "degraded", "simulated_latency": 1400, "simulated_failure_rate": 0.24})
    assert response.status_code == 200
    snapshot = response.json()
    provider = _provider(snapshot, "gemini")
    assert provider["availability"] == "degraded"
    assert provider["enabled"] is True
    assert snapshot["gateway_status"] == "degraded"


def test_unavailable_provider_is_filtered_from_gateway_decision() -> None:
    _enable("openai", "gemini")
    response = client.post("/ai-gateway/providers/openai/health", json={"health_state": "unavailable"})
    assert response.status_code == 200
    decision = _decision(_contract(capability_type="frontend_generation", cost_priority="balanced"))
    assert decision["selected_provider"]["provider_id"] != "openai"
    assert "openai" in decision["availability_filter"]
    _enable("openai")


def test_fallback_provider_available_for_frontend_capability() -> None:
    _enable("openai", "gemini")
    decision = _decision(_contract(capability_type="frontend_generation", cost_priority="balanced"))
    assert decision["selected_provider"] is not None
    assert decision["fallback_provider"] is not None
    assert len(decision["fallback_tree"]) >= 1


def test_provider_health_update_sets_snapshot_values() -> None:
    response = client.post("/ai-gateway/providers/qwen/health", json={"health_state": "maintenance", "simulated_latency": 0, "simulated_failure_rate": 1.0})
    assert response.status_code == 200
    provider = _provider(response.json(), "qwen")
    assert provider["health"]["health_state"] == "maintenance"
    assert provider["health"]["simulated_latency"] == 0
    assert provider["health"]["simulated_failure_rate"] == 1.0
    _enable("qwen")


def test_capability_lookup_returns_mapping_and_fallback_tree() -> None:
    _enable("openai", "deepseek", "qwen")
    response = client.get("/ai-gateway/capabilities/backend_generation")
    assert response.status_code == 200
    payload = response.json()
    assert payload["capability"]["capability_type"] == "backend_generation"
    assert "openai" in payload["capability"]["provider_ids"]
    assert payload["external_request_executed"] is False


def test_gateway_routing_access_uses_registry_health_filtering() -> None:
    _enable("deepseek", "qwen")
    client.post("/ai-gateway/providers/deepseek/disable")
    decision = _decision(_contract(capability_type="coding", cost_priority="low_cost"))
    assert decision["selected_provider"]["provider_id"] == "qwen"
    assert "deepseek" in decision["availability_filter"]
    assert decision["routing_plan"]["external_request_executed"] is False
    assert decision["external_request_executed"] is False
    _enable("deepseek")
