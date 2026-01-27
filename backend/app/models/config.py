"""
配置模型
"""
from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Date, ForeignKey

from ..core.database import Base


class SystemConfig(Base):
    """系统配置表"""
    __tablename__ = "system_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    config_group = Column(String(50), nullable=False, comment="配置分组")
    config_key = Column(String(100), nullable=False, comment="配置键")
    config_value = Column(Text, comment="配置值")
    value_type = Column(String(20), comment="值类型: string/number/boolean/json")
    description = Column(String(200), comment="描述")
    is_editable = Column(Boolean, default=True, comment="是否可编辑")
    updated_by = Column(Integer, ForeignKey("users.id"), comment="更新人")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")


class Dictionary(Base):
    """数据字典表"""
    __tablename__ = "dictionaries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dict_type = Column(String(50), nullable=False, comment="字典类型")
    dict_code = Column(String(50), nullable=False, comment="字典编码")
    dict_name = Column(String(100), nullable=False, comment="字典名称")
    dict_value = Column(String(200), comment="字典值")
    sort_order = Column(Integer, default=0, comment="排序")
    is_enabled = Column(Boolean, default=True, comment="是否启用")
    remark = Column(Text, comment="备注")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")


class License(Base):
    """授权许可表"""
    __tablename__ = "licenses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    license_key = Column(String(100), unique=True, nullable=False, comment="许可证密钥")
    license_type = Column(String(20), nullable=False, comment="许可类型: basic/standard/enterprise/unlimited")
    max_points = Column(Integer, nullable=False, comment="最大点位数")
    features = Column(Text, comment="功能列表(JSON)")
    issue_date = Column(Date, comment="发放日期")
    expire_date = Column(Date, comment="过期日期")
    hardware_id = Column(String(100), comment="硬件ID")
    is_active = Column(Boolean, default=True, comment="是否激活")
    activated_at = Column(DateTime, comment="激活时间")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
