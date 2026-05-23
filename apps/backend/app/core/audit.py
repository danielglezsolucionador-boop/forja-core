from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any
import json
import uuid

from app.core.config import settings

_audit_lock = RLock()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_audit_event(event_type: str, actor: str, payload: dict[str, Any], risk: str = "low") -> dict[str, Any]:
    settings.audit_dir.mkdir(parents=True, exist_ok=True)
    path: Path = settings.audit_dir / "events.jsonl"
    with _audit_lock:
        event = {
            "id": str(uuid.uuid4()),
            "timestamp": utc_now(),
            "event_type": event_type,
            "actor": actor,
            "risk": risk,
            "payload": payload,
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event


def read_audit_events(limit: int = 100) -> list[dict[str, Any]]:
    path = settings.audit_dir / "events.jsonl"
    with _audit_lock:
        if not path.exists():
            return []
        lines = path.read_text(encoding="utf-8").splitlines()
    events = [json.loads(line) for line in lines if line.strip()]
    return events[-limit:]
