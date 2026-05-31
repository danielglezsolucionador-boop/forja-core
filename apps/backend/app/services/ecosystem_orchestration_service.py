from __future__ import annotations

import json
from pathlib import Path
import uuid

from app.core.audit import append_audit_event, read_audit_events, utc_now
from app.core.config import settings
from app.core.storage import JsonStore, store


AGENTS = {"ceo", "cerebro", "forja", "hermes"}
MESSAGE_INTENTS = {
    "build",
    "repair",
    "analyze",
    "audit",
    "capability_request",
    "status_report",
    "result_delivery",
    "approval_request",
    "memory_request",
}
AUTHORITY = {
    ("ceo", "forja"): ["build", "repair", "analyze", "approve", "reject"],
    ("cerebro", "forja"): ["build", "repair", "capability", "receive_result", "coordinate"],
    ("forja", "hermes"): ["memory_prepare", "context_attach", "history_attach"],
    ("forja", "cerebro"): ["result_delivery", "approval_request", "audit_summary", "capability_request"],
}


class AgentContractManager:
    def __init__(self, state_store: JsonStore | None = None) -> None:
        self._store = state_store or store("agent_contracts")

    def initialize(self) -> dict:
        contracts = [self._contract(source, target, intents) for (source, target), intents in AUTHORITY.items()]
        payload = {"contracts": contracts, "generated_at": utc_now()}
        self._store.write(payload)
        for contract in contracts:
            append_audit_event(
                "agent_contract_created",
                "system",
                {"source_agent": contract["source_agent"], "target_agent": contract["target_agent"], "contract_id": contract["contract_id"]},
                risk="low",
            )
            append_audit_event(
                "agent_contract_validated",
                "system",
                {"contract_id": contract["contract_id"], "valid": True},
                risk="low",
            )
        return payload

    def contracts(self) -> list[dict]:
        payload = self._store.read({"contracts": []})
        if not payload.get("contracts"):
            return self.initialize()["contracts"]
        return payload["contracts"]

    def validate(self, contract: dict) -> dict:
        valid = (
            contract.get("source_agent") in AGENTS
            and contract.get("target_agent") in AGENTS
            and bool(contract.get("allowed_intents"))
            and bool(contract.get("response_rules"))
        )
        append_audit_event(
            "agent_contract_validated",
            "system",
            {"contract_id": contract.get("contract_id"), "valid": valid},
            risk="low" if valid else "medium",
        )
        return {"valid": valid, "contract": contract, "reason": None if valid else "invalid_contract"}

    def _contract(self, source: str, target: str, intents: list[str]) -> dict:
        return {
            "contract_id": f"agent-contract-{source}-{target}",
            "source_agent": source,
            "target_agent": target,
            "allowed_intents": intents,
            "authority_level": self._authority_level(source, target),
            "approval_rules": self._approval_rules(source, target),
            "response_rules": {"response_target": source if source in {"ceo", "cerebro"} else target, "preserve_correlation_id": True},
            "audit_required": True,
            "correlation_required": True,
            "created_at": utc_now(),
        }

    def _authority_level(self, source: str, target: str) -> str:
        if source == "ceo":
            return "owner"
        if source == "cerebro":
            return "coordinator"
        if target in {"hermes", "cerebro"}:
            return "producer"
        return "limited"

    def _approval_rules(self, source: str, target: str) -> dict:
        if source == "ceo":
            return {"can_approve": True, "can_reject": True, "human_required_for_medium_high": True}
        if source == "cerebro":
            return {"can_request_approval": True, "must_preserve_response_target": True}
        return {"mock_only": True, "real_connection": False}


