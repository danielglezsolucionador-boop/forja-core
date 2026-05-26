from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.schemas.blueprint import ProjectBlueprint
from app.schemas.workspace import WorkspaceCreationRecord, WorkspaceTimelineEvent


GenerationStatus = Literal["completed", "blocked", "duplicate_blocked"]
GenerationApprovalStatus = Literal["not_required", "approved", "required", "blocked"]


class FileGenerationIn(BaseModel):
    blueprint: ProjectBlueprint
    workspace: WorkspaceCreationRecord
    manual_approval: bool = False


class FileGenerationRecord(BaseModel):
    generation_id: str
    request_id: str
    workspace_id: str
    blueprint_id: str
    project_name: str
    project_type: str
    risk_level: str
    status: GenerationStatus
    reason: str | None = None
    approval_status: GenerationApprovalStatus
    logical_path: str
    generated_files: list[str]
    generated_directories: list[str]
    modules_created: list[str]
    dangerous_files_blocked: bool
    workspace_isolated: bool
    timeline: list[WorkspaceTimelineEvent]
    created_at: str
