from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


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