class EcosystemMessageService:
    def __init__(self, state_store: JsonStore | None = None) -> None:
        self._store = state_store or store("ecosystem_messages")

    def create(self, payload: dict) -> dict:
        message = {
            "message_id": payload.get("message_id") or f"msg-{uuid.uuid4()}",
            "correlation_id": payload.get("correlation_id"),
            "sender": str(payload.get("sender", "")).lower(),
            "recipient": str(payload.get("recipient", "")).lower(),
            "intent": str(payload.get("intent", "")).lower(),
            "payload": payload.get("payload") or {},
            "approvals": payload.get("approvals") or [],
            "capability_requirements": payload.get("capability_requirements") or [],
            "response_target": payload.get("response_target") or self._response_target(str(payload.get("sender", "")).lower(), str(payload.get("recipient", "")).lower()),
            "audit_id": payload.get("audit_id"),
            "priority": payload.get("priority") or "normal",
            "timestamp": utc_now(),
        }
        validation = self.validate(message)
        if not validation["valid"]:
            append_audit_event("invalid_message_blocked", message.get("sender") or "unknown", {"message_id": message["message_id"], "reason": validation["reason"]}, risk="medium")
            return {**message, "valid": False, "blocked_reason": validation["reason"]}
        self._save(message)
        append_audit_event("ecosystem_message_created", message["sender"], {"message_id": message["message_id"], "correlation_id": message["correlation_id"]}, risk="low")
        append_audit_event("ecosystem_message_validated", message["sender"], {"message_id": message["message_id"], "valid": True}, risk="low")
        return {**message, "valid": True, "blocked_reason": None}

    def validate(self, message: dict) -> dict:
        if message.get("sender") not in AGENTS:
            return {"valid": False, "reason": "invalid_sender"}
        if message.get("recipient") not in AGENTS:
            return {"valid": False, "reason": "invalid_recipient"}
        if message.get("intent") not in MESSAGE_INTENTS:
            return {"valid": False, "reason": "invalid_intent"}
        if not message.get("correlation_id"):
            return {"valid": False, "reason": "missing_correlation_id"}
        if not isinstance(message.get("payload"), dict):
            return {"valid": False, "reason": "invalid_payload"}
        expected_target = self._response_target(message["sender"], message["recipient"])
        if message.get("response_target") != expected_target:
            return {"valid": False, "reason": "invalid_response_target"}
        return {"valid": True, "reason": None}

    def latest(self) -> dict | None:
        records = self._store.read({"records": []}).get("records", [])
        return records[-1] if records else None

    def _response_target(self, sender: str, recipient: str) -> str:
        if sender in {"ceo", "cerebro"}:
            return sender
        return recipient

    def _save(self, message: dict) -> None:
        def mutator(payload: dict) -> None:
            payload.setdefault("records", []).append(message)
            payload["records"] = payload["records"][-240:]

        self._store.update({"records": []}, mutator)


class HermesMemoryBridge:
    def __init__(self, state_store: JsonStore | None = None) -> None:
        self._store = state_store or store("hermes_memory_bridge")

    def save_operational_memory(self, payload: dict) -> dict:
        return self._payload("operational_memory", payload)

    def retrieve_context(self, correlation_id: str) -> dict:
        return {"bridge": "hermes", "mode": "mock", "correlation_id": correlation_id, "context": {}, "real_call_executed": False, "status": "mock_only"}

    def attach_execution_summary(self, payload: dict) -> dict:
        return self._payload("execution_summary", payload)

    def attach_workspace_manifest(self, payload: dict) -> dict:
        return self._payload("workspace_manifest", payload)

    def attach_audit_summary(self, payload: dict) -> dict:
        return self._payload("audit_summary", payload)

    def get_memory_status(self) -> dict:
        return {"bridge_status": "prepared", "mode": "mock", "real_connection": False, "latest_payload": self.latest(), "generated_at": utc_now()}

    def latest(self) -> dict | None:
        records = self._store.read({"records": []}).get("records", [])
        return records[-1] if records else None

    def _payload(self, payload_type: str, payload: dict) -> dict:
        record = {
            "memory_payload_id": f"hermes-memory-{uuid.uuid4()}",
            "payload_type": payload_type,
            "correlation_id": payload.get("correlation_id") or f"corr-{uuid.uuid4()}",
            "request_summary": payload.get("request_summary"),
            "blueprint_summary": payload.get("blueprint_summary"),
            "delivery_package_summary": payload.get("delivery_package_summary"),
            "audit_summary": payload.get("audit_summary"),
            "workspace_manifest": payload.get("workspace_manifest"),
            "final_status": payload.get("final_status") or "prepared",
            "mode": "mock",
            "real_call_executed": False,
            "created_at": utc_now(),
        }
        self._save(record)
        append_audit_event("hermes_bridge_prepared", "forja", {"payload_id": record["memory_payload_id"]}, risk="low")
        append_audit_event("memory_payload_created", "forja", {"payload_id": record["memory_payload_id"], "payload_type": payload_type}, risk="low")
        append_audit_event("memory_bridge_mocked", "forja", {"payload_id": record["memory_payload_id"], "real_call_executed": False}, risk="low")
        return record

    def _save(self, record: dict) -> None:
        def mutator(payload: dict) -> None:
            payload.setdefault("records", []).append(record)
            payload["records"] = payload["records"][-120:]

        self._store.update({"records": []}, mutator)


