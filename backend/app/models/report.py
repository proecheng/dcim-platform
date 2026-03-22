"""
报表模型
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Float

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
    report_data = Column(Text, comment="报表数据(JSON)")
    generated_by = Column(Integer, ForeignKey("users.id"), comment="生成人")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")


class ReportSchedule(Base):
    """报表调度配置表"""

    __tablename__ = "report_schedules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="调度名称")
    report_type = Column(String(20), nullable=False, comment="报表类型: daily/weekly/monthly")
    is_enabled = Column(Boolean, default=True, comment="是否启用")
    last_run_at = Column(DateTime, comment="上次运行时间")
    next_run_at = Column(DateTime, comment="下次运行时间")
    created_by = Column(Integer, ForeignKey("users.id"), comment="创建人")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")


class DeviceHealthScore(Base):
    """设备健康度评分表"""

    __tablename__ = "device_health_scores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False, unique=True, comment="设备ID")
    device_name = Column(String(100), comment="设备名称")
    device_type = Column(String(50), comment="设备类型")
    score = Column(Float, nullable=False, default=100, comment="健康度评分 0-100")
    health_level = Column(String(20), nullable=False, default="健康", comment="健康等级: 健康/关注/预警/危险")
    alarm_count = Column(Integer, default=0, comment="近期告警数")
    maintenance_count = Column(Integer, default=0, comment="维保记录数")
    last_maintenance_at = Column(DateTime, comment="最近维保时间")
    score_factors = Column(Text, comment="评分因子详情(JSON)")
    data_sufficiency = Column(String(20), default="minimal", comment="数据充分度: full/partial/minimal")
    degradation_score = Column(Float, comment="劣化趋势评分 0-100")
    calculated_at = Column(DateTime, default=datetime.now, comment="计算时间")
