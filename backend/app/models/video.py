"""
视频监控模型
Story 10-1: 摄像头元数据管理
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey

from ..core.database import Base


class NVR(Base):
    """NVR 设备表"""

    __tablename__ = "nvrs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="NVR名称")
    ip_address = Column(String(50), nullable=False, comment="IP地址")
    port = Column(Integer, default=554, comment="端口")
    username = Column(String(100), nullable=True, comment="登录用户名")
    password = Column(String(200), nullable=True, comment="登录密码")
    manufacturer = Column(String(50), nullable=True, comment="厂商: hikvision/dahua/other")
    model = Column(String(100), nullable=True, comment="型号")
    max_channels = Column(Integer, nullable=True, comment="最大通道数")
    status = Column(String(20), default="offline", comment="状态: online/offline")
    description = Column(Text, nullable=True, comment="备注")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")


class Camera(Base):
    """摄像头表"""

    __tablename__ = "cameras"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="摄像头名称")
    code = Column(String(50), unique=True, nullable=False, comment="摄像头编码")
    rtsp_url = Column(String(500), nullable=True, comment="RTSP流地址")
    onvif_url = Column(String(500), nullable=True, comment="ONVIF控制地址")
    hls_url = Column(String(500), nullable=True, comment="HLS流地址")
    nvr_id = Column(Integer, ForeignKey("nvrs.id"), nullable=True, comment="关联NVR")
    channel_no = Column(Integer, nullable=True, comment="NVR通道号")
    area_code = Column(String(10), nullable=True, comment="关联区域代码")
    cabinet_id = Column(Integer, nullable=True, comment="关联机柜ID")
    device_id = Column(Integer, nullable=True, comment="关联设备ID")
    location_description = Column(String(200), nullable=True, comment="位置描述")
    camera_type = Column(String(20), default="dome", comment="类型: dome/bullet/ptz")
    status = Column(String(20), default="unknown", comment="状态: online/offline/unknown")
    is_enabled = Column(Boolean, default=True, comment="是否启用")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")


class CameraPreset(Base):
    """摄像头预置位表"""

    __tablename__ = "camera_presets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    camera_id = Column(Integer, ForeignKey("cameras.id"), nullable=False, comment="关联摄像头")
    preset_index = Column(Integer, nullable=False, comment="预置位编号")
    name = Column(String(100), nullable=False, comment="预置位名称")
    description = Column(String(200), nullable=True, comment="描述")


class VideoEvent(Base):
    """视频事件表"""

    __tablename__ = "video_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    camera_id = Column(Integer, ForeignKey("cameras.id"), nullable=False, comment="关联摄像头")
    event_type = Column(
        String(30), nullable=False, comment="事件类型: recording_start/recording_stop/ptz_control/preset_call"
    )
    trigger_source = Column(String(50), nullable=False, comment="触发来源: linkage/manual")
    alarm_id = Column(Integer, nullable=True, comment="关联告警ID")
    linkage_execution_id = Column(Integer, nullable=True, comment="关联联动执行ID")
    detail = Column(Text, nullable=True, comment="事件详情JSON")
    operator = Column(String(50), nullable=True, comment="操作人")
    created_at = Column(DateTime, default=datetime.now, comment="事件时间")
