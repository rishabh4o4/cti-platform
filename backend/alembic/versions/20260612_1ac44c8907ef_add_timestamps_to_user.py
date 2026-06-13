"""Add timestamps to User

Revision ID: 1ac44c8907ef
Revises: cca33144f5c0
Create Date: 2026-06-12 12:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1ac44c8907ef'
down_revision: str | None = 'cca33144f5c0'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Use timezone=True matching TimestampMixin
    op.add_column('users', sa.Column('created_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True))

    # Set default values for existing rows
    op.execute("UPDATE users SET created_at = NOW(), updated_at = NOW()")

    # Alter columns to NOT NULL
    op.alter_column('users', 'created_at', existing_type=sa.DateTime(timezone=True), nullable=False)
    op.alter_column('users', 'updated_at', existing_type=sa.DateTime(timezone=True), nullable=False)

    # Create index
    op.create_index(op.f('ix_users_created_at'), 'users', ['created_at'], unique=False)
    op.create_index(op.f('ix_users_updated_at'), 'users', ['updated_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_users_updated_at'), table_name='users')
    op.drop_index(op.f('ix_users_created_at'), table_name='users')
    op.drop_column('users', 'updated_at')
    op.drop_column('users', 'created_at')
