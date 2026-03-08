"""create system_reports and diagnosis_improvement_rules tables

Revision ID: 20260308_0000
Revises: b74705769037
Create Date: 2026-03-08

Story 26.2: 误诊反馈报告
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260308_0000'
down_revision = 'b74705769037'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 创建 system_reports 表
    op.create_table(
        'system_reports',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('report_type', sa.String(length=50), nullable=False, comment='报告类型'),
        sa.Column('report_period', sa.String(length=20), nullable=False, comment='报告周期 YYYY-MM'),
        sa.Column('report_version', sa.String(length=20), nullable=True, server_default='v1.0', comment='报告模板版本'),
        sa.Column('content', sa.Text(), nullable=False, comment='Markdown 格式报告内容'),
        sa.Column('summary', sa.JSON(), nullable=True, comment='报告摘要（关键指标）'),
        sa.Column('generated_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP'), comment='生成时间'),
        sa.Column('generated_by', sa.String(length=100), nullable=True, comment='生成者'),
        sa.Column('deleted_at', sa.DateTime(), nullable=True, comment='软删除时间戳'),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP'), comment='更新时间'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('report_type', 'report_period', name='uq_system_reports_type_period'),
        comment='系统报告表'
    )

    # 创建索引
    op.create_index('idx_system_reports_type_period', 'system_reports', ['report_type', 'report_period'])
    op.create_index('idx_system_reports_generated', 'system_reports', ['generated_at'])
    op.create_index('idx_system_reports_deleted', 'system_reports', ['deleted_at'])

    # 创建 diagnosis_improvement_rules 表
    op.create_table(
        'diagnosis_improvement_rules',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('rule_type', sa.String(length=20), nullable=False, comment='规则类型: false_positive 或 false_negative'),
        sa.Column('node_id', sa.String(length=100), nullable=True, comment='故障树节点ID（误报规则）'),
        sa.Column('fault_type', sa.String(length=100), nullable=True, comment='故障类型（漏报规则）'),
        sa.Column('suggestion_template', sa.Text(), nullable=False, comment='建议模板（支持变量替换）'),
        sa.Column('priority', sa.Integer(), nullable=True, server_default='0', comment='优先级（数字越大优先级越高）'),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true', comment='是否启用'),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP'), comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP'), comment='更新时间'),
        sa.PrimaryKeyConstraint('id'),
        comment='诊断改进建议规则表'
    )

    # 创建索引
    op.create_index('idx_improvement_rules_type_node', 'diagnosis_improvement_rules', ['rule_type', 'node_id'])
    op.create_index('idx_improvement_rules_type_fault', 'diagnosis_improvement_rules', ['rule_type', 'fault_type'])
    op.create_index('idx_improvement_rules_active', 'diagnosis_improvement_rules', ['is_active'])

    # 插入示例规则数据
    op.execute("""
        INSERT INTO diagnosis_improvement_rules (rule_type, node_id, suggestion_template, priority) VALUES
        ('false_positive', 'root_ups_battery', '建议增加电池SOH算法精度（Story 25.3），或调整故障树先验概率（降低 10%）', 10),
        ('false_positive', 'root_ac_cooling', '建议增加回风温差传感器权重（Story 25.5），或添加压缩机电流监控点位', 9)
    """)

    # 插入漏报规则（fault_type 字段）
    op.execute("""
        INSERT INTO diagnosis_improvement_rules (rule_type, fault_type, suggestion_template, priority) VALUES
        ('false_negative', 'breaker_trip', '建议添加断路器状态监控点位，或降低断路器告警触发阈值', 10),
        ('false_negative', 'sensor_drift', '建议启用传感器自校准功能，或缩短传感器巡检周期', 9)
    """)

    # 插入通用兜底规则
    op.execute("""
        INSERT INTO diagnosis_improvement_rules (rule_type, node_id, suggestion_template, priority) VALUES
        ('false_positive', '*', '建议人工审查该节点的故障树逻辑和先验概率设置', 0)
    """)

    op.execute("""
        INSERT INTO diagnosis_improvement_rules (rule_type, fault_type, suggestion_template, priority) VALUES
        ('false_negative', '*', '建议检查该故障类型的告警规则配置和传感器覆盖范围', 0)
    """)


def downgrade() -> None:
    # 删除 diagnosis_improvement_rules 表
    op.drop_index('idx_improvement_rules_active', table_name='diagnosis_improvement_rules')
    op.drop_index('idx_improvement_rules_type_fault', table_name='diagnosis_improvement_rules')
    op.drop_index('idx_improvement_rules_type_node', table_name='diagnosis_improvement_rules')
    op.drop_table('diagnosis_improvement_rules')

    # 删除 system_reports 表
    op.drop_index('idx_system_reports_deleted', table_name='system_reports')
    op.drop_index('idx_system_reports_generated', table_name='system_reports')
    op.drop_index('idx_system_reports_type_period', table_name='system_reports')
    op.drop_table('system_reports')

