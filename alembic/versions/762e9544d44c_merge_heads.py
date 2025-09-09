"""merge heads

Revision ID: 762e9544d44c
Revises: ead4a384baac, chat_tables_001
Create Date: 2025-08-11 14:02:02.111317

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '762e9544d44c'
down_revision: Union[str, Sequence[str], None] = ('ead4a384baac', 'chat_tables_001')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
