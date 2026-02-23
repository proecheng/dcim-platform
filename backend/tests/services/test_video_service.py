"""
视频监控服务测试

覆盖:
  - create_nvr / update_nvr / delete_nvr / get_nvr / list_nvrs: NVR CRUD
  - create_camera / delete_camera / get_camera / list_cameras: 摄像头 CRUD
  - create_video_event / list_video_events: 视频事件
  - ptz_control / call_preset / start_recording / stop_recording: 控制操作
"""

import pytest
import json

from app.services.video_service import (
    create_nvr,
    update_nvr,
    delete_nvr,
    get_nvr,
    list_nvrs,
    create_camera,
    delete_camera,
    get_camera,
    list_cameras,
    create_video_event,
    list_video_events,
    ptz_control,
    call_preset,
    start_recording,
    stop_recording,
    get_nvr_camera_count,
)
from app.schemas.video import NVRCreate, NVRUpdate, CameraCreate


class TestNVRService:
    """NVR 服务测试"""

    @pytest.mark.asyncio
    async def test_create_nvr(self, async_db):
        """创建 NVR"""
        data = NVRCreate(
            name="测试NVR",
            ip_address="192.168.1.100",
            port=554,
            manufacturer="hikvision",
        )
        nvr = await create_nvr(async_db, data)
        assert nvr.id is not None
        assert nvr.name == "测试NVR"
        assert nvr.ip_address == "192.168.1.100"

    @pytest.mark.asyncio
    async def test_update_nvr(self, async_db):
        """更新 NVR"""
        data = NVRCreate(name="原始NVR", ip_address="10.0.0.1")
        nvr = await create_nvr(async_db, data)

        update_data = NVRUpdate(name="更新后NVR", port=8554)
        updated = await update_nvr(async_db, nvr.id, update_data)
        assert updated is not None
        assert updated.name == "更新后NVR"
        assert updated.port == 8554

    @pytest.mark.asyncio
    async def test_update_nonexistent_nvr(self, async_db):
        """更新不存在的 NVR 返回 None"""
        update_data = NVRUpdate(name="不存在")
        result = await update_nvr(async_db, 99999, update_data)
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_nvr_success(self, async_db):
        """删除无关联摄像头的 NVR"""
        data = NVRCreate(name="待删除NVR", ip_address="10.0.0.2")
        nvr = await create_nvr(async_db, data)

        result = await delete_nvr(async_db, nvr.id)
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_nvr_with_cameras_raises(self, async_db):
        """删除有关联摄像头的 NVR 应抛出异常"""
        data = NVRCreate(name="有摄像头NVR", ip_address="10.0.0.3")
        nvr = await create_nvr(async_db, data)

        cam_data = CameraCreate(name="摄像头1", code="CAM-001", nvr_id=nvr.id)
        await create_camera(async_db, cam_data)

        with pytest.raises(ValueError, match="摄像头"):
            await delete_nvr(async_db, nvr.id)

    @pytest.mark.asyncio
    async def test_delete_nonexistent_nvr(self, async_db):
        """删除不存在的 NVR 返回 False"""
        result = await delete_nvr(async_db, 99999)
        assert result is False

    @pytest.mark.asyncio
    async def test_get_nvr(self, async_db):
        """获取 NVR 详情"""
        data = NVRCreate(name="查询NVR", ip_address="10.0.0.4")
        nvr = await create_nvr(async_db, data)

        found = await get_nvr(async_db, nvr.id)
        assert found is not None
        assert found.name == "查询NVR"

    @pytest.mark.asyncio
    async def test_list_nvrs(self, async_db):
        """NVR 列表分页"""
        for i in range(3):
            await create_nvr(async_db, NVRCreate(name=f"NVR-{i}", ip_address=f"10.0.0.{i + 10}"))

        result = await list_nvrs(async_db, page=1, page_size=2)
        assert result["total"] == 3
        assert len(result["items"]) == 2

    @pytest.mark.asyncio
    async def test_get_nvr_camera_count(self, async_db):
        """获取 NVR 关联摄像头数量"""
        nvr = await create_nvr(async_db, NVRCreate(name="计数NVR", ip_address="10.0.0.20"))
        count = await get_nvr_camera_count(async_db, nvr.id)
        assert count == 0


