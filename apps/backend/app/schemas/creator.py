from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


CreatorSender = Literal["user", "cerebro"]
CreatorPipelineStatus = Literal[
    "received",
    "governance_check",
    "awaiting_approval",
    "approved",
    "blocked",
    "executing",
    "completed",
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


class CreatorPipelineStep(BaseModel):
    status: CreatorPipelineStatus
    label: str
    detail: str


class CreatorGovernanceSnapshot(BaseModel):
    risk_level: Literal["low", "medium", "high", "critical"]
    blocked_reason: str
    required_permissions: list[str]
    provider_status: str


class CreatorTimelineEvent(BaseModel):
    timestamp: str
    event: str
    detail: str


class CreatorOutput(BaseModel):
    kind: Literal["file", "module", "result", "structure"]
    name: str
    status: str


class CreatorCommandRecord(BaseModel):
    id: str
    timestamp: str
    sender: CreatorSender
    reply_to_sender: CreatorSender
    command: str
    details: str
    status: CreatorPipelineStatus
    response: str
    pipeline: list[CreatorPipelineStep]
    governance: CreatorGovernanceSnapshot
    timeline: list[CreatorTimelineEvent]
    outputs: list[CreatorOutput]


class CreatorConsoleState(BaseModel):
    mode: str
    provider_state: str
    command_statuses: list[CreatorPipelineStatus]
    commands: list[CreatorCommandRecord]
    audit_stream: list[dict]
