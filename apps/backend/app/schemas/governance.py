from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Literal


RiskLevel = Literal["low", "medium", "high", "critical"]
DecisionStatus = Literal["pending", "approved", "blocked", "rejected"]


class ApprovalRequestIn(BaseModel):
    scope: str
    action: str
    risk: RiskLevel = "medium"
    reason: str
    metadata: dict[str, str] = Field(default_factory=dict)


class ApprovalDecisionIn(BaseModel):
    decision: Literal["approved", "rejected"]
    reason: str


class ApprovalRecord(ApprovalRequestIn):
    id: str
    timestamp: str
    status: DecisionStatus
    requested_by: str
    decided_by: str | None = None
    decision_reason: str | None = None
