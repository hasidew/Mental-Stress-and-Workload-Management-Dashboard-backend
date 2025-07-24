"""add consultant and availability tables

Revision ID: add_consultant_tables
Revises: 934c839f33ca
Create Date: 2024-01-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_consultant_tables_001'
down_revision = '79e56140a690'
branch_labels = None
depends_on = None


def upgrade():
    # Create consultants table
    op.create_table('consultants',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('qualifications', sa.Text(), nullable=False),
        sa.Column('registration_number', sa.String(length=50), nullable=False),
        sa.Column('hospital', sa.String(length=100), nullable=False),
        sa.Column('specialization', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_consultants_id'), 'consultants', ['id'], unique=False)
    op.create_index(op.f('ix_consultants_registration_number'), 'consultants', ['registration_number'], unique=True)
    
    # Create consultant_availabilities table
    op.create_table('consultant_availabilities',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('consultant_id', sa.Integer(), nullable=False),
        sa.Column('day_of_week', sa.Integer(), nullable=False),
        sa.Column('start_time', sa.Time(), nullable=False),
        sa.Column('end_time', sa.Time(), nullable=False),
        sa.Column('is_available', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['consultant_id'], ['consultants.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_consultant_availabilities_id'), 'consultant_availabilities', ['id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_consultant_availabilities_id'), table_name='consultant_availabilities')
    op.drop_table('consultant_availabilities')
    op.drop_index(op.f('ix_consultants_registration_number'), table_name='consultants')
    op.drop_index(op.f('ix_consultants_id'), table_name='consultants')
    op.drop_table('consultants') 