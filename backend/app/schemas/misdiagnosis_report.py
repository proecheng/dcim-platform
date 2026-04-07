"""
Pydantic Schema for Misdiagnosis Report - Story 26.6
"""

from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator, ConfigDict


class MisdiagnosisReportGenerateRequest(BaseModel):
    """手动生成报告请求"""

    start_date: date = Field(..., description="统计开始日期")
    end_date: date = Field(..., description="统计结束日期")

    @field_validator("end_date")
    @classmethod
    def validate_date_range(cls, v, info):
        if "start_date" in info.data:
            start_date = info.data["start_date"]
            if v <= start_date:
                raise ValueError("end_date 必须晚于 start_date")
            # 检查时间范围不超过31天
            delta = (v - start_date).days
            if delta > 31:
                raise ValueError("时间范围不能超过31天")
            # 检查 start_date 是否是月初
            if start_date.day != 1:
                raise ValueError("start_date 必须是月初（day=1）")
            # 检查 end_date 是否是月末
            if v.month != start_date.month or v.year != start_date.year:
                # 跨月了，检查是否是上个月的最后一天
                import calendar

                last_day = calendar.monthrange(start_date.year, start_date.month)[1]
                if v.day != last_day or v.month != start_date.month:
                    raise ValueError("end_date 必须是月末")
        return v


class DiagnosisSummary(BaseModel):
    """诊断概览统计"""

    total_diagnosis_count: int
    annotated_count: int
    annotation_coverage_rate: float


class MisdiagnosisDistribution(BaseModel):
    """误判类型分布"""

    false_positive_count: int
    false_positive_rate: float
    false_negative_count: int
    false_negative_rate: float
    false_negative_available: bool = Field(..., description="漏报统计是否可用")


class TopMisdiagnosedNode(BaseModel):
    """高频误判节点"""

    node_id: str
    node_name: str
    misdiagnosis_count: int
    total_count: int
    misdiagnosis_rate: float


class DeviceTypeMisdiagnosis(BaseModel):
    """设备类型误判分布"""

    device_type: str
    total_count: int
    misdiagnosis_count: int
    misdiagnosis_rate: float


class MisdiagnosisReportDetailResponse(BaseModel):
    """报告详情响应"""

    id: int
    report_name: str
    report_type: str
    start_time: datetime
    end_time: datetime
    file_path: Optional[str]
    file_size: Optional[int]
    status: str
    report_data: Optional[str]  # JSON 字符串
    generated_by: Optional[int]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MisdiagnosisReportListItem(BaseModel):
    """报告列表项"""

    id: int
    report_name: str
    report_type: str
    start_time: datetime
    end_time: datetime
    status: str
    file_size: Optional[int]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MisdiagnosisReportListResponse(BaseModel):
    """报告列表响应"""

    total: int
    page: int
    page_size: int
    items: List[MisdiagnosisReportListItem]
