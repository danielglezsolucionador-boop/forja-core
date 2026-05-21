from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Literal


AppKind = Literal["landing", "dashboard", "admin_panel", "saas_base", "api_service"]
FactoryStatus = Literal["draft", "approval_required", "approved", "executed", "blocked"]


class FactoryRequestIn(BaseModel):
    name: str
    app_kind: AppKind
    description: str
    modules: list[str] = Field(default_factory=list)


class FactoryRequestRecord(FactoryRequestIn):
    id: str
    timestamp: str
    status: FactoryStatus
    requested_by: str
    approval_request_id: str | None = None


class FactoryPlan(BaseModel):
    request_id: str
    status: str
    write_policy: str
    files: list[str]
    validation_gates: list[str]
    explanation: str


class FactoryExecuteIn(BaseModel):
    approval_request_id: str
    allow_write: bool = False


class FactoryExecutionRecord(BaseModel):
    id: str
    request_id: str
    timestamp: str
    status: Literal["blocked", "executed"]
    output_path: str | None
    reason: str
