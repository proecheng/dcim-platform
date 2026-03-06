"""create_diagnosis_sessions_and_audit_logs

Revision ID: a1b2c3d4e5f6
Revises: 5f3a9c2b1d7e
Create Date: 2026-03-06 16:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '5f3a9c2b1d7e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 创建诊断会话表
    op.create_table(
        'diagnosis_sessions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('trigger_alarm_id', sa.Integer(), nullable=True, comment='触发告警ID'),
        sa.Column('device_id', sa.Integer(), nullable=True, comment='设备ID'),
        sa.Column('engine_level', sa.String(5), nullable=False, comment='推理级别: L1/L2/L3'),
        sa.Column('status', sa.String(20), nullable=False, server_default='success', comment='会话状态: success/timeout/error/degraded'),
        sa.Column('push_status', sa.String(20), nullable=False, server_default='skipped', comment='推送状态: pushed/failed/skipped'),
        sa.Column('max_confidence', sa.Float(), nullable=True, comment='最高置信度(冗余)'),
        sa.Column('start_time', sa.DateTime(), nullable=False, comment='推理开始时间'),
        sa.Column('end_time', sa.DateTime(), nullable=True, comment='推理结束时间'),
        sa.Column('inference_time_ms', sa.Integer(), server_default='0', comment='推理耗时(毫秒)'),
        sa.Column('created_at', sa.DateTime(), nullable=True, comment='创建时间'),
        sa.ForeignKeyConstraint(['trigger_alarm_id'], ['alarms.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_diagnosis_sessions_trigger_alarm_id', 'diagnosis_sessions', ['trigger_alarm_id'])
    op.create_index('ix_diagnosis_sessions_device_id', 'diagnosis_sessions', ['device_id'])
    op.create_index('ix_diagnosis_sessions_engine_level', 'diagnosis_sessions', ['engine_level'])
    op.create_index('ix_diagnosis_sessions_created_at', 'diagnosis_sessions', ['created_at'])

    # 创建诊断审计日志表
    op.create_table(
        'diagnosis_audit_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False, comment='会话ID'),
        sa.Column('input_data', sa.JSON(), nullable=True, comment='推理输入数据'),
        sa.Column('output_data', sa.JSON(), nullable=True, comment='推理输出数据'),
        sa.Column('engine_level', sa.String(5), nullable=False, comment='推理级别'),
        sa.Column('inference_time_ms', sa.Integer(), server_default='0', comment='推理耗时(毫秒)'),
        sa.Column('fault_tree_version', sa.String(50), nullable=True, comment='故障树版本号'),
        sa.Column('created_at', sa.DateTime(), nullable=True, comment='创建时间'),
        sa.ForeignKeyConstraint(['session_id'], ['diagnosis_sessions.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_diagnosis_audit_logs_session_id', 'diagnosis_audit_logs', ['session_id'])


def downgrade() -> None:
    op.drop_index('ix_diagnosis_audit_logs_session_id', table_name='diagnosis_audit_logs')
    op.drop_table('diagnosis_audit_logs')
    op.drop_index('ix_diagnosis_sessions_created_at', table_name='diagnosis_sessions')
    op.drop_index('ix_diagnosis_sessions_engine_level', table_name='diagnosis_sessions')
    op.drop_index('ix_diagnosis_sessions_device_id', table_name='diagnosis_sessions')
    op.drop_index('ix_diagnosis_sessions_trigger_alarm_id', table_name='diagnosis_sessions')
    op.drop_table('diagnosis_sessions')
