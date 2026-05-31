from __future__ import annotations

from pathlib import Path
import uuid

from fastapi.testclient import TestClient

from app.core.audit import read_audit_events
from app.core.config import settings
from app.main import app
from app.services.execution_service import governed_execution_manager


client = TestClient(app)


def _request_id(prefix: str) -> str:
    return f"exec-{prefix}-{uuid.uuid4().hex[:12]}"


def _workspace_path(request_id: str) -> Path:
    return settings.base_dir / ".forja" / "workspaces" / request_id


def _start(input_text: str, request_id: str, sender: str = "ceo"):
    return client.post(
        "/execution/start",
        json={"sender": sender, "recipient": "forja", "input": input_text, "source_request_id": request_id},
    )


def _approve(execution_id: str):
    return client.post(f"/execution/{execution_id}/approval", json={"decision": "approve", "decided_by": "ceo"})


def _reject(execution_id: str):
    return client.post(f"/execution/{execution_id}/approval", json={"decision": "reject", "decided_by": "ceo"})


def test_low_risk_auto_execution() -> None:
    request_id = _request_id("low-docs")
    response = _start("crear documentacion tributaria", request_id)
    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "completed"
    assert payload["risk_level"] == "LOW"
    assert payload["approval_status"] == "not_required"
    assert payload["workspace"]["logical_path"] == f".forja/workspaces/{request_id}"
    assert any(output["kind"] == "readme" for output in payload["outputs"])
    assert (_workspace_path(request_id) / "README.md").is_file()


def test_medium_risk_requires_approval() -> None:
    request_id = _request_id("medium-app")
    response = _start("creame una app de inventario", request_id)
    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "awaiting_approval"
    assert payload["risk_level"] == "MEDIUM"
    assert payload["approval_status"] == "requested"
    assert payload["workspace"] is None
    assert not _workspace_path(request_id).exists()


def test_high_risk_is_blocked() -> None:
    request_id = _request_id("high-repair")
    response = _start("repara este backend", request_id)
    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "blocked"
    assert payload["risk_level"] == "HIGH"
    assert payload["approval_status"] == "blocked"
    assert payload["reason"] == "high_risk_authorization_required"


def test_duplicate_request_is_blocked_after_completion() -> None:
    request_id = _request_id("duplicate")
    first = _start("crear documentacion tributaria", request_id)
    assert first.status_code == 200
    assert first.json()["state"] == "completed"
    second = _start("crear documentacion tributaria", request_id)
    assert second.status_code == 200
    assert second.json()["state"] == "duplicate_blocked"
    assert second.json()["reason"] == "duplicate_execution_blocked"
    assert second.json()["duplicate_of"] == first.json()["execution_id"]


def test_parallel_request_is_blocked() -> None:
    request_id = _request_id("parallel")
    response = _start("creame una app de inventario", request_id)
    assert response.status_code == 200
    active = response.json()
    active["state"] = "generating"
    governed_execution_manager._save_record(active)
    duplicate = _start("creame una app de inventario", request_id)
    assert duplicate.status_code == 200
    assert duplicate.json()["state"] == "duplicate_blocked"
    assert duplicate.json()["reason"] == "parallel_execution_blocked"
    assert duplicate.json()["parallel_execution_blocked"] is True


def test_approval_granted_completes_generation() -> None:
    request_id = _request_id("approval-granted")
    pending = _start("creame una API para clientes", request_id)
    assert pending.status_code == 200
    approved = _approve(pending.json()["execution_id"])
    assert approved.status_code == 200
    payload = approved.json()
    assert payload["state"] == "completed"
    assert payload["approval_status"] == "approved"
    assert payload["workspace"]["status"] == "created"
    assert payload["generation"]["status"] == "completed"
    assert any(path.endswith("backend/app/main.py") for path in payload["generation"]["generated_files"])


def test_approval_rejected_blocks_execution() -> None:
    request_id = _request_id("approval-rejected")
    pending = _start("creame una app de inventario", request_id)
    assert pending.status_code == 200
    rejected = _reject(pending.json()["execution_id"])
    assert rejected.status_code == 200
    payload = rejected.json()
    assert payload["state"] == "blocked"
    assert payload["approval_status"] == "rejected"
    assert payload["reason"] == "approval_rejected"
    assert payload["workspace"] is None


def test_timeline_is_visible_and_ordered() -> None:
    request_id = _request_id("timeline")
    pending = _start("creame un dashboard financiero", request_id)
    approved = _approve(pending.json()["execution_id"])
    events = [item["event"] for item in approved.json()["timeline"]]
    assert "intent.received" in events
    assert "blueprint.generated" in events
    assert "approval.requested" in events
    assert "approval.granted" in events
    assert "workspace.created" in events
    assert "files.generated" in events
    assert "execution.completed" in events


def test_audit_is_recorded() -> None:
    request_id = _request_id("audit")
    pending = _start("creame una app de inventario", request_id)
    approved = _approve(pending.json()["execution_id"])
    assert approved.status_code == 200
    event_types = [event["event_type"] for event in read_audit_events(260)]
    assert "execution_started" in event_types
    assert "approval_requested" in event_types
    assert "approval_granted" in event_types
    assert "generation_started" in event_types
    assert "generation_completed" in event_types


def test_outputs_are_visible() -> None:
    request_id = _request_id("outputs")
    pending = _start("creame una app de inventario", request_id)
    approved = _approve(pending.json()["execution_id"])
    outputs = approved.json()["outputs"]
    kinds = {output["kind"] for output in outputs}
    assert {"readme", "blueprint", "architecture", "execution_report", "generated_file", "module"}.issubset(kinds)
    assert any(output["logical_path"].startswith(".forja/workspaces/") for output in outputs)


def test_failed_execution_is_recorded() -> None:
    request_id = f"../unsafe-{uuid.uuid4().hex[:8]}"
    response = _start("crear documentacion tributaria", request_id)
    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "failed"
    assert payload["reason"] in {"unsafe_request_id", "path_traversal_blocked"}
    event_types = [event["event_type"] for event in read_audit_events(80)]
    assert "execution_failed" in event_types


def test_recovery_state_can_be_read() -> None:
    request_id = f"../recover-{uuid.uuid4().hex[:8]}"
    failed = _start("crear documentacion tributaria", request_id)
    assert failed.status_code == 200
    execution_id = failed.json()["execution_id"]
    recovered = client.get(f"/execution/{execution_id}")
    assert recovered.status_code == 200
    assert recovered.json()["state"] == "failed"
    assert recovered.json()["execution_id"] == execution_id
