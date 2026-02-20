"""
深度学习节能优化算法模块

基于专利《基于数据追溯链与深度学习的多模板驱动工业节能方案智能生成方法及系统》

包含三个核心模块：
1. transformer - 时序Transformer可转移负荷识别
2. gnn - 图神经网络多措施协同优化
3. rl - 深度强化学习自适应优化
"""

from .config import MLConfig

__all__ = ["MLConfig"]
