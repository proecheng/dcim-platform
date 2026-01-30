"""
用电管理数据模型
"""
from enum import Enum
from typing import Optional, List, Dict
from pydantic import BaseModel, Field
from datetime import datetime, date


# ========== 用电设备 ==========

class PowerDeviceBase(BaseModel):
    """用电设备基础模型"""
    device_code: str = Field(..., description="设备编码")
    device_name: str = Field(..., description="设备名称")
    device_type: str = Field(..., description="设备类型: MAIN/UPS/PDU/AC/IT")
    rated_power: Optional[float] = Field(None, description="额定功率 kW")
    rated_voltage: Optional[float] = Field(None, description="额定电压 V")
    rated_current: Optional[float] = Field(None, description="额定电流 A")
    phase_type: Optional[str] = Field("3P", description="相位类型: 1P/3P")
    parent_device_id: Optional[int] = Field(None, description="上级设备ID")
    circuit_id: Optional[int] = Field(None, description="所属回路ID")
    circuit_no: Optional[str] = Field(None, description="回路编号")
    # 点位关联
    monitor_device_id: Optional[int] = Field(None, description="关联动环设备ID")
    power_point_id: Optional[int] = Field(None, description="有功功率点位ID")
    energy_point_id: Optional[int] = Field(None, description="累计电量点位ID")
    voltage_point_id: Optional[int] = Field(None, description="电压点位ID")
    current_point_id: Optional[int] = Field(None, description="电流点位ID")
    pf_point_id: Optional[int] = Field(None, description="功率因数点位ID")
    # 负荷特性
    is_metered: bool = Field(True, description="是否计量")
    is_it_load: bool = Field(False, description="是否IT负载")
    is_critical: bool = Field(False, description="是否关键负荷")
    area_code: Optional[str] = Field(None, description="区域代码")
    description: Optional[str] = Field(None, description="描述")


class PowerDeviceCreate(PowerDeviceBase):
    """创建用电设备"""
    pass


class PowerDeviceUpdate(BaseModel):
    """更新用电设备"""
    device_name: Optional[str] = None
    device_type: Optional[str] = None
    rated_power: Optional[float] = None
    rated_voltage: Optional[float] = None
    rated_current: Optional[float] = None
    phase_type: Optional[str] = None
    parent_device_id: Optional[int] = None
    circuit_id: Optional[int] = None
    circuit_no: Optional[str] = None
    # 点位关联
    monitor_device_id: Optional[int] = None
    power_point_id: Optional[int] = None
    energy_point_id: Optional[int] = None
    voltage_point_id: Optional[int] = None
    current_point_id: Optional[int] = None
    pf_point_id: Optional[int] = None
    # 负荷特性
    is_metered: Optional[bool] = None
    is_it_load: Optional[bool] = None
    is_critical: Optional[bool] = None
    area_code: Optional[str] = None
    description: Optional[str] = None
    is_enabled: Optional[bool] = None


class PowerDeviceResponse(PowerDeviceBase):
    """用电设备响应"""
    id: int
    is_enabled: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PowerDeviceTree(PowerDeviceResponse):
    """用电设备树结构"""
    children: List["PowerDeviceTree"] = []


# ========== 实时电力数据 ==========

class RealtimePowerData(BaseModel):
    """实时电力数据"""
    device_id: int
    device_code: str
    device_name: str
    device_type: str
    voltage_a: Optional[float] = Field(None, description="A相电压 V")
    voltage_b: Optional[float] = Field(None, description="B相电压 V")
    voltage_c: Optional[float] = Field(None, description="C相电压 V")
    current_a: Optional[float] = Field(None, description="A相电流 A")
    current_b: Optional[float] = Field(None, description="B相电流 A")
    current_c: Optional[float] = Field(None, description="C相电流 A")
    active_power: Optional[float] = Field(None, description="有功功率 kW")
    reactive_power: Optional[float] = Field(None, description="无功功率 kVar")
    apparent_power: Optional[float] = Field(None, description="视在功率 kVA")
    power_factor: Optional[float] = Field(None, description="功率因数")
    frequency: Optional[float] = Field(None, description="频率 Hz")
    total_energy: Optional[float] = Field(None, description="累计电量 kWh")
    load_rate: Optional[float] = Field(None, description="负载率 %")
    status: str = Field("normal", description="状态: normal/warning/alarm/offline")
    update_time: datetime


class RealtimePowerSummary(BaseModel):
    """实时电力汇总"""
    total_power: float = Field(..., description="总功率 kW")
    it_power: float = Field(..., description="IT负载功率 kW")
    cooling_power: float = Field(..., description="制冷功率 kW")
    ups_power: float = Field(..., description="UPS功率 kW")
    other_power: float = Field(..., description="其他功率 kW")
    current_pue: float = Field(..., description="当前PUE")
    today_energy: float = Field(..., description="今日用电 kWh")
    today_cost: float = Field(..., description="今日电费 元")
    month_energy: float = Field(..., description="本月用电 kWh")
    month_cost: float = Field(..., description="本月电费 元")


# ========== PUE ==========

class PUEData(BaseModel):
    """PUE数据"""
    current_pue: float = Field(..., description="当前PUE")
    total_power: float = Field(..., description="总功率 kW")
    it_power: float = Field(..., description="IT功率 kW")
    cooling_power: float = Field(..., description="制冷功率 kW")
    ups_loss: float = Field(..., description="UPS损耗 kW")
    lighting_power: float = Field(..., description="照明功率 kW")
    other_power: float = Field(..., description="其他功率 kW")
    update_time: datetime


class PUEHistoryItem(BaseModel):
    """PUE历史记录"""
    record_time: datetime
    pue: float
    total_power: float
    it_power: float

    class Config:
        from_attributes = True


class PUETrend(BaseModel):
    """PUE趋势"""
    period: str = Field(..., description="时间段: hour/day/week/month")
    data: List[PUEHistoryItem]
    avg_pue: float
    min_pue: float
    max_pue: float


# ========== 能耗统计 ==========

class EnergyHourlyData(BaseModel):
    """小时能耗数据"""
    id: int
    device_id: int
    stat_time: datetime
    total_energy: float
    avg_power: float
    max_power: float
    min_power: float
    avg_voltage: Optional[float]
    avg_current: Optional[float]
    avg_power_factor: Optional[float]

    class Config:
        from_attributes = True


class EnergyDailyData(BaseModel):
    """日能耗数据"""
    id: int
    device_id: int
    stat_date: date
    total_energy: float
    peak_energy: float
    normal_energy: float
    valley_energy: float
    max_power: float
    avg_power: float
    max_power_time: Optional[datetime]
    energy_cost: float
    pue: Optional[float]

    class Config:
        from_attributes = True


class EnergyMonthlyData(BaseModel):
    """月能耗数据"""
    id: int
    device_id: int
    stat_year: int
    stat_month: int
    total_energy: float
    peak_energy: float
    normal_energy: float
    valley_energy: float
    max_power: float
    avg_power: float
    max_power_date: Optional[date]
    energy_cost: float
    peak_cost: float
    normal_cost: float
    valley_cost: float
    avg_pue: Optional[float]

    class Config:
        from_attributes = True


class EnergyStatQuery(BaseModel):
    """能耗统计查询参数"""
    device_id: Optional[int] = None
    device_type: Optional[str] = None
    area_code: Optional[str] = None
    start_date: date
    end_date: date
    granularity: str = Field("daily", description="粒度: hourly/daily/monthly")


