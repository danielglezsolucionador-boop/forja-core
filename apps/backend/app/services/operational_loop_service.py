from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
from threading import RLock
import uuid

from app.core.audit import append_audit_event, read_audit_events, utc_now
from app.core.config import settings
from app.core.storage import JsonStore, store
from app.services.blueprint_service import project_blueprint_service
from app.services.file_generation_service import SUPPORTED_TYPES, controlled_file_generator
from app.services.intent_parser import normalize_intent_input
from app.services.intent_service import intent_interpreter_service
from app.services.workspace_service import SAFE_REQUEST_ID, WorkspaceSecurityError, workspace_manager


BUILD_STATES = {
    "build_requested",
    "intent_ready",
    "blueprint_ready",
    "approval_required",
    "approved",
    "workspace_ready",
    "files_generated",
    "build_completed",
    "build_blocked",
    "build_failed",
}
SAFE_FIX_CHECKS = {
    "readme_exists",
    "execution_report_exists",
    "outputs_exist",
    "outputs_not_empty",
    "audit_generated",
    "timeline_generated",
    "workspace_manifest_valid",
    "docs_exists",
    "tests_exists",
}
BLOCKER_CHECKS = {"workspace_exists", "blueprint_exists", "workspace_isolated"}
FAILURE_TYPES = {
    "validation_failure",
    "generation_failure",
    "workspace_failure",
    "provider_failure",
    "governance_block",
    "approval_required",
    "unsafe_operation",
    "duplicate_execution",
    "unknown_failure",
}
RETRY_ALLOWED_FAILURES = {"validation_failure", "generation_failure", "provider_failure"}
RETRY_BLOCKED_FAILURES = {
    "governance_block",
    "approval_required",
    "unsafe_operation",
    "duplicate_execution",
    "workspace_failure",
}


class OperationalLoopError(ValueError):
    pass


