"""Add metadata column to collection_runs

Revision ID: f8a2b1c9d3e7
Revises: 5537be644d83
Create Date: 2026-06-08 09:16:00.000000+00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'f8a2b1c9d3e7'
down_revision = '5537be644d83'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add the metadata JSONB column to collection_runs.
    # Defaults to '{}' so existing rows are immediately valid.
    op.add_column(
        'collection_runs',
        sa.Column(
            'metadata',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default='{}',
        ),
    )


def downgrade() -> None:
    op.drop_column('collection_runs', 'metadata')
