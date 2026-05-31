from __future__ import annotations

from pathlib import Path
import json
import re
import uuid

from app.core.audit import append_audit_event, utc_now
from app.core.config import settings
from app.core.storage import store
from app.services.governance_service import governance_service


class FactoryService:
    def __init__(self) -> None:
        self._requests = store("factory_requests")
        self._executions = store("factory_executions")

    def create_request(self, payload: dict, requested_by: str) -> dict:
        record = {
            "id": str(uuid.uuid4()),
            "timestamp": utc_now(),
            "status": "approval_required",
            "requested_by": requested_by,
            "approval_request_id": None,
            **payload,
        }
        approval = governance_service.create_request(
            {
                "scope": "factory.execution",
                "action": f"prepare {payload['app_kind']} output for {payload['name']}",
                "risk": "medium",
                "reason": "FORJA factory execution requires human approval before writes",
                "metadata": {"factory_request_id": record["id"]},
            },
            requested_by,
        )
        record["approval_request_id"] = approval["id"]
        self._requests.update([], lambda records: records.append(record))
        append_audit_event("factory.request_created", requested_by, {"id": record["id"], "approval_request_id": approval["id"]}, risk="medium")
        return record

    def list_requests(self, limit: int = 100) -> list[dict]:
        return self._requests.read([])[-limit:]

    def get_request(self, request_id: str) -> dict | None:
        return next((record for record in self._requests.read([]) if record["id"] == request_id), None)

    def build_plan(self, request_id: str) -> dict | None:
        request = self.get_request(request_id)
        if request is None:
            return None
        slug = self._slug(request["name"])
        files = [
            f"{slug}/README.md",
            f"{slug}/metadata.json",
            f"{slug}/validation-plan.json",
        ]
        return {
            "request_id": request_id,
            "status": "preview_only",
            "write_policy": "zero_write_until_human_approval",
            "files": files,
            "validation_gates": ["structure", "contracts", "governance", "audit"],
            "explanation": "This plan is inspectable and does not write generated app files until an approval request is approved and allow_write is true.",
        }

    def execute(self, request_id: str, approval_request_id: str, allow_write: bool) -> dict | None:
        request = self.get_request(request_id)
        if request is None:
            return None
        execution = {
            "id": str(uuid.uuid4()),
            "request_id": request_id,
            "timestamp": utc_now(),
            "status": "blocked",
            "output_path": None,
            "reason": "execution requires approved governance request and allow_write=true",
        }
        if allow_write and governance_service.is_approved(approval_request_id):
            output_dir = settings.outputs_dir / self._slug(request["name"])
            output_dir.mkdir(parents=True, exist_ok=True)
            manifest = {
                "factory_request": request,
                "generated_at": utc_now(),
                "status": "metadata_only",
                "note": "FORJA created an approved output package manifest, not a production app deployment.",
            }
            (output_dir / "metadata.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            (output_dir / "README.md").write_text(f"# {request['name']}\n\nApproved FORJA output package.\n", encoding="utf-8")
            (output_dir / "validation-plan.json").write_text(json.dumps({"gates": ["structure", "contracts", "governance", "audit"]}, indent=2), encoding="utf-8")
            execution["status"] = "executed"
            execution["output_path"] = str(output_dir)
            execution["reason"] = "approved metadata output package created"
        self._executions.update([], lambda executions: executions.append(execution))
        append_audit_event("factory.execution_attempted", "system", execution, risk="medium")
        return execution

    def list_executions(self, limit: int = 100) -> list[dict]:
        return self._executions.read([])[-limit:]

    def _slug(self, value: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9-]+", "-", value.strip().lower()).strip("-")
        return slug or "forja-output"


factory_service = FactoryService()
