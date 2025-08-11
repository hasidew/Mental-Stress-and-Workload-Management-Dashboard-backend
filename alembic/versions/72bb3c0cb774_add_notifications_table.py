"""add_notifications_table

Revision ID: 72bb3c0cb774
Revises: 1b5d4fad0075
Create Date: 2025-07-31 13:10:03.845825

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '72bb3c0cb774'
down_revision: Union[str, Sequence[str], None] = '1b5d4fad0075'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
