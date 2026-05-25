from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.audit import read_audit_events
from app.main import app


client = TestClient(app)


def _interpret(input_text: str, sender: str = "ceo") -> dict:
    response = client.post("/intent/interpret", json={"sender": sender, "recipient": "forja", "input": input_text})
    assert response.status_code == 200
    return response.json()


def _blueprint(input_text: str, sender: str = "ceo") -> dict:
    interpretation = _interpret(input_text, sender)
    response = client.post("/blueprint/generate", json={"interpretation": interpretation})
    assert response.status_code == 200
    return response.json()


def test_blueprint_app_inventario() -> None:
    payload = _blueprint("creame una app de inventario")
    assert payload["project_type"] == "app"
    assert payload["domain"] == "inventario"
    assert "frontend React/Vite" in payload["stack_recommendation"]
    assert "backend FastAPI" in payload["stack_recommendation"]
    assert "inventory_items" in payload["modules"]
    assert any(endpoint["path"] == "/inventario/summary" for endpoint in payload["endpoints"])
    assert any(entity["name"] == "InventoryItem" for entity in payload["data_model"])


def test_blueprint_api_clientes() -> None:
    payload = _blueprint("creame una API para clientes")
    assert payload["project_type"] == "api"
    assert payload["domain"] == "clientes"
    assert payload["stack_recommendation"] == ["FastAPI", "schemas", "routes", "service layer"]
    assert "customer_records" in payload["modules"]
    assert any(endpoint["method"] == "POST" and endpoint["path"] == "/clientes" for endpoint in payload["endpoints"])
    assert any(entity["name"] == "Customer" for entity in payload["data_model"])


def test_blueprint_dashboard_financiero() -> None:
    payload = _blueprint("creame un dashboard financiero")
    assert payload["project_type"] == "dashboard"
    assert payload["domain"] == "financiero"
    assert "cards" in payload["stack_recommendation"]
    assert "analytics" in payload["stack_recommendation"]
    assert any(screen == "Financiero overview" for screen in payload["screens"])
    assert "financial_metrics" in payload["modules"]


def test_blueprint_workflow_whatsapp() -> None:
    payload = _blueprint("creame un workflow WhatsApp")
    assert payload["project_type"] == "workflow"
    assert payload["domain"] == "WhatsApp"
    assert payload["stack_recommendation"] == ["steps", "triggers", "validations"]
    assert "whatsapp_adapter" in payload["modules"]
    assert any(endpoint["path"] == "/workflows/whatsapp/trigger" for endpoint in payload["endpoints"])


def test_blueprint_repair_backend() -> None:
    payload = _blueprint("repara este backend")
    assert payload["project_type"] == "repair"
    assert payload["project_name"] == "Backend Repair Blueprint"
    assert payload["risk_level"] == "HIGH"
    assert payload["approval_required"] is True
    assert "inspection plan" in payload["stack_recommendation"]
    assert "Inspeccionar proyecto existente sin modificar archivos." in payload["construction_steps"]
    assert any(risk["title"] == "Existing project modification risk" for risk in payload["risks"])


def test_blueprint_response_target_ceo() -> None:
    payload = _blueprint("creame una app de ventas", sender="ceo")
    assert payload["sender"] == "ceo"
    assert payload["response_target"] == "ceo"


def test_blueprint_response_target_cerebro() -> None:
    payload = _blueprint("creame una API para clientes", sender="cerebro")
    assert payload["sender"] == "cerebro"
    assert payload["response_target"] == "cerebro"


def test_blueprint_inherits_risk_level_and_audits() -> None:
    payload = _blueprint("mejora este dashboard")
    assert payload["risk_level"] == "HIGH"
    assert any(risk["level"] == "HIGH" for risk in payload["risks"])
    event_types = [event["event_type"] for event in read_audit_events(80)]
    assert "blueprint_generated" in event_types
    assert "blueprint_ready_for_approval" in event_types
