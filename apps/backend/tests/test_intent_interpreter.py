from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.audit import read_audit_events
from app.main import app


client = TestClient(app)


@pytest.mark.parametrize(
    ("input_text", "request_type", "domain", "risk_level"),
    [
        ("creame una app de inventario", "app", "inventario", "MEDIUM"),
        ("creame una API para clientes", "api", "clientes", "MEDIUM"),
        ("creame un dashboard financiero", "dashboard", "financiero", "MEDIUM"),
        ("creame un workflow WhatsApp", "workflow", "WhatsApp", "MEDIUM"),
        ("creame un modulo de autenticacion", "module", "general", "MEDIUM"),
        ("integra ecommerce con webhook", "integration", "ecommerce", "MEDIUM"),
        ("crear documentacion tributaria", "document", "tributario", "LOW"),
        ("repara este backend", "repair", "general", "HIGH"),
        ("mejora este dashboard", "upgrade", "general", "HIGH"),
    ],
)
def test_intent_interpreter_detects_request_domain_and_risk(input_text: str, request_type: str, domain: str, risk_level: str) -> None:
    response = client.post("/intent/interpret", json={"sender": "ceo", "recipient": "forja", "input": input_text})
    assert response.status_code == 200
    payload = response.json()
    assert payload["sender"] == "ceo"
    assert payload["recipient"] == "forja"
    assert payload["request_type"] == request_type
    assert payload["domain"] == domain
    assert payload["risk_level"] == risk_level
    assert payload["requires_approval"] is (risk_level in {"MEDIUM", "HIGH"})
    assert payload["response_target"] == "ceo"
    assert payload["raw_input"] == input_text
    assert payload["normalized_input"] == input_text.lower().replace("api", "api").replace("whatsapp", "whatsapp")
    assert 0.0 <= payload["confidence"] <= 1.0
    assert payload["suggested_modules"]


def test_intent_interpreter_handles_invalid_request_with_low_confidence() -> None:
    response = client.post("/intent/interpret", json={"sender": "ceo", "recipient": "forja", "input": "hola"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["request_type"] == "analysis"
    assert payload["domain"] == "general"
    assert payload["risk_level"] == "LOW"
    assert payload["requires_approval"] is False
    assert payload["confidence"] <= 0.2
    assert payload["suggested_modules"] == ["clarification_questions"]


def test_intent_interpreter_routes_ceo_response_target() -> None:
    response = client.post("/intent/interpret", json={"sender": "ceo", "recipient": "forja", "input": "creame una app de ventas"})
    assert response.status_code == 200
    assert response.json()["response_target"] == "ceo"


def test_intent_interpreter_routes_cerebro_response_target() -> None:
    response = client.post("/intent/interpret", json={"sender": "cerebro", "recipient": "forja", "input": "analiza este proyecto"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["sender"] == "cerebro"
    assert payload["request_type"] == "analysis"
    assert payload["response_target"] == "cerebro"


def test_intent_interpreter_records_audit_events() -> None:
    response = client.post("/intent/interpret", json={"sender": "ceo", "recipient": "forja", "input": "creame un modulo de autenticacion"})
    assert response.status_code == 200
    event_types = [event["event_type"] for event in read_audit_events(50)]
    assert "intent_received" in event_types
    assert "interpreted_request" in event_types
    assert "risk_detected" in event_types