class CerebroControlBridge:
    def __init__(self, state_store: JsonStore | None = None) -> None:
        self._store = state_store or store("cerebro_control_bridge")

    def receive_order(self, payload: dict) -> dict:
        return self._payload("order", payload)

    def request_approval(self, payload: dict) -> dict:
        return self._payload("approval_request", payload)

    def send_result(self, payload: dict) -> dict:
        return self._payload("result_delivery", payload)

    def send_capability_request(self, payload: dict) -> dict:
        return self._payload("capability_request", payload)

    def send_audit_summary(self, payload: dict) -> dict:
        return self._payload("audit_summary", payload)

    def get_control_status(self) -> dict:
        return {"bridge_status": "prepared", "mode": "mock", "real_connection": False, "latest_payload": self.latest(), "generated_at": utc_now()}

    def latest(self) -> dict | None:
        records = self._store.read({"records": []}).get("records", [])
        return records[-1] if records else None

    def _payload(self, payload_type: str, payload: dict) -> dict:
        record = {
            "control_payload_id": f"cerebro-control-{uuid.uuid4()}",
            "payload_type": payload_type,
            "correlation_id": payload.get("correlation_id") or f"corr-{uuid.uuid4()}",
            "sender": payload.get("sender") or "forja",
            "recipient": payload.get("recipient") or "cerebro",
            "intent": payload.get("intent") or payload_type,
            "response_target": payload.get("response_target") or "cerebro",
            "payload": payload.get("payload") or payload,
            "mode": "mock",
            "real_call_executed": False,
            "created_at": utc_now(),
        }
        self._save(record)
        append_audit_event("cerebro_bridge_prepared", "forja", {"payload_id": record["control_payload_id"]}, risk="low")
        append_audit_event("control_payload_created", "forja", {"payload_id": record["control_payload_id"], "payload_type": payload_type}, risk="low")
        append_audit_event("cerebro_mock_response_created", "forja", {"payload_id": record["control_payload_id"], "real_call_executed": False}, risk="low")
        return record

    def _save(self, record: dict) -> None:
        def mutator(payload: dict) -> None:
            payload.setdefault("records", []).append(record)
            payload["records"] = payload["records"][-120:]

        self._store.update({"records": []}, mutator)


class OrchestrationLogManager:
    def __init__(self, state_store: JsonStore | None = None) -> None:
        self._store = state_store or store("orchestration_log")

    def log(self, payload: dict) -> dict:
        correlation_id = payload.get("correlation_id") or f"corr-{uuid.uuid4()}"
        record = {
            "orchestration_id": payload.get("orchestration_id") or f"orch-{uuid.uuid4()}",
            "correlation_id": correlation_id,
            "sender": payload.get("sender") or "ceo",
            "recipient": payload.get("recipient") or "forja",
            "request_type": payload.get("request_type") or payload.get("intent") or "build",
            "capability_used": payload.get("capability_used"),
            "provider_used": payload.get("provider_used"),
            "workspace_id": payload.get("workspace_id"),
            "output_id": payload.get("output_id"),
            "audit_id": payload.get("audit_id"),
            "status": payload.get("status") or "logged",
            "response_target": payload.get("response_target") or self._response_target(payload.get("sender") or "ceo", payload.get("recipient") or "forja"),
            "created_at": utc_now(),
        }
        if record["sender"] not in AGENTS or record["recipient"] not in AGENTS:
            append_audit_event("orchestration_blocked", record["sender"], {"correlation_id": correlation_id, "reason": "invalid_agent"}, risk="medium")
            return {**record, "status": "blocked", "reason": "invalid_agent"}
        self._save(record)
        append_audit_event("orchestration_started", record["sender"], {"orchestration_id": record["orchestration_id"], "correlation_id": correlation_id}, risk="low")
        append_audit_event("orchestration_step_logged", record["sender"], {"orchestration_id": record["orchestration_id"], "status": record["status"]}, risk="low")
        if record["status"] in {"completed", "delivered"}:
            append_audit_event("orchestration_completed", record["sender"], {"orchestration_id": record["orchestration_id"], "correlation_id": correlation_id}, risk="low")
        return record

    def records(self, correlation_id: str | None = None) -> list[dict]:
        records = self._store.read({"records": []}).get("records", [])
        if correlation_id:
            return [record for record in records if record.get("correlation_id") == correlation_id]
        return records

    def latest(self) -> dict | None:
        records = self.records()
        return records[-1] if records else None

    def _response_target(self, sender: str, recipient: str) -> str:
        if sender in {"ceo", "cerebro"}:
            return sender
        return recipient

    def _save(self, record: dict) -> None:
        def mutator(payload: dict) -> None:
            payload.setdefault("records", []).append(record)
            payload["records"] = payload["records"][-300:]

        self._store.update({"records": []}, mutator)


