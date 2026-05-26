from __future__ import annotations

from pathlib import Path
import uuid

from fastapi.testclient import TestClient

from app.core.audit import read_audit_events
from app.core.config import settings
from app.main import app


client = TestClient(app)


def _request_id(prefix: str) -> str:
    return f"gen-{prefix}-{uuid.uuid4().hex[:12]}"


def _workspace_path(request_id: str) -> Path:
    return settings.base_dir / ".forja" / "workspaces" / request_id


def _blueprint(input_text: str, request_id: str) -> dict:
    intent = client.post("/intent/interpret", json={"sender": "ceo", "recipient": "forja", "input": input_text})
    assert intent.status_code == 200
    blueprint = client.post("/blueprint/generate", json={"interpretation": intent.json(), "source_request_id": request_id})
    assert blueprint.status_code == 200
    return blueprint.json()


def _workspace(blueprint: dict) -> dict:
    workspace = client.post("/workspace/create", json={"blueprint": blueprint})
    assert workspace.status_code == 200
    return workspace.json()


def _generate(blueprint: dict, workspace: dict, manual_approval: bool = True):
    return client.post("/generation/files", json={"blueprint": blueprint, "workspace": workspace, "manual_approval": manual_approval})


def test_app_inventario_file_generation() -> None:
    request_id = _request_id("app-inventario")
    blueprint = _blueprint("creame una app de inventario", request_id)
    workspace = _workspace(blueprint)
    response = _generate(blueprint, workspace)
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["approval_status"] == "approved"
    assert "frontend" in payload["modules_created"]
    assert "backend" in payload["modules_created"]
    path = _workspace_path(request_id)
    assert (path / "frontend" / "package.json").is_file()
    assert (path / "frontend" / "src" / "App.tsx").is_file()
    assert (path / "frontend" / "src" / "main.tsx").is_file()
    assert (path / "backend" / "requirements.txt").is_file()
    assert (path / "backend" / "app" / "main.py").is_file()


def test_api_clientes_file_generation() -> None:
    request_id = _request_id("api-clientes")
    blueprint = _blueprint("creame una API para clientes", request_id)
    workspace = _workspace(blueprint)
    response = _generate(blueprint, workspace)
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    path = _workspace_path(request_id)
    assert (path / "backend" / "app" / "routes" / "clientes.py").is_file()
    assert (path / "backend" / "app" / "schemas" / "clientes.py").is_file()
    assert (path / "backend" / "app" / "services" / "clientes_service.py").is_file()
    assert "app.include_router(clientes_router)" in (path / "backend" / "app" / "main.py").read_text(encoding="utf-8")
    assert "FastAPI API" in (path / "backend" / "README.md").read_text(encoding="utf-8")


def test_dashboard_financiero_file_generation() -> None:
    request_id = _request_id("dashboard-financiero")
    blueprint = _blueprint("creame un dashboard financiero", request_id)
    workspace = _workspace(blueprint)
    response = _generate(blueprint, workspace)
    assert response.status_code == 200
    path = _workspace_path(request_id)
    assert (path / "frontend" / "src" / "components" / "KpiCard.tsx").is_file()
    assert (path / "frontend" / "src" / "pages" / "DashboardPage.tsx").is_file()
    assert "React/Vite dashboard" in (path / "frontend" / "README.md").read_text(encoding="utf-8")


def test_module_autenticacion_file_generation() -> None:
    request_id = _request_id("module-auth")
    blueprint = _blueprint("creame un modulo de autenticacion", request_id)
    workspace = _workspace(blueprint)
    response = _generate(blueprint, workspace)
    assert response.status_code == 200
    payload = response.json()
    assert payload["modules_created"] == ["module"]
    path = _workspace_path(request_id)
    assert (path / "module" / "README.md").is_file()
    assert (path / "module" / "interfaces" / "contract.md").is_file()
    assert (path / "module" / "services" / "service.md").is_file()
    assert (path / "module" / "tests" / "test_contract.md").is_file()


