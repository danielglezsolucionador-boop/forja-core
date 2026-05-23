from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


CreatorSender = Literal["user", "cerebro", "seo", "system"]
CreatorRequestType = Literal["app", "api", "module", "workflow", "document", "integration"]
CreatorOutputType = Literal[
    "proposed_app_structure",
    "api_blueprint",
    "module_plan",
    "workflow_plan",
    "document_blueprint",
    "integration_plan",
    "blocked_action_report",
    "execution_summary",
]
CreatorPipelineStatus = Literal[
    "received",
    "governance_check",
    "awaiting_approval",
    "approved",
    "executing",
    "completed",
    "blocked",
    "failed",
]
CreatorDecision = Literal["approve", "reject", "hold"]


class CreatorCommandIn(BaseModel):
    sender: CreatorSender = "user"
    command: str = Field(min_length=3, max_length=240)
    details: str = Field(default="", max_length=4000)


class CreatorDecisionIn(BaseModel):
    decision: CreatorDecision
    reason: str = Field(default="", max_length=1000)


class CreatorExecuteIn(BaseModel):
    metadata_only: bool = True


class CreatorOutputAssociateIn(BaseModel):
    output_type: CreatorOutputType = "execution_summary"
    title: str = Field(default="Associated metadata output", max_length=140)
    summary: str = Field(default="metadata_only_output", max_length=1200)
    status: str = Field(default="associated_metadata_only", max_length=80)
    content: dict[str, Any] = Field(default_factory=dict)


class CreatorPipelineStep(BaseModel):
    status: CreatorPipelineStatus
    label: str
    detail: str


class CreatorGovernanceSnapshot(BaseModel):
    risk_level: Literal["low", "medium", "high", "critical"]
    blocked_reason: str | None = None
    required_permissions: list[str]
    provider_status: str
    approval_status: Literal["not_required", "pending", "approved", "rejected", "held"]


class CreatorTimelineEvent(BaseModel):
    timestamp: str
    event: str
    detail: str


class CreatorExecutionLog(BaseModel):
    timestamp: str
    level: Literal["info", "warning", "error"]
    message: str


class CreatorOutput(BaseModel):
    id: str
    request_id: str
    sender: CreatorSender
    output_type: CreatorOutputType
    kind: Literal["file", "module", "result", "structure", "metadata", "log", "report", "blueprint", "plan", "summary"]
    name: str
    title: str
    status: str
    mode: Literal["metadata_only_output"]
    summary: str
    produced: list[str]
    not_produced: list[str]
    blocked: list[str]
    content: dict[str, Any]
    downloadable: bool
    created_at: str


class CreatorCommandRecord(BaseModel):
    id: str
    timestamp: str
    sender: CreatorSender
    reply_to_sender: CreatorSender
    command: str
    details: str
    request_type: CreatorRequestType
    status: CreatorPipelineStatus
    response: str
    plan: list[str]
    pipeline: list[CreatorPipelineStep]
    governance: CreatorGovernanceSnapshot
    timeline: list[CreatorTimelineEvent]
    execution_logs: list[CreatorExecutionLog]
    outputs: list[CreatorOutput]


class CreatorConsoleState(BaseModel):
    mode: str
    provider_state: str
    command_statuses: list[CreatorPipelineStatus]
    commands: list[CreatorCommandRecord]
    outputs: list[CreatorOutput]
    audit_stream: list[dict]
