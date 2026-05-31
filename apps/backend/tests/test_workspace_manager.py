from __future__ import annotations

from pathlib import Path
import uuid

from fastapi.testclient import TestClient

from app.core.audit import read_audit_events
from app.core.config import settings
from app.main import app


client = TestClient(app)


def _blueprint(input_text: str, source_request_id: str | None = None) -> dict:
    intent = client.post("/intent/interpret", json={"sender": "ceo", "recipient": "forja", "input": input_text})
    assert intent.status_code == 200
    blueprint = client.post("/blueprint/generate", json={"interpretation": intent.json()})
    assert blueprint.status_code == 200
    payload = blueprint.json()
    if source_request_id is not None:
        payload["source_request_id"] = source_request_id
    return payload


def _create_workspace(blueprint: dict):
    return client.post("/workspace/create", json={"blueprint": blueprint})


def _request_id(prefix: str) -> str:
    return f"test-{prefix}-{uuid.uuid4().hex[:12]}"


def _workspace_path(request_id: str) -> Path:
    return settings.base_dir / ".forja" / "workspaces" / request_id


def test_app_inventario_workspace() -> None:
    request_id = _request_id("app-inventario")
    response = _create_workspace(_blueprint("creame una app de inventario", request_id))
    assert response.status_code == 200
    payload = response.json()
    assert payload["request_id"] == request_id
    assert payload["project_type"] == "app"
    assert payload["domain"] == "inventario"
    assert payload["logical_path"] == f".forja/workspaces/{request_id}"
    assert payload["workspace_isolated"] is True
    assert payload["complex_generation_allowed"] is False
    path = _workspace_path(request_id)
    assert path.exists()
    for directory in ["frontend", "backend", "docs", "tests", "outputs", "audit"]:
        assert (path / directory).is_dir()
    for filename in ["README.md", "blueprint.json", "architecture.md", "execution_report.md"]:
        assert (path / filename).is_file()
    assert "Inventario App Blueprint" in (path / "README.md").read_text(encoding="utf-8")


def test_api_clientes_workspace() -> None:
    request_id = _request_id("api-clientes")
    response = _create_workspace(_blueprint("creame una API para clientes", request_id))
    assert response.status_code == 200
    payload = response.json()
    assert payload["project_type"] == "api"
    assert payload["domain"] == "clientes"
    architecture = (_workspace_path(request_id) / "architecture.md").read_text(encoding="utf-8")
    assert "FastAPI" in architecture
    assert "`POST /clientes`" in architecture


def test_dashboard_financiero_workspace() -> None:
    request_id = _request_id("dashboard-financiero")
    response = _create_workspace(_blueprint("creame un dashboard financiero", request_id))
    assert response.status_code == 200
    payload = response.json()
    assert payload["project_type"] == "dashboard"
    assert payload["domain"] == "financiero"
    blueprint = (_workspace_path(request_id) / "blueprint.json").read_text(encoding="utf-8")
    assert "financial_metrics" in blueprint


def test_duplicate_workspace_request_is_blocked() -> None:
    request_id = _request_id("duplicate")
    blueprint = _blueprint("creame una app de inventario", request_id)
    first = _create_workspace(blueprint)
    assert first.status_code == 200
    second = _create_workspace(blueprint)
    assert second.status_code == 409
    assert second.json()["detail"] == "workspace_already_exists"


def test_unsafe_path_is_blocked() -> None:
    blueprint = _blueprint("creame una app de inventario", "../escape")
    response = _create_workspace(blueprint)
    assert response.status_code == 400
    assert response.json()["detail"] in {"unsafe_request_id", "path_traversal_blocked", "workspace_escape_blocked"}


def test_overwrite_is_blocked() -> None:
    request_id = _request_id("overwrite")
    root = settings.base_dir / ".forja" / "workspaces"
    root.mkdir(parents=True, exist_ok=True)
    (_workspace_path(request_id)).write_text("occupied", encoding="utf-8")
    response = _create_workspace(_blueprint("creame una API para clientes", request_id))
    assert response.status_code == 409
    assert response.json()["detail"] == "workspace_already_exists"


def test_approval_flow_medium_risk() -> None:
    request_id = _request_id("approval")
    response = _create_workspace(_blueprint("creame una app de inventario", request_id))
    assert response.status_code == 200
    payload = response.json()
    assert payload["risk_level"] == "MEDIUM"
    assert payload["approval_required"] is True
    assert payload["approval_status"] == "pending"
    assert payload["complex_generation_allowed"] is False


def test_audit_is_recorded() -> None:
    request_id = _request_id("audit")
    response = _create_workspace(_blueprint("creame una app de inventario", request_id))
    assert response.status_code == 200
    event_types = [event["event_type"] for event in read_audit_events(120)]
    assert "workspace_creation_requested" in event_types
    assert "workspace_created" in event_types
    duplicate = _create_workspace(_blueprint("creame una app de inventario", request_id))
    assert duplicate.status_code == 409
    event_types = [event["event_type"] for event in read_audit_events(120)]
    assert "workspace_blocked" in event_types


def test_timeline_is_recorded() -> None:
    request_id = _request_id("timeline")
    response = _create_workspace(_blueprint("creame una app de inventario", request_id))
    assert response.status_code == 200
    events = [item["event"] for item in response.json()["timeline"]]
    assert "workspace.creation_requested" in events
    assert "workspace.path_validated" in events
    assert "workspace.structure_created" in events
    assert "workspace.base_files_created" in events
    report = (_workspace_path(request_id) / "execution_report.md").read_text(encoding="utf-8")
    assert "workspace.base_files_created" in report
