from __future__ import annotations

import uuid

from app.core.audit import append_audit_event, utc_now
from app.core.storage import store


class AIPipelineService:
    def __init__(self) -> None:
        self._store = store("ai_pipeline_requests")

    def create_request(self, payload: dict, requested_by: str) -> dict:
        record = {
            "id": str(uuid.uuid4()),
            "timestamp": utc_now(),
            "requested_by": requested_by,
            "status": "blocked_provider_disabled",
            "provider_id": "ai.local-disabled",
            "explanation": "AI pipeline request recorded, but external provider execution is disabled in local FORJA.",
            **payload,
        }
        def mutate(records: list[dict]) -> None:
            records.append(record)
            del records[:-500]

        self._store.update([], mutate)
        append_audit_event("ai_pipeline.request_blocked", requested_by, {"id": record["id"], "provider_id": record["provider_id"]}, risk="medium")
        return record

    def list_requests(self, limit: int = 100) -> list[dict]:
        return self._store.read([])[-limit:]


ai_pipeline_service = AIPipelineService()
