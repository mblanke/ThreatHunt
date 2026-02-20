"""add processing_status and AI analysis tables

Revision ID: a1b2c3d4e5f6
Revises: 98ab619418bc
Create Date: 2026-02-19 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "98ab619418bc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add columns to datasets table
    with op.batch_alter_table("datasets") as batch_op:
        batch_op.add_column(sa.Column("processing_status", sa.String(20), server_default="ready"))
        batch_op.add_column(sa.Column("artifact_type", sa.String(128), nullable=True))
        batch_op.add_column(sa.Column("error_message", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("file_path", sa.String(512), nullable=True))
        batch_op.create_index("ix_datasets_status", ["processing_status"])

    # Create triage_results table
    op.create_table(
        "triage_results",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("dataset_id", sa.String(32), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("row_start", sa.Integer(), nullable=False),
        sa.Column("row_end", sa.Integer(), nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("verdict", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("findings", sa.JSON(), nullable=True),
        sa.Column("suspicious_indicators", sa.JSON(), nullable=True),
        sa.Column("mitre_techniques", sa.JSON(), nullable=True),
        sa.Column("model_used", sa.String(128), nullable=True),
        sa.Column("node_used", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Create host_profiles table
    op.create_table(
        "host_profiles",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("hunt_id", sa.String(32), sa.ForeignKey("hunts.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("hostname", sa.String(256), nullable=False),
        sa.Column("fqdn", sa.String(512), nullable=True),
        sa.Column("client_id", sa.String(64), nullable=True),
        sa.Column("risk_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("risk_level", sa.String(20), nullable=False, server_default="unknown"),
        sa.Column("artifact_summary", sa.JSON(), nullable=True),
        sa.Column("timeline_summary", sa.Text(), nullable=True),
        sa.Column("suspicious_findings", sa.JSON(), nullable=True),
        sa.Column("mitre_techniques", sa.JSON(), nullable=True),
        sa.Column("llm_analysis", sa.Text(), nullable=True),
        sa.Column("model_used", sa.String(128), nullable=True),
        sa.Column("node_used", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Create hunt_reports table
    op.create_table(
        "hunt_reports",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("hunt_id", sa.String(32), sa.ForeignKey("hunts.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("exec_summary", sa.Text(), nullable=True),
        sa.Column("full_report", sa.Text(), nullable=True),
        sa.Column("findings", sa.JSON(), nullable=True),
        sa.Column("recommendations", sa.JSON(), nullable=True),
        sa.Column("mitre_mapping", sa.JSON(), nullable=True),
        sa.Column("ioc_table", sa.JSON(), nullable=True),
        sa.Column("host_risk_summary", sa.JSON(), nullable=True),
        sa.Column("models_used", sa.JSON(), nullable=True),
        sa.Column("generation_time_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Create anomaly_results table
    op.create_table(
        "anomaly_results",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("dataset_id", sa.String(32), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("row_id", sa.String(32), sa.ForeignKey("dataset_rows.id", ondelete="CASCADE"), nullable=True),
        sa.Column("anomaly_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("distance_from_centroid", sa.Float(), nullable=True),
        sa.Column("cluster_id", sa.Integer(), nullable=True),
        sa.Column("is_outlier", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("anomaly_results")
    op.drop_table("hunt_reports")
    op.drop_table("host_profiles")
    op.drop_table("triage_results")

    with op.batch_alter_table("datasets") as batch_op:
        batch_op.drop_index("ix_datasets_status")
        batch_op.drop_column("file_path")
        batch_op.drop_column("error_message")
        batch_op.drop_column("artifact_type")
        batch_op.drop_column("processing_status")