class EnergyStat(BaseModel):
    """能耗统计结果"""
    total_energy: float = Field(..., description="总电量 kWh")
    peak_energy: float = Field(..., description="峰时电量 kWh")
    normal_energy: float = Field(..., description="平时电量 kWh")
    valley_energy: float = Field(..., description="谷时电量 kWh")
    total_cost: float = Field(..., description="总电费 元")
    peak_cost: float = Field(..., description="峰时电费 元")
    normal_cost: float = Field(..., description="平时电费 元")
    valley_cost: float = Field(..., description="谷时电费 元")
    avg_power: float = Field(..., description="平均功率 kW")
    max_power: float = Field(..., description="最大功率 kW")
    avg_pue: Optional[float] = Field(None, description="平均PUE")


class EnergyTrendItem(BaseModel):
    """能耗趋势项"""
    time_label: str
    energy: float
    cost: float
    power: Optional[float] = None


class EnergyTrend(BaseModel):
    """能耗趋势"""
    granularity: str
    data: List[EnergyTrendItem]
    total_energy: float
    total_cost: float


class EnergyComparison(BaseModel):
    """能耗对比"""
    current_period: EnergyStat
    previous_period: EnergyStat
    energy_change: float = Field(..., description="电量变化 kWh")
    energy_change_rate: float = Field(..., description="电量变化率 %")
    cost_change: float = Field(..., description="电费变化 元")
    cost_change_rate: float = Field(..., description="电费变化率 %")


# ========== 电价配置 ==========

class ElectricityPricingBase(BaseModel):
    """电价配置基础模型"""
    pricing_name: str = Field(..., description="电价名称")
    period_type: str = Field(..., description="时段类型: sharp/peak/flat/valley/deep_valley")
    start_time: str = Field(..., description="开始时间 HH:MM")
    end_time: str = Field(..., description="结束时间 HH:MM")
    price: float = Field(..., description="电价 元/kWh")
    effective_date: date = Field(..., description="生效日期")
    expire_date: Optional[date] = Field(None, description="失效日期")


class ElectricityPricingCreate(ElectricityPricingBase):
    """创建电价配置"""
    pass


class ElectricityPricingUpdate(BaseModel):
    """更新电价配置"""
    pricing_name: Optional[str] = None
    period_type: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    price: Optional[float] = None
    effective_date: Optional[date] = None
    expire_date: Optional[date] = None
    is_enabled: Optional[bool] = None


class ElectricityPricingResponse(ElectricityPricingBase):
    """电价配置响应"""
    id: int
    is_enabled: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ========== 电价全局配置 ==========

class PowerFactorRule(BaseModel):
    """功率因数调整规则"""
    min: float = Field(..., description="功率因数下限")
    max: float = Field(..., description="功率因数上限")
    adjustment: float = Field(..., description="电费调整比例 %（正数增加，负数减少）")


class PricingConfigBase(BaseModel):
    """电价全局配置基础模型"""
    config_name: str = Field(default="默认配置", description="配置名称")

    # 基本电费配置（需量/容量二选一）
    billing_mode: str = Field(default="demand", description="计费方式: demand(按需量) / capacity(按容量)")

    # 需量计费参数
    demand_price: float = Field(default=38.0, description="需量电价 元/kW·月")
    declared_demand: Optional[float] = Field(None, description="申报需量 kW")
    over_demand_multiplier: float = Field(default=2.0, description="超需量加价倍数")

    # 容量计费参数
    capacity_price: float = Field(default=28.0, description="容量电价 元/kVA·月")
    transformer_capacity: Optional[float] = Field(None, description="变压器容量 kVA")

    # 功率因数调整配置
    power_factor_baseline: float = Field(default=0.90, description="功率因数基准值")
    power_factor_rules: Optional[List[PowerFactorRule]] = Field(None, description="功率因数调整规则")

    # 固定费用配置（不参与优化，仅用于成本统计）
    transmission_fee: float = Field(default=0.0, description="输配电费 元/kWh")
    government_fund: float = Field(default=0.0, description="政府性基金 元/kWh")
    auxiliary_fee: float = Field(default=0.0, description="辅助服务费 元/kWh")
    other_fee: float = Field(default=0.0, description="其他附加费 元/kWh")

    # 配置元数据
    effective_date: date = Field(..., description="生效日期")
    expire_date: Optional[date] = Field(None, description="失效日期")
    description: Optional[str] = Field(None, description="配置说明")


class PricingConfigCreate(PricingConfigBase):
    """创建电价全局配置"""
    pass


class PricingConfigUpdate(BaseModel):
    """更新电价全局配置"""
    config_name: Optional[str] = None
    billing_mode: Optional[str] = None
    demand_price: Optional[float] = None
    declared_demand: Optional[float] = None
    over_demand_multiplier: Optional[float] = None
    capacity_price: Optional[float] = None
    transformer_capacity: Optional[float] = None
    power_factor_baseline: Optional[float] = None
    power_factor_rules: Optional[List[PowerFactorRule]] = None
    transmission_fee: Optional[float] = None
    government_fund: Optional[float] = None
    auxiliary_fee: Optional[float] = None
    other_fee: Optional[float] = None
    effective_date: Optional[date] = None
    expire_date: Optional[date] = None
    is_enabled: Optional[bool] = None
    description: Optional[str] = None


class PricingConfigResponse(PricingConfigBase):
    """电价全局配置响应"""
    id: int
    is_enabled: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ========== 节能建议 ==========

class EnergySuggestionBase(BaseModel):
    """节能建议基础模型"""
    rule_id: str = Field(..., description="规则ID")
    rule_name: Optional[str] = Field(None, description="规则名称")
    device_id: Optional[int] = Field(None, description="相关设备ID")
    trigger_value: Optional[float] = Field(None, description="触发值")
    threshold_value: Optional[float] = Field(None, description="阈值")
    suggestion: str = Field(..., description="建议内容")
    priority: str = Field("medium", description="优先级: high/medium/low")
    potential_saving: Optional[float] = Field(None, description="预计节省 kWh/月")
    potential_cost_saving: Optional[float] = Field(None, description="预计节省费用 元/月")


class EnergySuggestionCreate(EnergySuggestionBase):
    """创建节能建议"""
    pass


class EnergySuggestionResponse(EnergySuggestionBase):
    """节能建议响应"""
    id: int
    status: str
    accepted_by: Optional[int]
    accepted_at: Optional[datetime]
    completed_at: Optional[datetime]
    actual_saving: Optional[float]
    remark: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AcceptSuggestion(BaseModel):
    """接受建议"""
    remark: Optional[str] = None


class CompleteSuggestion(BaseModel):
    """完成建议"""
    actual_saving: Optional[float] = Field(None, description="实际节省 kWh")
    remark: Optional[str] = None


class RejectSuggestion(BaseModel):
    """拒绝建议"""
    remark: str = Field(..., description="拒绝原因")


class SavingPotential(BaseModel):
    """节能潜力分析"""
    total_potential_saving: float = Field(..., description="总节能潜力 kWh/月")
    total_cost_saving: float = Field(..., description="总节费潜力 元/月")
    high_priority_count: int = Field(..., description="高优先级建议数")
    medium_priority_count: int = Field(..., description="中优先级建议数")
    low_priority_count: int = Field(..., description="低优先级建议数")
    pending_count: int = Field(..., description="待处理建议数")
    accepted_count: int = Field(..., description="已接受建议数")
    completed_count: int = Field(..., description="已完成建议数")
    actual_saving_ytd: float = Field(..., description="本年已实现节能 kWh")


# ========== 配电图 ==========

class DistributionNode(BaseModel):
    """配电节点"""
    device_id: int
    device_code: str
    device_name: str
    device_type: str
    power: Optional[float] = Field(None, description="当前功率 kW")
    load_rate: Optional[float] = Field(None, description="负载率 %")
    status: str = Field("normal", description="状态")
    children: List["DistributionNode"] = []