class EcosystemOrchestrationStatus:
    def __init__(
        self,
        contracts: AgentContractManager,
        messages: EcosystemMessageService,
        hermes: HermesMemoryBridge,
        cerebro: CerebroControlBridge,
        orchestration: OrchestrationLogManager,
    ) -> None:
        self.contracts = contracts
        self.messages = messages
        self.hermes = hermes
        self.cerebro = cerebro
        self.orchestration = orchestration

    def status(self) -> dict:
        return {
            "status": "prepared",
            "mode": "mock_only",
            "contracts": self.contracts.contracts(),
            "latest_message": self.messages.latest(),
            "hermes_bridge": self.hermes.get_memory_status(),
            "cerebro_bridge": self.cerebro.get_control_status(),
            "orchestration_latest": self.orchestration.latest(),
            "real_hermes_connection": False,
            "real_cerebro_connection": False,
            "audit_events": self._audit_preview(),
            "generated_at": utc_now(),
        }

    def _audit_preview(self) -> list[dict]:
        types = {
            "agent_contract_created",
            "ecosystem_message_created",
            "hermes_bridge_prepared",
            "cerebro_bridge_prepared",
            "orchestration_started",
            "orchestration_completed",
        }
        result = []
        for event in read_audit_events(220):
            if event["event_type"] in types:
                result.append({"event_type": event["event_type"], "actor": event["actor"], "risk": event["risk"], "timestamp": event["timestamp"]})
        return result[-20:]


def write_operational_core_snapshot_document(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = (
        "# FORJA Operational Core Final\n\n"
        f"Date: {utc_now()}\n\n"
        "## What FORJA Can Do Now\n\n"
        "- Interpret human and mock Cerebro orders.\n"
        "- Generate governed blueprints, workspaces, initial files, validation reports, corrections, retries, and delivery packages.\n"
        "- Route capabilities through an economic AI Gateway abstraction.\n"
        "- Prepare Hermes and Cerebro ecosystem messages without real external calls.\n\n"
        "## What FORJA Cannot Do Yet\n\n"
        "- Connect to real Hermes or Cerebro runtime.\n"
        "- Execute unlimited real AI generation.\n"
        "- Deploy generated projects automatically.\n"
        "- Repair external projects without explicit future governance.\n\n"
        "## Builder Core\n\n"
        "Builder Core remains governed and workspace-isolated under `.forja/workspaces`.\n\n"
        "## AI Gateway\n\n"
        "Economic provider routing is primary. Premium providers remain prepared for future critical tasks.\n\n"
        "## Operational Loop\n\n"
        "Build, validation, correction, retry, and delivery managers are available.\n\n"
        "## Hermes Prep\n\n"
        "HermesMemoryBridge is mock/prep only; no real Hermes calls are executed.\n\n"
        "## Cerebro Prep\n\n"
        "CerebroControlBridge is mock/prep only; no real Cerebro calls are executed.\n\n"
        "## Limits\n\n"
        "- Safe mode and approval rules remain active.\n"
        "- Secrets are not logged or exposed.\n"
        "- Generated projects are scaffold outputs only.\n\n"
        "## Rollback\n\n"
        "Use the final branch/tag and generated backup archive to restore this source snapshot.\n\n"
        "## URLs\n\n"
        "- Frontend: https://forja-frontend.onrender.com/#human-console-preview\n"
        "- Backend: https://forja-core.onrender.com\n\n"
        "## Validation Summary\n\n"
        f"```json\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```\n\n"
        "## Next Steps\n\n"
        "- CTO/CEO review.\n"
        "- Configure economic provider credentials if real economic AI execution is required.\n"
        "- Plan Phase 8 only after review.\n"
    )
    path.write_text(content, encoding="utf-8")


agent_contract_manager = AgentContractManager()
ecosystem_message_service = EcosystemMessageService()
hermes_memory_bridge = HermesMemoryBridge()
cerebro_control_bridge = CerebroControlBridge()
orchestration_log_manager = OrchestrationLogManager()
ecosystem_orchestration_status = EcosystemOrchestrationStatus(
    agent_contract_manager,
    ecosystem_message_service,
    hermes_memory_bridge,
    cerebro_control_bridge,
    orchestration_log_manager,
)
