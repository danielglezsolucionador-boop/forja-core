from __future__ import annotations

import uuid

from app.core.audit import append_audit_event, read_audit_events, utc_now
from app.core.storage import store


COMMAND_STATUSES = [
    "received",
    "governance_check",
    "awaiting_approval",
    "approved",
    "blocked",
    "executing",
    "completed",
    "failed",
]


class CreatorService:
    def __init__(self) -> None:
        self._commands = store("creator_commands")

    def console_state(self, limit: int = 50) -> dict:
        return {
            "mode": "controlled_creator_console",
            "provider_state": "provider_disabled_by_governance",
            "command_statuses": COMMAND_STATUSES,
            "commands": self.list_commands(limit),
            "audit_stream": read_audit_events(40),
        }

    def create_command(self, payload: dict) -> dict:
        now = utc_now()
        record = {
            "id": str(uuid.uuid4()),
            "timestamp": now,
            "sender": payload["sender"],
            "reply_to_sender": payload["sender"],
            "command": payload["command"],
            "details": payload.get("details", ""),
            "status": "blocked",
            "response": "provider_disabled_by_governance",
            "pipeline": [
                {"status": "received", "label": "Received", "detail": "Command accepted into the controlled console."},
                {"status": "governance_check", "label": "Governance check", "detail": "Request inspected before execution."},
                {"status": "awaiting_approval", "label": "Awaiting approval", "detail": "Human approval is required before any write or provider action."},
                {"status": "blocked", "label": "Blocked", "detail": "External provider execution is disabled by governance."},
            ],
            "governance": {
                "risk_level": self._risk_level(payload),
                "blocked_reason": "provider_disabled_by_governance",
                "required_permissions": ["human_approval", "allow_write=true", "provider_enabled"],
                "provider_status": "disabled",
            },
            "timeline": [
                {"timestamp": now, "event": "command.received", "detail": f"Command received from {payload['sender']}."},
                {"timestamp": now, "event": "governance.checked", "detail": "Zero-write policy and disabled-provider boundary enforced."},
                {"timestamp": now, "event": "execution.blocked", "detail": "No AI provider, file write, workflow execution, or deployment was started."},
            ],
            "outputs": [
                {"kind": "result", "name": "provider_disabled_by_governance", "status": "blocked"},
                {"kind": "structure", "name": "execution_plan", "status": "not_created"},
                {"kind": "file", "name": "generated_files", "status": "not_written"},
            ],
        }
        self._commands.update([], lambda records: records.append(record))
        append_audit_event(
            "creator.command_blocked",
            payload["sender"],
            {"id": record["id"], "reply_to_sender": record["reply_to_sender"], "reason": record["response"]},
            risk=record["governance"]["risk_level"],
        )
        return record

    def decide_command(self, command_id: str, decision: str, reason: str) -> dict | None:
        result: dict | None = None
        now = utc_now()

        def mutate(records: list[dict]) -> None:
            nonlocal result
            for record in records:
                if record["id"] != command_id:
                    continue
                if decision == "hold":
                    record["status"] = "awaiting_approval"
                    detail = "Command held for authenticated governance review."
                elif decision == "reject":
                    record["status"] = "blocked"
                    detail = "Command rejected by operator intent."
                else:
                    record["status"] = "blocked"
                    detail = "Approval intent captured, but execution remains blocked because provider is disabled by governance."
                record["timeline"].append({"timestamp": now, "event": f"approval.{decision}", "detail": detail})
                record["governance"]["blocked_reason"] = "provider_disabled_by_governance" if decision == "approve" else detail
                if reason:
                    record["timeline"].append({"timestamp": now, "event": "approval.reason", "detail": reason})
                result = dict(record)
                return

        self._commands.update([], mutate)
        if result is not None:
            append_audit_event(
                "creator.approval_intent_recorded",
                "operator",
                {"id": command_id, "decision": decision, "final_status": result["status"]},
                risk=result["governance"]["risk_level"],
            )
        return result

    def list_commands(self, limit: int = 50) -> list[dict]:
        return self._commands.read([])[-limit:]

    def _risk_level(self, payload: dict) -> str:
        text = f"{payload.get('command', '')} {payload.get('details', '')}".lower()
        if any(word in text for word in ["deploy", "delete", "database", "secret", "payment", "production"]):
            return "high"
        if any(word in text for word in ["write", "create", "generate", "execute", "build"]):
            return "medium"
        return "low"


creator_service = CreatorService()
