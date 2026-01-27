"""
报表模型
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean

from ..core.database import Base


class ReportTemplate(Base):
    """报表模板表"""
    __tablename__ = "report_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    template_name = Column(String(100), nullable=False, comment="模板名称")
    template_type = Column(String(20), comment="模板类型: daily/weekly/monthly/custom")
    template_config = Column(Text, comment="模板配置(JSON)")
    point_ids = Column(Text, comment="包含的点位ID列表(JSON)")
    is_enabled = Column(Boolean, default=True, comment="是否启用")
    created_by = Column(Integer, ForeignKey("users.id"), comment="创建人")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")


class ReportRecord(Base):
    """报表生成记录表"""
    __tablename__ = "report_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    template_id = Column(Integer, ForeignKey("report_templates.id"), comment="模板ID")
    report_name = Column(String(200), comment="报表名称")
    report_type = Column(String(20), comment="报表类型")
    start_time = Column(DateTime, comment="开始时间")
    end_time = Column(DateTime, comment="结束时间")
    file_path = Column(String(255), comment="文件路径")
    file_size = Column(Integer, comment="文件大小")
    status = Column(String(20), comment="状态: generating/completed/failed")
    error_message = Column(Text, comment="错误信息")
    generated_by = Column(Integer, ForeignKey("users.id"), comment="生成人")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
