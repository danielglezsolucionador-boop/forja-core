from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
MEMORY_ROOT = REPO_ROOT / "docs" / "ecosystem-memory"
CORE_MEMORY_ROOT = MEMORY_ROOT / "core"
PRIMARY_MEMORY_PATH = CORE_MEMORY_ROOT / "FORJA_PHASE2_DECISION_TRACE.md"
ADDITIONAL_MEMORY_PATHS = [
    CORE_MEMORY_ROOT / "LONGITUDINAL_ECOSYSTEM_MEMORY.md",
    CORE_MEMORY_ROOT / "MEMORY_SYSTEM.md",
    CORE_MEMORY_ROOT / "OPERATIONAL_MEMORY.md",
]
APPS_ROOT = MEMORY_ROOT / "apps"


@dataclass(frozen=True)
class MemorySource:
    path: str
    name: str
    exists: bool
    last_modified: str | None
    size_bytes: int
    text: str


class EcosystemMemoryService:
    def snapshot(self) -> dict:
        sources = [self._read_source(PRIMARY_MEMORY_PATH)]
        sources.extend(self._read_source(path) for path in ADDITIONAL_MEMORY_PATHS)
        registered_apps = self._registered_apps()
        primary_text = sources[0].text
        apps_in_primary = self._apps_mentioned(primary_text, registered_apps)
        missing_from_primary = [app for app in registered_apps if app not in apps_in_primary]
        profile_counts = self._profile_counts(registered_apps)
        active_apps = [app for app in registered_apps if profile_counts.get(app, 0) > 0]
        return {
            "connected": any(source.exists for source in sources),
            "primary_source": sources[0].__dict__,
            "additional_sources": [source.__dict__ for source in sources[1:]],
            "registered_apps": registered_apps,
            "apps_in_primary_memory": apps_in_primary,
            "apps_missing_from_primary_memory": missing_from_primary,
            "active_apps": active_apps,
            "profile_counts": profile_counts,
            "priorities": self._priority_lines(primary_text),
            "blockers": self._blocker_lines(primary_text),
            "construction": self._construction_lines(primary_text),
        }

    def prompt_context(self, snapshot: dict | None = None) -> str:
        if snapshot is None:
            snapshot = self.snapshot()
        sources = [snapshot["primary_source"], *snapshot["additional_sources"]]
        source_names = [
            f"{source['name']} ({source['path']}; modified={source['last_modified'] or 'missing'})"
            for source in sources
            if source["exists"]
        ]
        lines = [
            "MEMORIA REAL DEL ECOSISTEMA (read-only; no inventar archivos).",
            "Fuentes conectadas: " + "; ".join(source_names),
            "Apps registradas en docs/ecosystem-memory/apps: " + self._join(snapshot["registered_apps"]),
            "Apps activas con perfiles existentes: " + self._join(snapshot["active_apps"]),
            "Apps mencionadas en memoria maestra: " + self._join(snapshot["apps_in_primary_memory"]),
            "Apps existentes que faltan en memoria maestra: " + self._join(snapshot["apps_missing_from_primary_memory"]),
            "Que estamos construyendo: " + self._join(snapshot["construction"]),
            "Prioridades reales: " + self._join(snapshot["priorities"]),
            "Bloqueos/riesgos reales: " + self._join(snapshot["blockers"]),
            "Si el usuario pregunta por ecosistema, responde solo desde estos datos y di cuando algo no esta registrado.",
        ]
        context = "\n".join(lines)
        return context[:1400]

    def _read_source(self, path: Path) -> MemorySource:
        if not path.exists() or not path.is_file():
            return MemorySource(str(path), path.name, False, None, 0, "")
        stat = path.stat()
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="utf-8", errors="replace")
        return MemorySource(
            path=self._display_path(path),
            name=path.name,
            exists=True,
            last_modified=self._format_mtime(stat.st_mtime),
            size_bytes=stat.st_size,
            text=text,
        )

    def _registered_apps(self) -> list[str]:
        if not APPS_ROOT.exists() or not APPS_ROOT.is_dir():
            return []
        return sorted(path.name for path in APPS_ROOT.iterdir() if path.is_dir())

    def _profile_counts(self, apps: list[str]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for app in apps:
            app_path = APPS_ROOT / app
            if not app_path.exists():
                counts[app] = 0
                continue
            counts[app] = sum(1 for path in app_path.rglob("*.md") if path.is_file())
        return counts

    def _apps_mentioned(self, text: str, apps: list[str]) -> list[str]:
        normalized = self._normalize(text)
        mentioned: list[str] = []
        for app in apps:
            candidates = {app, app.replace("_", " "), app.replace("_", "-")}
            if app == "CENTINELA":
                candidates.add("SENTINELA")
            if any(self._normalize(candidate) in normalized for candidate in candidates):
                mentioned.append(app)
        return mentioned

    def _priority_lines(self, text: str) -> list[str]:
        return self._bullets_after(text, ["## Risk Resolved", "## Protected", "## CEO Override"], limit=7)

    def _blocker_lines(self, text: str) -> list[str]:
        return self._bullets_after(text, ["## Risk Resolved"], limit=5)

    def _construction_lines(self, text: str) -> list[str]:
        return self._bullets_after(text, ["## Impact", "## Replaced"], limit=6)

    def _bullets_after(self, text: str, headings: list[str], limit: int) -> list[str]:
        lines = text.splitlines()
        captured: list[str] = []
        active = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("## "):
                active = stripped in headings
                continue
            if active and stripped.startswith("- "):
                captured.append(stripped[2:].strip())
            if len(captured) >= limit:
                break
        return captured

    def _normalize(self, value: str) -> str:
        return " ".join(value.upper().replace("_", " ").replace("-", " ").split())

    def _join(self, items: list[str]) -> str:
        return ", ".join(items) if items else "no registrado"

    def _format_mtime(self, mtime: float) -> str:
        from datetime import datetime

        return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")

    def _display_path(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(REPO_ROOT).as_posix()
        except ValueError:
            return path.name


ecosystem_memory_service = EcosystemMemoryService()
