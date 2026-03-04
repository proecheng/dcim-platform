"""add load shift tables

Revision ID: add_load_shift
Revises: 9c5eb5dd2970
Create Date: 2026-03-03 13:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_load_shift'
down_revision: Union[str, None] = '9c5eb5dd2970'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create shift_plans table
    op.create_table(
        'shift_plans',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('plan_code', sa.String(length=50), nullable=False),
        sa.Column('plan_name', sa.String(length=200), nullable=False),
        sa.Column('shift_from_period', sa.String(length=20), nullable=False),
        sa.Column('shift_to_period', sa.String(length=20), nullable=False),
        sa.Column('shift_date', sa.Date(), nullable=False),
        sa.Column('start_time', sa.Time(), nullable=False),
        sa.Column('end_time', sa.Time(), nullable=False),
        sa.Column('target_shift_power', sa.Float(), nullable=False),
        sa.Column('selected_devices', sa.JSON(), nullable=True),
        sa.Column('constraints', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('approval_status', sa.String(length=20), nullable=False),
        sa.Column('execution_status', sa.String(length=20), nullable=False),
        sa.Column('expected_cost_saving', sa.Float(), nullable=True),
        sa.Column('expected_energy_saving', sa.Float(), nullable=True),
        sa.Column('actual_shift_power', sa.Float(), nullable=True),
        sa.Column('actual_cost_saving', sa.Float(), nullable=True),
        sa.Column('actual_energy_saving', sa.Float(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('approved_by', sa.Integer(), nullable=True),
        sa.Column('approval_comment', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('executed_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_shift_plans_plan_code', 'shift_plans', ['plan_code'], unique=True)
    op.create_index('ix_shift_plans_shift_date', 'shift_plans', ['shift_date'])
    op.create_index('ix_shift_plans_status', 'shift_plans', ['status'])
    op.create_index('ix_shift_plans_created_by', 'shift_plans', ['created_by'])

    # Create shift_executions table
    op.create_table(
        'shift_executions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('plan_id', sa.Integer(), nullable=False),
        sa.Column('execution_code', sa.String(length=50), nullable=False),
        sa.Column('start_time', sa.DateTime(), nullable=False),
        sa.Column('end_time', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('actual_shift_power', sa.Float(), nullable=True),
        sa.Column('actual_cost_saving', sa.Float(), nullable=True),
        sa.Column('actual_energy_saving', sa.Float(), nullable=True),
        sa.Column('execution_log', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['plan_id'], ['shift_plans.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_shift_executions_plan_id', 'shift_executions', ['plan_id'])
    op.create_index('ix_shift_executions_status', 'shift_executions', ['status'])
    op.create_index('ix_shift_executions_start_time', 'shift_executions', ['start_time'])

    # Create shift_constraints table
    op.create_table(
        'shift_constraints',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('constraint_name', sa.String(length=200), nullable=False),
        sa.Column('constraint_type', sa.String(length=50), nullable=False),
        sa.Column('constraint_value', sa.JSON(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_shift_constraints_type', 'shift_constraints', ['constraint_type'])
    op.create_index('ix_shift_constraints_active', 'shift_constraints', ['is_active'])

    # Create shift_opportunities table
    op.create_table(
        'shift_opportunities',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('opportunity_code', sa.String(length=50), nullable=False),
        sa.Column('opportunity_name', sa.String(length=200), nullable=False),
        sa.Column('shift_from_period', sa.String(length=20), nullable=False),
        sa.Column('shift_to_period', sa.String(length=20), nullable=False),
        sa.Column('recommended_date', sa.Date(), nullable=False),
        sa.Column('recommended_start_time', sa.Time(), nullable=False),
        sa.Column('recommended_end_time', sa.Time(), nullable=False),
        sa.Column('estimated_shift_power', sa.Float(), nullable=False),
        sa.Column('estimated_cost_saving', sa.Float(), nullable=False),
        sa.Column('estimated_energy_saving', sa.Float(), nullable=False),
        sa.Column('confidence_score', sa.Float(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('converted_plan_id', sa.Integer(), nullable=True),
        sa.Column('analysis_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['converted_plan_id'], ['shift_plans.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_shift_opportunities_code', 'shift_opportunities', ['opportunity_code'], unique=True)
    op.create_index('ix_shift_opportunities_status', 'shift_opportunities', ['status'])
    op.create_index('ix_shift_opportunities_date', 'shift_opportunities', ['recommended_date'])

    # Create shift_analysis_records table
    op.create_table(
        'shift_analysis_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('analysis_type', sa.String(length=50), nullable=False),
        sa.Column('analysis_date', sa.Date(), nullable=False),
        sa.Column('analysis_result', sa.JSON(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_shift_analysis_type', 'shift_analysis_records', ['analysis_type'])
    op.create_index('ix_shift_analysis_date', 'shift_analysis_records', ['analysis_date'])

    # Create cooling_linkage_configs table
    op.create_table(
        'cooling_linkage_configs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('config_name', sa.String(length=200), nullable=False),
        sa.Column('cooling_lag_minutes', sa.Integer(), nullable=False),
        sa.Column('max_temp_rise', sa.Float(), nullable=False),
        sa.Column('min_cooling_efficiency', sa.Float(), nullable=False),
        sa.Column('cooling_adjustment_strategy', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create cooling_linkage_records table
    op.create_table(
        'cooling_linkage_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('plan_id', sa.Integer(), nullable=False),
        sa.Column('record_time', sa.DateTime(), nullable=False),
        sa.Column('it_load_kw', sa.Float(), nullable=False),
        sa.Column('cooling_load_kw', sa.Float(), nullable=False),
        sa.Column('inlet_temp', sa.Float(), nullable=True),
        sa.Column('outlet_temp', sa.Float(), nullable=True),
        sa.Column('cooling_efficiency', sa.Float(), nullable=True),
        sa.Column('adjustment_action', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['plan_id'], ['shift_plans.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_cooling_linkage_plan_id', 'cooling_linkage_records', ['plan_id'])
    op.create_index('ix_cooling_linkage_time', 'cooling_linkage_records', ['record_time'])

    # Create device_lifespan_impacts table
    op.create_table(
        'device_lifespan_impacts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('device_id', sa.Integer(), nullable=False),
        sa.Column('plan_id', sa.Integer(), nullable=False),
        sa.Column('impact_date', sa.Date(), nullable=False),
        sa.Column('startup_count', sa.Integer(), nullable=False),
        sa.Column('estimated_lifespan_loss_hours', sa.Float(), nullable=False),
        sa.Column('cumulative_loss_hours', sa.Float(), nullable=False),
        sa.Column('impact_description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['plan_id'], ['shift_plans.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_device_lifespan_device_id', 'device_lifespan_impacts', ['device_id'])
    op.create_index('ix_device_lifespan_plan_id', 'device_lifespan_impacts', ['plan_id'])
    op.create_index('ix_device_lifespan_date', 'device_lifespan_impacts', ['impact_date'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_index('ix_device_lifespan_date', table_name='device_lifespan_impacts')
    op.drop_index('ix_device_lifespan_plan_id', table_name='device_lifespan_impacts')
    op.drop_index('ix_device_lifespan_device_id', table_name='device_lifespan_impacts')
    op.drop_table('device_lifespan_impacts')

    op.drop_index('ix_cooling_linkage_time', table_name='cooling_linkage_records')
    op.drop_index('ix_cooling_linkage_plan_id', table_name='cooling_linkage_records')
    op.drop_table('cooling_linkage_records')

    op.drop_table('cooling_linkage_configs')

    op.drop_index('ix_shift_analysis_date', table_name='shift_analysis_records')
    op.drop_index('ix_shift_analysis_type', table_name='shift_analysis_records')
    op.drop_table('shift_analysis_records')

    op.drop_index('ix_shift_opportunities_date', table_name='shift_opportunities')
    op.drop_index('ix_shift_opportunities_status', table_name='shift_opportunities')
    op.drop_index('ix_shift_opportunities_code', table_name='shift_opportunities')
    op.drop_table('shift_opportunities')

    op.drop_index('ix_shift_constraints_active', table_name='shift_constraints')
    op.drop_index('ix_shift_constraints_type', table_name='shift_constraints')
    op.drop_table('shift_constraints')

    op.drop_index('ix_shift_executions_start_time', table_name='shift_executions')
    op.drop_index('ix_shift_executions_status', table_name='shift_executions')
    op.drop_index('ix_shift_executions_plan_id', table_name='shift_executions')
    op.drop_table('shift_executions')

    op.drop_index('ix_shift_plans_created_by', table_name='shift_plans')
    op.drop_index('ix_shift_plans_status', table_name='shift_plans')
    op.drop_index('ix_shift_plans_shift_date', table_name='shift_plans')
    op.drop_index('ix_shift_plans_plan_code', table_name='shift_plans')
    op.drop_table('shift_plans')
