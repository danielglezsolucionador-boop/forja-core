from __future__ import annotations

from pathlib import Path

from app.core.audit import read_audit_events
from app.core.storage import JsonStore
from app.services.ecosystem_orchestration_service import (
    AgentContractManager,
    CerebroControlBridge,
    EcosystemMessageService,
    EcosystemOrchestrationStatus,
    HermesMemoryBridge,
    OrchestrationLogManager,
    write_operational_core_snapshot_document,
)


def _contracts(tmp_path: Path) -> AgentContractManager:
    return AgentContractManager(JsonStore(tmp_path / "state" / "contracts.json"))


def _messages(tmp_path: Path) -> EcosystemMessageService:
    return EcosystemMessageService(JsonStore(tmp_path / "state" / "messages.json"))


def _hermes(tmp_path: Path) -> HermesMemoryBridge:
    return HermesMemoryBridge(JsonStore(tmp_path / "state" / "hermes.json"))


def _cerebro(tmp_path: Path) -> CerebroControlBridge:
    return CerebroControlBridge(JsonStore(tmp_path / "state" / "cerebro.json"))


def _orchestration(tmp_path: Path) -> OrchestrationLogManager:
    return OrchestrationLogManager(JsonStore(tmp_path / "state" / "orchestration.json"))


def test_agent_contracts_create_ceo_cerebro_and_hermes_contracts(tmp_path: Path) -> None:
    records = _contracts(tmp_path).initialize()["contracts"]
    pairs = {(item["source_agent"], item["target_agent"]) for item in records}
    assert ("ceo", "forja") in pairs
    assert ("cerebro", "forja") in pairs
    assert ("forja", "hermes") in pairs
    assert ("forja", "cerebro") in pairs


def test_agent_contract_ceo_authority_rules(tmp_path: Path) -> None:
    ceo = next(item for item in _contracts(tmp_path).contracts() if item["source_agent"] == "ceo")
    assert {"build", "repair", "analyze", "approve", "reject"}.issubset(set(ceo["allowed_intents"]))
    assert ceo["authority_level"] == "owner"
    assert ceo["approval_rules"]["can_approve"] is True


def test_agent_contract_cerebro_response_rules(tmp_path: Path) -> None:
    cerebro = next(item for item in _contracts(tmp_path).contracts() if item["source_agent"] == "cerebro")
    assert "coordinate" in cerebro["allowed_intents"]
    assert cerebro["response_rules"]["response_target"] == "cerebro"
    assert cerebro["audit_required"] is True


def test_agent_contract_invalid_contract_blocked(tmp_path: Path) -> None:
    result = _contracts(tmp_path).validate({"source_agent": "bad", "target_agent": "forja", "allowed_intents": [], "response_rules": {}})
    assert result["valid"] is False
    assert result["reason"] == "invalid_contract"


def test_agent_contract_audit_events(tmp_path: Path) -> None:
    _contracts(tmp_path).initialize()
    audit_types = {event["event_type"] for event in read_audit_events(80)}
    assert {"agent_contract_created", "agent_contract_validated"}.issubset(audit_types)


def test_ecosystem_message_ceo_to_forja_build(tmp_path: Path) -> None:
    message = _messages(tmp_path).create({"sender": "ceo", "recipient": "forja", "intent": "build", "correlation_id": "corr-ceo-build", "payload": {"input": "app"}})
    assert message["valid"] is True
    assert message["response_target"] == "ceo"


def test_ecosystem_message_cerebro_to_forja_repair(tmp_path: Path) -> None:
    message = _messages(tmp_path).create(
        {"sender": "cerebro", "recipient": "forja", "intent": "repair", "correlation_id": "corr-cerebro-repair", "payload": {"target": "backend"}}
    )
    assert message["valid"] is True
    assert message["response_target"] == "cerebro"


def test_ecosystem_message_forja_to_hermes_memory_request_mock(tmp_path: Path) -> None:
    message = _messages(tmp_path).create(
        {"sender": "forja", "recipient": "hermes", "intent": "memory_request", "correlation_id": "corr-hermes-memory", "payload": {"summary": "store"}}
    )
    assert message["valid"] is True
    assert message["response_target"] == "hermes"


