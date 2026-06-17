"""fix_role_enum

Revision ID: 5092e67b7d1b
Revises: 219886c5c38a
Create Date: 2026-06-17 05:50:46.138322+00:00

"""
from alembic import op
import sqlalchemy as sa



revision = '5092e67b7d1b'
down_revision = '219886c5c38a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("COMMIT")
    op.execute("ALTER TYPE role_enum RENAME VALUE 'ADMIN' TO 'admin'")
    op.execute("ALTER TYPE role_enum RENAME VALUE 'ANALYST' TO 'analyst'")
    op.execute("ALTER TYPE role_enum RENAME VALUE 'VIEWER' TO 'viewer'")
    op.execute("BEGIN")

def downgrade() -> None:
    op.execute("COMMIT")
    op.execute("ALTER TYPE role_enum RENAME VALUE 'admin' TO 'ADMIN'")
    op.execute("ALTER TYPE role_enum RENAME VALUE 'analyst' TO 'ANALYST'")
    op.execute("ALTER TYPE role_enum RENAME VALUE 'viewer' TO 'VIEWER'")
    op.execute("BEGIN")
