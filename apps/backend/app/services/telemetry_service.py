from __future__ import annotations

from typing import Any
import uuid

from app.core.audit import append_audit_event, utc_now
from app.core.storage import store


class TelemetryService:
    def __init__(self) -> None:
        self._store = store("telemetry")

    def record(self, event_name: str, source: str, severity: str, metadata: dict[str, Any]) -> dict[str, Any]:
        event = {
            "id": str(uuid.uuid4()),
            "timestamp": utc_now(),
            "event_name": event_name,
            "source": source,
            "severity": severity,
            "metadata": self._redact(metadata),
        }
        events = self._store.read([])
        events.append(event)
        self._store.write(events[-500:])
        append_audit_event("telemetry.recorded", source, {"event_name": event_name, "severity": severity})
        return event

    def recent(self, limit: int = 50) -> list[dict[str, Any]]:
        events = self._store.read([])
        return events[-limit:]

    def _redact(self, payload: dict[str, Any]) -> dict[str, Any]:
        blocked = {"token", "password", "secret", "api_key", "authorization"}
        redacted: dict[str, Any] = {}
        for key, value in payload.items():
            redacted[key] = "[redacted]" if key.lower() in blocked else value
        return redacted


telemetry_service = TelemetryService()