class DistributionDiagram(BaseModel):
    """配电图数据"""
    root: DistributionNode
    total_power: float
    timestamp: datetime


# ========== 变压器 ==========

class TransformerBase(BaseModel):
    """变压器基础模型"""
    transformer_code: str = Field(..., description="变压器编码")
    transformer_name: str = Field(..., description="变压器名称")
    rated_capacity: float = Field(..., description="额定容量 kVA")
    voltage_high: float = Field(10.0, description="高压侧电压 kV")
    voltage_low: float = Field(0.4, description="低压侧电压 kV")
    connection_type: str = Field("Dyn11", description="接线组别")
    efficiency: float = Field(98.5, description="效率 %")
    no_load_loss: Optional[float] = Field(None, description="空载损耗 kW")
    load_loss: Optional[float] = Field(None, description="负载损耗 kW")
    location: Optional[str] = Field(None, description="安装位置")
    status: str = Field("running", description="状态")
    declared_demand: Optional[float] = Field(None, description="申报需量 kW")
    demand_type: str = Field("kW", description="需量单位: kW/kVA")
    demand_warning_ratio: float = Field(0.9, description="需量预警比例 0-1")


class TransformerCreate(TransformerBase):
    """创建变压器"""
    pass


class TransformerUpdate(BaseModel):
    """更新变压器"""
    transformer_name: Optional[str] = None
    rated_capacity: Optional[float] = None
    voltage_high: Optional[float] = None
    voltage_low: Optional[float] = None
    efficiency: Optional[float] = None
    no_load_loss: Optional[float] = None
    load_loss: Optional[float] = None
    location: Optional[str] = None
    status: Optional[str] = None
    is_enabled: Optional[bool] = None
    declared_demand: Optional[float] = None
    demand_type: Optional[str] = None
    demand_warning_ratio: Optional[float] = None


class TransformerResponse(TransformerBase):
    """变压器响应"""
    id: int
    is_enabled: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ========== 计量点 ==========

class MeterPointBase(BaseModel):
    """计量点基础模型"""
    meter_code: str = Field(..., description="计量点编码")
    meter_name: str = Field(..., description="计量点名称")
    meter_no: Optional[str] = Field(None, description="电表号")
    transformer_id: Optional[int] = Field(None, description="关联变压器ID")
    ct_ratio: Optional[str] = Field(None, description="电流互感器倍率")
    pt_ratio: Optional[str] = Field(None, description="电压互感器倍率")
    multiplier: float = Field(1.0, description="综合倍率")
    declared_demand: Optional[float] = Field(None, description="申报需量 kW/kVA")
    demand_type: str = Field("kW", description="需量类型: kW/kVA")
    demand_period: int = Field(15, description="需量计算周期 分钟")
    customer_no: Optional[str] = Field(None, description="供电局户号")
    customer_name: Optional[str] = Field(None, description="户名")


class MeterPointCreate(MeterPointBase):
    """创建计量点"""
    pass


class MeterPointUpdate(BaseModel):
    """更新计量点"""
    meter_name: Optional[str] = None
    meter_no: Optional[str] = None
    transformer_id: Optional[int] = None
    ct_ratio: Optional[str] = None
    pt_ratio: Optional[str] = None
    multiplier: Optional[float] = None
    declared_demand: Optional[float] = None
    demand_type: Optional[str] = None
    demand_period: Optional[int] = None
    customer_no: Optional[str] = None
    customer_name: Optional[str] = None
    status: Optional[str] = None
    is_enabled: Optional[bool] = None


class MeterPointResponse(MeterPointBase):
    """计量点响应"""
    id: int
    status: str
    is_enabled: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MeterPointDetail(MeterPointResponse):
    """计量点详情(含变压器信息)"""
    transformer_name: Optional[str] = None
    transformer_capacity: Optional[float] = None


# ========== 配电柜 ==========

class DistributionPanelBase(BaseModel):
    """配电柜基础模型"""
    panel_code: str = Field(..., description="配电柜编码")
    panel_name: str = Field(..., description="配电柜名称")
    panel_type: str = Field(..., description="类型: main/sub/ups_input/ups_output")
    rated_current: Optional[float] = Field(None, description="额定电流 A")
    rated_voltage: float = Field(380, description="额定电压 V")
    parent_panel_id: Optional[int] = Field(None, description="上级配电柜ID")
    transformer_id: Optional[int] = Field(None, description="关联变压器ID")
    meter_point_id: Optional[int] = Field(None, description="关联计量点ID")
    location: Optional[str] = Field(None, description="安装位置")


class DistributionPanelCreate(DistributionPanelBase):
    """创建配电柜"""
    pass


class DistributionPanelUpdate(BaseModel):
    """更新配电柜"""
    panel_name: Optional[str] = None
    panel_type: Optional[str] = None
    rated_current: Optional[float] = None
    rated_voltage: Optional[float] = None
    parent_panel_id: Optional[int] = None
    transformer_id: Optional[int] = None
    meter_point_id: Optional[int] = None
    location: Optional[str] = None
    status: Optional[str] = None
    is_enabled: Optional[bool] = None


class DistributionPanelResponse(DistributionPanelBase):
    """配电柜响应"""
    id: int
    status: str
    is_enabled: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ========== 配电回路 ==========

class DistributionCircuitBase(BaseModel):
    """配电回路基础模型"""
    circuit_code: str = Field(..., description="回路编码")
    circuit_name: str = Field(..., description="回路名称")
    panel_id: int = Field(..., description="所属配电柜ID")
    rated_current: Optional[float] = Field(None, description="额定电流 A")
    breaker_type: Optional[str] = Field(None, description="断路器型号")
    breaker_rating: Optional[float] = Field(None, description="断路器额定值 A")
    load_type: Optional[str] = Field(None, description="负载类型")
    is_shiftable: bool = Field(False, description="是否可转移负荷")
    shift_priority: int = Field(99, description="转移优先级")


class DistributionCircuitCreate(DistributionCircuitBase):
    """创建配电回路"""
    pass


class DistributionCircuitUpdate(BaseModel):
    """更新配电回路"""
    circuit_name: Optional[str] = None
    rated_current: Optional[float] = None
    breaker_type: Optional[str] = None
    breaker_rating: Optional[float] = None
    load_type: Optional[str] = None
    is_shiftable: Optional[bool] = None
    shift_priority: Optional[int] = None
    is_enabled: Optional[bool] = None


class DistributionCircuitResponse(DistributionCircuitBase):
    """配电回路响应"""
    id: int
    is_enabled: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ========== 功率曲线 ==========

class PowerCurvePoint(BaseModel):
    """功率曲线数据点"""
    timestamp: datetime
    meter_point_id: Optional[int] = None
    device_id: Optional[int] = None
    active_power: float = Field(..., description="有功功率 kW")
    reactive_power: float = Field(0, description="无功功率 kVar")
    power_factor: float = Field(0.9, description="功率因数")
    demand_15min: float = Field(0, description="15分钟需量 kW")
    time_period: str = Field("flat", description="时段: peak/flat/valley/sharp")


class PowerCurveQuery(BaseModel):
    """功率曲线查询参数"""
    start_time: datetime
    end_time: datetime
    meter_point_id: Optional[int] = None
    device_id: Optional[int] = None
    granularity: str = Field("15min", description="粒度: 5min/15min/1hour")


class PowerCurveResponse(BaseModel):
    """功率曲线响应"""
    meter_point_id: Optional[int] = None
    device_id: Optional[int] = None
    device_name: Optional[str] = None
    data: List[PowerCurvePoint]
    max_power: float
    avg_power: float
    max_demand: float


# ========== 需量历史 ==========

