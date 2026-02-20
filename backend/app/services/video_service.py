"""
视频监控服务
Story 10-1: 摄像头元数据管理
"""

import logging
from typing import Optional, List, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete, desc

from ..models.video import NVR, Camera, CameraPreset, VideoEvent
from ..models.alarm import Alarm
from ..models.point import Point
from ..schemas.video import (
    NVRCreate,
    NVRUpdate,
    CameraCreate,
    CameraUpdate,
)

logger = logging.getLogger(__name__)


# ========== NVR 服务 ==========


async def create_nvr(db: AsyncSession, data: NVRCreate) -> NVR:
    """创建 NVR"""
    nvr = NVR(
        name=data.name,
        ip_address=data.ip_address,
        port=data.port,
        username=data.username,
        password=data.password,
        manufacturer=data.manufacturer,
        model=data.model,
        max_channels=data.max_channels,
        description=data.description,
    )
    db.add(nvr)
    await db.commit()
    await db.refresh(nvr)
    return nvr


async def update_nvr(db: AsyncSession, nvr_id: int, data: NVRUpdate) -> Optional[NVR]:
    """更新 NVR"""
    result = await db.execute(select(NVR).where(NVR.id == nvr_id))
    nvr = result.scalar_one_or_none()
    if not nvr:
        return None

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(nvr, key, value)

    await db.commit()
    await db.refresh(nvr)
    return nvr


async def delete_nvr(db: AsyncSession, nvr_id: int) -> bool:
    """删除 NVR（有关联摄像头时拒绝）"""
    # 检查关联摄像头
    count_result = await db.execute(select(func.count(Camera.id)).where(Camera.nvr_id == nvr_id))
    camera_count = count_result.scalar() or 0
    if camera_count > 0:
        raise ValueError(f"该 NVR 下有 {camera_count} 个摄像头，请先删除或解绑摄像头")

    result = await db.execute(select(NVR).where(NVR.id == nvr_id))
    nvr = result.scalar_one_or_none()
    if not nvr:
        return False

    await db.delete(nvr)
    await db.commit()
    return True


async def get_nvr(db: AsyncSession, nvr_id: int) -> Optional[NVR]:
    """获取 NVR 详情"""
    result = await db.execute(select(NVR).where(NVR.id == nvr_id))
    return result.scalar_one_or_none()


