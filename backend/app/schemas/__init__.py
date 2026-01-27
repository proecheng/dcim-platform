"""
Pydantic Schemas
"""
from .common import PageParams, PageResponse, ResponseModel, ErrorResponse, SuccessResponse
from .user import (
    UserCreate, UserUpdate, UserInfo, UserListResponse, UserLoginHistoryResponse,
    Token, TokenData, LoginRequest, PasswordChange,
    # 向后兼容
    UserBase, UserResponse
)
from .device import (
    DeviceCreate, DeviceUpdate, DeviceInfo, DeviceTree, DeviceStatusSummary
)
from .point import (
    PointCreate, PointUpdate, PointInfo, PointTypesSummary,
    PointGroupCreate, PointGroupInfo,
    PointRealtimeResponse, PointHistoryResponse, PointTypeStats, RealtimeSummary,
    # 向后兼容
    PointBase, PointResponse
)
from .realtime import RealtimeData, RealtimeSummary as RealtimeSummaryV2, ControlCommand
from .alarm import (
    AlarmInfo, AlarmAcknowledge, AlarmResolve, AlarmCount, AlarmStatistics, AlarmTrend,
    AlarmThresholdCreate, AlarmThresholdUpdate, AlarmThresholdResponse,
    # 向后兼容
    AlarmThresholdBase, AlarmResponse, AlarmStats
)
from .threshold import ThresholdCreate, ThresholdUpdate, ThresholdInfo, ThresholdBatchCreate
from .history import HistoryQuery, HistoryData, TrendData, HistoryStatistics, CompareQuery
from .report import (
    ReportTemplateCreate, ReportTemplateUpdate, ReportTemplateInfo,
    ReportRecordInfo, ReportGenerate
)
from .log import OperationLogInfo, SystemLogInfo, CommunicationLogInfo
from .config import SystemConfigInfo, SystemConfigUpdate, DictionaryInfo, LicenseInfo, LicenseActivate
from .energy import (
    # 用电设备
    PowerDeviceCreate, PowerDeviceUpdate, PowerDeviceResponse, PowerDeviceTree,
    # 实时电力
    RealtimePowerData, RealtimePowerSummary,
    # PUE
    PUEData, PUEHistoryItem, PUETrend,
    # 能耗统计
    EnergyHourlyData, EnergyDailyData, EnergyMonthlyData,
    EnergyStatQuery, EnergyStat, EnergyTrendItem, EnergyTrend, EnergyComparison,
    # 电价
    ElectricityPricingCreate, ElectricityPricingUpdate, ElectricityPricingResponse,
    # 节能建议
    EnergySuggestionCreate, EnergySuggestionResponse,
    AcceptSuggestion, CompleteSuggestion, RejectSuggestion, SavingPotential,
    # 配电图
    DistributionNode, DistributionDiagram
)
from .proposal_schema import (
    # 方案相关
    ProposalCreate, ProposalResponse, MeasureAcceptRequest,
    # 措施响应
    MeasureResponse,
    # 监控相关
    ExecutionLogResponse, MeasureMonitoringResponse, ProposalMonitoringResponse
)

__all__ = [
    # Common
    "PageParams", "PageResponse", "ResponseModel", "ErrorResponse", "SuccessResponse",
    # User
    "UserCreate", "UserUpdate", "UserInfo", "UserListResponse", "UserLoginHistoryResponse",
    "Token", "TokenData", "LoginRequest", "PasswordChange",
    "UserBase", "UserResponse",
    # Device
    "DeviceCreate", "DeviceUpdate", "DeviceInfo", "DeviceTree", "DeviceStatusSummary",
    # Point
    "PointCreate", "PointUpdate", "PointInfo", "PointTypesSummary",
    "PointGroupCreate", "PointGroupInfo",
    "PointRealtimeResponse", "PointHistoryResponse", "PointTypeStats", "RealtimeSummary",
    "PointBase", "PointResponse",
    # Realtime
    "RealtimeData", "RealtimeSummaryV2", "ControlCommand",
    # Alarm
    "AlarmInfo", "AlarmAcknowledge", "AlarmResolve", "AlarmCount", "AlarmStatistics", "AlarmTrend",
    "AlarmThresholdCreate", "AlarmThresholdUpdate", "AlarmThresholdResponse",
    "AlarmThresholdBase", "AlarmResponse", "AlarmStats",
    # Threshold
    "ThresholdCreate", "ThresholdUpdate", "ThresholdInfo", "ThresholdBatchCreate",
    # History
    "HistoryQuery", "HistoryData", "TrendData", "HistoryStatistics", "CompareQuery",
    # Report
    "ReportTemplateCreate", "ReportTemplateUpdate", "ReportTemplateInfo",
    "ReportRecordInfo", "ReportGenerate",
    # Log
    "OperationLogInfo", "SystemLogInfo", "CommunicationLogInfo",
    # Config
    "SystemConfigInfo", "SystemConfigUpdate", "DictionaryInfo", "LicenseInfo", "LicenseActivate",
    # Energy
    "PowerDeviceCreate", "PowerDeviceUpdate", "PowerDeviceResponse", "PowerDeviceTree",
    "RealtimePowerData", "RealtimePowerSummary",
    "PUEData", "PUEHistoryItem", "PUETrend",
    "EnergyHourlyData", "EnergyDailyData", "EnergyMonthlyData",
    "EnergyStatQuery", "EnergyStat", "EnergyTrendItem", "EnergyTrend", "EnergyComparison",
    "ElectricityPricingCreate", "ElectricityPricingUpdate", "ElectricityPricingResponse",
    "EnergySuggestionCreate", "EnergySuggestionResponse",
    "AcceptSuggestion", "CompleteSuggestion", "RejectSuggestion", "SavingPotential",
    "DistributionNode", "DistributionDiagram",
    # Proposal
    "ProposalCreate", "ProposalResponse", "MeasureAcceptRequest",
    "MeasureResponse",
    "ExecutionLogResponse", "MeasureMonitoringResponse", "ProposalMonitoringResponse"
]
