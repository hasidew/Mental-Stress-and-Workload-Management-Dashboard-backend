"""add_admin_role

Revision ID: 934c839f33ca
Revises: 0246eba45e5e
Create Date: 2025-07-14 14:00:15.991304

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '934c839f33ca'
down_revision: Union[str, Sequence[str], None] = '0246eba45e5e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Update the enum to include 'admin' role
    op.execute("ALTER TABLE users MODIFY COLUMN `role` ENUM('admin', 'employee', 'supervisor', 'psychiatrist', 'hr_manager') NOT NULL")


def downgrade() -> None:
    """Downgrade schema."""
    # Revert the enum to exclude 'admin' role
    op.execute("ALTER TABLE users MODIFY COLUMN `role` ENUM('employee', 'supervisor', 'psychiatrist', 'hr_manager') NOT NULL")
