from __future__ import annotations

from pathlib import Path
import json
import re
import uuid

from app.core.audit import append_audit_event, utc_now
from app.core.config import settings
from app.services.workspace_service import SAFE_REQUEST_ID, WorkspaceSecurityError


SUPPORTED_TYPES = {"app", "api", "dashboard", "module"}
DANGEROUS_NAMES = {".env", ".env.local", "id_rsa", "id_dsa"}
DANGEROUS_SUFFIXES = {".sh", ".bat", ".cmd", ".ps1", ".pem", ".key"}
DANGEROUS_CONTENT_MARKERS = ["api_key", "secret=", "password=", "private_key", "-----BEGIN"]


class FileGenerationSecurityError(ValueError):
    pass


class ControlledFileGenerator:
    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or settings.base_dir
        self.workspace_root = self.base_dir / ".forja" / "workspaces"

    def generate(self, blueprint: dict, workspace: dict, manual_approval: bool = False) -> dict:
        request_id = str(workspace["request_id"])
        risk = str(blueprint["risk_level"]).lower()
        timeline = [self._event("generation.started", "Controlled file generation requested.")]
        append_audit_event(
            "generation_started",
            blueprint["sender"],
            {
                "request_id": request_id,
                "workspace_id": workspace["workspace_id"],
                "blueprint_id": blueprint["blueprint_id"],
                "project_type": blueprint["project_type"],
                "manual_approval": manual_approval,
            },
            risk=risk,
        )

        try:
            workspace_path = self._validated_workspace_path(request_id)
            self._validate_workspace_contract(blueprint, workspace)
        except (FileGenerationSecurityError, WorkspaceSecurityError) as exc:
            append_audit_event(
                "unsafe_generation_blocked",
                blueprint["sender"],
                {"request_id": request_id, "blueprint_id": blueprint["blueprint_id"], "reason": str(exc)},
                risk="high",
            )
            raise

        if blueprint["project_type"] not in SUPPORTED_TYPES:
            return self._blocked_record(blueprint, workspace, "unsupported_project_type", "blocked", timeline)
        governance_block = self._governance_block_reason(blueprint, manual_approval)
        if governance_block:
            timeline.append(self._event("generation.blocked", governance_block))
            return self._blocked_record(blueprint, workspace, governance_block, self._approval_status(blueprint, manual_approval), timeline)

        plan = self._generation_plan(blueprint)
        target_files = [item[0] for item in plan]
        existing = [path for path in target_files if (workspace_path / path).exists()]
        marker = workspace_path / "audit" / "file_generation_record.json"
        if marker.exists() or existing:
            timeline.append(self._event("generation.duplicate_blocked", "Existing generated files were detected; no overwrite performed."))
            record = self._record(
                blueprint,
                workspace,
                status="duplicate_blocked",
                reason="duplicate_generation_blocked",
                approval_status=self._approval_status(blueprint, manual_approval),
                generated_files=[self._logical_file(request_id, path) for path in target_files],
                generated_directories=self._generated_directories(plan),
                modules_created=self._modules_created(blueprint),
                timeline=timeline,
            )
            append_audit_event(
                "duplicate_generation_blocked",
                blueprint["sender"],
                {"request_id": request_id, "workspace_id": workspace["workspace_id"], "blueprint_id": blueprint["blueprint_id"]},
                risk=risk,
            )
            return record

        for relative_path, content in plan:
            self._write_generated_file(workspace_path, relative_path, content)
        generated_directories = self._generated_directories(plan)
        timeline.append(self._event("generation.files_written", "Initial safe project files written inside workspace."))
        record = self._record(
            blueprint,
            workspace,
            status="completed",
            reason=None,
            approval_status=self._approval_status(blueprint, manual_approval),
            generated_files=[self._logical_file(request_id, path) for path, _ in plan],
            generated_directories=generated_directories,
            modules_created=self._modules_created(blueprint),
            timeline=timeline,
        )
        marker.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        append_audit_event(
            "files_generated",
            blueprint["sender"],
            {
                "request_id": request_id,
                "workspace_id": workspace["workspace_id"],
                "blueprint_id": blueprint["blueprint_id"],
                "files": record["generated_files"],
            },
            risk=risk,
        )
        timeline.append(self._event("generation.completed", "Controlled file generation completed without external commands."))
        record["timeline"] = timeline
        marker.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        append_audit_event(
            "generation_completed",
            blueprint["sender"],
            {"request_id": request_id, "workspace_id": workspace["workspace_id"], "blueprint_id": blueprint["blueprint_id"], "status": "completed"},
            risk=risk,
        )
        return record

    def _validated_workspace_path(self, request_id: str) -> Path:
        if not request_id or not SAFE_REQUEST_ID.fullmatch(request_id):
            raise WorkspaceSecurityError("unsafe_request_id")
        if ".." in request_id or "/" in request_id or "\\" in request_id or ":" in request_id:
            raise WorkspaceSecurityError("path_traversal_blocked")
        candidate = self.workspace_root / request_id
        resolved_root = self.workspace_root.resolve()
        resolved_candidate = candidate.resolve()
        if not self._is_relative_to(resolved_candidate, resolved_root):
            raise WorkspaceSecurityError("workspace_escape_blocked")
        if not candidate.is_dir():
            raise FileGenerationSecurityError("workspace_not_found")
        return candidate

    def _validate_workspace_contract(self, blueprint: dict, workspace: dict) -> None:
        if workspace["request_id"] != blueprint["source_request_id"]:
            raise FileGenerationSecurityError("workspace_request_mismatch")
        if workspace["blueprint_id"] != blueprint["blueprint_id"]:
            raise FileGenerationSecurityError("workspace_blueprint_mismatch")
        if not str(workspace.get("logical_path", "")).startswith(".forja/workspaces/"):
            raise FileGenerationSecurityError("unsafe_logical_path")

    def _governance_block_reason(self, blueprint: dict, manual_approval: bool) -> str | None:
        if blueprint["risk_level"] == "HIGH":
            return "high_risk_authorization_required"
        if blueprint["risk_level"] == "MEDIUM" and not manual_approval:
            return "manual_approval_required"
        return None

    def _approval_status(self, blueprint: dict, manual_approval: bool) -> str:
        if blueprint["risk_level"] == "LOW":
            return "not_required"
        if blueprint["risk_level"] == "MEDIUM":
            return "approved" if manual_approval else "required"
        return "blocked"

    def _blocked_record(self, blueprint: dict, workspace: dict, reason: str, approval_status: str, timeline: list[dict]) -> dict:
        if reason == "unsupported_project_type":
            append_audit_event(
                "unsafe_generation_blocked",
                blueprint["sender"],
                {"request_id": workspace["request_id"], "workspace_id": workspace["workspace_id"], "blueprint_id": blueprint["blueprint_id"], "reason": reason},
                risk=str(blueprint["risk_level"]).lower(),
            )
        return self._record(
            blueprint,
            workspace,
            status="blocked",
            reason=reason,
            approval_status=approval_status,
            generated_files=[],
            generated_directories=[],
            modules_created=[],
            timeline=timeline,
        )

    def _generation_plan(self, blueprint: dict) -> list[tuple[str, str]]:
        project_type = blueprint["project_type"]
        if project_type == "app":
            return self._app_plan(blueprint)
        if project_type == "api":
            return self._api_plan(blueprint)
        if project_type == "dashboard":
            return self._dashboard_plan(blueprint)
        if project_type == "module":
            return self._module_plan(blueprint)
        return []

    def _app_plan(self, blueprint: dict) -> list[tuple[str, str]]:
        return [
            ("frontend/package.json", self._frontend_package_json(blueprint)),
            ("frontend/README.md", self._project_readme(blueprint, "frontend React/Vite")),
            ("frontend/src/App.tsx", self._react_app(blueprint)),
            ("frontend/src/main.tsx", self._react_main()),
            ("backend/requirements.txt", self._requirements()),
            ("backend/README.md", self._project_readme(blueprint, "backend FastAPI")),
            ("backend/app/main.py", self._fastapi_main(blueprint)),
            ("backend/app/routes/__init__.py", '"""Generated safe route package."""\n'),
            ("backend/app/schemas/__init__.py", '"""Generated safe schema package."""\n'),
        ]

    def _api_plan(self, blueprint: dict) -> list[tuple[str, str]]:
        resource = self._resource_name(blueprint)
        return [
            ("backend/requirements.txt", self._requirements()),
            ("backend/README.md", self._project_readme(blueprint, "FastAPI API")),
            ("backend/app/main.py", self._fastapi_main(blueprint, resource)),
            ("backend/app/routes/__init__.py", '"""Generated API routes."""\n'),
            (f"backend/app/routes/{resource}.py", self._api_route(blueprint, resource)),
            ("backend/app/schemas/__init__.py", '"""Generated API schemas."""\n'),
            (f"backend/app/schemas/{resource}.py", self._api_schema(blueprint)),
            ("backend/app/services/__init__.py", '"""Generated API services."""\n'),
            (f"backend/app/services/{resource}_service.py", self._api_service(blueprint)),
        ]

    def _dashboard_plan(self, blueprint: dict) -> list[tuple[str, str]]:
        return [
            ("frontend/package.json", self._frontend_package_json(blueprint)),
            ("frontend/README.md", self._project_readme(blueprint, "React/Vite dashboard")),
            ("frontend/src/main.tsx", self._react_main()),
            ("frontend/src/App.tsx", self._react_app(blueprint)),
            ("frontend/src/components/KpiCard.tsx", self._kpi_card()),
            ("frontend/src/pages/DashboardPage.tsx", self._dashboard_page(blueprint)),
        ]

    def _module_plan(self, blueprint: dict) -> list[tuple[str, str]]:
        return [
            ("module/README.md", self._project_readme(blueprint, "controlled module")),
            ("module/interfaces/contract.md", self._module_contract(blueprint)),
            ("module/services/service.md", self._module_service(blueprint)),
            ("module/tests/test_contract.md", self._module_tests(blueprint)),
        ]

    def _write_generated_file(self, workspace_path: Path, relative_path: str, content: str) -> None:
        self._validate_relative_file(relative_path, content)
        path = workspace_path / relative_path
        resolved_workspace = workspace_path.resolve()
        resolved_path = path.resolve()
        if not self._is_relative_to(resolved_path, resolved_workspace):
            raise FileGenerationSecurityError("generated_file_escape_blocked")
        if path.exists():
            raise FileGenerationSecurityError("generated_file_exists")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _validate_relative_file(self, relative_path: str, content: str) -> None:
        path = Path(relative_path)
        if path.is_absolute() or ".." in path.parts:
            raise FileGenerationSecurityError("unsafe_generated_path")
        if path.name in DANGEROUS_NAMES or path.suffix.lower() in DANGEROUS_SUFFIXES:
            raise FileGenerationSecurityError("dangerous_file_blocked")
        lowered = content.lower()
        if any(marker in lowered for marker in DANGEROUS_CONTENT_MARKERS):
            raise FileGenerationSecurityError("dangerous_content_blocked")

    def _record(
        self,
        blueprint: dict,
        workspace: dict,
        *,
        status: str,
        reason: str | None,
        approval_status: str,
        generated_files: list[str],
        generated_directories: list[str],
        modules_created: list[str],
        timeline: list[dict],
    ) -> dict:
        return {
            "generation_id": f"gen-{uuid.uuid4()}",
            "request_id": workspace["request_id"],
            "workspace_id": workspace["workspace_id"],
            "blueprint_id": blueprint["blueprint_id"],
            "project_name": blueprint["project_name"],
            "project_type": blueprint["project_type"],
            "risk_level": blueprint["risk_level"],
            "status": status,
            "reason": reason,
            "approval_status": approval_status,
            "logical_path": workspace["logical_path"],
            "generated_files": generated_files,
            "generated_directories": generated_directories,
            "modules_created": modules_created,
            "dangerous_files_blocked": True,
            "workspace_isolated": True,
            "timeline": timeline,
            "created_at": utc_now(),
        }

    def _frontend_package_json(self, blueprint: dict) -> str:
        return json.dumps(
            {
                "name": self._slug(blueprint["project_name"]),
                "version": "0.1.0",
                "private": True,
                "type": "module",
                "scripts": {"dev": "vite", "build": "tsc -b && vite build", "preview": "vite preview"},
                "dependencies": {"@vitejs/plugin-react": "latest", "typescript": "latest", "vite": "latest", "react": "latest", "react-dom": "latest"},
                "devDependencies": {},
            },
            indent=2,
        )

    def _requirements(self) -> str:
        return "fastapi\nuvicorn\npydantic\n"

    def _project_readme(self, blueprint: dict, stack: str) -> str:
        return (
            f"# {blueprint['project_name']}\n\n"
            f"- Nombre: `{blueprint['project_name']}`\n"
            f"- Objetivo: {blueprint['objective']}\n"
            f"- Stack: `{stack}`\n"
            f"- Estructura: {', '.join(blueprint['suggested_structure'])}\n"
            "- Instrucciones: revisar, aprobar y ejecutar comandos manualmente en fases futuras.\n"
            f"- Riesgos: {', '.join(risk['title'] for risk in blueprint['risks'])}\n"
            "- Estado: `generated_controlled_files`\n"
            f"- Sender: `{blueprint['sender']}`\n"
            f"- Timestamp: `{utc_now()}`\n"
        )

    def _react_main(self) -> str:
        return "import React from 'react';\nimport ReactDOM from 'react-dom/client';\nimport App from './App';\n\nReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(<App />);\n"

    def _react_app(self, blueprint: dict) -> str:
        modules = ", ".join(blueprint["modules"][:4])
        return (
            "export default function App() {\n"
            "  return (\n"
            "    <main>\n"
            f"      <h1>{blueprint['project_name']}</h1>\n"
            f"      <p>{blueprint['objective']}</p>\n"
            f"      <small>Initial controlled modules: {modules}</small>\n"
            "    </main>\n"
            "  );\n"
            "}\n"
        )

    def _fastapi_main(self, blueprint: dict, route_resource: str | None = None) -> str:
        route_import = f"from app.routes.{route_resource} import router as {route_resource}_router\n" if route_resource else ""
        route_include = f"\napp.include_router({route_resource}_router)\n" if route_resource else ""
        return (
            "from fastapi import FastAPI\n"
            f"{route_import}\n"
            f"app = FastAPI(title='{blueprint['project_name']}')\n"
            f"{route_include}\n"
            "@app.get('/health')\n"
            "def health() -> dict:\n"
            "    return {'status': 'ok', 'mode': 'controlled_initial_files'}\n"
        )

    def _api_route(self, blueprint: dict, resource: str) -> str:
        return (
            "from fastapi import APIRouter\n\n"
            f"router = APIRouter(prefix='/{resource}', tags=['{resource}'])\n\n"
            "@router.get('')\n"
            "def list_items() -> dict:\n"
            f"    return {{'items': [], 'project': '{blueprint['project_name']}'}}\n"
        )

    def _api_schema(self, blueprint: dict) -> str:
        entity = blueprint["data_model"][0]
        return (
            "from pydantic import BaseModel\n\n"
            f"class {entity['name']}(BaseModel):\n"
            "    id: str\n"
            "    name: str | None = None\n"
        )

    def _api_service(self, blueprint: dict) -> str:
        return (
            "def list_records() -> list[dict]:\n"
            f"    return [{{'status': 'planned', 'project': '{blueprint['project_name']}'}}]\n"
        )

    def _kpi_card(self) -> str:
        return "export function KpiCard({ label, value }: { label: string; value: string }) {\n  return <article><span>{label}</span><strong>{value}</strong></article>;\n}\n"

    def _dashboard_page(self, blueprint: dict) -> str:
        return (
            "import { KpiCard } from '../components/KpiCard';\n\n"
            "export function DashboardPage() {\n"
            "  return (\n"
            "    <section>\n"
            f"      <h2>{blueprint['project_name']}</h2>\n"
            "      <KpiCard label='Status' value='Blueprint ready' />\n"
            "    </section>\n"
            "  );\n"
            "}\n"
        )

    def _module_contract(self, blueprint: dict) -> str:
        return f"# Interface Contract\n\nProject: {blueprint['project_name']}\n\nModules: {', '.join(blueprint['modules'])}\n"

    def _module_service(self, blueprint: dict) -> str:
        return f"# Service Plan\n\nObjective: {blueprint['objective']}\n"

    def _module_tests(self, blueprint: dict) -> str:
        return f"# Test Plan\n\nValidate module contract for {blueprint['project_name']} before implementation.\n"

    def _generated_directories(self, plan: list[tuple[str, str]]) -> list[str]:
        directories: list[str] = []
        for relative_path, _ in plan:
            path = Path(relative_path)
            for parent in path.parents:
                if str(parent) == ".":
                    continue
                value = str(parent).replace("\\", "/")
                if value not in directories:
                    directories.append(value)
        return directories

    def _modules_created(self, blueprint: dict) -> list[str]:
        if blueprint["project_type"] == "app":
            return ["frontend", "backend"]
        if blueprint["project_type"] == "api":
            return ["backend"]
        if blueprint["project_type"] == "dashboard":
            return ["frontend"]
        if blueprint["project_type"] == "module":
            return ["module"]
        return []

    def _logical_file(self, request_id: str, relative_path: str) -> str:
        return f".forja/workspaces/{request_id}/{relative_path}"

    def _resource_name(self, blueprint: dict) -> str:
        domain = blueprint["domain"]
        if domain == "WhatsApp":
            return "whatsapp"
        if domain == "RRHH":
            return "rrhh"
        if domain == "general":
            return self._slug(blueprint["project_type"]).replace("-", "_")
        return self._slug(domain).replace("-", "_")

    def _slug(self, value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "project"

    def _event(self, event: str, detail: str) -> dict:
        return {"timestamp": utc_now(), "event": event, "detail": detail}

    def _is_relative_to(self, child: Path, parent: Path) -> bool:
        try:
            child.relative_to(parent)
            return True
        except ValueError:
            return False


controlled_file_generator = ControlledFileGenerator()
