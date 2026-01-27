"""
数据模型
"""
from .user import User, RolePermission, UserLoginHistory
from .device import Device
from .point import Point, PointRealtime, PointGroup, PointGroupMember
from .alarm import AlarmThreshold, Alarm, AlarmRule, AlarmShield, AlarmDailyStats
from .history import PointHistory, PointHistoryArchive, PointChangeLog
from .log import OperationLog, SystemLog, CommunicationLog
from .report import ReportTemplate, ReportRecord
from .config import SystemConfig, Dictionary, License
from .energy import (
    PowerDevice, EnergyHourly, EnergyDaily, EnergyMonthly,
    ElectricityPricing, PricingConfig, EnergySuggestion, PUEHistory,
    EnergyOpportunity, OpportunityMeasure,
    ExecutionPlan, ExecutionTask, ExecutionResult,
    # V3.0 电费综合优化
    DispatchableDevice, StorageSystemConfig, PVSystemConfig,
    DispatchSchedule, RealtimeMonitoring, MonthlyStatistics, OptimizationResult
)
from .asset import (
    AssetStatus, AssetType, Cabinet, Asset, AssetLifecycle,
    MaintenanceRecord, AssetInventory, AssetInventoryItem
)
from .capacity import (
    CapacityType, CapacityStatus, SpaceCapacity, PowerCapacity,
    CoolingCapacity, WeightCapacity, CapacityPlan, CapacityHistory
)
from .operation import (
    WorkOrderStatus, WorkOrderType, WorkOrderPriority, InspectionStatus,
    WorkOrder, WorkOrderLog, InspectionPlan, InspectionTask, KnowledgeBase
)
from .floor_map import FloorMap
from .vpp_data import (
    ElectricityBill,
    LoadCurve,
    ElectricityPrice,
    AdjustableLoad,
    VPPConfig,
    TimePeriodType
)

__all__ = [
    # 用户
    "User",
    "RolePermission",
    "UserLoginHistory",
    # 设备
    "Device",
    # 点位
    "Point",
    "PointRealtime",
    "PointGroup",
    "PointGroupMember",
    # 告警
    "AlarmThreshold",
    "Alarm",
    "AlarmRule",
    "AlarmShield",
    "AlarmDailyStats",
    # 历史
    "PointHistory",
    "PointHistoryArchive",
    "PointChangeLog",
    # 日志
    "OperationLog",
    "SystemLog",
    "CommunicationLog",
    # 报表
    "ReportTemplate",
    "ReportRecord",
    # 配置
    "SystemConfig",
    "Dictionary",
    "License",
    # 用电管理
    "PowerDevice",
    "EnergyHourly",
    "EnergyDaily",
    "EnergyMonthly",
    "ElectricityPricing",
    "PricingConfig",
    "EnergySuggestion",
    "PUEHistory",
    # 节能中心
    "EnergyOpportunity",
    "OpportunityMeasure",
    "ExecutionPlan",
    "ExecutionTask",
    "ExecutionResult",
    # V3.0 电费综合优化
    "DispatchableDevice",
    "StorageSystemConfig",
    "PVSystemConfig",
    "DispatchSchedule",
    "RealtimeMonitoring",
    "MonthlyStatistics",
    "OptimizationResult",
    # 资产管理
    "AssetStatus",
    "AssetType",
    "Cabinet",
    "Asset",
    "AssetLifecycle",
    "MaintenanceRecord",
    "AssetInventory",
    "AssetInventoryItem",
    # 容量管理
    "CapacityType",
    "CapacityStatus",
    "SpaceCapacity",
    "PowerCapacity",
    "CoolingCapacity",
    "WeightCapacity",
    "CapacityPlan",
    "CapacityHistory",
    # 运维管理
    "WorkOrderStatus",
    "WorkOrderType",
    "WorkOrderPriority",
    "InspectionStatus",
    "WorkOrder",
    "WorkOrderLog",
    "InspectionPlan",
    "InspectionTask",
    "KnowledgeBase",
    # 楼层图
    "FloorMap",
    # VPP虚拟电厂
    "ElectricityBill",
    "LoadCurve",
    "ElectricityPrice",
    "AdjustableLoad",
    "VPPConfig",
    "TimePeriodType"
]
