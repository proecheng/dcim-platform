"""
节能方案相关的 Pydantic 模型
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal


# ========== 措施相关模型 ==========

class MeasureResponse(BaseModel):
    """措施响应模型"""
    id: int
    measure_code: str = Field(..., description="措施编号")
    regulation_object: str = Field(..., description="调节对象")
    regulation_description: Optional[str] = Field(None, description="调节说明")
    current_state: Optional[Dict[str, Any]] = Field(None, description="当前状态")
    target_state: Optional[Dict[str, Any]] = Field(None, description="目标状态")
    calculation_formula: Optional[str] = Field(None, description="计算公式")
    calculation_basis: Optional[str] = Field(None, description="计算依据")
    annual_benefit: Optional[Decimal] = Field(None, description="年收益 万元/年")
    investment: Optional[Decimal] = Field(0, description="投资 万元")
    is_selected: bool = Field(False, description="是否选择")
    execution_status: str = Field("pending", description="执行状态")
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True  # Pydantic v2


# ========== 方案相关模型 ==========

class ProposalResponse(BaseModel):
    """方案响应模型"""
    id: int
    proposal_code: str = Field(..., description="方案编号")
    proposal_type: str = Field(..., description="方案类型 A/B")
    template_id: str = Field(..., description="模板ID")
    template_name: str = Field(..., description="模板名称")
    total_benefit: Optional[Decimal] = Field(None, description="总收益 万元/年")
    total_investment: Optional[Decimal] = Field(0, description="总投资 万元")
    current_situation: Optional[Dict[str, Any]] = Field(None, description="当前状况")
    status: str = Field("pending", description="状态")
    created_at: datetime
    updated_at: datetime
    measures: List[MeasureResponse] = Field(default_factory=list, description="措施列表")

    class Config:
        from_attributes = True


class ProposalCreate(BaseModel):
    """创建方案请求模型"""
    template_id: str = Field(..., description="模板ID: A1/A2/A3/A4/A5/B1")
    analysis_days: int = Field(30, description="分析天数", ge=1, le=365)


class MeasureAcceptRequest(BaseModel):
    """接受方案请求模型"""
    selected_measure_ids: List[int] = Field(..., description="选中的措施ID列表")


# ========== 监控相关模型 ==========

class ExecutionLogResponse(BaseModel):
    """执行日志响应"""
    id: int
    execution_time: datetime
    power_before: Optional[Decimal]
    power_after: Optional[Decimal]
    power_saved: Optional[Decimal]
    expected_power_saved: Optional[Decimal]
    result: Optional[str]
    result_message: Optional[str]

    class Config:
        from_attributes = True


class MeasureMonitoringResponse(BaseModel):
    """措施监控响应"""
    measure_id: int
    measure_code: str
    regulation_object: str
    expected_benefit: Optional[Decimal]
    actual_benefit: Optional[Decimal] = Field(None, description="实际收益（从日志计算）")
    execution_count: int = Field(0, description="执行次数")
    success_count: int = Field(0, description="成功次数")
    latest_execution: Optional[ExecutionLogResponse] = None

    class Config:
        from_attributes = True


class ProposalMonitoringResponse(BaseModel):
    """方案监控响应"""
    proposal_id: int
    proposal_code: str
    template_name: str
    total_expected_benefit: Optional[Decimal]
    total_actual_benefit: Optional[Decimal] = Field(None, description="累计实际收益")
    measures: List[MeasureMonitoringResponse]


# ========== ML 增强相关模型 (专利 S2) ==========

class DevicePowerData(BaseModel):
    """设备功率数据 (用于 Transformer 分析)"""
    power: List[float] = Field(..., description="功率时序数据")
    period_types: List[int] = Field(default_factory=list, description="时段类型 0-4: 深谷/谷/平/峰/尖峰")
    is_weekday: List[int] = Field(default_factory=list, description="是否工作日 0/1")
    temperature: List[float] = Field(default_factory=list, description="温度数据")


class MLProposalCreate(BaseModel):
    """ML 增强方案生成请求"""
    template_id: str = Field(..., description="模板ID: A1/A2/A3/A4/A5/B1")
    analysis_days: int = Field(30, description="分析天数", ge=1, le=365)
    device_power_data: Optional[Dict[int, DevicePowerData]] = Field(
        None, description="设备功率数据 (可选, 用于 Transformer 分析)"
    )


class MLTransferableLoadResult(BaseModel):
    """可转移负荷分析结果"""
    device_id: int
    is_transferable: bool = Field(..., description="是否可转移")
    transferability_prob: float = Field(..., description="可转移概率")
    optimal_target_period: int = Field(..., description="最优转移目标时段")
    capacity_kw: float = Field(..., description="可转移容量 kW")
    confidence: float = Field(..., description="预测置信度")


class MLConflictAnalysisResult(BaseModel):
    """措施冲突分析结果"""
    measures_analyzed: int = Field(..., description="分析措施数量")
    recommended_count: int = Field(..., description="推荐措施数量")
    original_benefit: float = Field(..., description="原始收益")
    adjusted_benefit: float = Field(..., description="调整后收益")
    benefit_adjustment: float = Field(..., description="收益调整额")
    has_conflicts: bool = Field(..., description="是否存在冲突")


class MLAnalysisResponse(BaseModel):
    """ML 分析响应"""
    proposal_id: int
    ml_enabled: bool = Field(..., description="是否启用 ML")
    ml_available: bool = Field(..., description="ML 模块是否可用")
    transformer_analysis: Optional[Dict[str, Any]] = Field(None, description="Transformer 分析结果")
    gnn_analysis: Optional[Dict[str, Any]] = Field(None, description="GNN 分析结果")
    rl_adjustment: Optional[Dict[str, Any]] = Field(None, description="RL 调整结果")
    trace_summary: Optional[Dict[str, Any]] = Field(None, description="追溯汇总")


# ========== RL 自适应优化相关模型 (专利 S5) ==========

class RLStateInput(BaseModel):
    """RL 状态输入"""
    load_data: List[float] = Field(default_factory=list, description="负荷数据向量")
    price_period: int = Field(2, description="电价时段 0-4", ge=0, le=4)
    measure_states: List[int] = Field(default_factory=list, description="措施状态 0=未执行/1=执行中/2=完成")
    device_params: List[float] = Field(default_factory=list, description="设备参数")
    cumulative_saving: float = Field(0, description="累计节能收益")
    achievement_rate: float = Field(0.9, description="当前达成率")
    achievement_history: List[float] = Field(default_factory=list, description="达成率历史")


class RLAdjustment(BaseModel):
    """RL 调整建议"""
    value: Any = Field(..., description="调整值")
    description: str = Field(..., description="调整说明")
    unit: Optional[str] = Field(None, description="单位")
    index: Optional[int] = Field(None, description="索引 (离散动作)")


class RLOptimizationRequest(BaseModel):
    """RL 优化请求"""
    current_state: Optional[RLStateInput] = Field(None, description="当前状态 (可选, 不提供则使用默认)")


class RLOptimizationResponse(BaseModel):
    """RL 优化响应"""
    proposal_id: int
    success: bool = Field(..., description="是否成功")
    adjustments: Dict[str, RLAdjustment] = Field(default_factory=dict, description="调整建议")
    raw_actions: Optional[Dict[str, float]] = Field(None, description="原始动作值")
    exploration: bool = Field(False, description="是否为探索动作")
    exploration_rate: float = Field(0, description="当前探索率")
    confidence: float = Field(0, description="置信度")
    state_value: Optional[float] = Field(None, description="状态价值估计")
    optimization_id: Optional[int] = Field(None, description="优化记录ID")


class RLTrainingRequest(BaseModel):
    """RL 在线训练请求"""
    proposal_id: Optional[int] = Field(None, description="关联方案ID")
    actual_saving: float = Field(..., description="实际节能收益")
    expected_saving: float = Field(..., description="预期节能收益")
    comfort_violation: float = Field(0.0, description="舒适度违反程度 (0-1)", ge=0, le=1)
    safety_violation: float = Field(0.0, description="安全约束违反 (0-1)", ge=0, le=1)
    current_state: Optional[RLStateInput] = Field(None, description="当前状态")


class RLTrainingResponse(BaseModel):
    """RL 训练响应"""
    success: bool = Field(..., description="是否成功")
    reward: float = Field(..., description="计算奖励")
    achievement_rate: float = Field(..., description="达成率")
    exploration_rate: float = Field(..., description="当前探索率")
    step: int = Field(..., description="全局步数")
    network_updated: bool = Field(False, description="是否更新了网络")
    update_info: Optional[Dict[str, Any]] = Field(None, description="网络更新信息")
    training_log_id: Optional[int] = Field(None, description="训练日志ID")


class RLModelInfoResponse(BaseModel):
    """RL 模型信息响应"""
    model_name: str = Field("adaptive_optimizer", description="模型名称")
    is_trained: bool = Field(False, description="是否已训练")
    is_available: bool = Field(False, description="模型是否可用")
    total_steps: int = Field(0, description="总训练步数")
    total_episodes: int = Field(0, description="总训练回合")
    exploration_rate: float = Field(0.3, description="当前探索率")
    exploration_phase: str = Field("initial", description="探索阶段")
    avg_reward: Optional[float] = Field(None, description="平均奖励")
    avg_achievement_rate: Optional[float] = Field(None, description="平均达成率 %")
    best_reward: Optional[float] = Field(None, description="最佳奖励")
    checkpoint_saved_at: Optional[datetime] = Field(None, description="检查点保存时间")
    state_dim: Optional[int] = Field(None, description="状态空间维度")
    action_spec: Optional[Dict[str, Any]] = Field(None, description="动作空间规格")


class RLOptimizationHistoryItem(BaseModel):
    """RL 优化历史项"""
    id: int
    proposal_id: int
    created_at: datetime
    exploration: bool
    exploration_rate: Optional[float]
    confidence: Optional[float]
    applied: bool
    reward: Optional[float]
    achievement_rate: Optional[float]
    adjustments: Optional[Dict[str, Any]]

    class Config:
        from_attributes = True


class RLOptimizationHistoryResponse(BaseModel):
    """RL 优化历史响应"""
    total: int = Field(..., description="总记录数")
    items: List[RLOptimizationHistoryItem] = Field(default_factory=list, description="历史记录")


class RLExplorationRateUpdateRequest(BaseModel):
    """探索率更新请求"""
    exploration_rate: float = Field(..., description="新探索率", ge=0.0, le=1.0)
    phase: Optional[str] = Field(None, description="阶段: initial/stable/fluctuating/decaying")
