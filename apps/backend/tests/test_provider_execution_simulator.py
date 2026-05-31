from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.audit import read_audit_events
from app.main import app


client = TestClient(app)


def _contract(**overrides) -> dict:
    payload = {
        "capability_type": "frontend_generation",
        "reasoning_level": "medium",
        "coding_level": "high",
        "speed_priority": "balanced",
        "cost_priority": "balanced",
        "context_size": 64000,
        "provider_constraints": ["provider_agnostic"],
        "requires_human_approval": True,
        "fallback_allowed": True,
        "execution_scope": "provider_execution_simulation_test",
        "requested_by": "ceo",
    }
    payload.update(overrides)
    response = client.post("/capability-contracts", json=payload)
    assert response.status_code == 200
    return response.json()


def _simulate(contract: dict, **overrides) -> dict:
    payload = {"contract": contract}
    payload.update(overrides)
    response = client.post("/provider-execution/simulate", json=payload)
    assert response.status_code == 200
    return response.json()


def test_frontend_simulation_generates_operational_result() -> None:
    result = _simulate(_contract(capability_type="frontend_generation"))
    assert result["execution_status"] == "completed"
    assert result["generated_summary"].endswith("React dashboard structure prepared.")
    assert result["provider_used"]["provider_id"] == "openrouter"
    assert result["provider_used"]["cost_profile"] == "low_cost"
    assert result["external_request_executed"] is False
    assert any(output["kind"] == "frontend_generation" for output in result["outputs"])


def test_backend_simulation_generates_fastapi_summary() -> None:
    result = _simulate(_contract(capability_type="backend_generation", cost_priority="low_cost"))
    assert "FastAPI routes generated" in result["generated_summary"]
    assert result["execution_mode"] == "low_cost"
    assert result["estimated_cost_profile"] == "low_cost"


def test_repair_simulation_uses_premium_profile() -> None:
    result = _simulate(
        _contract(
            capability_type="repair",
            reasoning_level="high",
            coding_level="expert",
            cost_priority="premium_allowed",
            fallback_allowed=False,
        )
    )
    assert "Potential architecture issues detected" in result["generated_summary"]
    assert result["execution_mode"] == "premium"
    assert result["provider_used"]["provider_id"] in {"anthropic", "openai"}


def test_architecture_simulation_generates_architecture_output() -> None:
    result = _simulate(_contract(capability_type="architecture", reasoning_level="high", coding_level="medium"))
    assert "Microservice-ready structure recommended" in result["generated_summary"]
    assert any(output["kind"] == "architecture_plan" for output in result["outputs"])


def test_fallback_simulation_activates_prepared_chain() -> None:
    result = _simulate(_contract(capability_type="frontend_generation"), failure_mode="provider_unavailable")
    assert result["fallback_triggered"] is True
    assert result["fallback_provider_used"] is not None
    assert result["provider_used"]["provider_id"] == result["fallback_provider_used"]["provider_id"]
    assert any(event["event"] == "fallback.triggered" for event in result["timeline"])


def test_timeout_simulation_enters_degraded_mode_with_fallback() -> None:
    result = _simulate(_contract(capability_type="documentation", reasoning_level="medium", coding_level="none"), failure_mode="timeout")
    assert result["fallback_triggered"] is True
    assert result["execution_status"] == "degraded_mode"
    assert result["estimated_duration"] > 0


def test_provider_unavailable_simulation_completes_on_fallback() -> None:
    result = _simulate(_contract(capability_type="reasoning", coding_level="none"), failure_mode="provider_unavailable")
    assert result["execution_status"] == "completed"
    assert result["fallback_triggered"] is True
    assert "Fallback simulation completed" in result["generated_summary"]


def test_degraded_mode_low_confidence_uses_fallback() -> None:
    result = _simulate(_contract(capability_type="analysis", coding_level="none"), failure_mode="low_confidence")
    assert result["execution_status"] == "degraded_mode"
    assert result["fallback_triggered"] is True
    assert result["simulated_quality"] in {"low", "medium", "high"}


def test_premium_mode_simulation_estimates_premium_cost() -> None:
    result = _simulate(_contract(capability_type="reasoning", reasoning_level="extreme", coding_level="none", cost_priority="premium_allowed"))
    assert result["execution_mode"] == "premium"
    assert result["estimated_cost"] > 0
    assert result["provider_used"]["premium_provider"] is True


def test_low_cost_mode_simulation_selects_low_cost_provider() -> None:
    result = _simulate(_contract(capability_type="coding", cost_priority="low_cost", coding_level="high"))
    assert result["execution_mode"] == "low_cost"
    assert result["provider_used"]["cost_profile"] == "low_cost"


def test_failed_execution_when_primary_fails_without_fallback() -> None:
    result = _simulate(_contract(capability_type="repair", fallback_allowed=False), failure_mode="forced_failure")
    assert result["execution_status"] == "failed"
    assert result["fallback_triggered"] is False
    assert any(output["kind"] == "failure_report" for output in result["outputs"])


def test_provider_disabled_failure_mode_activates_fallback() -> None:
    result = _simulate(_contract(capability_type="backend_generation", cost_priority="low_cost"), failure_mode="provider_disabled")
    assert result["fallback_triggered"] is True
    assert result["provider_used"]["provider_id"] != result["primary_provider_attempted"]["provider_id"]


def test_audit_consistency_for_simulated_execution() -> None:
    result = _simulate(_contract(capability_type="documentation", coding_level="none"))
    audit_types = [event["event_type"] for event in result["audit_events"]]
    assert "execution_started" in audit_types
    assert "provider_execution_started" in audit_types
    assert "execution_completed" in audit_types

    global_audit_types = [event["event_type"] for event in read_audit_events(260)]
    assert "execution_started" in global_audit_types
    assert "provider_execution_started" in global_audit_types
