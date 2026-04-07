"""
回退保护事件模型

Story 30.2: 7 项自动回退保护机制
"""

from enum import Enum
from datetime import datetime

from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey

from app.core.database import Base


class RollbackTriggerType(str, Enum):
    """回退触发类型"""

    TEMP_OVER_LIMIT = "temp_over_limit"  # 条件1: T_inlet > 26°C
    RATE_OVER_PREDICTED = "rate_over_predicted"  # 条件2: 温升超预测 150%
    RATE_OVER_LIMIT = "rate_over_limit"  # 条件3: |dT/dt| > 5°C/h
    AC_FAULT = "ac_fault"  # 条件4: 空调故障告警
    SENSOR_OFFLINE = "sensor_offline"  # 条件5: 温度传感器离线
    UPS_ACTIVE = "ups_active"  # 条件6: 市电中断切 UPS
    HUMIDITY_DEW_POINT = "humidity_dew_point"  # 条件7: 湿度接近露点


class RollbackEvent(Base):
    """回退保护事件记录"""

    __tablename__ = "rollback_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    zone_id = Column(Integer, ForeignKey("cooling_zones.id"), nullable=False, comment="制冷区域 ID")
    trigger_type = Column(String(30), nullable=False, comment="触发类型")
    trigger_value = Column(Float, nullable=True, comment="触发时的实际值")
    threshold = Column(Float, nullable=True, comment="阈值")
    action = Column(String(100), nullable=False, comment="执行的回退动作")
    status = Column(String(20), default="active", comment="状态: active/resolved")
    context_json = Column(Text, nullable=True, comment="附加上下文 JSON")
    created_at = Column(DateTime, default=datetime.now, comment="触发时间")
    resolved_at = Column(DateTime, nullable=True, comment="恢复时间")