class DemandHistoryItem(BaseModel):
    """需量历史记录"""
    month: str = Field(..., description="月份 YYYY-MM")
    declared_demand: float = Field(..., description="申报需量 kW")
    max_demand: float = Field(..., description="最大需量 kW")
    avg_demand: float = Field(..., description="平均需量 kW")
    demand_95th: float = Field(..., description="95%分位数需量 kW")
    over_declared_times: int = Field(0, description="超申报次数")
    demand_cost: float = Field(0, description="需量电费 元")
    utilization_rate: float = Field(..., description="利用率 %")


class DemandHistoryResponse(BaseModel):
    """需量历史响应"""
    meter_point_id: int
    meter_name: str
    declared_demand: float
    history: List[DemandHistoryItem]


# ========== 设备负荷转移分析 ==========

class DeviceShiftPotential(BaseModel):
    """设备负荷转移潜力"""
    device_id: int
    device_name: str
    device_type: str
    rated_power: float = Field(..., description="额定功率 kW")
    current_power: float = Field(..., description="当前功率 kW")
    is_shiftable: bool = Field(..., description="是否可转移")
    shiftable_power: float = Field(..., description="可转移功率 kW")
    # 5时段用电占比
    sharp_energy_ratio: float = Field(0, description="尖峰用电占比 %")
    peak_energy_ratio: float = Field(..., description="峰时用电占比 %")
    flat_energy_ratio: float = Field(0, description="平时用电占比 %")
    valley_energy_ratio: float = Field(..., description="谷时用电占比 %")
    deep_valley_energy_ratio: float = Field(0, description="深谷用电占比 %")
    shift_potential_saving: float = Field(..., description="转移节省潜力 元/月")
    allowed_shift_hours: List[int] = Field(default_factory=list, description="允许转移时段")
    forbidden_shift_hours: List[int] = Field(default_factory=list, description="禁止转移时段")
    is_critical: bool = Field(False, description="是否关键负荷")


class DeviceShiftAnalysisResult(BaseModel):
    """设备负荷转移分析结果"""
    analysis_time: datetime
    total_devices: int
    shiftable_devices: int
    total_shiftable_power: float = Field(..., description="总可转移功率 kW")
    total_potential_saving: float = Field(..., description="总节省潜力 元/月")
    devices: List[DeviceShiftPotential]
    recommendations: List[str] = Field(default_factory=list, description="转移建议")


# ========== 需量配置分析 ==========

class DemandConfigAnalysisItem(BaseModel):
    """单个计量点需量配置分析"""
    meter_point_id: int
    meter_name: str
    declared_demand: float = Field(..., description="当前申报需量 kW")
    max_demand_12m: float = Field(..., description="近12月最大需量 kW")
    avg_demand_12m: float = Field(..., description="近12月平均需量 kW")
    demand_95th: float = Field(..., description="95%分位数需量 kW")
    utilization_rate: float = Field(..., description="当前利用率 %")
    optimal_demand: float = Field(..., description="建议申报需量 kW")
    is_over_declared: bool = Field(..., description="是否申报过高")
    is_under_declared: bool = Field(..., description="是否申报过低")
    potential_saving: float = Field(..., description="调整后节省 元/年")
    over_demand_risk: float = Field(..., description="超需量风险概率 %")
    recommendation: str = Field(..., description="配置建议")


class DemandConfigAnalysisResult(BaseModel):
    """需量配置分析结果"""
    analysis_time: datetime
    total_meter_points: int
    over_declared_count: int = Field(..., description="申报过高数量")
    under_declared_count: int = Field(..., description="申报过低数量")
    optimal_count: int = Field(..., description="配置合理数量")
    total_potential_saving: float = Field(..., description="总节省潜力 元/年")
    items: List[DemandConfigAnalysisItem]


# ========== 配电系统拓扑 ==========

class TopologyCircuitNode(BaseModel):
    """拓扑回路节点"""
    circuit_id: int
    circuit_code: str
    circuit_name: str
    load_type: Optional[str]
    is_shiftable: bool
    devices: List[PowerDeviceResponse] = []


class TopologyPanelNode(BaseModel):
    """拓扑配电柜节点"""
    panel_id: int
    panel_code: str
    panel_name: str
    panel_type: str
    circuits: List[TopologyCircuitNode] = []


class TopologyMeterNode(BaseModel):
    """拓扑计量点节点"""
    meter_point_id: int
    meter_code: str
    meter_name: str
    declared_demand: Optional[float]
    demand_type: str
    panels: List[TopologyPanelNode] = []


class TopologyTransformerNode(BaseModel):
    """拓扑变压器节点"""
    transformer_id: int
    transformer_code: str
    transformer_name: str
    rated_capacity: float
    meter_points: List[TopologyMeterNode] = []


class DistributionTopologyResponse(BaseModel):
    """配电系统拓扑响应"""
    transformers: List[TopologyTransformerNode]
    total_capacity: float = Field(..., description="总变压器容量 kVA")
    total_meter_points: int
    total_devices: int


# ========== 设备点位配置 ==========

class DevicePointConfig(BaseModel):
    """设备点位配置"""
    monitor_device_id: Optional[int] = Field(None, description="监控设备ID")
    power_point_id: Optional[int] = Field(None, description="功率点位ID")
    energy_point_id: Optional[int] = Field(None, description="电量点位ID")
    voltage_point_id: Optional[int] = Field(None, description="电压点位ID")
    current_point_id: Optional[int] = Field(None, description="电流点位ID")
    pf_point_id: Optional[int] = Field(None, description="功率因数点位ID")


class DevicePointConfigResponse(BaseModel):
    """设备点位配置响应"""
    device_id: int
    device_code: str
    device_name: str
    monitor_device: Optional[dict] = None
    points: dict = Field(default_factory=dict)


class DeviceRealtimeData(BaseModel):
    """设备实时数据"""
    device_id: int
    device_code: str
    device_name: str
    device_type: str
    rated_power: Optional[float]
    power: Optional[float] = Field(None, description="当前功率 kW")
    energy: Optional[float] = Field(None, description="累计电量 kWh")
    voltage: Optional[float] = Field(None, description="电压 V")
    current: Optional[float] = Field(None, description="电流 A")
    power_factor: Optional[float] = Field(None, description="功率因数")
    load_rate: Optional[float] = Field(None, description="负载率 %")
    update_time: Optional[str] = None


# ========== 设备负荷转移配置 ==========

class DeviceShiftConfigCreate(BaseModel):
    """设备负荷转移配置创建"""
    is_shiftable: bool = Field(False, description="是否可转移")
    shiftable_power_ratio: float = Field(0, description="可转移功率比例 0-1")
    is_critical: bool = Field(False, description="是否关键负荷")
    allowed_shift_hours: List[int] = Field(default_factory=list, description="允许转移时段")
    forbidden_shift_hours: List[int] = Field(default_factory=list, description="禁止转移时段")
    min_continuous_runtime: Optional[int] = Field(None, description="最小连续运行时间(分钟)")
    max_shift_duration: Optional[int] = Field(None, description="最大转移持续时间(分钟)")
    min_power: Optional[float] = Field(None, description="最低运行功率 kW")
    max_ramp_rate: Optional[float] = Field(None, description="最大爬坡速率 kW/min")
    shift_notice_time: int = Field(30, description="转移提前通知时间(分钟)")
    requires_manual_approval: bool = Field(True, description="是否需要人工确认")


class DeviceShiftConfigResponse(DeviceShiftConfigCreate):
    """设备负荷转移配置响应"""
    device_id: int


# ========== 需量分析结果 ==========

class DemandAnalysisResponse(BaseModel):
    """需量分析响应"""
    meter_point_id: int
    meter_name: str
    declared_demand: float
    max_demand: float
    avg_demand: float
    demand_95th: float
    utilization_rate: float
    recommended_demand: float
    is_over_declared: bool
    is_under_declared: bool
    potential_saving: float
    over_demand_risk: float
    recommendation: str
    monthly_data: List[dict] = Field(default_factory=list)


