# 节能分析插件系统
# Energy Saving Analysis Plugin System

from .base import (
    AnalysisPlugin,
    AnalysisContext,
    SuggestionResult,
    PluginConfig,
    PluginPriority,
    SuggestionType,
    EnergyData,
    PowerData,
    BillData,
    DeviceData,
    EnvironmentData
)
from .manager import PluginManager, plugin_manager
from .registry import register_all_plugins

# 具体插件
from .load_shifting import LoadShiftingPlugin
from .demand_optimization import DemandOptimizationPlugin
from .power_factor import PowerFactorPlugin
from .peak_valley import PeakValleyOptimizationPlugin
from .pue_optimization import PUEOptimizationPlugin
from .equipment_efficiency import EquipmentEfficiencyPlugin

__all__ = [
    # 基础类
    'AnalysisPlugin',
    'AnalysisContext',
    'SuggestionResult',
    'PluginConfig',
    'PluginPriority',
    'SuggestionType',
    'EnergyData',
    'PowerData',
    'BillData',
    'DeviceData',
    'EnvironmentData',
    # 管理器
    'PluginManager',
    'plugin_manager',
    'register_all_plugins',
    # 插件
    'LoadShiftingPlugin',
    'DemandOptimizationPlugin',
    'PowerFactorPlugin',
    'PeakValleyOptimizationPlugin',
    'PUEOptimizationPlugin',
    'EquipmentEfficiencyPlugin',
]
