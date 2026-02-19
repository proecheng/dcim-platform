"""
告警管理 API 覆盖率测试 — 覆盖 alarm.py 中未测试的端点
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from app.models.alarm import Alarm, AlarmRule, AlarmShield
from app.models.point import Point
from tests.conftest import auth_headers


# ============== 辅助函数 ==============

async def _seed_points_and_alarms(async_db):
    """创建测试点位和告警数据，返回 (point, point2, alarms)"""
    point = Point(
        point_code="TH-TEST-001", point_name="测试温度点位",
        point_type="AI", device_type="TH", area_code="A1",
    )
    point2 = Point(
        point_code="UPS-TEST-001", point_name="测试UPS点位",
        point_type="AI", device_type="UPS", area_code="B1",
    )
    async_db.add_all([point, point2])
    await async_db.flush()

    now = datetime.now()
    alarms = []
    for i, (pt, level, status) in enumerate([
        (point, "critical", "active"),
        (point, "major", "active"),
        (point, "minor", "acknowledged"),
        (point2, "info", "resolved"),
        (point2, "critical", "active"),
    ]):
        a = Alarm(
            alarm_no=f"ALM-COV-{i+1:03d}",
            point_id=pt.id,
            alarm_level=level,
            alarm_type="threshold",
            alarm_message=f"测试告警消息{i+1}",
            trigger_value=50.0 + i,
            threshold_value=45.0,
            status=status,
            created_at=now - timedelta(hours=i),
        )
        if status == "resolved":
            a.resolved_by = 1
            a.resolved_at = now
            a.duration_seconds = 3600
        alarms.append(a)

    async_db.add_all(alarms)
    await async_db.flush()
    return point, point2, alarms


# ============== 告警列表与查询 ==============

class TestAlarmListAndQuery:
    """告警列表、活动告警、计数、统计、趋势、高频点位"""

    async def test_get_alarms_basic(self, client, admin_user, async_db):
        """GET /alarms — 基本分页"""
        _, token = admin_user
        await _seed_points_and_alarms(async_db)
        resp = await client.get("/api/v1/alarms", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 5

    async def test_get_alarms_filter_status(self, client, admin_user, async_db):
        """GET /alarms?status=active — 按状态筛选"""
        _, token = admin_user
        await _seed_points_and_alarms(async_db)
        resp = await client.get(
            "/api/v1/alarms", params={"status": "active"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["status"] == "active"

    async def test_get_alarms_filter_level(self, client, admin_user, async_db):
        """GET /alarms?level=critical — 按级别筛选"""
        _, token = admin_user
        await _seed_points_and_alarms(async_db)
        resp = await client.get(
            "/api/v1/alarms", params={"level": "critical"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["alarm_level"] == "critical"

    async def test_get_alarms_filter_device_type(self, client, admin_user, async_db):
        """GET /alarms?device_type=TH — 按设备类型筛选"""
        _, token = admin_user
        await _seed_points_and_alarms(async_db)
        resp = await client.get(
            "/api/v1/alarms", params={"device_type": "TH"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200

    async def test_get_alarms_filter_keyword(self, client, admin_user, async_db):
        """GET /alarms?keyword=消息 — 关键词搜索"""
        _, token = admin_user
        await _seed_points_and_alarms(async_db)
        resp = await client.get(
            "/api/v1/alarms", params={"keyword": "消息"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200

    async def test_get_alarms_filter_time_range(self, client, admin_user, async_db):
        """GET /alarms — 时间范围筛选"""
        _, token = admin_user
        await _seed_points_and_alarms(async_db)
        now = datetime.now()
        resp = await client.get(
            "/api/v1/alarms",
            params={
                "start_time": (now - timedelta(days=1)).isoformat(),
                "end_time": now.isoformat(),
            },
            headers=auth_headers(token),
        )
        assert resp.status_code == 200

    async def test_get_active_alarms(self, client, admin_user, async_db):
        """GET /alarms/active — 活动告警"""
        _, token = admin_user
        await _seed_points_and_alarms(async_db)
        resp = await client.get("/api/v1/alarms/active", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        for item in data:
            assert item["status"] in ("active", "acknowledged")

    async def test_get_alarm_count(self, client, admin_user, async_db):
        """GET /alarms/count — 各级别告警数量"""
        _, token = admin_user
        await _seed_points_and_alarms(async_db)
        resp = await client.get("/api/v1/alarms/count", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert "critical" in data
        assert "major" in data
        assert "minor" in data
        assert "info" in data
        assert "total" in data
        assert data["total"] == data["critical"] + data["major"] + data["minor"] + data["info"]

    async def test_get_alarm_statistics(self, client, admin_user, async_db):
        """GET /alarms/statistics — 告警统计"""
        _, token = admin_user
        await _seed_points_and_alarms(async_db)
        resp = await client.get("/api/v1/alarms/statistics", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "by_level" in data
        assert "by_status" in data
        assert "by_device_type" in data
        assert "avg_duration_seconds" in data

    async def test_get_alarm_statistics_with_filters(self, client, admin_user, async_db):
        """GET /alarms/statistics — 带设备类型和级别筛选"""
        _, token = admin_user
        await _seed_points_and_alarms(async_db)
        resp = await client.get(
            "/api/v1/alarms/statistics",
            params={"device_type": "TH", "alarm_level": "critical"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200

    async def test_get_alarm_trend(self, client, admin_user, async_db):
        """GET /alarms/trend — 告警趋势"""
        _, token = admin_user
        await _seed_points_and_alarms(async_db)
        resp = await client.get(
            "/api/v1/alarms/trend", params={"days": 7},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    async def test_get_top_alarm_points(self, client, admin_user, async_db):
        """GET /alarms/top-points — 高频告警点位"""
        _, token = admin_user
        await _seed_points_and_alarms(async_db)
        resp = await client.get(
            "/api/v1/alarms/top-points", params={"days": 7, "limit": 5},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        if data:
            assert "point_id" in data[0]
            assert "alarm_count" in data[0]


# ============== 导出 ==============

class TestAlarmExport:
    """告警导出"""

    async def test_export_alarms_csv(self, client, operator_user, async_db):
        """GET /alarms/export — 导出 CSV"""
        _, token = operator_user
        await _seed_points_and_alarms(async_db)
        resp = await client.get("/api/v1/alarms/export", headers=auth_headers(token))
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("content-type", "")

    async def test_export_alarms_with_filters(self, client, operator_user, async_db):
        """GET /alarms/export — 带筛选条件导出"""
        _, token = operator_user
        await _seed_points_and_alarms(async_db)
        resp = await client.get(
            "/api/v1/alarms/export",
            params={"status": "active"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200


# ============== 告警详情 ==============

class TestAlarmDetail:
    """单条告警操作"""

    async def test_get_alarm_detail(self, client, admin_user, async_db):
        """GET /alarms/{alarm_id} — 告警详情"""
        _, token = admin_user
        _, _, alarms = await _seed_points_and_alarms(async_db)
        alarm_id = alarms[0].id
        resp = await client.get(
            f"/api/v1/alarms/{alarm_id}", headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == alarm_id
        assert data["point_code"] is not None

    async def test_get_alarm_not_found(self, client, admin_user, async_db):
        """GET /alarms/99999 — 不存在的告警"""
        _, token = admin_user
        resp = await client.get(
            "/api/v1/alarms/99999", headers=auth_headers(token),
        )
        assert resp.status_code == 404


# ============== 确认/解决/处理（使用 conftest fixtures） ==============

class TestAlarmActions:
    """确认、解决、处理告警"""

    @patch("app.api.v1.alarm.ws_manager.broadcast_alarm", new_callable=AsyncMock)
    async def test_acknowledge_alarm(self, mock_ws, client, operator_user, async_db):
        """PUT /alarms/{id}/acknowledge — 确认告警"""
        _, token = operator_user
        _, _, alarms = await _seed_points_and_alarms(async_db)
        active_alarm = alarms[0]  # status=active
        resp = await client.put(
            f"/api/v1/alarms/{active_alarm.id}/acknowledge",
            json={"remark": "已确认"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["message"] == "告警已确认"
        mock_ws.assert_called_once()

    @patch("app.api.v1.alarm.ws_manager.broadcast_alarm", new_callable=AsyncMock)
    async def test_acknowledge_non_active(self, mock_ws, client, operator_user, async_db):
        """PUT /alarms/{id}/acknowledge — 非 active 状态不可确认"""
        _, token = operator_user
        _, _, alarms = await _seed_points_and_alarms(async_db)
        resolved_alarm = alarms[3]  # status=resolved
        resp = await client.put(
            f"/api/v1/alarms/{resolved_alarm.id}/acknowledge",
            json={"remark": "test"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 400

    @patch("app.api.v1.alarm.ws_manager.broadcast_alarm", new_callable=AsyncMock)
    async def test_resolve_alarm(self, mock_ws, client, operator_user, async_db):
        """PUT /alarms/{id}/resolve — 解决告警"""
        _, token = operator_user
        _, _, alarms = await _seed_points_and_alarms(async_db)
        active_alarm = alarms[1]  # status=active
        resp = await client.put(
            f"/api/v1/alarms/{active_alarm.id}/resolve",
            json={"remark": "已修复", "resolve_type": "manual"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["message"] == "告警已解决"
        mock_ws.assert_called_once()

    @patch("app.api.v1.alarm.ws_manager.broadcast_alarm", new_callable=AsyncMock)
    async def test_resolve_already_resolved(self, mock_ws, client, operator_user, async_db):
        """PUT /alarms/{id}/resolve — 已解决的不可再解决"""
        _, token = operator_user
        _, _, alarms = await _seed_points_and_alarms(async_db)
        resolved_alarm = alarms[3]
        resp = await client.put(
            f"/api/v1/alarms/{resolved_alarm.id}/resolve",
            json={"remark": "test"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 400

    @patch("app.api.v1.alarm.ws_manager.broadcast_alarm", new_callable=AsyncMock)
    async def test_process_alarm(self, mock_ws, client, operator_user, async_db):
        """PUT /alarms/{id}/process — 处理告警"""
        _, token = operator_user
        _, _, alarms = await _seed_points_and_alarms(async_db)
        active_alarm = alarms[4]  # status=active
        resp = await client.put(
            f"/api/v1/alarms/{active_alarm.id}/process",
            json={"process_remark": "正在处理中"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["message"] == "告警处理记录已保存"
        mock_ws.assert_called_once()

    @patch("app.api.v1.alarm.ws_manager.broadcast_alarm", new_callable=AsyncMock)
    async def test_process_resolved_alarm(self, mock_ws, client, operator_user, async_db):
        """PUT /alarms/{id}/process — resolved 状态不可处理"""
        _, token = operator_user
        _, _, alarms = await _seed_points_and_alarms(async_db)
        resolved_alarm = alarms[3]
        resp = await client.put(
            f"/api/v1/alarms/{resolved_alarm.id}/process",
            json={"process_remark": "test"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 400

    @patch("app.api.v1.alarm.ws_manager.broadcast_alarm", new_callable=AsyncMock)
    async def test_batch_acknowledge(self, mock_ws, client, operator_user, async_db):
        """PUT /alarms/batch-acknowledge — 批量确认"""
        _, token = operator_user
        _, _, alarms = await _seed_points_and_alarms(async_db)
        ids = [a.id for a in alarms if a.status == "active"]
        resp = await client.put(
            "/api/v1/alarms/batch-acknowledge",
            json={"alarm_ids": ids, "remark": "批量确认"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "count" in data
        mock_ws.assert_called_once()


# ============== 告警规则 CRUD ==============

class TestAlarmRules:
    """告警规则管理"""

    async def test_create_rule(self, client, operator_user, async_db):
        """POST /alarms/rules — 创建规则"""
        _, token = operator_user
        resp = await client.post(
            "/api/v1/alarms/rules",
            json={
                "rule_name": "测试规则",
                "rule_type": "and",
                "alarm_level": "major",
                "alarm_message": "复合告警",
                "is_enabled": True,
            },
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["rule_name"] == "测试规则"
        assert data["id"] is not None

    async def test_get_rules_list(self, client, admin_user, async_db):
        """GET /alarms/rules — 规则列表"""
        _, token = admin_user
        rule = AlarmRule(
            rule_name="列表测试规则", rule_type="or",
            alarm_level="minor", is_enabled=True,
        )
        async_db.add(rule)
        await async_db.flush()

        resp = await client.get("/api/v1/alarms/rules", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    async def test_get_rules_filter(self, client, admin_user, async_db):
        """GET /alarms/rules — 带筛选"""
        _, token = admin_user
        rule = AlarmRule(
            rule_name="筛选规则", rule_type="and",
            alarm_level="critical", is_enabled=True,
        )
        async_db.add(rule)
        await async_db.flush()

        resp = await client.get(
            "/api/v1/alarms/rules",
            params={"rule_type": "and", "alarm_level": "critical", "is_enabled": True},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200

    async def test_get_rule_detail(self, client, admin_user, async_db):
        """GET /alarms/rules/{id} — 规则详情"""
        _, token = admin_user
        rule = AlarmRule(
            rule_name="详情规则", rule_type="and",
            alarm_level="major", is_enabled=True,
        )
        async_db.add(rule)
        await async_db.flush()

        resp = await client.get(
            f"/api/v1/alarms/rules/{rule.id}", headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["rule_name"] == "详情规则"

    async def test_get_rule_not_found(self, client, admin_user, async_db):
        """GET /alarms/rules/99999 — 不存在"""
        _, token = admin_user
        resp = await client.get(
            "/api/v1/alarms/rules/99999", headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_update_rule(self, client, operator_user, async_db):
        """PUT /alarms/rules/{id} — 更新规则"""
        _, token = operator_user
        rule = AlarmRule(
            rule_name="待更新规则", rule_type="and",
            alarm_level="minor", is_enabled=True,
        )
        async_db.add(rule)
        await async_db.flush()

        resp = await client.put(
            f"/api/v1/alarms/rules/{rule.id}",
            json={"rule_name": "已更新规则", "alarm_level": "critical"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["rule_name"] == "已更新规则"
        assert resp.json()["alarm_level"] == "critical"

    async def test_update_rule_not_found(self, client, operator_user, async_db):
        """PUT /alarms/rules/99999 — 不存在"""
        _, token = operator_user
        resp = await client.put(
            "/api/v1/alarms/rules/99999",
            json={"rule_name": "x"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_delete_rule(self, client, operator_user, async_db):
        """DELETE /alarms/rules/{id} — 删除规则"""
        _, token = operator_user
        rule = AlarmRule(
            rule_name="待删除规则", rule_type="or",
            alarm_level="info", is_enabled=False,
        )
        async_db.add(rule)
        await async_db.flush()

        resp = await client.delete(
            f"/api/v1/alarms/rules/{rule.id}", headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert "已删除" in resp.json()["message"]

    async def test_delete_rule_not_found(self, client, operator_user, async_db):
        """DELETE /alarms/rules/99999 — 不存在"""
        _, token = operator_user
        resp = await client.delete(
            "/api/v1/alarms/rules/99999", headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_toggle_rule(self, client, operator_user, async_db):
        """PUT /alarms/rules/{id}/toggle — 切换启用"""
        _, token = operator_user
        rule = AlarmRule(
            rule_name="切换规则", rule_type="and",
            alarm_level="major", is_enabled=True,
        )
        async_db.add(rule)
        await async_db.flush()

        resp = await client.put(
            f"/api/v1/alarms/rules/{rule.id}/toggle",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_enabled"] is False

    async def test_toggle_rule_not_found(self, client, operator_user, async_db):
        """PUT /alarms/rules/99999/toggle — 不存在"""
        _, token = operator_user
        resp = await client.put(
            "/api/v1/alarms/rules/99999/toggle",
            headers=auth_headers(token),
        )
        assert resp.status_code == 404


# ============== 告警屏蔽 ==============

class TestAlarmShields:
    """告警屏蔽管理"""

    async def test_create_shield(self, client, operator_user, async_db):
        """POST /alarms/shields — 创建屏蔽"""
        _, token = operator_user
        point = Point(
            point_code="SH-TEST-001", point_name="屏蔽测试点位",
            point_type="AI", device_type="TH",
        )
        async_db.add(point)
        await async_db.flush()

        now = datetime.now()
        resp = await client.post(
            "/api/v1/alarms/shields",
            json={
                "point_id": point.id,
                "alarm_level": "minor",
                "start_time": now.isoformat(),
                "end_time": (now + timedelta(hours=2)).isoformat(),
                "reason": "维护中",
            },
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] is not None
        assert data["status"] == "active"

    async def test_get_shields_list(self, client, admin_user, async_db):
        """GET /alarms/shields — 屏蔽列表"""
        _, token = admin_user
        point = Point(
            point_code="SH-LIST-001", point_name="屏蔽列表点位",
            point_type="AI", device_type="TH",
        )
        async_db.add(point)
        await async_db.flush()

        now = datetime.now()
        shield = AlarmShield(
            point_id=point.id, alarm_level="major",
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=1),
            reason="测试屏蔽",
        )
        async_db.add(shield)
        await async_db.flush()

        resp = await client.get("/api/v1/alarms/shields", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    async def test_get_shields_expired(self, client, admin_user, async_db):
        """GET /alarms/shields — 过期屏蔽状态为 expired"""
        _, token = admin_user
        now = datetime.now()
        shield = AlarmShield(
            alarm_level="info",
            start_time=now - timedelta(hours=3),
            end_time=now - timedelta(hours=1),
            reason="已过期屏蔽",
        )
        async_db.add(shield)
        await async_db.flush()

        resp = await client.get("/api/v1/alarms/shields", headers=auth_headers(token))
        assert resp.status_code == 200
        items = resp.json()["items"]
        expired = [s for s in items if s["reason"] == "已过期屏蔽"]
        if expired:
            assert expired[0]["status"] == "expired"

    async def test_delete_shield(self, client, operator_user, async_db):
        """DELETE /alarms/shields/{id} — 删除屏蔽"""
        _, token = operator_user
        now = datetime.now()
        shield = AlarmShield(
            alarm_level="critical",
            start_time=now, end_time=now + timedelta(hours=1),
            reason="待删除",
        )
        async_db.add(shield)
        await async_db.flush()

        resp = await client.delete(
            f"/api/v1/alarms/shields/{shield.id}",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert "已删除" in resp.json()["message"]

    async def test_delete_shield_not_found(self, client, operator_user, async_db):
        """DELETE /alarms/shields/99999 — 不存在"""
        _, token = operator_user
        resp = await client.delete(
            "/api/v1/alarms/shields/99999",
            headers=auth_headers(token),
        )
        assert resp.status_code == 404