# ========== 负荷转移分析结果 ==========

class LoadShiftAnalysisResponse(BaseModel):
    """负荷转移分析响应"""
    analysis_time: datetime
    peak_valley_distribution: dict
    device_potentials: List[dict]
    shift_suggestions: List[dict]
    total_shiftable_power: float
    total_potential_saving: float


# ========== ECharts拓扑数据 ==========

class EChartsTopologyResponse(BaseModel):
    """ECharts拓扑数据响应"""
    name: str
    children: List[dict] = Field(default_factory=list)


# ========== V2.3 负荷调节 ==========

class LoadRegulationConfigBase(BaseModel):
    """负荷调节配置基础模型"""
    device_id: int = Field(..., description="设备ID")
    regulation_type: str = Field(..., description="调节类型: temperature/brightness/mode/load")
    min_value: float = Field(..., description="最小可调值")
    max_value: float = Field(..., description="最大可调值")
    current_value: Optional[float] = Field(None, description="当前值")
    default_value: Optional[float] = Field(None, description="默认值")
    step_size: float = Field(1.0, description="调节步长")
    unit: Optional[str] = Field(None, description="单位")
    power_factor: Optional[float] = Field(None, description="功率系数")
    base_power: Optional[float] = Field(None, description="基准功率 kW")
    priority: int = Field(5, description="调节优先级 1-10")
    comfort_impact: str = Field("low", description="舒适度影响")
    performance_impact: str = Field("none", description="性能影响")


class LoadRegulationConfigCreate(LoadRegulationConfigBase):
    """创建负荷调节配置"""
    power_curve: Optional[List[dict]] = Field(None, description="功率曲线")
    is_auto: bool = Field(False, description="是否自动调节")


class LoadRegulationConfigUpdate(BaseModel):
    """更新负荷调节配置"""
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    current_value: Optional[float] = None
    default_value: Optional[float] = None
    step_size: Optional[float] = None
    power_factor: Optional[float] = None
    base_power: Optional[float] = None
    priority: Optional[int] = None
    comfort_impact: Optional[str] = None
    performance_impact: Optional[str] = None
    is_enabled: Optional[bool] = None
    is_auto: Optional[bool] = None


class LoadRegulationConfigResponse(LoadRegulationConfigBase):
    """负荷调节配置响应"""
    id: int
    power_curve: Optional[List[dict]] = None
    is_enabled: bool
    is_auto: bool
    created_at: datetime
    updated_at: datetime
    # 关联信息
    device_name: Optional[str] = None
    device_type: Optional[str] = None
    rated_power: Optional[float] = None

    class Config:
        from_attributes = True


class RegulationSimulateRequest(BaseModel):
    """调节模拟请求"""
    config_id: int = Field(..., description="配置ID")
    target_value: float = Field(..., description="目标值")


class RegulationSimulateResponse(BaseModel):
    """调节模拟响应"""
    config_id: int
    device_id: int
    device_name: str
    regulation_type: str
    current_value: float
    target_value: float
    current_power: float = Field(..., description="当前功率 kW")
    estimated_power: float = Field(..., description="预估功率 kW")
    power_change: float = Field(..., description="功率变化 kW")
    comfort_impact: str
    performance_impact: str


class RegulationApplyRequest(BaseModel):
    """应用调节请求"""
    config_id: int = Field(..., description="配置ID")
    target_value: float = Field(..., description="目标值")
    reason: str = Field("manual", description="调节原因")
    remark: Optional[str] = None


class RegulationHistoryResponse(BaseModel):
    """调节历史响应"""
    id: int
    config_id: int
    device_id: int
    device_name: Optional[str] = None
    regulation_type: str
    old_value: Optional[float]
    new_value: Optional[float]
    power_before: Optional[float]
    power_after: Optional[float]
    power_saved: Optional[float]
    trigger_reason: Optional[str]
    status: str
    executed_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class RegulationRecommendation(BaseModel):
    """调节建议"""
    config_id: int
    device_id: int
    device_name: str
    regulation_type: str
    current_value: float
    recommended_value: float
    power_saving: float = Field(..., description="节省功率 kW")
    reason: str = Field(..., description="建议原因")
    priority: str = Field(..., description="优先级")


# ========== V2.3 需量分析 ==========

class Demand15MinDataPoint(BaseModel):
    """15分钟需量数据点"""
    timestamp: datetime
    average_power: float = Field(..., description="15分钟平均功率 kW")
    max_power: Optional[float] = None
    min_power: Optional[float] = None
    rolling_demand: Optional[float] = None
    demand_ratio: Optional[float] = None
    time_period: str = Field("flat", description="时段")
    is_over_declared: bool = False


class Demand15MinCurveResponse(BaseModel):
    """15分钟需量曲线响应"""
    meter_point_id: int
    meter_name: str
    declared_demand: float
    start_time: datetime
    end_time: datetime
    data: List[Demand15MinDataPoint]
    max_demand: float
    max_demand_time: Optional[datetime]
    avg_demand: float
    over_declared_count: int


class DemandPeakAnalysisResponse(BaseModel):
    """需量峰值分析响应"""
    meter_point_id: int
    meter_name: str
    declared_demand: float
    analysis_period: str = Field(..., description="分析周期: day/week/month")
    peak_demands: List[dict] = Field(..., description="峰值列表")
    peak_hours_distribution: dict = Field(..., description="峰值时段分布")
    contributing_devices: List[dict] = Field(..., description="贡献设备")
    risk_assessment: dict = Field(..., description="风险评估")


class DemandOptimizationPlan(BaseModel):
    """需量优化方案"""
    meter_point_id: int
    meter_name: str
    current_declared: float
    recommended_declared: float
    current_max_demand: float
    optimization_measures: List[dict] = Field(..., description="优化措施")
    expected_max_demand: float
    demand_reduction: float
    cost_saving_monthly: float
    cost_saving_annual: float
    implementation_difficulty: str


class DemandForecastRequest(BaseModel):
    """需量预测请求"""
    meter_point_id: int
    forecast_days: int = Field(7, description="预测天数")
    include_regulation: bool = Field(False, description="是否包含调节效果")


class DemandForecastResponse(BaseModel):
    """需量预测响应"""
    meter_point_id: int
    meter_name: str
    declared_demand: float
    forecast_data: List[dict] = Field(..., description="预测数据")
    max_forecast_demand: float
    over_demand_probability: float
    recommendations: List[str]


# ========== V2.3 增强节能建议 ==========

class SuggestionTemplate(BaseModel):
    """节能建议模板"""
    template_id: str
    template_name: str
    category: str = Field(..., description="类别: pue/cost/demand/efficiency")
    trigger_conditions: List[dict] = Field(..., description="触发条件")
    title_template: str
    problem_template: str
    analysis_template: str
    measures_template: List[str]
    effect_template: str
    priority: str
    difficulty: str


class EnhancedSuggestionResponse(BaseModel):
    """增强节能建议响应"""
    id: int
    rule_id: str
    rule_name: Optional[str]
    template_id: Optional[str]
    category: Optional[str]
    device_id: Optional[int]
    device_name: Optional[str]
    suggestion: str
    problem_description: Optional[str]
    analysis_detail: Optional[str]
    implementation_steps: Optional[List[dict]]
    expected_effect: Optional[dict]
    priority: str
    difficulty: Optional[str]
    potential_saving: Optional[float]
    potential_cost_saving: Optional[float]
    payback_period: Optional[int]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class SuggestionAnalyzeRequest(BaseModel):
    """触发建议分析请求"""
    categories: Optional[List[str]] = Field(None, description="分析类别")
    device_ids: Optional[List[int]] = Field(None, description="设备ID列表")
    force_refresh: bool = Field(False, description="强制刷新")


