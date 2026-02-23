"""add cases and activity logs

Revision ID: a3b1c2d4e5f6
Revises: 98ab619418bc
Create Date: 2025-01-01 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "a3b1c2d4e5f6"
down_revision: Union[str, None] = "98ab619418bc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cases",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("severity", sa.String(16), server_default="medium"),
        sa.Column("tlp", sa.String(16), server_default="amber"),
        sa.Column("pap", sa.String(16), server_default="amber"),
        sa.Column("status", sa.String(24), server_default="open"),
        sa.Column("priority", sa.Integer, server_default="2"),
        sa.Column("assignee", sa.String(128), nullable=True),
        sa.Column("tags", sa.JSON, nullable=True),
        sa.Column("hunt_id", sa.String(32), sa.ForeignKey("hunts.id"), nullable=True),
        sa.Column("owner_id", sa.String(32), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("mitre_techniques", sa.JSON, nullable=True),
        sa.Column("iocs", sa.JSON, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_cases_hunt", "cases", ["hunt_id"])
    op.create_index("ix_cases_status", "cases", ["status"])

    op.create_table(
        "case_tasks",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("case_id", sa.String(32), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("status", sa.String(24), server_default="todo"),
        sa.Column("assignee", sa.String(128), nullable=True),
        sa.Column("order", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_case_tasks_case", "case_tasks", ["case_id"])

    op.create_table(
        "activity_logs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column("entity_id", sa.String(32), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("details", sa.JSON, nullable=True),
        sa.Column("user_id", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_activity_entity", "activity_logs", ["entity_type", "entity_id"])


def downgrade() -> None:
    op.drop_table("activity_logs")
    op.drop_table("case_tasks")
    op.drop_table("cases")