def test_duplicate_request_is_blocked() -> None:
    request_id = _request_id("duplicate")
    blueprint = _blueprint("creame una app de inventario", request_id)
    workspace = _workspace(blueprint)
    first = _generate(blueprint, workspace)
    assert first.status_code == 200
    second = _generate(blueprint, workspace)
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate_blocked"
    assert second.json()["reason"] == "duplicate_generation_blocked"


def test_unsafe_generation_blocked() -> None:
    request_id = _request_id("unsafe")
    blueprint = _blueprint("creame una app de inventario", request_id)
    workspace = _workspace(blueprint)
    workspace["request_id"] = "../escape"
    workspace["logical_path"] = ".forja/workspaces/../escape"
    response = _generate(blueprint, workspace)
    assert response.status_code == 400
    assert response.json()["detail"] in {"unsafe_request_id", "path_traversal_blocked", "workspace_escape_blocked"}


def test_approval_flow_for_medium_risk() -> None:
    request_id = _request_id("approval")
    blueprint = _blueprint("creame una app de inventario", request_id)
    workspace = _workspace(blueprint)
    blocked = _generate(blueprint, workspace, manual_approval=False)
    assert blocked.status_code == 200
    assert blocked.json()["status"] == "blocked"
    assert blocked.json()["reason"] == "manual_approval_required"
    assert not (_workspace_path(request_id) / "frontend" / "package.json").exists()
    approved = _generate(blueprint, workspace, manual_approval=True)
    assert approved.status_code == 200
    assert approved.json()["status"] == "completed"


def test_high_risk_generation_is_blocked() -> None:
    request_id = _request_id("high")
    blueprint = _blueprint("creame un modulo de autenticacion", request_id)
    blueprint["risk_level"] = "HIGH"
    blueprint["approval_required"] = True
    workspace = _workspace(blueprint)
    response = _generate(blueprint, workspace, manual_approval=True)
    assert response.status_code == 200
    assert response.json()["status"] == "blocked"
    assert response.json()["reason"] == "high_risk_authorization_required"


def test_audit_is_recorded() -> None:
    request_id = _request_id("audit")
    blueprint = _blueprint("creame una app de inventario", request_id)
    workspace = _workspace(blueprint)
    generated = _generate(blueprint, workspace)
    assert generated.status_code == 200
    duplicate = _generate(blueprint, workspace)
    assert duplicate.status_code == 200
    event_types = [event["event_type"] for event in read_audit_events(160)]
    assert "generation_started" in event_types
    assert "files_generated" in event_types
    assert "generation_completed" in event_types
    assert "duplicate_generation_blocked" in event_types


def test_timeline_is_recorded() -> None:
    request_id = _request_id("timeline")
    blueprint = _blueprint("creame una app de inventario", request_id)
    workspace = _workspace(blueprint)
    response = _generate(blueprint, workspace)
    assert response.status_code == 200
    events = [item["event"] for item in response.json()["timeline"]]
    assert "generation.started" in events
    assert "generation.files_written" in events
    assert "generation.completed" in events


def test_readme_generated() -> None:
    request_id = _request_id("readme")
    blueprint = _blueprint("creame una app de inventario", request_id)
    workspace = _workspace(blueprint)
    response = _generate(blueprint, workspace)
    assert response.status_code == 200
    readme = (_workspace_path(request_id) / "frontend" / "README.md").read_text(encoding="utf-8")
    assert "Nombre:" in readme
    assert "Objetivo:" in readme
    assert "Stack:" in readme
    assert "Instrucciones:" in readme
    assert "Riesgos:" in readme
    assert "Sender:" in readme
    assert "Timestamp:" in readme


def test_structure_generated() -> None:
    request_id = _request_id("structure")
    blueprint = _blueprint("creame una API para clientes", request_id)
    workspace = _workspace(blueprint)
    response = _generate(blueprint, workspace)
    assert response.status_code == 200
    generated_directories = response.json()["generated_directories"]
    assert "backend/app/routes" in generated_directories
    assert "backend/app/schemas" in generated_directories
    assert "backend/app/services" in generated_directories
