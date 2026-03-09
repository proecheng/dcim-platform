"""
数据模型
"""

from .enums import DataSourceType, PricingPeriodType
from .user import User, RolePermission, UserLoginHistory, UserSession, UserSite, PasswordHistory
from .device import Device
from .point import Point, PointRealtime, PointGroup, PointGroupMember
from .alarm import AlarmThreshold, Alarm, AlarmRule, AlarmShield, AlarmDailyStats, AlarmEscalation
from .history import PointHistory, PointHistoryArchive, PointChangeLog
from .log import OperationLog, SystemLog, CommunicationLog
from .report import ReportTemplate, ReportRecord, ReportSchedule, DeviceHealthScore
from .config import SystemConfig, Dictionary, License
from .energy import (
    PowerDevice,
    EnergyHourly,
    EnergyDaily,
    EnergyMonthly,
    ElectricityPricing,
    PricingConfig,
    PricingScheme,
    EnergySuggestion,
    PUEHistory,
    EnergyOpportunity,
    OpportunityMeasure,
    ExecutionPlan,
    ExecutionTask,
    ExecutionResult,
    # V3.0 电费综合优化
    DispatchableDevice,
    StorageSystemConfig,
    PVSystemConfig,
    DispatchSchedule,
    RealtimeMonitoring,
    MonthlyStatistics,
    OptimizationResult,
    # V3.2 效果监测 (专利 S4)
    MeasureBaseline,
    MonitoringRecord,
    EffectReport,
    MonitoringSession,
    # V3.2 RL 自适应优化 (专利 S5)
    RLOptimizationHistory,
    RLTrainingLog,
    RLModelState,
)
from .asset import (
    AssetStatus,
    AssetType,
    Cabinet,
    Asset,
    AssetLifecycle,
    MaintenanceRecord,
    AssetInventory,
    AssetInventoryItem,
)
from .capacity import (
    CapacityType,
    CapacityStatus,
    SpaceCapacity,
    PowerCapacity,
    CoolingCapacity,
    WeightCapacity,
    CapacityPlan,
    CapacityHistory,
)
from .operation import (
    WorkOrderStatus,
    WorkOrderType,
    WorkOrderPriority,
    InspectionStatus,
    ApprovalStatus,
    WorkOrder,
    WorkOrderLog,
    InspectionPlan,
    InspectionTask,
    KnowledgeBase,
    AlarmWorkOrderRule,
    WorkOrderApproval,
)
from .floor_map import FloorMap
from .power import UPSDevice, BatteryGroup
from .cooling import CoolingUnit, CoolingGroup, ColdAisle
from .vpp_data import ElectricityBill, LoadCurve, ElectricityPrice, AdjustableLoad, VPPConfig, TimePeriodType
from .trace import (
    DataSourceMapping,
    TraceRecord,
    TraceTree,
    TemplateParameter,
    MappingType,
    AggregationType,
    MLModelType,
)
from .gateway import Gateway, DataSource, DataSourcePoint, MqttAclRule
from .spatial import Site, Floor, Room, Row, LayoutTemplate
from .topology_config import PowerPhaseMapping, CoolingZone, CoolingZoneCabinet, CoolingZoneUnit, CabinetTemperatureSensor, CabinetITLoad
from .linkage import LinkagePolicy, LinkageAction, LinkageExecution, LinkageLog, LinkageRecovery, LinkageRecoveryLog
from .diagnosis import DiagnosisRule, DiagnosisResult, DiagnosisSession, DiagnosisAuditLog, DiagnosisAnnotation, BatterySOHRecord, SOHPointUnavailableTracking, SystemReport, DiagnosisImprovementRule, ProbabilityAdjustmentLog, AuditLog, TimeWindowAdjustmentLog
from .fault_tree import FaultTree, FaultTreeNode, FaultTreeEdge, FaultTreeDeviceMapping, FaultTreeVersion
from .ab_test_config import ABTestConfig, ABTestDeviceAssignment, ABTestArchive
from .command import CommandApproval, CommandAuditLog
from .drift import DriftDetectionResult
from .video import NVR, Camera, CameraPreset, VideoEvent
from .load_shift import (
    ShiftPlan,
    ShiftExecution,
    ShiftConstraint,
    ShiftOpportunity,
    ShiftAnalysisRecord,
    CoolingLinkageConfig,
    CoolingLinkageRecord,
    DeviceLifespanImpact,
)

