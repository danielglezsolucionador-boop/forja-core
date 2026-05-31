from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.schemas.blueprint import ProjectBlueprint
from app.schemas.intent import IntentDomain, IntentRequestType, IntentResponseTarget, IntentRiskLevel, IntentSender


WorkspaceStatus = Literal["created", "blocked"]
WorkspaceApprovalStatus = Literal["not_required", "pending"]


class WorkspaceCreateIn(BaseModel):
    blueprint: ProjectBlueprint


class WorkspaceTimelineEvent(BaseModel):
    timestamp: str
    event: str
    detail: str


class WorkspaceCreationRecord(BaseModel):
    workspace_id: str
    request_id: str
    blueprint_id: str
    sender: IntentSender
    response_target: IntentResponseTarget
    project_name: str
    project_type: IntentRequestType
    domain: IntentDomain
    risk_level: IntentRiskLevel
    approval_required: bool
    approval_status: WorkspaceApprovalStatus
    status: WorkspaceStatus
    logical_path: str
    directories: list[str]
    files: list[str]
    workspace_isolated: bool
    complex_generation_allowed: bool
    timeline: list[WorkspaceTimelineEvent]
    created_at: str
