"""OTA 升级 Schema — Story 15.5"""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


# --- Firmware ---
class FirmwareCreate(BaseModel):
    version: str = Field(..., max_length=50, description="版本号 (semver)")
    filename: str = Field(..., max_length=200, description="文件名")
    file_size: int = Field(..., gt=0, description="文件大小(字节)")
    checksum_sha256: str = Field(..., min_length=64, max_length=64, description="SHA-256 校验和")
    download_url: str = Field(..., max_length=500, description="下载地址")
    release_notes: Optional[str] = Field(None, max_length=2000, description="更新说明")
    min_version: Optional[str] = Field(None, max_length=50, description="最低兼容版本")


class FirmwareResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    version: str
    filename: str
    file_size: int
    checksum_sha256: str
    download_url: str
    release_notes: Optional[str] = None
    min_version: Optional[str] = None
    is_active: bool = True
    created_at: Optional[datetime] = None


# --- OTA Task ---
class OtaTaskCreate(BaseModel):
    firmware_id: int = Field(..., description="目标固件包 ID")
    gateway_ids: list[int] = Field(..., min_length=1, description="目标网关 ID 列表")
    strategy: str = Field("immediate", pattern="^(immediate|batch|canary)$", description="策略")
    batch_size: int = Field(0, ge=0, description="分批大小(0=全部)")
    batch_interval: int = Field(300, ge=0, le=3600, description="批次间隔(秒)")
    canary_percent: int = Field(10, ge=1, le=50, description="灰度百分比")


class OtaGatewayStatus(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    gateway_id: str
    batch_index: int = 0
    status: str = "pending"
    old_version: Optional[str] = None
    progress: int = 0
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class OtaTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: str
    firmware_id: int
    target_version: str
    strategy: str
    batch_size: int
    batch_interval: int
    canary_percent: int
    status: str
    total_gateways: int
    success_count: int
    fail_count: int
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class OtaTaskDetailResponse(OtaTaskResponse):
    """任务详情（含各网关状态）"""
    gateways: list[OtaGatewayStatus] = []