class SuggestionAnalyzeResponse(BaseModel):
    """建议分析响应"""
    analyzed_count: int
    new_suggestions: int
    updated_suggestions: int
    categories_analyzed: List[str]
    analysis_time: datetime


# ========== V2.3 能耗仪表盘 ==========

class EnergyDashboardRealtime(BaseModel):
    """实时能耗数据"""
    total_power: float = Field(..., description="总功率 kW")
    it_load: float = Field(..., description="IT负载 kW")
    cooling_load: float = Field(..., description="制冷负载 kW")
    other_load: float = Field(..., description="其他负载 kW")
    pue: float = Field(..., description="当前PUE")


class EnergyDashboardEfficiency(BaseModel):
    """效率指标"""
    current_pue: float
    target_pue: float = Field(1.5, description="目标PUE")
    pue_trend: str = Field(..., description="趋势: up/down/stable")
    pue_change_24h: float = Field(..., description="24小时变化")
    cooling_efficiency: float = Field(..., description="制冷效率 %")


class EnergyDashboardDemand(BaseModel):
    """需量状态"""
    current_demand: float = Field(..., description="当前需量 kW")
    declared_demand: float = Field(..., description="申报需量 kW")
    utilization_rate: float = Field(..., description="利用率 %")
    risk_level: str = Field(..., description="风险等级: low/medium/high/critical")
    time_to_peak: Optional[int] = Field(None, description="距峰值时间 分钟")


class EnergyDashboardCost(BaseModel):
    """成本信息"""
    today_cost: float = Field(..., description="今日电费 元")
    month_cost: float = Field(..., description="本月电费 元")
    forecast_month_cost: float = Field(..., description="预测月电费 元")
    cost_trend: str = Field(..., description="趋势: up/down/stable")


class EnergyDashboardSuggestions(BaseModel):
    """建议概览"""
    total_count: int
    urgent_count: int
    high_count: int
    potential_saving_kwh: float
    potential_saving_cost: float


class EnergyDashboardResponse(BaseModel):
    """能耗仪表盘响应"""
    realtime: EnergyDashboardRealtime
    efficiency: EnergyDashboardEfficiency
    demand: EnergyDashboardDemand
    cost: EnergyDashboardCost
    suggestions: EnergyDashboardSuggestions
    update_time: datetime


# ========== V2.5 节能中心机会管理 ==========

class OpportunityMeasureBase(BaseModel):
    """机会措施基础模型"""
    measure_type: str = Field(..., description="措施类型")
    measure_name: Optional[str] = Field(None, description="措施名称")
    regulation_object: Optional[str] = Field(None, description="调节对象")
    current_state: Optional[Dict] = Field(None, description="当前参数状态")
    target_state: Optional[Dict] = Field(None, description="目标参数状态")
    execution_mode: str = Field(default="manual", description="执行方式: auto/manual/hybrid")
    selected_devices: Optional[List[Dict]] = Field(None, description="选中设备配置")
    calculation_formula: Optional[Dict] = Field(None, description="计算公式")
    annual_benefit: Optional[float] = Field(None, description="年收益(元)")
    confidence: float = Field(default=0.80, description="措施置信度")
    constraints: Optional[Dict] = Field(None, description="约束条件")
    sort_order: int = Field(default=0, description="排序")


class OpportunityMeasureCreate(OpportunityMeasureBase):
    """创建机会措施"""
    opportunity_id: int


class OpportunityMeasureResponse(OpportunityMeasureBase):
    """机会措施响应"""
    id: int
    opportunity_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EnergyOpportunityBase(BaseModel):
    """节能机会基础模型"""
    category: int = Field(..., description="分类: 1-电费结构/2-设备运行/3-设备改造/4-综合能效")
    title: str = Field(..., description="机会标题")
    description: Optional[str] = Field(None, description="机会描述")
    priority: str = Field(default="medium", description="优先级: high/medium/low")
    status: str = Field(default="discovered", description="状态")
    potential_saving: Optional[float] = Field(None, description="年度潜在节省(元)")
    confidence: float = Field(default=0.80, description="置信度(0-1)")
    analysis_data: Optional[Dict] = Field(None, description="分析详情")
    source_plugin: Optional[str] = Field(None, description="来源插件ID")
    trigger_condition: Optional[str] = Field(None, description="触发条件")


class EnergyOpportunityCreate(EnergyOpportunityBase):
    """创建节能机会"""
    pass


class EnergyOpportunityUpdate(BaseModel):
    """更新节能机会"""
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    potential_saving: Optional[float] = None
    confidence: Optional[float] = None
    analysis_data: Optional[Dict] = None


class EnergyOpportunityResponse(EnergyOpportunityBase):
    """节能机会响应"""
    id: int
    discovered_at: datetime
    created_at: datetime
    updated_at: datetime
    measures: List[OpportunityMeasureResponse] = []

    class Config:
        from_attributes = True


class ExecutionTaskBase(BaseModel):
    """执行任务基础模型"""
    task_type: str = Field(..., description="任务类型")
    task_name: Optional[str] = Field(None, description="任务名称")
    target_object: Optional[str] = Field(None, description="目标对象")
    execution_mode: str = Field(default="manual", description="执行方式")
    parameters: Optional[Dict] = Field(None, description="执行参数")
    status: str = Field(default="pending", description="状态")
    assigned_to: Optional[str] = Field(None, description="负责人")
    scheduled_at: Optional[datetime] = Field(None, description="计划时间")
    sort_order: int = Field(default=0, description="排序")


class ExecutionTaskCreate(ExecutionTaskBase):
    """创建执行任务"""
    plan_id: int


class ExecutionTaskUpdate(BaseModel):
    """更新执行任务"""
    status: Optional[str] = None
    assigned_to: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    result: Optional[Dict] = None
    error_message: Optional[str] = None


class ExecutionTaskResponse(ExecutionTaskBase):
    """执行任务响应"""
    id: int
    plan_id: int
    executed_at: Optional[datetime]
    result: Optional[Dict]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ExecutionResultBase(BaseModel):
    """执行结果基础模型"""
    tracking_period: int = Field(default=7, description="追踪周期(天)")
    tracking_start: Optional[date] = Field(None, description="开始日期")
    tracking_end: Optional[date] = Field(None, description="结束日期")
    actual_saving: Optional[float] = Field(None, description="实际节省(元)")
    achievement_rate: Optional[float] = Field(None, description="达成率(%)")
    power_curve_before: Optional[Dict] = Field(None, description="执行前功率曲线")
    power_curve_after: Optional[Dict] = Field(None, description="执行后功率曲线")
    energy_before: Optional[Dict] = Field(None, description="执行前能耗")
    energy_after: Optional[Dict] = Field(None, description="执行后能耗")
    analysis_conclusion: Optional[str] = Field(None, description="分析结论")
    notes: Optional[str] = Field(None, description="备注")
    status: str = Field(default="tracking", description="状态")


class ExecutionResultCreate(ExecutionResultBase):
    """创建执行结果"""
    plan_id: int


class ExecutionResultResponse(ExecutionResultBase):
    """执行结果响应"""
    id: int
    plan_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ExecutionPlanBase(BaseModel):
    """执行计划基础模型"""
    plan_name: Optional[str] = Field(None, description="计划名称")
    expected_saving: Optional[float] = Field(None, description="预期年节省(元)")
    status: str = Field(default="pending", description="状态")
    notes: Optional[str] = Field(None, description="备注")


class ExecutionPlanCreate(ExecutionPlanBase):
    """创建执行计划"""
    opportunity_id: int
    created_by: Optional[int] = None


