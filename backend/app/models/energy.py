"""
用电管理模型
Enhanced with meter points, transformers, distribution panels for comprehensive energy analysis
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, Float, Text, DateTime, Date, ForeignKey, JSON, func, Numeric
from sqlalchemy.orm import relationship

from ..core.database import Base


# ==================== 配电系统拓扑模型 ====================

class Transformer(Base):
    """变压器配置表"""
    __tablename__ = "transformers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    transformer_code = Column(String(50), unique=True, nullable=False, comment="变压器编码 如TR-001")
    transformer_name = Column(String(100), nullable=False, comment="变压器名称 如1#变压器")
    rated_capacity = Column(Float, nullable=False, comment="额定容量 kVA")
    voltage_high = Column(Float, default=10.0, comment="高压侧电压 kV")
    voltage_low = Column(Float, default=0.4, comment="低压侧电压 kV")
    connection_type = Column(String(20), default="Dyn11", comment="接线组别")
    efficiency = Column(Float, default=98.5, comment="效率 %")
    no_load_loss = Column(Float, comment="空载损耗 kW")
    load_loss = Column(Float, comment="负载损耗 kW")
    impedance_voltage = Column(Float, comment="阻抗电压 %")
    install_date = Column(Date, comment="安装日期")
    location = Column(String(100), comment="安装位置")
    status = Column(String(20), default="running", comment="状态: running/standby/maintenance/fault")
    is_enabled = Column(Boolean, default=True, comment="是否启用")

    # 需量配置
    declared_demand = Column(Float, comment="申报需量 kW")
    demand_type = Column(String(10), default="kW", comment="需量单位: kW/kVA")
    demand_warning_ratio = Column(Float, default=0.9, comment="需量预警比例 0-1")

    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    # 关系
    meter_points = relationship("MeterPoint", back_populates="transformer")


class MeterPoint(Base):
    """计量点配置表"""
    __tablename__ = "meter_points"

    id = Column(Integer, primary_key=True, autoincrement=True)
    meter_code = Column(String(50), unique=True, nullable=False, comment="计量点编码 如M001")
    meter_name = Column(String(100), nullable=False, comment="计量点名称")
    meter_no = Column(String(50), comment="电表号")
    transformer_id = Column(Integer, ForeignKey("transformers.id"), comment="关联变压器ID")

    # 计量点类型和测量类型
    meter_type = Column(String(20), default="main", comment="计量类型: main/sub/check")
    measurement_types = Column(JSON, default=list, comment="测量类型列表")

    # 计量参数
    ct_ratio = Column(String(20), comment="电流互感器倍率 如400/5")
    pt_ratio = Column(String(20), comment="电压互感器倍率 如10000/100")
    multiplier = Column(Float, default=1.0, comment="综合倍率")

    # 需量配置
    declared_demand = Column(Float, comment="申报需量 kW/kVA")
    demand_type = Column(String(10), default="kW", comment="需量类型: kW/kVA")
    demand_period = Column(Integer, default=15, comment="需量计算周期 分钟")

    # 电费户号关联
    customer_no = Column(String(50), comment="供电局户号")
    customer_name = Column(String(100), comment="户名")

    # 电价配置
    pricing_config_id = Column(Integer, ForeignKey("electricity_pricing.id"), comment="电价配置ID")

    status = Column(String(20), default="normal", comment="状态: normal/fault/offline")
    is_enabled = Column(Boolean, default=True, comment="是否启用")
    remark = Column(Text, comment="备注")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    # 关系
    transformer = relationship("Transformer", back_populates="meter_points")
    panels = relationship("DistributionPanel", back_populates="meter_point")


class DistributionPanel(Base):
    """配电柜/开关柜表"""
    __tablename__ = "distribution_panels"

    id = Column(Integer, primary_key=True, autoincrement=True)
    panel_code = Column(String(50), unique=True, nullable=False, comment="配电柜编码 如PDU-001")
    panel_name = Column(String(100), nullable=False, comment="配电柜名称")
    panel_type = Column(String(20), nullable=False, comment="类型: main/sub/ups_input/ups_output")
    rated_current = Column(Float, comment="额定电流 A")
    rated_voltage = Column(Float, default=380, comment="额定电压 V")

    # 上下级关系
    parent_panel_id = Column(Integer, ForeignKey("distribution_panels.id"), comment="上级配电柜ID")
    transformer_id = Column(Integer, ForeignKey("transformers.id"), comment="关联变压器ID")
    meter_point_id = Column(Integer, ForeignKey("meter_points.id"), comment="关联计量点ID")

    # 位置
    location = Column(String(100), comment="安装位置")
    area_code = Column(String(10), comment="区域代码")

    status = Column(String(20), default="running", comment="状态: running/fault/maintenance")
    is_enabled = Column(Boolean, default=True, comment="是否启用")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    # 关系
    meter_point = relationship("MeterPoint", back_populates="panels")
    circuits = relationship("DistributionCircuit", back_populates="panel")


class DistributionCircuit(Base):
    """配电回路表"""
    __tablename__ = "distribution_circuits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    circuit_code = Column(String(50), unique=True, nullable=False, comment="回路编码 如C001")
    circuit_name = Column(String(100), nullable=False, comment="回路名称")
    panel_id = Column(Integer, ForeignKey("distribution_panels.id"), nullable=False, comment="所属配电柜ID")

    # 回路参数
    rated_current = Column(Float, comment="额定电流 A")
    breaker_type = Column(String(50), comment="断路器型号")
    breaker_rating = Column(Float, comment="断路器额定值 A")

    # 负载类型
    load_type = Column(String(20), comment="负载类型: ups/hvac/it_equipment/lighting/general/emergency")

    # 负荷转移配置
    is_shiftable = Column(Boolean, default=False, comment="是否可转移负荷")
    shift_priority = Column(Integer, default=99, comment="转移优先级 (1最高)")
    min_runtime_hours = Column(Float, comment="最小运行时长要求 小时")

    is_enabled = Column(Boolean, default=True, comment="是否启用")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    # 关系
    panel = relationship("DistributionPanel", back_populates="circuits")
    devices = relationship("PowerDevice", back_populates="circuit")


# ==================== 功率曲线与需量数据 ====================

class PowerCurveData(Base):
    """功率曲线数据表 (15分钟粒度)"""
    __tablename__ = "power_curve_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    meter_point_id = Column(Integer, ForeignKey("meter_points.id"), comment="计量点ID")
    device_id = Column(Integer, ForeignKey("power_devices.id"), comment="设备ID")
    timestamp = Column(DateTime, nullable=False, comment="时间戳")

    # 功率数据
    active_power = Column(Float, comment="有功功率 kW")
    reactive_power = Column(Float, comment="无功功率 kVar")
    apparent_power = Column(Float, comment="视在功率 kVA")
    power_factor = Column(Float, comment="功率因数")

    # 电能数据
    cumulative_energy = Column(Float, comment="累计电量 kWh")
    incremental_energy = Column(Float, comment="增量电量 kWh")

    # 需量数据
    demand_15min = Column(Float, comment="15分钟需量 kW")
    demand_rolling = Column(Float, comment="滑动窗口需量 kW")

    # 分时标识
    time_period = Column(String(10), comment="时段: sharp/peak/flat/valley/deep_valley")

    created_at = Column(DateTime, default=datetime.now, comment="创建时间")


class DemandHistory(Base):
    """需量历史记录表 (月度)"""
    __tablename__ = "demand_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    meter_point_id = Column(Integer, ForeignKey("meter_points.id"), nullable=False, comment="计量点ID")
    stat_year = Column(Integer, nullable=False, comment="统计年份")
    stat_month = Column(Integer, nullable=False, comment="统计月份")

    # 需量统计
    declared_demand = Column(Float, comment="申报需量 kW")
    max_demand = Column(Float, comment="当月最大需量 kW")
    avg_demand = Column(Float, comment="当月平均需量 kW")
    demand_95th = Column(Float, comment="95%分位数需量 kW")
    max_demand_time = Column(DateTime, comment="最大需量发生时间")

    # 超限统计
    over_declared_times = Column(Integer, default=0, comment="超申报次数")
    over_declared_max = Column(Float, comment="超申报最大值 kW")

    # 电费相关
    demand_cost = Column(Float, comment="需量电费 元")
    over_demand_penalty = Column(Float, default=0, comment="超需量罚款 元")

    created_at = Column(DateTime, default=datetime.now, comment="创建时间")


class OverDemandEvent(Base):
    """需量超限事件表"""
    __tablename__ = "over_demand_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    meter_point_id = Column(Integer, ForeignKey("meter_points.id"), nullable=False, comment="计量点ID")
    event_time = Column(DateTime, nullable=False, comment="事件时间")

    demand_value = Column(Float, nullable=False, comment="需量值 kW")
    declared_demand = Column(Float, nullable=False, comment="申报需量 kW")
    over_amount = Column(Float, nullable=False, comment="超出量 kW")
    duration_minutes = Column(Integer, comment="持续时间 分钟")

    # 贡献设备分析 (JSON格式)
    contributing_devices = Column(JSON, comment="贡献设备列表 [{device_id, device_name, power}]")

    is_processed = Column(Boolean, default=False, comment="是否已处理")
    process_note = Column(Text, comment="处理备注")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")


# ==================== 设备扩展属性 ====================

class DeviceLoadProfile(Base):
    """设备负荷曲线配置表"""
    __tablename__ = "device_load_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(Integer, ForeignKey("power_devices.id"), unique=True, nullable=False, comment="设备ID")

    # 负荷曲线类型
    profile_type = Column(String(20), default="constant", comment="类型: constant/variable/scheduled/demand_response")

    # 典型日负荷曲线 (JSON: 24个小时的负载系数)
    hourly_load_factors = Column(JSON, comment="每小时负载系数 [0-1], 长度24")

    # 周负荷特征
    weekday_factor = Column(Float, default=1.0, comment="工作日系数")
    weekend_factor = Column(Float, default=0.8, comment="周末系数")

    # 季节系数
    summer_factor = Column(Float, default=1.2, comment="夏季系数")
    winter_factor = Column(Float, default=1.0, comment="冬季系数")

    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")


class DeviceShiftConfig(Base):
    """设备负荷转移配置表"""
    __tablename__ = "device_shift_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(Integer, ForeignKey("power_devices.id"), unique=True, nullable=False, comment="设备ID")

    # 可转移性
    is_shiftable = Column(Boolean, default=False, comment="是否可转移")
    shiftable_power_ratio = Column(Float, default=0, comment="可转移功率比例 0-1")
    is_critical = Column(Boolean, default=False, comment="是否关键负荷")

    # 时间约束 (JSON)
    allowed_shift_hours = Column(JSON, comment="允许转移的时段 [0-23]")
    forbidden_shift_hours = Column(JSON, comment="禁止转移的时段 [0-23]")
    min_continuous_runtime = Column(Float, comment="最小连续运行时间 小时")
    max_shift_duration = Column(Float, comment="最大转移持续时间 小时")

    # 功率约束
    min_power = Column(Float, comment="最低运行功率 kW")
    max_ramp_rate = Column(Float, comment="最大爬坡速率 kW/min")

    # 业务约束
    shift_notice_time = Column(Integer, default=30, comment="转移提前通知时间 分钟")
    requires_manual_approval = Column(Boolean, default=True, comment="是否需要人工确认")

    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")


class PowerDevice(Base):
    """用电设备表"""
    __tablename__ = "power_devices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_code = Column(String(50), unique=True, nullable=False, comment="设备编码")
    device_name = Column(String(100), nullable=False, comment="设备名称")
    device_type = Column(String(20), nullable=False, comment="设备类型: UPS/HVAC/IT_SERVER/IT_STORAGE/LIGHTING/PUMP/OTHER")
    rated_power = Column(Float, comment="额定功率 kW")
    rated_voltage = Column(Float, comment="额定电压 V")
    rated_current = Column(Float, comment="额定电流 A")
    power_factor = Column(Float, default=0.9, comment="额定功率因数")
    efficiency = Column(Float, default=95, comment="设备效率 %")
    phase_type = Column(String(10), default="3P", comment="相位类型: 1P/3P")

    # 配电关系 - 扩展
    parent_device_id = Column(Integer, ForeignKey("power_devices.id"), comment="上级设备ID(配电关系)")
    circuit_id = Column(Integer, ForeignKey("distribution_circuits.id"), comment="所属回路ID")
    circuit_no = Column(String(20), comment="回路编号")

    # ==================== 新增: 点位关联 ====================
    # 关联动环监控设备(用于获取实时数据)
    monitor_device_id = Column(Integer, ForeignKey("devices.id"), comment="关联动环设备ID")

    # 关联电力点位（直接关联具体采集点位）
    power_point_id = Column(Integer, ForeignKey("points.id"), comment="有功功率点位ID")
    energy_point_id = Column(Integer, ForeignKey("points.id"), comment="累计电量点位ID")
    voltage_point_id = Column(Integer, ForeignKey("points.id"), comment="电压点位ID")
    current_point_id = Column(Integer, ForeignKey("points.id"), comment="电流点位ID")
    pf_point_id = Column(Integer, ForeignKey("points.id"), comment="功率因数点位ID")

    # 负荷特性
    is_metered = Column(Boolean, default=True, comment="是否计量")
    is_it_load = Column(Boolean, default=False, comment="是否IT负载(用于PUE计算)")
    is_critical = Column(Boolean, default=False, comment="是否关键负荷(不可中断)")

    # 运行参数
    avg_load_rate = Column(Float, comment="平均负载率 %")
    peak_load_rate = Column(Float, comment="峰值负载率 %")
    daily_energy = Column(Float, comment="日均用电量 kWh")

    area_code = Column(String(10), comment="区域代码")
    description = Column(Text, comment="描述")
    is_enabled = Column(Boolean, default=True, comment="是否启用")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    # 关系
    circuit = relationship("DistributionCircuit", back_populates="devices")
    load_profile = relationship("DeviceLoadProfile", uselist=False, backref="device")
    shift_config = relationship("DeviceShiftConfig", uselist=False, backref="device")


class EnergyHourly(Base):
    """小时能耗表"""
    __tablename__ = "energy_hourly"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(Integer, ForeignKey("power_devices.id"), nullable=False, comment="设备ID")
    stat_time = Column(DateTime, nullable=False, comment="统计时间(整点)")
    total_energy = Column(Float, default=0, comment="总电量 kWh")
    avg_power = Column(Float, default=0, comment="平均功率 kW")
    max_power = Column(Float, default=0, comment="最大功率 kW")
    min_power = Column(Float, default=0, comment="最小功率 kW")
    avg_voltage = Column(Float, comment="平均电压 V")
    avg_current = Column(Float, comment="平均电流 A")
    avg_power_factor = Column(Float, comment="平均功率因数")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")


class EnergyDaily(Base):
    """日能耗表"""
    __tablename__ = "energy_daily"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(Integer, ForeignKey("power_devices.id"), nullable=False, comment="设备ID")
    stat_date = Column(Date, nullable=False, comment="统计日期")
    total_energy = Column(Float, default=0, comment="总电量 kWh")
    peak_energy = Column(Float, default=0, comment="峰时电量 kWh")
    normal_energy = Column(Float, default=0, comment="平时电量 kWh")
    valley_energy = Column(Float, default=0, comment="谷时电量 kWh")
    max_power = Column(Float, default=0, comment="最大功率 kW")
    avg_power = Column(Float, default=0, comment="平均功率 kW")
    max_power_time = Column(DateTime, comment="最大功率时间")
    energy_cost = Column(Float, default=0, comment="电费 元")
    pue = Column(Float, comment="当日PUE")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")


class EnergyMonthly(Base):
    """月能耗表"""
    __tablename__ = "energy_monthly"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(Integer, ForeignKey("power_devices.id"), nullable=False, comment="设备ID")
    stat_year = Column(Integer, nullable=False, comment="统计年份")
    stat_month = Column(Integer, nullable=False, comment="统计月份")
    total_energy = Column(Float, default=0, comment="总电量 kWh")
    peak_energy = Column(Float, default=0, comment="峰时电量 kWh")
    normal_energy = Column(Float, default=0, comment="平时电量 kWh")
    valley_energy = Column(Float, default=0, comment="谷时电量 kWh")
    max_power = Column(Float, default=0, comment="最大功率 kW")
    avg_power = Column(Float, default=0, comment="平均功率 kW")
    max_power_date = Column(Date, comment="最大功率日期")
    energy_cost = Column(Float, default=0, comment="电费 元")
    peak_cost = Column(Float, default=0, comment="峰时电费 元")
    normal_cost = Column(Float, default=0, comment="平时电费 元")
    valley_cost = Column(Float, default=0, comment="谷时电费 元")
    avg_pue = Column(Float, comment="月平均PUE")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")


class ElectricityPricing(Base):
    """电价配置表 - 时段电价（电度电费）"""
    __tablename__ = "electricity_pricing"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pricing_name = Column(String(50), nullable=False, comment="电价名称")
    period_type = Column(String(10), nullable=False, comment="时段类型: sharp/peak/flat/valley/deep_valley")
    start_time = Column(String(5), nullable=False, comment="开始时间 HH:MM")
    end_time = Column(String(5), nullable=False, comment="结束时间 HH:MM")
    price = Column(Float, nullable=False, comment="电价 元/kWh")
    effective_date = Column(Date, nullable=False, comment="生效日期")
    expire_date = Column(Date, comment="失效日期")
    is_enabled = Column(Boolean, default=True, comment="是否启用")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")


class PricingConfig(Base):
    """电价全局配置表 - 基本电费、功率因数调整、固定费用等

    设计说明:
    - ElectricityPricing 存储时段电价（电度电费），每个时段一行
    - PricingConfig 存储全局配置（基本电费、功率因数、固定费用），只有一行有效配置
    """
    __tablename__ = "pricing_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    config_name = Column(String(100), nullable=False, default="默认配置", comment="配置名称")

    # ========== 基本电费配置（需量/容量二选一）==========
    billing_mode = Column(String(20), default="demand", comment="计费方式: demand(按需量) / capacity(按容量)")

    # 需量计费参数
    demand_price = Column(Float, default=38.0, comment="需量电价 元/kW·月")
    declared_demand = Column(Float, comment="申报需量 kW")
    over_demand_multiplier = Column(Float, default=2.0, comment="超需量加价倍数")

    # 容量计费参数
    capacity_price = Column(Float, default=28.0, comment="容量电价 元/kVA·月")
    transformer_capacity = Column(Float, comment="变压器容量 kVA")

    # ========== 功率因数调整配置 ==========
    power_factor_baseline = Column(Float, default=0.90, comment="功率因数基准值")
    power_factor_rules = Column(JSON, comment="""功率因数调整规则 JSON数组:
        [
            {"min": 0.95, "max": 1.0, "adjustment": -0.75},  // 减少0.75%
            {"min": 0.90, "max": 0.95, "adjustment": 0},     // 不调整
            {"min": 0.85, "max": 0.90, "adjustment": 1.5},   // 增加1.5%
            {"min": 0, "max": 0.85, "adjustment": 3.0}       // 增加3.0%
        ]
    """)

    # ========== 固定费用配置（不参与优化，仅用于成本统计）==========
    transmission_fee = Column(Float, default=0.15, comment="输配电费 元/kWh")
    government_fund = Column(Float, default=0.05, comment="政府性基金 元/kWh")
    auxiliary_fee = Column(Float, default=0.02, comment="辅助服务费 元/kWh")
    other_fee = Column(Float, default=0.0, comment="其他附加费 元/kWh")

    # ========== 配置元数据 ==========
    effective_date = Column(Date, nullable=False, comment="生效日期")
    expire_date = Column(Date, comment="失效日期")
    is_enabled = Column(Boolean, default=True, comment="是否启用")
    description = Column(Text, comment="配置说明")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")


class EnergySuggestion(Base):
    """节能建议表"""
    __tablename__ = "energy_suggestions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_id = Column(String(50), nullable=False, comment="规则ID")
    rule_name = Column(String(100), comment="规则名称")
    device_id = Column(Integer, ForeignKey("power_devices.id"), comment="相关设备ID")
    trigger_value = Column(Float, comment="触发值")
    threshold_value = Column(Float, comment="阈值")
    suggestion = Column(Text, nullable=False, comment="建议内容")
    priority = Column(String(20), default="medium", comment="优先级: high/medium/low/urgent")
    potential_saving = Column(Float, comment="预计节省 kWh/月")
    potential_cost_saving = Column(Float, comment="预计节省费用 元/月")
    status = Column(String(20), default="pending", comment="状态: pending/accepted/rejected/completed")
    accepted_by = Column(Integer, ForeignKey("users.id"), comment="接受人")
    accepted_at = Column(DateTime, comment="接受时间")
    completed_at = Column(DateTime, comment="完成时间")
    actual_saving = Column(Float, comment="实际节省 kWh")
    remark = Column(Text, comment="备注")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    # V2.3 新增: 模板化字段
    template_id = Column(String(50), comment="建议模板ID")
    category = Column(String(30), comment="建议类别: pue/cost/demand/efficiency/maintenance")
    problem_description = Column(Text, comment="问题描述")
    analysis_detail = Column(Text, comment="分析详情")
    implementation_steps = Column(JSON, comment="实施步骤 [{step, description, duration}]")
    expected_effect = Column(JSON, comment="预期效果 {saving_kwh, saving_cost, pue_reduction, etc}")
    parameters = Column(JSON, comment="模板参数 {key: value}")
    related_devices = Column(JSON, comment="相关设备列表 [device_id]")
    difficulty = Column(String(20), default="medium", comment="实施难度: easy/medium/hard")
    payback_period = Column(Integer, comment="投资回收期 天")


class PUEHistory(Base):
    """PUE历史记录表"""
    __tablename__ = "pue_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    record_time = Column(DateTime, nullable=False, comment="记录时间")
    total_power = Column(Float, nullable=False, comment="总功率 kW")
    it_power = Column(Float, nullable=False, comment="IT负载功率 kW")
    cooling_power = Column(Float, comment="制冷功率 kW")
    ups_loss = Column(Float, comment="UPS损耗 kW")
    lighting_power = Column(Float, comment="照明功率 kW")
    other_power = Column(Float, comment="其他功率 kW")
    pue = Column(Float, nullable=False, comment="PUE值")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")


# ==================== V2.3 新增: 负荷调节模型 ====================

class LoadRegulationConfig(Base):
    """负荷调节配置表"""
    __tablename__ = "load_regulation_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(Integer, ForeignKey("power_devices.id"), nullable=False, comment="关联用电设备ID")

    # 调节类型: temperature(温度), brightness(亮度), mode(运行模式), load(负载优先级)
    regulation_type = Column(String(20), nullable=False, comment="调节类型: temperature/brightness/mode/load")

    # 调节参数
    min_value = Column(Float, nullable=False, comment="最小可调值")
    max_value = Column(Float, nullable=False, comment="最大可调值")
    current_value = Column(Float, comment="当前值")
    default_value = Column(Float, comment="默认值")
    step_size = Column(Float, default=1.0, comment="调节步长")
    unit = Column(String(10), comment="单位: ℃/%/mode")

    # 功率映射
    power_factor = Column(Float, comment="功率系数(每单位变化对应的功率变化kW)")
    base_power = Column(Float, comment="基准功率 kW")
    power_curve = Column(JSON, comment="功率曲线 [{value, power}]")

    # 约束条件
    priority = Column(Integer, default=5, comment="调节优先级 1-10 (1最高)")
    comfort_impact = Column(String(20), default="low", comment="舒适度影响: none/low/medium/high")
    performance_impact = Column(String(20), default="none", comment="性能影响: none/low/medium/high")

    # 状态
    is_enabled = Column(Boolean, default=True, comment="是否启用")
    is_auto = Column(Boolean, default=False, comment="是否自动调节")

    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")


class RegulationHistory(Base):
    """调节历史记录表"""
    __tablename__ = "regulation_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    config_id = Column(Integer, ForeignKey("load_regulation_configs.id"), nullable=False, comment="调节配置ID")
    device_id = Column(Integer, ForeignKey("power_devices.id"), nullable=False, comment="设备ID")

    # 调节记录
    regulation_type = Column(String(20), nullable=False, comment="调节类型")
    old_value = Column(Float, comment="调节前值")
    new_value = Column(Float, comment="调节后值")
    power_before = Column(Float, comment="调节前功率 kW")
    power_after = Column(Float, comment="调节后功率 kW")
    power_saved = Column(Float, comment="节省功率 kW")

    # 触发原因
    trigger_reason = Column(String(50), comment="触发原因: manual/auto/demand_response/schedule")
    trigger_detail = Column(Text, comment="触发详情")

    # 执行状态
    status = Column(String(20), default="pending", comment="状态: pending/executing/completed/failed/reverted")
    executed_at = Column(DateTime, comment="执行时间")
    reverted_at = Column(DateTime, comment="恢复时间")

    # 操作人
    operator_id = Column(Integer, ForeignKey("users.id"), comment="操作人ID")
    remark = Column(Text, comment="备注")

    created_at = Column(DateTime, default=datetime.now, comment="创建时间")


# ==================== V2.3 新增: 需量分析模型 ====================

class DemandAnalysisRecord(Base):
    """需量分析记录表"""
    __tablename__ = "demand_analysis_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    meter_point_id = Column(Integer, ForeignKey("meter_points.id"), nullable=False, comment="计量点ID")
    analysis_date = Column(Date, nullable=False, comment="分析日期")

    # 需量统计
    max_demand = Column(Float, comment="当日/月最大需量 kW")
    max_demand_time = Column(DateTime, comment="最大需量发生时间")
    avg_demand = Column(Float, comment="平均需量 kW")
    min_demand = Column(Float, comment="最小需量 kW")
    demand_95th = Column(Float, comment="95%分位数需量 kW")

    # 申报需量对比
    declared_demand = Column(Float, comment="申报需量 kW")
    utilization_rate = Column(Float, comment="需量利用率 %")
    over_demand_count = Column(Integer, default=0, comment="超需量次数")
    over_demand_max = Column(Float, comment="超需量最大值 kW")

    # 风险评估
    over_demand_risk = Column(Float, comment="超需量风险评分 0-100")
    risk_level = Column(String(20), comment="风险等级: low/medium/high/critical")

    # 优化建议
    optimization_potential = Column(Float, comment="优化潜力 kW")
    recommended_demand = Column(Float, comment="建议申报需量 kW")
    potential_saving = Column(Float, comment="潜在节省 元/月")
    recommended_actions = Column(JSON, comment="推荐措施列表")

    # 分析类型
    analysis_type = Column(String(20), default="daily", comment="分析类型: daily/monthly/custom")

    created_at = Column(DateTime, default=datetime.now, comment="创建时间")


class Demand15MinData(Base):
    """15分钟需量数据表"""
    __tablename__ = "demand_15min_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    meter_point_id = Column(Integer, ForeignKey("meter_points.id"), nullable=False, comment="计量点ID")
    timestamp = Column(DateTime, nullable=False, comment="时间戳(15分钟整点)")

    # 功率数据
    average_power = Column(Float, nullable=False, comment="15分钟平均功率 kW")
    max_power = Column(Float, comment="15分钟内最大功率 kW")
    min_power = Column(Float, comment="15分钟内最小功率 kW")

    # 需量计算
    rolling_demand = Column(Float, comment="滑动窗口需量 kW")
    declared_demand = Column(Float, comment="申报需量 kW")
    demand_ratio = Column(Float, comment="需量占比 %")

    # 分时标识
    is_peak_period = Column(Boolean, default=False, comment="是否峰时")
    time_period = Column(String(10), comment="时段: sharp/peak/flat/valley/deep_valley")

    # 标记
    is_max_of_day = Column(Boolean, default=False, comment="是否当日最大需量")
    is_max_of_month = Column(Boolean, default=False, comment="是否当月最大需量")
    is_over_declared = Column(Boolean, default=False, comment="是否超申报需量")

    recorded_at = Column(DateTime, default=datetime.now, comment="记录时间")


# ==================== V2.4 新增: 节能方案模型 ====================

class EnergySavingProposal(Base):
    """节能方案表 (多措施方案)"""
    __tablename__ = "energy_saving_proposals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    proposal_code = Column(String(50), unique=True, nullable=False, comment="方案编号 如 A1-20260124-001")
    proposal_type = Column(String(10), nullable=False, comment="方案类型: A(无需投资) / B(需要投资)")
    template_id = Column(String(50), nullable=False, comment="模板ID: A1/A2/A3/A4/A5/B1")
    template_name = Column(String(200), nullable=False, comment="模板名称 如'峰谷套利优化方案'")
    total_benefit = Column(Numeric(10, 2), comment="总收益 万元/年")
    total_investment = Column(Numeric(10, 2), default=0, comment="总投资 万元")
    current_situation = Column(JSON, comment="当前状况数据")
    analysis_start_date = Column(Date, comment="分析起始日期")
    analysis_end_date = Column(Date, comment="分析结束日期")

    # ========== V3.1 数据追溯链 (专利S1) ==========
    trace_summary = Column(JSON, comment="""追溯汇总信息 JSON:
        {
            "total_traces": 15,
            "data_sources": ["energy_daily", "power_devices", ...],
            "time_range": {"start": "...", "end": "..."},
            "root_trace_ids": ["TR-001", "TR-002", ...]
        }
    """)

    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    status = Column(String(20), default="pending", comment="状态: pending/accepted/rejected/executing/completed")

    # 关系
    measures = relationship("ProposalMeasure", back_populates="proposal", cascade="all, delete-orphan")


class ProposalMeasure(Base):
    """方案措施表"""
    __tablename__ = "proposal_measures"

    id = Column(Integer, primary_key=True, autoincrement=True)
    proposal_id = Column(Integer, ForeignKey("energy_saving_proposals.id", ondelete="CASCADE"), nullable=False)
    measure_code = Column(String(50), nullable=False, comment="措施编号 如 A1-001-M001")
    regulation_object = Column(String(200), nullable=False, comment="调节对象 如'空压机系统'")
    regulation_description = Column(Text, comment="调节说明")
    current_state = Column(JSON, comment="当前状态数据")
    target_state = Column(JSON, comment="目标状态数据")
    calculation_formula = Column(Text, comment="计算公式和步骤")
    calculation_basis = Column(Text, comment="计算依据")
    annual_benefit = Column(Numeric(10, 2), comment="年收益 万元/年")
    investment = Column(Numeric(10, 2), default=0, comment="投资 万元")
    is_selected = Column(Boolean, default=False, comment="用户是否选择该措施")
    execution_status = Column(String(20), default="pending", comment="执行状态: pending/executing/completed/failed")

    # ========== V3.1 数据追溯链 (专利S1) ==========
    trace_data = Column(JSON, comment="""数据追溯链信息 JSON:
        {
            "root_trace_id": "TR-20260201-001",
            "traces": {
                "param_code": "trace_id",
                ...
            },
            "calculation_steps": [
                {"step": 1, "description": "...", "trace_id": "..."},
                ...
            ]
        }
    """)

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # 关系
    proposal = relationship("EnergySavingProposal", back_populates="measures")
    execution_logs = relationship("MeasureExecutionLog", back_populates="measure", cascade="all, delete-orphan")


class MeasureExecutionLog(Base):
    """措施执行日志表"""
    __tablename__ = "measure_execution_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    measure_id = Column(Integer, ForeignKey("proposal_measures.id", ondelete="CASCADE"), nullable=False)
    execution_time = Column(DateTime, nullable=False, default=func.now(), comment="执行时间")
    power_before = Column(Numeric(10, 2), comment="调节前功率 kW")
    power_after = Column(Numeric(10, 2), comment="调节后功率 kW")
    power_saved = Column(Numeric(10, 2), comment="实际节省功率 kW")
    expected_power_saved = Column(Numeric(10, 2), comment="预期节省功率 kW")
    result = Column(String(20), comment="执行结果: success/failed/partial")
    result_message = Column(Text, comment="结果描述")
    execution_data = Column(JSON, comment="执行详细数据")
    created_at = Column(DateTime, default=func.now())

    # 关系
    measure = relationship("ProposalMeasure", back_populates="execution_logs")


# ==================== 效果监测模型 (专利 S4) ====================

class MeasureBaseline(Base):
    """
    措施基准值表 (S4a)

    在措施执行前采集目标设备的运行参数作为基准值
    """
    __tablename__ = "measure_baselines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    measure_id = Column(Integer, ForeignKey("proposal_measures.id", ondelete="CASCADE"), nullable=False)

    # 基准采集时间
    captured_at = Column(DateTime, nullable=False, default=func.now(), comment="采集时间")
    capture_duration = Column(Integer, default=60, comment="采集时长(分钟)")

    # 功率基准
    power_avg = Column(Numeric(10, 2), comment="平均功率 kW")
    power_max = Column(Numeric(10, 2), comment="最大功率 kW")
    power_min = Column(Numeric(10, 2), comment="最小功率 kW")

    # 能耗基准
    energy_hourly = Column(Numeric(10, 2), comment="小时能耗 kWh")
    energy_daily = Column(Numeric(12, 2), comment="日能耗 kWh")

    # 设备参数基准
    device_params = Column(JSON, comment="设备参数快照 {temp, speed, load, etc}")

    # 数据来源
    data_source = Column(String(50), comment="数据来源: realtime/history/simulation")
    device_ids = Column(JSON, comment="关联设备ID列表")
    point_ids = Column(JSON, comment="关联监测点位ID列表")

    created_at = Column(DateTime, default=func.now())

    # 关系
    measure = relationship("ProposalMeasure", backref="baselines")


class MonitoringRecord(Base):
    """
    监测记录表 (S4b)

    在措施执行后按预设周期持续采集设备运行参数
    """
    __tablename__ = "monitoring_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    measure_id = Column(Integer, ForeignKey("proposal_measures.id", ondelete="CASCADE"), nullable=False)
    baseline_id = Column(Integer, ForeignKey("measure_baselines.id"), comment="关联基准ID")

    # 监测时间
    recorded_at = Column(DateTime, nullable=False, default=func.now(), comment="记录时间")
    monitoring_period = Column(Integer, default=15, comment="监测周期(分钟)")

    # 实时功率
    power_current = Column(Numeric(10, 2), comment="当前功率 kW")
    power_baseline = Column(Numeric(10, 2), comment="对比基准功率 kW")
    power_diff = Column(Numeric(10, 2), comment="功率差值 kW (正=节省)")

    # 累计节能
    energy_saved = Column(Numeric(12, 2), comment="累计节能量 kWh")
    cost_saved = Column(Numeric(12, 2), comment="累计节省金额 元")

    # 设备参数
    device_params = Column(JSON, comment="当前设备参数")
    param_changes = Column(JSON, comment="参数变化对比")

    # 监测状态
    status = Column(String(20), default="normal", comment="状态: normal/warning/anomaly")
    anomaly_message = Column(Text, comment="异常描述")

    created_at = Column(DateTime, default=func.now())

    # 关系
    measure = relationship("ProposalMeasure", backref="monitoring_records")


class EffectReport(Base):
    """
    效果报告表 (S4c/S4d)

    计算实际节能收益和效果达成率
    """
    __tablename__ = "effect_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    proposal_id = Column(Integer, ForeignKey("energy_saving_proposals.id", ondelete="CASCADE"), nullable=False)
    measure_id = Column(Integer, ForeignKey("proposal_measures.id", ondelete="CASCADE"), comment="关联措施ID(可选)")

    # 报告周期
    report_type = Column(String(20), nullable=False, comment="报告类型: daily/weekly/monthly/custom")
    period_start = Column(DateTime, nullable=False, comment="周期开始")
    period_end = Column(DateTime, nullable=False, comment="周期结束")

    # 预期收益
    expected_energy_saved = Column(Numeric(12, 2), comment="预期节能量 kWh")
    expected_cost_saved = Column(Numeric(12, 2), comment="预期节省金额 元")

    # 实际收益 (S4c)
    actual_energy_saved = Column(Numeric(12, 2), comment="实际节能量 kWh")
    actual_cost_saved = Column(Numeric(12, 2), comment="实际节省金额 元")

    # 效果达成率 (S4d)
    achievement_rate = Column(Numeric(5, 2), comment="效果达成率 % = 实际/预期*100")
    energy_achievement_rate = Column(Numeric(5, 2), comment="节能量达成率 %")
    cost_achievement_rate = Column(Numeric(5, 2), comment="成本节省达成率 %")

    # 偏差分析
    deviation_reason = Column(Text, comment="偏差原因分析")
    improvement_suggestion = Column(Text, comment="改进建议")

    # RL 反馈状态 (S4e)
    rl_feedback_sent = Column(Boolean, default=False, comment="是否已推送RL模块")
    rl_feedback_at = Column(DateTime, comment="RL反馈时间")
    rl_adjustment_action = Column(JSON, comment="RL建议的调整动作")

    # 元数据
    data_quality = Column(Numeric(3, 2), comment="数据质量评分 0-1")
    monitoring_coverage = Column(Numeric(3, 2), comment="监测覆盖率 0-1")

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # 关系
    proposal = relationship("EnergySavingProposal", backref="effect_reports")
    measure = relationship("ProposalMeasure", backref="effect_reports")


class MonitoringSession(Base):
    """
    监测会话表

    管理措施的持续监测周期
    """
    __tablename__ = "monitoring_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    proposal_id = Column(Integer, ForeignKey("energy_saving_proposals.id", ondelete="CASCADE"), nullable=False)

    # 会话状态
    status = Column(String(20), default="pending", comment="状态: pending/active/paused/completed/failed")
    started_at = Column(DateTime, comment="开始时间")
    ended_at = Column(DateTime, comment="结束时间")

    # 监测配置
    monitoring_interval = Column(Integer, default=15, comment="监测间隔(分钟)")
    report_interval = Column(String(20), default="daily", comment="报告周期: hourly/daily/weekly")
    auto_rl_feedback = Column(Boolean, default=True, comment="是否自动RL反馈")

    # 汇总统计
    total_records = Column(Integer, default=0, comment="总记录数")
    total_energy_saved = Column(Numeric(12, 2), default=0, comment="累计节能量 kWh")
    avg_achievement_rate = Column(Numeric(5, 2), comment="平均达成率 %")

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # 关系
    proposal = relationship("EnergySavingProposal", backref="monitoring_sessions")


# ==================== V3.2 RL 自适应优化 (专利 S5) ====================

class RLOptimizationHistory(Base):
    """
    RL 优化历史表

    记录每次 RL 优化的输入状态、输出动作和效果
    """
    __tablename__ = "rl_optimization_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    proposal_id = Column(Integer, ForeignKey("energy_saving_proposals.id", ondelete="CASCADE"), nullable=False)

    # 输入状态
    state_vector = Column(JSON, comment="输入状态向量")
    state_summary = Column(JSON, comment="状态摘要 (可读)")

    # 输出动作
    actions = Column(JSON, comment="RL 输出动作")
    adjustments = Column(JSON, comment="转换后的调整建议")

    # 执行信息
    exploration = Column(Boolean, default=False, comment="是否为探索动作")
    exploration_rate = Column(Numeric(5, 4), comment="当前探索率")
    confidence = Column(Numeric(5, 4), comment="置信度")
    state_value = Column(Numeric(10, 4), comment="状态价值估计")

    # 效果反馈
    applied = Column(Boolean, default=False, comment="是否已应用")
    applied_at = Column(DateTime, comment="应用时间")
    reward = Column(Numeric(10, 4), comment="实际奖励")
    achievement_rate = Column(Numeric(5, 2), comment="达成率 %")

    created_at = Column(DateTime, default=func.now())

    # 关系
    proposal = relationship("EnergySavingProposal", backref="rl_optimizations")


class RLTrainingLog(Base):
    """
    RL 训练日志表

    记录在线训练的每一步信息
    """
    __tablename__ = "rl_training_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    proposal_id = Column(Integer, ForeignKey("energy_saving_proposals.id", ondelete="CASCADE"), comment="关联方案")

    # 训练输入
    actual_saving = Column(Numeric(12, 2), comment="实际节能收益")
    expected_saving = Column(Numeric(12, 2), comment="预期节能收益")
    comfort_violation = Column(Numeric(5, 4), default=0, comment="舒适度违反程度")
    safety_violation = Column(Numeric(5, 4), default=0, comment="安全约束违反")

    # 训练结果
    reward = Column(Numeric(10, 4), comment="计算奖励")
    achievement_rate = Column(Numeric(5, 4), comment="达成率")
    exploration_rate = Column(Numeric(5, 4), comment="当前探索率")
    step_count = Column(Integer, comment="全局步数")

    # 网络更新信息
    policy_loss = Column(Numeric(10, 6), comment="策略损失")
    value_loss = Column(Numeric(10, 6), comment="价值损失")
    entropy = Column(Numeric(10, 6), comment="策略熵")
    network_updated = Column(Boolean, default=False, comment="本步是否更新了网络")

    created_at = Column(DateTime, default=func.now())

    # 关系
    proposal = relationship("EnergySavingProposal", backref="rl_training_logs")


class RLModelState(Base):
    """
    RL 模型状态表

    保存模型运行状态和探索率信息
    """
    __tablename__ = "rl_model_states"

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_name = Column(String(100), default="adaptive_optimizer", comment="模型名称")

    # 模型状态
    is_trained = Column(Boolean, default=False, comment="是否已训练")
    total_steps = Column(Integer, default=0, comment="总训练步数")
    total_episodes = Column(Integer, default=0, comment="总训练回合")
    exploration_rate = Column(Numeric(5, 4), default=0.3, comment="当前探索率")
    exploration_phase = Column(String(20), default="initial", comment="探索阶段: initial/stable/fluctuating/decaying")

    # 性能统计
    avg_reward = Column(Numeric(10, 4), comment="平均奖励")
    avg_achievement_rate = Column(Numeric(5, 2), comment="平均达成率 %")
    best_reward = Column(Numeric(10, 4), comment="最佳奖励")
    recent_achievements = Column(JSON, comment="最近100次达成率")

    # 模型检查点
    checkpoint_path = Column(String(500), comment="检查点路径")
    checkpoint_saved_at = Column(DateTime, comment="检查点保存时间")

    # 配置快照
    config_snapshot = Column(JSON, comment="训练配置快照")

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


# ==================== 节能中心重构模型 V2.5 ====================

class EnergyOpportunity(Base):
    """节能机会主表 - 整合后的4大类机会"""
    __tablename__ = "energy_opportunities"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # 分类: 1-电费结构优化 2-设备运行优化 3-设备改造升级 4-综合能效提升
    category = Column(Integer, nullable=False, comment="分类: 1-电费结构/2-设备运行/3-设备改造/4-综合能效")
    title = Column(String(200), nullable=False, comment="机会标题")
    description = Column(Text, comment="机会描述")

    # 优先级和状态
    priority = Column(String(20), default="medium", comment="优先级: high/medium/low")
    status = Column(String(30), default="discovered", comment="状态: discovered/simulating/ready/executing/completed/rejected")

    # 收益评估
    potential_saving = Column(Numeric(12, 2), comment="年度潜在节省(元)")
    confidence = Column(Numeric(3, 2), default=0.80, comment="置信度(0-1)")

    # 分析数据（JSON存储详细分析结果）
    analysis_data = Column(JSON, comment="分析详情JSON")

    # 来源追踪
    source_plugin = Column(String(50), comment="来源分析插件ID")
    trigger_condition = Column(Text, comment="触发条件描述")

    # 时间戳
    discovered_at = Column(DateTime, default=datetime.now, comment="发现时间")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    # 关系
    measures = relationship("OpportunityMeasure", back_populates="opportunity", cascade="all, delete-orphan")
    execution_plans = relationship("ExecutionPlan", back_populates="opportunity", cascade="all, delete-orphan")


class OpportunityMeasure(Base):
    """机会措施表 - 一个机会可包含多个具体措施"""
    __tablename__ = "opportunity_measures"

    id = Column(Integer, primary_key=True, autoincrement=True)
    opportunity_id = Column(Integer, ForeignKey("energy_opportunities.id", ondelete="CASCADE"), nullable=False)

    # 措施类型
    measure_type = Column(String(50), nullable=False, comment="措施类型: demand_adjust/peak_shift/temp_adjust/brightness_adjust/equipment_upgrade")
    measure_name = Column(String(200), comment="措施名称")

    # 调节对象
    regulation_object = Column(String(200), comment="调节对象描述")

    # 当前状态和目标状态（JSON）
    current_state = Column(JSON, comment="当前参数状态")
    target_state = Column(JSON, comment="目标参数状态")

    # 执行方式
    execution_mode = Column(String(20), default="manual", comment="执行方式: auto/manual/hybrid")

    # 涉及设备
    selected_devices = Column(JSON, comment="选中的设备ID列表及配置")

    # 计算公式和收益
    calculation_formula = Column(JSON, comment="计算公式明细")
    annual_benefit = Column(Numeric(12, 2), comment="年收益(元)")
    confidence = Column(Numeric(3, 2), default=0.80, comment="措施置信度")

    # 约束条件
    constraints = Column(JSON, comment="约束条件")

    # 排序
    sort_order = Column(Integer, default=0, comment="排序顺序")

    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    # 关系
    opportunity = relationship("EnergyOpportunity", back_populates="measures")


class ExecutionPlan(Base):
    """执行计划表 - 确认执行后生成"""
    __tablename__ = "execution_plans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    opportunity_id = Column(Integer, ForeignKey("energy_opportunities.id", ondelete="CASCADE"), nullable=False)

    # 计划信息
    plan_name = Column(String(200), comment="计划名称")
    expected_saving = Column(Numeric(12, 2), comment="预期年节省(元)")

    # 状态: pending/executing/completed/failed/cancelled
    status = Column(String(30), default="pending", comment="状态")

    # 执行信息
    started_at = Column(DateTime, comment="开始执行时间")
    completed_at = Column(DateTime, comment="完成时间")
    created_by = Column(Integer, comment="创建人ID")

    # 元数据
    notes = Column(Text, comment="备注")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    # 关系
    opportunity = relationship("EnergyOpportunity", back_populates="execution_plans")
    tasks = relationship("ExecutionTask", back_populates="plan", cascade="all, delete-orphan")
    results = relationship("ExecutionResult", back_populates="plan", cascade="all, delete-orphan")


class ExecutionTask(Base):
    """执行任务表 - 计划分解为具体任务"""
    __tablename__ = "execution_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plan_id = Column(Integer, ForeignKey("execution_plans.id", ondelete="CASCADE"), nullable=False)

    # 任务信息
    task_type = Column(String(50), nullable=False, comment="任务类型: demand_adjust/device_control/manual_operation")
    task_name = Column(String(200), comment="任务名称")
    target_object = Column(String(200), comment="目标对象(设备ID或配置项)")

    # 执行方式
    execution_mode = Column(String(20), default="manual", comment="执行方式: auto/manual")

    # 执行参数
    parameters = Column(JSON, comment="执行参数")

    # 状态: pending/executing/completed/failed/skipped
    status = Column(String(30), default="pending", comment="状态")

    # 责任人
    assigned_to = Column(String(100), comment="负责人")

    # 执行时间和结果
    scheduled_at = Column(DateTime, comment="计划执行时间")
    executed_at = Column(DateTime, comment="实际执行时间")
    result = Column(JSON, comment="执行结果")
    error_message = Column(Text, comment="错误信息")

    # 排序
    sort_order = Column(Integer, default=0, comment="执行顺序")

    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    # 关系
    plan = relationship("ExecutionPlan", back_populates="tasks")


class ExecutionResult(Base):
    """效果追踪表 - 执行后效果跟踪"""
    __tablename__ = "execution_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plan_id = Column(Integer, ForeignKey("execution_plans.id", ondelete="CASCADE"), nullable=False)

    # 追踪周期
    tracking_period = Column(Integer, default=7, comment="追踪周期(天)")
    tracking_start = Column(Date, comment="追踪开始日期")
    tracking_end = Column(Date, comment="追踪结束日期")

    # 实际效果
    actual_saving = Column(Numeric(12, 2), comment="实际节省(元)")
    achievement_rate = Column(Numeric(5, 2), comment="达成率(%)")

    # 对比数据
    power_curve_before = Column(JSON, comment="执行前功率曲线数据")
    power_curve_after = Column(JSON, comment="执行后功率曲线数据")
    energy_before = Column(JSON, comment="执行前能耗数据")
    energy_after = Column(JSON, comment="执行后能耗数据")

    # 分析结论
    analysis_conclusion = Column(Text, comment="分析结论")
    notes = Column(Text, comment="备注说明")

    # 状态: tracking/completed
    status = Column(String(20), default="tracking", comment="状态")

    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    # 关系
    plan = relationship("ExecutionPlan", back_populates="results")


# ==================== V3.0 电费综合优化系统 ====================

class DispatchableDevice(Base):
    """可调度设备表 - 支持6类通用负荷分类"""
    __tablename__ = "dispatchable_devices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="设备名称")

    # 设备分类: shiftable/curtailable/modulating/generation/storage/rigid
    device_type = Column(String(20), nullable=False, comment="设备类型")
    rated_power = Column(Numeric(10, 2), nullable=False, comment="额定功率 kW")
    min_power = Column(Numeric(10, 2), comment="最小功率 kW")
    max_power = Column(Numeric(10, 2), comment="最大功率 kW")

    # ========== 时移型参数 (shiftable) ==========
    run_duration = Column(Numeric(5, 2), comment="单次运行时长 h")
    daily_runs = Column(Integer, comment="每日运行次数")
    allowed_periods = Column(JSON, comment="允许时段 JSON array")
    forbidden_periods = Column(JSON, comment="禁止时段 JSON array")

    # ========== 削减型参数 (curtailable) ==========
    curtail_ratio = Column(Numeric(5, 2), comment="可削减比例 %")
    max_curtail_duration = Column(Numeric(5, 2), comment="最大削减时长 h")
    max_curtail_per_day = Column(Integer, comment="每日最大削减次数")
    recovery_time = Column(Numeric(5, 2), comment="恢复时间 h")

    # ========== 调节型参数 (modulating) ==========
    ramp_rate = Column(Numeric(10, 2), comment="调节速率 kW/min")
    response_delay = Column(Integer, comment="响应延迟 s")

    # ========== 发电型参数 (generation) ==========
    generation_cost = Column(Numeric(10, 4), comment="发电成本 元/kWh")
    is_controllable = Column(Boolean, default=False, comment="是否可调度")
    forecast_curve = Column(JSON, comment="预测曲线 JSON")

    # ========== 通用参数 ==========
    priority = Column(Integer, default=5, comment="优先级 1-10 (1最高)")
    is_active = Column(Boolean, default=True, comment="是否启用")
    meter_point_id = Column(Integer, ForeignKey("meter_points.id"), comment="关联计量点")
    power_device_id = Column(Integer, ForeignKey("power_devices.id"), comment="关联用电设备ID")

    description = Column(Text, comment="设备描述")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")


class StorageSystemConfig(Base):
    """储能系统配置表"""
    __tablename__ = "storage_system_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="储能系统名称")
    capacity = Column(Numeric(10, 2), nullable=False, comment="容量 kWh")
    max_charge_power = Column(Numeric(10, 2), nullable=False, comment="最大充电功率 kW")
    max_discharge_power = Column(Numeric(10, 2), nullable=False, comment="最大放电功率 kW")
    charge_efficiency = Column(Numeric(5, 2), default=0.95, comment="充电效率")
    discharge_efficiency = Column(Numeric(5, 2), default=0.95, comment="放电效率")
    min_soc = Column(Numeric(5, 2), default=0.10, comment="最小SOC")
    max_soc = Column(Numeric(5, 2), default=0.90, comment="最大SOC")
    cycle_cost = Column(Numeric(10, 4), default=0.1, comment="循环成本 元/kWh")

    is_active = Column(Boolean, default=True, comment="是否启用")
    meter_point_id = Column(Integer, ForeignKey("meter_points.id"), comment="关联计量点")
    description = Column(Text, comment="描述")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")


class PVSystemConfig(Base):
    """光伏系统配置表"""
    __tablename__ = "pv_system_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="光伏系统名称")
    rated_capacity = Column(Numeric(10, 2), nullable=False, comment="额定容量 kWp")
    efficiency = Column(Numeric(5, 2), default=0.85, comment="系统效率")
    is_controllable = Column(Boolean, default=False, comment="是否可调度")

    is_active = Column(Boolean, default=True, comment="是否启用")
    meter_point_id = Column(Integer, ForeignKey("meter_points.id"), comment="关联计量点")
    description = Column(Text, comment="描述")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")


class DispatchSchedule(Base):
    """调度计划表"""
    __tablename__ = "dispatch_schedules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    schedule_date = Column(Date, nullable=False, comment="调度日期")
    device_id = Column(Integer, ForeignKey("dispatchable_devices.id"), comment="设备ID")
    time_slot = Column(Integer, nullable=False, comment="时段序号 0-95 (15分钟间隔)")
    action = Column(String(20), nullable=False, comment="操作: on/off/charge/discharge/curtail")
    power_setpoint = Column(Numeric(10, 2), comment="功率设定值 kW")
    expected_saving = Column(Numeric(10, 2), comment="预期节省 元")
    status = Column(String(20), default="pending", comment="状态: pending/executed/skipped/failed")

    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    executed_at = Column(DateTime, comment="执行时间")


class RealtimeMonitoring(Base):
    """实时监控记录表 - 需量监控"""
    __tablename__ = "realtime_monitoring"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, comment="时间戳")
    current_power = Column(Numeric(10, 2), nullable=False, comment="当前功率 kW")
    window_avg_power = Column(Numeric(10, 2), comment="15分钟窗口平均功率 kW")
    demand_target = Column(Numeric(10, 2), comment="需量目标 kW")
    utilization_ratio = Column(Numeric(5, 2), comment="需量利用率 %")
    alert_level = Column(String(20), comment="预警级别: normal/warning/critical")

    created_at = Column(DateTime, default=datetime.now, comment="创建时间")


class MonthlyStatistics(Base):
    """月度统计表 - 电费统计"""
    __tablename__ = "monthly_statistics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    year_month = Column(String(7), nullable=False, comment="年月 YYYY-MM")
    total_energy = Column(Numeric(12, 2), comment="总用电量 kWh")
    max_demand = Column(Numeric(10, 2), comment="最大需量 kW")
    demand_target = Column(Numeric(10, 2), comment="需量目标 kW")

    # 电费分项
    energy_cost = Column(Numeric(12, 2), comment="电量电费 元")
    demand_cost = Column(Numeric(12, 2), comment="需量电费 元")
    power_factor_adjustment = Column(Numeric(12, 2), comment="力调电费 元")
    total_cost = Column(Numeric(12, 2), comment="总电费 元")

    # 优化效果
    optimized_saving = Column(Numeric(12, 2), comment="优化节省 元")
    baseline_cost = Column(Numeric(12, 2), comment="基准电费 元")

    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")


class OptimizationResult(Base):
    """优化结果表"""
    __tablename__ = "optimization_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    result_date = Column(Date, nullable=False, comment="结果日期")
    optimization_type = Column(String(20), nullable=False, comment="优化类型: day_ahead/realtime")
    status = Column(String(20), nullable=False, comment="状态: success/failed/partial")

    # 求解结果
    objective_value = Column(Numeric(12, 2), comment="目标函数值 元")
    solve_time = Column(Numeric(10, 2), comment="求解时间 s")
    expected_saving = Column(Numeric(12, 2), comment="预期节省 元")
    actual_saving = Column(Numeric(12, 2), comment="实际节省 元")

    # 详细结果 (JSON)
    result_data = Column(JSON, comment="详细结果 JSON")

    created_at = Column(DateTime, default=datetime.now, comment="创建时间")

