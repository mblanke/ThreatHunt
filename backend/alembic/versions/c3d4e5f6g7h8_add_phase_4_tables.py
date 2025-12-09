"""Add Phase 4 tables

Revision ID: c3d4e5f6g7h8
Revises: b2c3d4e5f6g7
Create Date: 2025-12-09 17:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6g7h8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6g7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema for Phase 4."""
    
    # Create playbooks table
    op.create_table(
        'playbooks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('trigger_type', sa.String(), nullable=False),
        sa.Column('trigger_config', sa.JSON(), nullable=True),
        sa.Column('actions', sa.JSON(), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_playbooks_id'), 'playbooks', ['id'], unique=False)
    op.create_index(op.f('ix_playbooks_name'), 'playbooks', ['name'], unique=False)
    
    # Create playbook_executions table
    op.create_table(
        'playbook_executions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('playbook_id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('result', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('triggered_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['playbook_id'], ['playbooks.id'], ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.ForeignKeyConstraint(['triggered_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_playbook_executions_id'), 'playbook_executions', ['id'], unique=False)
    
    # Create threat_scores table
    op.create_table(
        'threat_scores',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('host_id', sa.Integer(), nullable=True),
        sa.Column('artifact_id', sa.Integer(), nullable=True),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('threat_type', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('indicators', sa.JSON(), nullable=True),
        sa.Column('ml_model_version', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.ForeignKeyConstraint(['host_id'], ['hosts.id'], ),
        sa.ForeignKeyConstraint(['artifact_id'], ['artifacts.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_threat_scores_id'), 'threat_scores', ['id'], unique=False)
    op.create_index(op.f('ix_threat_scores_score'), 'threat_scores', ['score'], unique=False)
    op.create_index(op.f('ix_threat_scores_created_at'), 'threat_scores', ['created_at'], unique=False)
    
    # Create report_templates table
    op.create_table(
        'report_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('template_type', sa.String(), nullable=False),
        sa.Column('template_config', sa.JSON(), nullable=False),
        sa.Column('is_default', sa.Boolean(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_report_templates_id'), 'report_templates', ['id'], unique=False)
    op.create_index(op.f('ix_report_templates_name'), 'report_templates', ['name'], unique=False)
    
    # Create reports table
    op.create_table(
        'reports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('template_id', sa.Integer(), nullable=True),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('report_type', sa.String(), nullable=False),
        sa.Column('format', sa.String(), nullable=False),
        sa.Column('file_path', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('generated_by', sa.Integer(), nullable=False),
        sa.Column('generated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.ForeignKeyConstraint(['template_id'], ['report_templates.id'], ),
        sa.ForeignKeyConstraint(['generated_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_reports_id'), 'reports', ['id'], unique=False)


def downgrade() -> None:
    """Downgrade schema for Phase 4."""
    
    # Drop reports table
    op.drop_index(op.f('ix_reports_id'), table_name='reports')
    op.drop_table('reports')
    
    # Drop report_templates table
    op.drop_index(op.f('ix_report_templates_name'), table_name='report_templates')
    op.drop_index(op.f('ix_report_templates_id'), table_name='report_templates')
    op.drop_table('report_templates')
    
    # Drop threat_scores table
    op.drop_index(op.f('ix_threat_scores_created_at'), table_name='threat_scores')
    op.drop_index(op.f('ix_threat_scores_score'), table_name='threat_scores')
    op.drop_index(op.f('ix_threat_scores_id'), table_name='threat_scores')
    op.drop_table('threat_scores')
    
    # Drop playbook_executions table
    op.drop_index(op.f('ix_playbook_executions_id'), table_name='playbook_executions')
    op.drop_table('playbook_executions')
    
    # Drop playbooks table
    op.drop_index(op.f('ix_playbooks_name'), table_name='playbooks')
    op.drop_index(op.f('ix_playbooks_id'), table_name='playbooks')
    op.drop_table('playbooks')
