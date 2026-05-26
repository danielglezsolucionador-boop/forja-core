from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import uuid

from fastapi.testclient import TestClient

from app.core.audit import read_audit_events
from app.core.config import settings
from app.main import app
from app.services.execution_service import governed_execution_manager


client = TestClient(app)


def _request_id(prefix: str) -> str:
    return f"stable-{prefix}-{uuid.uuid4().hex[:12]}"


def _workspace_path(request_id: str) -> Path:
    return settings.base_dir / ".forja" / "workspaces" / request_id


def _start(input_text: str, request_id: str, sender: str = "ceo") -> dict:
    response = client.post(
        "/execution/start",
        json={"sender": sender, "recipient": "forja", "input": input_text, "source_request_id": request_id},
    )
    assert response.status_code == 200
    return response.json()


def _approve(execution_id: str, high_risk_authorization: bool = False) -> dict:
    response = client.post(
        f"/execution/{execution_id}/approval",
        json={"decision": "approve", "decided_by": "ceo", "high_risk_authorization": high_risk_authorization},
    )
    assert response.status_code == 200
    return response.json()


def _run_medium_flow(input_text: str, request_id: str, sender: str = "ceo") -> dict:
    pending = _start(input_text, request_id, sender=sender)
    assert pending["state"] == "awaiting_approval"
    return _approve(pending["execution_id"])


def _workspace_inventory(request_id: str) -> list[str]:
    root = _workspace_path(request_id)
    return sorted(str(path.relative_to(root)).replace("\\", "/") for path in root.rglob("*") if path.is_file())


def test_module_autenticacion_e2e_generates_module_files_and_outputs() -> None:
    request_id = _request_id("module-auth")
    payload = _run_medium_flow("creame un modulo de autenticacion", request_id)

    assert payload["state"] == "completed"
    assert payload["request_type"] == "module"
    assert payload["blueprint"]["project_type"] == "module"
    assert payload["generation"]["modules_created"] == ["module"]
    assert any(path.endswith("module/interfaces/contract.md") for path in payload["generation"]["generated_files"])
    assert any(path.endswith("module/services/service.md") for path in payload["generation"]["generated_files"])
    assert (_workspace_path(request_id) / "module" / "tests" / "test_contract.md").is_file()
    assert any(output["kind"] == "generated_file" for output in payload["outputs"])


def test_workflow_whatsapp_creates_controlled_workspace_without_complex_generation() -> None:
    request_id = _request_id("workflow-wa")
    payload = _run_medium_flow("creame un workflow WhatsApp", request_id)

    assert payload["state"] == "completed"
    assert payload["request_type"] == "workflow"
    assert payload["domain"] == "WhatsApp"
    assert payload["risk_level"] == "MEDIUM"
    assert payload["generation"] is None
    assert payload["workspace"]["logical_path"] == f".forja/workspaces/{request_id}"
    assert {output["label"] for output in payload["outputs"]} == {
        "workspace",
        "README.md",
        "blueprint.json",
        "architecture.md",
        "execution_report.md",
    }
    assert (_workspace_path(request_id) / "blueprint.json").is_file()


def test_idempotency_keeps_outputs_and_files_single_copy_after_completed_request() -> None:
    request_id = _request_id("idem")
    completed = _run_medium_flow("creame una app de inventario", request_id)
    files_before = _workspace_inventory(request_id)

    duplicate = _start("creame una app de inventario", request_id)
    files_after = _workspace_inventory(request_id)

    assert duplicate["state"] == "duplicate_blocked"
    assert duplicate["reason"] == "duplicate_execution_blocked"
    assert duplicate["duplicate_of"] == completed["execution_id"]
    assert duplicate["outputs"] == completed["outputs"]
    assert files_after == files_before
    assert len(files_after) == len(set(files_after))
    assert "audit/file_generation_record.json" in files_after
    assert "audit/governed_execution_record.json" in files_after


def test_second_approval_after_completion_is_duplicate_blocked() -> None:
    request_id = _request_id("approval-twice")
    pending = _start("creame una API para clientes", request_id)
    completed = _approve(pending["execution_id"])
    second = _approve(pending["execution_id"])

    assert completed["state"] == "completed"
    assert second["state"] == "duplicate_blocked"
    assert second["reason"] == "duplicate_execution_blocked"
    assert second["duplicate_of"] == completed["execution_id"]


def test_parallel_active_request_lock_blocks_start_without_workspace_write() -> None:
    request_id = _request_id("active-lock")
    assert governed_execution_manager._try_lock_request(request_id) is True
    try:
        duplicate = _start("creame una app de inventario", request_id)
    finally:
        governed_execution_manager._unlock_request(request_id)

    assert duplicate["state"] == "duplicate_blocked"
    assert duplicate["reason"] == "parallel_execution_blocked"
    assert duplicate["parallel_execution_blocked"] is True
    assert not _workspace_path(request_id).exists()


