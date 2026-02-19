"""
视频监控 Schema
Story 10-1: 摄像头元数据管理
"""
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, ConfigDict


# ========== NVR ==========

class NVRCreate(BaseModel):
    """创建 NVR"""
    name: str
    ip_address: str
    port: int = 554
    username: Optional[str] = None
    password: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    max_channels: Optional[int] = None
    description: Optional[str] = None


class NVRUpdate(BaseModel):
    """更新 NVR"""
    name: Optional[str] = None
    ip_address: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    max_channels: Optional[int] = None
    status: Optional[str] = None
    description: Optional[str] = None


class NVRResponse(BaseModel):
    """NVR 响应"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    ip_address: str
    port: int
    username: Optional[str] = None
    password_masked: Optional[str] = None  # 掩码后的密码
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    max_channels: Optional[int] = None
    status: str
    description: Optional[str] = None
    camera_count: int = 0  # 关联摄像头数量
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ========== CameraPreset ==========

class CameraPresetCreate(BaseModel):
    """创建预置位"""
    preset_index: int
    name: str
    description: Optional[str] = None


class CameraPresetResponse(BaseModel):
    """预置位响应"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    camera_id: int
    preset_index: int
    name: str
    description: Optional[str] = None


# ========== Camera ==========

class CameraCreate(BaseModel):
    """创建摄像头"""
    name: str
    code: str
    rtsp_url: Optional[str] = None
    onvif_url: Optional[str] = None
    hls_url: Optional[str] = None
    nvr_id: Optional[int] = None
    channel_no: Optional[int] = None
    area_code: Optional[str] = None
    cabinet_id: Optional[int] = None
    device_id: Optional[int] = None
    location_description: Optional[str] = None
    camera_type: str = "dome"
    presets: Optional[List[CameraPresetCreate]] = None


class CameraUpdate(BaseModel):
    """更新摄像头"""
    name: Optional[str] = None
    code: Optional[str] = None
    rtsp_url: Optional[str] = None
    onvif_url: Optional[str] = None
    hls_url: Optional[str] = None
    nvr_id: Optional[int] = None
    channel_no: Optional[int] = None
    area_code: Optional[str] = None
    cabinet_id: Optional[int] = None
    device_id: Optional[int] = None
    location_description: Optional[str] = None
    camera_type: Optional[str] = None
    status: Optional[str] = None
    is_enabled: Optional[bool] = None
    presets: Optional[List[CameraPresetCreate]] = None


class CameraResponse(BaseModel):
    """摄像头响应"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    rtsp_url: Optional[str] = None
    onvif_url: Optional[str] = None
    hls_url: Optional[str] = None
    nvr_id: Optional[int] = None
    nvr_name: Optional[str] = None  # 关联 NVR 名称
    channel_no: Optional[int] = None
    area_code: Optional[str] = None
    cabinet_id: Optional[int] = None
    device_id: Optional[int] = None
    location_description: Optional[str] = None
    camera_type: str
    status: str
    is_enabled: bool
    presets: List[CameraPresetResponse] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ========== VideoEvent ==========

class PTZControlRequest(BaseModel):
    """云台控制请求"""
    camera_id: int
    action: str  # up/down/left/right/zoom_in/zoom_out/stop
    speed: int = 5  # 1-10


class PresetCallRequest(BaseModel):
    """预置位调用请求"""
    camera_id: int
    preset_index: int


class RecordingRequest(BaseModel):
    """录像控制请求"""
    camera_id: int
    alarm_id: Optional[int] = None
    linkage_execution_id: Optional[int] = None


class VideoEventResponse(BaseModel):
    """视频事件响应"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    camera_id: int
    camera_name: Optional[str] = None
    event_type: str
    trigger_source: str
    alarm_id: Optional[int] = None
    linkage_execution_id: Optional[int] = None
    detail: Optional[str] = None
    operator: Optional[str] = None
    created_at: Optional[datetime] = None


# ========== Playback (Story 10-4) ==========

class AlarmBrief(BaseModel):
    """告警摘要"""
    id: int
    alarm_level: str
    alarm_message: str
    alarm_time: Optional[datetime] = None


class CameraBrief(BaseModel):
    """摄像头摘要（回放用）"""
    id: int
    name: str
    code: str
    rtsp_url: Optional[str] = None
    hls_url: Optional[str] = None
    location_description: Optional[str] = None


class RecordingSegmentResponse(BaseModel):
    """录像片段"""
    id: int
    camera_id: int
    camera_name: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    alarm_id: Optional[int] = None
    duration_seconds: Optional[int] = None


class PlaybackInfoResponse(BaseModel):
    """告警回放信息"""
    alarm_info: AlarmBrief
    cameras: List[CameraBrief]
    recording_events: List[VideoEventResponse]
    playback_url_template: str
