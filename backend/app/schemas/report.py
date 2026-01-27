"""
报表相关 Schema
"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict


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
    generated_by: Optional[int] = None
    created_at: Optional[datetime] = None


class ReportGenerate(BaseModel):
    """生成报表"""
    template_id: Optional[int] = None
    report_type: Optional[str] = None
    start_time: datetime
    end_time: datetime
    point_ids: Optional[List[int]] = None
