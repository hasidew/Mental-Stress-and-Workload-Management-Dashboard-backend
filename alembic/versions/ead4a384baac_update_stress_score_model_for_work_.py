"""update_stress_score_model_for_work_stress_calculation

Revision ID: ead4a384baac
Revises: cf4442d79b8f
Create Date: 2025-08-11 12:01:50.639379

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ead4a384baac'
down_revision: Union[str, Sequence[str], None] = 'cf4442d79b8f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Update stress_scores table for new Work Stress Calculation method
    
    # Change score column from INTEGER to FLOAT
    op.alter_column('stress_scores', 'score',
               existing_type=sa.Integer(),
               type_=sa.Float(),
               existing_nullable=False,
               existing_server_default=None)
    
    # Add new columns for detailed stress calculation
    op.add_column('stress_scores', sa.Column('pss_score', sa.Float(), nullable=True))
    op.add_column('stress_scores', sa.Column('normalized_pss', sa.Float(), nullable=True))
    op.add_column('stress_scores', sa.Column('workload_stress_score', sa.Float(), nullable=True))
    op.add_column('stress_scores', sa.Column('total_hours_worked', sa.Float(), nullable=True))
    
    # Update existing records to have default values
    op.execute("UPDATE stress_scores SET pss_score = 0, normalized_pss = 0, workload_stress_score = 0, total_hours_worked = 0 WHERE pss_score IS NULL")
    
    # Make new columns non-nullable
    op.alter_column('stress_scores', 'pss_score', nullable=False)
    op.alter_column('stress_scores', 'normalized_pss', nullable=False)
    op.alter_column('stress_scores', 'workload_stress_score', nullable=False)
    op.alter_column('stress_scores', 'total_hours_worked', nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Remove new columns
    op.drop_column('stress_scores', 'total_hours_worked')
    op.drop_column('stress_scores', 'workload_stress_score')
    op.drop_column('stress_scores', 'normalized_pss')
    op.drop_column('stress_scores', 'pss_score')
    
    # Change score column back to INTEGER
    op.alter_column('stress_scores', 'score',
               existing_type=sa.Float(),
               type_=sa.Integer(),
               existing_nullable=False)
