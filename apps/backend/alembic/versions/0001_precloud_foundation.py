"""precloud foundation

Revision ID: 0001_precloud_foundation
Revises:
Create Date: 2026-05-21
"""
from alembic import op
import sqlalchemy as sa


revision = "0001_precloud_foundation"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("actor", sa.String(length=120), nullable=False),
        sa.Column("risk", sa.String(length=32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_events_event_type", "audit_events", ["event_type"])
    op.create_index("ix_audit_events_actor", "audit_events", ["actor"])
    op.create_index("ix_audit_events_risk", "audit_events", ["risk"])
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])

    op.create_table(
        "approval_requests",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("scope", sa.String(length=120), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("risk", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("requested_by", sa.String(length=120), nullable=False),
        sa.Column("decided_by", sa.String(length=120), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_approval_requests_scope", "approval_requests", ["scope"])
    op.create_index("ix_approval_requests_status", "approval_requests", ["status"])
    op.create_index("ix_approval_requests_requested_by", "approval_requests", ["requested_by"])

    op.create_table(
        "factory_requests",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("app_kind", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("requested_by", sa.String(length=120), nullable=False),
        sa.Column("approval_request_id", sa.String(length=64), nullable=True),
        sa.Column("spec", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_factory_requests_name", "factory_requests", ["name"])
    op.create_index("ix_factory_requests_status", "factory_requests", ["status"])
    op.create_index("ix_factory_requests_approval_request_id", "factory_requests", ["approval_request_id"])

    op.create_table(
        "workflow_runs",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("current_step", sa.Integer(), nullable=False),
        sa.Column("human_checkpoint_required", sa.Boolean(), nullable=False),
        sa.Column("spec", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_workflow_runs_name", "workflow_runs", ["name"])
    op.create_index("ix_workflow_runs_status", "workflow_runs", ["status"])

    op.create_table(
        "ai_pipeline_requests",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("requested_by", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("provider_id", sa.String(length=120), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("spec", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ai_pipeline_requests_requested_by", "ai_pipeline_requests", ["requested_by"])
    op.create_index("ix_ai_pipeline_requests_status", "ai_pipeline_requests", ["status"])
    op.create_index("ix_ai_pipeline_requests_provider_id", "ai_pipeline_requests", ["provider_id"])


def downgrade() -> None:
    op.drop_table("ai_pipeline_requests")
    op.drop_table("workflow_runs")
    op.drop_table("factory_requests")
    op.drop_table("approval_requests")
    op.drop_table("audit_events")
