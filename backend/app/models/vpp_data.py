"""
虚拟电厂(VPP)数据模型
VPP Data Models for Virtual Power Plant solution
"""
from datetime import datetime, date, time
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Date, Time, Enum
from sqlalchemy.sql import func
from app.core.database import Base
import enum


class TimePeriodType(str, enum.Enum):
    """时段类型枚举"""
    PEAK = "peak"      # 峰时
    VALLEY = "valley"  # 谷时
    FLAT = "flat"      # 平时


class ElectricityBill(Base):
    """电费清单表"""
    __tablename__ = "electricity_bills"

    id = Column(Integer, primary_key=True, autoincrement=True)
    month = Column(String(7), index=True, nullable=False, comment="月份 YYYY-MM格式")

    # 用电量数据
    total_consumption = Column(Float, nullable=False, comment="月度总用电量 kWh")
    peak_consumption = Column(Float, comment="峰段用电量 kWh")
    valley_consumption = Column(Float, comment="谷段用电量 kWh")
    flat_consumption = Column(Float, comment="平段用电量 kWh")

    # 需量数据
    max_demand = Column(Float, comment="最大需量 kW")
    power_factor = Column(Float, comment="功率因数")

    # 电费数据
    total_cost = Column(Float, nullable=False, comment="月度总电费 元")
    basic_fee = Column(Float, comment="基本电费 元")
    market_purchase_fee = Column(Float, comment="市场化购电电费 元")
    transmission_fee = Column(Float, comment="输配电费 元")
    system_operation_fee = Column(Float, comment="系统运行费 元")
    government_fund = Column(Float, comment="政府性基金及附加 元")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")


class LoadCurve(Base):
    """负荷曲线数据表 (15分钟间隔)"""
    __tablename__ = "load_curves"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, index=True, nullable=False, comment="时间戳 (15分钟间隔)")
    load_value = Column(Float, nullable=False, comment="负荷值 kW")
    date = Column(Date, index=True, nullable=False, comment="日期")
    time_period = Column(Enum(TimePeriodType), comment="时段类型 (峰/平/谷)")
    is_workday = Column(Boolean, default=True, comment="是否工作日")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")


class ElectricityPrice(Base):
    """电价配置表"""
    __tablename__ = "electricity_prices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    period_type = Column(Enum(TimePeriodType), nullable=False, comment="时段类型")
    price = Column(Float, nullable=False, comment="单价 元/kWh")
    start_time = Column(Time, nullable=False, comment="开始时间 HH:MM")
    end_time = Column(Time, nullable=False, comment="结束时间 HH:MM")
    effective_date = Column(Date, comment="生效日期")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")


class AdjustableLoad(Base):
    """可调节负荷资源表"""
    __tablename__ = "adjustable_loads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    equipment_name = Column(String(200), nullable=False, comment="设备名称")
    equipment_type = Column(String(100), comment="设备类型")
    rated_power = Column(Float, nullable=False, comment="额定功率 kW")
    adjustable_ratio = Column(Float, nullable=False, comment="可调节比例 %")
    response_time = Column(Integer, comment="响应时间 分钟")
    adjustment_cost = Column(Float, comment="调节成本 元/次")
    is_active = Column(Boolean, default=True, comment="是否启用")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")


class VPPConfig(Base):
    """VPP配置参数表"""
    __tablename__ = "vpp_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    config_key = Column(String(100), unique=True, index=True, nullable=False, comment="配置键")
    config_value = Column(Float, nullable=False, comment="配置值")
    config_unit = Column(String(50), comment="单位")
    description = Column(String(500), comment="描述")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
