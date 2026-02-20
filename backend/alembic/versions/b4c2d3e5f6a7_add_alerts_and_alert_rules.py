"""add alerts and alert_rules tables

Revision ID: b4c2d3e5f6a7
Revises: a3b1c2d4e5f6
Create Date: 2025-01-01 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = "b4c2d3e5f6a7"
down_revision: Union[str, None] = "a3b1c2d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "alerts",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("severity", sa.String(16), server_default="medium"),
        sa.Column("status", sa.String(24), server_default="new"),
        sa.Column("analyzer", sa.String(64), nullable=False),
        sa.Column("score", sa.Float, server_default="0"),
        sa.Column("evidence", sa.JSON, nullable=True),
        sa.Column("mitre_technique", sa.String(32), nullable=True),
        sa.Column("tags", sa.JSON, nullable=True),
        sa.Column("hunt_id", sa.String(32), sa.ForeignKey("hunts.id"), nullable=True),
        sa.Column("dataset_id", sa.String(32), sa.ForeignKey("datasets.id"), nullable=True),
        sa.Column("case_id", sa.String(32), sa.ForeignKey("cases.id"), nullable=True),
        sa.Column("assignee", sa.String(128), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_alerts_severity", "alerts", ["severity"])
    op.create_index("ix_alerts_status", "alerts", ["status"])
    op.create_index("ix_alerts_hunt", "alerts", ["hunt_id"])
    op.create_index("ix_alerts_dataset", "alerts", ["dataset_id"])

    op.create_table(
        "alert_rules",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("analyzer", sa.String(64), nullable=False),
        sa.Column("config", sa.JSON, nullable=True),
        sa.Column("severity_override", sa.String(16), nullable=True),
        sa.Column("enabled", sa.Boolean, server_default=sa.text("1")),
        sa.Column("hunt_id", sa.String(32), sa.ForeignKey("hunts.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_alert_rules_analyzer", "alert_rules", ["analyzer"])


def downgrade() -> None:
    op.drop_table("alert_rules")
    op.drop_table("alerts")
