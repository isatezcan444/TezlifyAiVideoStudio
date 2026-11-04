"""create_studio_projects_table

Revision ID: f73b18d94e21
Revises: e51f28b7a94c
Create Date: 2026-11-04 11:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f73b18d94e21'
down_revision: Union[str, Sequence[str], None] = 'e51f28b7a94c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        'studio_projects',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('scene_graph_json', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_studio_projects_id'), 'studio_projects', ['id'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_studio_projects_id'), table_name='studio_projects')
    op.drop_table('studio_projects')
