from __future__ import annotations

from pathlib import Path
import json
import re
import uuid

from app.core.audit import append_audit_event, utc_now
from app.core.config import settings


REQUIRED_DIRECTORIES = ["frontend", "backend", "docs", "tests", "outputs", "audit"]
REQUIRED_FILES = ["README.md", "blueprint.json", "architecture.md", "execution_report.md"]
SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$")


class WorkspaceSecurityError(ValueError):
    pass


class WorkspaceAlreadyExistsError(FileExistsError):
    pass


class WorkspaceManager:
    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or settings.base_dir
        self.workspace_root = self.base_dir / ".forja" / "workspaces"

    def create_workspace(self, blueprint: dict) -> dict:
        request_id = str(blueprint["source_request_id"])
        risk = str(blueprint["risk_level"]).lower()
        append_audit_event(
            "workspace_creation_requested",
            blueprint["sender"],
            {
                "request_id": request_id,
                "blueprint_id": blueprint["blueprint_id"],
                "project_type": blueprint["project_type"],
                "risk_level": blueprint["risk_level"],
            },
            risk=risk,
        )
        timeline = [
            self._event("workspace.creation_requested", "Workspace creation requested from ProjectBlueprint."),
        ]
        try:
            workspace_path = self._validated_workspace_path(request_id)
        except WorkspaceSecurityError as exc:
            append_audit_event(
                "unsafe_path_blocked",
                blueprint["sender"],
                {"request_id": request_id, "blueprint_id": blueprint["blueprint_id"], "reason": str(exc)},
                risk="high",
            )
            raise

        timeline.append(self._event("workspace.path_validated", "Workspace path is isolated under .forja/workspaces."))
        if workspace_path.exists():
            append_audit_event(
                "workspace_blocked",
                blueprint["sender"],
                {"request_id": request_id, "blueprint_id": blueprint["blueprint_id"], "reason": "workspace_already_exists"},
                risk=risk,
            )
            raise WorkspaceAlreadyExistsError("workspace_already_exists")

        self.workspace_root.mkdir(parents=True, exist_ok=True)
        workspace_path.mkdir(parents=False, exist_ok=False)
        for directory in REQUIRED_DIRECTORIES:
            (workspace_path / directory).mkdir()
        timeline.append(self._event("workspace.structure_created", "Required workspace directories created."))

        record = self._record(blueprint, request_id, timeline)
        self._write_base_files(workspace_path, blueprint, record)
        timeline.append(self._event("workspace.base_files_created", "README, blueprint, architecture, and execution report created."))
        if record["approval_required"]:
            timeline.append(self._event("workspace.approval_required", "Medium/high risk requires approval before complex generation."))
        else:
            timeline.append(self._event("workspace.low_risk_ready", "Low risk workspace is ready for safe review."))
        record["timeline"] = timeline

        self._rewrite_execution_report(workspace_path, blueprint, record)
        append_audit_event(
            "workspace_created",
            blueprint["sender"],
            {
                "workspace_id": record["workspace_id"],
                "request_id": request_id,
                "blueprint_id": blueprint["blueprint_id"],
                "logical_path": record["logical_path"],
                "approval_status": record["approval_status"],
            },
            risk=risk,
        )
        return record

    def _validated_workspace_path(self, request_id: str) -> Path:
        if not request_id or not SAFE_REQUEST_ID.fullmatch(request_id):
            raise WorkspaceSecurityError("unsafe_request_id")
        if ".." in request_id or "/" in request_id or "\\" in request_id or ":" in request_id:
            raise WorkspaceSecurityError("path_traversal_blocked")
        candidate = self.workspace_root / request_id
        if Path(request_id).is_absolute() or candidate.is_absolute() and not self._is_relative_to(candidate.resolve(), self.workspace_root.resolve()):
            raise WorkspaceSecurityError("absolute_or_external_path_blocked")
        resolved_root = self.workspace_root.resolve()
        resolved_candidate = candidate.resolve()
        if not self._is_relative_to(resolved_candidate, resolved_root):
            raise WorkspaceSecurityError("workspace_escape_blocked")
        return candidate

    def _record(self, blueprint: dict, request_id: str, timeline: list[dict]) -> dict:
        approval_required = blueprint["risk_level"] in {"MEDIUM", "HIGH"} or bool(blueprint.get("approval_required", False))
        return {
            "workspace_id": f"ws-{uuid.uuid4()}",
            "request_id": request_id,
            "blueprint_id": blueprint["blueprint_id"],
            "sender": blueprint["sender"],
            "response_target": blueprint["response_target"],
            "project_name": blueprint["project_name"],
            "project_type": blueprint["project_type"],
            "domain": blueprint["domain"],
            "risk_level": blueprint["risk_level"],
            "approval_required": approval_required,
            "approval_status": "pending" if approval_required else "not_required",
            "status": "created",
            "logical_path": f".forja/workspaces/{request_id}",
            "directories": list(REQUIRED_DIRECTORIES),
            "files": list(REQUIRED_FILES),
            "workspace_isolated": True,
            "complex_generation_allowed": False,
            "timeline": timeline,
            "created_at": utc_now(),
        }

    def _write_base_files(self, workspace_path: Path, blueprint: dict, record: dict) -> None:
        self._write_text(workspace_path / "README.md", self._readme(blueprint, record))
        self._write_text(workspace_path / "blueprint.json", json.dumps(blueprint, ensure_ascii=False, indent=2))
        self._write_text(workspace_path / "architecture.md", self._architecture(blueprint))
        self._write_text(workspace_path / "execution_report.md", self._execution_report(blueprint, record))

    def _rewrite_execution_report(self, workspace_path: Path, blueprint: dict, record: dict) -> None:
        self._write_text(workspace_path / "execution_report.md", self._execution_report(blueprint, record), overwrite=True)

    def _write_text(self, path: Path, content: str, overwrite: bool = False) -> None:
        if path.exists() and not overwrite:
            raise WorkspaceAlreadyExistsError("base_file_already_exists")
        if not self._is_relative_to(path.resolve(), self.workspace_root.resolve()):
            raise WorkspaceSecurityError("workspace_file_escape_blocked")
        path.write_text(content, encoding="utf-8")

    def _readme(self, blueprint: dict, record: dict) -> str:
        risks = "\n".join(f"- {risk['level']}: {risk['title']} - {risk['mitigation']}" for risk in blueprint["risks"])
        return (
            f"# {blueprint['project_name']}\n\n"
            "Workspace base creado por FORJA Fase 4.3.\n\n"
            f"- Nombre del proyecto: `{blueprint['project_name']}`\n"
            f"- Tipo: `{blueprint['project_type']}`\n"
            f"- Dominio: `{blueprint['domain']}`\n"
            f"- Objetivo: {blueprint['objective']}\n"
            f"- Fecha: `{record['created_at']}`\n"
            f"- Sender: `{blueprint['sender']}`\n"
            f"- Estado: `{record['status']}`\n"
            f"- Approval status: `{record['approval_status']}`\n\n"
            "## Riesgos\n\n"
            f"{risks}\n"
        )

    def _architecture(self, blueprint: dict) -> str:
        return (
            f"# Architecture - {blueprint['project_name']}\n\n"
            "## Stack\n\n"
            f"{self._bullet_list(blueprint['stack_recommendation'])}\n"
            "## Estructura\n\n"
            f"{self._bullet_list(blueprint['suggested_structure'])}\n"
            "## Modulos\n\n"
            f"{self._bullet_list(blueprint['modules'])}\n"
            "## Endpoints\n\n"
            f"{self._endpoint_list(blueprint['endpoints'])}\n"
            "## Pantallas\n\n"
            f"{self._bullet_list(blueprint['screens'])}\n"
            "## Riesgos\n\n"
            f"{self._risk_list(blueprint['risks'])}\n"
        )

    def _execution_report(self, blueprint: dict, record: dict) -> str:
        return (
            "# Execution Report\n\n"
            f"- Workspace creado: `{record['status'] == 'created'}`\n"
            f"- Timestamp: `{record['created_at']}`\n"
            f"- Request ID: `{record['request_id']}`\n"
            f"- Blueprint ID: `{blueprint['blueprint_id']}`\n"
            f"- Sender: `{blueprint['sender']}`\n"
            f"- Status: `{record['status']}`\n"
            f"- Logical path: `{record['logical_path']}`\n"
            f"- Complex generation allowed: `{record['complex_generation_allowed']}`\n\n"
            "## Timeline\n\n"
            f"{self._timeline_list(record['timeline'])}\n"
        )

    def _bullet_list(self, values: list[str]) -> str:
        return "\n".join(f"- {value}" for value in values) or "- none"

    def _endpoint_list(self, endpoints: list[dict]) -> str:
        return "\n".join(f"- `{item['method']} {item['path']}`: {item['purpose']}" for item in endpoints) or "- none"

    def _risk_list(self, risks: list[dict]) -> str:
        return "\n".join(f"- `{item['level']}` {item['title']}: {item['mitigation']}" for item in risks) or "- none"

    def _timeline_list(self, timeline: list[dict]) -> str:
        return "\n".join(f"- `{item['timestamp']}` {item['event']}: {item['detail']}" for item in timeline) or "- none"

    def _event(self, event: str, detail: str) -> dict:
        return {"timestamp": utc_now(), "event": event, "detail": detail}

    def _is_relative_to(self, child: Path, parent: Path) -> bool:
        try:
            child.relative_to(parent)
            return True
        except ValueError:
            return False


workspace_manager = WorkspaceManager()
