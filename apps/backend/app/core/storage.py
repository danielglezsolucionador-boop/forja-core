from __future__ import annotations

from pathlib import Path
import json
import tempfile
from threading import RLock
from typing import Any

from app.core.config import settings

_locks: dict[Path, RLock] = {}
_locks_guard = RLock()


def _lock_for(path: Path) -> RLock:
    resolved = path.resolve()
    with _locks_guard:
        if resolved not in _locks:
            _locks[resolved] = RLock()
        return _locks[resolved]


class JsonStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = _lock_for(path)

    def read(self, default: Any) -> Any:
        with self._lock:
            return self._read_unlocked(default)

    def write(self, payload: Any) -> None:
        with self._lock:
            self._write_unlocked(payload)

    def update(self, default: Any, mutator):
        with self._lock:
            payload = self._read_unlocked(default)
            result = mutator(payload)
            self._write_unlocked(payload)
            return result

    def _read_unlocked(self, default: Any) -> Any:
        if not self.path.exists():
            return default
        with self.path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _write_unlocked(self, payload: Any) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=self.path.parent) as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            temp_name = handle.name
        Path(temp_name).replace(self.path)


def store(name: str) -> JsonStore:
    return JsonStore(settings.state_dir / f"{name}.json")
