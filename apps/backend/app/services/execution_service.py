from __future__ import annotations

from pathlib import Path
from threading import RLock
import hashlib
import json
import uuid

from app.core.audit import append_audit_event, read_audit_events, utc_now
from app.core.config import settings
from app.core.storage import JsonStore, store
from app.services.blueprint_service import project_blueprint_service
from app.services.file_generation_service import SUPPORTED_TYPES, controlled_file_generator
from app.services.intent_parser import normalize_intent_input
from app.services.intent_service import intent_interpreter_service
from app.services.workspace_service import SAFE_REQUEST_ID, WorkspaceSecurityError, workspace_manager


ACTIVE_EXECUTION_STATES = {"pending", "interpreted", "blueprint_ready", "approved", "generating"}
GENERATING_STATES = {"generating"}
FINAL_EXECUTION_STATES = {"completed", "blocked", "failed", "duplicate_blocked"}


class GovernedExecutionError(ValueError):
    pass


class GovernedExecutionManager:
    def __init__(self, state_store: JsonStore | None = None, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or settings.base_dir
        self.workspace_root = self.base_dir / ".forja" / "workspaces"
        self._store = state_store or store("governed_executions")
        self._active_guard = RLock()
        self._active_requests: set[str] = set()
        self._active_workspaces: set[str] = set()

    def start(self, payload: dict) -> dict:
        raw_input = payload.get("input", "")
        sender = payload.get("sender", "ceo")
        recipient = payload.get("recipient", "forja")
        normalized_input = normalize_intent_input(raw_input)
        request_id = payload.get("source_request_id") or self._request_id(sender, normalized_input)
        idempotency_key = self._idempotency_key(sender, recipient, request_id)
        existing = self._find_by_request(request_id)
        if existing:
            duplicate = self._existing_or_duplicate(existing)
            if duplicate["state"] == "duplicate_blocked":
                return duplicate
            return existing

        if not self._try_lock_request(request_id):
            return self._parallel_block_record(sender, recipient, raw_input, normalized_input, request_id, idempotency_key)

        record = self._new_record(sender, recipient, raw_input, normalized_input, request_id, idempotency_key)
        self._save_record(record)
        append_audit_event(
            "execution_started",
            sender,
            {"execution_id": record["execution_id"], "request_id": request_id, "recipient": recipient},
            risk="low",
        )
        try:
            self._validate_request_id(request_id)
            record["timeline"].append(self._event("intent.received", "Human or Cerebro request received by governed execution."))
            interpretation = intent_interpreter_service.interpret({"sender": sender, "recipient": recipient, "input": raw_input})
            record.update(
                {
                    "state": "interpreted",
                    "interpretation": interpretation,
                    "response_target": interpretation["response_target"],
                    "request_type": interpretation["request_type"],
                    "domain": interpretation["domain"],
                    "risk_level": self._risk_level(interpretation),
                    "approval_required": interpretation["requires_approval"],
                    "approval_status": "requested" if interpretation["requires_approval"] else "not_required",
                    "updated_at": utc_now(),
                }
            )
            record["timeline"].append(self._event("intent.interpreted", "Intent interpretation completed under governance."))
            self._save_record(record)

            if interpretation["confidence"] <= 0.2:
                return self._block_validation(record)

            blueprint = project_blueprint_service.generate({"interpretation": interpretation, "source_request_id": request_id})
            record.update(
                {
                    "state": "blueprint_ready",
                    "blueprint": blueprint,
                    "project_name": blueprint["project_name"],
                    "risk_level": self._risk_level(interpretation, blueprint),
                    "approval_required": blueprint["risk_level"] in {"MEDIUM", "HIGH"} or bool(blueprint.get("approval_required")),
                    "updated_at": utc_now(),
                }
            )
            record["timeline"].append(self._event("blueprint.generated", "ProjectBlueprint generated and ready for governance."))
            self._save_record(record)

            risk_level = record["risk_level"]
            if risk_level == "HIGH":
                return self._block_high_risk(record)
            if risk_level == "MEDIUM":
                return self._request_approval(record)
            record["approval_status"] = "not_required"
            record["timeline"].append(self._event("approval.not_required", "Low risk execution can continue automatically."))
            return self._complete(record, manual_approval=False)
        except Exception as exc:
            return self._fail(record, str(exc))
        finally:
            self._unlock_request(request_id)

    def decide(self, execution_id: str, payload: dict) -> dict | None:
        record = self.get(execution_id)
        if not record:
            return None
        decision = payload.get("decision")
        decided_by = payload.get("decided_by", "ceo")
        high_risk_authorization = bool(payload.get("high_risk_authorization", False))

        if decision == "reject":
            record["state"] = "blocked"
            record["reason"] = "approval_rejected"
            record["approval_status"] = "rejected"
            record["updated_at"] = utc_now()
            record["timeline"].append(self._event("approval.rejected", "Human approval rejected; execution stopped before writes."))
            append_audit_event(
                "approval_rejected",
                decided_by,
                {"execution_id": execution_id, "request_id": record["request_id"]},
                risk=str(record.get("risk_level") or "LOW").lower(),
            )
            self._save_record(record)
            return self._with_audit_preview(record)

        if decision != "approve":
            raise GovernedExecutionError("unsupported_approval_decision")

        if record["state"] == "completed":
            return self._duplicate_record(record, "duplicate_execution_blocked")
        if record["state"] == "generating":
            return self._duplicate_record(record, "parallel_execution_blocked")
        if record["state"] not in {"awaiting_approval", "blocked"}:
            return self._with_audit_preview(record)
        if record["risk_level"] == "HIGH" and not high_risk_authorization:
            record["state"] = "blocked"
            record["reason"] = "high_risk_authorization_required"
            record["approval_status"] = "blocked"
            record["updated_at"] = utc_now()
            record["timeline"].append(self._event("approval.blocked", "High risk execution requires explicit high risk authorization."))
            self._save_record(record)
            return self._with_audit_preview(record)

        if not self._try_lock_request(record["request_id"]):
            return self._duplicate_record(record, "parallel_execution_blocked")
        try:
            record["state"] = "approved"
            record["reason"] = None
            record["approval_status"] = "approved"
            record["updated_at"] = utc_now()
            record["timeline"].append(self._event("approval.granted", "Human approval granted under governed execution."))
            append_audit_event(
                "approval_granted",
                decided_by,
                {"execution_id": execution_id, "request_id": record["request_id"], "high_risk_authorization": high_risk_authorization},
                risk=str(record.get("risk_level") or "LOW").lower(),
            )
            self._save_record(record)
            return self._complete(record, manual_approval=True)
        except Exception as exc:
            return self._fail(record, str(exc))
        finally:
            self._unlock_request(record["request_id"])

    def get(self, execution_id: str) -> dict | None:
        for record in self._records():
            if record["execution_id"] == execution_id:
                return self._with_audit_preview(record)
        return None

    def _complete(self, record: dict, manual_approval: bool) -> dict:
        request_id = record["request_id"]
        if not self._try_lock_workspace(request_id):
            return self._duplicate_record(record, "parallel_execution_blocked")
        try:
            record["state"] = "generating"
            record["updated_at"] = utc_now()
            record["timeline"].append(self._event("workspace.creation_started", "Workspace lock acquired; creating isolated workspace."))
            self._save_record(record)

            blueprint = record["blueprint"]
            workspace = workspace_manager.create_workspace(blueprint)
            record["workspace"] = workspace
            record["workspace_isolated"] = bool(workspace["workspace_isolated"])
            record["timeline"].append(self._event("workspace.created", "Workspace created inside .forja/workspaces."))
            self._save_record(record)

            generation = None
            if self._should_generate_files(blueprint):
                generation = controlled_file_generator.generate(blueprint, workspace, manual_approval=manual_approval)
                record["generation"] = generation
                if generation["status"] == "completed":
                    record["timeline"].append(self._event("files.generated", "Controlled project files generated inside workspace."))
                elif generation["status"] == "duplicate_blocked":
                    record["state"] = "duplicate_blocked"
                    record["reason"] = "duplicate_generation_blocked"
                    record["parallel_execution_blocked"] = True
                    record["timeline"].append(self._event("execution.duplicate_blocked", "File generation reported duplicate output."))
                    self._save_record(record)
                    return self._with_audit_preview(record)
                else:
                    record["state"] = "blocked"
                    record["reason"] = generation["reason"]
                    record["timeline"].append(self._event("execution.blocked", f"Generation blocked: {generation['reason']}."))
                    self._save_record(record)
                    return self._with_audit_preview(record)

            record["outputs"] = self._outputs(workspace, generation)
            record["state"] = "completed"
            record["reason"] = None
            record["updated_at"] = utc_now()
            record["timeline"].append(self._event("execution.completed", "Governed execution completed with outputs registered."))
            self._write_execution_record(workspace, record)
            self._save_record(record)
            append_audit_event(
                "execution_completed",
                record["sender"],
                {"execution_id": record["execution_id"], "request_id": request_id, "outputs": len(record["outputs"])},
                risk=str(record.get("risk_level") or "LOW").lower(),
            )
            return self._with_audit_preview(record)
        finally:
            self._unlock_workspace(request_id)

    def _request_approval(self, record: dict) -> dict:
        record["state"] = "awaiting_approval"
        record["reason"] = "manual_approval_required"
        record["approval_status"] = "requested"
        record["updated_at"] = utc_now()
        record["timeline"].append(self._event("approval.requested", "Medium risk execution requires human approval before workspace and files."))
        append_audit_event(
            "approval_requested",
            record["sender"],
            {"execution_id": record["execution_id"], "request_id": record["request_id"], "risk_level": record["risk_level"]},
            risk=str(record.get("risk_level") or "MEDIUM").lower(),
        )
        self._save_record(record)
        return self._with_audit_preview(record)

    def _block_high_risk(self, record: dict) -> dict:
        record["state"] = "blocked"
        record["reason"] = "high_risk_authorization_required"
        record["approval_status"] = "blocked"
        record["updated_at"] = utc_now()
        record["timeline"].append(self._event("approval.requested", "High risk execution blocked before workspace or file generation."))
        record["timeline"].append(self._event("execution.blocked", "High risk request needs explicit authorization and no external project writes are allowed."))
        append_audit_event(
            "approval_requested",
            record["sender"],
            {"execution_id": record["execution_id"], "request_id": record["request_id"], "risk_level": record["risk_level"], "blocked": True},
            risk="high",
        )
        self._save_record(record)
        return self._with_audit_preview(record)

    def _block_validation(self, record: dict) -> dict:
        record["state"] = "blocked"
        record["reason"] = "validation_failed"
        record["approval_status"] = "blocked"
        record["updated_at"] = utc_now()
        record["timeline"].append(self._event("validation.failed", "Request confidence is too low for Builder Core execution."))
        record["timeline"].append(self._event("execution.blocked", "FORJA needs a clearer instruction before creating a workspace."))
        append_audit_event(
            "execution_failed",
            record["sender"],
            {"execution_id": record["execution_id"], "request_id": record["request_id"], "reason": "validation_failed"},
            risk="low",
        )
        self._save_record(record)
        return self._with_audit_preview(record)

    def _fail(self, record: dict, reason: str) -> dict:
        record["state"] = "failed"
        record["reason"] = reason
        record["approval_status"] = "blocked"
        record["updated_at"] = utc_now()
        record["timeline"].append(self._event("execution.failed", reason))
        append_audit_event(
            "execution_failed",
            record["sender"],
            {"execution_id": record["execution_id"], "request_id": record["request_id"], "reason": reason},
            risk="high" if "path" in reason or "escape" in reason else str(record.get("risk_level") or "LOW").lower(),
        )
        self._save_record(record)
        return self._with_audit_preview(record)

    def _existing_or_duplicate(self, existing: dict) -> dict:
        if existing["state"] == "completed":
            return self._duplicate_record(existing, "duplicate_execution_blocked")
        if existing["state"] in GENERATING_STATES:
            return self._duplicate_record(existing, "parallel_execution_blocked")
        if existing["state"] in FINAL_EXECUTION_STATES:
            return self._duplicate_record(existing, "duplicate_execution_blocked")
        return self._with_audit_preview(existing)

    def _duplicate_record(self, existing: dict, reason: str) -> dict:
        duplicate = dict(existing)
        duplicate["execution_id"] = f"exec-{uuid.uuid4()}"
        duplicate["state"] = "duplicate_blocked"
        duplicate["reason"] = reason
        duplicate["duplicate_of"] = existing["execution_id"]
        duplicate["parallel_execution_blocked"] = reason == "parallel_execution_blocked"
        duplicate["updated_at"] = utc_now()
        duplicate["timeline"] = list(existing.get("timeline", []))
        duplicate["timeline"].append(self._event("execution.duplicate_blocked", reason))
        append_audit_event(
            "duplicate_execution_blocked",
            existing["sender"],
            {"execution_id": duplicate["execution_id"], "duplicate_of": existing["execution_id"], "request_id": existing["request_id"], "reason": reason},
            risk=str(existing.get("risk_level") or "LOW").lower(),
        )
        return self._with_audit_preview(duplicate)

    def _parallel_block_record(self, sender: str, recipient: str, raw_input: str, normalized_input: str, request_id: str, idempotency_key: str) -> dict:
        record = self._new_record(sender, recipient, raw_input, normalized_input, request_id, idempotency_key)
        record["state"] = "duplicate_blocked"
        record["reason"] = "parallel_execution_blocked"
        record["parallel_execution_blocked"] = True
        record["timeline"].append(self._event("execution.duplicate_blocked", "Active request lock prevented parallel execution."))
        append_audit_event(
            "duplicate_execution_blocked",
            sender,
            {"execution_id": record["execution_id"], "request_id": request_id, "reason": "parallel_execution_blocked"},
            risk="medium",
        )
        return record

    def _new_record(self, sender: str, recipient: str, raw_input: str, normalized_input: str, request_id: str, idempotency_key: str) -> dict:
        now = utc_now()
        return {
            "execution_id": f"exec-{uuid.uuid4()}",
            "request_id": request_id,
            "idempotency_key": idempotency_key,
            "sender": sender,
            "recipient": recipient,
            "response_target": "ceo" if sender != "cerebro" else "cerebro",
            "raw_input": raw_input,
            "normalized_input": normalized_input,
            "request_type": "pending",
            "domain": "general",
            "project_name": None,
            "risk_level": None,
            "state": "pending",
            "reason": None,
            "approval_required": False,
            "approval_status": "not_required",
            "duplicate_of": None,
            "workspace_isolated": True,
            "parallel_execution_blocked": False,
            "governance_bypass_blocked": True,
            "interpretation": None,
            "blueprint": None,
            "workspace": None,
            "generation": None,
            "outputs": [],
            "timeline": [self._event("execution.pending", "Governed execution initialized.")],
            "audit_events": [],
            "created_at": now,
            "updated_at": now,
        }

    def _outputs(self, workspace: dict, generation: dict | None) -> list[dict]:
        request_id = workspace["request_id"]
        logical_root = workspace["logical_path"]
        outputs = [
            {"kind": "workspace", "label": "workspace", "logical_path": logical_root, "status": "created", "source": "workspace_manager"},
        ]
        kind_by_file = {
            "README.md": "readme",
            "blueprint.json": "blueprint",
            "architecture.md": "architecture",
            "execution_report.md": "execution_report",
        }
        for filename in workspace.get("files", []):
            outputs.append(
                {
                    "kind": kind_by_file.get(filename, "workspace"),
                    "label": filename,
                    "logical_path": f"{logical_root}/{filename}",
                    "status": "available",
                    "source": "workspace_manager",
                }
            )
        if generation:
            for module in generation.get("modules_created", []):
                outputs.append({"kind": "module", "label": module, "logical_path": f"{logical_root}/{module}", "status": "available", "source": "file_generator"})
            for directory in generation.get("generated_directories", []):
                outputs.append(
                    {
                        "kind": "generated_directory",
                        "label": directory,
                        "logical_path": f".forja/workspaces/{request_id}/{directory}",
                        "status": "available",
                        "source": "file_generator",
                    }
                )
            for path in generation.get("generated_files", []):
                outputs.append({"kind": "generated_file", "label": path.rsplit("/", 1)[-1], "logical_path": path, "status": "available", "source": "file_generator"})
        return self._unique_outputs(outputs)

    def _unique_outputs(self, outputs: list[dict]) -> list[dict]:
        deduped: list[dict] = []
        seen_paths: set[str] = set()
        for output in outputs:
            logical_path = output["logical_path"]
            if logical_path in seen_paths:
                continue
            seen_paths.add(logical_path)
            deduped.append(output)
        return deduped

    def _write_execution_record(self, workspace: dict, record: dict) -> None:
        request_id = workspace["request_id"]
        workspace_path = self.workspace_root / request_id
        resolved_workspace = workspace_path.resolve()
        resolved_target = (workspace_path / "audit" / "governed_execution_record.json").resolve()
        if not self._is_relative_to(resolved_target, resolved_workspace):
            raise WorkspaceSecurityError("execution_record_escape_blocked")
        payload = dict(record)
        payload["audit_events"] = []
        resolved_target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _should_generate_files(self, blueprint: dict) -> bool:
        return blueprint["project_type"] in SUPPORTED_TYPES and blueprint["risk_level"] in {"MEDIUM", "LOW"}

    def _risk_level(self, interpretation: dict, blueprint: dict | None = None) -> str:
        request_type = interpretation["request_type"]
        if request_type in {"repair", "upgrade"}:
            return "HIGH"
        if blueprint and blueprint["risk_level"] == "HIGH":
            return "HIGH"
        if request_type in {"app", "api", "dashboard", "module", "workflow", "integration"}:
            return "MEDIUM"
        return "LOW"

    def _request_id(self, sender: str, normalized_input: str) -> str:
        digest = hashlib.sha256(f"{sender}:{normalized_input}".encode("utf-8")).hexdigest()[:16]
        return f"exec-{digest}"

    def _idempotency_key(self, sender: str, recipient: str, request_id: str) -> str:
        return hashlib.sha256(f"{sender}:{recipient}:{request_id}".encode("utf-8")).hexdigest()

    def _validate_request_id(self, request_id: str) -> None:
        if not request_id or not SAFE_REQUEST_ID.fullmatch(request_id):
            raise WorkspaceSecurityError("unsafe_request_id")
        if ".." in request_id or "/" in request_id or "\\" in request_id or ":" in request_id:
            raise WorkspaceSecurityError("path_traversal_blocked")

    def _find_by_request(self, request_id: str) -> dict | None:
        matches = [record for record in self._records() if record["request_id"] == request_id]
        if not matches:
            return None
        for state in ("generating", "awaiting_approval", "completed", "blocked", "failed"):
            for record in reversed(matches):
                if record["state"] == state:
                    return record
        return matches[-1]

    def _records(self) -> list[dict]:
        payload = self._store.read({"records": []})
        return payload.get("records", [])

    def _save_record(self, record: dict) -> None:
        def mutator(payload: dict) -> None:
            records = payload.setdefault("records", [])
            for index, existing in enumerate(records):
                if existing["execution_id"] == record["execution_id"]:
                    records[index] = record
                    return
            records.append(record)

        self._store.update({"records": []}, mutator)

    def _with_audit_preview(self, record: dict) -> dict:
        event_types = {
            "execution_started",
            "approval_requested",
            "approval_granted",
            "approval_rejected",
            "generation_started",
            "generation_completed",
            "duplicate_execution_blocked",
            "execution_failed",
        }
        request_id = record.get("request_id")
        preview = []
        for event in read_audit_events(240):
            payload = event.get("payload", {})
            if event["event_type"] in event_types and (payload.get("request_id") == request_id or payload.get("execution_id") == record.get("execution_id")):
                preview.append(
                    {
                        "event_type": event["event_type"],
                        "actor": event["actor"],
                        "risk": event["risk"],
                        "timestamp": event["timestamp"],
                    }
                )
        enriched = dict(record)
        enriched["audit_events"] = preview[-12:]
        return enriched

    def _try_lock_request(self, request_id: str) -> bool:
        with self._active_guard:
            if request_id in self._active_requests:
                return False
            self._active_requests.add(request_id)
            return True

    def _unlock_request(self, request_id: str) -> None:
        with self._active_guard:
            self._active_requests.discard(request_id)

    def _try_lock_workspace(self, workspace_key: str) -> bool:
        with self._active_guard:
            if workspace_key in self._active_workspaces:
                return False
            self._active_workspaces.add(workspace_key)
            return True

    def _unlock_workspace(self, workspace_key: str) -> None:
        with self._active_guard:
            self._active_workspaces.discard(workspace_key)

    def _event(self, event: str, detail: str) -> dict:
        return {"timestamp": utc_now(), "event": event, "detail": detail}

    def _is_relative_to(self, child: Path, parent: Path) -> bool:
        try:
            child.relative_to(parent)
            return True
        except ValueError:
            return False


governed_execution_manager = GovernedExecutionManager()
