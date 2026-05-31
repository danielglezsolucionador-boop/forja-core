from __future__ import annotations

import uuid

from app.core.audit import append_audit_event, utc_now
from app.core.storage import store


class NotificationService:
    def __init__(self) -> None:
        self._store = store("notifications")

    def enqueue(self, title: str, message: str, severity: str, channel: str, metadata: dict[str, str]) -> dict:
        status = "queued" if channel == "local" else "blocked"
        record = {
            "id": str(uuid.uuid4()),
            "timestamp": utc_now(),
            "title": title,
            "message": message,
            "severity": severity,
            "channel": channel,
            "metadata": metadata,
            "status": status,
            "delivery_note": "local queue only" if channel == "local" else "external delivery requires provider approval",
        }
        def mutate(records: list[dict]) -> None:
            records.append(record)
            del records[:-500]

        self._store.update([], mutate)
        append_audit_event("notification.created", "system", {"id": record["id"], "channel": channel, "status": status}, risk="low" if status == "queued" else "medium")
        return record

    def recent(self, limit: int = 50) -> list[dict]:
        return self._store.read([])[-limit:]


notification_service = NotificationService()
