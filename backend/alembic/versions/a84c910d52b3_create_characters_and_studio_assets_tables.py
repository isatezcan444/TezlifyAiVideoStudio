"""create characters and studio assets tables

Revision ID: a84c910d52b3
Revises: f73b18d94e21
Create Date: 2026-11-04 11:20:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'a84c910d52b3'
down_revision = 'f73b18d94e21'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # 1. Characters table
    op.create_table(
        'characters',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('gender', sa.String(length=32), nullable=False, server_default='neutral'),
        sa.Column('palette_json', sa.Text(), nullable=False),
        sa.Column('hair_style', sa.String(length=64), nullable=False, server_default='short_parted'),
        sa.Column('eye_style', sa.String(length=64), nullable=False, server_default='round'),
        sa.Column('clothing_style', sa.String(length=64), nullable=False, server_default='casual'),
        sa.Column('voice_id', sa.String(length=64), nullable=False, server_default=''),
        sa.Column('default_expression', sa.String(length=32), nullable=False, server_default='neutral'),
        sa.Column('default_pose', sa.String(length=32), nullable=False, server_default='standing'),
        sa.Column('proportions_json', sa.Text(), nullable=False),
        sa.Column('blend_file_path', sa.String(length=512), nullable=True),
        sa.Column('thumbnail_path', sa.String(length=512), nullable=True),
        sa.Column('is_builtin', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index(op.f('ix_characters_id'), 'characters', ['id'], unique=False)

    # 2. Studio Assets table
    op.create_table(
        'studio_assets',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('category', sa.String(length=32), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('file_path', sa.String(length=512), nullable=False),
        sa.Column('asset_format', sa.String(length=32), nullable=False, server_default='blend'),
        sa.Column('thumbnail_path', sa.String(length=512), nullable=True),
        sa.Column('version', sa.String(length=16), nullable=False, server_default='1.0'),
        sa.Column('tags_json', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('is_builtin', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index(op.f('ix_studio_assets_id'), 'studio_assets', ['id'], unique=False)
    op.create_index(op.f('ix_studio_assets_category'), 'studio_assets', ['category'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_studio_assets_category'), table_name='studio_assets')
    op.drop_index(op.f('ix_studio_assets_id'), table_name='studio_assets')
    op.drop_table('studio_assets')
    op.drop_index(op.f('ix_characters_id'), table_name='characters')
    op.drop_table('characters')
