"""create render jobs table

Revision ID: b71e29c04d1a
Revises: a84c910d52b3
Create Date: 2026-11-04 11:45:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'b71e29c04d1a'
down_revision = 'a84c910d52b3'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        'render_jobs',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('project_id', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='pending'),
        sa.Column('progress_percent', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('current_step', sa.String(length=255), nullable=False, server_default='Pending'),
        sa.Column('output_video_path', sa.String(length=512), nullable=True),
        sa.Column('output_metadata_json', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
    )
    op.create_index(op.f('ix_render_jobs_id'), 'render_jobs', ['id'], unique=False)
    op.create_index(op.f('ix_render_jobs_project_id'), 'render_jobs', ['project_id'], unique=False)
    op.create_index(op.f('ix_render_jobs_status'), 'render_jobs', ['status'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_render_jobs_status'), table_name='render_jobs')
    op.drop_index(op.f('ix_render_jobs_project_id'), table_name='render_jobs')
    op.drop_index(op.f('ix_render_jobs_id'), table_name='render_jobs')
    op.drop_table('render_jobs')
