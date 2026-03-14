"""
网关/视频/OTA 模块覆盖率测试
gateways.py / video.py / ota.py
"""

import pytest
from tests.conftest import auth_headers


# ==================== Gateway Tests ====================


GATEWAY_PREFIX = "/api/v1/gateways"

GATEWAY_PAYLOAD = {
    "gateway_id": "gw-test-001",
    "name": "测试网关",
    "ip_address": "192.168.1.100",
    "version": "1.0.0",
    "is_enabled": True,
}


@pytest.mark.asyncio
class TestGatewayList:
    """网关列表"""

    async def test_list_empty(self, client, admin_user):
        _, token = admin_user
        resp = await client.get(GATEWAY_PREFIX, headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    async def test_list_no_auth(self, client):
        resp = await client.get(GATEWAY_PREFIX)
        assert resp.status_code in (401, 403)

    async def test_list_with_filters(self, client, admin_user):
        _, token = admin_user
        resp = await client.get(
            GATEWAY_PREFIX,
            params={"status": "online", "keyword": "notexist"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 0


@pytest.mark.asyncio
class TestGatewaySummary:
    """网关状态汇总"""

    async def test_summary_empty(self, client, admin_user):
        _, token = admin_user
        resp = await client.get(f"{GATEWAY_PREFIX}/summary", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["online"] == 0
        assert data["offline"] == 0

    async def test_summary_no_auth(self, client):
        resp = await client.get(f"{GATEWAY_PREFIX}/summary")
        assert resp.status_code in (401, 403)


@pytest.mark.asyncio
class TestGatewayCRUD:
    """网关增删改查"""

    async def test_create_gateway(self, client, admin_user):
        _, token = admin_user
        resp = await client.post(GATEWAY_PREFIX, json=GATEWAY_PAYLOAD, headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "测试网关"
        assert data["gateway_id"] == "gw-test-001"
        assert "id" in data

    async def test_create_duplicate_gateway_id(self, client, admin_user):
        _, token = admin_user
        await client.post(GATEWAY_PREFIX, json=GATEWAY_PAYLOAD, headers=auth_headers(token))
        resp = await client.post(GATEWAY_PREFIX, json=GATEWAY_PAYLOAD, headers=auth_headers(token))
        assert resp.status_code == 400

    async def test_create_no_auth(self, client):
        resp = await client.post(GATEWAY_PREFIX, json=GATEWAY_PAYLOAD)
        assert resp.status_code in (401, 403)

    async def test_create_viewer_forbidden(self, client, viewer_user):
        _, token = viewer_user
        resp = await client.post(GATEWAY_PREFIX, json=GATEWAY_PAYLOAD, headers=auth_headers(token))
        assert resp.status_code == 403

    async def test_get_gateway_detail(self, client, admin_user):
        _, token = admin_user
        create_resp = await client.post(GATEWAY_PREFIX, json=GATEWAY_PAYLOAD, headers=auth_headers(token))
        gw_id = create_resp.json()["id"]
        resp = await client.get(f"{GATEWAY_PREFIX}/{gw_id}", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "测试网关"
        assert data["datasource_count"] == 0
        assert data["point_count"] == 0

    async def test_get_gateway_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.get(f"{GATEWAY_PREFIX}/99999", headers=auth_headers(token))
        assert resp.status_code == 404

    async def test_update_gateway(self, client, admin_user):
        _, token = admin_user
        create_resp = await client.post(GATEWAY_PREFIX, json=GATEWAY_PAYLOAD, headers=auth_headers(token))
        gw_id = create_resp.json()["id"]
        resp = await client.put(
            f"{GATEWAY_PREFIX}/{gw_id}",
            json={"name": "更新后网关", "status": "online"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "更新后网关"

    async def test_update_gateway_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.put(
            f"{GATEWAY_PREFIX}/99999",
            json={"name": "不存在"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_delete_gateway(self, client, admin_user):
        _, token = admin_user
        create_resp = await client.post(GATEWAY_PREFIX, json=GATEWAY_PAYLOAD, headers=auth_headers(token))
        gw_id = create_resp.json()["id"]
        resp = await client.delete(f"{GATEWAY_PREFIX}/{gw_id}", headers=auth_headers(token))
        assert resp.status_code == 200
        # 确认已删除
        get_resp = await client.get(f"{GATEWAY_PREFIX}/{gw_id}", headers=auth_headers(token))
        assert get_resp.status_code == 404

    async def test_delete_gateway_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.delete(f"{GATEWAY_PREFIX}/99999", headers=auth_headers(token))
        assert resp.status_code == 404

    async def test_delete_viewer_forbidden(self, client, viewer_user):
        _, token = viewer_user
        resp = await client.delete(f"{GATEWAY_PREFIX}/1", headers=auth_headers(token))
        assert resp.status_code == 403


@pytest.mark.asyncio
class TestGatewayEvents:
    """网关事件"""

    async def test_events_for_existing_gateway(self, client, admin_user):
        _, token = admin_user
        create_resp = await client.post(GATEWAY_PREFIX, json=GATEWAY_PAYLOAD, headers=auth_headers(token))
        gw_id = create_resp.json()["id"]
        resp = await client.get(f"{GATEWAY_PREFIX}/{gw_id}/events", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["total"] == 0
        assert resp.json()["items"] == []

    async def test_events_gateway_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.get(f"{GATEWAY_PREFIX}/99999/events", headers=auth_headers(token))
        assert resp.status_code == 404

    async def test_events_no_auth(self, client):
        resp = await client.get(f"{GATEWAY_PREFIX}/1/events")
        assert resp.status_code in (401, 403)


@pytest.mark.asyncio
class TestGatewayConfigHistory:
    """网关配置下发历史"""

    async def test_config_history_existing(self, client, admin_user):
        _, token = admin_user
        create_resp = await client.post(GATEWAY_PREFIX, json=GATEWAY_PAYLOAD, headers=auth_headers(token))
        gw_id = create_resp.json()["id"]
        resp = await client.get(f"{GATEWAY_PREFIX}/{gw_id}/config-history", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    async def test_config_history_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.get(f"{GATEWAY_PREFIX}/99999/config-history", headers=auth_headers(token))
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestGatewayPushConfig:
    """配置下发（预期 503 因为 MQTT 未连接）"""

    async def test_push_config_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.post(f"{GATEWAY_PREFIX}/99999/push-config", headers=auth_headers(token))
        assert resp.status_code == 404

    async def test_push_config_no_auth(self, client):
        resp = await client.post(f"{GATEWAY_PREFIX}/1/push-config")
        assert resp.status_code in (401, 403)

    async def test_push_config_mqtt_unavailable(self, client, admin_user):
        """推送配置时 MQTT 未连接 → 503"""
        _, token = admin_user
        create_resp = await client.post(GATEWAY_PREFIX, json=GATEWAY_PAYLOAD, headers=auth_headers(token))
        gw_id = create_resp.json()["id"]
        resp = await client.post(f"{GATEWAY_PREFIX}/{gw_id}/push-config", headers=auth_headers(token))
        # MQTT 未连接时返回 503
        assert resp.status_code == 503


@pytest.mark.asyncio
class TestGatewayAssignSite:
    """网关站点分配"""

    async def test_assign_site_gateway_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.put(
            f"{GATEWAY_PREFIX}/99999/site",
            json={"site_id": 1},
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_assign_site_no_auth(self, client):
        resp = await client.put(f"{GATEWAY_PREFIX}/1/site", json={"site_id": 1})
        assert resp.status_code in (401, 403)

    async def test_assign_site_operator_forbidden(self, client, operator_user):
        """站点分配仅管理员可用"""
        _, token = operator_user
        resp = await client.put(
            f"{GATEWAY_PREFIX}/1/site",
            json={"site_id": 1},
            headers=auth_headers(token),
        )
        assert resp.status_code == 403


# ==================== Video / NVR Tests ====================


VIDEO_PREFIX = "/api/v1/video"

NVR_PAYLOAD = {
    "name": "测试NVR",
    "ip_address": "192.168.1.200",
    "port": 554,
    "username": "admin",
    "password": "pass123",
    "manufacturer": "Hikvision",
    "model": "DS-7608NI",
    "max_channels": 8,
    "description": "测试用NVR",
}

CAMERA_PAYLOAD = {
    "name": "测试摄像头",
    "code": "CAM-TEST-001",
    "rtsp_url": "rtsp://192.168.1.200:554/stream1",
    "camera_type": "dome",
    "area_code": "A-01",
    "location_description": "机房入口",
}


@pytest.mark.asyncio
class TestNVRList:
    """NVR 列表"""

    async def test_list_nvrs_empty(self, client, admin_user):
        _, token = admin_user
        resp = await client.get(f"{VIDEO_PREFIX}/nvrs", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    async def test_list_nvrs_no_auth(self, client):
        resp = await client.get(f"{VIDEO_PREFIX}/nvrs")
        assert resp.status_code in (401, 403)


@pytest.mark.asyncio
class TestNVRCRUD:
    """NVR 增删改查"""

    async def test_create_nvr(self, client, admin_user):
        _, token = admin_user
        resp = await client.post(f"{VIDEO_PREFIX}/nvrs", json=NVR_PAYLOAD, headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "测试NVR"
        assert data["password_masked"] == "***"
        assert "id" in data

    async def test_create_nvr_no_auth(self, client):
        resp = await client.post(f"{VIDEO_PREFIX}/nvrs", json=NVR_PAYLOAD)
        assert resp.status_code in (401, 403)

    async def test_create_nvr_viewer_forbidden(self, client, viewer_user):
        _, token = viewer_user
        resp = await client.post(f"{VIDEO_PREFIX}/nvrs", json=NVR_PAYLOAD, headers=auth_headers(token))
        assert resp.status_code == 403

    async def test_get_nvr_detail(self, client, admin_user):
        _, token = admin_user
        create_resp = await client.post(f"{VIDEO_PREFIX}/nvrs", json=NVR_PAYLOAD, headers=auth_headers(token))
        nvr_id = create_resp.json()["id"]
        resp = await client.get(f"{VIDEO_PREFIX}/nvrs/{nvr_id}", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["name"] == "测试NVR"

    async def test_get_nvr_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.get(f"{VIDEO_PREFIX}/nvrs/99999", headers=auth_headers(token))
        assert resp.status_code == 404

    async def test_update_nvr(self, client, admin_user):
        _, token = admin_user
        create_resp = await client.post(f"{VIDEO_PREFIX}/nvrs", json=NVR_PAYLOAD, headers=auth_headers(token))
        nvr_id = create_resp.json()["id"]
        resp = await client.put(
            f"{VIDEO_PREFIX}/nvrs/{nvr_id}",
            json={"name": "更新后NVR", "max_channels": 16},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "更新后NVR"

    async def test_update_nvr_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.put(
            f"{VIDEO_PREFIX}/nvrs/99999",
            json={"name": "不存在"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_delete_nvr(self, client, admin_user):
        _, token = admin_user
        create_resp = await client.post(f"{VIDEO_PREFIX}/nvrs", json=NVR_PAYLOAD, headers=auth_headers(token))
        nvr_id = create_resp.json()["id"]
        resp = await client.delete(f"{VIDEO_PREFIX}/nvrs/{nvr_id}", headers=auth_headers(token))
        assert resp.status_code == 200
        # 确认已删除
        get_resp = await client.get(f"{VIDEO_PREFIX}/nvrs/{nvr_id}", headers=auth_headers(token))
        assert get_resp.status_code == 404

    async def test_delete_nvr_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.delete(f"{VIDEO_PREFIX}/nvrs/99999", headers=auth_headers(token))
        assert resp.status_code == 404


# ==================== Video / Camera Tests ====================


@pytest.mark.asyncio
class TestCameraList:
    """摄像头列表"""

    async def test_list_cameras_empty(self, client, admin_user):
        _, token = admin_user
        resp = await client.get(f"{VIDEO_PREFIX}/cameras", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    async def test_list_cameras_with_filters(self, client, admin_user):
        _, token = admin_user
        resp = await client.get(
            f"{VIDEO_PREFIX}/cameras",
            params={"status": "offline", "area_code": "Z-99"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    async def test_list_cameras_no_auth(self, client):
        resp = await client.get(f"{VIDEO_PREFIX}/cameras")
        assert resp.status_code in (401, 403)


@pytest.mark.asyncio
class TestCameraCRUD:
    """摄像头增删改查"""

    async def test_create_camera(self, client, admin_user):
        _, token = admin_user
        resp = await client.post(f"{VIDEO_PREFIX}/cameras", json=CAMERA_PAYLOAD, headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "测试摄像头"
        assert data["code"] == "CAM-TEST-001"

    async def test_create_camera_with_presets(self, client, admin_user):
        _, token = admin_user
        payload = {
            **CAMERA_PAYLOAD,
            "code": "CAM-TEST-002",
            "presets": [
                {"preset_index": 1, "name": "入口"},
                {"preset_index": 2, "name": "走廊"},
            ],
        }
        resp = await client.post(f"{VIDEO_PREFIX}/cameras", json=payload, headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["presets"]) == 2

    async def test_create_camera_no_auth(self, client):
        resp = await client.post(f"{VIDEO_PREFIX}/cameras", json=CAMERA_PAYLOAD)
        assert resp.status_code in (401, 403)

    async def test_get_camera_detail(self, client, admin_user):
        _, token = admin_user
        create_resp = await client.post(
            f"{VIDEO_PREFIX}/cameras", json=CAMERA_PAYLOAD, headers=auth_headers(token)
        )
        cam_id = create_resp.json()["id"]
        resp = await client.get(f"{VIDEO_PREFIX}/cameras/{cam_id}", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["name"] == "测试摄像头"

    async def test_get_camera_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.get(f"{VIDEO_PREFIX}/cameras/99999", headers=auth_headers(token))
        assert resp.status_code == 404

    async def test_update_camera(self, client, admin_user):
        _, token = admin_user
        create_resp = await client.post(
            f"{VIDEO_PREFIX}/cameras", json=CAMERA_PAYLOAD, headers=auth_headers(token)
        )
        cam_id = create_resp.json()["id"]
        resp = await client.put(
            f"{VIDEO_PREFIX}/cameras/{cam_id}",
            json={"name": "更新后摄像头", "status": "online"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "更新后摄像头"

    async def test_update_camera_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.put(
            f"{VIDEO_PREFIX}/cameras/99999",
            json={"name": "不存在"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_delete_camera(self, client, admin_user):
        _, token = admin_user
        create_resp = await client.post(
            f"{VIDEO_PREFIX}/cameras", json=CAMERA_PAYLOAD, headers=auth_headers(token)
        )
        cam_id = create_resp.json()["id"]
        resp = await client.delete(f"{VIDEO_PREFIX}/cameras/{cam_id}", headers=auth_headers(token))
        assert resp.status_code == 200
        # 确认已删除
        get_resp = await client.get(f"{VIDEO_PREFIX}/cameras/{cam_id}", headers=auth_headers(token))
        assert get_resp.status_code == 404

    async def test_delete_camera_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.delete(f"{VIDEO_PREFIX}/cameras/99999", headers=auth_headers(token))
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestCameraByQueries:
    """按告警/区域/设备查询摄像头"""

    async def test_cameras_by_area_empty(self, client, admin_user):
        _, token = admin_user
        resp = await client.get(f"{VIDEO_PREFIX}/cameras/by-area/NONEXIST", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_cameras_by_device_empty(self, client, admin_user):
        _, token = admin_user
        resp = await client.get(f"{VIDEO_PREFIX}/cameras/by-device/99999", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_cameras_by_alarm_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.get(f"{VIDEO_PREFIX}/cameras/by-alarm/99999", headers=auth_headers(token))
        assert resp.status_code == 404

    async def test_cameras_by_area_no_auth(self, client):
        resp = await client.get(f"{VIDEO_PREFIX}/cameras/by-area/A-01")
        assert resp.status_code in (401, 403)


# ==================== Video / PTZ & Recording Tests ====================


@pytest.mark.asyncio
class TestPTZControl:
    """云台控制"""

    async def test_ptz_control_camera_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.post(
            f"{VIDEO_PREFIX}/ptz/control",
            json={"camera_id": 99999, "action": "up", "speed": 5},
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_ptz_control_no_auth(self, client):
        resp = await client.post(
            f"{VIDEO_PREFIX}/ptz/control",
            json={"camera_id": 1, "action": "up", "speed": 5},
        )
        assert resp.status_code in (401, 403)

    async def test_ptz_control_success(self, client, admin_user):
        _, token = admin_user
        # 先创建摄像头
        cam_resp = await client.post(
            f"{VIDEO_PREFIX}/cameras", json=CAMERA_PAYLOAD, headers=auth_headers(token)
        )
        cam_id = cam_resp.json()["id"]
        resp = await client.post(
            f"{VIDEO_PREFIX}/ptz/control",
            json={"camera_id": cam_id, "action": "left", "speed": 3},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["event_type"] == "ptz_control"


@pytest.mark.asyncio
class TestPTZPreset:
    """预置位调用"""

    async def test_preset_camera_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.post(
            f"{VIDEO_PREFIX}/ptz/preset",
            json={"camera_id": 99999, "preset_index": 1},
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_preset_no_auth(self, client):
        resp = await client.post(
            f"{VIDEO_PREFIX}/ptz/preset",
            json={"camera_id": 1, "preset_index": 1},
        )
        assert resp.status_code in (401, 403)


@pytest.mark.asyncio
class TestRecording:
    """录像控制"""

    async def test_start_recording_camera_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.post(
            f"{VIDEO_PREFIX}/recording/start",
            json={"camera_id": 99999},
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_stop_recording_camera_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.post(
            f"{VIDEO_PREFIX}/recording/stop",
            json={"camera_id": 99999},
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_start_recording_no_auth(self, client):
        resp = await client.post(
            f"{VIDEO_PREFIX}/recording/start",
            json={"camera_id": 1},
        )
        assert resp.status_code in (401, 403)

    async def test_start_and_stop_recording(self, client, admin_user):
        _, token = admin_user
        cam_resp = await client.post(
            f"{VIDEO_PREFIX}/cameras", json=CAMERA_PAYLOAD, headers=auth_headers(token)
        )
        cam_id = cam_resp.json()["id"]
        # 开始录像
        start_resp = await client.post(
            f"{VIDEO_PREFIX}/recording/start",
            json={"camera_id": cam_id},
            headers=auth_headers(token),
        )
        assert start_resp.status_code == 200
        assert start_resp.json()["event_type"] == "recording_start"
        # 停止录像
        stop_resp = await client.post(
            f"{VIDEO_PREFIX}/recording/stop",
            json={"camera_id": cam_id},
            headers=auth_headers(token),
        )
        assert stop_resp.status_code == 200
        assert stop_resp.json()["event_type"] == "recording_stop"


# ==================== Video / Events & Playback Tests ====================


@pytest.mark.asyncio
class TestVideoEvents:
    """视频事件列表"""

    async def test_list_events_empty(self, client, admin_user):
        _, token = admin_user
        resp = await client.get(f"{VIDEO_PREFIX}/events", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    async def test_list_events_with_filter(self, client, admin_user):
        _, token = admin_user
        resp = await client.get(
            f"{VIDEO_PREFIX}/events",
            params={"event_type": "ptz_control"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200

    async def test_list_events_no_auth(self, client):
        resp = await client.get(f"{VIDEO_PREFIX}/events")
        assert resp.status_code in (401, 403)


@pytest.mark.asyncio
class TestPlayback:
    """回放"""

    async def test_playback_alarm_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.get(f"{VIDEO_PREFIX}/playback/alarm/99999", headers=auth_headers(token))
        assert resp.status_code == 404

    async def test_playback_alarm_no_auth(self, client):
        resp = await client.get(f"{VIDEO_PREFIX}/playback/alarm/1")
        assert resp.status_code in (401, 403)

    async def test_recording_segments_empty(self, client, admin_user):
        _, token = admin_user
        resp = await client.get(
            f"{VIDEO_PREFIX}/playback/segments",
            params={"camera_id": 99999},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    async def test_recording_segments_no_auth(self, client):
        resp = await client.get(f"{VIDEO_PREFIX}/playback/segments", params={"camera_id": 1})
        assert resp.status_code in (401, 403)


# ==================== OTA / Firmware Tests ====================


OTA_PREFIX = "/api/v1/ota"

FIRMWARE_PAYLOAD = {
    "version": "2.0.0",
    "filename": "gateway-fw-2.0.0.bin",
    "file_size": 1048576,
    "checksum_sha256": "a" * 64,
    "download_url": "https://fw.example.com/gateway-fw-2.0.0.bin",
    "release_notes": "测试固件更新",
    "min_version": "1.0.0",
}


@pytest.mark.asyncio
class TestFirmwareList:
    """固件列表"""

    async def test_list_firmware_empty(self, client, admin_user):
        _, token = admin_user
        resp = await client.get(f"{OTA_PREFIX}/firmware", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_firmware_no_auth(self, client):
        resp = await client.get(f"{OTA_PREFIX}/firmware")
        assert resp.status_code in (401, 403)

    async def test_list_firmware_viewer_forbidden(self, client, viewer_user):
        """固件列表需要 operator 以上权限"""
        _, token = viewer_user
        resp = await client.get(f"{OTA_PREFIX}/firmware", headers=auth_headers(token))
        assert resp.status_code == 403


@pytest.mark.asyncio
class TestFirmwareCRUD:
    """固件增删"""

    async def test_create_firmware(self, client, admin_user):
        _, token = admin_user
        resp = await client.post(f"{OTA_PREFIX}/firmware", json=FIRMWARE_PAYLOAD, headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == "2.0.0"
        assert data["filename"] == "gateway-fw-2.0.0.bin"
        assert data["is_active"] is True

    async def test_create_firmware_duplicate_version(self, client, admin_user):
        _, token = admin_user
        await client.post(f"{OTA_PREFIX}/firmware", json=FIRMWARE_PAYLOAD, headers=auth_headers(token))
        resp = await client.post(f"{OTA_PREFIX}/firmware", json=FIRMWARE_PAYLOAD, headers=auth_headers(token))
        assert resp.status_code == 400

    async def test_create_firmware_no_auth(self, client):
        resp = await client.post(f"{OTA_PREFIX}/firmware", json=FIRMWARE_PAYLOAD)
        assert resp.status_code in (401, 403)

    async def test_create_firmware_operator_forbidden(self, client, operator_user):
        """注册固件需要 admin 权限"""
        _, token = operator_user
        resp = await client.post(f"{OTA_PREFIX}/firmware", json=FIRMWARE_PAYLOAD, headers=auth_headers(token))
        assert resp.status_code == 403

    async def test_delete_firmware(self, client, admin_user):
        _, token = admin_user
        create_resp = await client.post(
            f"{OTA_PREFIX}/firmware", json=FIRMWARE_PAYLOAD, headers=auth_headers(token)
        )
        fw_id = create_resp.json()["id"]
        resp = await client.delete(f"{OTA_PREFIX}/firmware/{fw_id}", headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_delete_firmware_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.delete(f"{OTA_PREFIX}/firmware/99999", headers=auth_headers(token))
        assert resp.status_code == 404

    async def test_list_firmware_with_filter(self, client, admin_user):
        _, token = admin_user
        await client.post(f"{OTA_PREFIX}/firmware", json=FIRMWARE_PAYLOAD, headers=auth_headers(token))
        resp = await client.get(
            f"{OTA_PREFIX}/firmware",
            params={"is_active": True},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1


# ==================== OTA / Task Tests ====================


@pytest.mark.asyncio
class TestOtaTaskList:
    """OTA 任务列表"""

    async def test_list_tasks_empty(self, client, admin_user):
        _, token = admin_user
        resp = await client.get(f"{OTA_PREFIX}/tasks", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    async def test_list_tasks_with_status_filter(self, client, admin_user):
        _, token = admin_user
        resp = await client.get(
            f"{OTA_PREFIX}/tasks",
            params={"status": "pending"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    async def test_list_tasks_no_auth(self, client):
        resp = await client.get(f"{OTA_PREFIX}/tasks")
        assert resp.status_code in (401, 403)


@pytest.mark.asyncio
class TestOtaTaskCRUD:
    """OTA 任务创建与操作"""

    async def _create_firmware_and_gateway(self, client, token):
        """辅助方法：创建固件和网关，返回 (firmware_id, gateway_id)"""
        fw_resp = await client.post(
            f"{OTA_PREFIX}/firmware", json=FIRMWARE_PAYLOAD, headers=auth_headers(token)
        )
        fw_id = fw_resp.json()["id"]

        gw_resp = await client.post(GATEWAY_PREFIX, json=GATEWAY_PAYLOAD, headers=auth_headers(token))
        gw_id = gw_resp.json()["id"]
        return fw_id, gw_id

    async def test_create_task(self, client, admin_user):
        _, token = admin_user
        fw_id, gw_id = await self._create_firmware_and_gateway(client, token)
        resp = await client.post(
            f"{OTA_PREFIX}/tasks",
            json={
                "firmware_id": fw_id,
                "gateway_ids": [gw_id],
                "strategy": "immediate",
            },
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "pending"
        assert data["total_gateways"] == 1
        assert "task_id" in data

    async def test_create_task_invalid_firmware(self, client, admin_user):
        _, token = admin_user
        resp = await client.post(
            f"{OTA_PREFIX}/tasks",
            json={
                "firmware_id": 99999,
                "gateway_ids": [1],
                "strategy": "immediate",
            },
            headers=auth_headers(token),
        )
        assert resp.status_code == 400

    async def test_create_task_no_auth(self, client):
        resp = await client.post(
            f"{OTA_PREFIX}/tasks",
            json={"firmware_id": 1, "gateway_ids": [1], "strategy": "immediate"},
        )
        assert resp.status_code in (401, 403)

    async def test_get_task_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.get(f"{OTA_PREFIX}/tasks/nonexistent-task-id", headers=auth_headers(token))
        assert resp.status_code == 404

    async def test_get_task_detail(self, client, admin_user):
        _, token = admin_user
        fw_id, gw_id = await self._create_firmware_and_gateway(client, token)
        create_resp = await client.post(
            f"{OTA_PREFIX}/tasks",
            json={
                "firmware_id": fw_id,
                "gateway_ids": [gw_id],
                "strategy": "immediate",
            },
            headers=auth_headers(token),
        )
        task_id = create_resp.json()["task_id"]
        resp = await client.get(f"{OTA_PREFIX}/tasks/{task_id}", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_id"] == task_id
        assert "gateways" in data


@pytest.mark.asyncio
class TestOtaTaskActions:
    """OTA 任务操作（start/cancel/pause/resume）"""

    async def test_start_task_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.post(
            f"{OTA_PREFIX}/tasks/nonexistent-id/start", headers=auth_headers(token)
        )
        assert resp.status_code == 400

    async def test_cancel_task_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.post(
            f"{OTA_PREFIX}/tasks/nonexistent-id/cancel", headers=auth_headers(token)
        )
        assert resp.status_code == 400

    async def test_pause_task_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.post(
            f"{OTA_PREFIX}/tasks/nonexistent-id/pause", headers=auth_headers(token)
        )
        assert resp.status_code == 400

    async def test_resume_task_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.post(
            f"{OTA_PREFIX}/tasks/nonexistent-id/resume", headers=auth_headers(token)
        )
        assert resp.status_code == 400

    async def test_start_task_no_auth(self, client):
        resp = await client.post(f"{OTA_PREFIX}/tasks/some-id/start")
        assert resp.status_code in (401, 403)

    async def test_cancel_task_no_auth(self, client):
        resp = await client.post(f"{OTA_PREFIX}/tasks/some-id/cancel")
        assert resp.status_code in (401, 403)

    async def test_pause_task_no_auth(self, client):
        resp = await client.post(f"{OTA_PREFIX}/tasks/some-id/pause")
        assert resp.status_code in (401, 403)

    async def test_resume_task_no_auth(self, client):
        resp = await client.post(f"{OTA_PREFIX}/tasks/some-id/resume")
        assert resp.status_code in (401, 403)

    async def test_delete_firmware_with_active_task(self, client, admin_user):
        """有活跃任务的固件无法删除"""
        _, token = admin_user
        # 创建固件
        fw_resp = await client.post(
            f"{OTA_PREFIX}/firmware", json=FIRMWARE_PAYLOAD, headers=auth_headers(token)
        )
        fw_id = fw_resp.json()["id"]
        # 创建网关
        gw_resp = await client.post(GATEWAY_PREFIX, json=GATEWAY_PAYLOAD, headers=auth_headers(token))
        gw_id = gw_resp.json()["id"]
        # 创建任务（状态为 pending，属于活跃任务）
        await client.post(
            f"{OTA_PREFIX}/tasks",
            json={
                "firmware_id": fw_id,
                "gateway_ids": [gw_id],
                "strategy": "immediate",
            },
            headers=auth_headers(token),
        )
        # 尝试删除固件 → 应失败
        resp = await client.delete(f"{OTA_PREFIX}/firmware/{fw_id}", headers=auth_headers(token))
        assert resp.status_code == 400