class BuildLoopManager:
    def __init__(
        self,
        state_store: JsonStore | None = None,
        base_dir: Path | None = None,
        workspace_manager_override=None,
        file_generator_override=None,
    ) -> None:
        self.base_dir = Path(base_dir) if base_dir else settings.base_dir
        self.workspace_root = self.base_dir / ".forja" / "workspaces"
        self._store = state_store or store("build_loops")
        self._workspace_manager = workspace_manager_override or workspace_manager
        self._file_generator = file_generator_override or controlled_file_generator
        self._guard = RLock()
        self._active_requests: set[str] = set()

    def start(self, payload: dict) -> dict:
        sender = str(payload.get("sender", "ceo")).strip().lower()
        recipient = str(payload.get("recipient", "forja")).strip().lower()
        raw_input = str(payload.get("input", "")).strip()
        normalized = normalize_intent_input(raw_input)
        request_id = str(payload.get("source_request_id") or self._request_id(sender, normalized))
        manual_approval = bool(payload.get("manual_approval", False))

        record = self._new_record(sender, recipient, raw_input, normalized, request_id)
        append_audit_event(
            "build_loop_started",
            sender or "unknown",
            {"build_id": record["build_id"], "request_id": request_id, "recipient": recipient},
            risk="low",
        )
        self._save_record(record)

        if not self._valid_sender(sender) or recipient != "forja" or not raw_input:
            return self._block(record, "invalid_request", risk="low")
        try:
            self._validate_request_id(request_id)
        except WorkspaceSecurityError as exc:
            return self._block(record, str(exc), risk="high")
        existing = self._find_completed(request_id)
        if existing:
            return self._duplicate_record(existing, "duplicate_execution")
        if not self._try_lock(request_id):
            return self._duplicate_record(record, "parallel_build_blocked")

        try:
            return self._run(record, manual_approval=manual_approval)
        except Exception as exc:
            return self._fail(record, str(exc))
        finally:
            self._unlock(request_id)

    def latest(self) -> dict | None:
        records = self._records()
        return self._with_audit_preview(records[-1]) if records else None

    def status(self) -> dict:
        latest = self.latest()
        return {
            "manager": "BuildLoopManager",
            "available_states": sorted(BUILD_STATES),
            "latest_build": latest,
            "safe_workspace_root": ".forja/workspaces",
            "external_commands_enabled": False,
            "generated_at": utc_now(),
        }

    def _run(self, record: dict, manual_approval: bool) -> dict:
        sender = record["sender"]
        request_id = record["request_id"]
        record["timeline"].append(self._event("build.requested", "Build loop received a governed request."))
        self._step(record, "build_requested", "Request accepted by BuildLoopManager.")

        interpretation = intent_interpreter_service.interpret({"sender": sender, "recipient": "forja", "input": record["raw_input"]})
        record.update(
            {
                "state": "intent_ready",
                "active_phase": "intent",
                "interpretation": interpretation,
                "risk_level": interpretation["risk_level"],
                "request_type": interpretation["request_type"],
                "domain": interpretation["domain"],
                "approval_required": bool(interpretation["requires_approval"]),
                "response_target": interpretation["response_target"],
            }
        )
        self._step(record, "intent_ready", "Intent interpretation completed.")
        if interpretation["confidence"] <= 0.2:
            return self._block(record, "invalid_request", risk="low")

        blueprint = project_blueprint_service.generate({"interpretation": interpretation, "source_request_id": request_id})
        risk_level = self._risk_level(interpretation, blueprint)
        approval_required = risk_level in {"MEDIUM", "HIGH"} or bool(blueprint.get("approval_required"))
        record.update(
            {
                "state": "blueprint_ready",
                "active_phase": "blueprint",
                "blueprint": blueprint,
                "project_name": blueprint["project_name"],
                "risk_level": risk_level,
                "approval_required": approval_required,
            }
        )
        self._step(record, "blueprint_ready", "ProjectBlueprint generated.")

        if risk_level == "HIGH":
            return self._block(record, "high_risk_authorization_required", risk="high")
        if approval_required and not manual_approval:
            record["state"] = "approval_required"
            record["active_phase"] = "approval"
            record["approval_status"] = "requested"
            record["progress"] = 45
            record["timeline"].append(self._event("approval.required", "Manual approval required before workspace creation."))
            self._save_record(record)
            append_audit_event(
                "build_loop_blocked",
                sender,
                {"build_id": record["build_id"], "request_id": request_id, "reason": "approval_required"},
                risk=risk_level.lower(),
            )
            return self._with_audit_preview(record)

        record["state"] = "approved"
        record["active_phase"] = "approval"
        record["approval_status"] = "approved" if approval_required else "not_required"
        self._step(record, "approved", "Build approval gate satisfied.")

        workspace = self._workspace_manager.create_workspace(blueprint)
        record.update({"state": "workspace_ready", "active_phase": "workspace", "workspace": workspace})
        self._step(record, "workspace_ready", "Workspace created inside .forja/workspaces.")

        generation = None
        if blueprint["project_type"] in SUPPORTED_TYPES:
            generation = self._file_generator.generate(blueprint, workspace, manual_approval=approval_required or manual_approval)
            if generation["status"] not in {"completed", "duplicate_blocked"}:
                return self._block(record, generation.get("reason") or "generation_blocked", risk=risk_level.lower())
            record["generation"] = generation

        outputs = self._outputs(workspace, generation)
        record.update({"state": "files_generated", "active_phase": "generation", "outputs": outputs})
        self._step(record, "files_generated", "Controlled files and output records generated.")
        self._write_workspace_artifacts(record)

        record["state"] = "build_completed"
        record["active_phase"] = "completed"
        record["progress"] = 100
        record["timeline"].append(self._event("build.completed", "Build loop closed successfully."))
        record["updated_at"] = utc_now()
        self._save_record(record)
        append_audit_event(
            "build_loop_completed",
            sender,
            {"build_id": record["build_id"], "request_id": request_id, "outputs": len(record["outputs"])},
            risk=risk_level.lower(),
        )
        return self._with_audit_preview(record)

    def _write_workspace_artifacts(self, record: dict) -> None:
        workspace = record["workspace"]
        workspace_path = self._workspace_path(workspace["request_id"])
        outputs_dir = workspace_path / "outputs"
        audit_dir = workspace_path / "audit"
        outputs_dir.mkdir(exist_ok=True)
        audit_dir.mkdir(exist_ok=True)
        summary = (
            f"# Build Summary\n\n"
            f"- Build ID: `{record['build_id']}`\n"
            f"- Request ID: `{record['request_id']}`\n"
            f"- Project: `{record.get('project_name')}`\n"
            f"- State: `{record['state']}`\n"
            f"- Approval: `{record['approval_status']}`\n"
            f"- Outputs: `{len(record['outputs'])}`\n"
        )
        self._write_safe(outputs_dir / "build_summary.md", summary, workspace_path, overwrite=False)
        manifest = workspace_manifest(workspace_path, record)
        self._write_safe(workspace_path / "workspace_manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2), workspace_path, overwrite=True)
        self._write_safe(audit_dir / "timeline.json", json.dumps(record["timeline"], ensure_ascii=False, indent=2), workspace_path, overwrite=True)
        audit_payload = dict(record)
        audit_payload["audit_events"] = []
        self._write_safe(audit_dir / "build_loop_record.json", json.dumps(audit_payload, ensure_ascii=False, indent=2), workspace_path, overwrite=True)

    def _outputs(self, workspace: dict, generation: dict | None) -> list[dict]:
        logical_root = workspace["logical_path"]
        outputs = [
            {"kind": "workspace", "label": "workspace", "logical_path": logical_root, "status": "created", "source": "build_loop"},
            {"kind": "output", "label": "build_summary.md", "logical_path": f"{logical_root}/outputs/build_summary.md", "status": "generated", "source": "build_loop"},
            {"kind": "manifest", "label": "workspace_manifest.json", "logical_path": f"{logical_root}/workspace_manifest.json", "status": "generated", "source": "build_loop"},
        ]
        for filename in workspace.get("files", []):
            outputs.append({"kind": "base_file", "label": filename, "logical_path": f"{logical_root}/{filename}", "status": "available", "source": "workspace_manager"})
        if generation:
            for file_path in generation.get("generated_files", []):
                outputs.append({"kind": "generated_file", "label": file_path.rsplit("/", 1)[-1], "logical_path": file_path, "status": "available", "source": "file_generator"})
        return _dedupe_outputs(outputs)

    def _step(self, record: dict, state: str, detail: str) -> None:
        record["state"] = state
        record["updated_at"] = utc_now()
        record["progress"] = {
            "build_requested": 10,
            "intent_ready": 25,
            "blueprint_ready": 40,
            "approved": 55,
            "workspace_ready": 72,
            "files_generated": 88,
        }.get(state, record.get("progress", 0))
        record["timeline"].append(self._event(state.replace("_", "."), detail))
        append_audit_event(
            "build_step_completed",
            record["sender"],
            {"build_id": record["build_id"], "request_id": record["request_id"], "state": state},
            risk=str(record.get("risk_level") or "LOW").lower(),
        )
        self._save_record(record)

    def _block(self, record: dict, reason: str, risk: str = "medium") -> dict:
        record["state"] = "build_blocked"
        record["reason"] = reason
        record["active_phase"] = "blocked"
        record["updated_at"] = utc_now()
        record["timeline"].append(self._event("build.blocked", reason))
        self._save_record(record)
        append_audit_event(
            "build_loop_blocked",
            record.get("sender", "system"),
            {"build_id": record["build_id"], "request_id": record["request_id"], "reason": reason},
            risk=risk,
        )
        return self._with_audit_preview(record)

    def _fail(self, record: dict, reason: str) -> dict:
        record["state"] = "build_failed"
        record["reason"] = reason
        record["active_phase"] = "failed"
        record["updated_at"] = utc_now()
        record["timeline"].append(self._event("build.failed", reason))
        self._save_record(record)
        append_audit_event(
            "build_loop_failed",
            record.get("sender", "system"),
            {"build_id": record["build_id"], "request_id": record["request_id"], "reason": reason},
            risk="high" if "path" in reason or "escape" in reason else str(record.get("risk_level") or "MEDIUM").lower(),
        )
        return self._with_audit_preview(record)

    def _duplicate_record(self, existing: dict, reason: str) -> dict:
        duplicate = dict(existing)
        duplicate["build_id"] = f"build-{uuid.uuid4()}"
        duplicate["state"] = "build_blocked"
        duplicate["reason"] = reason
        duplicate["duplicate_of"] = existing.get("build_id")
        duplicate["updated_at"] = utc_now()
        duplicate["timeline"] = list(existing.get("timeline", []))
        duplicate["timeline"].append(self._event("build.duplicate_blocked", reason))
        append_audit_event(
            "build_loop_blocked",
            duplicate.get("sender", "system"),
            {"build_id": duplicate["build_id"], "request_id": duplicate["request_id"], "reason": reason},
            risk=str(duplicate.get("risk_level") or "LOW").lower(),
        )
        return self._with_audit_preview(duplicate)

    def _new_record(self, sender: str, recipient: str, raw_input: str, normalized_input: str, request_id: str) -> dict:
        now = utc_now()
        return {
            "build_id": f"build-{uuid.uuid4()}",
            "request_id": request_id,
            "sender": sender,
            "recipient": recipient,
            "response_target": "cerebro" if sender == "cerebro" else "ceo",
            "raw_input": raw_input,
            "normalized_input": normalized_input,
            "request_type": "pending",
            "domain": "general",
            "project_name": None,
            "risk_level": "LOW",
            "state": "build_requested",
            "active_phase": "request",
            "progress": 0,
            "reason": None,
            "approval_required": False,
            "approval_status": "not_required",
            "duplicate_of": None,
            "interpretation": None,
            "blueprint": None,
            "workspace": None,
            "generation": None,
            "outputs": [],
            "timeline": [self._event("build.initialized", "Build loop initialized.")],
            "audit_events": [],
            "created_at": now,
            "updated_at": now,
        }

    def _request_id(self, sender: str, normalized_input: str) -> str:
        digest = hashlib.sha256(f"build:{sender}:{normalized_input}".encode("utf-8")).hexdigest()[:16]
        return f"build-{digest}"

    def _risk_level(self, interpretation: dict, blueprint: dict) -> str:
        if interpretation["request_type"] in {"repair", "upgrade"}:
            return "HIGH"
        return blueprint.get("risk_level") or interpretation.get("risk_level") or "LOW"

    def _valid_sender(self, sender: str) -> bool:
        return sender in {"ceo", "cerebro", "user", "seo", "system"}

    def _validate_request_id(self, request_id: str) -> None:
        if not request_id or not SAFE_REQUEST_ID.fullmatch(request_id):
            raise WorkspaceSecurityError("unsafe_request_id")
        if ".." in request_id or "/" in request_id or "\\" in request_id or ":" in request_id:
            raise WorkspaceSecurityError("path_traversal_blocked")

    def _workspace_path(self, request_id: str) -> Path:
        self._validate_request_id(request_id)
        root = self.workspace_root.resolve()
        target = (self.workspace_root / request_id).resolve()
        if not _is_relative_to(target, root):
            raise WorkspaceSecurityError("workspace_escape_blocked")
        return target

    def _write_safe(self, path: Path, content: str, workspace_path: Path, overwrite: bool) -> None:
        resolved = path.resolve()
        if not _is_relative_to(resolved, workspace_path.resolve()):
            raise WorkspaceSecurityError("workspace_write_escape_blocked")
        if path.exists() and not overwrite:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _find_completed(self, request_id: str) -> dict | None:
        for record in reversed(self._records()):
            if record.get("request_id") == request_id and record.get("state") == "build_completed":
                return record
        return None

    def _try_lock(self, request_id: str) -> bool:
        with self._guard:
            if request_id in self._active_requests:
                return False
            self._active_requests.add(request_id)
            return True

    def _unlock(self, request_id: str) -> None:
        with self._guard:
            self._active_requests.discard(request_id)

    def _records(self) -> list[dict]:
        return self._store.read({"records": []}).get("records", [])

    def _save_record(self, record: dict) -> None:
        def mutator(payload: dict) -> None:
            records = payload.setdefault("records", [])
            for index, existing in enumerate(records):
                if existing.get("build_id") == record["build_id"]:
                    records[index] = record
                    return
            records.append(record)
            payload["records"] = records[-160:]

        self._store.update({"records": []}, mutator)

    def _with_audit_preview(self, record: dict) -> dict:
        event_types = {"build_loop_started", "build_step_completed", "build_loop_completed", "build_loop_blocked", "build_loop_failed"}
        preview = _audit_preview(event_types, record.get("request_id"), record.get("build_id"))
        enriched = dict(record)
        enriched["audit_events"] = preview
        return enriched

    def _event(self, event: str, detail: str) -> dict:
        return {"timestamp": utc_now(), "event": event, "detail": detail}


class ValidationLoopManager:
    def __init__(self, state_store: JsonStore | None = None, base_dir: Path | None = None) -> None:
        self.base_dir = Path(base_dir) if base_dir else settings.base_dir
        self.workspace_root = self.base_dir / ".forja" / "workspaces"
        self._store = state_store or store("validation_loops")

    def validate(self, payload: dict) -> dict:
        build = payload.get("build_record") or {}
        request_id = str(payload.get("request_id") or build.get("request_id") or "").strip()
        workspace_id = str(payload.get("workspace_id") or (build.get("workspace") or {}).get("workspace_id") or request_id)
        validation_id = f"val-{uuid.uuid4()}"
        actor = str(build.get("sender") or payload.get("sender") or "system")
        timeline = [self._event("validation.started", "Validation loop started.")]
        append_audit_event("validation_started", actor, {"validation_id": validation_id, "request_id": request_id}, risk="low")

        checks: list[dict] = []
        workspace_path = self._workspace_path(request_id) if request_id and SAFE_REQUEST_ID.fullmatch(request_id) else self.workspace_root / "__invalid__"
        blueprint = _load_json(workspace_path / "blueprint.json")
        project_type = str((blueprint or build.get("blueprint") or {}).get("project_type") or build.get("request_type") or "unknown")

        self._check(checks, "workspace_exists", workspace_path.is_dir(), "Workspace directory exists.", "Workspace directory missing.")
        self._check(checks, "workspace_isolated", _is_relative_to(workspace_path.resolve(), self.workspace_root.resolve()), "Workspace path is isolated.", "Workspace path is not isolated.")
        self._check(checks, "blueprint_exists", (workspace_path / "blueprint.json").is_file(), "blueprint.json exists.", "blueprint.json missing.")
        self._check(checks, "architecture_exists", (workspace_path / "architecture.md").is_file(), "architecture.md exists.", "architecture.md missing.")
        self._check(checks, "readme_exists", (workspace_path / "README.md").is_file(), "README.md exists.", "README.md missing.")
        self._check(checks, "execution_report_exists", (workspace_path / "execution_report.md").is_file(), "execution_report.md exists.", "execution_report.md missing.")
        self._check(checks, "outputs_exist", (workspace_path / "outputs").is_dir(), "outputs directory exists.", "outputs directory missing.")
        self._check(checks, "outputs_not_empty", _directory_has_files(workspace_path / "outputs"), "outputs contain generated records.", "outputs are empty.")
        self._check(checks, "audit_generated", _directory_has_files(workspace_path / "audit"), "audit artifacts exist.", "audit artifacts missing.")
        self._check(checks, "timeline_generated", (workspace_path / "audit" / "timeline.json").is_file(), "timeline artifact exists.", "timeline artifact missing.")
        manifest = _load_json(workspace_path / "workspace_manifest.json")
        self._check(checks, "workspace_manifest_valid", bool(manifest and manifest.get("request_id") == request_id), "workspace_manifest.json is valid.", "workspace_manifest.json missing or invalid.")
        for name in self._structure_checks(project_type):
            self._check(checks, f"{name}_exists", (workspace_path / name).is_dir(), f"{name}/ exists.", f"{name}/ missing.")

        failed = [check for check in checks if not check["passed"]]
        for check in checks:
            event_type = "validation_check_passed" if check["passed"] else "validation_check_failed"
            append_audit_event(event_type, actor, {"validation_id": validation_id, "request_id": request_id, "check": check["check"]}, risk="low" if check["passed"] else "medium")
            timeline.append(self._event(f"validation.{check['check']}", "passed" if check["passed"] else "failed"))

        severity = self._severity(failed)
        report = {
            "validation_id": validation_id,
            "request_id": request_id,
            "workspace_id": workspace_id,
            "passed": not failed,
            "checks": checks,
            "failed_checks": failed,
            "warnings": self._warnings(checks),
            "severity": severity,
            "auto_fix_possible": bool(failed) and severity in {"low", "medium"} and all(check["check"] in SAFE_FIX_CHECKS for check in failed),
            "timeline": timeline,
            "created_at": utc_now(),
        }
        append_audit_event(
            "validation_completed",
            actor,
            {"validation_id": validation_id, "request_id": request_id, "passed": report["passed"], "severity": severity},
            risk="low" if report["passed"] else severity,
        )
        self._save_report(report)
        self._write_report(workspace_path, report)
        return report

    def latest(self) -> dict | None:
        records = self._records()
        return records[-1] if records else None

    def _structure_checks(self, project_type: str) -> list[str]:
        if project_type == "app":
            return ["frontend", "backend", "docs", "tests"]
        if project_type == "api":
            return ["backend", "docs", "tests"]
        if project_type == "dashboard":
            return ["frontend", "docs", "tests"]
        if project_type == "module":
            return ["module", "docs", "tests"]
        return ["docs", "tests"]

    def _severity(self, failed: list[dict]) -> str:
        failed_names = {check["check"] for check in failed}
        if failed_names & {"workspace_exists", "workspace_isolated"}:
            return "blocker"
        if "blueprint_exists" in failed_names:
            return "blocker"
        if failed_names - SAFE_FIX_CHECKS:
            return "high"
        if len(failed) >= 3:
            return "medium"
        return "low" if failed else "low"

    def _warnings(self, checks: list[dict]) -> list[str]:
        warnings: list[str] = []
        if any(check["check"] == "outputs_not_empty" and not check["passed"] for check in checks):
            warnings.append("outputs_missing_or_empty")
        if any(check["check"] == "audit_generated" and not check["passed"] for check in checks):
            warnings.append("audit_artifacts_missing")
        return warnings

    def _check(self, checks: list[dict], name: str, passed: bool, ok: str, fail: str) -> None:
        checks.append({"check": name, "passed": bool(passed), "detail": ok if passed else fail})

    def _workspace_path(self, request_id: str) -> Path:
        return (self.workspace_root / request_id).resolve()

    def _write_report(self, workspace_path: Path, report: dict) -> None:
        if workspace_path.is_dir() and _is_relative_to(workspace_path.resolve(), self.workspace_root.resolve()):
            target = workspace_path / "audit" / "validation_report.json"
            target.parent.mkdir(exist_ok=True)
            target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    def _save_report(self, report: dict) -> None:
        def mutator(payload: dict) -> None:
            payload.setdefault("records", []).append(report)
            payload["records"] = payload["records"][-200:]

        self._store.update({"records": []}, mutator)

    def _records(self) -> list[dict]:
        return self._store.read({"records": []}).get("records", [])

    def _event(self, event: str, detail: str) -> dict:
        return {"timestamp": utc_now(), "event": event, "detail": detail}


class CorrectionLoopManager:
    def __init__(self, validation_manager: ValidationLoopManager | None = None, state_store: JsonStore | None = None, base_dir: Path | None = None) -> None:
        self.base_dir = Path(base_dir) if base_dir else settings.base_dir
        self.workspace_root = self.base_dir / ".forja" / "workspaces"
        self._validation_manager = validation_manager or ValidationLoopManager(base_dir=self.base_dir)
        self._store = state_store or store("correction_loops")

    def correct(self, payload: dict) -> dict:
        report = payload.get("validation_report") or {}
        request_id = str(report.get("request_id") or payload.get("request_id") or "").strip()
        actor = str(payload.get("sender") or "system")
        correction_id = f"corr-{uuid.uuid4()}"
        timeline = [self._event("correction.started", "Correction loop started.")]
        append_audit_event("correction_started", actor, {"correction_id": correction_id, "request_id": request_id}, risk="low")
        workspace_path = (self.workspace_root / request_id).resolve()

        if not report.get("auto_fix_possible"):
            record = self._record(correction_id, request_id, "correction_blocked", [], timeline, None, blocked=["auto_fix_not_allowed"])
            append_audit_event("correction_blocked", actor, {"correction_id": correction_id, "request_id": request_id, "reason": "auto_fix_not_allowed"}, risk="high")
            self._save(record)
            return record
        if not workspace_path.is_dir() or not _is_relative_to(workspace_path, self.workspace_root.resolve()):
            record = self._record(correction_id, request_id, "correction_blocked", [], timeline, None, blocked=["workspace_invalid"])
            append_audit_event("correction_blocked", actor, {"correction_id": correction_id, "request_id": request_id, "reason": "workspace_invalid"}, risk="high")
            self._save(record)
            return record

        applied: list[str] = []
        for check in report.get("failed_checks", []):
            name = check.get("check")
            fixed = self._apply_fix(workspace_path, request_id, name)
            if fixed:
                applied.append(name)
                append_audit_event("safe_fix_applied", actor, {"correction_id": correction_id, "request_id": request_id, "check": name}, risk="low")
                timeline.append(self._event("correction.applied", f"Safe fix applied for {name}."))

        revalidation = self._validation_manager.validate({"request_id": request_id, "sender": actor})
        timeline.append(self._event("correction.revalidated", "Workspace revalidated after safe fixes."))
        append_audit_event(
            "correction_revalidated",
            actor,
            {"correction_id": correction_id, "request_id": request_id, "passed": revalidation["passed"]},
            risk="low" if revalidation["passed"] else "medium",
        )
        state = "correction_completed" if revalidation["passed"] else "correction_failed"
        record = self._record(correction_id, request_id, state, applied, timeline, revalidation)
        self._write_report(workspace_path, record)
        self._save(record)
        return record

    def latest(self) -> dict | None:
        records = self._store.read({"records": []}).get("records", [])
        return records[-1] if records else None

    def _apply_fix(self, workspace_path: Path, request_id: str, check: str) -> bool:
        if check == "readme_exists":
            _write_if_missing(workspace_path / "README.md", f"# FORJA Workspace\n\nRecovered README for `{request_id}`.\n")
            return True
        if check == "execution_report_exists":
            _write_if_missing(workspace_path / "execution_report.md", f"# Execution Report\n\nRecovered execution report for `{request_id}`.\n")
            return True
        if check in {"outputs_exist", "outputs_not_empty"}:
            outputs = workspace_path / "outputs"
            outputs.mkdir(exist_ok=True)
            _write_if_missing(outputs / "correction-placeholder.md", f"# Correction Placeholder\n\nSafe output placeholder for `{request_id}`.\n")
            return True
        if check == "audit_generated":
            audit = workspace_path / "audit"
            audit.mkdir(exist_ok=True)
            _write_if_missing(audit / "audit-placeholder.json", json.dumps({"request_id": request_id, "created_at": utc_now()}, indent=2))
            return True
        if check == "timeline_generated":
            audit = workspace_path / "audit"
            audit.mkdir(exist_ok=True)
            _write_if_missing(audit / "timeline.json", json.dumps([self._event("timeline.recovered", "Timeline placeholder recovered.")], indent=2))
            return True
        if check == "workspace_manifest_valid":
            manifest = workspace_manifest(workspace_path, {"request_id": request_id, "state": "corrected", "outputs": []})
            (workspace_path / "workspace_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            return True
        if check == "docs_exists":
            (workspace_path / "docs").mkdir(exist_ok=True)
            return True
        if check == "tests_exists":
            (workspace_path / "tests").mkdir(exist_ok=True)
            return True
        return False

    def _record(
        self,
        correction_id: str,
        request_id: str,
        state: str,
        applied: list[str],
        timeline: list[dict],
        revalidation: dict | None,
        blocked: list[str] | None = None,
    ) -> dict:
        return {
            "correction_id": correction_id,
            "request_id": request_id,
            "state": state,
            "safe_fixes_applied": applied,
            "blocked_fixes": blocked or [],
            "revalidation": revalidation,
            "timeline": timeline,
            "created_at": utc_now(),
        }

    def _write_report(self, workspace_path: Path, record: dict) -> None:
        if workspace_path.is_dir() and _is_relative_to(workspace_path.resolve(), self.workspace_root.resolve()):
            target = workspace_path / "audit" / "correction_report.json"
            target.parent.mkdir(exist_ok=True)
            target.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    def _save(self, record: dict) -> None:
        def mutator(payload: dict) -> None:
            payload.setdefault("records", []).append(record)
            payload["records"] = payload["records"][-200:]

        self._store.update({"records": []}, mutator)

    def _event(self, event: str, detail: str) -> dict:
        return {"timestamp": utc_now(), "event": event, "detail": detail}


class RetryPolicyManager:
    def __init__(self, state_store: JsonStore | None = None, max_retries: int = 3) -> None:
        self._store = state_store or store("retry_policy")
        self.max_retries = max_retries

    def evaluate(self, payload: dict) -> dict:
        operation_id = str(payload.get("operation_id") or payload.get("request_id") or f"retry-{uuid.uuid4()}")
        request_id = str(payload.get("request_id") or operation_id)
        failure_type = str(payload.get("failure_type") or "unknown_failure")
        retry_count = int(payload.get("retry_count", 0))
        retry_reason = str(payload.get("retry_reason") or payload.get("reason") or failure_type)
        failure_classification = self._classify(failure_type, retry_reason)
        timeline = [self._event("failure.classified", failure_classification)]
        append_audit_event("failure_classified", "system", {"operation_id": operation_id, "request_id": request_id, "failure_classification": failure_classification}, risk="medium")

        duplicate = self._is_duplicate_active(operation_id)
        if duplicate:
            record = self._record(operation_id, request_id, retry_count, retry_reason, False, "duplicate_execution", failure_classification, "retry_blocked", timeline)
            append_audit_event("retry_blocked", "system", {"operation_id": operation_id, "reason": "duplicate_execution"}, risk="medium")
            self._save(record)
            return record
        if retry_count >= self.max_retries:
            record = self._record(operation_id, request_id, retry_count, retry_reason, False, "max_retries_reached", failure_classification, "retry_blocked", timeline)
            append_audit_event("max_retries_reached", "system", {"operation_id": operation_id, "retry_count": retry_count}, risk="medium")
            self._save(record)
            return record

        allowed = failure_classification in RETRY_ALLOWED_FAILURES and failure_classification not in RETRY_BLOCKED_FAILURES
        blocked_reason = None if allowed else f"{failure_classification}_not_retryable"
        state = "retry_completed" if allowed else "retry_blocked"
        record = self._record(operation_id, request_id, retry_count + (1 if allowed else 0), retry_reason, allowed, blocked_reason, failure_classification, state, timeline)
        if allowed:
            append_audit_event("retry_started", "system", {"operation_id": operation_id, "request_id": request_id, "retry_count": record["retry_count"]}, risk="low")
            record["timeline"].append(self._event("retry.completed", "Retry policy allowed a controlled retry."))
            append_audit_event("retry_completed", "system", {"operation_id": operation_id, "request_id": request_id, "retry_count": record["retry_count"]}, risk="low")
        else:
            append_audit_event("retry_blocked", "system", {"operation_id": operation_id, "request_id": request_id, "reason": blocked_reason}, risk="high")
        self._save(record)
        return record

    def latest(self) -> dict | None:
        records = self._store.read({"records": []}).get("records", [])
        return records[-1] if records else None

    def _classify(self, failure_type: str, reason: str) -> str:
        if failure_type in FAILURE_TYPES:
            return failure_type
        lowered = reason.lower()
        if "path" in lowered or "traversal" in lowered or "secret" in lowered or "overwrite" in lowered:
            return "unsafe_operation"
        if "approval" in lowered:
            return "approval_required"
        if "duplicate" in lowered:
            return "duplicate_execution"
        return "unknown_failure"

    def _is_duplicate_active(self, operation_id: str) -> bool:
        records = self._store.read({"records": []}).get("records", [])
        return any(record.get("operation_id") == operation_id and record.get("state") == "retry_started" for record in records)

    def _record(
        self,
        operation_id: str,
        request_id: str,
        retry_count: int,
        retry_reason: str,
        retry_allowed: bool,
        blocked_reason: str | None,
        classification: str,
        state: str,
        timeline: list[dict],
    ) -> dict:
        return {
            "retry_id": f"retry-{uuid.uuid4()}",
            "operation_id": operation_id,
            "request_id": request_id,
            "max_retries": self.max_retries,
            "retry_count": retry_count,
            "retry_reason": retry_reason,
            "retry_allowed": retry_allowed,
            "retry_blocked_reason": blocked_reason,
            "failure_classification": classification,
            "state": state,
            "timeline": timeline,
            "created_at": utc_now(),
        }

    def _save(self, record: dict) -> None:
        def mutator(payload: dict) -> None:
            payload.setdefault("records", []).append(record)
            payload["records"] = payload["records"][-200:]

        self._store.update({"records": []}, mutator)

    def _event(self, event: str, detail: str) -> dict:
        return {"timestamp": utc_now(), "event": event, "detail": detail}


class DeliveryPackageManager:
    def __init__(self, state_store: JsonStore | None = None, base_dir: Path | None = None) -> None:
        self.base_dir = Path(base_dir) if base_dir else settings.base_dir
        self.workspace_root = self.base_dir / ".forja" / "workspaces"
        self._store = state_store or store("delivery_packages")

    def create(self, payload: dict) -> dict:
        build = payload.get("build_record") or {}
        validation = payload.get("validation_report") or {}
        correction = payload.get("correction_report") or {}
        request_id = str(payload.get("request_id") or build.get("request_id") or validation.get("request_id") or "").strip()
        actor = str(build.get("sender") or payload.get("sender") or "system")
        package_id = f"delivery-{uuid.uuid4()}"
        workspace_path = (self.workspace_root / request_id).resolve()
        timeline = [self._event("delivery.started", "Delivery package creation started.")]
        append_audit_event("delivery_package_started", actor, {"package_id": package_id, "request_id": request_id}, risk="low")
        if not workspace_path.is_dir() or not _is_relative_to(workspace_path, self.workspace_root.resolve()):
            record = self._record(package_id, request_id, "failed", [], timeline, "workspace_invalid")
            append_audit_event("delivery_package_failed", actor, {"package_id": package_id, "request_id": request_id, "reason": "workspace_invalid"}, risk="high")
            self._save(record)
            return record

        delivery_dir = workspace_path / "delivery"
        delivery_dir.mkdir(exist_ok=True)
        blueprint = _load_json(workspace_path / "blueprint.json") or build.get("blueprint") or {}
        manifest = workspace_manifest(workspace_path, build)
        validation_payload = validation or _load_json(workspace_path / "audit" / "validation_report.json") or {}
        correction_payload = correction or _load_json(workspace_path / "audit" / "correction_report.json") or {}
        files = {
            "summary.md": self._summary(build, blueprint, validation_payload),
            "blueprint.json": json.dumps(blueprint, ensure_ascii=False, indent=2),
            "architecture.md": _read_text(workspace_path / "architecture.md", "# Architecture\n\nNot available.\n"),
            "execution_report.md": _read_text(workspace_path / "execution_report.md", "# Execution Report\n\nNot available.\n"),
            "validation_report.md": self._report_markdown("Validation Report", validation_payload),
            "correction_report.md": self._report_markdown("Correction Report", correction_payload or {"status": "not_required"}),
            "workspace_manifest.json": json.dumps(manifest, ensure_ascii=False, indent=2),
            "audit_summary.md": self._audit_summary(request_id),
            "next_steps.md": self._next_steps(build, validation_payload),
        }
        written: list[dict] = []
        for filename, content in files.items():
            target = delivery_dir / filename
            target.write_text(content, encoding="utf-8")
            written.append(
                {
                    "label": filename,
                    "logical_path": f".forja/workspaces/{request_id}/delivery/{filename}",
                    "checksum": _sha256_text(content),
                    "status": "available",
                }
            )
        timeline.append(self._event("delivery.created", "Delivery package files created."))
        record = self._record(package_id, request_id, "completed", written, timeline, None)
        self._write_report(workspace_path, record)
        self._save(record)
        append_audit_event("delivery_package_created", actor, {"package_id": package_id, "request_id": request_id, "files": len(written)}, risk="low")
        return record

    def latest(self) -> dict | None:
        records = self._store.read({"records": []}).get("records", [])
        return records[-1] if records else None

    def _summary(self, build: dict, blueprint: dict, validation: dict) -> str:
        outputs = build.get("outputs", [])
        output_lines = "\n".join(f"- {item.get('label')} ({item.get('status')})" for item in outputs) or "- Base workspace artifacts"
        return (
            "# Delivery Summary\n\n"
            f"- Request: {build.get('raw_input') or blueprint.get('objective') or 'not recorded'}\n"
            f"- Built: {blueprint.get('project_name') or build.get('project_name') or 'FORJA controlled workspace'}\n"
            f"- Status: {build.get('state') or 'completed'}\n"
            f"- Validation: {'passed' if validation.get('passed') else validation.get('severity', 'pending')}\n\n"
            "## Generated Files\n\n"
            f"{output_lines}\n\n"
            "## Pending\n\n"
            "- Manual review before running generated project commands.\n\n"
            "## Risks\n\n"
            "- Generated project files are initial controlled scaffolds only.\n\n"
            "## Review\n\n"
            "- Inspect delivery files, validation report, manifest, and audit summary.\n"
        )

    def _next_steps(self, build: dict, validation: dict) -> str:
        approval = build.get("approval_status", "not_required")
        return (
            "# Next Steps\n\n"
            "- Review generated files in the delivery package.\n"
            f"- Confirm approval state: `{approval}`.\n"
            "- Test generated project manually in a separate phase.\n"
            "- Do not run package managers or deploy generated projects automatically.\n"
            "- Continue only after validation and CEO/CTO review.\n"
            f"- Validation severity: `{validation.get('severity', 'pending')}`.\n"
        )

    def _report_markdown(self, title: str, payload: dict) -> str:
        return f"# {title}\n\n```json\n{json.dumps(payload or {'status': 'not_available'}, ensure_ascii=False, indent=2)}\n```\n"

    def _audit_summary(self, request_id: str) -> str:
        rows = []
        for event in read_audit_events(200):
            payload = event.get("payload", {})
            if payload.get("request_id") == request_id:
                rows.append(f"- `{event['timestamp']}` {event['event_type']} ({event['risk']})")
        return "# Audit Summary\n\n" + ("\n".join(rows[-40:]) or "- No matching audit events found.") + "\n"

    def _record(self, package_id: str, request_id: str, status: str, files: list[dict], timeline: list[dict], reason: str | None) -> dict:
        return {
            "package_id": package_id,
            "request_id": request_id,
            "status": status,
            "reason": reason,
            "logical_path": f".forja/workspaces/{request_id}/delivery" if request_id else None,
            "files": files,
            "timeline": timeline,
            "created_at": utc_now(),
        }

    def _write_report(self, workspace_path: Path, record: dict) -> None:
        target = workspace_path / "audit" / "delivery_package_record.json"
        target.parent.mkdir(exist_ok=True)
        target.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    def _save(self, record: dict) -> None:
        def mutator(payload: dict) -> None:
            payload.setdefault("records", []).append(record)
            payload["records"] = payload["records"][-200:]

        self._store.update({"records": []}, mutator)

    def _event(self, event: str, detail: str) -> dict:
        return {"timestamp": utc_now(), "event": event, "detail": detail}


def workspace_manifest(workspace_path: Path, record: dict) -> dict:
    files: list[dict] = []
    folders: list[str] = []
    if workspace_path.exists():
        for path in sorted(workspace_path.rglob("*")):
            relative = path.relative_to(workspace_path).as_posix()
            if path.is_dir():
                folders.append(relative)
            else:
                content = path.read_bytes()
                files.append({"path": relative, "checksum": hashlib.sha256(content).hexdigest(), "bytes": len(content)})
    return {
        "request_id": record.get("request_id") or workspace_path.name,
        "workspace_id": (record.get("workspace") or {}).get("workspace_id") or record.get("workspace_id") or workspace_path.name,
        "status": record.get("state") or record.get("status") or "available",
        "files": files,
        "folders": folders,
        "timestamps": {"created_at": record.get("created_at"), "generated_at": utc_now()},
        "logical_path": f".forja/workspaces/{workspace_path.name}",
    }


def _audit_preview(event_types: set[str], request_id: str | None, entity_id: str | None) -> list[dict]:
    preview = []
    for event in read_audit_events(280):
        payload = event.get("payload", {})
        if event["event_type"] in event_types and (payload.get("request_id") == request_id or payload.get("build_id") == entity_id):
            preview.append({"event_type": event["event_type"], "actor": event["actor"], "risk": event["risk"], "timestamp": event["timestamp"]})
    return preview[-14:]


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _directory_has_files(path: Path) -> bool:
    return path.is_dir() and any(item.is_file() for item in path.rglob("*"))


def _load_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _read_text(path: Path, default: str) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else default


def _write_if_missing(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(content, encoding="utf-8")


def _sha256_text(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _dedupe_outputs(outputs: list[dict]) -> list[dict]:
    seen: set[str] = set()
    result: list[dict] = []
    for output in outputs:
        key = output.get("logical_path") or output.get("label")
        if key in seen:
            continue
        seen.add(key)
        result.append(output)
    return result


build_loop_manager = BuildLoopManager()
validation_loop_manager = ValidationLoopManager()
correction_loop_manager = CorrectionLoopManager(validation_manager=validation_loop_manager)
retry_policy_manager = RetryPolicyManager()
delivery_package_manager = DeliveryPackageManager()
