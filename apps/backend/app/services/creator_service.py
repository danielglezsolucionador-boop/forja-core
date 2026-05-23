from __future__ import annotations

import uuid

from app.core.audit import append_audit_event, read_audit_events, utc_now
from app.core.storage import store


COMMAND_STATUSES = [
    "received",
    "governance_check",
    "awaiting_approval",
    "approved",
    "executing",
    "completed",
    "blocked",
    "failed",
]


class CreatorService:
    def __init__(self) -> None:
        self._commands = store("creator_commands")

    def console_state(self, limit: int = 50) -> dict:
        return {
            "mode": "controlled_execution_engine",
            "provider_state": "provider_disabled_by_governance",
            "command_statuses": COMMAND_STATUSES,
            "commands": self.list_commands(limit),
            "audit_stream": read_audit_events(60),
        }

    def create_command(self, payload: dict) -> dict:
        now = utc_now()
        request_type = self._request_type(payload)
        risk_level = self._risk_level(payload)
        requires_provider = self._requires_provider(payload)
        status = "blocked" if requires_provider else "awaiting_approval"
        response = "blocked_provider_disabled" if requires_provider else "awaiting_human_approval"
        blocked_reason = "blocked_provider_disabled" if requires_provider else None
        record = {
            "id": str(uuid.uuid4()),
            "timestamp": now,
            "sender": payload["sender"],
            "reply_to_sender": payload["sender"],
            "command": payload["command"],
            "details": payload.get("details", ""),
            "request_type": request_type,
            "status": status,
            "response": response,
            "plan": self._plan(request_type, risk_level),
            "pipeline": self._pipeline(status, requires_provider),
            "governance": {
                "risk_level": risk_level,
                "blocked_reason": blocked_reason,
                "required_permissions": ["human_approval", "metadata_only=true", "zero_write_policy"],
                "provider_status": "disabled",
                "approval_status": "pending" if not requires_provider else "not_required",
            },
            "timeline": [
                self._event(now, "command.received", f"Command received from {payload['sender']}."),
                self._event(now, "request.classified", f"Classified as {request_type} with {risk_level} risk."),
                self._event(now, "governance.checked", "Zero-write policy, human approval, and provider boundary evaluated."),
            ],
            "execution_logs": [
                self._log(now, "info", "Request accepted by controlled execution engine."),
                self._log(now, "warning" if requires_provider else "info", response),
            ],
            "outputs": [
                {"kind": "metadata", "name": "execution_metadata", "status": "pending_approval" if not requires_provider else "not_created"},
                {"kind": "result", "name": response, "status": status},
            ],
        }
        if requires_provider:
            record["timeline"].append(self._event(now, "execution.blocked", "Provider execution is disabled by governance."))
        else:
            record["timeline"].append(self._event(now, "approval.required", "Human approval is required before metadata-only execution."))
        self._commands.update([], lambda records: records.append(record))
        append_audit_event(
            "creator.command_created",
            payload["sender"],
            {"id": record["id"], "reply_to_sender": record["reply_to_sender"], "status": status, "request_type": request_type},
            risk=risk_level,
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
                    record["response"] = "held_for_governance_review"
                    record["governance"]["approval_status"] = "held"
                    detail = "Command held for governance review."
                elif decision == "reject":
                    record["status"] = "blocked"
                    record["response"] = "rejected_by_human_governance"
                    record["governance"]["approval_status"] = "rejected"
                    record["governance"]["blocked_reason"] = "rejected_by_human_governance"
                    detail = "Command rejected by human governance."
                elif record["response"] == "blocked_provider_disabled":
                    record["status"] = "blocked"
                    record["governance"]["approval_status"] = "not_required"
                    record["governance"]["blocked_reason"] = "blocked_provider_disabled"
                    detail = "Approval cannot override disabled provider governance."
                else:
                    record["status"] = "approved"
                    record["response"] = "approved_for_metadata_only_execution"
                    record["governance"]["approval_status"] = "approved"
                    record["governance"]["blocked_reason"] = None
                    detail = "Human approval recorded for metadata-only execution."
                record["pipeline"] = self._pipeline(record["status"], record["response"] == "blocked_provider_disabled")
                record["timeline"].append(self._event(now, f"approval.{decision}", detail))
                record["execution_logs"].append(self._log(now, "info", detail))
                if reason:
                    record["timeline"].append(self._event(now, "approval.reason", reason))
                result = dict(record)
                return

        self._commands.update([], mutate)
        if result is not None:
            append_audit_event(
                "creator.approval_decision",
                "operator",
                {"id": command_id, "decision": decision, "final_status": result["status"]},
                risk=result["governance"]["risk_level"],
            )
        return result

    def execute_command(self, command_id: str, metadata_only: bool) -> dict | None:
        result: dict | None = None
        now = utc_now()

        def mutate(records: list[dict]) -> None:
            nonlocal result
            for record in records:
                if record["id"] != command_id:
                    continue
                if record["response"] == "blocked_provider_disabled":
                    self._block_execution(record, now, "blocked_provider_disabled")
                elif record["governance"]["approval_status"] != "approved":
                    self._block_execution(record, now, "missing_human_approval")
                elif not metadata_only:
                    self._block_execution(record, now, "zero_write_policy_requires_metadata_only")
                else:
                    record["status"] = "executing"
                    record["timeline"].append(self._event(now, "execution.started", "Metadata-only execution started."))
                    record["execution_logs"].append(self._log(now, "info", "Planner selected metadata-only execution."))
                    complete_at = utc_now()
                    record["status"] = "completed"
                    record["response"] = f"metadata_only_completed_for_{record['reply_to_sender']}"
                    record["pipeline"] = self._pipeline("completed", False)
                    record["timeline"].append(self._event(complete_at, "execution.completed", "Metadata output record created in command state only."))
                    record["execution_logs"].append(self._log(complete_at, "info", "No provider call, deployment, or file generation was performed."))
                    record["outputs"] = [
                        {"kind": "metadata", "name": f"{record['request_type']}_execution_metadata", "status": "created"},
                        {"kind": "result", "name": record["response"], "status": "completed"},
                        {"kind": "log", "name": "audit_trace", "status": "recorded"},
                    ]
                result = dict(record)
                return

        self._commands.update([], mutate)
        if result is not None:
            append_audit_event(
                "creator.execution_attempted",
                "operator",
                {"id": command_id, "status": result["status"], "response": result["response"]},
                risk=result["governance"]["risk_level"],
            )
        return result

    def list_commands(self, limit: int = 50) -> list[dict]:
        return [self._normalize_record(record) for record in self._commands.read([])[-limit:]]

    def _normalize_record(self, record: dict) -> dict:
        normalized = dict(record)
        normalized.setdefault("request_type", self._request_type(normalized))
        normalized.setdefault("plan", self._plan(normalized["request_type"], normalized.get("governance", {}).get("risk_level", "low")))
        normalized.setdefault("execution_logs", [])
        normalized.setdefault("timeline", [])
        normalized.setdefault("outputs", [])
        normalized.setdefault("response", "provider_disabled_by_governance")
        if normalized["response"] == "provider_disabled_by_governance":
            normalized["response"] = "blocked_provider_disabled"
        normalized.setdefault("governance", {})
        normalized["governance"].setdefault("risk_level", self._risk_level(normalized))
        normalized["governance"].setdefault("blocked_reason", None if normalized.get("status") in {"awaiting_approval", "approved", "completed"} else normalized["response"])
        normalized["governance"].setdefault("required_permissions", ["human_approval", "metadata_only=true", "zero_write_policy"])
        normalized["governance"].setdefault("provider_status", "disabled")
        normalized["governance"].setdefault(
            "approval_status",
            "approved" if normalized.get("status") in {"approved", "completed"} else "pending" if normalized.get("status") == "awaiting_approval" else "not_required",
        )
        normalized["pipeline"] = self._pipeline(normalized.get("status", "blocked"), normalized["response"] == "blocked_provider_disabled")
        return normalized

    def _block_execution(self, record: dict, now: str, reason: str) -> None:
        record["status"] = "blocked"
        record["response"] = reason
        record["governance"]["blocked_reason"] = reason
        record["pipeline"] = self._pipeline("blocked", reason == "blocked_provider_disabled")
        record["timeline"].append(self._event(now, "execution.blocked", reason))
        record["execution_logs"].append(self._log(now, "warning", reason))
        record["outputs"] = [
            {"kind": "metadata", "name": "execution_metadata", "status": "not_created"},
            {"kind": "result", "name": reason, "status": "blocked"},
        ]

    def _pipeline(self, status: str, provider_blocked: bool) -> list[dict]:
        labels = {
            "received": "Received",
            "governance_check": "Governance check",
            "awaiting_approval": "Awaiting approval",
            "approved": "Approved",
            "executing": "Executing",
            "completed": "Completed",
            "blocked": "Blocked",
            "failed": "Failed",
        }
        details = {
            "received": "Command accepted into the controlled console.",
            "governance_check": "Request classified and checked against safety gates.",
            "awaiting_approval": "Human approval is required before execution.",
            "approved": "Human approval is recorded for metadata-only execution.",
            "executing": "Metadata-only execution is in progress.",
            "completed": "Metadata-only execution completed without autonomous writes.",
            "blocked": "Provider execution is disabled by governance." if provider_blocked else "Execution is blocked by governance.",
            "failed": "Execution failed before completion.",
        }
        return [{"status": item, "label": labels[item], "detail": details[item]} for item in COMMAND_STATUSES]

    def _request_type(self, payload: dict) -> str:
        text = f"{payload.get('command', '')} {payload.get('details', '')}".lower()
        mapping = {
            "integration": ["integration", "connect", "webhook"],
            "document": ["document", "report", "policy", "readme"],
            "workflow": ["workflow", "process", "approval flow"],
            "api": ["api", "endpoint", "route"],
            "app": ["app", "dashboard", "console", "frontend"],
            "module": ["module", "component", "package"],
        }
        for request_type, markers in mapping.items():
            if any(marker in text for marker in markers):
                return request_type
        return "module"

    def _risk_level(self, payload: dict) -> str:
        text = f"{payload.get('command', '')} {payload.get('details', '')}".lower()
        if any(word in text for word in ["delete", "secret", "payment", "production database", "drop"]):
            return "critical"
        if any(word in text for word in ["deploy", "database", "migration", "credential", "production"]):
            return "high"
        if any(word in text for word in ["write", "create", "generate", "execute", "build"]):
            return "medium"
        return "low"

    def _requires_provider(self, payload: dict) -> bool:
        text = f"{payload.get('command', '')} {payload.get('details', '')}".lower()
        if any(marker in text for marker in ["no external ai", "no provider", "do not call external ai", "without provider"]):
            return False
        return any(marker in text for marker in ["use ai", "provider", "openai", "external ai", "llm"])

    def _plan(self, request_type: str, risk_level: str) -> list[str]:
        return [
            f"classify_request_type:{request_type}",
            f"classify_risk:{risk_level}",
            "require_human_approval",
            "execute_metadata_only",
            "record_audit_trace",
            "reply_to_original_sender",
        ]

    def _event(self, timestamp: str, event: str, detail: str) -> dict:
        return {"timestamp": timestamp, "event": event, "detail": detail}

    def _log(self, timestamp: str, level: str, message: str) -> dict:
        return {"timestamp": timestamp, "level": level, "message": message}


creator_service = CreatorService()
