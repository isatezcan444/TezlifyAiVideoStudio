"""create_scheduled_publishes_table

Revision ID: e51f28b7a94c
Revises: 232a9f73f7fa
Create Date: 2026-11-03 20:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e51f28b7a94c'
down_revision: Union[str, Sequence[str], None] = '232a9f73f7fa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        'scheduled_publishes',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('media_asset_id', sa.String(length=64), nullable=False),
        sa.Column('social_account_id', sa.String(length=64), nullable=False),
        sa.Column('platform', sa.String(length=32), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('tags_json', sa.Text(), nullable=False),
        sa.Column('privacy_status', sa.String(length=32), nullable=False),
        sa.Column('scheduled_at_utc', sa.DateTime(), nullable=False),
        sa.Column('timezone', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('publish_record_id', sa.String(length=64), nullable=True),
        sa.Column('attempt_count', sa.Integer(), nullable=False),
        sa.Column('max_attempts', sa.Integer(), nullable=False),
        sa.Column('last_error_code', sa.String(length=64), nullable=True),
        sa.Column('last_error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['media_asset_id'], ['media_assets.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['social_account_id'], ['social_accounts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['publish_record_id'], ['publish_records.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_scheduled_publishes_id'), 'scheduled_publishes', ['id'], unique=False)
    op.create_index(op.f('ix_scheduled_publishes_media_asset_id'), 'scheduled_publishes', ['media_asset_id'], unique=False)
    op.create_index(op.f('ix_scheduled_publishes_social_account_id'), 'scheduled_publishes', ['social_account_id'], unique=False)
    op.create_index(op.f('ix_scheduled_publishes_platform'), 'scheduled_publishes', ['platform'], unique=False)
    op.create_index(op.f('ix_scheduled_publishes_scheduled_at_utc'), 'scheduled_publishes', ['scheduled_at_utc'], unique=False)
    op.create_index(op.f('ix_scheduled_publishes_status'), 'scheduled_publishes', ['status'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_scheduled_publishes_status'), table_name='scheduled_publishes')
    op.drop_index(op.f('ix_scheduled_publishes_scheduled_at_utc'), table_name='scheduled_publishes')
    op.drop_index(op.f('ix_scheduled_publishes_platform'), table_name='scheduled_publishes')
    op.drop_index(op.f('ix_scheduled_publishes_social_account_id'), table_name='scheduled_publishes')
    op.drop_index(op.f('ix_scheduled_publishes_media_asset_id'), table_name='scheduled_publishes')
    op.drop_index(op.f('ix_scheduled_publishes_id'), table_name='scheduled_publishes')
    op.drop_table('scheduled_publishes')
