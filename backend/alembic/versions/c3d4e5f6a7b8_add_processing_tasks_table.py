"""add processing_tasks table

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-02-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "processing_tasks",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("hunt_id", sa.String(32), sa.ForeignKey("hunts.id", ondelete="CASCADE"), nullable=True),
        sa.Column("dataset_id", sa.String(32), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=True),
        sa.Column("job_id", sa.String(64), nullable=True),
        sa.Column("stage", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("progress", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_processing_tasks_hunt_stage", "processing_tasks", ["hunt_id", "stage"])
    op.create_index("ix_processing_tasks_dataset_stage", "processing_tasks", ["dataset_id", "stage"])
    op.create_index("ix_processing_tasks_job_id", "processing_tasks", ["job_id"])
    op.create_index("ix_processing_tasks_status", "processing_tasks", ["status"])


def downgrade() -> None:
    op.drop_index("ix_processing_tasks_status", table_name="processing_tasks")
    op.drop_index("ix_processing_tasks_job_id", table_name="processing_tasks")
    op.drop_index("ix_processing_tasks_dataset_stage", table_name="processing_tasks")
    op.drop_index("ix_processing_tasks_hunt_stage", table_name="processing_tasks")
    op.drop_table("processing_tasks")
