from __future__ import annotations

from pathlib import Path
import uuid

from fastapi.testclient import TestClient

from app.core.audit import read_audit_events
from app.core.config import settings
from app.main import app


client = TestClient(app)


def _request_id(prefix: str) -> str:
    return f"console-{prefix}-{uuid.uuid4().hex[:12]}"


def _workspace_path(request_id: str) -> Path:
    return settings.base_dir / ".forja" / "workspaces" / request_id


def _start(input_text: str, request_id: str):
    return client.post(
        "/execution/start",
        json={"sender": "ceo", "recipient": "forja", "input": input_text, "source_request_id": request_id},
    )


def _approve(execution_id: str):
    return client.post(f"/execution/{execution_id}/approval", json={"decision": "approve", "decided_by": "ceo"})


def _run_medium_flow(input_text: str, request_id: str) -> dict:
    pending = _start(input_text, request_id)
    assert pending.status_code == 200
    assert pending.json()["state"] == "awaiting_approval"
    approved = _approve(pending.json()["execution_id"])
    assert approved.status_code == 200
    return approved.json()


def test_human_console_app_inventario_end_to_end() -> None:
    request_id = _request_id("app-inventario")
    payload = _run_medium_flow("creame una app de inventario", request_id)
    assert payload["state"] == "completed"
    assert payload["interpretation"]["request_type"] == "app"
    assert payload["interpretation"]["domain"] == "inventario"
    assert payload["blueprint"]["project_type"] == "app"
    assert payload["workspace"]["logical_path"] == f".forja/workspaces/{request_id}"
    assert payload["generation"]["status"] == "completed"
    assert any(path.endswith("frontend/src/App.tsx") for path in payload["generation"]["generated_files"])
    assert (_workspace_path(request_id) / "frontend" / "src" / "App.tsx").is_file()


def test_human_console_api_clientes_end_to_end() -> None:
    request_id = _request_id("api-clientes")
    payload = _run_medium_flow("creame una API para clientes", request_id)
    assert payload["interpretation"]["request_type"] == "api"
    assert payload["interpretation"]["domain"] == "clientes"
    assert any(path.endswith("backend/app/routes/clientes.py") for path in payload["generation"]["generated_files"])
    assert (_workspace_path(request_id) / "backend" / "app" / "services" / "clientes_service.py").is_file()


def test_human_console_dashboard_financiero_end_to_end() -> None:
    request_id = _request_id("dashboard-financiero")
    payload = _run_medium_flow("creame un dashboard financiero", request_id)
    assert payload["interpretation"]["request_type"] == "dashboard"
    assert payload["interpretation"]["domain"] == "financiero"
    assert any(path.endswith("frontend/src/pages/DashboardPage.tsx") for path in payload["generation"]["generated_files"])
    assert (_workspace_path(request_id) / "frontend" / "src" / "components" / "KpiCard.tsx").is_file()


def test_human_console_rejection_flow_blocks_before_workspace() -> None:
    request_id = _request_id("reject")
    pending = _start("creame una app de inventario", request_id)
    assert pending.status_code == 200
    rejected = client.post(f"/execution/{pending.json()['execution_id']}/approval", json={"decision": "reject", "decided_by": "ceo"})
    assert rejected.status_code == 200
    payload = rejected.json()
    assert payload["state"] == "blocked"
    assert payload["reason"] == "approval_rejected"
    assert payload["workspace"] is None
    assert not _workspace_path(request_id).exists()


def test_human_console_duplicate_request_is_blocked() -> None:
    request_id = _request_id("duplicate")
    completed = _run_medium_flow("creame una app de inventario", request_id)
    duplicate = _start("creame una app de inventario", request_id)
    assert duplicate.status_code == 200
    payload = duplicate.json()
    assert payload["state"] == "duplicate_blocked"
    assert payload["reason"] == "duplicate_execution_blocked"
    assert payload["duplicate_of"] == completed["execution_id"]


def test_human_console_blocked_high_risk_request() -> None:
    request_id = _request_id("blocked")
    response = _start("repara este backend", request_id)
    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "blocked"
    assert payload["risk_level"] == "HIGH"
    assert payload["reason"] == "high_risk_authorization_required"
    assert payload["workspace"] is None


def test_human_console_invalid_request_is_controlled() -> None:
    request_id = _request_id("invalid")
    response = _start("hola", request_id)
    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "blocked"
    assert payload["reason"] == "validation_failed"
    assert payload["interpretation"]["confidence"] <= 0.2
    assert payload["workspace"] is None
    assert "validation.failed" in [event["event"] for event in payload["timeline"]]


def test_human_console_timeline_outputs_and_audit_are_visible() -> None:
    request_id = _request_id("visibility")
    payload = _run_medium_flow("creame una app de inventario", request_id)
    timeline = [event["event"] for event in payload["timeline"]]
    assert "intent.received" in timeline
    assert "intent.interpreted" in timeline
    assert "blueprint.generated" in timeline
    assert "approval.requested" in timeline
    assert "approval.granted" in timeline
    assert "workspace.created" in timeline
    assert "files.generated" in timeline
    assert "execution.completed" in timeline
    output_kinds = {output["kind"] for output in payload["outputs"]}
    assert {"readme", "blueprint", "architecture", "execution_report", "generated_file", "module"}.issubset(output_kinds)
    audit_types = {event["event_type"] for event in payload["audit_events"]}
    assert {"execution_started", "approval_requested", "approval_granted", "generation_started", "generation_completed"}.issubset(audit_types)
    global_audit = [event["event_type"] for event in read_audit_events(300)]
    assert "execution_completed" in global_audit
