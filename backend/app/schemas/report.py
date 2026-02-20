"""
报表相关 Schema
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class ReportTemplateCreate(BaseModel):
    """创建报表模板"""

    template_name: str
    template_type: Optional[str] = None
    template_config: Optional[str] = None
    point_ids: Optional[str] = None
    is_enabled: bool = True


class ReportTemplateUpdate(BaseModel):
    """更新报表模板"""

    template_name: Optional[str] = None
    template_type: Optional[str] = None
    template_config: Optional[str] = None
    point_ids: Optional[str] = None
    is_enabled: Optional[bool] = None


class ReportTemplateInfo(BaseModel):
    """报表模板信息"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    template_name: str
    template_type: Optional[str] = None
    template_config: Optional[str] = None
    point_ids: Optional[str] = None
    is_enabled: bool = True
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ReportRecordInfo(BaseModel):
    """报表记录信息"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    template_id: Optional[int] = None
    report_name: Optional[str] = None
    report_type: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    status: Optional[str] = None
    error_message: Optional[str] = None
    report_data: Optional[str] = None
    generated_by: Optional[int] = None
    created_at: Optional[datetime] = None


class ReportGenerate(BaseModel):
    """生成报表"""

    template_id: Optional[int] = None
    report_type: Optional[str] = None
    start_time: datetime
    end_time: datetime
    point_ids: Optional[List[int]] = None


# --- Story 12-1: 自动运行报表 ---


class ReportScheduleCreate(BaseModel):
    """创建报表调度"""

    name: str = Field(..., min_length=1, max_length=100, description="调度名称")
    report_type: str = Field(..., description="报表类型: daily/weekly/monthly")
    is_enabled: bool = Field(True, description="是否启用")


class ReportScheduleUpdate(BaseModel):
    """更新报表调度"""

    name: Optional[str] = Field(None, max_length=100, description="调度名称")
    report_type: Optional[str] = Field(None, description="报表类型: daily/weekly/monthly")
    is_enabled: Optional[bool] = Field(None, description="是否启用")


class ReportScheduleResponse(BaseModel):
    """报表调度响应"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    report_type: str
    is_enabled: bool = True
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AutoReportRequest(BaseModel):
    """自动报表生成请求"""

    report_type: str = Field(..., description="报表类型: daily/weekly/monthly")


class AutoReportData(BaseModel):
    """自动报表数据"""

    report_type: str
    title: str
    period: Dict[str, str]
    generated_at: str
    alarm_trends: Dict[str, Any] = Field(default_factory=dict)
    energy_comparison: Dict[str, Any] = Field(default_factory=dict)
    workorder_stats: Dict[str, Any] = Field(default_factory=dict)
    device_availability: Dict[str, Any] = Field(default_factory=dict)
    comparison: Dict[str, Any] = Field(default_factory=dict)