async def list_nvrs(db: AsyncSession, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
    """NVR 列表（分页）"""
    count_result = await db.execute(select(func.count(NVR.id)))
    total = count_result.scalar() or 0

    query = select(NVR).order_by(desc(NVR.created_at))
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()

    return {"total": total, "items": items}


async def get_nvr_camera_count(db: AsyncSession, nvr_id: int) -> int:
    """获取 NVR 关联摄像头数量"""
    result = await db.execute(select(func.count(Camera.id)).where(Camera.nvr_id == nvr_id))
    return result.scalar() or 0


# ========== Camera 服务 ==========


async def create_camera(db: AsyncSession, data: CameraCreate) -> Camera:
    """创建摄像头（含预置位）"""
    camera = Camera(
        name=data.name,
        code=data.code,
        rtsp_url=data.rtsp_url,
        onvif_url=data.onvif_url,
        hls_url=data.hls_url,
        nvr_id=data.nvr_id,
        channel_no=data.channel_no,
        area_code=data.area_code,
        cabinet_id=data.cabinet_id,
        device_id=data.device_id,
        location_description=data.location_description,
        camera_type=data.camera_type,
    )
    db.add(camera)
    await db.flush()  # 获取 camera.id

    # 创建预置位
    if data.presets:
        for preset_data in data.presets:
            preset = CameraPreset(
                camera_id=camera.id,
                preset_index=preset_data.preset_index,
                name=preset_data.name,
                description=preset_data.description,
            )
            db.add(preset)

    await db.commit()
    await db.refresh(camera)
    return camera


async def update_camera(db: AsyncSession, camera_id: int, data: CameraUpdate) -> Optional[Camera]:
    """更新摄像头（含预置位替换）"""
    result = await db.execute(select(Camera).where(Camera.id == camera_id))
    camera = result.scalar_one_or_none()
    if not camera:
        return None

    update_data = data.model_dump(exclude_unset=True, exclude={"presets"})
    for key, value in update_data.items():
        setattr(camera, key, value)

    # 如果提供了 presets，替换全部预置位
    if data.presets is not None:
        await db.execute(delete(CameraPreset).where(CameraPreset.camera_id == camera_id))
        for preset_data in data.presets:
            preset = CameraPreset(
                camera_id=camera_id,
                preset_index=preset_data.preset_index,
                name=preset_data.name,
                description=preset_data.description,
            )
            db.add(preset)

    await db.commit()
    await db.refresh(camera)
    return camera


async def delete_camera(db: AsyncSession, camera_id: int) -> bool:
    """删除摄像头（级联删除预置位）"""
    result = await db.execute(select(Camera).where(Camera.id == camera_id))
    camera = result.scalar_one_or_none()
    if not camera:
        return False

    # 删除预置位
    await db.execute(delete(CameraPreset).where(CameraPreset.camera_id == camera_id))
    await db.delete(camera)
    await db.commit()
    return True


async def get_camera(db: AsyncSession, camera_id: int) -> Optional[Dict[str, Any]]:
    """获取摄像头详情（含预置位和 NVR 名称）"""
    result = await db.execute(select(Camera).where(Camera.id == camera_id))
    camera = result.scalar_one_or_none()
    if not camera:
        return None

    # 获取预置位
    presets_result = await db.execute(
        select(CameraPreset).where(CameraPreset.camera_id == camera_id).order_by(CameraPreset.preset_index)
    )
    presets = presets_result.scalars().all()

    # 获取 NVR 名称
    nvr_name = None
    if camera.nvr_id:
        nvr_result = await db.execute(select(NVR.name).where(NVR.id == camera.nvr_id))
        nvr_name = nvr_result.scalar_one_or_none()

    return {
        "camera": camera,
        "presets": presets,
        "nvr_name": nvr_name,
    }


async def list_cameras(
    db: AsyncSession,
    nvr_id: Optional[int] = None,
    area_code: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    """摄像头列表（分页+筛选）"""
    query = select(Camera)
    count_query = select(func.count(Camera.id))

    if nvr_id is not None:
        query = query.where(Camera.nvr_id == nvr_id)
        count_query = count_query.where(Camera.nvr_id == nvr_id)
    if area_code:
        query = query.where(Camera.area_code == area_code)
        count_query = count_query.where(Camera.area_code == area_code)
    if status:
        query = query.where(Camera.status == status)
        count_query = count_query.where(Camera.status == status)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(desc(Camera.created_at))
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    cameras = result.scalars().all()

    # 批量获取 NVR 名称
    nvr_ids = {c.nvr_id for c in cameras if c.nvr_id}
    nvr_names: Dict[int, str] = {}
    if nvr_ids:
        nvr_result = await db.execute(select(NVR.id, NVR.name).where(NVR.id.in_(nvr_ids)))
        nvr_names = {row[0]: row[1] for row in nvr_result.all()}

    # 批量获取预置位
    camera_ids = [c.id for c in cameras]
    presets_map: Dict[int, List] = {cid: [] for cid in camera_ids}
    if camera_ids:
        presets_result = await db.execute(
            select(CameraPreset).where(CameraPreset.camera_id.in_(camera_ids)).order_by(CameraPreset.preset_index)
        )
        for preset in presets_result.scalars().all():
            presets_map[preset.camera_id].append(preset)

    return {
        "total": total,
        "cameras": cameras,
        "nvr_names": nvr_names,
        "presets_map": presets_map,
    }


async def get_cameras_by_area(db: AsyncSession, area_code: str) -> List[Camera]:
    """按区域查询摄像头（联动用）"""
    result = await db.execute(
        select(Camera).where(Camera.area_code == area_code, Camera.is_enabled == True).order_by(Camera.name)
    )
    return list(result.scalars().all())


async def get_cameras_by_device(db: AsyncSession, device_id: int) -> List[Camera]:
    """按设备查询摄像头（联动用）"""
    result = await db.execute(
        select(Camera).where(Camera.device_id == device_id, Camera.is_enabled == True).order_by(Camera.name)
    )
    return list(result.scalars().all())


# ========== VideoEvent 服务 ==========


async def create_video_event(
    db: AsyncSession,
    camera_id: int,
    event_type: str,
    trigger_source: str,
    alarm_id: Optional[int] = None,
    linkage_execution_id: Optional[int] = None,
    detail: Optional[str] = None,
    operator: Optional[str] = None,
) -> VideoEvent:
    """创建视频事件记录"""
    event = VideoEvent(
        camera_id=camera_id,
        event_type=event_type,
        trigger_source=trigger_source,
        alarm_id=alarm_id,
        linkage_execution_id=linkage_execution_id,
        detail=detail,
        operator=operator,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


async def list_video_events(
    db: AsyncSession,
    camera_id: Optional[int] = None,
    event_type: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    """视频事件列表（分页+筛选）"""
    query = select(VideoEvent)
    count_query = select(func.count(VideoEvent.id))

    if camera_id is not None:
        query = query.where(VideoEvent.camera_id == camera_id)
        count_query = count_query.where(VideoEvent.camera_id == camera_id)
    if event_type:
        query = query.where(VideoEvent.event_type == event_type)
        count_query = count_query.where(VideoEvent.event_type == event_type)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(desc(VideoEvent.created_at))
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()

    # 批量获取摄像头名称
    cam_ids = {e.camera_id for e in items}
    cam_names: Dict[int, str] = {}
    if cam_ids:
        cam_result = await db.execute(select(Camera.id, Camera.name).where(Camera.id.in_(cam_ids)))
        cam_names = {row[0]: row[1] for row in cam_result.all()}

    return {"total": total, "items": items, "cam_names": cam_names}


async def ptz_control(db: AsyncSession, camera_id: int, action: str, speed: int, operator: str) -> VideoEvent:
    """云台控制（模拟 ONVIF PTZ 命令）"""
    import json

    detail = json.dumps({"action": action, "speed": speed}, ensure_ascii=False)
    logger.info("PTZ 控制: camera=%d action=%s speed=%d operator=%s", camera_id, action, speed, operator)
    return await create_video_event(
        db,
        camera_id,
        "ptz_control",
        "manual",
        detail=detail,
        operator=operator,
    )


async def call_preset(db: AsyncSession, camera_id: int, preset_index: int, operator: str) -> VideoEvent:
    """调用预置位（模拟 ONVIF 预置位调用）"""
    import json

    detail = json.dumps({"preset_index": preset_index}, ensure_ascii=False)
    logger.info("预置位调用: camera=%d preset=%d operator=%s", camera_id, preset_index, operator)
    return await create_video_event(
        db,
        camera_id,
        "preset_call",
        "manual",
        detail=detail,
        operator=operator,
    )


async def start_recording(
    db: AsyncSession,
    camera_id: int,
    trigger_source: str,
    alarm_id: Optional[int] = None,
    linkage_execution_id: Optional[int] = None,
) -> VideoEvent:
    """开始录像（模拟 ONVIF 录像触发）"""
    import json

    detail = json.dumps({"action": "start"}, ensure_ascii=False)
    logger.info("开始录像: camera=%d source=%s alarm=%s", camera_id, trigger_source, alarm_id)
    return await create_video_event(
        db,
        camera_id,
        "recording_start",
        trigger_source,
        alarm_id=alarm_id,
        linkage_execution_id=linkage_execution_id,
        detail=detail,
    )


async def stop_recording(db: AsyncSession, camera_id: int) -> VideoEvent:
    """停止录像（模拟 ONVIF 录像停止）"""
    import json

    detail = json.dumps({"action": "stop"}, ensure_ascii=False)
    logger.info("停止录像: camera=%d", camera_id)
    return await create_video_event(
        db,
        camera_id,
        "recording_stop",
        "manual",
        detail=detail,
    )


# ========== 回放服务 (Story 10-4) ==========


async def get_playback_info(db: AsyncSession, alarm_id: int) -> Optional[Dict[str, Any]]:
    """获取告警回放信息（摄像头 + 时间定位）"""
    # 查询告警
    alarm_result = await db.execute(select(Alarm).where(Alarm.id == alarm_id))
    alarm = alarm_result.scalar_one_or_none()
    if not alarm:
        return None

    # 通过 Point 获取 device_id / area_code
    point_result = await db.execute(select(Point).where(Point.id == alarm.point_id))
    point = point_result.scalar_one_or_none()

    # 查找关联摄像头: device_id 优先，area_code 兜底
    cameras: List[Camera] = []
    if point and point.device_id:
        cameras = await get_cameras_by_device(db, point.device_id)
    if not cameras and point and point.area_code:
        cameras = await get_cameras_by_area(db, point.area_code)

    # 查找该告警关联的录像事件
    events_result = await db.execute(
        select(VideoEvent)
        .where(
            VideoEvent.alarm_id == alarm_id,
            VideoEvent.event_type.in_(["recording_start", "recording_stop"]),
        )
        .order_by(VideoEvent.created_at)
    )
    recording_events = list(events_result.scalars().all())

    # 批量获取摄像头名称
    cam_ids = {e.camera_id for e in recording_events}
    cam_names: Dict[int, str] = {}
    if cam_ids:
        cam_result = await db.execute(select(Camera.id, Camera.name).where(Camera.id.in_(cam_ids)))
        cam_names = {row[0]: row[1] for row in cam_result.all()}

    return {
        "alarm_info": {
            "id": alarm.id,
            "alarm_level": alarm.alarm_level,
            "alarm_message": alarm.alarm_message,
            "alarm_time": alarm.created_at,
        },
        "cameras": cameras,
        "recording_events": recording_events,
        "cam_names": cam_names,
        "playback_url_template": "{hls_url}?starttime={start}&endtime={end}",
    }


async def list_recording_segments(
    db: AsyncSession,
    camera_id: int,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    """查询录像片段列表（配对 start/stop 事件）"""
    from datetime import datetime as dt

    query = select(VideoEvent).where(
        VideoEvent.camera_id == camera_id,
        VideoEvent.event_type.in_(["recording_start", "recording_stop"]),
    )
    count_query = select(func.count(VideoEvent.id)).where(
        VideoEvent.camera_id == camera_id,
        VideoEvent.event_type.in_(["recording_start", "recording_stop"]),
    )

    if start_time:
        parsed_start = dt.fromisoformat(start_time)
        query = query.where(VideoEvent.created_at >= parsed_start)
        count_query = count_query.where(VideoEvent.created_at >= parsed_start)
    if end_time:
        parsed_end = dt.fromisoformat(end_time)
        query = query.where(VideoEvent.created_at <= parsed_end)
        count_query = count_query.where(VideoEvent.created_at <= parsed_end)

    total_result = await db.execute(count_query)
    total_result.scalar() or 0

    query = query.order_by(VideoEvent.created_at)
    result = await db.execute(query)
    events = list(result.scalars().all())

    # 配对 start/stop 事件为片段
    segments: List[Dict[str, Any]] = []
    # 获取摄像头名称
    cam_result = await db.execute(select(Camera.name).where(Camera.id == camera_id))
    camera_name = cam_result.scalar_one_or_none()

    pending_start = None
    for evt in events:
        if evt.event_type == "recording_start":
            if pending_start:
                # 前一个 start 没有 stop，生成无结束时间的片段
                segments.append(
                    {
                        "id": pending_start.id,
                        "camera_id": camera_id,
                        "camera_name": camera_name,
                        "start_time": pending_start.created_at,
                        "end_time": None,
                        "alarm_id": pending_start.alarm_id,
                        "duration_seconds": None,
                    }
                )
            pending_start = evt
        elif evt.event_type == "recording_stop" and pending_start:
            duration = None
            if pending_start.created_at and evt.created_at:
                duration = int((evt.created_at - pending_start.created_at).total_seconds())
            segments.append(
                {
                    "id": pending_start.id,
                    "camera_id": camera_id,
                    "camera_name": camera_name,
                    "start_time": pending_start.created_at,
                    "end_time": evt.created_at,
                    "alarm_id": pending_start.alarm_id,
                    "duration_seconds": duration,
                }
            )
            pending_start = None

    # 最后一个 start 没有 stop
    if pending_start:
        segments.append(
            {
                "id": pending_start.id,
                "camera_id": camera_id,
                "camera_name": camera_name,
                "start_time": pending_start.created_at,
                "end_time": None,
                "alarm_id": pending_start.alarm_id,
                "duration_seconds": None,
            }
        )

    # 分页
    start_idx = (page - 1) * page_size
    paged_segments = segments[start_idx : start_idx + page_size]

    return {"total": len(segments), "items": paged_segments}
