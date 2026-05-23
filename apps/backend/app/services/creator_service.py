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
        self._capabilities = store("creator_capability_requests")
        self._capability_consumptions = store("creator_capability_consumptions")

    def console_state(self, limit: int = 50) -> dict:
        return {
            "mode": "controlled_execution_engine",
            "provider_state": "provider_disabled_by_governance",
            "command_statuses": COMMAND_STATUSES,
            "commands": self.list_commands(limit),
            "outputs": self.list_outputs(limit=100),
            "capability_requests": self.list_capability_requests(limit=100),
            "approved_capabilities": self.list_approved_capabilities(limit=100),
            "capability_consumptions": self.list_capability_consumptions(limit=100),
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

    def create_capability_request(self, payload: dict) -> dict:
        now = utc_now()
        reply_to = self._capability_reply_target(payload["sender"])
        requirements = [
            {
                "id": str(uuid.uuid4()),
                "kind": item["kind"],
                "characteristics": item.get("characteristics", []),
                "reason": item["reason"],
                "priority": item.get("priority", "medium"),
            }
            for item in payload["requirements"]
        ]
        record = {
            "id": str(uuid.uuid4()),
            "timestamp": now,
            "sender": payload["sender"],
            "reply_to": reply_to,
            "related_command_id": payload.get("related_command_id"),
            "objective": payload["objective"],
            "explanation": payload["explanation"],
            "status": "pending",
            "response": f"capability_request_pending_for_{reply_to}",
            "requirements": requirements,
            "governance": self._capability_governance("pending"),
            "timeline": [
                self._event(now, "capability.requested", f"Capability request created by {payload['sender']}."),
                self._event(now, "capability.governance_checked", "FORJA requested technical capability only; provider, cost, and strategy decisions remain external."),
                self._event(now, "capability.awaiting_decision", f"Awaiting authorization from {reply_to}."),
            ],
            "approved_metadata": None,
        }
        self._capabilities.update([], lambda records: records.append(record))
        append_audit_event(
            "creator.capability_requested",
            payload["sender"],
            {"id": record["id"], "reply_to": reply_to, "requirements": [item["kind"] for item in requirements]},
            risk="medium",
        )
        return self._normalize_capability_request(record)

    def list_capability_requests(self, sender: str | None = None, status: str | None = None, limit: int = 100) -> list[dict]:
        records = [self._normalize_capability_request(record) for record in self._capabilities.read([])]
        if sender:
            records = [record for record in records if record["sender"] == sender]
        if status:
            records = [record for record in records if record["status"] == status]
        return records[-limit:]

    def decide_capability_request(self, request_id: str, decision: str, reason: str) -> dict | None:
        result: dict | None = None
        now = utc_now()

        def mutate(records: list[dict]) -> None:
            nonlocal result
            for record in records:
                if record["id"] != request_id:
                    continue
                normalized = self._normalize_capability_request(record)
                record.clear()
                record.update(normalized)
                record["status"] = decision
                record["response"] = f"capability_request_{decision}_for_{record['reply_to']}"
                record["governance"] = self._capability_governance(decision)
                record["timeline"].append(self._event(now, f"capability.{decision}", reason or f"Capability request {decision}."))
                result = self._normalize_capability_request(record)
                return

        self._capabilities.update([], mutate)
        if result is not None:
            append_audit_event(
                "creator.capability_decision",
                "operator",
                {"id": request_id, "decision": decision, "reply_to": result["reply_to"]},
                risk="medium",
            )
        return result

    def attach_capability_metadata(self, request_id: str, metadata: dict) -> tuple[dict | None, str | None]:
        result: dict | None = None
        error: str | None = None
        now = utc_now()

        def mutate(records: list[dict]) -> None:
            nonlocal result, error
            for record in records:
                if record["id"] != request_id:
                    continue
                normalized = self._normalize_capability_request(record)
                record.clear()
                record.update(normalized)
                if record["status"] != "approved":
                    error = "capability_request_not_approved"
                    result = self._normalize_capability_request(record)
                    return
                if self._metadata_has_forbidden_keys(metadata):
                    record["status"] = "unavailable"
                    record["response"] = f"capability_metadata_rejected_by_governance_for_{record['reply_to']}"
                    record["governance"] = self._capability_governance("unavailable")
                    record["timeline"].append(
                        self._event(now, "capability.metadata_blocked", "Metadata included provider, secret, cost, or strategy fields that FORJA cannot decide.")
                    )
                else:
                    record["approved_metadata"] = {
                        "metadata_only": True,
                        "provider_selected": False,
                        "api_consumption_enabled": False,
                        **metadata,
                    }
                    record["response"] = f"capability_metadata_attached_for_{record['reply_to']}"
                    record["timeline"].append(self._event(now, "capability.metadata_attached", "Approved capability metadata attached without provider selection or API consumption."))
                result = self._normalize_capability_request(record)
                return

        self._capabilities.update([], mutate)
        if result is not None and error is None:
            append_audit_event(
                "creator.capability_metadata_attached",
                "operator",
                {"id": request_id, "status": result["status"], "reply_to": result["reply_to"]},
                risk="medium",
            )
        return result, error

    def consume_capability(self, request_id: str, payload: dict) -> dict | None:
        capability = self.get_capability_request(request_id)
        if capability is None:
            return None
        now = utc_now()
        sender = payload.get("sender", capability["sender"])
        failure_reason = self._capability_consumption_blocker(capability, payload)
        if failure_reason:
            record = self._make_capability_consumption(
                capability,
                payload,
                sender=sender,
                status="blocked",
                response=f"capability_consumption_blocked_for_{capability['reply_to']}",
                failure_reason=failure_reason,
                provider_status="not_bound",
                usage_metadata={},
                cost_metadata=self._default_cost_metadata(),
                provider_response_metadata={},
                result_metadata={"safe_mode": True, "executed": False},
                created_at=now,
            )
            record["timeline"].append(self._event(now, "capability.consumption_blocked", failure_reason))
        else:
            usage_metadata = self._sanitize_consumption_metadata(payload.get("usage_metadata", {}))
            cost_metadata = self._normalize_cost_metadata(payload.get("cost_metadata", {}))
            provider_response_metadata = self._sanitize_consumption_metadata(payload.get("provider_response_metadata", {}))
            result_metadata = self._sanitize_consumption_metadata(payload.get("result_metadata", {}))
            provider_status = "provider_response_metadata_registered" if provider_response_metadata else "approved_metadata_only"
            record = self._make_capability_consumption(
                capability,
                payload,
                sender=sender,
                status="completed",
                response=f"capability_consumption_completed_for_{capability['reply_to']}",
                failure_reason=None,
                provider_status=provider_status,
                usage_metadata=usage_metadata,
                cost_metadata=cost_metadata,
                provider_response_metadata=provider_response_metadata,
                result_metadata={
                    "safe_mode": True,
                    "executed": True,
                    "external_api_called": False,
                    **result_metadata,
                },
                created_at=now,
            )
            record["timeline"].extend(
                [
                    self._event(now, "capability.wrapper_started", "Provider-safe wrapper started in safe metadata mode."),
                    self._event(now, "capability.usage_registered", "Usage metadata registered without autonomous loop."),
                    self._event(now, "capability.cost_registered", "Cost metadata registered explicitly; no hidden costs inferred."),
                    self._event(now, "capability.consumption_completed", "Approved capability consumed in safe mode without direct API call."),
                ]
            )
        self._capability_consumptions.update([], lambda records: records.append(record))
        append_audit_event(
            "creator.capability_consumed",
            sender,
            {
                "id": record["id"],
                "capability_request_id": request_id,
                "status": record["status"],
                "response": record["response"],
                "external_api_called": record["external_api_called"],
            },
            risk="medium",
        )
        return self._normalize_capability_consumption(record)

    def list_approved_capabilities(self, limit: int = 100) -> list[dict]:
        approved = [
            record
            for record in self.list_capability_requests(limit=1000)
            if record["status"] == "approved" and record.get("approved_metadata") is not None
        ]
        return approved[-limit:]

    def get_capability_request(self, request_id: str) -> dict | None:
        for record in self._capabilities.read([]):
            normalized = self._normalize_capability_request(record)
            if normalized["id"] == request_id:
                return normalized
        return None

    def list_capability_consumptions(self, capability_request_id: str | None = None, limit: int = 100) -> list[dict]:
        records = [self._normalize_capability_consumption(record) for record in self._capability_consumptions.read([])]
        if capability_request_id:
            records = [record for record in records if record["capability_request_id"] == capability_request_id]
        return records[-limit:]

    def get_capability_consumption(self, consumption_id: str) -> dict | None:
        for record in self._capability_consumptions.read([]):
            normalized = self._normalize_capability_consumption(record)
            if normalized["id"] == consumption_id:
                return normalized
        return None

    def register_capability_execution(self, consumption_id: str, metadata: dict) -> dict | None:
        return self._update_capability_consumption_metadata(consumption_id, "execution", metadata)

    def register_capability_usage(self, consumption_id: str, metadata: dict) -> dict | None:
        return self._update_capability_consumption_metadata(consumption_id, "usage", metadata)

    def register_capability_cost(self, consumption_id: str, metadata: dict) -> dict | None:
        return self._update_capability_consumption_metadata(consumption_id, "cost", metadata)

    def register_capability_provider_response(self, consumption_id: str, metadata: dict) -> dict | None:
        return self._update_capability_consumption_metadata(consumption_id, "provider_response", metadata)

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

    def _normalize_capability_request(self, record: dict) -> dict:
        normalized = dict(record)
        normalized.setdefault("id", str(uuid.uuid4()))
        normalized.setdefault("timestamp", utc_now())
        normalized.setdefault("sender", "system")
        if normalized["sender"] not in {"user", "cerebro", "seo", "system"}:
            normalized["sender"] = "system"
        normalized.setdefault("reply_to", self._capability_reply_target(normalized["sender"]))
        if normalized["reply_to"] not in {"ceo", "cerebro", "seo", "system"}:
            normalized["reply_to"] = self._capability_reply_target(normalized["sender"])
        normalized.setdefault("related_command_id", None)
        normalized.setdefault("objective", "Capability request")
        normalized.setdefault("explanation", "FORJA detected a technical capability requirement.")
        normalized.setdefault("status", "pending")
        normalized.setdefault("response", f"capability_request_{normalized['status']}_for_{normalized['reply_to']}")
        normalized["requirements"] = [
            {
                "id": item.get("id", str(uuid.uuid4())),
                "kind": item.get("kind", "other"),
                "characteristics": item.get("characteristics", []),
                "reason": item.get("reason", "Capability required for advanced task execution."),
                "priority": item.get("priority", "medium"),
            }
            for item in normalized.get("requirements", [])
        ]
        normalized.setdefault("governance", self._capability_governance(normalized["status"]))
        normalized["governance"].setdefault("forja_role", "technical_capability_requester_only")
        normalized["governance"].setdefault("provider_decision_owner", ["ceo", "cerebro"])
        normalized["governance"].setdefault("forbidden_actions", ["provider_selection", "cost_decision", "strategy_decision", "api_consumption"])
        normalized.setdefault("timeline", [])
        normalized.setdefault("approved_metadata", None)
        return normalized

    def _capability_reply_target(self, sender: str) -> str:
        if sender == "user":
            return "ceo"
        if sender == "cerebro":
            return "cerebro"
        if sender == "seo":
            return "seo"
        return "system"

    def _capability_governance(self, status: str) -> dict:
        return {
            "status": status,
            "forja_role": "technical_capability_requester_only",
            "provider_decision_owner": ["ceo", "cerebro"],
            "cost_decision_owner": ["ceo", "cerebro"],
            "strategy_decision_owner": ["ceo", "cerebro"],
            "forbidden_actions": ["provider_selection", "cost_decision", "strategy_decision", "api_consumption", "secret_collection"],
            "external_api_calls_enabled": False,
            "requires_authorization": status == "pending",
        }

    def _metadata_has_forbidden_keys(self, value: Any) -> bool:
        forbidden = ["provider", "api_key", "token", "secret", "cost", "price", "billing", "strategy"]
        if isinstance(value, dict):
            for key, nested in value.items():
                if any(marker in str(key).lower() for marker in forbidden):
                    return True
                if self._metadata_has_forbidden_keys(nested):
                    return True
        if isinstance(value, list):
            return any(self._metadata_has_forbidden_keys(item) for item in value)
        return False

    def _capability_consumption_blocker(self, capability: dict, payload: dict) -> str | None:
        if capability["status"] != "approved":
            return "capability_not_approved"
        if capability.get("approved_metadata") is None:
            return "approved_capability_metadata_missing"
        if payload.get("manual_approval") is not True:
            return "missing_manual_consumption_approval"
        for key in ["usage_metadata", "cost_metadata", "provider_response_metadata", "result_metadata"]:
            if self._metadata_has_secret_keys(payload.get(key, {})):
                return "metadata_contains_secret_or_token"
        if self._provider_response_has_fake_provider(payload.get("provider_response_metadata", {})):
            return "provider_identity_not_allowed_in_safe_mode"
        return None

    def _make_capability_consumption(
        self,
        capability: dict,
        payload: dict,
        *,
        sender: str,
        status: str,
        response: str,
        failure_reason: str | None,
        provider_status: str,
        usage_metadata: dict,
        cost_metadata: dict,
        provider_response_metadata: dict,
        result_metadata: dict,
        created_at: str,
    ) -> dict:
        return {
            "id": str(uuid.uuid4()),
            "capability_request_id": capability["id"],
            "timestamp": created_at,
            "sender": sender if sender in {"user", "cerebro", "seo", "system"} else capability["sender"],
            "reply_to": capability["reply_to"],
            "task": payload.get("task", capability["objective"]),
            "status": status,
            "response": response,
            "failure_reason": failure_reason,
            "manual_approval": payload.get("manual_approval") is True,
            "execution_mode": "safe_metadata",
            "provider_status": provider_status,
            "external_api_called": False,
            "usage_metadata": usage_metadata,
            "cost_metadata": cost_metadata,
            "provider_response_metadata": provider_response_metadata,
            "result_metadata": result_metadata,
            "governance": self._capability_consumption_governance(status),
            "timeline": [
                self._event(created_at, "capability.consumption_requested", f"Safe-mode consumption requested by {sender}."),
                self._event(created_at, "capability.consumption_governance_checked", "Manual approval, approved capability metadata, and secret boundaries evaluated."),
            ],
        }

    def _normalize_capability_consumption(self, record: dict) -> dict:
        normalized = dict(record)
        normalized.setdefault("id", str(uuid.uuid4()))
        normalized.setdefault("capability_request_id", "")
        normalized.setdefault("timestamp", utc_now())
        normalized.setdefault("sender", "system")
        if normalized["sender"] not in {"user", "cerebro", "seo", "system"}:
            normalized["sender"] = "system"
        normalized.setdefault("reply_to", self._capability_reply_target(normalized["sender"]))
        if normalized["reply_to"] not in {"ceo", "cerebro", "seo", "system"}:
            normalized["reply_to"] = self._capability_reply_target(normalized["sender"])
        normalized.setdefault("task", "Capability consumption")
        normalized.setdefault("status", "blocked")
        normalized.setdefault("response", f"capability_consumption_{normalized['status']}_for_{normalized['reply_to']}")
        normalized.setdefault("failure_reason", None)
        normalized.setdefault("manual_approval", False)
        normalized.setdefault("execution_mode", "safe_metadata")
        normalized.setdefault("provider_status", "not_bound")
        normalized.setdefault("external_api_called", False)
        normalized.setdefault("usage_metadata", {})
        normalized.setdefault("cost_metadata", self._default_cost_metadata())
        normalized.setdefault("provider_response_metadata", {})
        normalized.setdefault("result_metadata", {})
        normalized.setdefault("governance", self._capability_consumption_governance(normalized["status"]))
        normalized.setdefault("timeline", [])
        return normalized

    def _update_capability_consumption_metadata(self, consumption_id: str, section: str, metadata: dict) -> dict | None:
        result: dict | None = None
        now = utc_now()

        def mutate(records: list[dict]) -> None:
            nonlocal result
            for record in records:
                if record.get("id") != consumption_id:
                    continue
                normalized = self._normalize_capability_consumption(record)
                record.clear()
                record.update(normalized)
                if self._metadata_has_secret_keys(metadata):
                    record["status"] = "failed"
                    record["failure_reason"] = "metadata_contains_secret_or_token"
                    record["provider_status"] = "failed_metadata_registered"
                    record["timeline"].append(self._event(now, f"capability.{section}_metadata_blocked", "Metadata contained secret-like fields and was blocked."))
                elif section == "provider_response" and self._provider_response_has_fake_provider(metadata):
                    record["status"] = "failed"
                    record["failure_reason"] = "provider_identity_not_allowed_in_safe_mode"
                    record["provider_status"] = "failed_metadata_registered"
                    record["timeline"].append(self._event(now, "capability.provider_response_blocked", "Provider identity fields are not accepted in safe mode."))
                elif section == "usage":
                    record["usage_metadata"] = {**record["usage_metadata"], **self._sanitize_consumption_metadata(metadata)}
                    record["timeline"].append(self._event(now, "capability.usage_metadata_registered", "Usage metadata registered."))
                elif section == "cost":
                    record["cost_metadata"] = self._normalize_cost_metadata({**record["cost_metadata"], **metadata})
                    record["timeline"].append(self._event(now, "capability.cost_metadata_registered", "Cost metadata registered explicitly."))
                elif section == "provider_response":
                    record["provider_response_metadata"] = {**record["provider_response_metadata"], **self._sanitize_consumption_metadata(metadata)}
                    record["provider_status"] = "provider_response_metadata_registered"
                    record["timeline"].append(self._event(now, "capability.provider_response_metadata_registered", "Provider response metadata registered without storing secrets."))
                else:
                    record["result_metadata"] = {**record["result_metadata"], **self._sanitize_consumption_metadata(metadata)}
                    record["timeline"].append(self._event(now, "capability.execution_metadata_registered", "Execution/result metadata registered."))
                result = self._normalize_capability_consumption(record)
                return

        self._capability_consumptions.update([], mutate)
        if result is not None:
            append_audit_event(
                f"creator.capability_{section}_registered",
                "operator",
                {"id": consumption_id, "status": result["status"], "provider_status": result["provider_status"]},
                risk="medium",
            )
        return result

    def _capability_consumption_governance(self, status: str) -> dict:
        return {
            "status": status,
            "safe_mode": True,
            "manual_approval_required": True,
            "autonomous_loops_allowed": False,
            "dangerous_calls_allowed": False,
            "external_api_call_performed": False,
            "secret_storage_allowed": False,
            "provider_selection_allowed": False,
        }

    def _default_cost_metadata(self) -> dict:
        return {
            "reported": False,
            "amount": None,
            "currency": None,
            "units": None,
            "note": "No cost metadata registered. FORJA did not infer hidden costs.",
        }

    def _normalize_cost_metadata(self, metadata: dict) -> dict:
        if self._metadata_has_secret_keys(metadata):
            return {**self._default_cost_metadata(), "blocked_reason": "metadata_contains_secret_or_token"}
        return {
            "reported": bool(metadata),
            "amount": metadata.get("amount"),
            "currency": metadata.get("currency"),
            "units": metadata.get("units"),
            "note": metadata.get("note", "Cost metadata explicitly registered by operator." if metadata else "No cost metadata registered. FORJA did not infer hidden costs."),
        }

    def _sanitize_consumption_metadata(self, metadata: dict) -> dict:
        if not isinstance(metadata, dict):
            return {}
        return {key: value for key, value in metadata.items() if not self._metadata_has_secret_keys({key: value})}

    def _metadata_has_secret_keys(self, value: Any) -> bool:
        forbidden = ["api_key", "apikey", "token", "secret", "password", "credential", "private_key"]
        if isinstance(value, dict):
            for key, nested in value.items():
                if any(marker in str(key).lower() for marker in forbidden):
                    return True
                if self._metadata_has_secret_keys(nested):
                    return True
        if isinstance(value, list):
            return any(self._metadata_has_secret_keys(item) for item in value)
        return False

    def _provider_response_has_fake_provider(self, metadata: dict) -> bool:
        if not isinstance(metadata, dict):
            return False
        forbidden = ["provider", "model", "api_key", "token", "secret"]
        return any(any(marker == str(key).lower() or marker in str(key).lower() for marker in forbidden) for key in metadata)

    def _event(self, timestamp: str, event: str, detail: str) -> dict:
        return {"timestamp": timestamp, "event": event, "detail": detail}

    def _log(self, timestamp: str, level: str, message: str) -> dict:
        return {"timestamp": timestamp, "level": level, "message": message}


creator_service = CreatorService()
