from __future__ import annotations

import uuid
from typing import Any

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

OUTPUT_TYPE_BY_REQUEST = {
    "app": "proposed_app_structure",
    "api": "api_blueprint",
    "module": "module_plan",
    "workflow": "workflow_plan",
    "document": "document_blueprint",
    "integration": "integration_plan",
}


class CreatorService:
    def __init__(self) -> None:
        self._commands = store("creator_commands")

    def console_state(self, limit: int = 50) -> dict:
        return {
            "mode": "controlled_execution_engine",
            "provider_state": "provider_disabled_by_governance",
            "command_statuses": COMMAND_STATUSES,
            "commands": self.list_commands(limit),
            "outputs": self.list_outputs(limit=100),
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
            "outputs": [],
        }
        if requires_provider:
            record["timeline"].append(self._event(now, "execution.blocked", "Provider execution is disabled by governance."))
            record["outputs"].append(self._blocked_output(record, "blocked_provider_disabled", now))
        else:
            record["timeline"].append(self._event(now, "approval.required", "Human approval is required before metadata-only execution."))
            record["outputs"].append(self._execution_summary_output(record, "awaiting_approval", now))
        self._commands.update([], lambda records: records.append(record))
        append_audit_event(
            "creator.command_created",
            payload["sender"],
            {"id": record["id"], "reply_to_sender": record["reply_to_sender"], "status": status, "request_type": request_type},
            risk=risk_level,
        )
        return self._normalize_record(record)

    def decide_command(self, command_id: str, decision: str, reason: str) -> dict | None:
        result: dict | None = None
        now = utc_now()

        def mutate(records: list[dict]) -> None:
            nonlocal result
            for record in records:
                if record["id"] != command_id:
                    continue
                self._prepare_record_for_mutation(record)
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
                    record["outputs"].append(self._blocked_output(record, "rejected_by_human_governance", now))
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
                result = self._normalize_record(record)
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
                self._prepare_record_for_mutation(record)
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
                    record["timeline"].append(self._event(complete_at, "execution.completed", "Metadata-only output records created in command state only."))
                    record["execution_logs"].append(self._log(complete_at, "info", "No provider call, deployment, source code, or file generation was performed."))
                    record["outputs"].append(self._typed_metadata_output(record, complete_at))
                    record["outputs"].append(self._execution_summary_output(record, "completed", complete_at))
                result = self._normalize_record(record)
                return

        self._commands.update([], mutate)
        if result is not None:
            append_audit_event(
                "creator.execution_attempted",
                "operator",
                {"id": command_id, "status": result["status"], "response": result["response"], "outputs": len(result["outputs"])},
                risk=result["governance"]["risk_level"],
            )
        return result

    def associate_output(self, command_id: str, payload: dict) -> dict | None:
        result: dict | None = None
        now = utc_now()

        def mutate(records: list[dict]) -> None:
            nonlocal result
            for record in records:
                if record["id"] != command_id:
                    continue
                self._prepare_record_for_mutation(record)
                output = self._make_output(
                    record,
                    output_type=payload["output_type"],
                    kind=self._kind_for_output_type(payload["output_type"]),
                    name=payload["output_type"],
                    title=payload["title"],
                    status=payload["status"],
                    summary=f"metadata_only_output: {payload['summary']}",
                    produced=["associated_metadata_record"],
                    not_produced=self._not_produced(),
                    blocked=["autonomous_write", "provider_execution"],
                    content={
                        "associated_by": "operator",
                        "request_id": record["id"],
                        "metadata_only": True,
                        **payload.get("content", {}),
                    },
                    created_at=now,
                )
                record["outputs"].append(output)
                record["timeline"].append(self._event(now, "output.associated", f"Associated metadata output {output['output_type']} with request."))
                record["execution_logs"].append(self._log(now, "info", f"Output associated: {output['id']}"))
                result = output
                return

        self._commands.update([], mutate)
        if result is not None:
            append_audit_event(
                "creator.output_associated",
                "operator",
                {"id": command_id, "output_id": result["id"], "output_type": result["output_type"]},
                risk="low",
            )
        return result

    def list_commands(self, limit: int = 50) -> list[dict]:
        return [self._normalize_record(record) for record in self._commands.read([])[-limit:]]

    def list_outputs(self, sender: str | None = None, command_id: str | None = None, limit: int = 100) -> list[dict]:
        outputs: list[dict] = []
        for record in self._commands.read([]):
            normalized = self._normalize_record(record)
            if command_id and normalized["id"] != command_id:
                continue
            for output in normalized["outputs"]:
                if sender and output["sender"] != sender:
                    continue
                outputs.append(output)
        return outputs[-limit:]

    def get_output(self, output_id: str) -> dict | None:
        for output in self.list_outputs(limit=1000):
            if output["id"] == output_id:
                return output
        return None

    def command_outputs(self, command_id: str) -> list[dict] | None:
        for record in self._commands.read([]):
            normalized = self._normalize_record(record)
            if normalized["id"] == command_id:
                return normalized["outputs"]
        return None

    def _prepare_record_for_mutation(self, record: dict) -> None:
        normalized = self._normalize_record(record)
        record.clear()
        record.update(normalized)

    def _normalize_record(self, record: dict) -> dict:
        normalized = dict(record)
        normalized.setdefault("sender", "user")
        if normalized["sender"] not in {"user", "cerebro", "seo", "system"}:
            normalized["sender"] = "system"
        normalized.setdefault("reply_to_sender", normalized["sender"])
        if normalized["reply_to_sender"] not in {"user", "cerebro", "seo", "system"}:
            normalized["reply_to_sender"] = normalized["sender"]
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
        normalized["outputs"] = [self._normalize_output(normalized, output, index) for index, output in enumerate(normalized["outputs"])]
        return normalized

    def _normalize_output(self, record: dict, output: dict, index: int) -> dict:
        if output.get("id") and output.get("output_type"):
            normalized = dict(output)
            normalized.setdefault("request_id", record["id"])
            normalized.setdefault("sender", record["sender"])
            normalized.setdefault("mode", "metadata_only_output")
            normalized.setdefault("summary", "metadata_only_output")
            normalized.setdefault("produced", [])
            normalized.setdefault("not_produced", self._not_produced())
            normalized.setdefault("blocked", [])
            normalized.setdefault("content", {})
            normalized.setdefault("downloadable", True)
            normalized.setdefault("created_at", record.get("timestamp", utc_now()))
            normalized.setdefault("title", normalized.get("name", normalized["output_type"]))
            return normalized

        name = str(output.get("name", "execution_metadata"))
        status = str(output.get("status", record.get("status", "not_created")))
        output_type = self._infer_legacy_output_type(record, output)
        return self._make_output(
            record,
            output_type=output_type,
            kind=output.get("kind", self._kind_for_output_type(output_type)),
            name=name,
            title=name.replace("_", " ").title(),
            status=status,
            summary=f"metadata_only_output: legacy output record normalized from {name}.",
            produced=["legacy_metadata_record"] if status not in {"not_created", "blocked"} else [],
            not_produced=self._not_produced(),
            blocked=[name] if record.get("status") == "blocked" else [],
            content={
                "legacy": True,
                "request_id": record["id"],
                "request_type": record["request_type"],
                "original": output,
            },
            created_at=record.get("timestamp", utc_now()),
            output_id=f"legacy-{record['id']}-{index}",
        )

    def _block_execution(self, record: dict, now: str, reason: str) -> None:
        record["status"] = "blocked"
        record["response"] = reason
        record["governance"]["blocked_reason"] = reason
        record["pipeline"] = self._pipeline("blocked", reason == "blocked_provider_disabled")
        record["timeline"].append(self._event(now, "execution.blocked", reason))
        record["execution_logs"].append(self._log(now, "warning", reason))
        record["outputs"].append(self._blocked_output(record, reason, now))

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
            "register_artifacts",
            "reply_to_original_sender",
        ]

    def _typed_metadata_output(self, record: dict, created_at: str) -> dict:
        output_type = OUTPUT_TYPE_BY_REQUEST[record["request_type"]]
        proposed_structure = self._proposed_structure(record["request_type"])
        return self._make_output(
            record,
            output_type=output_type,
            kind=self._kind_for_output_type(output_type),
            name=output_type,
            title=self._title_for_output_type(output_type),
            status="created",
            summary=(
                "metadata_only_output: FORJA produced a controlled proposal artifact only. "
                "No source code, deployable app, external provider result, or file artifact was generated."
            ),
            produced=["request_classification", "governance_snapshot", "proposed_structure", "execution_metadata"],
            not_produced=self._not_produced(),
            blocked=["autonomous_write", "provider_execution", "cloud_deploy"],
            content={
                "request": self._request_payload(record),
                "proposed_structure": proposed_structure,
                "execution_policy": self._execution_policy(),
                "result": "metadata_only_output",
            },
            created_at=created_at,
        )

    def _execution_summary_output(self, record: dict, status: str, created_at: str) -> dict:
        blocked = ["metadata_execution_until_human_approval"] if status == "awaiting_approval" else ["autonomous_write", "provider_execution"]
        produced = ["request_classification", "governance_snapshot", "execution_plan"]
        if status == "completed":
            produced.append("artifact_registry_entry")
        return self._make_output(
            record,
            output_type="execution_summary",
            kind="summary",
            name="execution_summary",
            title="Execution Summary",
            status=status,
            summary=f"metadata_only_output: request is {status}. FORJA did not generate real code or files.",
            produced=produced,
            not_produced=self._not_produced(),
            blocked=blocked,
            content={
                "request": self._request_payload(record),
                "pipeline_status": status,
                "timeline_events": [event["event"] for event in record.get("timeline", [])],
                "execution_policy": self._execution_policy(),
            },
            created_at=created_at,
        )

    def _blocked_output(self, record: dict, reason: str, created_at: str) -> dict:
        return self._make_output(
            record,
            output_type="blocked_action_report",
            kind="report",
            name=reason,
            title="Blocked Action Report",
            status="blocked",
            summary=f"metadata_only_output: action blocked by governance. Reason: {reason}.",
            produced=["blocked_action_report", "governance_trace"],
            not_produced=self._not_produced(),
            blocked=[reason, "autonomous_write", "provider_execution"],
            content={
                "request": self._request_payload(record),
                "blocked_reason": reason,
                "governance": record.get("governance", {}),
                "execution_policy": self._execution_policy(),
            },
            created_at=created_at,
        )

    def _make_output(
        self,
        record: dict,
        *,
        output_type: str,
        kind: str,
        name: str,
        title: str,
        status: str,
        summary: str,
        produced: list[str],
        not_produced: list[str],
        blocked: list[str],
        content: dict[str, Any],
        created_at: str,
        output_id: str | None = None,
    ) -> dict:
        return {
            "id": output_id or str(uuid.uuid4()),
            "request_id": record["id"],
            "sender": record["sender"],
            "output_type": output_type,
            "kind": kind,
            "name": name,
            "title": title,
            "status": status,
            "mode": "metadata_only_output",
            "summary": summary,
            "produced": produced,
            "not_produced": not_produced,
            "blocked": blocked,
            "content": content,
            "downloadable": True,
            "created_at": created_at,
        }

    def _infer_legacy_output_type(self, record: dict, output: dict) -> str:
        name = str(output.get("name", "")).lower()
        status = str(output.get("status", "")).lower()
        if record.get("status") == "blocked" or "blocked" in name or status == "blocked":
            return "blocked_action_report"
        if "summary" in name or output.get("kind") == "result":
            return "execution_summary"
        return OUTPUT_TYPE_BY_REQUEST.get(record.get("request_type", "module"), "module_plan")

    def _kind_for_output_type(self, output_type: str) -> str:
        if output_type == "proposed_app_structure":
            return "structure"
        if output_type in {"api_blueprint", "document_blueprint"}:
            return "blueprint"
        if output_type in {"module_plan", "workflow_plan", "integration_plan"}:
            return "plan"
        if output_type == "blocked_action_report":
            return "report"
        return "summary"

    def _title_for_output_type(self, output_type: str) -> str:
        return output_type.replace("_", " ").title()

    def _proposed_structure(self, request_type: str) -> list[str]:
        structures = {
            "app": ["app_shell", "runtime_status_panel", "governance_gate", "output_manager", "audit_stream"],
            "api": ["route_contract", "request_schema", "response_schema", "governance_policy", "audit_event"],
            "module": ["module_boundary", "input_contract", "processing_steps", "result_metadata", "test_plan"],
            "workflow": ["trigger", "governance_check", "approval_gate", "metadata_execution", "audit_record"],
            "document": ["purpose", "audience", "sections", "control_notes", "review_gate"],
            "integration": ["source_system", "target_system", "data_contract", "security_boundary", "rollback_note"],
        }
        return structures.get(request_type, structures["module"])

    def _not_produced(self) -> list[str]:
        return ["source_code", "deployable_app", "files_on_disk", "external_provider_response", "production_change"]

    def _execution_policy(self) -> dict:
        return {
            "mode": "metadata_only_output",
            "zero_write_policy": True,
            "human_in_the_loop": True,
            "provider_execution": "disabled_by_governance",
            "autonomous_writes": "blocked",
        }

    def _request_payload(self, record: dict) -> dict:
        return {
            "id": record["id"],
            "sender": record["sender"],
            "reply_to_sender": record["reply_to_sender"],
            "request_type": record["request_type"],
            "command": record["command"],
            "status": record["status"],
            "response": record["response"],
        }

    def _event(self, timestamp: str, event: str, detail: str) -> dict:
        return {"timestamp": timestamp, "event": event, "detail": detail}

    def _log(self, timestamp: str, level: str, message: str) -> dict:
        return {"timestamp": timestamp, "level": level, "message": message}


creator_service = CreatorService()
