from __future__ import annotations

from pathlib import Path
import json
import tempfile
from typing import Any

from app.core.config import settings


class JsonStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def read(self, default: Any) -> Any:
        if not self.path.exists():
            return default
        with self.path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def write(self, payload: Any) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=self.path.parent) as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            temp_name = handle.name
        Path(temp_name).replace(self.path)


def store(name: str) -> JsonStore:
    return JsonStore(settings.state_dir / f"{name}.json")
