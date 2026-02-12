"""
数据追溯链模型
实现专利 S1 - 多层数据源映射表和数据追溯链

三层映射结构:
- 第一层 直接映射层: 占位符参数 → 数据库单一字段
- 第二层 聚合映射层: 占位符参数 → 聚合函数运算结果
- 第三层 复合映射层: 占位符参数 → 多数据源组合运算公式

V3.2: 增加 ML 预测追溯支持 (专利 S2)
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, Float, Text, DateTime, JSON, ForeignKey, Numeric, Enum
from sqlalchemy.orm import relationship
import enum

from ..core.database import Base


class MappingType(str, enum.Enum):
    """映射类型枚举"""
    DIRECT = "direct"           # 直接映射 - 单一字段
    AGGREGATE = "aggregate"     # 聚合映射 - 聚合函数
    COMPOSITE = "composite"     # 复合映射 - 多源组合
    ML_PREDICTION = "ml_prediction"  # ML预测映射 - 深度学习模型输出


class AggregationType(str, enum.Enum):
    """聚合函数类型"""
    SUM = "sum"                 # 求和
    AVG = "avg"                 # 平均
    MAX = "max"                 # 最大值
    MIN = "min"                 # 最小值
    COUNT = "count"             # 计数
    PERCENTILE = "percentile"   # 分位数
    STDDEV = "stddev"           # 标准差


class MLModelType(str, enum.Enum):
    """ML模型类型枚举"""
    TRANSFORMER = "transformer"  # 时序Transformer (S2-TF)
    GNN = "gnn"                  # 图神经网络 (S2-GNN)
    RL = "rl"                    # 深度强化学习 (S5)


class DataSourceMapping(Base):
    """
    数据源映射配置表

    定义占位符参数与数据源的映射关系，支持三层映射结构
    """
    __tablename__ = "data_source_mappings"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # 参数标识
    param_code = Column(String(100), unique=True, nullable=False, comment="参数编码 如 annual_energy")
    param_name = Column(String(200), nullable=False, comment="参数名称 如 年用电量")
    param_unit = Column(String(50), comment="参数单位 如 kWh")

    # 映射类型
    mapping_type = Column(String(20), nullable=False, comment="映射类型: direct/aggregate/composite")

    # ========== 第一层: 直接映射 ==========
    source_table = Column(String(100), comment="源表名称")
    source_field = Column(String(100), comment="源字段名称")

    # ========== 第二层: 聚合映射 ==========
    aggregation_type = Column(String(20), comment="聚合函数: sum/avg/max/min/count/percentile")
    aggregation_params = Column(JSON, comment="聚合参数 如 {percentile: 95}")
    filter_condition = Column(Text, comment="筛选条件 SQL WHERE 子句")
    time_range_type = Column(String(20), comment="时间范围类型: year/month/day/custom")

    # ========== 第三层: 复合映射 ==========
    formula = Column(Text, comment="计算公式 如 {param1} * {param2} / 100")
    child_params = Column(JSON, comment="子参数列表 [param_code1, param_code2]")

    # 元数据
    template_ids = Column(JSON, comment="适用的模板ID列表 [A1, A2]")
    description = Column(Text, comment="参数说明")
    is_enabled = Column(Boolean, default=True, comment="是否启用")

    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")


class TraceRecord(Base):
    """
    追溯记录表

    为每个计算值生成追溯记录，支持树状追溯结构
    记录数据来源、计算公式和中间结果
    """
    __tablename__ = "trace_records"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # 追溯标识
    trace_id = Column(String(50), unique=True, nullable=False, index=True, comment="全局唯一追溯标识")

    # 关联信息
    proposal_id = Column(Integer, ForeignKey("energy_saving_proposals.id"), comment="关联方案ID")
    measure_id = Column(Integer, ForeignKey("proposal_measures.id"), comment="关联措施ID")
    mapping_id = Column(Integer, ForeignKey("data_source_mappings.id"), comment="关联映射配置ID")

    # 参数信息
    param_code = Column(String(100), nullable=False, comment="参数编码")
    param_name = Column(String(200), comment="参数名称")

    # 映射类型
    mapping_type = Column(String(20), nullable=False, comment="映射类型: direct/aggregate/composite")

    # ========== 数据获取元信息 ==========
    source_table = Column(String(100), comment="源表名称")
    source_field = Column(String(100), comment="源字段名称")
    filter_condition = Column(Text, comment="筛选条件")
    aggregation_type = Column(String(20), comment="聚合函数类型")
    aggregation_params = Column(JSON, comment="聚合参数")
    time_range_start = Column(DateTime, comment="时间范围开始")
    time_range_end = Column(DateTime, comment="时间范围结束")

    # ========== 计算信息 ==========
    formula = Column(Text, comment="计算公式")
    formula_display = Column(Text, comment="公式展示形式（带具体数值）")

    # ========== 值信息 ==========
    raw_value = Column(Numeric(20, 6), comment="原始值")
    formatted_value = Column(String(100), comment="格式化后的值")
    value_unit = Column(String(50), comment="值单位")

    # ========== 树状结构 ==========
    parent_trace_id = Column(String(50), comment="父追溯ID（用于复合计算）")
    child_trace_ids = Column(JSON, comment="子追溯ID列表")
    depth = Column(Integer, default=0, comment="追溯深度 (0=根节点)")

    # ========== 查询重放信息 ==========
    query_sql = Column(Text, comment="实际执行的SQL查询")
    query_params = Column(JSON, comment="查询参数")
    query_execution_time = Column(Float, comment="查询执行时间(ms)")

    # ========== ML 预测信息 (专利 S2) ==========
    ml_model_type = Column(String(20), comment="ML模型类型: transformer/gnn/rl")
    ml_model_version = Column(String(50), comment="模型版本号")
    ml_confidence = Column(Float, comment="预测置信度 0-1")
    ml_input_features = Column(JSON, comment="模型输入特征摘要")
    ml_output_raw = Column(JSON, comment="模型原始输出")

    # 时间戳
    calculated_at = Column(DateTime, default=datetime.now, comment="计算时间")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")


class TraceTree(Base):
    """
    追溯树索引表

    用于快速查询追溯树结构，支持从任意节点展开查看完整计算路径
    """
    __tablename__ = "trace_trees"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # 树根信息
    root_trace_id = Column(String(50), nullable=False, index=True, comment="根追溯ID")

    # 节点信息
    node_trace_id = Column(String(50), nullable=False, index=True, comment="节点追溯ID")

    # 路径信息
    path = Column(String(500), comment="从根到此节点的路径 如 root/child1/child2")
    depth = Column(Integer, default=0, comment="节点深度")

    # 关联的方案/措施
    proposal_id = Column(Integer, ForeignKey("energy_saving_proposals.id"), comment="关联方案ID")
    measure_id = Column(Integer, ForeignKey("proposal_measures.id"), comment="关联措施ID")

    created_at = Column(DateTime, default=datetime.now, comment="创建时间")


class TemplateParameter(Base):
    """
    模板参数配置表

    定义每个模板使用的占位符参数及其映射关系
    """
    __tablename__ = "template_parameters"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # 模板信息
    template_id = Column(String(50), nullable=False, comment="模板ID 如 A1")
    template_name = Column(String(200), comment="模板名称")

    # 参数信息
    param_code = Column(String(100), nullable=False, comment="参数编码")
    param_name = Column(String(200), nullable=False, comment="参数显示名称")
    param_description = Column(Text, comment="参数说明")

    # 映射配置
    mapping_id = Column(Integer, ForeignKey("data_source_mappings.id"), comment="关联映射配置ID")

    # 默认值（当无法从数据源获取时使用）
    default_value = Column(Numeric(20, 6), comment="默认值")

    # 验证规则
    min_value = Column(Numeric(20, 6), comment="最小值")
    max_value = Column(Numeric(20, 6), comment="最大值")
    is_required = Column(Boolean, default=True, comment="是否必需")

    # 排序
    sort_order = Column(Integer, default=0, comment="排序顺序")

    is_enabled = Column(Boolean, default=True, comment="是否启用")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    # 关系
    mapping = relationship("DataSourceMapping", foreign_keys=[mapping_id])
