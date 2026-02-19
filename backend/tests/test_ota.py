"""OTA 升级服务测试 — Story 15.5"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch

from app.models.gateway import Gateway, FirmwarePackage, OtaTask, OtaTaskGateway
from app.services.ota_service import OtaService, ota_service
from tests.conftest import auth_headers


# ==================== Fixtures ====================

@pytest.fixture
async def firmware(async_db):
    """创建测试固件包"""
    fw = FirmwarePackage(
        version="2.1.0",
        filename="gw-2.1.0.bin",
        file_size=10485760,
        checksum_sha256="a" * 64,
        download_url="https://firmware.example.com/gw-2.1.0.bin",
        release_notes="测试固件",
        is_active=True,
    )
    async_db.add(fw)
    await async_db.flush()
    return fw


@pytest.fixture
async def gateways(async_db):
    """创建 3 个测试网关"""
    gws = []
    for i in range(3):
        gw = Gateway(
            gateway_id=f"gw-{i:03d}",
            name=f"测试网关-{i}",
            ip_address=f"192.168.1.{10 + i}",
            version="2.0.0",
            status="online",
            site_id=1,
            is_enabled=True,
            last_heartbeat=datetime.now(),
        )
        async_db.add(gw)
        gws.append(gw)
    await async_db.flush()
    return gws


# ==================== OtaService 单元测试 ====================

class TestAssignBatches:
    """批次分配逻辑"""

    def test_immediate_all_batch_zero(self):
        gws = [type("GW", (), {"gateway_id": f"gw-{i}"})() for i in range(5)]
        result = OtaService._assign_batches(gws, "immediate", 0, 10)
        assert all(batch == 0 for _, batch in result)
        assert len(result) == 5

    def test_batch_strategy(self):
        gws = [type("GW", (), {"gateway_id": f"gw-{i}"})() for i in range(7)]
        result = OtaService._assign_batches(gws, "batch", 3, 10)
        batches = [b for _, b in result]
        assert batches == [0, 0, 0, 1, 1, 1, 2]

    def test_canary_strategy(self):
        gws = [type("GW", (), {"gateway_id": f"gw-{i}"})() for i in range(10)]
        result = OtaService._assign_batches(gws, "canary", 0, 20)
        batches = [b for _, b in result]
        # 20% of 10 = 2 canary gateways
        assert batches.count(0) == 2
        assert batches.count(1) == 8

    def test_canary_at_least_one(self):
        gws = [type("GW", (), {"gateway_id": f"gw-{i}"})() for i in range(3)]
        result = OtaService._assign_batches(gws, "canary", 0, 1)
        batches = [b for _, b in result]
        assert batches.count(0) >= 1

    def test_single_gateway(self):
        gws = [type("GW", (), {"gateway_id": "gw-0"})()]
        result = OtaService._assign_batches(gws, "batch", 3, 10)
        assert len(result) == 1
        assert result[0][1] == 0


class TestCreateTask:
    """创建升级任务"""

    async def test_create_immediate(self, async_db, firmware, gateways):
        gw_ids = [gw.id for gw in gateways]
        task = await ota_service.create_task(
            firmware_id=firmware.id,
            gateway_ids=gw_ids,
            strategy="immediate",
            batch_size=0,
            batch_interval=0,
            canary_percent=10,
            created_by="admin",
            db=async_db,
        )
        assert task.task_id is not None
        assert task.status == "pending"
        assert task.total_gateways == 3
        assert task.target_version == "2.1.0"

    async def test_create_batch(self, async_db, firmware, gateways):
        gw_ids = [gw.id for gw in gateways]
        task = await ota_service.create_task(
            firmware_id=firmware.id,
            gateway_ids=gw_ids,
            strategy="batch",
            batch_size=2,
            batch_interval=60,
            canary_percent=10,
            created_by="admin",
            db=async_db,
        )
        assert task.total_gateways == 3

    async def test_firmware_not_found(self, async_db, gateways):
        with pytest.raises(ValueError, match="固件包不存在"):
            await ota_service.create_task(
                firmware_id=9999,
                gateway_ids=[gateways[0].id],
                strategy="immediate",
                batch_size=0,
                batch_interval=0,
                canary_percent=10,
                created_by="admin",
                db=async_db,
            )

    async def test_gateway_not_found(self, async_db, firmware):
        with pytest.raises(ValueError, match="未找到"):
            await ota_service.create_task(
                firmware_id=firmware.id,
                gateway_ids=[9999],
                strategy="immediate",
                batch_size=0,
                batch_interval=0,
                canary_percent=10,
                created_by="admin",
                db=async_db,
            )

    async def test_firmware_inactive(self, async_db, gateways):
        fw = FirmwarePackage(
            version="3.0.0",
            filename="gw-3.0.0.bin",
            file_size=1000,
            checksum_sha256="b" * 64,
            download_url="https://example.com/gw-3.0.0.bin",
            is_active=False,
        )
        async_db.add(fw)
        await async_db.flush()
        with pytest.raises(ValueError, match="固件包不存在"):
            await ota_service.create_task(
                firmware_id=fw.id,
                gateway_ids=[gateways[0].id],
                strategy="immediate",
                batch_size=0,
                batch_interval=0,
                canary_percent=10,
                created_by="admin",
                db=async_db,
            )

    async def test_version_incompatible(self, async_db, gateways):
        fw = FirmwarePackage(
            version="3.0.0",
            filename="gw-3.0.0.bin",
            file_size=1000,
            checksum_sha256="c" * 64,
            download_url="https://example.com/gw-3.0.0.bin",
            min_version="2.5.0",
            is_active=True,
        )
        async_db.add(fw)
        await async_db.flush()
        with pytest.raises(ValueError, match="版本不兼容"):
            await ota_service.create_task(
                firmware_id=fw.id,
                gateway_ids=[gateways[0].id],
                strategy="immediate",
                batch_size=0,
                batch_interval=0,
                canary_percent=10,
                created_by="admin",
                db=async_db,
            )


class TestStartTask:
    """启动任务"""

    async def test_start_sends_mqtt(self, async_db, firmware, gateways):
        gw_ids = [gw.id for gw in gateways]
        task = await ota_service.create_task(
            firmware_id=firmware.id,
            gateway_ids=gw_ids,
            strategy="immediate",
            batch_size=0,
            batch_interval=0,
            canary_percent=10,
            created_by="admin",
            db=async_db,
        )
        mock_publish = AsyncMock()
        await ota_service.start_task(task.task_id, mock_publish, async_db)

        # 应该为每个网关发送一条 MQTT 消息
        assert mock_publish.call_count == 3
        for call in mock_publish.call_args_list:
            topic = call[0][0]
            assert "/ota" in topic
            assert call[1]["qos"] == 2

    async def test_start_wrong_status(self, async_db, firmware, gateways):
        gw_ids = [gw.id for gw in gateways]
        task = await ota_service.create_task(
            firmware_id=firmware.id,
            gateway_ids=gw_ids,
            strategy="immediate",
            batch_size=0,
            batch_interval=0,
            canary_percent=10,
            created_by="admin",
            db=async_db,
        )
        mock_publish = AsyncMock()
        await ota_service.start_task(task.task_id, mock_publish, async_db)
        # 再次启动应失败
        with pytest.raises(ValueError, match="状态不允许启动"):
            await ota_service.start_task(task.task_id, mock_publish, async_db)


class TestHandleOtaStatus:
    """处理 OTA 状态上报"""

    async def test_downloading_status(self, async_db, firmware, gateways):
        gw_ids = [gw.id for gw in gateways]
        task = await ota_service.create_task(
            firmware_id=firmware.id,
            gateway_ids=gw_ids,
            strategy="immediate",
            batch_size=0,
            batch_interval=0,
            canary_percent=10,
            created_by="admin",
            db=async_db,
        )
        await ota_service.handle_ota_status({
            "task_id": task.task_id,
            "gw_id": "gw-000",
            "status": "downloading",
            "progress": 30,
        }, async_db)

        from sqlalchemy import select
        result = await async_db.execute(
            select(OtaTaskGateway).where(
                OtaTaskGateway.task_id == task.task_id,
                OtaTaskGateway.gateway_id == "gw-000",
            )
        )
        tg = result.scalar_one()
        assert tg.status == "downloading"
        assert tg.progress == 30
        assert tg.started_at is not None

    async def test_success_updates_version(self, async_db, firmware, gateways):
        gw_ids = [gw.id for gw in gateways]
        task = await ota_service.create_task(
            firmware_id=firmware.id,
            gateway_ids=gw_ids,
            strategy="immediate",
            batch_size=0,
            batch_interval=0,
            canary_percent=10,
            created_by="admin",
            db=async_db,
        )
        mock_publish = AsyncMock()
        await ota_service.start_task(task.task_id, mock_publish, async_db)

        await ota_service.handle_ota_status({
            "task_id": task.task_id,
            "gw_id": "gw-000",
            "status": "success",
            "progress": 100,
        }, async_db)

        # 检查网关版本已更新
        from sqlalchemy import select
        result = await async_db.execute(
            select(Gateway).where(Gateway.gateway_id == "gw-000")
        )
        gw = result.scalar_one()
        assert gw.version == "2.1.0"

        # 检查任务成功计数
        result = await async_db.execute(
            select(OtaTask).where(OtaTask.task_id == task.task_id)
        )
        t = result.scalar_one()
        assert t.success_count == 1

    async def test_failed_increments_fail_count(self, async_db, firmware, gateways):
        gw_ids = [gw.id for gw in gateways]
        task = await ota_service.create_task(
            firmware_id=firmware.id,
            gateway_ids=gw_ids,
            strategy="immediate",
            batch_size=0,
            batch_interval=0,
            canary_percent=10,
            created_by="admin",
            db=async_db,
        )
        mock_publish = AsyncMock()
        await ota_service.start_task(task.task_id, mock_publish, async_db)

        await ota_service.handle_ota_status({
            "task_id": task.task_id,
            "gw_id": "gw-001",
            "status": "failed",
            "error": "校验失败",
        }, async_db)

        from sqlalchemy import select
        result = await async_db.execute(
            select(OtaTask).where(OtaTask.task_id == task.task_id)
        )
        t = result.scalar_one()
        assert t.fail_count == 1

    async def test_missing_fields_ignored(self, async_db):
        # 缺少必要字段不应抛异常
        await ota_service.handle_ota_status({}, async_db)
        await ota_service.handle_ota_status({"task_id": "x"}, async_db)


class TestCancelTask:
    """取消任务"""

    async def test_cancel_sends_mqtt(self, async_db, firmware, gateways):
        gw_ids = [gw.id for gw in gateways]
        task = await ota_service.create_task(
            firmware_id=firmware.id,
            gateway_ids=gw_ids,
            strategy="immediate",
            batch_size=0,
            batch_interval=0,
            canary_percent=10,
            created_by="admin",
            db=async_db,
        )
        mock_publish = AsyncMock()
        await ota_service.start_task(task.task_id, mock_publish, async_db)
        mock_publish.reset_mock()

        await ota_service.cancel_task(task.task_id, mock_publish, async_db)

        from sqlalchemy import select
        result = await async_db.execute(
            select(OtaTask).where(OtaTask.task_id == task.task_id)
        )
        t = result.scalar_one()
        assert t.status == "cancelled"

    async def test_cancel_completed_fails(self, async_db, firmware, gateways):
        gw_ids = [gw.id for gw in gateways]
        task = await ota_service.create_task(
            firmware_id=firmware.id,
            gateway_ids=gw_ids,
            strategy="immediate",
            batch_size=0,
            batch_interval=0,
            canary_percent=10,
            created_by="admin",
            db=async_db,
        )
        # 手动设置为 completed
        from sqlalchemy import update
        await async_db.execute(
            update(OtaTask).where(OtaTask.task_id == task.task_id).values(status="completed")
        )
        await async_db.commit()

        with pytest.raises(ValueError, match="任务已结束"):
            await ota_service.cancel_task(task.task_id, AsyncMock(), async_db)


class TestPauseResume:
    """暂停/恢复任务"""

    async def test_pause_running(self, async_db, firmware, gateways):
        gw_ids = [gw.id for gw in gateways]
        task = await ota_service.create_task(
            firmware_id=firmware.id,
            gateway_ids=gw_ids,
            strategy="immediate",
            batch_size=0,
            batch_interval=0,
            canary_percent=10,
            created_by="admin",
            db=async_db,
        )
        mock_publish = AsyncMock()
        await ota_service.start_task(task.task_id, mock_publish, async_db)
        await ota_service.pause_task(task.task_id, async_db)

        from sqlalchemy import select
        result = await async_db.execute(
            select(OtaTask).where(OtaTask.task_id == task.task_id)
        )
        t = result.scalar_one()
        assert t.status == "paused"

    async def test_pause_pending_fails(self, async_db, firmware, gateways):
        gw_ids = [gw.id for gw in gateways]
        task = await ota_service.create_task(
            firmware_id=firmware.id,
            gateway_ids=gw_ids,
            strategy="immediate",
            batch_size=0,
            batch_interval=0,
            canary_percent=10,
            created_by="admin",
            db=async_db,
        )
        with pytest.raises(ValueError, match="只能暂停运行中"):
            await ota_service.pause_task(task.task_id, async_db)

    async def test_resume_paused(self, async_db, firmware, gateways):
        gw_ids = [gw.id for gw in gateways]
        task = await ota_service.create_task(
            firmware_id=firmware.id,
            gateway_ids=gw_ids,
            strategy="batch",
            batch_size=1,
            batch_interval=0,
            canary_percent=10,
            created_by="admin",
            db=async_db,
        )
        mock_publish = AsyncMock()
        await ota_service.start_task(task.task_id, mock_publish, async_db)
        await ota_service.pause_task(task.task_id, async_db)
        mock_publish.reset_mock()

        await ota_service.resume_task(task.task_id, mock_publish, async_db)

        from sqlalchemy import select
        result = await async_db.execute(
            select(OtaTask).where(OtaTask.task_id == task.task_id)
        )
        t = result.scalar_one()
        assert t.status == "running"


class TestTaskNotFound:
    """任务不存在"""

    async def test_start_not_found(self, async_db):
        with pytest.raises(ValueError, match="不存在"):
            await ota_service.start_task("nonexistent", AsyncMock(), async_db)

    async def test_cancel_not_found(self, async_db):
        with pytest.raises(ValueError, match="不存在"):
            await ota_service.cancel_task("nonexistent", AsyncMock(), async_db)

    async def test_pause_not_found(self, async_db):
        with pytest.raises(ValueError, match="不存在"):
            await ota_service.pause_task("nonexistent", async_db)


class TestAutoFailThreshold:
    """失败率超阈值自动暂停"""

    async def test_high_fail_rate_pauses(self, async_db, firmware, gateways):
        gw_ids = [gw.id for gw in gateways]
        task = await ota_service.create_task(
            firmware_id=firmware.id,
            gateway_ids=gw_ids,
            strategy="immediate",
            batch_size=0,
            batch_interval=0,
            canary_percent=10,
            created_by="admin",
            db=async_db,
        )
        mock_publish = AsyncMock()
        await ota_service.start_task(task.task_id, mock_publish, async_db)

        # 让所有网关失败 (100% > 30% 阈值)
        for gw in gateways:
            await ota_service.handle_ota_status({
                "task_id": task.task_id,
                "gw_id": gw.gateway_id,
                "status": "failed",
                "error": "测试失败",
            }, async_db)

        from sqlalchemy import select
        result = await async_db.execute(
            select(OtaTask).where(OtaTask.task_id == task.task_id)
        )
        t = result.scalar_one()
        # 应该被自动暂停或标记为 failed
        assert t.status in ("paused", "failed")


# ==================== API 集成测试 ====================

class TestFirmwareAPI:
    """固件包 API"""

    async def test_create_firmware(self, client, admin_user):
        _, token = admin_user
        resp = await client.post("/api/v1/ota/firmware", json={
            "version": "1.0.0",
            "filename": "gw-1.0.0.bin",
            "file_size": 5000000,
            "checksum_sha256": "d" * 64,
            "download_url": "https://example.com/gw-1.0.0.bin",
        }, headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == "1.0.0"
        assert data["is_active"] is True

    async def test_create_duplicate_version(self, client, admin_user):
        _, token = admin_user
        payload = {
            "version": "1.0.0",
            "filename": "gw-1.0.0.bin",
            "file_size": 5000000,
            "checksum_sha256": "e" * 64,
            "download_url": "https://example.com/gw-1.0.0.bin",
        }
        await client.post("/api/v1/ota/firmware", json=payload, headers=auth_headers(token))
        resp = await client.post("/api/v1/ota/firmware", json=payload, headers=auth_headers(token))
        assert resp.status_code == 400

    async def test_list_firmware(self, client, admin_user):
        _, token = admin_user
        await client.post("/api/v1/ota/firmware", json={
            "version": "1.0.0",
            "filename": "gw-1.0.0.bin",
            "file_size": 5000000,
            "checksum_sha256": "f" * 64,
            "download_url": "https://example.com/gw-1.0.0.bin",
        }, headers=auth_headers(token))
        resp = await client.get("/api/v1/ota/firmware", headers=auth_headers(token))
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    async def test_delete_firmware(self, client, admin_user):
        _, token = admin_user
        create_resp = await client.post("/api/v1/ota/firmware", json={
            "version": "9.9.9",
            "filename": "gw-9.9.9.bin",
            "file_size": 1000,
            "checksum_sha256": "0" * 64,
            "download_url": "https://example.com/gw-9.9.9.bin",
        }, headers=auth_headers(token))
        fw_id = create_resp.json()["id"]
        resp = await client.delete(f"/api/v1/ota/firmware/{fw_id}", headers=auth_headers(token))
        assert resp.status_code == 200


class TestTaskAPI:
    """OTA 任务 API"""

    async def test_create_task(self, client, admin_user, async_db):
        _, token = admin_user
        # 先创建固件和网关
        fw = FirmwarePackage(
            version="2.0.0",
            filename="gw-2.0.0.bin",
            file_size=1000,
            checksum_sha256="1" * 64,
            download_url="https://example.com/gw-2.0.0.bin",
            is_active=True,
        )
        async_db.add(fw)
        gw = Gateway(
            gateway_id="gw-api-test",
            name="API测试网关",
            version="1.0.0",
            status="online",
            site_id=1,
            is_enabled=True,
        )
        async_db.add(gw)
        await async_db.flush()

        resp = await client.post("/api/v1/ota/tasks", json={
            "firmware_id": fw.id,
            "gateway_ids": [gw.id],
            "strategy": "immediate",
        }, headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "pending"
        assert data["total_gateways"] == 1

    async def test_list_tasks(self, client, admin_user):
        _, token = admin_user
        resp = await client.get("/api/v1/ota/tasks", headers=auth_headers(token))
        assert resp.status_code == 200
        assert "items" in resp.json()

    async def test_get_task_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.get("/api/v1/ota/tasks/nonexistent", headers=auth_headers(token))
        assert resp.status_code == 404


# ==================== Momus 修复验证测试 ====================

class TestVersionComparison:
    """I2: 语义版本比较"""

    def test_simple_lt(self):
        assert OtaService._version_lt("1.0.0", "2.0.0") is True

    def test_minor_lt(self):
        assert OtaService._version_lt("2.0.0", "2.1.0") is True

    def test_patch_lt(self):
        assert OtaService._version_lt("2.1.0", "2.1.1") is True

    def test_not_lt(self):
        assert OtaService._version_lt("2.1.0", "2.0.0") is False

    def test_equal(self):
        assert OtaService._version_lt("2.0.0", "2.0.0") is False

    def test_semantic_vs_string(self):
        # 字符串比较会错误地认为 "2.9.0" > "2.10.0"
        assert OtaService._version_lt("2.9.0", "2.10.0") is True

    def test_malformed_version(self):
        # 非标准版本不应崩溃
        assert OtaService._parse_version("abc") == (0,)


class TestBatchProgression:
    """B1: 批次推进功能"""

    async def test_batch_auto_progresses(self, async_db, firmware, gateways):
        """batch 策略: 第一批完成后应自动触发第二批"""
        gw_ids = [gw.id for gw in gateways]
        task = await ota_service.create_task(
            firmware_id=firmware.id,
            gateway_ids=gw_ids,
            strategy="batch",
            batch_size=1,  # 每批 1 个，共 3 批
            batch_interval=0,
            canary_percent=10,
            created_by="admin",
            db=async_db,
        )
        mock_publish = AsyncMock()
        await ota_service.start_task(task.task_id, mock_publish, async_db)
        # 第一批发送了 1 条
        assert mock_publish.call_count == 1
        mock_publish.reset_mock()

        # 第一个网关成功 → 应触发第二批
        await ota_service._check_batch_completion(
            task.task_id, async_db, mqtt_publish_fn=mock_publish
        )
        # 还有进行中的（batch 0 的网关还没上报），不应触发
        # 模拟 batch 0 的网关上报 success
        from sqlalchemy import select, update
        tg_result = await async_db.execute(
            select(OtaTaskGateway).where(
                OtaTaskGateway.task_id == task.task_id,
                OtaTaskGateway.batch_index == 0,
            )
        )
        tg0 = tg_result.scalar_one()
        await async_db.execute(
            update(OtaTaskGateway).where(OtaTaskGateway.id == tg0.id).values(
                status="success"
            )
        )
        await async_db.execute(
            update(OtaTask).where(OtaTask.task_id == task.task_id).values(
                success_count=1
            )
        )
        await async_db.commit()

        # 现在 batch 0 完成，应触发 batch 1
        await ota_service._check_batch_completion(
            task.task_id, async_db, mqtt_publish_fn=mock_publish
        )
        assert mock_publish.call_count >= 1  # 第二批已发送


class TestCancelGatewayStatus:
    """I5: 取消时网关状态应为 cancelled"""

    async def test_cancelled_gateways_status(self, async_db, firmware, gateways):
        gw_ids = [gw.id for gw in gateways]
        task = await ota_service.create_task(
            firmware_id=firmware.id,
            gateway_ids=gw_ids,
            strategy="immediate",
            batch_size=0,
            batch_interval=0,
            canary_percent=10,
            created_by="admin",
            db=async_db,
        )
        mock_publish = AsyncMock()
        await ota_service.start_task(task.task_id, mock_publish, async_db)
        await ota_service.cancel_task(task.task_id, mock_publish, async_db)

        from sqlalchemy import select
        result = await async_db.execute(
            select(OtaTaskGateway).where(OtaTaskGateway.task_id == task.task_id)
        )
        for tg in result.scalars().all():
            assert tg.status == "cancelled"


class TestInvalidStatusRejected:
    """S2: 无效状态值被拒绝"""

    async def test_invalid_status_ignored(self, async_db, firmware, gateways):
        gw_ids = [gw.id for gw in gateways]
        task = await ota_service.create_task(
            firmware_id=firmware.id,
            gateway_ids=gw_ids,
            strategy="immediate",
            batch_size=0,
            batch_interval=0,
            canary_percent=10,
            created_by="admin",
            db=async_db,
        )
        # 发送无效状态不应崩溃，也不应更新数据库
        await ota_service.handle_ota_status({
            "task_id": task.task_id,
            "gw_id": "gw-000",
            "status": "hacked",
            "progress": 100,
        }, async_db)

        from sqlalchemy import select
        result = await async_db.execute(
            select(OtaTaskGateway).where(
                OtaTaskGateway.task_id == task.task_id,
                OtaTaskGateway.gateway_id == "gw-000",
            )
        )
        tg = result.scalar_one()
        assert tg.status == "pending"  # 未被修改


class TestDeleteFirmwareWithActiveTask:
    """I3: 删除有活跃任务的固件包应被拒绝"""

    async def test_delete_blocked_by_active_task(self, client, admin_user, async_db):
        _, token = admin_user
        fw = FirmwarePackage(
            version="5.0.0",
            filename="gw-5.0.0.bin",
            file_size=1000,
            checksum_sha256="5" * 64,
            download_url="https://example.com/gw-5.0.0.bin",
            is_active=True,
        )
        async_db.add(fw)
        await async_db.flush()

        # 创建一个 pending 任务引用该固件
        task = OtaTask(
            task_id="test-del-fw",
            firmware_id=fw.id,
            target_version="5.0.0",
            status="pending",
            total_gateways=1,
        )
        async_db.add(task)
        await async_db.commit()

        resp = await client.delete(f"/api/v1/ota/firmware/{fw.id}", headers=auth_headers(token))
        assert resp.status_code == 400
        assert "活跃任务" in resp.json()["detail"]
