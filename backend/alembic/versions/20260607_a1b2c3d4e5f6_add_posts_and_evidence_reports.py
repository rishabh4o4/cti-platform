"""add_posts_and_evidence_reports

Revision ID: a1b2c3d4e5f6
Revises: 1898232c9028
Create Date: 2026-06-07 21:00:00.000000+00:00

"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = 'a1b2c3d4e5f6'
down_revision = '1898232c9028'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table('posts',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('author_id', sa.String(length=255), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_posts_author_id'), 'posts', ['author_id'], unique=False)
    
    op.create_table('evidence_reports',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('case_number', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('assigned_to', sa.String(length=255), nullable=True),
        sa.Column('evidence_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_evidence_reports_case_number'), 'evidence_reports', ['case_number'], unique=False)
    op.create_index(op.f('ix_evidence_reports_status'), 'evidence_reports', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_evidence_reports_status'), table_name='evidence_reports')
    op.drop_index(op.f('ix_evidence_reports_case_number'), table_name='evidence_reports')
    op.drop_table('evidence_reports')
    
    op.drop_index(op.f('ix_posts_author_id'), table_name='posts')
    op.drop_table('posts')
