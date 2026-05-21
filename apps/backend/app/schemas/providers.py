from __future__ import annotations

from pydantic import BaseModel
from typing import Literal


ProviderStatus = Literal["disabled", "available", "degraded", "blocked"]


class ProviderRecord(BaseModel):
    id: str
    kind: str
    status: ProviderStatus
    reason: str
    timeout_ms: int
    retry_limit: int
