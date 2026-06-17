"""Compatibility stamp for existing deployed databases.

Revision ID: 219886c5c38a
Revises: 72f90687bc00
Create Date: 2026-06-14 22:15:00.000000+00:00

"""

from alembic import op

revision = "219886c5c38a"
down_revision = "72f90687bc00"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """No-op migration for databases already stamped with this revision."""
    op.execute("SELECT 1")


def downgrade() -> None:
    """No-op downgrade; previous schema state is represented by down_revision."""
    op.execute("SELECT 1")
