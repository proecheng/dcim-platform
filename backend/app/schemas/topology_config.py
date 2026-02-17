"""
配电与制冷拓扑配置 Schema
"""
from typing import Optional, List
from pydantic import BaseModel, Field, model_validator


# ==================== PowerPhaseMapping Schemas ====================

class PowerPhaseMappingCreate(BaseModel):
    """创建三相接线映射"""
    cabinet_id: int = Field(..., description="机柜ID")
    pdu_device_id: int = Field(..., description="PDU设备ID")
    phase: str = Field(..., description="相位: A/B/C")
    feed_type: str = Field(..., description="馈电类型: primary/backup")
    rated_current: Optional[float] = Field(None, description="额定电流(A)")
    description: Optional[str] = Field(None, description="描述")


class PowerPhaseMappingUpdate(BaseModel):
    """更新三相接线映射"""
    phase: Optional[str] = Field(None, description="相位: A/B/C")
    feed_type: Optional[str] = Field(None, description="馈电类型: primary/backup")
    rated_current: Optional[float] = Field(None, description="额定电流(A)")
    description: Optional[str] = Field(None, description="描述")


class PowerPhaseMappingResponse(BaseModel):
    """三相接线映射响应"""
    id: int
    cabinet_id: int
    pdu_device_id: int
    phase: str
    feed_type: str
    rated_current: Optional[float] = None
    description: Optional[str] = None
    pdu_device_name: Optional[str] = None
    pdu_device_code: Optional[str] = None
    cabinet_code: Optional[str] = None
    cabinet_name: Optional[str] = None

    class Config:
        from_attributes = True


# ==================== CoolingZone Schemas ====================

class CoolingZoneCreate(BaseModel):
    """创建制冷区域"""
    zone_name: str = Field(..., description="区域名称")
    room_id: Optional[int] = Field(None, description="所属房间ID")
    design_capacity_kw: Optional[float] = Field(None, description="设计制冷量(kW)")
    description: Optional[str] = Field(None, description="描述")
    cabinet_ids: List[int] = Field(default_factory=list, description="关联机柜ID列表")
    cooling_unit_ids: List[int] = Field(default_factory=list, description="关联空调ID列表")


class CoolingZoneUpdate(BaseModel):
    """更新制冷区域"""
    zone_name: Optional[str] = Field(None, description="区域名称")
    room_id: Optional[int] = Field(None, description="所属房间ID")
    design_capacity_kw: Optional[float] = Field(None, description="设计制冷量(kW)")
    description: Optional[str] = Field(None, description="描述")
    cabinet_ids: Optional[List[int]] = Field(None, description="关联机柜ID列表")
    cooling_unit_ids: Optional[List[int]] = Field(None, description="关联空调ID列表")


class CoolingZoneCabinetItem(BaseModel):
    """制冷区域中的机柜简要信息"""
    id: int
    cabinet_code: str
    cabinet_name: str


class CoolingZoneUnitItem(BaseModel):
    """制冷区域中的空调简要信息"""
    id: int
    device_code: Optional[str] = None
    device_name: Optional[str] = None
    cooling_capacity_kw: Optional[float] = None


class CoolingZoneResponse(BaseModel):
    """制冷区域响应"""
    id: int
    zone_code: str
    zone_name: str
    room_id: Optional[int] = None
    design_capacity_kw: Optional[float] = None
    description: Optional[str] = None
    cabinets: List[CoolingZoneCabinetItem] = Field(default_factory=list)
    cooling_units: List[CoolingZoneUnitItem] = Field(default_factory=list)

    class Config:
        from_attributes = True


# ==================== PhaseBalance Schemas ====================

class PhaseBalanceResponse(BaseModel):
    """三相不平衡度响应"""
    pdu_device_id: int
    pdu_device_name: Optional[str] = None
    phase_a_power: float = 0.0
    phase_b_power: float = 0.0
    phase_c_power: float = 0.0
    imbalance_rate: Optional[float] = None
    data_source: str = "no_data"
    phase_a_cabinets: List[str] = Field(default_factory=list)
    phase_b_cabinets: List[str] = Field(default_factory=list)
    phase_c_cabinets: List[str] = Field(default_factory=list)


# ==================== CabinetTopologySummary ====================

class SpatialInfo(BaseModel):
    """空间信息"""
    site_name: Optional[str] = None
    floor_name: Optional[str] = None
    room_name: Optional[str] = None
    row_name: Optional[str] = None


class PowerInfo(BaseModel):
    """配电信息"""
    pdu_device_name: Optional[str] = None
    phase: Optional[str] = None
    feed_type: Optional[str] = None


class CoolingInfo(BaseModel):
    """制冷信息"""
    zone_name: Optional[str] = None
    design_capacity_kw: Optional[float] = None


