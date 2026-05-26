from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.audit import read_audit_events
from app.main import app


client = TestClient(app)


def _contract(**overrides) -> dict:
    payload = {
        "capability_type": "reasoning",
        "reasoning_level": "medium",
        "coding_level": "none",
        "speed_priority": "balanced",
        "cost_priority": "balanced",
        "context_size": 64000,
        "provider_constraints": ["provider_agnostic"],
        "requires_human_approval": None,
        "fallback_allowed": True,
        "execution_scope": "provider_abstraction_test_only",
        "requested_by": "ceo",
    }
    payload.update(overrides)
    response = client.post("/capability-contracts", json=payload)
    assert response.status_code == 200
    return response.json()


def _route(contract: dict) -> dict:
    response = client.post("/provider-abstraction/route", json={"contract": contract})
    assert response.status_code == 200
    return response.json()


def test_reasoning_high_routes_to_anthropic_or_openai() -> None:
    decision = _route(_contract(reasoning_level="high", cost_priority="premium_allowed"))
    assert decision["selected_provider"]["provider_id"] in {"anthropic", "openai"}
    assert decision["selected_provider"]["reasoning_strength"] in {"high", "extreme"}
    assert decision["confidence"] > 0.7
    assert decision["external_request_executed"] is False


def test_low_cost_coding_routes_to_deepseek_with_qwen_fallback() -> None:
    decision = _route(_contract(capability_type="coding", coding_level="high", cost_priority="low_cost"))
    assert decision["selected_provider"]["provider_id"] == "deepseek"
    assert decision["fallback_provider"]["provider_id"] == "qwen"
    assert decision["estimated_cost_profile"] == "low_cost"


def test_frontend_generation_prefers_openai_or_gemini() -> None:
    decision = _route(_contract(capability_type="frontend_generation", coding_level="high"))
    assert decision["selected_provider"]["provider_id"] in {"openai", "gemini"}
    assert {provider["provider_id"] for provider in decision["compatible_providers"]}.issuperset({"openai", "gemini"})


def test_backend_generation_has_coding_compatible_profiles() -> None:
    decision = _route(_contract(capability_type="backend_generation", coding_level="high", cost_priority="balanced"))
    assert decision["selected_provider"]["provider_id"] in {"openai", "deepseek", "qwen"}
    assert all("backend_generation" in provider["supported_capabilities"] for provider in decision["compatible_providers"])


def test_premium_provider_profile_is_available_for_premium_contract() -> None:
    decision = _route(_contract(capability_type="architecture", reasoning_level="high", cost_priority="premium_allowed"))
    assert decision["selected_provider"]["premium_provider"] is True
    assert decision["estimated_quality_profile"] in {"high", "extreme"}


def test_local_provider_constraint_routes_to_local_profile() -> None:
    decision = _route(
        _contract(
            capability_type="analysis",
            reasoning_level="low",
            context_size=16000,
            provider_constraints=["local_only"],
        )
    )
    assert decision["selected_provider"]["provider_id"] == "local_llm"
    assert decision["selected_provider"]["local_provider"] is True
    assert decision["fallback_provider"] is None


def test_fallback_allowed_prepares_alternate_provider() -> None:
    decision = _route(_contract(capability_type="reasoning", fallback_allowed=True))
    assert decision["fallback_provider"] is not None
    assert decision["fallback_strategy"].startswith("prepare_alternate_provider:")


def test_fallback_disabled_returns_no_fallback() -> None:
    decision = _route(_contract(capability_type="reasoning", fallback_allowed=False))
    assert decision["fallback_provider"] is None
    assert decision["fallback_strategy"] == "disabled_by_contract"


def test_incompatible_capability_returns_no_selected_provider() -> None:
    decision = _route(
        _contract(
            capability_type="coding",
            coding_level="high",
            context_size=128000,
            provider_constraints=["local_only"],
        )
    )
    assert decision["selected_provider"] is None
    assert decision["fallback_provider"] is None
    assert decision["confidence"] == 0.0
    assert decision["compatible_providers"] == []


def test_profiles_and_audit_events_are_exposed() -> None:
    profiles = client.get("/provider-abstraction/profiles")
    assert profiles.status_code == 200
    provider_ids = {profile["provider_id"] for profile in profiles.json()}
    assert {"openai", "anthropic", "gemini", "deepseek", "qwen", "local_llm"}.issubset(provider_ids)

    _route(_contract(capability_type="documentation", reasoning_level="low"))
    audit_types = [event["event_type"] for event in read_audit_events(160)]
    assert "provider_matching_started" in audit_types
    assert "provider_selected" in audit_types
    assert "fallback_prepared" in audit_types