def test_outputs_are_logical_paths_and_workspace_stays_isolated() -> None:
    request_id = _request_id("isolation")
    payload = _run_medium_flow("creame un dashboard financiero", request_id)
    workspace_root = (settings.base_dir / ".forja" / "workspaces").resolve()
    physical_workspace = _workspace_path(request_id).resolve()

    assert physical_workspace.is_dir()
    assert physical_workspace.relative_to(workspace_root)
    for output in payload["outputs"]:
        logical_path = output["logical_path"]
        assert logical_path.startswith(f".forja/workspaces/{request_id}")
        assert "C:" not in logical_path
        assert "\\" not in logical_path
        assert ".." not in Path(logical_path).parts


def test_unsafe_request_and_high_risk_bypass_are_blocked() -> None:
    unsafe = _start("crear documentacion tributaria", f"../escape-{uuid.uuid4().hex[:8]}")
    assert unsafe["state"] == "failed"
    assert unsafe["reason"] in {"unsafe_request_id", "path_traversal_blocked"}
    assert unsafe["workspace"] is None

    high_risk = _start("repara este backend", _request_id("repair"))
    assert high_risk["state"] == "blocked"
    assert high_risk["reason"] == "high_risk_authorization_required"
    assert high_risk["workspace"] is None

    bypass = _approve(high_risk["execution_id"])
    assert bypass["state"] == "blocked"
    assert bypass["reason"] == "high_risk_authorization_required"
    assert bypass["workspace"] is None


def test_recovery_execution_after_controlled_failure_with_new_safe_request() -> None:
    failed = _start("crear documentacion tributaria", f"../recover-{uuid.uuid4().hex[:8]}")
    recovered = _start("crear documentacion tributaria", _request_id("recovered-doc"))

    assert failed["state"] == "failed"
    assert "execution.failed" in [event["event"] for event in failed["timeline"]]
    assert recovered["state"] == "completed"
    assert recovered["risk_level"] == "LOW"
    assert recovered["workspace"]["status"] == "created"


def test_stress_multiple_requests_repeats_audit_and_timeline_consistency() -> None:
    cases = [
        ("app", "creame una app de inventario", True),
        ("api", "creame una API para clientes", True),
        ("dashboard", "creame un dashboard financiero", True),
        ("module", "creame un modulo de autenticacion", True),
        ("workflow", "creame un workflow WhatsApp", False),
    ]
    completed: list[dict] = []

    for prefix, command, generates_files in cases:
        request_id = _request_id(f"stress-{prefix}")
        payload = _run_medium_flow(command, request_id)
        completed.append(payload)
        duplicate = _start(command, request_id)

        assert payload["state"] == "completed"
        assert payload["workspace"]["logical_path"] == f".forja/workspaces/{request_id}"
        assert duplicate["state"] == "duplicate_blocked"
        assert duplicate["reason"] == "duplicate_execution_blocked"
        assert bool(payload["generation"]) is generates_files
        events = [event["event"] for event in payload["timeline"]]
        assert events.index("intent.received") < events.index("blueprint.generated") < events.index("workspace.created") < events.index("execution.completed")
        assert len(payload["outputs"]) == len({output["logical_path"] for output in payload["outputs"]})

    audit_types = [event["event_type"] for event in read_audit_events(600)]
    assert audit_types.count("approval_granted") >= len(cases)
    assert audit_types.count("duplicate_execution_blocked") >= len(cases)
    assert audit_types.count("execution_completed") >= len(cases)
    assert all(record["workspace_isolated"] is True for record in completed)


def test_concurrent_approval_stress_allows_single_completion() -> None:
    request_id = _request_id("simul-approval")
    pending = _start("creame un dashboard financiero", request_id)

    def approve_once() -> dict:
        local_client = TestClient(app)
        response = local_client.post(f"/execution/{pending['execution_id']}/approval", json={"decision": "approve", "decided_by": "ceo"})
        assert response.status_code == 200
        return response.json()

    with ThreadPoolExecutor(max_workers=2) as executor:
        approvals = list(executor.map(lambda _: approve_once(), range(2)))

    states = [payload["state"] for payload in approvals]
    assert states.count("completed") == 1
    assert states.count("duplicate_blocked") == 1
    assert any(payload["reason"] in {"parallel_execution_blocked", "duplicate_execution_blocked"} for payload in approvals if payload["state"] == "duplicate_blocked")
    assert (_workspace_path(request_id) / "audit" / "governed_execution_record.json").is_file()