class ExecutionPlanResponse(ExecutionPlanBase):
    """执行计划响应"""
    id: int
    opportunity_id: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_by: Optional[int]
    created_at: datetime
    updated_at: datetime
    tasks: List[ExecutionTaskResponse] = []
    results: List[ExecutionResultResponse] = []

    class Config:
        from_attributes = True


# ========== 仪表盘数据模型 ==========

class OpportunitySummary(BaseModel):
    """机会概览"""
    id: int
    category: int
    title: str
    description: Optional[str] = None
    priority: str
    potential_saving: float
    confidence: float
    status: str
    source_plugin: Optional[str] = None
    analysis_data: Optional[Dict] = None


class DashboardSummaryCards(BaseModel):
    """仪表盘概览卡片"""
    annual_potential_saving: float = Field(..., description="年度可节省(元)")
    pending_opportunities: int = Field(..., description="待处理机会数")
    executing_plans: int = Field(..., description="执行中任务数")
    monthly_actual_saving: float = Field(..., description="本月已节省(元)")


class DashboardResponse(BaseModel):
    """机会仪表盘响应"""
    summary_cards: DashboardSummaryCards
    opportunities: List[OpportunitySummary]
    by_category: Dict[str, List[OpportunitySummary]]
    total_count: int


# ========== 模拟请求/响应 ==========

class SimulationRequest(BaseModel):
    """模拟请求"""
    simulation_type: str = Field(..., description="模拟类型")
    parameters: Dict = Field(..., description="模拟参数")


class SimulationResponse(BaseModel):
    """模拟响应"""
    is_feasible: bool
    current_state: Dict
    simulated_state: Dict
    benefit: Dict
    confidence: float
    warnings: List[str] = []
    recommendations: List[str] = []


class DeviceCapability(BaseModel):
    """设备能力"""
    device_id: int
    device_name: str
    device_type: str
    rated_power: Optional[float]
    adjustable_power: float = Field(..., description="可调节功率 kW")
    allowed_hours: List[int] = Field(..., description="允许调节时段(0-23)")
    execution_mode: str = Field(..., description="执行方式: auto/manual/hybrid")
    regulation_type: Optional[str] = Field(None, description="调节类型: temperature/brightness/load")
    current_value: Optional[float] = Field(None, description="当前值")
    min_value: Optional[float] = Field(None, description="最小可调值")
    max_value: Optional[float] = Field(None, description="最大可调值")
    unit: Optional[str] = Field(None, description="单位")
    constraints: Optional[Dict] = Field(None, description="约束条件")


class DeviceSelectionRequest(BaseModel):
    """设备选择请求"""
    selected_device_ids: List[int] = Field(..., description="选中的设备ID列表")
    target_power: Optional[float] = Field(None, description="目标功率 kW")
    target_hours: Optional[List[int]] = Field(None, description="目标时段")


class DeviceSelectionResponse(BaseModel):
    """设备选择响应"""
    selected_count: int
    total_adjustable_power: float
    time_intersection: List[int] = Field(..., description="时段交集")
    is_feasible: bool
    warnings: List[str] = []


# ========== V2.6 负荷转移执行计划 ==========

class ShiftRule(BaseModel):
    """负荷转移规则"""
    source_period: str = Field(..., description="源时段: sharp/peak/flat")
    target_period: str = Field(..., description="目标时段: flat/valley/deep_valley")
    power: float = Field(..., description="转移功率 kW")
    hours: int = Field(..., description="转移小时数")


class DeviceShiftRule(BaseModel):
    """设备转移规则"""
    device_id: int = Field(..., description="设备ID")
    device_name: str = Field(..., description="设备名称")
    rules: List[ShiftRule] = Field(..., description="转移规则列表")


class CreateLoadShiftPlanRequest(BaseModel):
    """创建负荷转移执行计划请求"""
    plan_name: str = Field(..., min_length=2, max_length=50, description="计划名称")
    strategy: str = Field(..., description="优化策略: max_benefit/min_cost")
    daily_saving: float = Field(..., description="预期日节省(元)")
    annual_saving: float = Field(..., description="预期年节省(元)")
    device_rules: List[DeviceShiftRule] = Field(..., description="设备转移规则")
    remark: Optional[str] = Field(None, max_length=200, description="备注")
    meter_point_id: Optional[int] = Field(None, description="计量点ID")


class CreateLoadShiftPlanResponse(BaseModel):
    """创建执行计划响应"""
    plan_id: int = Field(..., description="计划ID")
    opportunity_id: int = Field(..., description="机会ID")
    plan_name: str = Field(..., description="计划名称")
    expected_saving: float = Field(..., description="预期年节省(元)")
    task_count: int = Field(..., description="任务数量")


# ========== V2.7 拓扑编辑功能 ==========

class TopologyNodeType(str, Enum):
    """拓扑节点类型"""
    TRANSFORMER = "transformer"
    METER_POINT = "meter_point"
    PANEL = "panel"
    CIRCUIT = "circuit"
    DEVICE = "device"
    POINT = "point"


class TopologyNodePosition(BaseModel):
    """拓扑节点位置"""
    x: float = Field(..., description="X坐标")
    y: float = Field(..., description="Y坐标")


class TopologyNodeCreate(BaseModel):
    """创建拓扑节点"""
    node_type: TopologyNodeType = Field(..., description="节点类型")
    parent_id: Optional[int] = Field(None, description="父节点ID")
    parent_type: Optional[TopologyNodeType] = Field(None, description="父节点类型")
    position: Optional[TopologyNodePosition] = Field(None, description="节点位置")

    # 变压器字段
    transformer_code: Optional[str] = Field(None, max_length=50)
    transformer_name: Optional[str] = Field(None, max_length=100)
    rated_capacity: Optional[float] = Field(None, ge=0)
    voltage_high: Optional[float] = Field(None, ge=0)
    voltage_low: Optional[float] = Field(None, ge=0)

    # 计量点字段
    meter_code: Optional[str] = Field(None, max_length=50)
    meter_name: Optional[str] = Field(None, max_length=100)
    ct_ratio: Optional[float] = Field(None)
    pt_ratio: Optional[float] = Field(None)

    # 配电柜字段
    panel_code: Optional[str] = Field(None, max_length=50)
    panel_name: Optional[str] = Field(None, max_length=100)
    panel_type: Optional[str] = Field(None)

    # 回路字段
    circuit_code: Optional[str] = Field(None, max_length=50)
    circuit_name: Optional[str] = Field(None, max_length=100)
    circuit_type: Optional[str] = Field(None)
    rated_current: Optional[float] = Field(None, ge=0)

    # 设备字段
    device_code: Optional[str] = Field(None, max_length=50)
    device_name: Optional[str] = Field(None, max_length=100)
    device_type: Optional[str] = Field(None)
    rated_power: Optional[float] = Field(None)

    # 采集点位字段
    point_code: Optional[str] = Field(None, max_length=50)
    point_name: Optional[str] = Field(None, max_length=100)
    point_type: Optional[str] = Field(None)
    measurement_type: Optional[str] = Field(None)
    register_address: Optional[str] = Field(None, max_length=50)
    data_type: Optional[str] = Field(None)
    scale_factor: Optional[float] = Field(None)


