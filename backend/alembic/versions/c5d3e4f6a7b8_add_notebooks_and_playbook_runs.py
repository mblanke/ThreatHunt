"""add notebooks and playbook_runs tables

Revision ID: c5d3e4f6a7b8
Revises: b4c2d3e5f6a7
Create Date: 2025-01-01 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "c5d3e4f6a7b8"
down_revision: Union[str, None] = "b4c2d3e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notebooks",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("cells", sa.JSON, nullable=True),
        sa.Column("hunt_id", sa.String(32), sa.ForeignKey("hunts.id"), nullable=True),
        sa.Column("case_id", sa.String(32), sa.ForeignKey("cases.id"), nullable=True),
        sa.Column("owner_id", sa.String(32), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("tags", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_notebooks_hunt", "notebooks", ["hunt_id"])

    op.create_table(
        "playbook_runs",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("playbook_name", sa.String(256), nullable=False),
        sa.Column("status", sa.String(24), server_default="in-progress"),
        sa.Column("current_step", sa.Integer, server_default="1"),
        sa.Column("total_steps", sa.Integer, server_default="0"),
        sa.Column("step_results", sa.JSON, nullable=True),
        sa.Column("hunt_id", sa.String(32), sa.ForeignKey("hunts.id"), nullable=True),
        sa.Column("case_id", sa.String(32), sa.ForeignKey("cases.id"), nullable=True),
        sa.Column("started_by", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_playbook_runs_hunt", "playbook_runs", ["hunt_id"])
    op.create_index("ix_playbook_runs_status", "playbook_runs", ["status"])


def downgrade() -> None:
    op.drop_table("playbook_runs")
    op.drop_table("notebooks")
