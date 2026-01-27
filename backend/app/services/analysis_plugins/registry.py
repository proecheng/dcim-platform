"""
插件注册模块
Plugin Registration Module

注册所有分析插件
Registers all analysis plugins
"""

from .manager import plugin_manager
from .load_shifting import LoadShiftingPlugin
from .demand_optimization import DemandOptimizationPlugin
from .power_factor import PowerFactorPlugin
from .peak_valley import PeakValleyOptimizationPlugin
from .pue_optimization import PUEOptimizationPlugin
from .equipment_efficiency import EquipmentEfficiencyPlugin


def register_all_plugins():
    """注册所有分析插件"""
    plugins = [
        LoadShiftingPlugin(),
        DemandOptimizationPlugin(),
        PowerFactorPlugin(),
        PeakValleyOptimizationPlugin(),
        PUEOptimizationPlugin(),
        EquipmentEfficiencyPlugin(),
    ]

    for plugin in plugins:
        plugin_manager.register_plugin(plugin)

    return plugin_manager


# 导出
__all__ = [
    'plugin_manager',
    'register_all_plugins',
    'LoadShiftingPlugin',
    'DemandOptimizationPlugin',
    'PowerFactorPlugin',
    'PeakValleyOptimizationPlugin',
    'PUEOptimizationPlugin',
    'EquipmentEfficiencyPlugin',
]
