"""
GNN模块 - 基于图神经网络的措施冲突检测
"""

from .model import MeasureEmbedding, RelationalGraphConv, ConflictGNN
from .graph_builder import MeasureGraphBuilder

__all__ = ["MeasureEmbedding", "RelationalGraphConv", "ConflictGNN", "MeasureGraphBuilder"]
