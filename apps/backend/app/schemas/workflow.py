from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Literal


WorkflowStatus = Literal["created", "running", "blocked", "completed", "failed"]


class WorkflowIn(BaseModel):
    name: str
    objective: str
    steps: list[str] = Field(min_length=1)


class WorkflowRecord(WorkflowIn):
    id: str
    timestamp: str
    status: WorkflowStatus
    current_step: int
    human_checkpoint_required: bool
    audit_note: str


class WorkflowAdvanceIn(BaseModel):
    checkpoint_acknowledged: bool = False
    note: str = ""
