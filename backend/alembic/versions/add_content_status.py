"""add content status field

Revision ID: add_content_status
Revises: cdbfb07611c3
Create Date: 2026-06-10
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_content_status'
down_revision = 'cdbfb07611c3'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('content_items', sa.Column('status', sa.String(32), nullable=False, server_default='open'))
    op.create_index('ix_content_items_status', 'content_items', ['status'])

def downgrade() -> None:
    op.drop_index('ix_content_items_status', table_name='content_items')
    op.drop_column('content_items', 'status')