def test_ecosystem_message_forja_to_cerebro_result_delivery_mock(tmp_path: Path) -> None:
    message = _messages(tmp_path).create(
        {"sender": "forja", "recipient": "cerebro", "intent": "result_delivery", "correlation_id": "corr-cerebro-result", "payload": {"status": "completed"}}
    )
    assert message["valid"] is True
    assert message["response_target"] == "cerebro"


def test_ecosystem_message_invalid_recipient_missing_correlation_and_payload(tmp_path: Path) -> None:
    invalid_recipient = _messages(tmp_path).create({"sender": "ceo", "recipient": "bad", "intent": "build", "correlation_id": "corr-bad", "payload": {}})
    missing_correlation = _messages(tmp_path).create({"sender": "ceo", "recipient": "forja", "intent": "build", "payload": {}})
    invalid_payload = _messages(tmp_path).create({"sender": "ceo", "recipient": "forja", "intent": "build", "correlation_id": "corr-invalid", "payload": "bad"})
    assert invalid_recipient["blocked_reason"] == "invalid_recipient"
    assert missing_correlation["blocked_reason"] == "missing_correlation_id"
    assert invalid_payload["blocked_reason"] == "invalid_payload"


def test_ecosystem_message_audit_events(tmp_path: Path) -> None:
    _messages(tmp_path).create({"sender": "ceo", "recipient": "forja", "intent": "audit", "correlation_id": "corr-audit", "payload": {"scope": "loop"}})
    audit_types = {event["event_type"] for event in read_audit_events(80)}
    assert {"ecosystem_message_created", "ecosystem_message_validated"}.issubset(audit_types)


def test_hermes_memory_payload_build_and_status(tmp_path: Path) -> None:
    bridge = _hermes(tmp_path)
    payload = bridge.save_operational_memory(
        {
            "correlation_id": "corr-hermes",
            "request_summary": "Build app",
            "blueprint_summary": "React/FastAPI",
            "delivery_package_summary": "Delivery ready",
            "audit_summary": "Audit ok",
            "workspace_manifest": {"files": []},
            "final_status": "completed",
        }
    )
    status = bridge.get_memory_status()
    assert payload["mode"] == "mock"
    assert payload["real_call_executed"] is False
    assert status["bridge_status"] == "prepared"


def test_hermes_execution_workspace_and_audit_payloads(tmp_path: Path) -> None:
    bridge = _hermes(tmp_path)
    execution = bridge.attach_execution_summary({"correlation_id": "corr-exec", "request_summary": "execution"})
    manifest = bridge.attach_workspace_manifest({"correlation_id": "corr-manifest", "workspace_manifest": {"files": ["README.md"]}})
    audit = bridge.attach_audit_summary({"correlation_id": "corr-audit-summary", "audit_summary": "audit"})
    assert execution["payload_type"] == "execution_summary"
    assert manifest["workspace_manifest"]["files"] == ["README.md"]
    assert audit["payload_type"] == "audit_summary"


def test_hermes_bridge_does_not_call_real_runtime(tmp_path: Path) -> None:
    context = _hermes(tmp_path).retrieve_context("corr-no-real")
    assert context["mode"] == "mock"
    assert context["real_call_executed"] is False


def test_hermes_bridge_audit_events(tmp_path: Path) -> None:
    _hermes(tmp_path).save_operational_memory({"correlation_id": "corr-hermes-audit"})
    audit_types = {event["event_type"] for event in read_audit_events(80)}
    assert {"hermes_bridge_prepared", "memory_payload_created", "memory_bridge_mocked"}.issubset(audit_types)


def test_cerebro_bridge_order_repair_approval_result_and_capability(tmp_path: Path) -> None:
    bridge = _cerebro(tmp_path)
    build = bridge.receive_order({"correlation_id": "corr-cerebro-build", "intent": "build", "payload": {"input": "app"}})
    repair = bridge.receive_order({"correlation_id": "corr-cerebro-repair", "intent": "repair", "payload": {"target": "backend"}})
    approval = bridge.request_approval({"correlation_id": "corr-cerebro-approval", "payload": {"approval": "required"}})
    result = bridge.send_result({"correlation_id": "corr-cerebro-result", "payload": {"status": "completed"}})
    capability = bridge.send_capability_request({"correlation_id": "corr-cerebro-capability", "payload": {"capability": "coding"}})
    assert build["payload_type"] == "order"
    assert repair["intent"] == "repair"
    assert approval["payload_type"] == "approval_request"
    assert result["payload_type"] == "result_delivery"
    assert capability["payload_type"] == "capability_request"
    assert all(item["real_call_executed"] is False for item in [build, repair, approval, result, capability])