__all__ = [
    # 枚举
    "DataSourceType",
    "PricingPeriodType",
    # 用户
    "User",
    "RolePermission",
    "UserLoginHistory",
    "UserSession",
    "UserSite",
    "PasswordHistory",
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
    "AlarmEscalation",
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
    "ReportSchedule",
    "DeviceHealthScore",
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
    "PricingScheme",
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
    "AlarmWorkOrderRule",
    "ApprovalStatus",
    "WorkOrderApproval",
    # 楼层图
    "FloorMap",
    # 供配电管理
    "UPSDevice",
    "BatteryGroup",
    # 制冷系统
    "CoolingUnit",
    "CoolingGroup",
    "ColdAisle",
    # VPP虚拟电厂
    "ElectricityBill",
    "LoadCurve",
    "ElectricityPrice",
    "AdjustableLoad",
    "VPPConfig",
    "TimePeriodType",
    # V3.1 数据追溯链
    "DataSourceMapping",
    "TraceRecord",
    "TraceTree",
    "TemplateParameter",
    "MappingType",
    "AggregationType",
    "MLModelType",
    # V3.2 效果监测 (专利 S4)
    "MeasureBaseline",
    "MonitoringRecord",
    "EffectReport",
    "MonitoringSession",
    # V3.2 RL 自适应优化 (专利 S5)
    "RLOptimizationHistory",
    "RLTrainingLog",
    "RLModelState",
    # 网关和数据源
    "Gateway",
    "DataSource",
    "DataSourcePoint",
    "MqttAclRule",
    # 空间拓扑
    "Site",
    "Floor",
    "Room",
    "Row",
    "LayoutTemplate",
    # 拓扑配置
    "PowerPhaseMapping",
    "CoolingZone",
    "CoolingZoneCabinet",
    "CoolingZoneUnit",
    "CabinetTemperatureSensor",
    "CabinetITLoad",
    # 联动引擎
    "LinkagePolicy",
    "LinkageAction",
    "LinkageExecution",
    "LinkageLog",
    "LinkageRecovery",
    "LinkageRecoveryLog",
    # 智能诊断
    "DiagnosisRule",
    "DiagnosisResult",
    "DiagnosisSession",
    "DiagnosisAuditLog",
    "DiagnosisAnnotation",
    "BatterySOHRecord",
    "SOHPointUnavailableTracking",
    "SystemReport",
    "DiagnosisImprovementRule",
    "ProbabilityAdjustmentLog",
    "AuditLog",
    "TimeWindowAdjustmentLog",
    # 故障树
    "FaultTree",
    "FaultTreeNode",
    "FaultTreeEdge",
    "FaultTreeDeviceMapping",
    "FaultTreeVersion",
    # A/B 测试
    "ABTestConfig",
    "ABTestDeviceAssignment",
    "ABTestArchive",
    # 控制命令分级确认
    "CommandApproval",
    "CommandAuditLog",
    # 传感器漂移检测
    "DriftDetectionResult",
    # 视频监控
    "NVR",
    "Camera",
    "CameraPreset",
    "VideoEvent",
    # 负荷转移
    "ShiftPlan",
    "ShiftExecution",
    "ShiftConstraint",
    "ShiftOpportunity",
    "ShiftAnalysisRecord",
    "CoolingLinkageConfig",
    "CoolingLinkageRecord",
    "DeviceLifespanImpact",
]
