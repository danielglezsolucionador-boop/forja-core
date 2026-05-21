from __future__ import annotations

import uuid

from app.core.audit import append_audit_event, utc_now
from app.core.storage import store


class WorkflowService:
    def __init__(self) -> None:
        self._store = store("workflows")

    def create(self, payload: dict, actor: str) -> dict:
        record = {
            "id": str(uuid.uuid4()),
            "timestamp": utc_now(),
            "status": "created",
            "current_step": 0,
            "human_checkpoint_required": True,
            "audit_note": "workflow created; human checkpoint required before running",
            **payload,
        }
        records = self._store.read([])
        records.append(record)
        self._store.write(records)
        append_audit_event("workflow.created", actor, {"id": record["id"], "steps": len(record["steps"])}, risk="medium")
        return record

    def advance(self, workflow_id: str, checkpoint_acknowledged: bool, note: str, actor: str) -> dict | None:
        records = self._store.read([])
        for record in records:
            if record["id"] == workflow_id:
                if record["human_checkpoint_required"] and not checkpoint_acknowledged:
                    record["status"] = "blocked"
                    record["audit_note"] = "human checkpoint required"
                else:
                    record["human_checkpoint_required"] = False
                    if record["current_step"] + 1 >= len(record["steps"]):
                        record["status"] = "completed"
                    else:
                        record["status"] = "running"
                        record["current_step"] += 1
                    record["audit_note"] = note or "workflow advanced"
                self._store.write(records)
                append_audit_event("workflow.advanced", actor, {"id": workflow_id, "status": record["status"], "current_step": record["current_step"]}, risk="medium")
                return record
        return None

    def list(self, limit: int = 100) -> list[dict]:
        return self._store.read([])[-limit:]


workflow_service = WorkflowService()
