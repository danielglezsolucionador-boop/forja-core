from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json

from fastapi.testclient import TestClient

from app.core.audit import read_audit_events
from app.core.config import settings
from app.main import app
from app.services.creator_service import creator_service


client = TestClient(app)


class FakeCreatorChatEngine:
    def __init__(self, text: str = "Hola, soy FORJA. Estoy operativo y listo para conversar.") -> None:
        self.text = text
        self.payloads: list[dict] = []

    def execute(self, payload: dict) -> dict:
        self.payloads.append(payload)
        return {
            "execution_id": "real-ai-test-chat",
            "provider_used": "openrouter",
            "model_used": "openrouter-test-model",
            "execution_state": "completed",
            "response_received": True,
            "generated_text": self.text,
            "generated_text_preview": self.text,
            "outputs": [{"logical_path": ".forja/workspaces/test/outputs/chat.generated.md"}],
            "fallback_triggered": False,
            "safe_mode": True,
            "timeline": [{"timestamp": "2026-01-01T00:00:00+00:00", "event": "response.received", "detail": "Response received from openrouter."}],
            "external_request_executed": True,
        }


class QueuedFakeCreatorChatEngine(FakeCreatorChatEngine):
    def __init__(self, texts: list[str]) -> None:
        super().__init__(texts[-1] if texts else "")
        self.texts = texts
        self.index = 0

    def execute(self, payload: dict) -> dict:
        text = self.texts[min(self.index, len(self.texts) - 1)]
        self.index += 1
        self.text = text
        return super().execute(payload)


class FakeEcosystemMemory:
    def snapshot(self) -> dict:
        return {
            "connected": True,
            "primary_source": {"path": "docs/ecosystem-memory/core/FORJA_PHASE2_DECISION_TRACE.md"},
            "additional_sources": [{"path": "docs/ecosystem-memory/core/LONGITUDINAL_ECOSYSTEM_MEMORY.md", "exists": True}],
            "registered_apps": ["CEREBRO", "CENTINELA", "PLUMA"],
            "apps_in_primary_memory": ["CEREBRO", "CENTINELA"],
            "apps_missing_from_primary_memory": ["PLUMA"],
            "active_apps": ["CEREBRO", "CENTINELA", "PLUMA"],
            "priorities": ["Cerebro decision trace baseline"],
            "blockers": ["Cerebro lacked governance enforcement before provider execution"],
            "construction": ["Cerebro now has governance wrapper"],
        }

    def prompt_context(self, snapshot: dict | None = None) -> str:
        return (
            r"Fuentes conectadas: FORJA_PHASE2_DECISION_TRACE.md; "
            "Apps registradas en docs/ecosystem-memory/apps: CEREBRO, CENTINELA, PLUMA; "
            "Apps existentes que faltan en memoria maestra: PLUMA"
        )


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
    snapshot = payload["snapshot"]
    metric_labels = {metric["label"] for metric in snapshot["metrics"]}
    assert "Apps en construccion" in metric_labels
    assert "Tareas activas" in metric_labels
    assert "Bloqueos" in metric_labels
    assert "Aprobaciones pendientes" in metric_labels
    assert "Entregas listas" in metric_labels
    assert snapshot["memory"]["connected"] is True
    assert snapshot["memory"]["primary_source"] == "docs/ecosystem-memory/core/FORJA_PHASE2_DECISION_TRACE.md"
    assert snapshot["constructionQueue"]
    assert snapshot["deliveries"]
    assert snapshot["flow"]
    assert snapshot["activity"]


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


