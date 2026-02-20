"""
数据追溯链服务
实现专利 S1 - 数据追溯链的创建、管理和查询

功能:
1. 生成全局唯一追溯标识
2. 创建三层映射的追溯记录
3. 构建追溯树结构
4. 支持逐层展开查看完整计算路径
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any, Union
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.trace import DataSourceMapping, TraceRecord, TraceTree, TemplateParameter, MappingType, AggregationType


class DataTraceService:
    """数据追溯链服务"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._trace_cache: Dict[str, TraceRecord] = {}

    # ==================== 追溯ID生成 ====================

    @staticmethod
    def generate_trace_id(prefix: str = "TR") -> str:
        """
        生成全局唯一追溯标识

        格式: TR-YYYYMMDD-XXXXXX
        """
        date_str = datetime.now().strftime("%Y%m%d")
        unique_part = uuid.uuid4().hex[:8].upper()
        return f"{prefix}-{date_str}-{unique_part}"

    # ==================== 追溯记录创建 ====================

    async def create_direct_trace(
        self,
        param_code: str,
        param_name: str,
        source_table: str,
        source_field: str,
        value: Union[Decimal, float, int],
        value_unit: str = "",
        filter_condition: str = None,
        query_sql: str = None,
        query_params: Dict = None,
        proposal_id: int = None,
        measure_id: int = None,
        parent_trace_id: str = None,
    ) -> TraceRecord:
        """
        创建第一层直接映射追溯记录

        直接映射: 占位符参数 → 数据库单一字段
        """
        trace_id = self.generate_trace_id()

        trace = TraceRecord(
            trace_id=trace_id,
            proposal_id=proposal_id,
            measure_id=measure_id,
            param_code=param_code,
            param_name=param_name,
            mapping_type=MappingType.DIRECT.value,
            source_table=source_table,
            source_field=source_field,
            filter_condition=filter_condition,
            raw_value=Decimal(str(value)) if value is not None else None,
            formatted_value=self._format_value(value, value_unit),
            value_unit=value_unit,
            parent_trace_id=parent_trace_id,
            depth=0 if parent_trace_id is None else 1,
            query_sql=query_sql,
            query_params=query_params,
            calculated_at=datetime.now(),
        )

        self.db.add(trace)
        self._trace_cache[trace_id] = trace
        return trace

    async def create_aggregate_trace(
        self,
        param_code: str,
        param_name: str,
        source_table: str,
        source_field: str,
        aggregation_type: AggregationType,
        value: Union[Decimal, float, int],
        value_unit: str = "",
        filter_condition: str = None,
        aggregation_params: Dict = None,
        time_range_start: datetime = None,
        time_range_end: datetime = None,
        query_sql: str = None,
        query_params: Dict = None,
        proposal_id: int = None,
        measure_id: int = None,
        parent_trace_id: str = None,
    ) -> TraceRecord:
        """
        创建第二层聚合映射追溯记录

        聚合映射: 占位符参数 → 聚合函数运算结果 (SUM, AVG, MAX, MIN, PERCENTILE等)
        """
        trace_id = self.generate_trace_id()

        trace = TraceRecord(
            trace_id=trace_id,
            proposal_id=proposal_id,
            measure_id=measure_id,
            param_code=param_code,
            param_name=param_name,
            mapping_type=MappingType.AGGREGATE.value,
            source_table=source_table,
            source_field=source_field,
            filter_condition=filter_condition,
            aggregation_type=aggregation_type.value
            if isinstance(aggregation_type, AggregationType)
            else aggregation_type,
            aggregation_params=aggregation_params,
            time_range_start=time_range_start,
            time_range_end=time_range_end,
            raw_value=Decimal(str(value)) if value is not None else None,
            formatted_value=self._format_value(value, value_unit),
            value_unit=value_unit,
            parent_trace_id=parent_trace_id,
            depth=0 if parent_trace_id is None else 1,
            query_sql=query_sql,
            query_params=query_params,
            calculated_at=datetime.now(),
        )

        self.db.add(trace)
        self._trace_cache[trace_id] = trace
        return trace

    async def create_composite_trace(
        self,
        param_code: str,
        param_name: str,
        formula: str,
        formula_display: str,
        child_traces: List[TraceRecord],
        value: Union[Decimal, float, int],
        value_unit: str = "",
        proposal_id: int = None,
        measure_id: int = None,
        parent_trace_id: str = None,
    ) -> TraceRecord:
        """
        创建第三层复合映射追溯记录

        复合映射: 占位符参数 → 多数据源组合运算公式
        递归记录所有子参数的追溯信息，形成追溯树结构
        """
        trace_id = self.generate_trace_id()

        # 获取子追溯ID列表
        child_trace_ids = [t.trace_id for t in child_traces]

        # 计算深度
        max_child_depth = max([t.depth for t in child_traces], default=0)
        depth = max_child_depth + 1 if parent_trace_id is None else max_child_depth + 2

        trace = TraceRecord(
            trace_id=trace_id,
            proposal_id=proposal_id,
            measure_id=measure_id,
            param_code=param_code,
            param_name=param_name,
            mapping_type=MappingType.COMPOSITE.value,
            formula=formula,
            formula_display=formula_display,
            child_trace_ids=child_trace_ids,
            raw_value=Decimal(str(value)) if value is not None else None,
            formatted_value=self._format_value(value, value_unit),
            value_unit=value_unit,
            parent_trace_id=parent_trace_id,
            depth=depth,
            calculated_at=datetime.now(),
        )

        self.db.add(trace)
        self._trace_cache[trace_id] = trace

        # 更新子追溯的父ID
        for child in child_traces:
            if child.parent_trace_id is None:
                child.parent_trace_id = trace_id

        return trace

    # ==================== 追溯树构建 ====================

    async def build_trace_tree(
        self, root_trace: TraceRecord, proposal_id: int = None, measure_id: int = None
    ) -> List[TraceTree]:
        """
        构建追溯树索引

        用于快速查询追溯树结构，支持从任意节点展开查看完整计算路径
        """
        tree_nodes = []
        root_trace_id = root_trace.trace_id

        async def build_node(trace: TraceRecord, path: str, depth: int):
            node = TraceTree(
                root_trace_id=root_trace_id,
                node_trace_id=trace.trace_id,
                path=path,
                depth=depth,
                proposal_id=proposal_id,
                measure_id=measure_id,
            )
            tree_nodes.append(node)
            self.db.add(node)

            # 递归处理子节点
            if trace.child_trace_ids:
                for child_id in trace.child_trace_ids:
                    child_trace = self._trace_cache.get(child_id)
                    if child_trace:
                        child_path = f"{path}/{child_id}"
                        await build_node(child_trace, child_path, depth + 1)

        await build_node(root_trace, root_trace_id, 0)
        return tree_nodes

    # ==================== 追溯查询 ====================

    async def get_trace_by_id(self, trace_id: str) -> Optional[TraceRecord]:
        """根据追溯ID获取追溯记录"""
        # 先查缓存
        if trace_id in self._trace_cache:
            return self._trace_cache[trace_id]

        # 查数据库
        result = await self.db.execute(select(TraceRecord).where(TraceRecord.trace_id == trace_id))
        trace = result.scalar_one_or_none()
        if trace:
            self._trace_cache[trace_id] = trace
        return trace

    async def get_trace_tree(self, trace_id: str) -> Dict[str, Any]:
        """
        获取完整追溯树

        返回树状结构，支持前端逐层展开
        """
        trace = await self.get_trace_by_id(trace_id)
        if not trace:
            return None

        return await self._build_tree_dict(trace)

    async def _build_tree_dict(self, trace: TraceRecord) -> Dict[str, Any]:
        """递归构建追溯树字典"""
        node = {
            "trace_id": trace.trace_id,
            "param_code": trace.param_code,
            "param_name": trace.param_name,
            "mapping_type": trace.mapping_type,
            "value": float(trace.raw_value) if trace.raw_value else None,
            "formatted_value": trace.formatted_value,
            "unit": trace.value_unit,
            "depth": trace.depth,
            "calculated_at": trace.calculated_at.isoformat() if trace.calculated_at else None,
        }

        # 根据映射类型添加特定信息
        if trace.mapping_type == MappingType.DIRECT.value:
            node["source"] = {
                "table": trace.source_table,
                "field": trace.source_field,
                "filter": trace.filter_condition,
            }
        elif trace.mapping_type == MappingType.AGGREGATE.value:
            node["source"] = {
                "table": trace.source_table,
                "field": trace.source_field,
                "aggregation": trace.aggregation_type,
                "params": trace.aggregation_params,
                "filter": trace.filter_condition,
                "time_range": {
                    "start": trace.time_range_start.isoformat() if trace.time_range_start else None,
                    "end": trace.time_range_end.isoformat() if trace.time_range_end else None,
                },
            }
            node["query_sql"] = trace.query_sql
        elif trace.mapping_type == MappingType.COMPOSITE.value:
            node["formula"] = trace.formula
            node["formula_display"] = trace.formula_display

            # 递归获取子节点
            if trace.child_trace_ids:
                node["children"] = []
                for child_id in trace.child_trace_ids:
                    child_trace = await self.get_trace_by_id(child_id)
                    if child_trace:
                        child_node = await self._build_tree_dict(child_trace)
                        node["children"].append(child_node)

        return node

    async def get_traces_by_proposal(self, proposal_id: int) -> List[TraceRecord]:
        """获取方案的所有追溯记录"""
        result = await self.db.execute(select(TraceRecord).where(TraceRecord.proposal_id == proposal_id))
        return result.scalars().all()

    async def get_traces_by_measure(self, measure_id: int) -> List[TraceRecord]:
        """获取措施的所有追溯记录"""
        result = await self.db.execute(select(TraceRecord).where(TraceRecord.measure_id == measure_id))
        return result.scalars().all()

    # ==================== 数据源映射管理 ====================

    async def get_mapping_by_code(self, param_code: str) -> Optional[DataSourceMapping]:
        """根据参数编码获取映射配置"""
        result = await self.db.execute(
            select(DataSourceMapping).where(
                and_(DataSourceMapping.param_code == param_code, DataSourceMapping.is_enabled == True)
            )
        )
        return result.scalar_one_or_none()

    async def get_template_parameters(self, template_id: str) -> List[TemplateParameter]:
        """获取模板的所有参数配置"""
        result = await self.db.execute(
            select(TemplateParameter)
            .where(and_(TemplateParameter.template_id == template_id, TemplateParameter.is_enabled == True))
            .order_by(TemplateParameter.sort_order)
        )
        return result.scalars().all()

    # ==================== 辅助方法 ====================

    @staticmethod
    def _format_value(value: Union[Decimal, float, int, None], unit: str = "") -> str:
        """格式化数值显示"""
        if value is None:
            return "N/A"

        # 转换为float进行格式化
        v = float(value)

        # 根据大小选择格式
        if abs(v) >= 10000:
            formatted = f"{v:,.0f}"
        elif abs(v) >= 100:
            formatted = f"{v:,.2f}"
        elif abs(v) >= 1:
            formatted = f"{v:.2f}"
        else:
            formatted = f"{v:.4f}"

        if unit:
            formatted = f"{formatted} {unit}"

        return formatted

    async def commit(self):
        """提交所有追溯记录"""
        await self.db.commit()
        self._trace_cache.clear()


class TracedValue:
    """
    带追溯信息的值

    封装计算结果及其追溯记录，用于公式计算器返回
    """

    def __init__(self, value: Union[Decimal, float, int], trace: TraceRecord, unit: str = ""):
        self.value = Decimal(str(value)) if not isinstance(value, Decimal) else value
        self.trace = trace
        self.unit = unit

    def __float__(self):
        return float(self.value)

    def __repr__(self):
        return f"TracedValue({self.value}, trace_id={self.trace.trace_id})"

    @property
    def trace_id(self) -> str:
        return self.trace.trace_id

    def to_dict(self) -> Dict[str, Any]:
        return {"value": float(self.value), "trace_id": self.trace.trace_id, "unit": self.unit}
