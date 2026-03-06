"""init l1 diagnosis rules

Revision ID: c6818ff61a90
Revises: 2484701f5ab1
Create Date: 2026-03-06 10:41:01.065052

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c6818ff61a90'
down_revision: Union[str, None] = '2484701f5ab1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 插入初始 L1 诊断规则（示例规则，实际部署时需根据真实点位 ID 调整）
    op.execute("""
        INSERT INTO diagnosis_rules (rule_code, name, description, category, trigger_condition, diagnosis_logic, priority, is_enabled, is_system, created_at, updated_at)
        VALUES
        ('L1_R001', 'UPS电池低压', 'UPS电池组电压过低告警', 'power/ups',
         '{"logic": "AND", "conditions": [{"point_id": "ups_battery_voltage", "operator": "<", "value": 44.0}]}',
         '{"conclusion": "UPS电池组电压过低，可能需要更换电池", "confidence": 0.9, "suggested_actions": ["检查电池组内阻", "联系维保更换电池"], "possible_causes": ["电池老化", "充电器故障"]}',
         10, 1, 1, datetime('now'), datetime('now')),

        ('L1_R002', 'UPS过载', 'UPS负载率过高告警', 'power/ups',
         '{"logic": "AND", "conditions": [{"point_id": "ups_load_percent", "operator": ">", "value": 90.0}]}',
         '{"conclusion": "UPS负载过高，存在过载风险", "confidence": 0.85, "suggested_actions": ["检查负载分布", "考虑扩容"], "possible_causes": ["新增设备", "负载不均"]}',
         15, 1, 1, datetime('now'), datetime('now')),

        ('L1_R003', '机房温度过高', '机房环境温度超标', 'environment/temperature',
         '{"logic": "AND", "conditions": [{"point_id": "room_temperature", "operator": ">", "value": 28.0}]}',
         '{"conclusion": "机房温度过高，可能影响设备稳定性", "confidence": 0.85, "suggested_actions": ["检查空调运行状态", "检查冷通道封闭"], "possible_causes": ["空调故障", "冷量不足", "热通道泄漏"]}',
         20, 1, 1, datetime('now'), datetime('now'))
    """)


def downgrade() -> None:
    op.execute("DELETE FROM diagnosis_rules WHERE rule_code IN ('L1_R001', 'L1_R002', 'L1_R003')")
