from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class OperationalStatus:
    status: str
    reason: str
    evidence: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class HealthContract:
    service: str
    version: str
    status: str
    modules: dict[str, str]
