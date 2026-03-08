"""
诊断规则模型
Story 9-3: 智能故障诊断
Story 24.6: 诊断会话、审计日志、结果扩展
Story 25.3: UPS电池SOH预测
Story 25.5: 传感器元数据与精度加权
Story 25.7: 趋势分析与多传感器融合
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


class TrendWarning(Base):
    """趋势预警记录表 - Story 25.7"""

    __tablename__ = "trend_warnings"
    __table_args__ = (
        Index("idx_trend_warnings_point_time", "point_id", "detected_at"),
        Index("idx_trend_warnings_ack", "acknowledged", "detected_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    point_id = Column(Integer, ForeignKey("points.id", ondelete="CASCADE"), nullable=False, comment="点位ID")
    trend_type = Column(String(20), nullable=False, comment="趋势类型: 上升/下降")
    start_value = Column(Float, nullable=False, comment="起始值")
    end_value = Column(Float, nullable=False, comment="结束值")
    total_change = Column(Float, nullable=False, comment="总变化量")
    message = Column(Text, nullable=False, comment="预警消息")
    level = Column(String(20), nullable=False, default="info", comment="预警级别")
    detected_at = Column(DateTime, nullable=False, default=datetime.now, comment="检测时间")
    acknowledged = Column(Boolean, nullable=False, default=False, comment="是否已确认")
    acknowledged_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, comment="确认人ID")
    acknowledged_at = Column(DateTime, nullable=True, comment="确认时间")


class SensorFusionRecord(Base):
    """多传感器融合记录表 - Story 25.7"""

    __tablename__ = "sensor_fusion_records"
    __table_args__ = (
        Index("idx_sensor_fusion_zone_time", "zone_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    zone_id = Column(Integer, ForeignKey("cooling_zones.id", ondelete="CASCADE"), nullable=False, comment="区域ID")
    sensor_count = Column(Integer, nullable=False, comment="传感器数量")
    std_dev = Column(Float, nullable=True, comment="标准差")
    evidence_type = Column(String(50), nullable=False, comment="证据类型")
    is_evidence = Column(Boolean, nullable=False, default=False, comment="是否作为证据")
    probability = Column(Float, nullable=True, comment="概率")
    message = Column(Text, nullable=True, comment="融合结果消息")
    created_at = Column(DateTime, nullable=False, default=datetime.now, comment="创建时间")


class CounterfactualAnalysis(Base):
    """反事实分析表 - Story 26.1"""

    __tablename__ = "counterfactual_analyses"
    __table_args__ = (
        Index("idx_counterfactual_session", "session_id"),
        Index("idx_counterfactual_created", "created_at"),
        Index("idx_counterfactual_confidence", "original_confidence"),
        Index("idx_counterfactual_time", "analysis_time_ms"),
        Index("idx_counterfactual_deleted", "deleted_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("diagnosis_sessions.id", ondelete="CASCADE"), nullable=False, unique=True, comment="诊断会话ID")
    original_root_cause = Column(String(500), nullable=True, comment="原始根因")
    original_confidence = Column(Float, nullable=True, comment="原始置信度")
    top_evidences = Column(JSON, nullable=False, comment="Top证据列表")
    analysis_results = Column(JSON, nullable=False, comment="分析结果")
    analysis_time_ms = Column(Integer, nullable=False, default=0, comment="分析耗时(毫秒)")
    fault_tree_version = Column(String(50), nullable=True, comment="故障树版本号")
    config_version = Column(String(50), nullable=True, comment="配置版本号")
    deleted_at = Column(DateTime, nullable=True, comment="软删除时间")
    created_at = Column(DateTime, nullable=False, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now, comment="更新时间")


class SystemReport(Base):
    """系统报告表 - Story 26.2"""

    __tablename__ = "system_reports"
    __table_args__ = (
        Index("idx_system_reports_type_period", "report_type", "report_period"),
        Index("idx_system_reports_generated", "generated_at"),
        Index("idx_system_reports_deleted", "deleted_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_type = Column(String(50), nullable=False, comment="报告类型")
    report_period = Column(String(20), nullable=False, comment="报告周期 YYYY-MM")
    report_version = Column(String(20), nullable=True, default="v1.0", comment="报告模板版本")
    content = Column(Text, nullable=False, comment="Markdown 格式报告内容")
    summary = Column(JSON, nullable=True, comment="报告摘要（关键指标）")
    generated_at = Column(DateTime, nullable=True, default=datetime.now, comment="生成时间")
    generated_by = Column(String(100), nullable=True, comment="生成者")
    deleted_at = Column(DateTime, nullable=True, comment="软删除时间戳")
    updated_at = Column(DateTime, nullable=True, default=datetime.now, onupdate=datetime.now, comment="更新时间")


class DiagnosisImprovementRule(Base):
    """诊断改进建议规则表 - Story 26.2"""

    __tablename__ = "diagnosis_improvement_rules"
    __table_args__ = (
        Index("idx_improvement_rules_type_node", "rule_type", "node_id"),
        Index("idx_improvement_rules_type_fault", "rule_type", "fault_type"),
        Index("idx_improvement_rules_active", "is_active"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_type = Column(String(20), nullable=False, comment="规则类型: false_positive 或 false_negative")
    node_id = Column(String(100), nullable=True, comment="故障树节点ID（误报规则）")
    fault_type = Column(String(100), nullable=True, comment="故障类型（漏报规则）")
    suggestion_template = Column(Text, nullable=False, comment="建议模板（支持变量替换）")
    priority = Column(Integer, nullable=True, default=0, comment="优先级（数字越大优先级越高）")
    is_active = Column(Boolean, nullable=True, default=True, comment="是否启用")
    created_at = Column(DateTime, nullable=True, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, nullable=True, default=datetime.now, onupdate=datetime.now, comment="更新时间")


class ProbabilityAdjustmentLog(Base):
    """概率调参记录表 - Story 26.3"""

    __tablename__ = "probability_adjustment_logs"
    __table_args__ = (
        Index("idx_adjustment_logs_tree", "tree_id"),
        Index("idx_adjustment_logs_node", "node_id"),
        Index("idx_adjustment_logs_status", "status"),
        Index("idx_adjustment_logs_created", "created_at"),
        Index("idx_adjustment_logs_approved_by", "approved_by"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    tree_id = Column(Integer, ForeignKey("fault_trees.id", ondelete="CASCADE"), nullable=False, comment="故障树ID")
    node_id = Column(Integer, ForeignKey("fault_tree_nodes.id", ondelete="CASCADE"), nullable=False, comment="节点ID")
    node_name = Column(String(200), nullable=False, comment="节点名称")
    node_type = Column(String(20), nullable=False, comment="节点类型: root/intermediate/leaf")
    current_probability = Column(Float, nullable=False, comment="当前先验概率")
    proposed_probability = Column(Float, nullable=False, comment="建议先验概率")
    adjustment_percent = Column(Float, nullable=False, comment="调整百分比")
    sample_count = Column(Integer, nullable=False, comment="样本数")
    accurate_count = Column(Integer, nullable=False, comment="准确标注次数")
    inaccurate_count = Column(Integer, nullable=False, comment="不准确标注次数")
    accuracy_rate = Column(Float, nullable=False, comment="准确率")
    status = Column(String(20), nullable=False, default="pending", comment="状态: pending/approved/rejected")
    reason = Column(Text, nullable=True, comment="审批理由或拒绝原因")
    approved_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, comment="审批人ID")
    approved_at = Column(DateTime, nullable=True, comment="审批时间")
    version = Column(Integer, nullable=False, default=1, comment="乐观锁版本号")
    created_at = Column(DateTime, nullable=False, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now, comment="更新时间")


class AuditLog(Base):
    """通用审计日志表 - Story 26.4"""

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("idx_audit_logs_user_id", "user_id"),
        Index("idx_audit_logs_action", "action"),
        Index("idx_audit_logs_resource", "resource_type", "resource_id"),
        Index("idx_audit_logs_created_at", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, comment="用户ID")
    action = Column(String(100), nullable=False, comment="操作类型")
    resource_type = Column(String(50), nullable=False, comment="资源类型")
    resource_id = Column(Integer, nullable=True, comment="资源ID")
    details = Column(Text, nullable=True, comment="操作详情")
    ip_address = Column(String(50), nullable=True, comment="IP地址")
    user_agent = Column(String(500), nullable=True, comment="User Agent")
    created_at = Column(DateTime, nullable=False, default=datetime.now, comment="创建时间")


class TimeWindowAdjustmentLog(Base):
    """时间窗口调参记录表 - Story 26.4"""

    __tablename__ = "time_window_adjustment_logs"
    __table_args__ = (
        Index("idx_adjustment_logs_device_type", "device_type"),
        Index("idx_adjustment_logs_status", "status"),
        Index("idx_adjustment_logs_created", "created_at"),
        Index("idx_adjustment_logs_approved_by", "approved_by"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_type = Column(String(100), nullable=False, comment="设备类型")
    current_window_minutes = Column(Integer, nullable=False, comment="当前时间窗口(分钟)")
    proposed_window_minutes = Column(Integer, nullable=False, comment="建议时间窗口(分钟)")
    adjustment_percent = Column(Float, nullable=False, comment="调整百分比")
    sample_count = Column(Integer, nullable=False, comment="样本数")
    p50_duration_seconds = Column(Float, nullable=False, comment="P50持续时长(秒)")
    p90_duration_seconds = Column(Float, nullable=False, comment="P90持续时长(秒)")
    status = Column(String(20), nullable=False, default="pending", comment="状态: pending/approved/rejected")
    reason = Column(Text, nullable=True, comment="审批理由或拒绝原因")
    approved_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, comment="审批人ID")
    approved_at = Column(DateTime, nullable=True, comment="审批时间")
    version = Column(Integer, nullable=False, default=1, comment="乐观锁版本号")
    created_at = Column(DateTime, nullable=False, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now, comment="更新时间")