def test_creator_console_uses_openrouter_real_chat(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-creator-console-real-chat-test")
    fake_engine = FakeCreatorChatEngine()
    monkeypatch.setattr(creator_service, "_real_execution_engine", fake_engine)

    response = client.post(
        "/creator/commands",
        json={"sender": "cerebro", "command": "Build a controlled operator module", "details": "Use external AI provider."},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["sender"] == "cerebro"
    assert payload["reply_to_sender"] == "cerebro"
    assert payload["status"] == "completed"
    assert payload["response"] == "Hola, soy FORJA. Estoy operativo y listo para conversar."
    assert payload["governance"]["provider_status"] == "active"
    assert payload["governance"]["approval_status"] == "not_required"
    assert payload["outputs"][0]["summary"].startswith("real_chat_response:")
    assert fake_engine.payloads[0]["provider_id"] == "openrouter"
    assert fake_engine.payloads[0]["safe_mode"] is True

    state = client.get("/creator/console")
    assert state.status_code == 200
    assert state.json()["provider_state"] == "openrouter_ready"


def test_api_chat_compatibility_uses_creator_console_real_chat(monkeypatch) -> None:
    fake_engine = FakeCreatorChatEngine("FORJA responde por /api/chat sin fallback.")
    monkeypatch.setattr(creator_service, "_real_execution_engine", fake_engine)

    status = client.get("/api/chat")
    assert status.status_code == 200
    assert status.json()["reply"] != "OPENROUTER_NOT_CONFIGURED"

    response = client.post(
        "/api/chat",
        json={"message": "Hola FORJA", "app": "FORJA", "context": "validacion compat chat"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["reply"] == "FORJA responde por /api/chat sin fallback."
    assert payload["reply_source"] == "openrouter"
    assert payload["intent"]["name"] == "saludo"
    assert payload["provider"] == "openrouter"
    assert payload["command_id"]
    assert payload["response_received"] is True
    assert payload["secrets_exposed"] is False
    assert fake_engine.payloads[0]["provider_id"] == "openrouter"
    assert fake_engine.payloads[0]["read_only_chat"] is True
    assert fake_engine.payloads[0]["max_tokens"] == 1800


def test_api_chat_compacts_context_above_legacy_12000_limit(monkeypatch) -> None:
    fake_engine = FakeCreatorChatEngine("Propuesta para spa en Cusco lista y accionable.")
    monkeypatch.setattr(creator_service, "_real_execution_engine", fake_engine)
    long_context = {
        "globalStatus": "OPERATIONAL",
        "directorLines": [
            {"label": "Linea", "status": "READY", "text": "contexto repetido " * 120}
            for _ in range(12)
        ],
        "snapshot": {
            "metrics": [{"label": "Apps", "value": "12", "status": "READY", "detail": "detalle " * 200}],
            "constructionQueue": [{"app": "FORJA", "task": "tarea " * 200, "status": "READY"} for _ in range(20)],
            "approvals": [{"title": "aprobacion " * 120, "status": "PENDING"} for _ in range(20)],
            "blockers": [{"title": "bloqueo " * 120, "cause": "causa " * 120} for _ in range(20)],
            "deliveries": [{"name": "entrega " * 120, "path": "ruta " * 120} for _ in range(20)],
            "flow": [{"stage": "FLOW", "detail": "detalle " * 120} for _ in range(20)],
            "memory": {"registered_apps": ["FORJA"] * 100, "active_apps": ["FORJA"] * 100},
            "localAgent": {"latest_results": [{"title": "resultado " * 120} for _ in range(20)]},
        },
    }

    response = client.post(
        "/api/chat",
        json={
            "message": "FORJA, crea una propuesta para un spa en Cusco.",
            "app": "FORJA",
            "context": json.dumps(long_context),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["context_compacted"] is True
    assert payload["provider_payload_chars"] <= 5600
    assert "demasiado contexto" not in payload["reply"].lower()
    assert "spa en Cusco" in payload["reply"]
    assert "turistas que estan comparando" not in payload["reply"]
    assert "agencia de viajes" not in payload["reply"].lower()
    assert len(fake_engine.payloads[0]["objective"]) <= 5200


def test_api_chat_short_greeting_does_not_surface_context_budget_warning(monkeypatch) -> None:
    fake_engine = FakeCreatorChatEngine("Hola, soy FORJA. Estoy operativa y lista para ayudarte.")
    monkeypatch.setattr(creator_service, "_real_execution_engine", fake_engine)
    long_context = {
        "globalStatus": "OPERATIONAL",
        "directorLines": [
            {"label": "Estado", "status": "READY", "text": "contexto operativo " * 120}
            for _ in range(10)
        ],
        "snapshot": {
            "metrics": [{"label": "Apps en construccion", "value": "9", "status": "OPERATIONAL", "detail": "detalle " * 160}],
            "constructionQueue": [{"app": "FORJA", "task": "tarea " * 100, "status": "READY"} for _ in range(8)],
            "memory": {"registered_apps": ["FORJA"] * 20, "active_apps": ["FORJA"] * 20},
            "localAgent": {"agents": {"online": 1}, "tasks": {"queued": 0}},
        },
    }

    response = client.post(
        "/api/chat",
        json={
            "message": "hola",
            "app": "FORJA",
            "context": json.dumps(long_context),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["context_compacted"] is True
    assert "demasiado contexto" not in payload["reply"].lower()
    assert "Estoy lista para ordenar la obra" in payload["reply"]
    assert payload["reply_source"] == "memory_direct"
    assert fake_engine.payloads == []


def test_api_chat_human_cabin_commercial_context_uses_local_guardrail(monkeypatch) -> None:
    fake_engine = FakeCreatorChatEngine("Proveedor externo no deberia bloquear la cabina.")
    monkeypatch.setattr(creator_service, "_real_execution_engine", fake_engine)
    context = {
        "source": "human_cabin_v5_compact_context",
        "globalStatus": "OPERATIONAL",
        "snapshot": {
            "metrics": [{"label": "Apps en construccion", "value": "9", "status": "OPERATIONAL"}],
            "localAgent": {"agents": {"online": 1}, "tasks": {"queued": 0}},
        },
    }

    response = client.post(
        "/api/chat",
        json={
            "message": "FORJA, crea una propuesta para un spa en Cusco.",
            "app": "FORJA",
            "context": json.dumps(context),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["reply_source"] == "memory_direct"
    assert "spa en Cusco" in payload["reply"]
    assert "Calendario de 7 dias" in payload["reply"]
    assert "CTA:" in payload["reply"]
    assert "demasiado contexto" not in payload["reply"].lower()
    assert fake_engine.payloads == []


def test_api_chat_marketing_focus_does_not_inject_ecosystem_memory(monkeypatch) -> None:
    fake_engine = FakeCreatorChatEngine(
        "Titulo: Propuesta para agencia de viajes. Objetivo: captar turistas con una campana clara. "
        "Publico objetivo: viajeros interesados en experiencias memorables. Estrategia: inspiracion, prueba social y oferta. "
        "Calendario: 7 dias de contenido con CTA diario. Siguiente paso: elegir la experiencia principal y preparar el primer post."
    )
    monkeypatch.setattr(creator_service, "_real_execution_engine", fake_engine)
    monkeypatch.setattr(creator_service, "_ecosystem_memory", FakeEcosystemMemory())

    response = client.post(
        "/api/chat",
        json={
            "message": "Convierte esta idea en un entregable para cliente: campana de 7 dias para captar turistas.",
            "app": "FORJA",
            "context": "Human Cabin tiene CEREBRO, CENTINELA, Local Agent y memoria interna visibles.",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    objective = fake_engine.payloads[0]["objective"]
    assert payload["intent"]["name"] == "preparar_marketing"
    assert payload["reply_source"] == "openrouter"
    assert "modo cliente/marketing" in objective
    assert "calendario de 7 dias" in objective
    assert "FORJA_PHASE2_DECISION_TRACE.md" not in objective
    assert "Apps registradas" not in objective
    assert "Human Cabin tiene CEREBRO" not in objective


def test_api_chat_marketing_guardrail_removes_internal_leaks(monkeypatch) -> None:
    fake_engine = FakeCreatorChatEngine("Debemos usar CEREBRO, Local Agent, OpenRouter y la arquitectura interna.")
    monkeypatch.setattr(creator_service, "_real_execution_engine", fake_engine)

    response = client.post(
        "/api/chat",
        json={
            "message": "Hazme un entregable formal para enviar a un cliente, con titulo, objetivo, estrategia, acciones y proximos pasos.",
            "app": "FORJA",
            "context": "validacion marketing",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["reply_source"] == "commercial_guardrail"
    assert "CEREBRO" not in payload["reply"]
    assert "Local Agent" not in payload["reply"]
    assert "OpenRouter" not in payload["reply"]
    assert "Titulo:" in payload["reply"]
    assert "Objetivo:" in payload["reply"]
    assert "Siguiente paso:" in payload["reply"]


def test_api_chat_marketing_guardrail_replaces_low_value_safety_reply(monkeypatch) -> None:
    fake_engine = FakeCreatorChatEngine("User Safety: safe")
    monkeypatch.setattr(creator_service, "_real_execution_engine", fake_engine)

    response = client.post(
        "/api/chat",
        json={
            "message": "FORJA, necesito crear una propuesta de contenido para una agencia de viajes en Cusco. Dame estructura, ideas, calendario y primer paso.",
            "app": "FORJA",
            "context": "validacion marketing",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["reply_source"] == "commercial_guardrail"
    assert payload["reply"] != "User Safety: safe"
    assert "Titulo:" in payload["reply"]
    assert "Calendario de 7 dias:" in payload["reply"]
    assert "Siguiente paso:" in payload["reply"]


def test_api_chat_marketing_guardrail_requires_complete_client_deliverable(monkeypatch) -> None:
    fake_engine = FakeCreatorChatEngine("Entendido. Primer paso: crear un calendario para publicar durante 7 dias.")
    monkeypatch.setattr(creator_service, "_real_execution_engine", fake_engine)

    response = client.post(
        "/api/chat",
        json={
            "message": "Convierte esta idea en un entregable para cliente: campana de 7 dias para captar turistas.",
            "app": "FORJA",
            "context": "validacion marketing",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["reply_source"] == "commercial_guardrail"
    for expected in ["Titulo:", "Objetivo:", "Publico objetivo:", "Estrategia:", "Acciones:", "Calendario de 7 dias:", "CTA:", "Siguiente paso:"]:
        assert expected in payload["reply"]


def test_api_chat_recovery_review_uses_internal_guardrail(monkeypatch) -> None:
    fake_engine = FakeCreatorChatEngine("Accion inmediata: crear un video y una presentacion esta semana.")
    monkeypatch.setattr(creator_service, "_real_execution_engine", fake_engine)

    response = client.post(
        "/api/chat",
        json={
            "message": "Estamos recuperando FORJA porque respondia mal. Que estamos revisando ahora?",
            "app": "FORJA",
            "context": "validacion interna",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["reply_source"] == "internal_guardrail"
    assert "Foco conversacional" in payload["reply"]
    assert "Local Agent" in payload["reply"]
    assert "prompts reales" in payload["reply"]


def test_api_chat_simplification_keeps_commercial_client_focus(monkeypatch) -> None:
    fake_engine = QueuedFakeCreatorChatEngine(
        [
            "Titulo: Campana Cusco. Objetivo: captar turistas. Publico: viajeros. Estrategia: contenido. Calendario: dia 1 a dia 7. CTA: Escribenos. Siguiente paso: publicar.",
            "Objetivo: Posicionar FORJA como aliado estrategico para pymes.",
        ]
    )
    monkeypatch.setattr(creator_service, "_real_execution_engine", fake_engine)
    session_id = "pytest-commercial-simplify-focus"

    first = client.post(
        "/api/chat",
        json={
            "message": "FORJA, necesito crear una propuesta de contenido para una agencia de viajes en Cusco. Dame estructura, ideas, calendario y primer paso.",
            "app": "FORJA",
            "session_id": session_id,
            "context": "validacion marketing",
        },
    )
    assert first.status_code == 200

    second = client.post(
        "/api/chat",
        json={"message": "No entendi. Explicamelo mas simple y dime exactamente que hago primero.", "app": "FORJA", "session_id": session_id},
    )
    assert second.status_code == 200
    payload = second.json()
    assert payload["reply_source"] == "commercial_guardrail"
    assert "FORJA" not in payload["reply"]
    assert "Lo primero que haria ahora" in payload["reply"]


def test_api_chat_commercial_continuation_rejects_domain_drift(monkeypatch) -> None:
    fake_engine = QueuedFakeCreatorChatEngine(
        [
            "Titulo: Propuesta para spa en Cusco. Objetivo: atraer reservas. Publico: visitantes que buscan bienestar. Estrategia: contenido de confianza. Calendario: dia 1 a dia 7. CTA: Reserva. Siguiente paso: publicar.",
            "Titulo: Descubre el Futuro de los Espacios Compactos. Objetivo: captar leads de vivienda ligera. Publico objetivo: adultos urbanos. Estrategia: mostrar home office minimalista. Calendario: dia 1 a dia 7. CTA: escribenos. Siguiente paso: cotizar.",
        ]
    )
    monkeypatch.setattr(creator_service, "_real_execution_engine", fake_engine)
    session_id = "pytest-commercial-domain-drift"

    first = client.post(
        "/api/chat",
        json={
            "message": "FORJA, crea una propuesta para un spa en Cusco.",
            "app": "FORJA",
            "session_id": session_id,
            "context": "validacion marketing",
        },
    )
    assert first.status_code == 200

    second = client.post(
        "/api/chat",
        json={"message": "Convierte esto en un entregable para cliente.", "app": "FORJA", "session_id": session_id},
    )
    assert second.status_code == 200
    payload = second.json()
    assert payload["reply_source"] == "commercial_guardrail"
    assert "spa en Cusco" in payload["reply"]
    assert "Espacios Compactos" not in payload["reply"]
    assert "home office" not in payload["reply"]


def test_api_chat_uses_safe_token_floor_and_cap(monkeypatch) -> None:
    monkeypatch.delenv("FORJA_OPENROUTER_MAX_TOKENS", raising=False)
    monkeypatch.delenv("OPENROUTER_MAX_TOKENS", raising=False)
    assert creator_service._real_chat_max_tokens() == 1800

    monkeypatch.setenv("FORJA_OPENROUTER_MAX_TOKENS", "800")
    assert creator_service._real_chat_max_tokens() == 1200

    monkeypatch.setenv("FORJA_OPENROUTER_MAX_TOKENS", "9000")
    assert creator_service._real_chat_max_tokens() == 2500


def test_api_chat_creates_local_agent_report_task_from_human_cabin(monkeypatch) -> None:
    fake_engine = FakeCreatorChatEngine("FORJA crea la tarea del Local Agent.")
    monkeypatch.setattr(creator_service, "_real_execution_engine", fake_engine)

    response = client.post(
        "/api/chat",
        json={
            "message": "Genera un inventario de aplicaciones y guardalo como ECOSYSTEM_APPS_REPORT.md",
            "app": "FORJA",
            "context": "human cabin report request",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    task = payload["local_agent_task"]
    assert task["task_id"].startswith("task-")
    assert task["status"] == "queued"
    assert task["task_type"] == "report_generation"
    assert task["desired_output"] == "ECOSYSTEM_APPS_REPORT.md"
    assert "CEO, tarea creada. La estoy enviando al agente local." in payload["reply"]
    assert payload["delivery"]["path"].endswith(r"FORJA\ECOSYSTEM_APPS_REPORT.md")

    stored = client.get(f"/local-agent/tasks/{task['task_id']}")
    assert stored.status_code == 200
    assert stored.json()["policy"]["requires_backup"] is True
    assert stored.json()["policy"]["requires_rollback_plan"] is True
    assert stored.json()["target"]["delivery_owner"] == "CEO"


def test_api_chat_understands_create_app_intent_and_persists_history(monkeypatch) -> None:
    fake_engine = FakeCreatorChatEngine(
        "OpenRouter apoyo la respuesta natural. Para construir AUDITORIA necesito definir 5 cosas. Enviar al Local Agent."
    )
    monkeypatch.setattr(creator_service, "_real_execution_engine", fake_engine)
    session_id = "pytest-create-auditoria-clean"

    response = client.post(
        "/api/chat",
        json={
            "message": "Quiero hacer una app que se llame Auditoria. Que necesitas para hacerla?",
            "app": "FORJA",
            "session_id": session_id,
            "context": "human cabin natural intent",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"]["name"] == "crear_app"
    assert payload["intent"]["requires_local_agent"] is True
    assert payload["intent"]["requires_confirmation"] is True
    assert "Para construir AUDITORIA necesito definir 5 cosas" in payload["reply"]
    assert "Enviar al Local Agent" in payload["reply"]
    assert payload["reply_source"] == "openrouter"
    assert payload["local_agent_task"] is None

    history = client.get("/api/chat/history", params={"session_id": session_id})
    assert history.status_code == 200
    messages = history.json()["messages"]
    assert any(message["role"] == "user" and "Auditoria" in message["text"] for message in messages)
    assert any(message["role"] == "forja" and "AUDITORIA" in message["text"] for message in messages)


def test_api_chat_reports_last_delivery_path(monkeypatch) -> None:
    fake_engine = FakeCreatorChatEngine("OpenRouter apoyo la tarea.")
    monkeypatch.setattr(creator_service, "_real_execution_engine", fake_engine)
    session_id = "pytest-last-delivery"

    created = client.post(
        "/api/chat",
        json={
            "message": "Genera un inventario de aplicaciones del ecosistema y guardalo como ECOSYSTEM_APPS_REPORT.md",
            "app": "FORJA",
            "session_id": session_id,
            "context": "human cabin report request",
        },
    )
    assert created.status_code == 200
    expected_path = created.json()["delivery"]["path"]

    response = client.post(
        "/api/chat",
        json={"message": "Donde quedo el archivo?", "app": "FORJA", "session_id": session_id},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"]["name"] == "pedir_entrega"
    assert expected_path in payload["reply"]


def test_creator_console_injects_existing_ecosystem_memory(monkeypatch) -> None:
    fake_engine = FakeCreatorChatEngine("FORJA responde usando memoria real.")
    monkeypatch.setattr(creator_service, "_real_execution_engine", fake_engine)
    monkeypatch.setattr(creator_service, "_ecosystem_memory", FakeEcosystemMemory())

    response = client.post(
        "/creator/commands",
        json={"sender": "user", "command": "Que aplicaciones existen?", "details": "Safe-mode OpenRouter response enabled."},
    )
    assert response.status_code == 200
    payload = response.json()
    objective = fake_engine.payloads[0]["objective"]
    assert "FORJA_PHASE2_DECISION_TRACE.md" in objective
    assert "CEREBRO, CENTINELA, PLUMA" in objective
    assert "PLUMA" in payload["outputs"][0]["content"]["ecosystem_memory"]["apps_missing_from_primary_memory"]
    assert "ecosystem_memory=read_only" in payload["governance"]["required_permissions"]
    assert any(event["event"] == "ecosystem_memory.loaded" for event in payload["timeline"])


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
