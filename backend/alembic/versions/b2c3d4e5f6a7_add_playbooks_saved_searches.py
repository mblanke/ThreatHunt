"""add playbooks, playbook_steps, saved_searches tables

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-21 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add display_name to users table
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("display_name", sa.String(128), nullable=True))

    # Create playbooks table
    op.create_table(
        "playbooks",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(256), nullable=False, index=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(32), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("is_template", sa.Boolean(), server_default="0"),
        sa.Column("hunt_id", sa.String(32), sa.ForeignKey("hunts.id"), nullable=True),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Create playbook_steps table
    op.create_table(
        "playbook_steps",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("playbook_id", sa.String(32), sa.ForeignKey("playbooks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("step_type", sa.String(32), server_default="manual"),
        sa.Column("target_route", sa.String(256), nullable=True),
        sa.Column("is_completed", sa.Boolean(), server_default="0"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_playbook_steps_playbook", "playbook_steps", ["playbook_id"])

    # Create saved_searches table
    op.create_table(
        "saved_searches",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(256), nullable=False, index=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("search_type", sa.String(32), nullable=False),
        sa.Column("query_params", sa.JSON(), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=True),
        sa.Column("created_by", sa.String(32), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("hunt_id", sa.String(32), sa.ForeignKey("hunts.id"), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_result_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_saved_searches_type", "saved_searches", ["search_type"])


def downgrade() -> None:
    op.drop_table("saved_searches")
    op.drop_table("playbook_steps")
    op.drop_table("playbooks")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("display_name")