class TopologyNodeUpdate(BaseModel):
    """更新拓扑节点"""
    node_id: int = Field(..., description="节点ID")
    node_type: TopologyNodeType = Field(..., description="节点类型")
    position: Optional[TopologyNodePosition] = Field(None, description="节点位置")

    # 通用字段
    name: Optional[str] = Field(None, max_length=100, description="名称")
    code: Optional[str] = Field(None, max_length=50, description="编码")
    status: Optional[str] = Field(None, description="状态")
    is_enabled: Optional[bool] = Field(None, description="是否启用")
    location: Optional[str] = Field(None, description="位置")
    remark: Optional[str] = Field(None, description="备注")

    # 特定字段 - 根据node_type使用
    rated_capacity: Optional[float] = Field(None, description="额定容量")
    rated_power: Optional[float] = Field(None, description="额定功率")
    rated_current: Optional[float] = Field(None, description="额定电流")
    voltage_high: Optional[float] = Field(None, description="高压侧电压")
    voltage_low: Optional[float] = Field(None, description="低压侧电压")
    ct_ratio: Optional[float] = Field(None, description="CT变比")
    pt_ratio: Optional[float] = Field(None, description="PT变比")
    declared_demand: Optional[float] = Field(None, description="申报需量")


class TopologyNodeDelete(BaseModel):
    """删除拓扑节点"""
    node_id: int = Field(..., description="节点ID")
    node_type: TopologyNodeType = Field(..., description="节点类型")
    cascade: bool = Field(False, description="是否级联删除子节点")


class TopologyConnectionCreate(BaseModel):
    """创建拓扑连接"""
    source_id: int = Field(..., description="源节点ID")
    source_type: TopologyNodeType = Field(..., description="源节点类型")
    target_id: int = Field(..., description="目标节点ID")
    target_type: TopologyNodeType = Field(..., description="目标节点类型")


class TopologyConnectionDelete(BaseModel):
    """删除拓扑连接"""
    source_id: int = Field(..., description="源节点ID")
    source_type: TopologyNodeType = Field(..., description="源节点类型")
    target_id: int = Field(..., description="目标节点ID")
    target_type: TopologyNodeType = Field(..., description="目标节点类型")


class TopologyBatchOperation(BaseModel):
    """批量拓扑操作"""
    creates: List[TopologyNodeCreate] = Field(default_factory=list, description="创建操作列表")
    updates: List[TopologyNodeUpdate] = Field(default_factory=list, description="更新操作列表")
    deletes: List[TopologyNodeDelete] = Field(default_factory=list, description="删除操作列表")
    connections_add: List[TopologyConnectionCreate] = Field(default_factory=list, description="添加连接列表")
    connections_remove: List[TopologyConnectionDelete] = Field(default_factory=list, description="删除连接列表")


class TopologyBatchResult(BaseModel):
    """批量操作结果"""
    success: bool = Field(..., description="是否全部成功")
    created_count: int = Field(0, description="创建数量")
    updated_count: int = Field(0, description="更新数量")
    deleted_count: int = Field(0, description="删除数量")
    connections_added: int = Field(0, description="添加连接数量")
    connections_removed: int = Field(0, description="删除连接数量")
    errors: List[str] = Field(default_factory=list, description="错误信息列表")
    created_ids: Dict[str, int] = Field(default_factory=dict, description="创建的节点ID映射")


class TopologyExport(BaseModel):
    """拓扑导出数据"""
    version: str = Field("1.0", description="导出版本")
    export_time: datetime = Field(..., description="导出时间")
    transformers: List[Dict] = Field(default_factory=list)
    meter_points: List[Dict] = Field(default_factory=list)
    panels: List[Dict] = Field(default_factory=list)
    circuits: List[Dict] = Field(default_factory=list)
    devices: List[Dict] = Field(default_factory=list)
    connections: List[Dict] = Field(default_factory=list)


class TopologyImport(BaseModel):
    """拓扑导入数据"""
    version: str = Field(..., description="导入版本")
    clear_existing: bool = Field(False, description="是否清除现有数据")
    transformers: List[Dict] = Field(default_factory=list)
    meter_points: List[Dict] = Field(default_factory=list)
    panels: List[Dict] = Field(default_factory=list)
    circuits: List[Dict] = Field(default_factory=list)
    devices: List[Dict] = Field(default_factory=list)
    connections: List[Dict] = Field(default_factory=list)


# ========== V2.7 设备测点配置 ==========

class DevicePointType(str, Enum):
    """设备测点类型"""
    MEASUREMENT = "measurement"  # 测量点
    CONTROL = "control"  # 控制点
    STATUS = "status"  # 状态点
    ALARM = "alarm"  # 告警点


class DevicePointConfig(BaseModel):
    """设备测点配置"""
    point_code: str = Field(..., max_length=50, description="点位编码")
    point_name: str = Field(..., max_length=100, description="点位名称")
    point_type: str = Field("AI", description="点位类型: AI/DI/AO/DO")
    device_type: str = Field("power", description="用途: power/current/energy/voltage/power_factor/other")
    area_code: str = Field("A1", description="区域代码")
    data_type: str = Field("float", description="数据类型: float/int/bool/string")
    unit: Optional[str] = Field(None, description="单位")
    min_range: Optional[float] = Field(None, description="量程最小值")
    max_range: Optional[float] = Field(None, description="量程最大值")
    collect_interval: int = Field(10, description="采集周期(秒)")
    description: Optional[str] = Field(None, description="描述")

    # 采集配置
    device_id: Optional[int] = Field(None, description="关联采集设备ID")
    register_address: Optional[str] = Field(None, description="寄存器地址")
    function_code: Optional[int] = Field(None, description="功能码")
    scale_factor: float = Field(1.0, description="比例因子")
    offset: float = Field(0.0, description="偏移量")

    # 告警配置
    alarm_enabled: bool = Field(False, description="是否启用告警")
    alarm_high: Optional[float] = Field(None, description="上限告警值")
    alarm_low: Optional[float] = Field(None, description="下限告警值")


class DevicePointConfigCreate(BaseModel):
    """创建设备测点"""
    energy_device_id: int = Field(..., description="用能设备ID")
    points: List[DevicePointConfig] = Field(..., description="测点列表")


class DevicePointConfigUpdate(BaseModel):
    """更新设备测点"""
    point_id: Optional[int] = Field(None, description="测点ID")
    point_name: Optional[str] = Field(None, max_length=100)
    unit: Optional[str] = Field(None)
    min_range: Optional[float] = Field(None, description="量程最小值")
    max_range: Optional[float] = Field(None, description="量程最大值")
    collect_interval: Optional[int] = Field(None, description="采集周期(秒)")
    description: Optional[str] = Field(None)
    device_id: Optional[int] = Field(None)
    register_address: Optional[str] = Field(None)
    function_code: Optional[int] = Field(None)
    scale_factor: Optional[float] = Field(None)
    offset: Optional[float] = Field(None)
    alarm_enabled: Optional[bool] = Field(None)
    alarm_high: Optional[float] = Field(None)
    alarm_low: Optional[float] = Field(None)


class DevicePointConfigResponse(BaseModel):
    """设备测点响应"""
    id: int
    energy_device_id: int
    point_code: str
    point_name: str
    point_type: str
    data_type: str
    unit: Optional[str]
    description: Optional[str]
    device_id: Optional[int]
    register_address: Optional[str]
    function_code: Optional[int]
    scale_factor: float
    offset: float
    alarm_enabled: bool
    alarm_high: Optional[float]
    alarm_low: Optional[float]
    current_value: Optional[float] = None
    last_update_time: Optional[datetime] = None

    class Config:
        from_attributes = True


class TopologyNodeResponse(BaseModel):
    """拓扑节点响应"""
    id: int
    node_type: str
    code: str
    name: str
    status: Optional[str] = None
    is_enabled: bool = True
    parent_id: Optional[int] = None
    parent_type: Optional[str] = None
    children_count: int = 0
    position: Optional[TopologyNodePosition] = None
    attributes: Dict = Field(default_factory=dict, description="节点特定属性")
    points: List[DevicePointConfigResponse] = Field(default_factory=list, description="关联测点")

    class Config:
        from_attributes = True