def test_cerebro_bridge_audit_summary_and_status(tmp_path: Path) -> None:
    bridge = _cerebro(tmp_path)
    audit = bridge.send_audit_summary({"correlation_id": "corr-cerebro-audit", "payload": {"events": 3}})
    status = bridge.get_control_status()
    assert audit["payload_type"] == "audit_summary"
    assert status["bridge_status"] == "prepared"
    assert status["real_connection"] is False


def test_cerebro_bridge_audit_events(tmp_path: Path) -> None:
    _cerebro(tmp_path).send_result({"correlation_id": "corr-cerebro-audit-events"})
    audit_types = {event["event_type"] for event in read_audit_events(80)}
    assert {"cerebro_bridge_prepared", "control_payload_created", "cerebro_mock_response_created"}.issubset(audit_types)


def test_orchestration_log_ceo_cerebro_hermes_capability_and_delivery(tmp_path: Path) -> None:
    manager = _orchestration(tmp_path)
    records = [
        manager.log({"correlation_id": "corr-orch", "sender": "ceo", "recipient": "forja", "request_type": "build", "status": "started"}),
        manager.log({"correlation_id": "corr-orch", "sender": "cerebro", "recipient": "forja", "request_type": "build", "status": "started"}),
        manager.log({"correlation_id": "corr-orch", "sender": "forja", "recipient": "hermes", "request_type": "memory_request", "status": "logged"}),
        manager.log({"correlation_id": "corr-orch", "sender": "forja", "recipient": "cerebro", "request_type": "capability_request", "status": "logged"}),
        manager.log({"correlation_id": "corr-orch", "sender": "forja", "recipient": "cerebro", "request_type": "result_delivery", "output_id": "delivery", "status": "delivered"}),
    ]
    assert len(manager.records("corr-orch")) == 5
    assert records[-1]["response_target"] == "cerebro"
    assert records[-1]["output_id"] == "delivery"


def test_orchestration_log_correlation_and_audit(tmp_path: Path) -> None:
    manager = _orchestration(tmp_path)
    record = manager.log({"correlation_id": "corr-orch-audit", "sender": "ceo", "recipient": "forja", "status": "completed"})
    assert manager.records("corr-orch-audit")[0]["orchestration_id"] == record["orchestration_id"]
    audit_types = {event["event_type"] for event in read_audit_events(80)}
    assert {"orchestration_started", "orchestration_step_logged", "orchestration_completed"}.issubset(audit_types)


def test_orchestration_blocks_invalid_agent(tmp_path: Path) -> None:
    record = _orchestration(tmp_path).log({"correlation_id": "corr-invalid-agent", "sender": "bad", "recipient": "forja"})
    assert record["status"] == "blocked"
    assert record["reason"] == "invalid_agent"


def test_final_ecosystem_status_and_snapshot_document(tmp_path: Path) -> None:
    contracts = _contracts(tmp_path)
    messages = _messages(tmp_path)
    hermes = _hermes(tmp_path)
    cerebro = _cerebro(tmp_path)
    orchestration = _orchestration(tmp_path)
    contracts.initialize()
    messages.create({"sender": "ceo", "recipient": "forja", "intent": "build", "correlation_id": "corr-final", "payload": {"input": "app"}})
    hermes.save_operational_memory({"correlation_id": "corr-final", "request_summary": "build"})
    cerebro.send_result({"correlation_id": "corr-final", "payload": {"status": "completed"}})
    orchestration.log({"correlation_id": "corr-final", "sender": "ceo", "recipient": "forja", "status": "completed"})
    status = EcosystemOrchestrationStatus(contracts, messages, hermes, cerebro, orchestration).status()
    doc_path = tmp_path / "FORJA_OPERATIONAL_CORE_FINAL.md"
    write_operational_core_snapshot_document(doc_path, {"status": status["status"]})
    assert status["status"] == "prepared"
    assert status["real_hermes_connection"] is False
    assert status["real_cerebro_connection"] is False
    assert doc_path.read_text(encoding="utf-8").startswith("# FORJA Operational Core Final")
