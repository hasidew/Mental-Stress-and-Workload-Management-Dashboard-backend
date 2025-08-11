"""remove_assigned_date_from_tasks

Revision ID: cf4442d79b8f
Revises: 7bc30fb01f16
Create Date: 2025-08-11 11:10:44.850053

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cf4442d79b8f'
down_revision: Union[str, Sequence[str], None] = '7bc30fb01f16'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Remove assigned_date column from tasks table
    op.drop_column('tasks', 'assigned_date')


def downgrade() -> None:
    """Downgrade schema."""
    # Add back assigned_date column to tasks table
    op.add_column('tasks', sa.Column('assigned_date', sa.DateTime(), nullable=True))
    
    # Update existing tasks to have assigned_date = created_at
    op.execute("UPDATE tasks SET assigned_date = created_at WHERE assigned_date IS NULL")
    
    # Make assigned_date non-nullable
    op.alter_column('tasks', 'assigned_date', nullable=False)
