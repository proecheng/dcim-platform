"""
告警模型
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, Text, ForeignKey, Date

from ..core.database import Base


class AlarmThreshold(Base):
    """告警阈值配置表"""
    __tablename__ = "alarm_thresholds"

    id = Column(Integer, primary_key=True, autoincrement=True)
    point_id = Column(Integer, ForeignKey("points.id"), nullable=False, comment="点位ID")
    threshold_type = Column(String(20), nullable=False, comment="阈值类型: high_high/high/low/low_low/equal/change")
    threshold_value = Column(Float, comment="阈值")
    alarm_level = Column(String(20), default="minor", comment="告警级别: critical/major/minor/info")
    alarm_message = Column(String(200), comment="告警消息")
    delay_seconds = Column(Integer, default=0, comment="延迟触发(秒)")
    dead_band = Column(Float, default=0, comment="死区(回差)")
    is_enabled = Column(Boolean, default=True, comment="是否启用")
    priority = Column(Integer, default=0, comment="优先级")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")


class Alarm(Base):
    """告警记录表"""
    __tablename__ = "alarms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alarm_no = Column(String(50), unique=True, nullable=False, comment="告警编号")
    point_id = Column(Integer, ForeignKey("points.id"), nullable=False, comment="点位ID")
    threshold_id = Column(Integer, ForeignKey("alarm_thresholds.id"), comment="阈值配置ID")
    alarm_level = Column(String(20), nullable=False, comment="告警级别")
    alarm_type = Column(String(20), comment="告警类型: threshold/communication/system")
    alarm_message = Column(Text, nullable=False, comment="告警消息")
    trigger_value = Column(Float, comment="触发值")
    threshold_value = Column(Float, comment="阈值")
    status = Column(String(20), default="active", comment="状态: active/acknowledged/resolved/ignored")
    acknowledged_by = Column(Integer, ForeignKey("users.id"), comment="确认人")
    acknowledged_at = Column(DateTime, comment="确认时间")
    ack_remark = Column(Text, comment="确认备注")
    resolved_by = Column(Integer, ForeignKey("users.id"), comment="解决人")
    resolved_at = Column(DateTime, comment="解决时间")
    resolve_remark = Column(Text, comment="解决备注")
    resolve_type = Column(String(20), comment="解决类型: manual/auto/timeout")
    duration_seconds = Column(Integer, comment="持续时间(秒)")
    is_notified = Column(Boolean, default=False, comment="是否已通知")
    notify_count = Column(Integer, default=0, comment="通知次数")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")


class AlarmRule(Base):
    """告警规则表（复合告警）"""
    __tablename__ = "alarm_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_name = Column(String(100), nullable=False, comment="规则名称")
    rule_type = Column(String(20), comment="规则类型: and/or/sequence")
    condition_expr = Column(Text, comment="条件表达式")
    alarm_level = Column(String(20), comment="告警级别")
    alarm_message = Column(String(200), comment="告警消息")
    is_enabled = Column(Boolean, default=True, comment="是否启用")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")


class AlarmShield(Base):
    """告警屏蔽表"""
    __tablename__ = "alarm_shields"

    id = Column(Integer, primary_key=True, autoincrement=True)
    point_id = Column(Integer, ForeignKey("points.id"), comment="点位ID(空表示全局)")
    alarm_level = Column(String(20), comment="屏蔽级别(空表示全部)")
    start_time = Column(DateTime, nullable=False, comment="开始时间")
    end_time = Column(DateTime, nullable=False, comment="结束时间")
    reason = Column(Text, comment="屏蔽原因")
    created_by = Column(Integer, ForeignKey("users.id"), comment="创建人")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")


class AlarmDailyStats(Base):
    """告警统计表（按天聚合）"""
    __tablename__ = "alarm_daily_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stat_date = Column(Date, nullable=False, comment="统计日期")
    point_id = Column(Integer, comment="点位ID")
    alarm_level = Column(String(20), comment="告警级别")
    total_count = Column(Integer, default=0, comment="总数")
    ack_count = Column(Integer, default=0, comment="已确认数")
    resolve_count = Column(Integer, default=0, comment="已解决数")
    avg_duration_seconds = Column(Integer, comment="平均持续时间")
    max_duration_seconds = Column(Integer, comment="最大持续时间")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
