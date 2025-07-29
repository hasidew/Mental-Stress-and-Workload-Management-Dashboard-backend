"""fix_booking_status_enum_values

Revision ID: 1b5d4fad0075
Revises: 482dda2293cb
Create Date: 2025-07-26 18:11:54.703235

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1b5d4fad0075'
down_revision: Union[str, Sequence[str], None] = '482dda2293cb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Update the enum values for the status column
    op.execute("ALTER TABLE consultant_bookings MODIFY COLUMN status ENUM('pending', 'approved', 'rejected', 'completed', 'cancelled') NOT NULL DEFAULT 'pending'")


def downgrade() -> None:
    """Downgrade schema."""
    # Revert to old enum values
    op.execute("ALTER TABLE consultant_bookings MODIFY COLUMN status ENUM('scheduled', 'completed', 'cancelled') NOT NULL DEFAULT 'scheduled'")
