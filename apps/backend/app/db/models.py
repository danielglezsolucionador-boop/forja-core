from __future__ import annotations

from sqlalchemy import DateTime, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(120), index=True)
    actor: Mapped[str] = mapped_column(String(120), index=True)
    risk: Mapped[str] = mapped_column(String(32), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    scope: Mapped[str] = mapped_column(String(120), index=True)
    action: Mapped[str] = mapped_column(Text)
    risk: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    requested_by: Mapped[str] = mapped_column(String(120), index=True)
    decided_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class FactoryRequest(Base):
    __tablename__ = "factory_requests"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(180), index=True)
    app_kind: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    requested_by: Mapped[str] = mapped_column(String(120), index=True)
    approval_request_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    spec: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(180), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    human_checkpoint_required: Mapped[bool] = mapped_column(default=True)
    spec: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class AIPipelineRequest(Base):
    __tablename__ = "ai_pipeline_requests"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    requested_by: Mapped[str] = mapped_column(String(120), index=True)
    status: Mapped[str] = mapped_column(String(64), index=True)
    provider_id: Mapped[str] = mapped_column(String(120), index=True)
    objective: Mapped[str] = mapped_column(Text)
    spec: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class LocalAgentAgent(Base):
    __tablename__ = "local_agent_agents"

    agent_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    agent_name: Mapped[str] = mapped_column(String(160), index=True)
    machine_label: Mapped[str] = mapped_column(String(160), index=True)
    machine_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    owner: Mapped[str] = mapped_column(String(120), index=True)
    status: Mapped[str] = mapped_column(String(40), index=True)
    last_seen_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    token_hash: Mapped[str] = mapped_column(String(128))
    capabilities: Mapped[list] = mapped_column(JSON, default=list)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LocalAgentTask(Base):
    __tablename__ = "local_agent_tasks"

    task_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    agent_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(40), index=True)
    task_type: Mapped[str] = mapped_column(String(80), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), index=True)
    completed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
