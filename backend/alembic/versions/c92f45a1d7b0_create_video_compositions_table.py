"""create video compositions table

Revision ID: c92f45a1d7b0
Revises: b71e29c04d1a
Create Date: 2026-11-04 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'c92f45a1d7b0'
down_revision = 'b71e29c04d1a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'video_compositions',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('project_id', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('composition_json', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index(op.f('ix_video_compositions_id'), 'video_compositions', ['id'], unique=False)
    op.create_index(
        op.f('ix_video_compositions_project_id'),
        'video_compositions',
        ['project_id'],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_video_compositions_project_id'), table_name='video_compositions')
    op.drop_index(op.f('ix_video_compositions_id'), table_name='video_compositions')
    op.drop_table('video_compositions')
