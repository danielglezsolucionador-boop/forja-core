from __future__ import annotations

import uuid

from app.core.audit import append_audit_event, utc_now
from app.core.storage import store


class GovernanceService:
    def __init__(self) -> None:
        self._store = store("approvals")

    def create_request(self, payload: dict, requested_by: str) -> dict:
        record = {
            "id": str(uuid.uuid4()),
            "timestamp": utc_now(),
            "status": "blocked" if payload["risk"] == "critical" else "pending",
            "requested_by": requested_by,
            "decided_by": None,
            "decision_reason": None,
            **payload,
        }
        self._store.update([], lambda records: records.append(record))
        append_audit_event("governance.request_created", requested_by, {"id": record["id"], "risk": record["risk"], "status": record["status"]}, risk=record["risk"])
        return record

    def decide(self, request_id: str, decision: str, reason: str, decided_by: str) -> dict | None:
        result: dict | None = None
        denied = False

        def mutate(records: list[dict]) -> None:
            nonlocal result, denied
            for record in records:
                if record["id"] == request_id:
                    if record["status"] == "blocked" and decision == "approved":
                        denied = True
                        result = dict(record)
                        return
                    record["status"] = decision
                    record["decided_by"] = decided_by
                    record["decision_reason"] = reason
                    result = dict(record)
                    return

        self._store.update([], mutate)
        if result is not None:
            if denied:
                append_audit_event("governance.approval_denied_for_blocked", decided_by, {"id": request_id}, risk="critical")
            else:
                append_audit_event("governance.request_decided", decided_by, {"id": request_id, "decision": decision}, risk=result["risk"])
        return result

    def list_requests(self, limit: int = 100) -> list[dict]:
        return self._store.read([])[-limit:]

    def is_approved(self, request_id: str) -> bool:
        return any(record["id"] == request_id and record["status"] == "approved" for record in self._store.read([]))


governance_service = GovernanceService()
