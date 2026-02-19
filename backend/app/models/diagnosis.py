"""
诊断规则模型
Story 9-3: 智能故障诊断
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, JSON

from ..core.database import Base


class DiagnosisRule(Base):
    """诊断规则表"""
    __tablename__ = "diagnosis_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_code = Column(String(50), unique=True, nullable=False, comment="规则编码")
    name = Column(String(100), nullable=False, comment="规则名称")
    description = Column(Text, nullable=True, comment="规则描述")
    category = Column(String(30), nullable=False, comment="分类: temperature/humidity/power/communication/security/cooling/environment/composite")
    trigger_condition = Column(JSON, comment="触发条件")
    diagnosis_logic = Column(JSON, comment="诊断逻辑(含possible_causes)")
    priority = Column(Integer, default=0, comment="优先级(高优先匹配)")
    is_enabled = Column(Boolean, default=True, comment="是否启用")
    is_system = Column(Boolean, default=False, comment="是否系统内置规则")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")


class DiagnosisResult(Base):
    """诊断结果表"""
    __tablename__ = "diagnosis_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alarm_id = Column(Integer, ForeignKey("alarms.id"), nullable=True, comment="告警ID")
    alarm_no = Column(String(50), nullable=True, comment="告警编号(冗余)")
    rule_id = Column(Integer, ForeignKey("diagnosis_rules.id"), nullable=True, comment="匹配规则ID")
    rule_code = Column(String(50), nullable=True, comment="规则编码(冗余)")
    device_type = Column(String(20), nullable=True, comment="设备类型")
    zone = Column(String(10), nullable=True, comment="区域")
    causes = Column(JSON, comment="诊断原因列表")
    diagnosis_time_ms = Column(Integer, default=0, comment="诊断耗时(毫秒)")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
