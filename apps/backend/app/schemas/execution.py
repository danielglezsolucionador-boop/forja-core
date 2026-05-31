from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.blueprint import ProjectBlueprint
from app.schemas.generation import FileGenerationRecord
from app.schemas.intent import IntentInterpretation, IntentRecipient, IntentRiskLevel, IntentSender
from app.schemas.workspace import WorkspaceCreationRecord, WorkspaceTimelineEvent


ExecutionState = Literal[
    "pending",
    "interpreted",
    "blueprint_ready",
    "awaiting_approval",
    "approved",
    "generating",
    "completed",
    "blocked",
    "failed",
    "duplicate_blocked",
]
ExecutionApprovalStatus = Literal["not_required", "requested", "approved", "rejected", "blocked"]
ExecutionApprovalDecision = Literal["approve", "reject"]
ExecutionOutputKind = Literal[
    "readme",
    "blueprint",
    "architecture",
    "execution_report",
    "generated_file",
    "generated_directory",
    "module",
    "workspace",
]


class GovernedExecutionStartIn(BaseModel):
    sender: IntentSender = "ceo"
    recipient: IntentRecipient = "forja"
    input: str = Field(min_length=1, max_length=4000)
    source_request_id: str | None = Field(default=None, max_length=120)


class GovernedExecutionApprovalIn(BaseModel):
    decision: ExecutionApprovalDecision
    decided_by: str = Field(default="ceo", max_length=80)
    high_risk_authorization: bool = False


class ExecutionOutput(BaseModel):
    kind: ExecutionOutputKind
    label: str
    logical_path: str
    status: str
    source: str


class ExecutionAuditPreview(BaseModel):
    event_type: str
    actor: str
    risk: str
    timestamp: str


class GovernedExecutionRecord(BaseModel):
    execution_id: str
    request_id: str
    idempotency_key: str
    sender: IntentSender
    recipient: IntentRecipient
    response_target: str
    raw_input: str
    normalized_input: str
    request_type: str
    domain: str
    project_name: str | None = None
    risk_level: IntentRiskLevel | None = None
    state: ExecutionState
    reason: str | None = None
    approval_required: bool
    approval_status: ExecutionApprovalStatus
    duplicate_of: str | None = None
    workspace_isolated: bool
    parallel_execution_blocked: bool
    governance_bypass_blocked: bool
    interpretation: IntentInterpretation | None = None
    blueprint: ProjectBlueprint | None = None
    workspace: WorkspaceCreationRecord | None = None
    generation: FileGenerationRecord | None = None
    outputs: list[ExecutionOutput]
    timeline: list[WorkspaceTimelineEvent]
    audit_events: list[ExecutionAuditPreview]
    created_at: str
    updated_at: str
