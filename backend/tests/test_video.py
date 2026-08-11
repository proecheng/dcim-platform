"""视频监控 API 测试 — Story 10-1: 摄像头元数据管理"""

import pytest

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import delete

from app.core.database import Base
from app.models.device import Device
from app.models.video import NVR, Camera, CameraPreset, VideoEvent
from app.models.user import User
from app.models.alarm import Alarm
from app.models.point import Point
from app.api.deps import (
    SiteAccessContext,
    enforce_inventory_authorization,
    get_db,
    get_site_access_context,
    require_admin,
    require_operator,
    require_viewer,
)


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture(scope="module")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="module")
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture(scope="module")
def session_factory(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
async def db_session(session_factory):
    async with session_factory() as session:
        await session.execute(delete(VideoEvent))
        await session.execute(delete(CameraPreset))
        await session.execute(delete(Camera))
        await session.execute(delete(NVR))
        await session.execute(delete(Alarm))
        await session.execute(delete(Point))
        await session.execute(delete(Device))
        await session.commit()
        yield session


@pytest.fixture
def mock_admin():
    user = User()
    user.id = 1
    user.username = "test_admin"
    user.role = "admin"
    user.is_active = True
    return user


@pytest.fixture
async def app(db_session, mock_admin):
    from app.main import app as _app

    async def override_get_db():
        yield db_session

    async def override_require_admin():
        return mock_admin

    async def override_require_operator():
        return mock_admin

    async def override_require_viewer():
        return mock_admin

    async def override_inventory_authorization():
        return None

    async def override_site_access_context():
        return SiteAccessContext(user_id=mock_admin.id, role="admin", jti="video-test-jti", site_ids=None)

    _app.dependency_overrides[get_db] = override_get_db
    _app.dependency_overrides[require_admin] = override_require_admin
    _app.dependency_overrides[require_operator] = override_require_operator
    _app.dependency_overrides[require_viewer] = override_require_viewer
    _app.dependency_overrides[enforce_inventory_authorization] = override_inventory_authorization
    _app.dependency_overrides[get_site_access_context] = override_site_access_context
    yield _app
    _app.dependency_overrides.clear()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ============================================================
# Constants
# ============================================================

BASE_URL = "/api/v1/video"


# ============================================================
# Helpers
# ============================================================


async def _create_nvr(session: AsyncSession, name: str, ip: str) -> NVR:
    """直接在 DB 创建 NVR"""
    nvr = NVR(name=name, ip_address=ip, port=554, username="admin", password="pass123")
    session.add(nvr)
    await session.flush()
    return nvr


async def _create_camera(
    session: AsyncSession,
    code: str,
    name: str,
    nvr_id: int = None,
    area_code: str = None,
    device_id: int = None,
    status: str = "unknown",
) -> Camera:
    """直接在 DB 创建 Camera"""
    camera = Camera(
        name=name,
        code=code,
        nvr_id=nvr_id,
        area_code=area_code,
        device_id=device_id,
        status=status,
        is_enabled=True,
    )
    session.add(camera)
    await session.flush()
    return camera


# ============================================================
# Tests — NVR CRUD
# ============================================================


@pytest.mark.anyio
async def test_create_nvr(client):
    """POST /nvrs 创建 NVR，验证响应字段和密码掩码"""
    payload = {
        "name": "测试NVR-1",
        "ip_address": "192.168.1.100",
        "port": 554,
        "username": "admin",
        "password": "secret123",
        "manufacturer": "hikvision",
        "max_channels": 32,
    }
    resp = await client.post(f"{BASE_URL}/nvrs", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "测试NVR-1"
    assert data["ip_address"] == "192.168.1.100"
    assert data["password_masked"] == "***"
    assert data["manufacturer"] == "hikvision"
    assert data["max_channels"] == 32
    assert "id" in data


@pytest.mark.anyio
async def test_list_nvrs(client, db_session):
    """GET /nvrs 列表，验证分页"""
    await _create_nvr(db_session, "NVR-A", "10.0.0.1")
    await _create_nvr(db_session, "NVR-B", "10.0.0.2")
    await db_session.commit()

    resp = await client.get(f"{BASE_URL}/nvrs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2


@pytest.mark.anyio
async def test_get_nvr(client, db_session):
    """GET /nvrs/{id} 获取详情"""
    nvr = await _create_nvr(db_session, "NVR-Detail", "10.0.1.1")
    await db_session.commit()

    resp = await client.get(f"{BASE_URL}/nvrs/{nvr.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == nvr.id
    assert data["name"] == "NVR-Detail"
    assert data["ip_address"] == "10.0.1.1"


@pytest.mark.anyio
async def test_update_nvr(client, db_session):
    """PUT /nvrs/{id} 更新 NVR"""
    nvr = await _create_nvr(db_session, "NVR-Old", "10.0.2.1")
    await db_session.commit()

    resp = await client.put(
        f"{BASE_URL}/nvrs/{nvr.id}",
        json={
            "name": "NVR-Updated",
            "ip_address": "10.0.2.2",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "NVR-Updated"
    assert data["ip_address"] == "10.0.2.2"


@pytest.mark.anyio
async def test_delete_nvr(client, db_session):
    """DELETE /nvrs/{id} 删除 NVR，再 GET 返回 404"""
    nvr = await _create_nvr(db_session, "NVR-Del", "10.0.3.1")
    await db_session.commit()

    resp = await client.delete(f"{BASE_URL}/nvrs/{nvr.id}")
    assert resp.status_code == 200

    resp2 = await client.get(f"{BASE_URL}/nvrs/{nvr.id}")
    assert resp2.status_code == 404


@pytest.mark.anyio
async def test_delete_nvr_with_cameras(client, db_session):
    """DELETE /nvrs/{id} 有关联摄像头时返回 400"""
    nvr = await _create_nvr(db_session, "NVR-Protected", "10.0.4.1")
    await db_session.flush()
    await _create_camera(db_session, "CAM-PROT-001", "保护摄像头", nvr_id=nvr.id)
    await db_session.commit()

    resp = await client.delete(f"{BASE_URL}/nvrs/{nvr.id}")
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_nvr_not_found(client):
    """GET /nvrs/999 不存在返回 404"""
    resp = await client.get(f"{BASE_URL}/nvrs/999")
    assert resp.status_code == 404


# ============================================================
# Tests — Camera CRUD
# ============================================================


@pytest.mark.anyio
async def test_create_camera(client, db_session):
    """POST /cameras 创建摄像头（含预置位）"""
    nvr = await _create_nvr(db_session, "NVR-Cam", "10.1.0.1")
    await db_session.commit()

    payload = {
        "name": "大厅摄像头",
        "code": "CAM-HALL-001",
        "rtsp_url": "rtsp://10.1.0.1/ch1",
        "nvr_id": nvr.id,
        "channel_no": 1,
        "area_code": "A1",
        "camera_type": "dome",
        "presets": [
            {"preset_index": 1, "name": "入口", "description": "大厅入口"},
            {"preset_index": 2, "name": "出口"},
        ],
    }
    resp = await client.post(f"{BASE_URL}/cameras", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "大厅摄像头"
    assert data["code"] == "CAM-HALL-001"
    assert data["nvr_id"] == nvr.id
    assert len(data["presets"]) == 2
    assert data["presets"][0]["name"] == "入口"


@pytest.mark.anyio
async def test_list_cameras(client, db_session):
    """GET /cameras 列表"""
    await _create_camera(db_session, "CAM-LIST-001", "摄像头1")
    await _create_camera(db_session, "CAM-LIST-002", "摄像头2")
    await db_session.commit()

    resp = await client.get(f"{BASE_URL}/cameras")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2


@pytest.mark.anyio
async def test_get_camera(client, db_session):
    """GET /cameras/{id} 详情含预置位"""
    camera = await _create_camera(db_session, "CAM-GET-001", "详情摄像头")
    await db_session.flush()
    preset = CameraPreset(camera_id=camera.id, preset_index=1, name="预置位1")
    db_session.add(preset)
    await db_session.commit()

    resp = await client.get(f"{BASE_URL}/cameras/{camera.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == camera.id
    assert data["code"] == "CAM-GET-001"
    assert len(data["presets"]) == 1
    assert data["presets"][0]["name"] == "预置位1"


@pytest.mark.anyio
async def test_update_camera(client, db_session):
    """PUT /cameras/{id} 更新摄像头及预置位替换"""
    camera = await _create_camera(db_session, "CAM-UPD-001", "旧名称")
    await db_session.flush()
    old_preset = CameraPreset(camera_id=camera.id, preset_index=1, name="旧预置位")
    db_session.add(old_preset)
    await db_session.commit()

    resp = await client.put(
        f"{BASE_URL}/cameras/{camera.id}",
        json={
            "name": "新名称",
            "presets": [
                {"preset_index": 1, "name": "新预置位A"},
                {"preset_index": 2, "name": "新预置位B"},
            ],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "新名称"
    assert len(data["presets"]) == 2
    preset_names = {p["name"] for p in data["presets"]}
    assert "新预置位A" in preset_names
    assert "新预置位B" in preset_names


@pytest.mark.anyio
async def test_delete_camera(client, db_session):
    """DELETE /cameras/{id} 删除摄像头"""
    camera = await _create_camera(db_session, "CAM-DEL-001", "待删除")
    await db_session.commit()

    resp = await client.delete(f"{BASE_URL}/cameras/{camera.id}")
    assert resp.status_code == 200

    resp2 = await client.get(f"{BASE_URL}/cameras/{camera.id}")
    assert resp2.status_code == 404


# ============================================================
# Tests — Camera Filtering
# ============================================================


@pytest.mark.anyio
async def test_filter_cameras_by_nvr(client, db_session):
    """GET /cameras?nvr_id= 按 NVR 筛选"""
    nvr1 = await _create_nvr(db_session, "NVR-F1", "10.2.0.1")
    nvr2 = await _create_nvr(db_session, "NVR-F2", "10.2.0.2")
    await db_session.flush()
    await _create_camera(db_session, "CAM-FN-001", "摄像头A", nvr_id=nvr1.id)
    await _create_camera(db_session, "CAM-FN-002", "摄像头B", nvr_id=nvr2.id)
    await db_session.commit()

    resp = await client.get(f"{BASE_URL}/cameras", params={"nvr_id": nvr1.id})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["nvr_id"] == nvr1.id


@pytest.mark.anyio
async def test_filter_cameras_by_area(client, db_session):
    """GET /cameras?area_code= 按区域筛选"""
    await _create_camera(db_session, "CAM-FA-001", "A区摄像头", area_code="A1")
    await _create_camera(db_session, "CAM-FA-002", "B区摄像头", area_code="B1")
    await db_session.commit()

    resp = await client.get(f"{BASE_URL}/cameras", params={"area_code": "A1"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["area_code"] == "A1"


@pytest.mark.anyio
async def test_filter_cameras_by_status(client, db_session):
    """GET /cameras?status= 按状态筛选"""
    await _create_camera(db_session, "CAM-FS-001", "在线摄像头", status="online")
    await _create_camera(db_session, "CAM-FS-002", "离线摄像头", status="offline")
    await db_session.commit()

    resp = await client.get(f"{BASE_URL}/cameras", params={"status": "online"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["status"] == "online"


# ============================================================
# Tests — Camera by Area / Device
# ============================================================


@pytest.mark.anyio
async def test_get_cameras_by_area(client, db_session):
    """GET /cameras/by-area/{area_code} 按区域联动查询"""
    await _create_camera(db_session, "CAM-BA-001", "A2摄像头1", area_code="A2")
    await _create_camera(db_session, "CAM-BA-002", "A2摄像头2", area_code="A2")
    await _create_camera(db_session, "CAM-BA-003", "B2摄像头", area_code="B2")
    await db_session.commit()

    resp = await client.get(f"{BASE_URL}/cameras/by-area/A2")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    for cam in data:
        assert cam["area_code"] == "A2"


@pytest.mark.anyio
async def test_get_cameras_by_device(client, db_session):
    """GET /cameras/by-device/{device_id} 按设备联动查询"""
    device_a = Device(device_code="DEV-CAM-100", device_name="设备100", device_type="CAM", area_code="A1")
    device_b = Device(device_code="DEV-CAM-200", device_name="设备200", device_type="CAM", area_code="A2")
    db_session.add_all([device_a, device_b])
    await db_session.flush()
    await _create_camera(db_session, "CAM-BD-001", "设备100摄像头", device_id=device_a.id)
    await _create_camera(db_session, "CAM-BD-002", "设备200摄像头", device_id=device_b.id)
    await db_session.commit()

    resp = await client.get(f"{BASE_URL}/cameras/by-device/{device_a.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["device_id"] == device_a.id


# ============================================================
# Tests — Preset Management
# ============================================================


@pytest.mark.anyio
async def test_camera_presets_management(client, db_session):
    """创建摄像头含预置位，更新时替换旧预置位"""
    # 创建含预置位的摄像头
    payload = {
        "name": "预置位测试摄像头",
        "code": "CAM-PRESET-001",
        "camera_type": "ptz",
        "presets": [
            {"preset_index": 1, "name": "原始位1"},
            {"preset_index": 2, "name": "原始位2"},
        ],
    }
    resp = await client.post(f"{BASE_URL}/cameras", json=payload)
    assert resp.status_code == 200
    cam_id = resp.json()["id"]
    assert len(resp.json()["presets"]) == 2

    # 更新为新预置位，旧的应被替换
    resp2 = await client.put(
        f"{BASE_URL}/cameras/{cam_id}",
        json={
            "presets": [
                {"preset_index": 1, "name": "替换位1"},
                {"preset_index": 2, "name": "替换位2"},
                {"preset_index": 3, "name": "替换位3"},
            ],
        },
    )
    assert resp2.status_code == 200
    data = resp2.json()
    assert len(data["presets"]) == 3
    preset_names = {p["name"] for p in data["presets"]}
    assert "原始位1" not in preset_names
    assert "替换位1" in preset_names
    assert "替换位3" in preset_names


# ============================================================
# Helpers — Alarm/Point
# ============================================================


async def _create_point(session, point_code="AI_TH_A1_001", area_code="A1", device_id=None):
    """创建测试点位"""
    point = Point(
        point_code=point_code,
        point_name=f"测试点位-{point_code}",
        point_type="AI",
        area_code=area_code,
        device_type="TH",
        device_id=device_id,
        is_enabled=True,
    )
    session.add(point)
    await session.flush()
    return point


async def _create_alarm(session, point_id):
    """创建测试告警"""
    alarm = Alarm(
        alarm_no=f"ALM-TEST-{point_id}",
        point_id=point_id,
        alarm_level="major",
        alarm_message="测试告警",
    )
    session.add(alarm)
    await session.flush()
    return alarm


# ============================================================
# Tests — GET /cameras/by-alarm/{alarm_id} (Story 10-2)
# ============================================================


@pytest.mark.anyio
async def test_get_cameras_by_alarm_with_device(client, db_session):
    """告警关联设备有摄像头时返回摄像头列表"""
    # 创建点位（关联 device_id=100）
    point = await _create_point(db_session, "AI_TH_A1_010", "A1", device_id=100)
    alarm = await _create_alarm(db_session, point.id)
    # 创建摄像头关联到 device_id=100
    await _create_camera(db_session, "CAM-DEV-100", "设备摄像头", device_id=100)
    await db_session.commit()

    resp = await client.get(f"{BASE_URL}/cameras/by-alarm/{alarm.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["code"] == "CAM-DEV-100"


@pytest.mark.anyio
async def test_get_cameras_by_alarm_with_area(client, db_session):
    """告警无设备关联但有区域摄像头时返回区域摄像头"""
    # 创建点位（无 device_id，有 area_code=B1）
    point = await _create_point(db_session, "AI_TH_B1_001", "B1", device_id=None)
    alarm = await _create_alarm(db_session, point.id)
    # 创建区域摄像头
    await _create_camera(db_session, "CAM-AREA-B1", "B1区域摄像头", area_code="B1")
    await db_session.commit()

    resp = await client.get(f"{BASE_URL}/cameras/by-alarm/{alarm.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["code"] == "CAM-AREA-B1"


@pytest.mark.anyio
async def test_get_cameras_by_alarm_not_found(client):
    """告警不存在返回 404"""
    resp = await client.get(f"{BASE_URL}/cameras/by-alarm/99999")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_get_cameras_by_alarm_no_cameras(client, db_session):
    """告警存在但无关联摄像头返回空列表"""
    point = await _create_point(db_session, "AI_TH_C1_001", "C1", device_id=None)
    alarm = await _create_alarm(db_session, point.id)
    await db_session.commit()

    resp = await client.get(f"{BASE_URL}/cameras/by-alarm/{alarm.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 0


# ============================================================
# Tests — PTZ / Recording / Events (Story 10-3)
# ============================================================


@pytest.mark.anyio
async def test_ptz_control(client, db_session):
    """POST /ptz/control 云台控制"""
    cam = await _create_camera(db_session, "CAM-PTZ-001", "PTZ测试摄像头")
    await db_session.commit()
    resp = await client.post(f"{BASE_URL}/ptz/control", json={"camera_id": cam.id, "action": "up", "speed": 5})
    assert resp.status_code == 200
    data = resp.json()
    assert data["event_type"] == "ptz_control"
    assert data["trigger_source"] == "manual"
    assert data["camera_name"] == "PTZ测试摄像头"


@pytest.mark.anyio
async def test_call_preset(client, db_session):
    """POST /ptz/preset 调用预置位"""
    cam = await _create_camera(db_session, "CAM-PRESET-001", "预置位测试")
    await db_session.commit()
    resp = await client.post(f"{BASE_URL}/ptz/preset", json={"camera_id": cam.id, "preset_index": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert data["event_type"] == "preset_call"


@pytest.mark.anyio
async def test_start_recording(client, db_session):
    """POST /recording/start 开始录像"""
    cam = await _create_camera(db_session, "CAM-REC-001", "录像测试")
    await db_session.commit()
    resp = await client.post(f"{BASE_URL}/recording/start", json={"camera_id": cam.id})
    assert resp.status_code == 200
    data = resp.json()
    assert data["event_type"] == "recording_start"
    assert data["trigger_source"] == "manual"


@pytest.mark.anyio
async def test_stop_recording(client, db_session):
    """POST /recording/stop 停止录像"""
    cam = await _create_camera(db_session, "CAM-STOP-001", "停止录像测试")
    await db_session.commit()
    resp = await client.post(f"{BASE_URL}/recording/stop", json={"camera_id": cam.id})
    assert resp.status_code == 200
    data = resp.json()
    assert data["event_type"] == "recording_stop"


@pytest.mark.anyio
async def test_list_video_events(client, db_session):
    """GET /events 视频事件列表"""
    cam = await _create_camera(db_session, "CAM-EVT-001", "事件测试")
    await db_session.commit()
    # 创建几个事件
    await client.post(f"{BASE_URL}/ptz/control", json={"camera_id": cam.id, "action": "up"})
    await client.post(f"{BASE_URL}/recording/start", json={"camera_id": cam.id})
    resp = await client.get(f"{BASE_URL}/events")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2


@pytest.mark.anyio
async def test_list_video_events_filter(client, db_session):
    """GET /events 按类型筛选"""
    cam = await _create_camera(db_session, "CAM-FLT-001", "筛选测试")
    await db_session.commit()
    await client.post(f"{BASE_URL}/ptz/control", json={"camera_id": cam.id, "action": "left"})
    await client.post(f"{BASE_URL}/recording/start", json={"camera_id": cam.id})
    resp = await client.get(f"{BASE_URL}/events", params={"event_type": "ptz_control"})
    assert resp.status_code == 200
    data = resp.json()
    for item in data["items"]:
        assert item["event_type"] == "ptz_control"


# ============================================================
# Tests — Playback API (Story 10-4)
# ============================================================


@pytest.mark.anyio
async def test_get_playback_info(client, db_session):
    """测试获取告警回放信息"""
    # 创建点位（关联 device_id=1）
    point = await _create_point(db_session, "PT-PLAY-001", "AREA-A", device_id=1)
    alarm = await _create_alarm(db_session, point.id)
    # 创建摄像头（关联 device_id=1）
    await _create_camera(db_session, "CAM-PLAY-001", "回放测试摄像头", device_id=1)
    await db_session.commit()

    resp = await client.get(f"{BASE_URL}/playback/alarm/{alarm.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["alarm_info"]["id"] == alarm.id
    assert data["alarm_info"]["alarm_level"] == "major"
    assert data["alarm_info"]["alarm_message"] == "测试告警"
    assert len(data["cameras"]) >= 1
    assert data["cameras"][0]["code"] == "CAM-PLAY-001"
    assert "playback_url_template" in data


@pytest.mark.anyio
async def test_get_playback_info_not_found(client):
    """测试告警不存在时返回404"""
    resp = await client.get(f"{BASE_URL}/playback/alarm/99999")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_list_recording_segments(client, db_session):
    """测试查询录像片段列表"""
    # 创建摄像头
    camera = await _create_camera(db_session, "CAM-SEG-001", "片段测试摄像头")
    await db_session.flush()

    # 创建 recording_start 和 recording_stop 事件
    import json

    start_evt = VideoEvent(
        camera_id=camera.id,
        event_type="recording_start",
        trigger_source="manual",
        detail=json.dumps({"action": "start"}),
    )
    db_session.add(start_evt)
    await db_session.flush()

    stop_evt = VideoEvent(
        camera_id=camera.id,
        event_type="recording_stop",
        trigger_source="manual",
        detail=json.dumps({"action": "stop"}),
    )
    db_session.add(stop_evt)
    await db_session.commit()

    resp = await client.get(f"{BASE_URL}/playback/segments", params={"camera_id": camera.id})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert len(data["items"]) >= 1
    seg = data["items"][0]
    assert seg["camera_id"] == camera.id
    assert seg["start_time"] is not None


@pytest.mark.anyio
async def test_list_recording_segments_empty(client, db_session):
    """测试无录像片段返回空列表"""
    camera = await _create_camera(db_session, "CAM-EMPTY-001", "空片段摄像头")
    await db_session.commit()

    resp = await client.get(f"{BASE_URL}/playback/segments", params={"camera_id": camera.id})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []
