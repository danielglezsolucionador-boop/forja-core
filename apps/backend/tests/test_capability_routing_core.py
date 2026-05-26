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
        "execution_scope": "capability_routing_core_test",
        "requested_by": "ceo",
    }
    payload.update(overrides)
    response = client.post("/capability-contracts", json=payload)
    assert response.status_code == 200
    return response.json()


def _plan(contract: dict, **overrides) -> dict:
    payload = {"contract": contract}
    payload.update(overrides)
    response = client.post("/capability-routing/plan", json=payload)
    assert response.status_code == 200
    return response.json()


def test_low_cost_request_routes_to_low_cost_coding_profiles() -> None:
    plan = _plan(_contract(capability_type="coding", coding_level="high", cost_priority="low_cost"))
    assert plan["execution_mode"] == "low_cost"
    assert plan["primary_provider"]["provider_id"] == "deepseek"
    assert plan["fallback_provider"]["provider_id"] == "qwen"
    assert plan["estimated_cost"] == "low_cost"


def test_premium_request_routes_to_premium_provider() -> None:
    plan = _plan(_contract(capability_type="architecture", reasoning_level="high", cost_priority="premium_allowed"))
    assert plan["execution_mode"] == "premium"
    assert plan["primary_provider"]["premium_provider"] is True
    assert plan["approval_required"] is True


def test_frontend_request_routes_to_frontend_specialist() -> None:
    plan = _plan(_contract(capability_type="frontend_generation", coding_level="high", speed_priority="balanced"))
    assert plan["primary_provider"]["provider_id"] in {"openai", "gemini"}
    assert "frontend_generation" in plan["primary_provider"]["supported_capabilities"]


def test_backend_request_routes_to_backend_capable_provider() -> None:
    plan = _plan(_contract(capability_type="backend_generation", coding_level="high", cost_priority="balanced"))
    assert plan["primary_provider"]["provider_id"] in {"openai", "deepseek", "qwen"}
    assert "backend_generation" in plan["primary_provider"]["supported_capabilities"]


def test_repair_request_routes_to_premium_provider_and_high_risk() -> None:
    plan = _plan(_contract(capability_type="repair", reasoning_level="high", coding_level="expert", fallback_allowed=True))
    assert plan["execution_mode"] == "premium"
    assert plan["risk_level"] == "HIGH"
    assert plan["primary_provider"]["provider_id"] in {"anthropic", "openai"}
    assert plan["approval_required"] is True


def test_reasoning_extreme_routes_to_high_quality_provider() -> None:
    plan = _plan(_contract(reasoning_level="extreme", cost_priority="premium_allowed"))
    assert plan["execution_mode"] == "premium"
    assert plan["primary_provider"]["provider_id"] in {"anthropic", "openai"}
    assert plan["estimated_quality"] in {"extreme", "high"}
    assert plan["risk_level"] == "HIGH"


def test_provider_disabled_is_excluded_from_selection() -> None:
    plan = _plan(
        _contract(capability_type="coding", coding_level="high", cost_priority="low_cost"),
        disabled_provider_ids=["deepseek"],
    )
    assert plan["primary_provider"]["provider_id"] == "qwen"
    assert all(score["provider_id"] != "deepseek" for score in plan["provider_scores"])


def test_fallback_enabled_builds_fallback_tree() -> None:
    plan = _plan(_contract(capability_type="reasoning", fallback_allowed=True))
    assert plan["fallback_provider"] is not None
    assert len(plan["fallback_tree"]) >= 1
    assert [event["event"] for event in plan["timeline"]] == [
        "capability.analyzed",
        "providers.evaluated",
        "provider.selected",
        "fallback.prepared",
    ]


def test_fallback_disabled_keeps_empty_fallback_tree() -> None:
    plan = _plan(_contract(capability_type="reasoning", fallback_allowed=False))
    assert plan["fallback_provider"] is None
    assert plan["fallback_tree"] == []
    assert "Fallback disabled" in plan["timeline"][-1]["detail"]


def test_incompatible_provider_returns_no_primary() -> None:
    plan = _plan(_contract(capability_type="frontend_generation", provider_constraints=["local_only"]))
    assert plan["primary_provider"] is None
    assert plan["fallback_provider"] is None
    assert plan["confidence"] == 0.0


def test_safe_mode_prefers_local_simple_fast_request() -> None:
    plan = _plan(
        _contract(
            capability_type="reasoning",
            reasoning_level="low",
            speed_priority="fast",
            context_size=16000,
            provider_constraints=["safe_mode", "local_only"],
        )
    )
    assert plan["execution_mode"] == "safe_mode"
    assert plan["primary_provider"]["provider_id"] == "local_llm"
    assert plan["primary_provider"]["local_provider"] is True


def test_experimental_mode_requires_approval() -> None:
    plan = _plan(_contract(capability_type="analysis", provider_constraints=["experimental_mode"]))
    assert plan["execution_mode"] == "experimental"
    assert plan["risk_level"] == "HIGH"
    assert plan["approval_required"] is True


def test_routing_audit_events_are_recorded() -> None:
    _plan(_contract(capability_type="documentation", reasoning_level="low"))
    audit_types = [event["event_type"] for event in read_audit_events(240)]
    assert "routing_started" in audit_types
    assert "provider_evaluated" in audit_types
    assert "routing_completed" in audit_types
    assert "fallback_prepared" in audit_types
