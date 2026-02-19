"""
视频监控 API
Story 10-1: 摄像头元数据管理
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..deps import get_db, require_admin, require_operator, require_viewer
from ...models.user import User
from ...models.alarm import Alarm
from ...models.point import Point
from ...schemas.video import (
    NVRCreate, NVRUpdate, NVRResponse,
    CameraCreate, CameraUpdate, CameraResponse, CameraPresetResponse,
    PTZControlRequest, PresetCallRequest, RecordingRequest, VideoEventResponse,
    PlaybackInfoResponse, AlarmBrief, CameraBrief, RecordingSegmentResponse,
)
from ...services import video_service

logger = logging.getLogger(__name__)

router = APIRouter()


# ========== NVR 端点 ==========

@router.post("/nvrs", response_model=NVRResponse, summary="创建NVR")
async def create_nvr(
    data: NVRCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """创建 NVR 设备"""
    nvr = await video_service.create_nvr(db, data)
    camera_count = await video_service.get_nvr_camera_count(db, nvr.id)
    return _build_nvr_response(nvr, camera_count)


@router.get("/nvrs", summary="NVR列表")
async def list_nvrs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """获取 NVR 列表（分页）"""
    result = await video_service.list_nvrs(db, page, page_size)
    items = []
    for nvr in result["items"]:
        count = await video_service.get_nvr_camera_count(db, nvr.id)
        items.append(_build_nvr_response(nvr, count))
    return {
        "total": result["total"],
        "items": items,
        "page": page,
        "page_size": page_size,
    }


@router.get("/nvrs/{nvr_id}", response_model=NVRResponse, summary="NVR详情")
async def get_nvr(
    nvr_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """获取 NVR 详情"""
    nvr = await video_service.get_nvr(db, nvr_id)
    if not nvr:
        raise HTTPException(status_code=404, detail="NVR不存在")
    camera_count = await video_service.get_nvr_camera_count(db, nvr.id)
    return _build_nvr_response(nvr, camera_count)


@router.put("/nvrs/{nvr_id}", response_model=NVRResponse, summary="更新NVR")
async def update_nvr(
    nvr_id: int,
    data: NVRUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """更新 NVR"""
    nvr = await video_service.update_nvr(db, nvr_id, data)
    if not nvr:
        raise HTTPException(status_code=404, detail="NVR不存在")
    camera_count = await video_service.get_nvr_camera_count(db, nvr.id)
    return _build_nvr_response(nvr, camera_count)


@router.delete("/nvrs/{nvr_id}", summary="删除NVR")
async def delete_nvr(
    nvr_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """删除 NVR（有关联摄像头时拒绝）"""
    try:
        success = await video_service.delete_nvr(db, nvr_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not success:
        raise HTTPException(status_code=404, detail="NVR不存在")
    return {"message": "删除成功"}


# ========== Camera 端点 ==========

# 静态路由必须在参数化路由之前
@router.get("/cameras/by-alarm/{alarm_id}", summary="按告警查询关联摄像头")
async def get_cameras_by_alarm(
    alarm_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """根据告警 ID 查找关联摄像头（通过 Alarm→Point→device_id/area_code 关联链）"""
    # 查询告警关联的点位
    alarm_result = await db.execute(select(Alarm).where(Alarm.id == alarm_id))
    alarm = alarm_result.scalar_one_or_none()
    if not alarm:
        raise HTTPException(status_code=404, detail="告警不存在")

    # 查询点位获取 device_id 和 area_code
    point_result = await db.execute(select(Point).where(Point.id == alarm.point_id))
    point = point_result.scalar_one_or_none()
    if not point:
        return []

    cameras = []
    # 先按设备查找
    if point.device_id:
        cameras = await video_service.get_cameras_by_device(db, point.device_id)
    # 再按区域查找
    if not cameras and point.area_code:
        cameras = await video_service.get_cameras_by_area(db, point.area_code)

    return [CameraResponse.model_validate(c) for c in cameras]


@router.get("/cameras/by-area/{area_code}", summary="按区域查询摄像头")
async def get_cameras_by_area(
    area_code: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """按区域查询已启用的摄像头（联动查询用）"""
    cameras = await video_service.get_cameras_by_area(db, area_code)
    return [CameraResponse.model_validate(c) for c in cameras]


@router.get("/cameras/by-device/{device_id}", summary="按设备查询摄像头")
async def get_cameras_by_device(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """按设备查询已启用的摄像头（联动查询用）"""
    cameras = await video_service.get_cameras_by_device(db, device_id)
    return [CameraResponse.model_validate(c) for c in cameras]


@router.post("/cameras", response_model=CameraResponse, summary="创建摄像头")
async def create_camera(
    data: CameraCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """创建摄像头（含预置位）"""
    camera = await video_service.create_camera(db, data)
    detail = await video_service.get_camera(db, camera.id)
    return _build_camera_response(detail)


@router.get("/cameras", summary="摄像头列表")
async def list_cameras(
    nvr_id: Optional[int] = Query(None, description="按NVR筛选"),
    area_code: Optional[str] = Query(None, description="按区域筛选"),
    status: Optional[str] = Query(None, description="按状态筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """获取摄像头列表（分页+筛选）"""
    result = await video_service.list_cameras(
        db, nvr_id=nvr_id, area_code=area_code, status=status,
        page=page, page_size=page_size,
    )
    items = []
    for camera in result["cameras"]:
        nvr_name = result["nvr_names"].get(camera.nvr_id) if camera.nvr_id else None
        presets = result["presets_map"].get(camera.id, [])
        resp = CameraResponse.model_validate(camera)
        resp.nvr_name = nvr_name
        resp.presets = [CameraPresetResponse.model_validate(p) for p in presets]
        items.append(resp)
    return {
        "total": result["total"],
        "items": items,
        "page": page,
        "page_size": page_size,
    }


@router.get("/cameras/{camera_id}", response_model=CameraResponse, summary="摄像头详情")
async def get_camera(
    camera_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """获取摄像头详情（含预置位和NVR名称）"""
    detail = await video_service.get_camera(db, camera_id)
    if not detail:
        raise HTTPException(status_code=404, detail="摄像头不存在")
    return _build_camera_response(detail)


@router.put("/cameras/{camera_id}", response_model=CameraResponse, summary="更新摄像头")
async def update_camera(
    camera_id: int,
    data: CameraUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """更新摄像头（含预置位替换）"""
    camera = await video_service.update_camera(db, camera_id, data)
    if not camera:
        raise HTTPException(status_code=404, detail="摄像头不存在")
    detail = await video_service.get_camera(db, camera.id)
    return _build_camera_response(detail)


@router.delete("/cameras/{camera_id}", summary="删除摄像头")
async def delete_camera(
    camera_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """删除摄像头（级联删除预置位）"""
    success = await video_service.delete_camera(db, camera_id)
    if not success:
        raise HTTPException(status_code=404, detail="摄像头不存在")
    return {"message": "删除成功"}


# ========== 辅助函数 ==========

def _build_nvr_response(nvr, camera_count: int) -> NVRResponse:
    """构建 NVR 响应（密码掩码）"""
    return NVRResponse(
        id=nvr.id,
        name=nvr.name,
        ip_address=nvr.ip_address,
        port=nvr.port,
        username=nvr.username,
        password_masked="***" if nvr.password else None,
        manufacturer=nvr.manufacturer,
        model=nvr.model,
        max_channels=nvr.max_channels,
        status=nvr.status,
        description=nvr.description,
        camera_count=camera_count,
        created_at=nvr.created_at,
        updated_at=nvr.updated_at,
    )


def _build_camera_response(detail: dict) -> CameraResponse:
    """构建摄像头响应"""
    camera = detail["camera"]
    resp = CameraResponse.model_validate(camera)
    resp.nvr_name = detail.get("nvr_name")
    resp.presets = [
        CameraPresetResponse.model_validate(p) for p in detail.get("presets", [])
    ]
    return resp


# ========== PTZ / 录像 / 事件端点 (Story 10-3) ==========

@router.post("/ptz/control", response_model=VideoEventResponse, summary="云台控制")
async def ptz_control(
    data: PTZControlRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_operator),
):
    """远程控制摄像头云台（模拟 ONVIF PTZ 命令）"""
    # 验证摄像头存在
    cam = await video_service.get_camera(db, data.camera_id)
    if not cam:
        raise HTTPException(status_code=404, detail="摄像头不存在")
    event = await video_service.ptz_control(
        db, data.camera_id, data.action, data.speed, user.username,
    )
    resp = VideoEventResponse.model_validate(event)
    resp.camera_name = cam["camera"].name
    return resp


@router.post("/ptz/preset", response_model=VideoEventResponse, summary="调用预置位")
async def call_preset(
    data: PresetCallRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_operator),
):
    """调用摄像头预置位（模拟 ONVIF 预置位调用）"""
    cam = await video_service.get_camera(db, data.camera_id)
    if not cam:
        raise HTTPException(status_code=404, detail="摄像头不存在")
    event = await video_service.call_preset(
        db, data.camera_id, data.preset_index, user.username,
    )
    resp = VideoEventResponse.model_validate(event)
    resp.camera_name = cam["camera"].name
    return resp


@router.post("/recording/start", response_model=VideoEventResponse, summary="开始录像")
async def start_recording(
    data: RecordingRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    """触发摄像头开始录像（模拟 ONVIF 录像命令）"""
    cam = await video_service.get_camera(db, data.camera_id)
    if not cam:
        raise HTTPException(status_code=404, detail="摄像头不存在")
    event = await video_service.start_recording(
        db, data.camera_id, "manual",
        alarm_id=data.alarm_id, linkage_execution_id=data.linkage_execution_id,
    )
    resp = VideoEventResponse.model_validate(event)
    resp.camera_name = cam["camera"].name
    return resp


@router.post("/recording/stop", response_model=VideoEventResponse, summary="停止录像")
async def stop_recording(
    data: RecordingRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    """停止摄像头录像（模拟 ONVIF 录像命令）"""
    cam = await video_service.get_camera(db, data.camera_id)
    if not cam:
        raise HTTPException(status_code=404, detail="摄像头不存在")
    event = await video_service.stop_recording(db, data.camera_id)
    resp = VideoEventResponse.model_validate(event)
    resp.camera_name = cam["camera"].name
    return resp


@router.get("/events", summary="视频事件列表")
async def list_video_events(
    camera_id: Optional[int] = Query(None, description="按摄像头筛选"),
    event_type: Optional[str] = Query(None, description="按事件类型筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """获取视频事件列表（分页+筛选）"""
    result = await video_service.list_video_events(
        db, camera_id=camera_id, event_type=event_type,
        page=page, page_size=page_size,
    )
    items = []
    for event in result["items"]:
        resp = VideoEventResponse.model_validate(event)
        resp.camera_name = result["cam_names"].get(event.camera_id)
        items.append(resp)
    return {
        "total": result["total"],
        "items": items,
        "page": page,
        "page_size": page_size,
    }


# ========== 回放端点 (Story 10-4) ==========

@router.get("/playback/alarm/{alarm_id}", response_model=PlaybackInfoResponse, summary="告警回放信息")
async def get_playback_info(
    alarm_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """获取告警回放信息（关联摄像头 + 时间定位 + 录像事件）"""
    result = await video_service.get_playback_info(db, alarm_id)
    if not result:
        raise HTTPException(status_code=404, detail="告警不存在")

    # 构建响应
    cameras = [
        CameraBrief(
            id=c.id, name=c.name, code=c.code,
            rtsp_url=c.rtsp_url, hls_url=c.hls_url,
            location_description=c.location_description,
        )
        for c in result["cameras"]
    ]
    events = []
    for evt in result["recording_events"]:
        resp = VideoEventResponse.model_validate(evt)
        resp.camera_name = result["cam_names"].get(evt.camera_id)
        events.append(resp)

    return PlaybackInfoResponse(
        alarm_info=AlarmBrief(**result["alarm_info"]),
        cameras=cameras,
        recording_events=events,
        playback_url_template=result["playback_url_template"],
    )


@router.get("/playback/segments", summary="录像片段列表")
async def list_recording_segments(
    camera_id: int = Query(..., description="摄像头ID"),
    start_time: Optional[str] = Query(None, description="开始时间 ISO格式"),
    end_time: Optional[str] = Query(None, description="结束时间 ISO格式"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """查询录像片段列表（按摄像头+时间范围）"""
    result = await video_service.list_recording_segments(
        db, camera_id, start_time=start_time, end_time=end_time,
        page=page, page_size=page_size,
    )
    return {
        "total": result["total"],
        "items": [RecordingSegmentResponse(**seg) for seg in result["items"]],
        "page": page,
        "page_size": page_size,
    }
