"""local agent persistent registry and tasks

Revision ID: 0002_local_agent_persistence
Revises: 0001_precloud_foundation
Create Date: 2026-06-04
"""
from alembic import op
import sqlalchemy as sa


revision = "0002_local_agent_persistence"
down_revision = "0001_precloud_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "local_agent_agents",
        sa.Column("agent_id", sa.String(length=80), primary_key=True),
        sa.Column("agent_name", sa.String(length=160), nullable=False),
        sa.Column("machine_label", sa.String(length=160), nullable=False),
        sa.Column("machine_id", sa.String(length=160), nullable=True),
        sa.Column("version", sa.String(length=80), nullable=True),
        sa.Column("owner", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_local_agent_agents_status", "local_agent_agents", ["status"])
    op.create_index("ix_local_agent_agents_last_seen_at", "local_agent_agents", ["last_seen_at"])
    op.create_index("ix_local_agent_agents_machine_id", "local_agent_agents", ["machine_id"])

    op.create_table(
        "local_agent_tasks",
        sa.Column("task_id", sa.String(length=80), primary_key=True),
        sa.Column("agent_id", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("task_type", sa.String(length=80), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_local_agent_tasks_status", "local_agent_tasks", ["status"])
    op.create_index("ix_local_agent_tasks_agent_id", "local_agent_tasks", ["agent_id"])
    op.create_index("ix_local_agent_tasks_updated_at", "local_agent_tasks", ["updated_at"])


def downgrade() -> None:
    op.drop_table("local_agent_tasks")
    op.drop_table("local_agent_agents")