class CabinetTopologySummary(BaseModel):
    """机柜拓扑汇总"""
    cabinet_id: int
    cabinet_code: Optional[str] = None
    cabinet_name: Optional[str] = None
    spatial: Optional[SpatialInfo] = None
    power: List[PowerInfo] = Field(default_factory=list)
    cooling: List[CoolingInfo] = Field(default_factory=list)


# ==================== CoolingZoneCapacity ====================

class CoolingZoneCapacityResponse(BaseModel):
    """制冷区域容量使用响应"""
    zone_id: int
    zone_name: str
    design_capacity_kw: Optional[float] = None
    total_cabinet_power: float = 0.0
    utilization_rate: Optional[float] = None


# ==================== 智能选址 Schemas ====================

class SmartSiteWeights(BaseModel):
    space: float = Field(30, ge=0, description="空间容量权重")
    power: float = Field(25, ge=0, description="电力容量权重")
    phase_balance: float = Field(20, ge=0, description="三相平衡度权重")
    temperature: float = Field(15, ge=0, description="温度环境权重")
    cooling: float = Field(10, ge=0, description="制冷余量权重")

    @model_validator(mode='after')
    def normalize_weights(self):
        total = self.space + self.power + self.phase_balance + self.temperature + self.cooling
        if total <= 0:
            self.space, self.power, self.phase_balance, self.temperature, self.cooling = 30, 25, 20, 15, 10
        elif abs(total - 100) > 0.01:
            factor = 100 / total
            self.space = round(self.space * factor, 2)
            self.power = round(self.power * factor, 2)
            self.phase_balance = round(self.phase_balance * factor, 2)
            self.temperature = round(self.temperature * factor, 2)
            self.cooling = max(0, round(100 - self.space - self.power - self.phase_balance - self.temperature, 2))
        return self


class SmartSiteRequest(BaseModel):
    required_u: int = Field(..., ge=1, description="所需U位数")
    required_power_kw: Optional[float] = Field(None, ge=0, description="所需功率(kW)")
    required_weight_kg: Optional[float] = Field(None, ge=0, description="所需承重(kg)")
    limit: int = Field(10, ge=1, le=50, description="返回候选数量")
    weights: Optional[SmartSiteWeights] = Field(None, description="权重配置")


class DimensionScore(BaseModel):
    dimension: str
    score: float
    weight: float
    weighted_score: float
    data_available: bool
    detail: str = ""


class CabinetSiteScore(BaseModel):
    cabinet_id: int
    cabinet_code: str
    cabinet_name: str
    location: Optional[str] = None
    room_name: Optional[str] = None
    row_name: Optional[str] = None
    available_u: int
    total_score: float
    confidence: str
    dimensions: List[DimensionScore] = Field(default_factory=list)
    grid_x: Optional[int] = None
    grid_y: Optional[int] = None
    aisle_type: Optional[str] = None


class SmartSiteResponse(BaseModel):
    candidates: List[CabinetSiteScore] = Field(default_factory=list)
    total_evaluated: int = 0
    qualified_count: int = 0


# ==================== 故障影响分析 Schemas ====================

class FaultImpactRequest(BaseModel):
    """故障影响分析请求"""
    fault_source_type: str = Field(..., description="故障源类型: pdu/panel")
    fault_source_id: int = Field(..., description="故障源ID (pdu→devices.id, panel→distribution_panels.id)")


class AffectedCabinet(BaseModel):
    """受影响机柜"""
    cabinet_id: int
    cabinet_code: str
    cabinet_name: str
    location: Optional[str] = None
    feed_type: Optional[str] = None
    phase: Optional[str] = None
    asset_count: int = 0
    impact_level: str = "power_loss"  # power_loss=完全断电, degraded=降级(有冗余)
    has_redundancy: bool = False


class AffectedAsset(BaseModel):
    """受影响资产"""
    asset_id: int
    asset_code: str
    asset_name: str
    asset_type: Optional[str] = None
    cabinet_code: Optional[str] = None


class CoolingImpactItem(BaseModel):
    """制冷交叉影响"""
    zone_id: int
    zone_name: str
    affected_cabinet_count: int = 0
    total_cabinet_count: int = 0
    cooling_units: List[str] = Field(default_factory=list)
    same_power_circuit: bool = False
    power_circuit_data_source: str = "unknown"  # confirmed/unknown


class RelatedAlarmItem(BaseModel):
    """关联告警"""
    alarm_id: int
    alarm_no: str
    alarm_level: str
    alarm_message: str
    status: str
    created_at: Optional[str] = None


class FaultImpactResponse(BaseModel):
    """故障影响分析响应"""
    fault_source_type: str
    fault_source_id: int
    fault_source_name: Optional[str] = None
    affected_cabinets: List[AffectedCabinet] = Field(default_factory=list)
    affected_assets: List[AffectedAsset] = Field(default_factory=list)
    cooling_impacts: List[CoolingImpactItem] = Field(default_factory=list)
    related_alarms: List[RelatedAlarmItem] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
    analysis_time: Optional[str] = None
