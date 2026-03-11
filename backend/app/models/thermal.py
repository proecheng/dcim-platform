"""
热动力学数据模型 — 热参数标定与温度预测记录

基于架构文档 V4.2.0 Section 21 设计
"""

from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    Date,
    Time,
    ForeignKey,
    Index,
    UniqueConstraint,
)
from sqlalchemy.types import JSON

from ..core.database import Base


class ThermalParameter(Base):
    """热参数标定记录表

    记录制冷区域的 R/C 参数标定历史，支持多版本管理
    """

    __tablename__ = "thermal_parameters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cooling_zone_id = Column(
        Integer,
        ForeignKey("cooling_zones.id", ondelete="CASCADE"),
        nullable=False,
        comment="关联制冷区域ID"
    )
    thermal_R = Column(Float, nullable=True, comment="热阻标定值 °C/kW")
    thermal_C = Column(Float, nullable=True, comment="热容标定值 kWh/°C（总热容，非单位面积）")
    fitting_r_squared = Column(Float, nullable=True, comment="拟合 R² 值")
    fitting_method = Column(
        String(20),
        nullable=True,
        default="manual",
        comment="标定方法: auto_fit/manual/default"
    )
    sample_count = Column(Integer, nullable=True, comment="样本数")
    calibrated_at = Column(DateTime, nullable=True, comment="标定时间")
    is_active = Column(Boolean, default=True, comment="是否为当前生效参数")
    is_demo = Column(Boolean, default=False, comment="是否为 demo 数据")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        comment="更新时间"
    )

    # 复合索引：cooling_zone_id + is_active
    __table_args__ = (
        Index("ix_thermal_params_zone_active", "cooling_zone_id", "is_active"),
        # 部分唯一索引：确保每个 zone 只有一个活跃版本
        # 注意：SQLite 不支持部分唯一索引，需要在应用层或迁移脚本中处理
        UniqueConstraint(
            "cooling_zone_id",
            "is_active",
            name="uq_thermal_params_zone_active",
            # sqlite_where 仅在 PostgreSQL 中生效
        ),
    )


class TemperaturePredictionLog(Base):
    """温度预测记录表

    记录温度预测偏差，用于模型验证
    采用单条记录模式（非 JSON 批量），便于 TimescaleDB 时序查询
    """

    __tablename__ = "temperature_prediction_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cooling_zone_id = Column(
        Integer,
        ForeignKey("cooling_zones.id", ondelete="CASCADE"),
        nullable=False,
        comment="关联制冷区域ID"
    )
    predicted_temp = Column(Float, nullable=False, comment="预测温度 °C")
    actual_temp = Column(Float, nullable=True, comment="实际温度 °C")
    prediction_horizon_min = Column(Integer, nullable=False, comment="预测时长 分钟")
    deviation = Column(Float, nullable=True, comment="偏差 = actual - predicted")
    model_version = Column(String(50), nullable=False, comment="模型参数版本")
    created_at = Column(DateTime, default=datetime.now, nullable=False, comment="记录时间")

    # 复合索引：cooling_zone_id ASC + created_at DESC（时序查询优化）
    __table_args__ = (
        Index("ix_temp_pred_zone_time", "cooling_zone_id", created_at.desc()),
    )


class PrecoolSchedule(Base):
    """预冷计划表

    存储由贪心优化算法生成的预冷调度计划，
    包含预冷/峰时时段、温度轨迹、节省电费等信息。
    """

    __tablename__ = "precool_schedules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cooling_zone_id = Column(
        Integer,
        ForeignKey("cooling_zones.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="关联制冷区域ID"
    )
    schedule_date = Column(Date, nullable=False, comment="计划日期")

    # 预冷时段
    precool_start_time = Column(Time, nullable=False, comment="预冷开始时间（谷时）")
    precool_end_time = Column(Time, nullable=False, comment="预冷结束时间")
    target_temp = Column(Float, nullable=False, comment="预冷目标温度 °C")

    # 峰时削减时段
    peak_start_time = Column(Time, nullable=False, comment="峰时削减开始时间")
    peak_end_time = Column(Time, nullable=False, comment="峰时削减结束时间")

    # 能效指标
    planned_savings_kwh = Column(Float, default=0.0, comment="计划节省电量 kWh")
    actual_savings_kwh = Column(Float, nullable=True, comment="实际节省电量 kWh")

    # 执行状态
    status = Column(
        String(20),
        default="pending",
        index=True,
        comment="状态: pending/executing/completed/aborted"
    )
    abort_reason = Column(String(500), nullable=True, comment="中止原因")

    # 温度轨迹 JSON
    temperature_trajectory = Column(
        JSON,
        nullable=True,
        comment="预测/实际温度轨迹 JSON: {predicted: [...], timestamps: [...]}"
    )

    # 验证信息
    is_validated = Column(Boolean, default=False, comment="是否通过约束验证")
    validated_at = Column(DateTime, nullable=True, comment="验证时间")

    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        comment="更新时间"
    )

    __table_args__ = (
        UniqueConstraint(
            "cooling_zone_id",
            "schedule_date",
            name="uq_zone_schedule_date"
        ),
        Index("ix_precool_schedules_status", "status"),
    )
