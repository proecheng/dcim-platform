"""
节能分析插件基础架构
Energy Saving Analysis Plugin Base Architecture

根据 findings.md 5.4.1 设计实现
Enhanced with meter points, distribution topology and power curve support
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class PluginPriority(Enum):
    """插件优先级"""
    CRITICAL = 1  # 紧急
    HIGH = 2      # 高
    MEDIUM = 3    # 中
    LOW = 4       # 低


class SuggestionType(Enum):
    """建议类型"""
    LOAD_SHIFTING = "load_shifting"           # 负荷转移
    DEMAND_OPTIMIZATION = "demand_optimization"  # 需量优化
    POWER_FACTOR = "power_factor"             # 功率因数
    PEAK_VALLEY = "peak_valley"               # 峰谷优化
    PUE_OPTIMIZATION = "pue_optimization"     # PUE优化
    EQUIPMENT_EFFICIENCY = "equipment_efficiency"  # 设备效率
    DEMAND_CONFIG = "demand_config"           # 需量配置
    DEVICE_SHIFT = "device_shift"             # 设备负荷转移


@dataclass
class EnergyData:
    """能耗数据"""
    date: datetime
    total_energy: float          # 总电量 kWh
    peak_energy: float           # 峰时电量 kWh
    valley_energy: float         # 谷时电量 kWh
    flat_energy: float           # 平时电量 kWh
    sharp_energy: float = 0      # 尖峰电量 kWh (新增)
    peak_cost: float = 0         # 峰时电费
    valley_cost: float = 0       # 谷时电费
    flat_cost: float = 0         # 平时电费
    total_cost: float = 0        # 总电费


@dataclass
class PowerData:
    """功率数据"""
    timestamp: datetime
    device_id: str
    device_name: str
    device_type: str
    voltage: float               # 电压 V
    current: float               # 电流 A
    active_power: float          # 有功功率 kW
    reactive_power: float        # 无功功率 kVar
    apparent_power: float        # 视在功率 kVA
    power_factor: float          # 功率因数
    frequency: float             # 频率 Hz
    load_rate: float             # 负载率 %


@dataclass
class BillData:
    """电费账单数据"""
    period_start: datetime
    period_end: datetime
    total_energy: float          # 总电量
    total_cost: float            # 总电费
    peak_ratio: float            # 峰时占比
    valley_ratio: float          # 谷时占比
    flat_ratio: float            # 平时占比
    demand_cost: float           # 需量电费
    basic_cost: float            # 基本电费
    max_demand: float            # 最大需量 kW


@dataclass
class DeviceData:
    """设备数据"""
    device_id: str
    device_name: str
    device_type: str             # UPS/PDU/AIR_CONDITIONER/IT_EQUIPMENT
    rated_power: float           # 额定功率 kW
    current_power: float         # 当前功率 kW
    efficiency: float            # 效率 %
    running_hours: float         # 运行时长 h
    location: str                # 位置
    # 新增字段
    circuit_id: Optional[int] = None        # 所属回路ID
    meter_point_id: Optional[int] = None    # 关联计量点ID
    is_critical: bool = False               # 是否关键负荷
    is_shiftable: bool = False              # 是否可转移


@dataclass
class EnvironmentData:
    """环境数据"""
    timestamp: datetime
    temperature: float           # 温度 ℃
    humidity: float              # 湿度 %
    pue: float                   # PUE值
    it_power: float              # IT负载功率 kW
    cooling_power: float         # 制冷功率 kW
    total_power: float           # 总功率 kW


# ==================== 新增数据类 ====================

@dataclass
class MeterPointData:
    """计量点数据"""
    meter_point_id: int
    meter_code: str
    meter_name: str
    transformer_id: Optional[int]    # 关联变压器ID
    transformer_name: Optional[str]  # 变压器名称
    declared_demand: float           # 申报需量 kW
    demand_type: str                 # kW 或 kVA
    customer_no: Optional[str]       # 供电局户号


@dataclass
class PowerCurvePoint:
    """功率曲线数据点"""
    timestamp: datetime
    meter_point_id: Optional[int]    # 计量点ID
    device_id: Optional[int]         # 设备ID
    active_power: float              # 有功功率 kW
    reactive_power: float            # 无功功率 kVar
    power_factor: float              # 功率因数
    demand_15min: float              # 15分钟需量 kW
    time_period: str                 # peak/flat/valley/sharp


@dataclass
class DemandHistoryData:
    """需量历史数据"""
    month: str                       # YYYY-MM
    declared_demand: float           # 申报需量
    max_demand: float                # 当月最大需量
    avg_demand: float                # 当月平均需量
    demand_95th: float               # 95%分位数需量
    over_declared_times: int         # 超申报次数
    demand_cost: float               # 需量电费
    utilization_rate: float          # 利用率 = max_demand/declared_demand


@dataclass
class DeviceShiftInfo:
    """设备负荷转移信息"""
    device_id: int
    device_name: str
    device_type: str
    rated_power: float               # 额定功率
    current_power: float             # 当前功率
    is_shiftable: bool               # 是否可转移
    shiftable_power_ratio: float     # 可转移功率比例
    allowed_shift_hours: List[int]   # 允许转移的时段
    forbidden_shift_hours: List[int] # 禁止转移的时段
    is_critical: bool                # 是否关键负荷
    # 用电分布
    peak_energy_ratio: float         # 峰时用电占比
    valley_energy_ratio: float       # 谷时用电占比


@dataclass
class DistributionTopology:
    """配电系统拓扑"""
    transformers: List[Dict[str, Any]]      # 变压器列表
    meter_points: List[MeterPointData]      # 计量点列表
    panels: List[Dict[str, Any]]            # 配电柜列表
    circuits: List[Dict[str, Any]]          # 回路列表
    device_meter_mapping: Dict[int, int]    # 设备ID -> 计量点ID 映射


@dataclass
class AnalysisContext:
    """
    分析上下文 - 提供给插件的数据
    Analysis Context - Data provided to plugins
    Enhanced with meter points, distribution topology and power curve support
    """
    # 能耗数据 (最近30天)
    energy_data: List[EnergyData] = field(default_factory=list)

    # 实时功率数据 (所有设备)
    power_data: List[PowerData] = field(default_factory=list)

    # 电费账单数据 (最近12个月)
    bill_data: List[BillData] = field(default_factory=list)

    # 设备信息
    device_data: List[DeviceData] = field(default_factory=list)

    # 环境数据 (最近7天)
    environment_data: List[EnvironmentData] = field(default_factory=list)

    # ==================== 新增: 配电拓扑与计量点 ====================

    # 配电系统拓扑
    distribution_topology: Optional[DistributionTopology] = None

    # 计量点数据
    meter_points: List[MeterPointData] = field(default_factory=list)

    # 功率曲线数据 (15分钟粒度)
    power_curve_data: List[PowerCurvePoint] = field(default_factory=list)

    # 需量历史数据 (按计量点)
    demand_history: Dict[int, List[DemandHistoryData]] = field(default_factory=dict)

    # 设备负荷转移信息
    device_shift_info: List[DeviceShiftInfo] = field(default_factory=list)

    # 设备能耗数据 (按设备ID分组的日能耗)
    device_energy_data: Dict[int, List[EnergyData]] = field(default_factory=dict)

    # ==================== 电价配置 ====================

    # 电价配置
    pricing_config: Dict[str, float] = field(default_factory=lambda: {
        'peak_price': 1.2,      # 峰时电价 元/kWh
        'valley_price': 0.4,    # 谷时电价 元/kWh
        'flat_price': 0.8,      # 平时电价 元/kWh
        'sharp_price': 1.5,     # 尖峰电价 元/kWh
        'demand_price': 38.0    # 需量电价 元/kW·月
    })

    # 时段配置
    time_periods: Dict[str, List[tuple]] = field(default_factory=lambda: {
        'sharp': [(10, 12), (19, 21)],    # 尖峰时段 (夏季)
        'peak': [(8, 10), (12, 14), (17, 19), (21, 23)],   # 峰时时段
        'valley': [(0, 7)],               # 谷时时段
        'flat': [(7, 8), (14, 17), (23, 24)]  # 平时时段
    })

    # 分析时间范围
    analysis_start: Optional[datetime] = None
    analysis_end: Optional[datetime] = None

    # 额外参数
    extra_params: Dict[str, Any] = field(default_factory=dict)

    # ==================== 辅助方法 ====================

    def get_meter_point_by_id(self, meter_point_id: int) -> Optional[MeterPointData]:
        """根据ID获取计量点"""
        for mp in self.meter_points:
            if mp.meter_point_id == meter_point_id:
                return mp
        return None

    def get_devices_by_meter_point(self, meter_point_id: int) -> List[DeviceData]:
        """获取某计量点下的所有设备"""
        return [d for d in self.device_data if d.meter_point_id == meter_point_id]

    def get_shiftable_devices(self) -> List[DeviceShiftInfo]:
        """获取所有可转移负荷的设备"""
        return [d for d in self.device_shift_info if d.is_shiftable and not d.is_critical]

    def get_demand_history_for_meter(self, meter_point_id: int) -> List[DemandHistoryData]:
        """获取某计量点的需量历史"""
        return self.demand_history.get(meter_point_id, [])

    def get_power_curve_for_period(
        self,
        start_time: datetime,
        end_time: datetime,
        meter_point_id: Optional[int] = None,
        device_id: Optional[int] = None
    ) -> List[PowerCurvePoint]:
        """获取指定时间段的功率曲线"""
        result = []
        for point in self.power_curve_data:
            if start_time <= point.timestamp <= end_time:
                if meter_point_id is not None and point.meter_point_id != meter_point_id:
                    continue
                if device_id is not None and point.device_id != device_id:
                    continue
                result.append(point)
        return result

    def calculate_peak_valley_ratio(self, meter_point_id: Optional[int] = None) -> Dict[str, float]:
        """计算峰谷比例"""
        if meter_point_id:
            energy_list = self.device_energy_data.get(meter_point_id, self.energy_data)
        else:
            energy_list = self.energy_data

        if not energy_list:
            return {'peak': 0, 'flat': 0, 'valley': 0, 'sharp': 0}

        total_peak = sum(e.peak_energy for e in energy_list)
        total_flat = sum(e.flat_energy for e in energy_list)
        total_valley = sum(e.valley_energy for e in energy_list)
        total_sharp = sum(e.sharp_energy for e in energy_list)
        total = total_peak + total_flat + total_valley + total_sharp

        if total == 0:
            return {'peak': 0, 'flat': 0, 'valley': 0, 'sharp': 0}

        return {
            'peak': total_peak / total,
            'flat': total_flat / total,
            'valley': total_valley / total,
            'sharp': total_sharp / total
        }


@dataclass
class SuggestionResult:
    """
    建议结果 - 插件分析输出
    Suggestion Result - Plugin analysis output
    """
    # 建议类型
    suggestion_type: SuggestionType

    # 优先级
    priority: PluginPriority

    # 建议标题
    title: str

    # 建议描述
    description: str

    # 详细内容
    detail: str

    # 预计节能量 kWh/年
    estimated_saving: float

    # 预计节省金额 元/年
    estimated_cost_saving: float

    # 实施难度 (1-5, 1最容易)
    implementation_difficulty: int

    # 投资回报期 (月)
    payback_period: Optional[float] = None

    # 相关设备
    related_devices: List[str] = field(default_factory=list)

    # 分析数据
    analysis_data: Dict[str, Any] = field(default_factory=dict)

    # 创建时间
    created_at: datetime = field(default_factory=datetime.now)

    # 置信度 (0-100)
    confidence: int = 80


@dataclass
class PluginConfig:
    """
    插件配置
    Plugin Configuration
    """
    # 插件ID
    plugin_id: str

    # 插件名称
    name: str

    # 是否启用
    enabled: bool = True

    # 执行优先级 (数字越小优先级越高)
    execution_order: int = 100

    # 最小分析数据天数
    min_data_days: int = 7

    # 阈值配置
    thresholds: Dict[str, float] = field(default_factory=dict)

    # 额外配置
    extra_config: Dict[str, Any] = field(default_factory=dict)


class AnalysisPlugin(ABC):
    """
    分析插件基类
    Analysis Plugin Base Class

    所有节能分析插件必须继承此类并实现 analyze 方法
    """

    def __init__(self, config: Optional[PluginConfig] = None):
        """初始化插件"""
        self._config = config or self.get_default_config()
        self._logger = logging.getLogger(f"{__name__}.{self.plugin_id}")

    @property
    @abstractmethod
    def plugin_id(self) -> str:
        """插件唯一标识"""
        pass

    @property
    @abstractmethod
    def plugin_name(self) -> str:
        """插件名称"""
        pass

    @property
    @abstractmethod
    def plugin_description(self) -> str:
        """插件描述"""
        pass

    @property
    @abstractmethod
    def suggestion_type(self) -> SuggestionType:
        """建议类型"""
        pass

    @property
    def config(self) -> PluginConfig:
        """获取配置"""
        return self._config

    @config.setter
    def config(self, value: PluginConfig):
        """设置配置"""
        self._config = value

    @abstractmethod
    def get_default_config(self) -> PluginConfig:
        """获取默认配置"""
        pass

    @abstractmethod
    async def analyze(self, context: AnalysisContext) -> List[SuggestionResult]:
        """
        执行分析

        Args:
            context: 分析上下文，包含所有需要的数据

        Returns:
            建议结果列表
        """
        pass

    def validate_context(self, context: AnalysisContext) -> bool:
        """
        验证上下文数据是否满足分析要求

        Args:
            context: 分析上下文

        Returns:
            是否满足要求
        """
        # 检查能耗数据天数
        if len(context.energy_data) < self._config.min_data_days:
            self._logger.warning(
                f"能耗数据不足: 需要 {self._config.min_data_days} 天, "
                f"实际 {len(context.energy_data)} 天"
            )
            return False
        return True

    def create_suggestion(
        self,
        title: str,
        description: str,
        detail: str,
        estimated_saving: float,
        estimated_cost_saving: float,
        implementation_difficulty: int,
        priority: PluginPriority = PluginPriority.MEDIUM,
        payback_period: Optional[float] = None,
        related_devices: Optional[List[str]] = None,
        analysis_data: Optional[Dict[str, Any]] = None,
        confidence: int = 80
    ) -> SuggestionResult:
        """
        创建建议结果的便捷方法

        Args:
            title: 建议标题
            description: 建议描述
            detail: 详细内容
            estimated_saving: 预计节能量 kWh/年
            estimated_cost_saving: 预计节省金额 元/年
            implementation_difficulty: 实施难度 (1-5)
            priority: 优先级
            payback_period: 投资回报期 (月)
            related_devices: 相关设备列表
            analysis_data: 分析数据
            confidence: 置信度

        Returns:
            SuggestionResult 实例
        """
        return SuggestionResult(
            suggestion_type=self.suggestion_type,
            priority=priority,
            title=title,
            description=description,
            detail=detail,
            estimated_saving=estimated_saving,
            estimated_cost_saving=estimated_cost_saving,
            implementation_difficulty=implementation_difficulty,
            payback_period=payback_period,
            related_devices=related_devices or [],
            analysis_data=analysis_data or {},
            confidence=confidence
        )

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(id={self.plugin_id}, enabled={self._config.enabled})>"
