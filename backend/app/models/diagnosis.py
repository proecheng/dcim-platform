"""
诊断规则模型
Story 9-3: 智能故障诊断
Story 24.6: 诊断会话、审计日志、结果扩展
Story 25.3: UPS电池SOH预测
Story 25.5: 传感器元数据与精度加权
"""

from datetime import datetime, date
from enum import Enum
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Float, ForeignKey, JSON, Index, Date

from ..core.database import Base


class CalibrationStatus(str, Enum):
    """校准状态枚举"""
    VALID = "valid"
    EXPIRED = "expired"
    NO_METADATA = "no_metadata"
    NOT_CALIBRATED = "not_calibrated"


class DiagnosisRule(Base):
    """诊断规则表"""

    __tablename__ = "diagnosis_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_code = Column(String(50), unique=True, nullable=False, comment="规则编码")
    name = Column(String(100), nullable=False, comment="规则名称")
    description = Column(Text, nullable=True, comment="规则描述")
    category = Column(
        String(30),
        nullable=False,
        comment="分类: temperature/humidity/power/communication/security/cooling/environment/composite",
    )
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

    # Story 24.2 迁移已创建的字段（补全模型声明）
    device_id = Column(Integer, nullable=True, index=True, comment="设备ID")
    diagnosis_level = Column(String(10), nullable=True, comment="诊断级别")
    matched = Column(Boolean, nullable=True, server_default='0', comment="是否匹配规则")
    conclusion = Column(Text, nullable=True, comment="诊断结论")
    confidence = Column(Float, nullable=True, comment="置信度")
    suggested_actions = Column(JSON, nullable=True, comment="建议操作")
    evidence = Column(JSON, nullable=True, comment="证据数据")
    inference_time_ms = Column(Integer, nullable=True, comment="推理耗时(毫秒)")
    error_message = Column(Text, nullable=True, comment="错误信息")

    # Story 24.6 新增字段
    session_id = Column(Integer, ForeignKey("diagnosis_sessions.id"), nullable=True, comment="诊断会话ID")
    root_cause = Column(String(500), nullable=True, comment="根因描述")
    reasoning_path = Column(JSON, nullable=True, comment="推理路径")
    fault_tree_version = Column(String(50), nullable=True, comment="故障树版本号")


class DiagnosisSession(Base):
    """诊断会话表 - Story 24.6"""

    __tablename__ = "diagnosis_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trigger_alarm_id = Column(Integer, ForeignKey("alarms.id"), nullable=True, comment="触发告警ID")
    device_id = Column(Integer, nullable=True, index=True, comment="设备ID")
    engine_level = Column(String(5), nullable=False, comment="推理级别: L1/L2/L3")
    status = Column(String(20), nullable=False, default="success", comment="会话状态: success/timeout/error/degraded")
    push_status = Column(String(20), nullable=False, default="skipped", comment="推送状态: pushed/failed/skipped")
    max_confidence = Column(Float, nullable=True, comment="最高置信度(冗余)")
    start_time = Column(DateTime, nullable=False, comment="推理开始时间")
    end_time = Column(DateTime, nullable=True, comment="推理结束时间")
    inference_time_ms = Column(Integer, default=0, comment="推理耗时(毫秒)")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")


class DiagnosisAuditLog(Base):
    """诊断审计日志表 - Story 24.6"""

    __tablename__ = "diagnosis_audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("diagnosis_sessions.id"), nullable=False, comment="会话ID")
    input_data = Column(JSON, comment="推理输入数据")
    output_data = Column(JSON, comment="推理输出数据")
    engine_level = Column(String(5), nullable=False, comment="推理级别")
    inference_time_ms = Column(Integer, default=0, comment="推理耗时(毫秒)")
    fault_tree_version = Column(String(50), nullable=True, comment="故障树版本号")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")


class DiagnosisAnnotation(Base):
    """诊断结果标注表 - Story 24.8"""

    __tablename__ = "diagnosis_annotations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("diagnosis_sessions.id", ondelete="CASCADE"), nullable=False, index=True, comment="诊断会话ID")
    annotator_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True, comment="标注者ID")
    annotation = Column(String(20), nullable=False, comment="标注结果: accurate/inaccurate/unknown")
    actual_root_cause = Column(Text, nullable=True, comment="实际根因(标注为inaccurate时必填)")
    notes = Column(Text, nullable=True, comment="备注")
    annotated_at = Column(DateTime, nullable=False, default=datetime.now, comment="标注时间")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")


class BatterySOHRecord(Base):
    """UPS电池SOH记录表 - Story 25.3"""

    __tablename__ = "battery_soh_records"
    __table_args__ = (
        Index("idx_battery_soh_device_id", "device_id"),
        Index("idx_battery_soh_calculated_at", "calculated_at"),
        Index("idx_battery_soh_device_time", "device_id", "calculated_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, comment="设备ID")
    soh_percent = Column(Float, nullable=False, comment="SOH百分比 [0-100]")
    resistance_mohm = Column(Float, nullable=True, comment="当前内阻(毫欧)")
    cycle_count = Column(Integer, nullable=True, comment="充放电循环次数")
    weights_version = Column(String(50), nullable=True, comment="权重配置版本")
    calculated_at = Column(DateTime, nullable=False, comment="计算时间(UTC)")


class SOHPointUnavailableTracking(Base):
    """SOH点位不可用追踪表 - Story 25.3"""

    __tablename__ = "soh_point_unavailable_tracking"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, unique=True, comment="设备ID")
    consecutive_days = Column(Integer, nullable=False, default=0, comment="连续不可用天数")
    last_unavailable_date = Column(DateTime, nullable=False, comment="最后一次不可用日期")
    alarm_triggered = Column(Boolean, nullable=False, default=False, comment="是否已触发告警")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")


class BreakerProfile(Base):
    """断路器配置表 - Story 25.4"""

    __tablename__ = "breaker_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    breaker_device_id = Column(Integer, ForeignKey("power_devices.id", ondelete="CASCADE"), nullable=False, unique=True, comment="断路器设备ID")
    trip_curve_type = Column(String(1), nullable=False, comment="脱扣曲线类型: B/C/D")
    rated_current = Column(Float, nullable=False, comment="额定电流 A")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")


class SensorMetadata(Base):
    """传感器元数据表 - Story 25.5"""

    __tablename__ = "sensor_metadata"

    id = Column(Integer, primary_key=True, autoincrement=True)
    point_id = Column(Integer, ForeignKey("points.id", ondelete="CASCADE"), nullable=False, unique=True, index=True, comment="点位ID")
    ct_pt_ratio = Column(Float, nullable=True, comment="CT/PT变比")
    accuracy_class = Column(Float, nullable=False, comment="精度等级: 0.2/0.5/1.0")
    calibration_date = Column(Date, nullable=True, comment="校准日期")
    calibration_interval_days = Column(Integer, nullable=False, default=365, comment="校准周期天数")
    calibration_result = Column(String(500), nullable=True, comment="校准结果描述")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")
