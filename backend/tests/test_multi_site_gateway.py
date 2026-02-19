"""多站点网关接入测试 — Story 16.3"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock

from sqlalchemy import select

from app.models.gateway import Gateway
from app.models.spatial import Site
from app.services.gateway_registration import handle_gateway_status, _resolve_site_id
from app.services.point_data import handle_point_data
from app.services.dedup_service import is_duplicate, mark_processed
from tests.conftest import auth_headers


# ==================== Fixtures ====================

@pytest.fixture
async def site_a(async_db):
    """创建测试站点 A"""
    site = Site(site_name="北京机房", site_code="BJ-DC01", status="active")
    async_db.add(site)
    await async_db.flush()
    return site


@pytest.fixture
async def site_b(async_db):
    """创建测试站点 B"""
    site = Site(site_name="上海机房", site_code="SH-DC01", status="active")
    async_db.add(site)
    await async_db.flush()
    return site


@pytest.fixture
async def gateway_no_site(async_db):
    """创建无站点绑定的网关"""
    gw = Gateway(
        gateway_id="gw-orphan",
        name="孤立网关",
        status="online",
        last_heartbeat=datetime.now(),
    )
    async_db.add(gw)
    await async_db.flush()
    return gw


@pytest.fixture
async def gateway_with_site(async_db, site_a):
    """创建已绑定站点 A 的网关"""
    gw = Gateway(
        gateway_id="gw-bound",
        name="已绑定网关",
        status="online",
        site_id=site_a.id,
        last_heartbeat=datetime.now(),
    )
    async_db.add(gw)
    await async_db.flush()
    return gw


# ==================== _resolve_site_id 测试 ====================

class TestResolveSiteId:
    """site_id 解析与验证"""

    async def test_none_input(self, async_db):
        """None 输入返回 None"""
        result = await _resolve_site_id(None, async_db)
        assert result is None

    async def test_valid_site_id(self, async_db, site_a):
        """有效 site_id 返回整数"""
        result = await _resolve_site_id(str(site_a.id), async_db)
        assert result == site_a.id

    async def test_nonexistent_site_id(self, async_db):
        """不存在的 site_id 返回 None"""
        result = await _resolve_site_id("99999", async_db)
        assert result is None

    async def test_non_integer_site_id(self, async_db):
        """非整数 site_id 返回 None"""
        result = await _resolve_site_id("abc", async_db)
        assert result is None

    async def test_empty_string_site_id(self, async_db):
        """空字符串 site_id 返回 None"""
        result = await _resolve_site_id("", async_db)
        assert result is None


# ==================== 网关自动注册绑定 site_id ====================

class TestGatewayRegistrationSiteId:
    """网关注册/心跳的 site_id 绑定"""

    @patch("app.services.gateway_registration.cache_gateway_status", new_callable=AsyncMock)
    async def test_auto_register_with_valid_site(self, mock_cache, async_db, site_a):
        """自动注册时绑定有效 site_id"""
        payload = {"gw_id": "gw-new-01", "name": "新网关", "ip": "10.0.1.1"}
        await handle_gateway_status(payload, async_db, site_id=str(site_a.id))

        result = await async_db.execute(
            select(Gateway).where(Gateway.gateway_id == "gw-new-01")
        )
        gw = result.scalar_one()
        assert gw.site_id == site_a.id
        assert gw.status == "online"

    @patch("app.services.gateway_registration.cache_gateway_status", new_callable=AsyncMock)
    async def test_auto_register_with_invalid_site(self, mock_cache, async_db):
        """自动注册时 site_id 无效，网关仍注册但 site_id 为 None"""
        payload = {"gw_id": "gw-new-02", "name": "新网关2"}
        await handle_gateway_status(payload, async_db, site_id="99999")

        result = await async_db.execute(
            select(Gateway).where(Gateway.gateway_id == "gw-new-02")
        )
        gw = result.scalar_one()
        assert gw.site_id is None
        assert gw.status == "online"

    @patch("app.services.gateway_registration.cache_gateway_status", new_callable=AsyncMock)
    async def test_auto_register_without_site(self, mock_cache, async_db):
        """自动注册时不传 site_id"""
        payload = {"gw_id": "gw-new-03", "name": "新网关3"}
        await handle_gateway_status(payload, async_db)

        result = await async_db.execute(
            select(Gateway).where(Gateway.gateway_id == "gw-new-03")
        )
        gw = result.scalar_one()
        assert gw.site_id is None

    @patch("app.services.gateway_registration.cache_gateway_status", new_callable=AsyncMock)
    async def test_heartbeat_fills_missing_site(self, mock_cache, async_db, site_a, gateway_no_site):
        """心跳更新时，网关无 site_id 且 topic 有，自动补充"""
        payload = {"gw_id": gateway_no_site.gateway_id, "name": "孤立网关"}
        await handle_gateway_status(payload, async_db, site_id=str(site_a.id))

        result = await async_db.execute(
            select(Gateway).where(Gateway.gateway_id == gateway_no_site.gateway_id)
        )
        gw = result.scalar_one()
        assert gw.site_id == site_a.id

    @patch("app.services.gateway_registration.cache_gateway_status", new_callable=AsyncMock)
    async def test_heartbeat_no_overwrite_on_mismatch(self, mock_cache, async_db, site_a, site_b, gateway_with_site):
        """心跳 site_id 与 DB 不一致时，不覆盖"""
        payload = {"gw_id": gateway_with_site.gateway_id, "name": "已绑定网关"}
        await handle_gateway_status(payload, async_db, site_id=str(site_b.id))

        result = await async_db.execute(
            select(Gateway).where(Gateway.gateway_id == gateway_with_site.gateway_id)
        )
        gw = result.scalar_one()
        # 保持原 site_id，不被覆盖
        assert gw.site_id == site_a.id

    @patch("app.services.gateway_registration.cache_gateway_status", new_callable=AsyncMock)
    async def test_heartbeat_same_site_no_change(self, mock_cache, async_db, site_a, gateway_with_site):
        """心跳 site_id 与 DB 一致时，正常更新"""
        payload = {"gw_id": gateway_with_site.gateway_id, "name": "已绑定网关"}
        await handle_gateway_status(payload, async_db, site_id=str(site_a.id))

        result = await async_db.execute(
            select(Gateway).where(Gateway.gateway_id == gateway_with_site.gateway_id)
        )
        gw = result.scalar_one()
        assert gw.site_id == site_a.id
        assert gw.status == "online"


# ==================== 点位数据处理 site_id ====================

class TestPointDataSiteId:
    """点位数据处理的 site_id 传递"""

    @patch("app.services.point_data.cache_point_data", new_callable=AsyncMock)
    @patch("app.services.point_data.is_duplicate", new_callable=AsyncMock, return_value=False)
    @patch("app.services.point_data.mark_processed", new_callable=AsyncMock)
    async def test_point_data_with_site_id(self, mock_mark, mock_dup, mock_cache, async_db):
        """点位数据处理接受 site_id 参数"""
        payload = {
            "gw_id": "gw-test",
            "points": [{"id": "pt-001", "v": "25.5", "q": 0}],
        }
        count = await handle_point_data(payload, async_db, site_id="1")
        assert count == 1

    @patch("app.services.point_data.cache_point_data", new_callable=AsyncMock)
    @patch("app.services.point_data.is_duplicate", new_callable=AsyncMock, return_value=False)
    @patch("app.services.point_data.mark_processed", new_callable=AsyncMock)
    async def test_point_data_without_site_id(self, mock_mark, mock_dup, mock_cache, async_db):
        """点位数据处理不传 site_id 时向后兼容"""
        payload = {
            "gw_id": "gw-test",
            "points": [{"id": "pt-002", "v": "30.0", "q": 0}],
        }
        count = await handle_point_data(payload, async_db)
        assert count == 1


# ==================== 断点续传去重 ====================

class TestDedupService:
    """断点续传消息去重"""

    async def test_is_duplicate_redis_unavailable(self):
        """Redis 不可用时返回 False（允许处理）"""
        result = await is_duplicate("gw-test", 1)
        assert result is False

    async def test_mark_processed_redis_unavailable(self):
        """Redis 不可用时静默失败"""
        # 不应抛异常
        await mark_processed("gw-test", 1)

    @patch("app.services.point_data.cache_point_data", new_callable=AsyncMock)
    @patch("app.services.point_data.is_duplicate", new_callable=AsyncMock, return_value=True)
    async def test_duplicate_seq_skipped(self, mock_dup, mock_cache, async_db):
        """重复 seq 的消息被跳过"""
        payload = {
            "gw_id": "gw-test",
            "seq": 100,
            "points": [{"id": "pt-dup", "v": "20.0", "q": 0}],
        }
        count = await handle_point_data(payload, async_db)
        assert count == 0

    @patch("app.services.point_data.cache_point_data", new_callable=AsyncMock)
    @patch("app.services.point_data.is_duplicate", new_callable=AsyncMock, return_value=False)
    @patch("app.services.point_data.mark_processed", new_callable=AsyncMock)
    async def test_new_seq_processed_and_marked(self, mock_mark, mock_dup, mock_cache, async_db):
        """新 seq 的消息正常处理并标记"""
        payload = {
            "gw_id": "gw-test",
            "seq": 200,
            "points": [{"id": "pt-new", "v": "22.0", "q": 0}],
        }
        count = await handle_point_data(payload, async_db)
        assert count == 1
        mock_mark.assert_called_once_with("gw-test", 200)

    @patch("app.services.point_data.cache_point_data", new_callable=AsyncMock)
    @patch("app.services.point_data.is_duplicate", new_callable=AsyncMock, return_value=False)
    @patch("app.services.point_data.mark_processed", new_callable=AsyncMock)
    async def test_no_seq_backward_compatible(self, mock_mark, mock_dup, mock_cache, async_db):
        """无 seq 字段的消息正常处理（向后兼容）"""
        payload = {
            "gw_id": "gw-test",
            "points": [{"id": "pt-nosq", "v": "18.0", "q": 0}],
        }
        count = await handle_point_data(payload, async_db)
        assert count == 1
        # 无 seq 时不调用 is_duplicate 和 mark_processed
        mock_dup.assert_not_called()
        mock_mark.assert_not_called()


# ==================== 网关站点分配 API ====================

class TestGatewayAssignSiteAPI:
    """PUT /api/v1/gateways/{id}/site 端点"""

    async def test_assign_site_success(self, client, admin_user, async_db, site_a):
        """管理员成功分配网关到站点"""
        _, token = admin_user
        gw = Gateway(gateway_id="gw-api-01", name="API测试网关", status="offline")
        async_db.add(gw)
        await async_db.flush()

        resp = await client.put(
            f"/api/v1/gateways/{gw.id}/site",
            json={"site_id": site_a.id},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["site_id"] == site_a.id

    async def test_assign_site_not_found_gateway(self, client, admin_user):
        """网关不存在返回 404"""
        _, token = admin_user
        resp = await client.put(
            "/api/v1/gateways/99999/site",
            json={"site_id": 1},
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_assign_site_not_found_site(self, client, admin_user, async_db):
        """目标站点不存在返回 404"""
        _, token = admin_user
        gw = Gateway(gateway_id="gw-api-02", name="API测试网关2", status="offline")
        async_db.add(gw)
        await async_db.flush()

        resp = await client.put(
            f"/api/v1/gateways/{gw.id}/site",
            json={"site_id": 99999},
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_assign_site_viewer_forbidden(self, client, viewer_user, async_db, site_a):
        """只读用户无权分配"""
        _, token = viewer_user
        gw = Gateway(gateway_id="gw-api-03", name="API测试网关3", status="offline")
        async_db.add(gw)
        await async_db.flush()

        resp = await client.put(
            f"/api/v1/gateways/{gw.id}/site",
            json={"site_id": site_a.id},
            headers=auth_headers(token),
        )
        assert resp.status_code == 403


# ==================== MQTT 消息路由 site_id 传递 ====================

class TestMqttMessageRouting:
    """MQTT _handle_message 中 site_id 传递"""

    async def test_status_message_passes_site_id(self):
        """status 消息传递 site_id 到 handle_gateway_status"""
        from app.mqtt.client import MqttService

        svc = MqttService()

        mock_message = MagicMock()
        mock_message.topic = "dcim/42/gw/gw-test/status"
        mock_message.payload = b'{"gw_id": "gw-test", "name": "test"}'

        with patch("app.mqtt.client.handle_gateway_status", new_callable=AsyncMock) as mock_handler, \
             patch("app.mqtt.client.async_session") as mock_session_ctx:
            mock_db = AsyncMock()
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            await svc._handle_message(mock_message)

            mock_handler.assert_called_once()
            call_kwargs = mock_handler.call_args
            assert call_kwargs[1]["site_id"] == "42"

    async def test_data_message_passes_site_id(self):
        """data 消息传递 site_id 到 handle_point_data"""
        from app.mqtt.client import MqttService

        svc = MqttService()

        mock_message = MagicMock()
        mock_message.topic = "dcim/7/gw/gw-test/data"
        mock_message.payload = b'{"gw_id": "gw-test", "points": []}'

        with patch("app.mqtt.client.handle_point_data", new_callable=AsyncMock) as mock_handler, \
             patch("app.mqtt.client.async_session") as mock_session_ctx:
            mock_db = AsyncMock()
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            await svc._handle_message(mock_message)

            mock_handler.assert_called_once()
            call_kwargs = mock_handler.call_args
            assert call_kwargs[1]["site_id"] == "7"
