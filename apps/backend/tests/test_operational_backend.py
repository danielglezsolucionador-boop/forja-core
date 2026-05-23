from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from app.core.audit import read_audit_events
from app.core.config import settings
from app.main import app
from app.services.creator_service import creator_service


client = TestClient(app)


def login() -> str:
    response = client.post("/auth/login", json={"username": settings.admin_username, "password": settings.admin_password})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_health_contract() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "forja-backend"
    assert payload["modules"]["auth"] == "active"
    assert payload["database"]["status"] in {"not_configured", "ok", "unavailable"}


def test_auth_me_blocks_invalid_token() -> None:
    response = client.get("/auth/me", headers={"Authorization": "Bearer invalid"})
    assert response.status_code == 401


def test_auth_me_accepts_valid_token() -> None:
    token = login()
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["username"] == settings.admin_username


def test_runtime_is_honest_about_no_busy_loop() -> None:
    response = client.get("/runtime/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["busy_loop"] is False
    assert payload["runtime_loop"] == "not_started_by_design"
    assert payload["zero_write_policy"] is True
    assert payload["database"]["status"] in {"not_configured", "ok", "unavailable"}


def test_factory_execution_blocks_without_human_approval() -> None:
    token = login()
    headers = {"Authorization": f"Bearer {token}"}
    request = client.post(
        "/factory/requests",
        headers=headers,
        json={"name": "Canary Dashboard", "app_kind": "dashboard", "description": "Operational canary", "modules": ["health"]},
    )
    assert request.status_code == 200
    request_id = request.json()["id"]
    approval_id = request.json()["approval_request_id"]
    plan = client.get(f"/factory/requests/{request_id}/plan", headers=headers)
    assert plan.status_code == 200
    assert plan.json()["write_policy"] == "zero_write_until_human_approval"
    execution = client.post(
        f"/factory/requests/{request_id}/execute",
        headers=headers,
        json={"approval_request_id": approval_id, "allow_write": False},
    )
    assert execution.status_code == 200
    assert execution.json()["status"] == "blocked"


def test_ai_pipeline_records_but_blocks_provider_execution() -> None:
    token = login()
    response = client.post(
        "/ai/pipeline/requests",
        headers={"Authorization": f"Bearer {token}"},
        json={"objective": "summarize architecture", "input_summary": "local canary", "constraints": ["no external provider"]},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "blocked_provider_disabled"
    assert payload["provider_id"] == "ai.local-disabled"


def test_creator_console_blocks_without_provider_execution() -> None:
    response = client.post(
        "/creator/commands",
        json={"sender": "cerebro", "command": "Build a controlled operator module", "details": "Use external AI provider."},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["sender"] == "cerebro"
    assert payload["reply_to_sender"] == "cerebro"
    assert payload["status"] == "blocked"
    assert payload["response"] == "blocked_provider_disabled"
    assert payload["governance"]["provider_status"] == "disabled"

    state = client.get("/creator/console")
    assert state.status_code == 200
    assert state.json()["provider_state"] == "provider_disabled_by_governance"


def test_creator_execution_requires_approval_then_completes_metadata_only() -> None:
    response = client.post(
        "/creator/commands",
        json={"sender": "user", "command": "Prepare workflow module", "details": "Metadata only. No external AI."},
    )
    assert response.status_code == 200
    created = response.json()
    assert created["status"] == "awaiting_approval"
    assert created["request_type"] == "workflow"
    assert created["reply_to_sender"] == "user"

    blocked = client.post(f"/creator/commands/{created['id']}/execute", json={"metadata_only": True})
    assert blocked.status_code == 200
    assert blocked.json()["status"] == "blocked"
    assert blocked.json()["response"] == "missing_human_approval"

    approved = client.post(
        f"/creator/commands/{created['id']}/decision",
        json={"decision": "approve", "reason": "Controlled metadata-only execution approved."},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["governance"]["approval_status"] == "approved"

    executed = client.post(f"/creator/commands/{created['id']}/execute", json={"metadata_only": True})
    assert executed.status_code == 200
    payload = executed.json()
    assert payload["status"] == "completed"
    assert payload["response"] == "metadata_only_completed_for_user"
    assert any(item["event"] == "execution.completed" for item in payload["timeline"])
    assert any(item["output_type"] == "workflow_plan" and item["mode"] == "metadata_only_output" for item in payload["outputs"])


def test_creator_execution_is_idempotent_after_completion() -> None:
    response = client.post(
        "/creator/commands",
        json={"sender": "user", "command": "Prepare module package", "details": "Metadata only. No external AI."},
    )
    assert response.status_code == 200
    created = response.json()

    approved = client.post(
        f"/creator/commands/{created['id']}/decision",
        json={"decision": "approve", "reason": "Idempotency validation."},
    )
    assert approved.status_code == 200

    first = client.post(f"/creator/commands/{created['id']}/execute", json={"metadata_only": True})
    assert first.status_code == 200
    second = client.post(f"/creator/commands/{created['id']}/execute", json={"metadata_only": True})
    assert second.status_code == 200

    payload = second.json()
    module_outputs = [output for output in payload["outputs"] if output["output_type"] == "module_plan"]
    completed_summaries = [output for output in payload["outputs"] if output["output_type"] == "execution_summary" and output["status"] == "completed"]
    assert payload["status"] == "completed"
    assert len(module_outputs) == 1
    assert len(completed_summaries) == 1
    assert len([item for item in payload["timeline"] if item["event"] == "execution.started"]) == 1
    assert len([item for item in payload["timeline"] if item["event"] == "execution.completed"]) == 1
    assert any(item["event"] == "execution.duplicate_blocked" for item in payload["timeline"])
    assert any(event["event_type"] == "creator.duplicate_execution_blocked" for event in read_audit_events(200))


def test_creator_execution_blocks_concurrent_duplicate_attempts() -> None:
    response = client.post(
        "/creator/commands",
        json={"sender": "cerebro", "command": "Prepare integration module", "details": "Metadata only. No external AI."},
    )
    assert response.status_code == 200
    created = response.json()

    approved = client.post(
        f"/creator/commands/{created['id']}/decision",
        json={"decision": "approve", "reason": "Concurrent idempotency validation."},
    )
    assert approved.status_code == 200

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: creator_service.execute_command(created["id"], True), range(8)))

    assert all(result is not None for result in results)
    final = creator_service.execute_command(created["id"], True)
    assert final is not None
    integration_outputs = [output for output in final["outputs"] if output["output_type"] == "integration_plan"]
    completed_summaries = [output for output in final["outputs"] if output["output_type"] == "execution_summary" and output["status"] == "completed"]
    assert final["status"] == "completed"
    assert len(integration_outputs) == 1
    assert len(completed_summaries) == 1
    assert len([item for item in final["timeline"] if item["event"] == "execution.started"]) == 1
    assert len([item for item in final["timeline"] if item["event"] == "execution.completed"]) == 1
    assert len([item for item in final["timeline"] if item["event"] == "execution.duplicate_blocked"]) >= 1
    assert any(event["event_type"] == "creator.duplicate_execution_blocked" for event in read_audit_events(300))


def test_creator_output_manager_lists_downloads_and_associates_metadata() -> None:
    response = client.post(
        "/creator/commands",
        json={"sender": "seo", "command": "Prepare API blueprint", "details": "Metadata only. No external AI."},
    )
    assert response.status_code == 200
    created = response.json()
    assert created["sender"] == "seo"
    assert created["status"] == "awaiting_approval"

    approved = client.post(
        f"/creator/commands/{created['id']}/decision",
        json={"decision": "approve", "reason": "Output manager validation."},
    )
    assert approved.status_code == 200

    executed = client.post(f"/creator/commands/{created['id']}/execute", json={"metadata_only": True})
    assert executed.status_code == 200
    payload = executed.json()
    assert payload["status"] == "completed"
    assert any(output["output_type"] == "api_blueprint" for output in payload["outputs"])
    assert all(output["mode"] == "metadata_only_output" for output in payload["outputs"])

    outputs = client.get(f"/creator/commands/{created['id']}/outputs")
    assert outputs.status_code == 200
    command_outputs = outputs.json()
    output_id = next(output["id"] for output in command_outputs if output["output_type"] == "api_blueprint")

    listed = client.get("/creator/outputs", params={"sender": "seo"})
    assert listed.status_code == 200
    assert any(output["id"] == output_id for output in listed.json())

    detail = client.get(f"/creator/outputs/{output_id}")
    assert detail.status_code == 200
    assert detail.json()["summary"].startswith("metadata_only_output")
    assert "source_code" in detail.json()["not_produced"]

    metadata = client.get(f"/creator/outputs/{output_id}/metadata")
    assert metadata.status_code == 200
    assert "attachment" in metadata.headers["content-disposition"]
    assert metadata.json()["id"] == output_id

    associated = client.post(
        f"/creator/commands/{created['id']}/outputs",
        json={
            "output_type": "execution_summary",
            "title": "Operator Metadata Note",
            "summary": "Associated during output manager validation.",
            "content": {"validation": "artifact_registry"},
        },
    )
    assert associated.status_code == 200
    assert associated.json()["mode"] == "metadata_only_output"
    assert associated.json()["request_id"] == created["id"]


def test_creator_capability_requests_are_sender_aware_and_audited() -> None:
    user_request = client.post(
        "/creator/capabilities",
        json={
            "sender": "user",
            "objective": "Need OCR for invoice review",
            "explanation": "FORJA needs OCR capability to inspect scanned fiscal documents.",
            "requirements": [
                {
                    "kind": "ocr",
                    "characteristics": ["spanish_documents", "structured_text"],
                    "reason": "Scanned invoices cannot be inspected as plain text.",
                    "priority": "high",
                }
            ],
        },
    )
    assert user_request.status_code == 200
    payload = user_request.json()
    assert payload["status"] == "pending"
    assert payload["reply_to"] == "ceo"
    assert payload["response"] == "capability_request_pending_for_ceo"
    assert payload["governance"]["external_api_calls_enabled"] is False

    blocked_metadata = client.post(
        f"/creator/capabilities/{payload['id']}/metadata",
        json={"metadata": {"capability_scope": "ocr_only"}},
    )
    assert blocked_metadata.status_code == 409
    assert blocked_metadata.json()["detail"] == "capability_request_not_approved"

    approved = client.post(
        f"/creator/capabilities/{payload['id']}/approve",
        json={"reason": "CEO approved OCR capability search without provider selection."},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    attached = client.post(
        f"/creator/capabilities/{payload['id']}/metadata",
        json={"metadata": {"capability_scope": "ocr_only", "constraints": ["no_api_calls_yet"]}},
    )
    assert attached.status_code == 200
    attached_payload = attached.json()
    assert attached_payload["approved_metadata"]["metadata_only"] is True
    assert attached_payload["approved_metadata"]["provider_selected"] is False
    assert attached_payload["approved_metadata"]["api_consumption_enabled"] is False

    cerebro_request = client.post(
        "/creator/capabilities",
        json={
            "sender": "cerebro",
            "objective": "Need stronger reasoning",
            "explanation": "Cerebro asks FORJA to request stronger reasoning capability for architecture planning.",
            "requirements": [
                {
                    "kind": "strong_reasoning",
                    "characteristics": ["architecture_planning"],
                    "reason": "The task needs deeper multi-step planning.",
                    "priority": "medium",
                }
            ],
        },
    )
    assert cerebro_request.status_code == 200
    assert cerebro_request.json()["reply_to"] == "cerebro"
    assert cerebro_request.json()["response"] == "capability_request_pending_for_cerebro"

    rejected = client.post(
        f"/creator/capabilities/{cerebro_request.json()['id']}/reject",
        json={"reason": "Cerebro rejected this request for now."},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"

    listed = client.get("/creator/capabilities", params={"sender": "user"})
    assert listed.status_code == 200
    assert any(item["id"] == payload["id"] for item in listed.json())

    state = client.get("/creator/console")
    assert state.status_code == 200
    assert any(item["id"] == payload["id"] for item in state.json()["capability_requests"])
    assert any(event["event_type"] == "creator.capability_requested" for event in state.json()["audit_stream"])


def test_approved_capability_consumption_safe_mode_tracks_usage_cost_and_audit() -> None:
    created = client.post(
        "/creator/capabilities",
        json={
            "sender": "user",
            "objective": "Need OCR safe consumption",
            "explanation": "FORJA needs OCR capability for safe-mode consumption validation.",
            "requirements": [
                {
                    "kind": "ocr",
                    "characteristics": ["metadata_only", "no_secret_collection"],
                    "reason": "OCR is needed to inspect scanned documents.",
                    "priority": "high",
                }
            ],
        },
    )
    assert created.status_code == 200
    capability = created.json()

    blocked_not_approved = client.post(
        f"/creator/capabilities/{capability['id']}/consume",
        json={"sender": "user", "task": "Run OCR safe-mode validation", "manual_approval": True},
    )
    assert blocked_not_approved.status_code == 200
    assert blocked_not_approved.json()["status"] == "blocked"
    assert blocked_not_approved.json()["failure_reason"] == "capability_not_approved"
    assert blocked_not_approved.json()["external_api_called"] is False

    approved = client.post(f"/creator/capabilities/{capability['id']}/approve", json={"reason": "CEO approved safe-mode OCR."})
    assert approved.status_code == 200
    metadata = client.post(
        f"/creator/capabilities/{capability['id']}/metadata",
        json={"metadata": {"capability_scope": ["ocr"], "constraints": ["safe_mode", "no_direct_api_call"]}},
    )
    assert metadata.status_code == 200

    blocked_missing_manual = client.post(
        f"/creator/capabilities/{capability['id']}/consume",
        json={"sender": "user", "task": "Run OCR without per-use approval", "manual_approval": False},
    )
    assert blocked_missing_manual.status_code == 200
    assert blocked_missing_manual.json()["failure_reason"] == "missing_manual_consumption_approval"

    consumed = client.post(
        f"/creator/capabilities/{capability['id']}/consume",
        json={
            "sender": "user",
            "task": "Run OCR safe-mode validation",
            "manual_approval": True,
            "usage_metadata": {"input_units": 2, "unit_type": "document_pages"},
            "cost_metadata": {"amount": 0.12, "currency": "USD", "units": "2_pages"},
            "provider_response_metadata": {"response_summary": "OCR text metadata was registered externally."},
            "result_metadata": {"result_summary": "controlled_result_metadata_registered"},
        },
    )
    assert consumed.status_code == 200
    payload = consumed.json()
    assert payload["status"] == "completed"
    assert payload["response"] == "capability_consumption_completed_for_ceo"
    assert payload["manual_approval"] is True
    assert payload["external_api_called"] is False
    assert payload["provider_status"] == "provider_response_metadata_registered"
    assert payload["cost_metadata"]["amount"] == 0.12
    assert payload["result_metadata"]["safe_mode"] is True

    execution = client.post(
        f"/creator/capability-consumptions/{payload['id']}/execution",
        json={"metadata": {"execution_result": "safe_mode_record_updated"}},
    )
    assert execution.status_code == 200
    assert execution.json()["result_metadata"]["execution_result"] == "safe_mode_record_updated"

    usage = client.post(
        f"/creator/capability-consumptions/{payload['id']}/usage",
        json={"metadata": {"output_units": 2}},
    )
    assert usage.status_code == 200
    assert usage.json()["usage_metadata"]["output_units"] == 2

    cost = client.post(
        f"/creator/capability-consumptions/{payload['id']}/cost",
        json={"metadata": {"amount": 0.2, "currency": "USD", "units": "2_pages"}},
    )
    assert cost.status_code == 200
    assert cost.json()["cost_metadata"]["amount"] == 0.2

    provider_response = client.post(
        f"/creator/capability-consumptions/{payload['id']}/provider-response",
        json={"metadata": {"response_summary": "safe response metadata updated"}},
    )
    assert provider_response.status_code == 200
    assert provider_response.json()["provider_response_metadata"]["response_summary"] == "safe response metadata updated"

    listed = client.get("/creator/capability-consumptions", params={"capability_request_id": capability["id"]})
    assert listed.status_code == 200
    assert any(item["id"] == payload["id"] for item in listed.json())

    state = client.get("/creator/console")
    assert state.status_code == 200
    assert any(item["id"] == capability["id"] for item in state.json()["approved_capabilities"])
    assert any(item["id"] == payload["id"] for item in state.json()["capability_consumptions"])
    audit_types = [event["event_type"] for event in state.json()["audit_stream"]]
    assert "creator.capability_consumed" in audit_types
    assert "creator.capability_cost_registered" in audit_types


def test_capability_runtime_observability_audit_replay_and_governance() -> None:
    created = client.post(
        "/creator/capabilities",
        json={
            "sender": "cerebro",
            "objective": "Need controlled reasoning observability",
            "explanation": "Cerebro needs a safe approved capability so FORJA can validate runtime observability.",
            "requirements": [
                {
                    "kind": "strong_reasoning",
                    "characteristics": ["observability", "audit_replay"],
                    "reason": "Runtime metrics and audit replay must be visible before any external provider is used.",
                    "priority": "high",
                }
            ],
        },
    )
    assert created.status_code == 200
    capability = created.json()

    approved = client.post(f"/creator/capabilities/{capability['id']}/approve", json={"reason": "Cerebro approved safe-mode observability."})
    assert approved.status_code == 200
    metadata = client.post(
        f"/creator/capabilities/{capability['id']}/metadata",
        json={"metadata": {"capability_scope": ["strong_reasoning"], "constraints": ["safe_mode", "audit_first"]}},
    )
    assert metadata.status_code == 200

    timeout_block = client.post(
        f"/creator/capabilities/{capability['id']}/consume",
        json={
            "sender": "cerebro",
            "task": "Prevent unsafe near-zero timeout",
            "manual_approval": True,
            "timeout_ms": 50,
        },
    )
    assert timeout_block.status_code == 200
    assert timeout_block.json()["status"] == "blocked"
    assert timeout_block.json()["failure_classification"] == "timeout"
    assert timeout_block.json()["governance_escalation"] in {"review_required", "escalated_to_cerebro"}

    consumed = client.post(
        f"/creator/capabilities/{capability['id']}/consume",
        json={
            "sender": "cerebro",
            "task": "Run safe metadata observability",
            "manual_approval": True,
            "timeout_ms": 30000,
            "usage_metadata": {"input_units": 3, "unit_type": "planning_chunks"},
            "cost_metadata": {"amount": 1.25, "currency": "USD", "units": "metadata_only"},
            "provider_response_metadata": {"response_summary": "Operator registered provider response metadata only."},
            "result_metadata": {"result_summary": "runtime_observability_recorded"},
        },
    )
    assert consumed.status_code == 200
    payload = consumed.json()
    assert payload["status"] == "completed"
    assert payload["failure_classification"] == "none"
    assert payload["risk_score"] >= 15
    assert payload["external_api_called"] is False
    assert payload["replay_metadata"]["mode"] == "metadata_only_replay"

    failed_metadata = client.post(
        f"/creator/capability-consumptions/{payload['id']}/provider-response",
        json={"metadata": {"provider": "not_allowed_in_safe_mode"}},
    )
    assert failed_metadata.status_code == 200
    assert failed_metadata.json()["status"] == "failed"
    assert failed_metadata.json()["failure_classification"] == "provider_boundary"

    metrics = client.get("/creator/capability-runtime/metrics")
    assert metrics.status_code == 200
    metrics_payload = metrics.json()
    assert metrics_payload["external_api_calls"] == 0
    assert metrics_payload["cost_by_currency"]["USD"] >= 1.25
    assert metrics_payload["failure_classification_counts"]["timeout"] >= 1

    events = client.get("/creator/capability-runtime/events")
    assert events.status_code == 200
    assert any(event["event_type"] == "capability.consumption_recorded" for event in events.json())
    assert any(event["failure_classification"] in {"timeout", "provider_boundary", "none"} for event in events.json())

    provider_health = client.get("/creator/capability-runtime/provider-health")
    assert provider_health.status_code == 200
    assert provider_health.json()["provider_bound"] is False
    assert provider_health.json()["external_api_calls_enabled"] is False

    replay = client.get(f"/creator/capability-consumptions/{payload['id']}/replay")
    assert replay.status_code == 200
    assert replay.json()["external_api_called"] is False
    assert "provider_switching" in replay.json()["blocked_actions"]

    audit_summary = client.get("/creator/capability-runtime/audit-summary")
    assert audit_summary.status_code == 200
    assert audit_summary.json()["replay_supported"] is True

    state = client.get("/creator/console")
    assert state.status_code == 200
    assert state.json()["capability_runtime_metrics"]["external_api_calls"] == 0
    assert state.json()["provider_health"]["external_provider"] == "not_selected"
