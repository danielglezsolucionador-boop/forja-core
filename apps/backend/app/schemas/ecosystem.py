from __future__ import annotations

from pydantic import BaseModel


class EcosystemIntegration(BaseModel):
    id: str
    status: str
    mode: str
    owner: str
    boundary: str
