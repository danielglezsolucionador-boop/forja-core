from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.audit import read_audit_events
from app.main import app


client = TestClient(app)


def _contract(**overrides):
    payload = {
        "capability_type": "coding",
        "reasoning_level": "medium",
        "coding_level": "high",
        "speed_priority": "balanced",
        "cost_priority": "balanced",
        "context_size": 64000,
        "provider_constraints": ["provider_agnostic"],
        "requires_human_approval": True,
        "fallback_allowed": True,
        "execution_scope": "builder_core_contract_only",
        "requested_by": "ceo",
    }
    payload.update(overrides)
    response = client.post("/capability-contracts", json=payload)
    assert response.status_code == 200
    return response.json()


def test_coding_capability_contract() -> None:
    payload = _contract(capability_type="coding", coding_level="high")
    assert payload["capability_id"].startswith("cap-")
    assert payload["capability_type"] == "coding"
    assert payload["coding_level"] == "high"
    assert payload["provider_constraints"] == ["provider_agnostic", "no_model_selection", "no_api_execution"]


def test_reasoning_capability_contract() -> None:
    payload = _contract(capability_type="reasoning", reasoning_level="high", coding_level="none")
    assert payload["capability_type"] == "reasoning"
    assert payload["reasoning_level"] == "high"
    assert payload["requires_human_approval"] is True


def test_repair_capability_requires_human_approval_by_profile() -> None:
    payload = _contract(
        capability_type="repair",
        reasoning_level="high",
        coding_level="expert",
        requires_human_approval=None,
        fallback_allowed=False,
    )
    assert payload["capability_type"] == "repair"
    assert payload["requires_human_approval"] is True
    assert payload["fallback_allowed"] is False


def test_architecture_capability_contract() -> None:
    payload = _contract(capability_type="architecture", reasoning_level="high", coding_level="medium")
    assert payload["capability_type"] == "architecture"
    assert payload["execution_scope"] == "builder_core_contract_only"


def test_premium_allowed_cost_priority() -> None:
    payload = _contract(cost_priority="premium_allowed", requires_human_approval=None)
    assert payload["cost_priority"] == "premium_allowed"
    assert payload["requires_human_approval"] is True


def test_low_cost_priority() -> None:
    payload = _contract(capability_type="summarization", cost_priority="low_cost", coding_level="none", requires_human_approval=None)
    assert payload["cost_priority"] == "low_cost"
    assert payload["requires_human_approval"] is False


def test_maximum_quality_speed_priority() -> None:
    payload = _contract(speed_priority="maximum_quality", requires_human_approval=None)
    assert payload["speed_priority"] == "maximum_quality"
    assert payload["requires_human_approval"] is True


def test_fallback_enabled() -> None:
    payload = _contract(fallback_allowed=True)
    assert payload["fallback_allowed"] is True


def test_fallback_disabled() -> None:
    payload = _contract(capability_type="analysis", coding_level="none", fallback_allowed=False, requires_human_approval=None)
    assert payload["fallback_allowed"] is False
    assert payload["requires_human_approval"] is True


def test_provider_specific_contract_is_blocked_and_audits_contracts() -> None:
    blocked = client.post(
        "/capability-contracts",
        json={
            "capability_type": "reasoning",
            "reasoning_level": "medium",
            "coding_level": "none",
            "speed_priority": "balanced",
            "cost_priority": "balanced",
            "context_size": 32000,
            "provider_constraints": ["openai"],
            "fallback_allowed": True,
            "execution_scope": "capability_contract_only",
            "requested_by": "ceo",
        },
    )
    assert blocked.status_code == 400
    assert blocked.json()["detail"] == "provider_specific_contract_blocked"

    _contract(capability_type="documentation", coding_level="none")
    audit_types = [event["event_type"] for event in read_audit_events(120)]
    assert "capability_requested" in audit_types
    assert "capability_profile_generated" in audit_types
