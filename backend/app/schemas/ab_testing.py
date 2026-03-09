"""
A/B 测试 Pydantic Schema - Story 26.5
"""
from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, Literal, Union
from datetime import datetime


class StrategyParamsHash(BaseModel):
    """哈希分流策略参数"""
    percentage: int = Field(..., ge=0, le=100, description="使用版本A的百分比")


class StrategyParamsDeviceType(BaseModel):
    """设备类型分流策略参数"""
    device_types_a: list[str] = Field(..., min_length=1, description="使用版本A的设备类型列表")


class StrategyParamsSite(BaseModel):
    """站点分流策略参数"""
    site_ids_a: list[int] = Field(..., min_length=1, description="使用版本A的站点ID列表")


class ABTestCreateRequest(BaseModel):
    """创建 A/B 测试请求"""
    name: str = Field(..., min_length=1, max_length=255)
    fault_tree_id: int = Field(..., gt=0)
    version_a_id: int = Field(..., gt=0, description="测试版本ID")
    version_b_id: int = Field(..., gt=0, description="对照版本ID")
    strategy: Literal["hash", "device_type", "site", "percentage"]
    strategy_params: Union[StrategyParamsHash, StrategyParamsDeviceType, StrategyParamsSite]
    min_duration_hours: Optional[int] = Field(168, ge=1, description="最小运行时长（小时）")
    min_sample_size: Optional[int] = Field(100, ge=10, description="最小样本量")

    @field_validator("version_b_id")
    @classmethod
    def versions_must_differ(cls, v, info):
        if "version_a_id" in info.data and v == info.data["version_a_id"]:
            raise ValueError("version_a_id 和 version_b_id 必须不同")
        return v


class ABTestUpdateRequest(BaseModel):
    """更新 A/B 测试请求"""
    strategy_params: Union[StrategyParamsHash, StrategyParamsDeviceType, StrategyParamsSite]
    version: int = Field(..., description="乐观锁版本号")


class ABTestCompleteRequest(BaseModel):
    """完成 A/B 测试请求"""
    action: Literal["promote_version_a", "rollback_to_version_b"]
    version: int = Field(..., description="乐观锁版本号")


class ABTestResponse(BaseModel):
    """A/B 测试响应"""
    id: int
    name: str
    fault_tree_id: int
    version_a_id: int
    version_b_id: int
    strategy: str
    strategy_params: dict
    status: str
    version: int
    min_duration_hours: int
    min_sample_size: int
    created_by: Optional[int]
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class VersionStats(BaseModel):
    """版本统计数据"""
    version_id: int
    version_name: str
    diagnosis_count: int
    accuracy_rate: float
    avg_inference_time_ms: float
    false_positive_rate: float
    false_negative_rate: float


class StatisticalTestResult(BaseModel):
    """统计检验结果"""
    method: str
    p_value: Optional[float]
    is_significant: bool
    chi2_statistic: Optional[float] = None
    degrees_of_freedom: Optional[int] = None
    odds_ratio: Optional[float] = None
    note: Optional[str] = None
    warning: Optional[str] = None


class ABTestReportResponse(BaseModel):
    """A/B 测试效果报告响应"""
    ab_test_id: int
    name: str
    duration_days: int
    duration_hours: int
    version_a: VersionStats
    version_b: VersionStats
    statistical_test: StatisticalTestResult
    recommendation: str
    can_complete: bool
    completion_requirements: dict
