from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


TaskType = Literal[
    "read",
    "diagnosis",
    "report_generation",
    "controlled_edit",
    "build",
    "test",
    "audit",
    "commit_prepare",
    "commit_execute",
    "push",
    "deploy",
    "rollback",
]
TaskStatus = Literal[
    "draft",
    "submitted",
    "classified",
    "awaiting_human_approval",
    "awaiting_critical_approval",
    "approved",
    "queued",
    "leased",
    "snapshotting",
    "backing_up",
    "preparing_workspace",
    "running",
    "uploading_results",
    "completed",
    "failed",
    "blocked",
    "cancelled",
    "rollback_available",
    "rolling_back",
    "rolled_back",
]
RiskLevel = Literal["low", "medium", "high", "critical"]


class LocalAgentRegisterIn(BaseModel):
    agent_name: str = Field(min_length=2, max_length=120)
    machine_label: str = Field(min_length=2, max_length=120)
    owner: str = Field(default="ceo", max_length=80)
    capability_profile: list[str] = Field(default_factory=list)
    allowed_repositories: list[str] = Field(default_factory=list)
    allowed_workspaces: list[str] = Field(default_factory=list)
    policy_profile: str = "default"


class LocalAgentRecord(BaseModel):
    agent_id: str
    agent_name: str
    machine_label: str
    owner: str
    status: str
    last_seen_at: str | None = None
    capability_profile: list[str]
    allowed_repositories: list[str]
    allowed_workspaces: list[str]
    policy_profile: str
    created_at: str
    revoked_at: str | None = None
    agent_token: str | None = None


class LocalAgentTaskIn(BaseModel):
    instruction: str = Field(min_length=3, max_length=4000)
    title: str | None = Field(default=None, max_length=160)
    requested_by: str = Field(default="ceo", max_length=80)
    source: str = Field(default="human_cabin", max_length=80)
    priority: str = Field(default="normal", max_length=40)
    target: dict[str, Any] = Field(default_factory=dict)
    desired_output: str = Field(default="result", max_length=80)


class LocalAgentTaskRecord(BaseModel):
    task_id: str
    title: str
    instruction: str
    source: str
    requested_by: str
    created_at: str
    updated_at: str
    status: TaskStatus
    priority: str
    risk_level: RiskLevel
    task_type: TaskType
    capabilities_required: list[str]
    target: dict[str, Any]
    policy: dict[str, Any]
    assigned_agent_id: str | None = None
    lease: dict[str, Any] | None = None
    approvals: list[dict[str, Any]] = Field(default_factory=list)
    history: list[dict[str, Any]] = Field(default_factory=list)
    snapshots: list[dict[str, Any]] = Field(default_factory=list)
    backups: list[dict[str, Any]] = Field(default_factory=list)
    rollback: dict[str, Any] | None = None
    command_logs: list[dict[str, Any]] = Field(default_factory=list)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    result: dict[str, Any] | None = None


class LocalAgentTaskPollIn(BaseModel):
    capabilities: list[str] = Field(default_factory=list)
    available_repositories: list[str] = Field(default_factory=list)
    max_tasks: int = Field(default=1, ge=1, le=5)


class LocalAgentLeaseRecord(BaseModel):
    lease_id: str
    task_id: str
    agent_id: str
    leased_at: str
    expires_at: str
    heartbeat_at: str
    renewal_count: int
    task: dict[str, Any]


class LocalAgentApprovalIn(BaseModel):
    approved_by: str = Field(default="ceo", max_length=80)
    reason: str = Field(default="", max_length=1000)
    action: str | None = Field(default=None, max_length=120)
    exact_target: dict[str, Any] = Field(default_factory=dict)


class LocalAgentEventIn(BaseModel):
    event_type: str = Field(min_length=2, max_length=160)
    payload: dict[str, Any] = Field(default_factory=dict)
    risk: RiskLevel = "low"
    idempotency_key: str | None = Field(default=None, max_length=200)


class LocalAgentSnapshotIn(BaseModel):
    snapshot: dict[str, Any]


class LocalAgentBackupIn(BaseModel):
    backup: dict[str, Any]


class LocalAgentRollbackIn(BaseModel):
    rollback: dict[str, Any]


class LocalAgentCommandLogIn(BaseModel):
    command_log: dict[str, Any]


class LocalAgentArtifactIn(BaseModel):
    artifact: dict[str, Any]


class LocalAgentResultIn(BaseModel):
    result: dict[str, Any]


class LocalAgentDashboard(BaseModel):
    agents: dict[str, Any]
    tasks: dict[str, Any]
    latest_results: list[dict[str, Any]]
    critical_approvals: list[dict[str, Any]]
    deliveries: list[dict[str, Any]]
    rollbacks_available: list[dict[str, Any]]
    recent_activity: list[dict[str, Any]]