class TestCameraService:
    """摄像头服务测试"""

    @pytest.mark.asyncio
    async def test_create_camera(self, async_db):
        """创建摄像头"""
        data = CameraCreate(name="测试摄像头", code="CAM-TEST-001", camera_type="dome")
        camera = await create_camera(async_db, data)
        assert camera.id is not None
        assert camera.name == "测试摄像头"
        assert camera.code == "CAM-TEST-001"

    @pytest.mark.asyncio
    async def test_delete_camera(self, async_db):
        """删除摄像头"""
        data = CameraCreate(name="待删除摄像头", code="CAM-DEL-001")
        camera = await create_camera(async_db, data)

        result = await delete_camera(async_db, camera.id)
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_nonexistent_camera(self, async_db):
        """删除不存在的摄像头返回 False"""
        result = await delete_camera(async_db, 99999)
        assert result is False

    @pytest.mark.asyncio
    async def test_get_camera(self, async_db):
        """获取摄像头详情"""
        data = CameraCreate(name="查询摄像头", code="CAM-GET-001")
        camera = await create_camera(async_db, data)

        result = await get_camera(async_db, camera.id)
        assert result is not None
        assert result["camera"].name == "查询摄像头"
        assert isinstance(result["presets"], list)

    @pytest.mark.asyncio
    async def test_get_nonexistent_camera(self, async_db):
        """获取不存在的摄像头返回 None"""
        result = await get_camera(async_db, 99999)
        assert result is None

    @pytest.mark.asyncio
    async def test_list_cameras_pagination(self, async_db):
        """摄像头列表分页"""
        for i in range(5):
            await create_camera(async_db, CameraCreate(name=f"摄像头-{i}", code=f"CAM-LIST-{i:03d}"))

        result = await list_cameras(async_db, page=1, page_size=3)
        assert result["total"] == 5
        assert len(result["cameras"]) == 3


class TestVideoEventService:
    """视频事件服务测试"""

    @pytest.mark.asyncio
    async def test_create_video_event(self, async_db):
        """创建视频事件"""
        camera = await create_camera(async_db, CameraCreate(name="事件摄像头", code="CAM-EVT-001"))
        event = await create_video_event(
            async_db, camera_id=camera.id, event_type="ptz_control", trigger_source="manual"
        )
        assert event.id is not None
        assert event.event_type == "ptz_control"

    @pytest.mark.asyncio
    async def test_ptz_control(self, async_db):
        """PTZ 云台控制"""
        camera = await create_camera(async_db, CameraCreate(name="PTZ摄像头", code="CAM-PTZ-001"))
        event = await ptz_control(async_db, camera.id, action="pan_left", speed=5, operator="admin")
        assert event.event_type == "ptz_control"
        detail = json.loads(event.detail)
        assert detail["action"] == "pan_left"
        assert detail["speed"] == 5

    @pytest.mark.asyncio
    async def test_call_preset(self, async_db):
        """调用预置位"""
        camera = await create_camera(async_db, CameraCreate(name="预置位摄像头", code="CAM-PRE-001"))
        event = await call_preset(async_db, camera.id, preset_index=1, operator="admin")
        assert event.event_type == "preset_call"

    @pytest.mark.asyncio
    async def test_start_stop_recording(self, async_db):
        """开始和停止录像"""
        camera = await create_camera(async_db, CameraCreate(name="录像摄像头", code="CAM-REC-001"))
        start_evt = await start_recording(async_db, camera.id, trigger_source="alarm", alarm_id=1)
        assert start_evt.event_type == "recording_start"

        stop_evt = await stop_recording(async_db, camera.id)
        assert stop_evt.event_type == "recording_stop"

    @pytest.mark.asyncio
    async def test_list_video_events(self, async_db):
        """视频事件列表"""
        camera = await create_camera(async_db, CameraCreate(name="列表摄像头", code="CAM-LST-001"))
        await create_video_event(async_db, camera.id, "ptz_control", "manual")
        await create_video_event(async_db, camera.id, "recording_start", "alarm")

        result = await list_video_events(async_db, camera_id=camera.id)
        assert result["total"] == 2
        assert len(result["items"]) == 2
