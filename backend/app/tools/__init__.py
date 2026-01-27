"""
工具模块
Tools Module

包含:
- demo_data_generator: 展示数据生成器
- realtime_simulator: 实时数据模拟器
"""

from .demo_data_generator import DemoDataGenerator, DATACENTER_CONFIG
from .realtime_simulator import RealtimeSimulator

__all__ = ['DemoDataGenerator', 'RealtimeSimulator', 'DATACENTER_CONFIG']
