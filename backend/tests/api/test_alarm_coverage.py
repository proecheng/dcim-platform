"""
告警管理 API 覆盖率测试 — 覆盖 alarm.py 中未测试的端点
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from app.models.alarm import Alarm, AlarmRule, AlarmShield
from app.models.point import Point
from tests.conftest import auth_headers


# ============== 辅助函数 ==============


async def _seed_points_and_alarms(async_db):
    """创建测试点位和告警数据，返回 (point, point2, alarms)"""
    point = Point(
        point_code="TH-TEST-001",
        point_name="测试温度点位",
        point_type="AI",
        device_type="TH",
        area_code="A1",
    )
    point2 = Point(
        point_code="UPS-TEST-001",
        point_name="测试UPS点位",
        point_type="AI",
        device_type="UPS",
        area_code="B1",
    )
    async_db.add_all([point, point2])
    await async_db.flush()

    now = datetime.now()
    alarms = []
    for i, (pt, level, status) in enumerate(
        [
            (point, "critical", "active"),
            (point, "major", "active"),
            (point, "minor", "acknowledged"),
            (point2, "info", "resolved"),
            (point2, "critical", "active"),
        ]
    ):
        a = Alarm(
            alarm_no=f"ALM-COV-{i + 1:03d}",
            point_id=pt.id,
            alarm_level=level,
            alarm_type="threshold",
            alarm_message=f"测试告警消息{i + 1}",
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
            "/api/v1/alarms",
            params={"status": "active"},
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
            "/api/v1/alarms",
            params={"level": "critical"},
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
            "/api/v1/alarms",
            params={"device_type": "TH"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200

    async def test_get_alarms_filter_keyword(self, client, admin_user, async_db):
        """GET /alarms?keyword=消息 — 关键词搜索"""
        _, token = admin_user
        await _seed_points_and_alarms(async_db)
        resp = await client.get(
            "/api/v1/alarms",
            params={"keyword": "消息"},
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
            "/api/v1/alarms/trend",
            params={"days": 7},
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
            "/api/v1/alarms/top-points",
            params={"days": 7, "limit": 5},
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
            f"/api/v1/alarms/{alarm_id}",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == alarm_id
        assert data["point_code"] is not None

    async def test_get_alarm_not_found(self, client, admin_user, async_db):
        """GET /alarms/99999 — 不存在的告警"""
        _, token = admin_user
        resp = await client.get(
            "/api/v1/alarms/99999",
            headers=auth_headers(token),
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
            rule_name="列表测试规则",
            rule_type="or",
            alarm_level="minor",
            is_enabled=True,
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
            rule_name="筛选规则",
            rule_type="and",
            alarm_level="critical",
            is_enabled=True,
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
            rule_name="详情规则",
            rule_type="and",
            alarm_level="major",
            is_enabled=True,
        )
        async_db.add(rule)
        await async_db.flush()

        resp = await client.get(
            f"/api/v1/alarms/rules/{rule.id}",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["rule_name"] == "详情规则"

    async def test_get_rule_not_found(self, client, admin_user, async_db):
        """GET /alarms/rules/99999 — 不存在"""
        _, token = admin_user
        resp = await client.get(
            "/api/v1/alarms/rules/99999",
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_update_rule(self, client, operator_user, async_db):
        """PUT /alarms/rules/{id} — 更新规则"""
        _, token = operator_user
        rule = AlarmRule(
            rule_name="待更新规则",
            rule_type="and",
            alarm_level="minor",
            is_enabled=True,
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
            rule_name="待删除规则",
            rule_type="or",
            alarm_level="info",
            is_enabled=False,
        )
        async_db.add(rule)
        await async_db.flush()

        resp = await client.delete(
            f"/api/v1/alarms/rules/{rule.id}",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert "已删除" in resp.json()["message"]

    async def test_delete_rule_not_found(self, client, operator_user, async_db):
        """DELETE /alarms/rules/99999 — 不存在"""
        _, token = operator_user
        resp = await client.delete(
            "/api/v1/alarms/rules/99999",
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_toggle_rule(self, client, operator_user, async_db):
        """PUT /alarms/rules/{id}/toggle — 切换启用"""
        _, token = operator_user
        rule = AlarmRule(
            rule_name="切换规则",
            rule_type="and",
            alarm_level="major",
            is_enabled=True,
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
            point_code="SH-TEST-001",
            point_name="屏蔽测试点位",
            point_type="AI",
            device_type="TH",
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
            point_code="SH-LIST-001",
            point_name="屏蔽列表点位",
            point_type="AI",
            device_type="TH",
        )
        async_db.add(point)
        await async_db.flush()

        now = datetime.now()
        shield = AlarmShield(
            point_id=point.id,
            alarm_level="major",
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
            start_time=now,
            end_time=now + timedelta(hours=1),
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


# ============== 补充覆盖率测试 ==============


class TestAlarmListCoverageExtra:
    """补充 get_alarms 的分页、点位信息获取、keyword 分支 (L56, L69-85)"""

    async def test_get_alarms_keyword_with_results(self, client, admin_user, async_db):
        """GET /alarms?keyword=告警消息1 — keyword 筛选命中"""
        _, token = admin_user
        point, _, alarms = await _seed_points_and_alarms(async_db)
        resp = await client.get(
            "/api/v1/alarms",
            params={"keyword": "告警消息1"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["point_code"] is not None
            assert item["point_name"] is not None

    async def test_get_alarms_pagination_page2(self, client, admin_user, async_db):
        """GET /alarms?page=2&page_size=2 — 第二页分页 (L69-85)"""
        _, token = admin_user
        await _seed_points_and_alarms(async_db)
        resp = await client.get(
            "/api/v1/alarms",
            params={"page": 2, "page_size": 2},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 2
        assert data["page_size"] == 2
        assert data["total"] >= 5

    async def test_get_alarms_point_id_filter(self, client, admin_user, async_db):
        """GET /alarms?point_id=X — 按点位ID筛选 (L55-56)"""
        _, token = admin_user
        point, _, _ = await _seed_points_and_alarms(async_db)
        resp = await client.get(
            "/api/v1/alarms",
            params={"point_id": point.id},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1


class TestActiveAlarmsCoverageExtra:
    """补充 get_active_alarms 的点位信息获取 (L108-120)"""

    async def test_active_alarms_with_point_info(self, client, admin_user, async_db):
        """GET /alarms/active — 验证返回的活动告警包含点位信息"""
        _, token = admin_user
        await _seed_points_and_alarms(async_db)
        resp = await client.get("/api/v1/alarms/active", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 3
        for item in data:
            assert item["point_code"] is not None
            assert item["point_name"] is not None


class TestAlarmTrendCoverageExtra:
    """补充 get_alarm_trend 的数据整理 (L243-250)"""

    async def test_trend_with_data(self, client, admin_user, async_db):
        """GET /alarms/trend — 有数据时返回趋势列表"""
        _, token = admin_user
        await _seed_points_and_alarms(async_db)
        resp = await client.get(
            "/api/v1/alarms/trend",
            params={"days": 1},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        if data:
            item = data[0]
            assert "date" in item
            assert "critical" in item
            assert "major" in item
            assert "minor" in item
            assert "info" in item


class TestTopAlarmPointsCoverageExtra:
    """补充 get_top_alarm_points 的点位查询 (L278-290)"""

    async def test_top_points_with_valid_points(self, client, admin_user, async_db):
        """GET /alarms/top-points — 有数据时返回点位信息"""
        _, token = admin_user
        await _seed_points_and_alarms(async_db)
        resp = await client.get(
            "/api/v1/alarms/top-points",
            params={"days": 1, "limit": 10},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["point_code"] is not None
        assert data[0]["point_name"] is not None
        assert data[0]["alarm_count"] >= 1


class TestExportCoverageExtra:
    """补充 export_alarms 的 CSV 写入 (L314-331)"""

    async def test_export_csv_content(self, client, operator_user, async_db):
        """GET /alarms/export — 验证 CSV 内容包含告警数据"""
        _, token = operator_user
        await _seed_points_and_alarms(async_db)
        resp = await client.get("/api/v1/alarms/export", headers=auth_headers(token))
        assert resp.status_code == 200
        content = resp.text
        assert "ALM-COV-001" in content

    async def test_export_with_time_range(self, client, operator_user, async_db):
        """GET /alarms/export — 带时间范围导出"""
        _, token = operator_user
        await _seed_points_and_alarms(async_db)
        now = datetime.now()
        resp = await client.get(
            "/api/v1/alarms/export",
            params={
                "start_time": (now - timedelta(days=1)).isoformat(),
                "end_time": now.isoformat(),
            },
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("content-type", "")


class TestBatchAckCoverageExtra:
    """补充 batch_acknowledge 的 WebSocket 广播 (L358-370)"""

    @patch("app.api.v1.alarm.ws_manager.broadcast_alarm", new_callable=AsyncMock)
    async def test_batch_ack_ws_payload(self, mock_ws, client, operator_user, async_db):
        """PUT /alarms/batch-acknowledge — 验证 WS 广播内容"""
        _, token = operator_user
        _, _, alarms = await _seed_points_and_alarms(async_db)
        active_ids = [a.id for a in alarms if a.status == "active"]
        resp = await client.put(
            "/api/v1/alarms/batch-acknowledge",
            json={"alarm_ids": active_ids, "remark": "batch_test"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 1
        call_args = mock_ws.call_args[0][0]
        assert call_args["action"] == "batch_ack"
        assert "alarm_ids" in call_args

    @patch("app.api.v1.alarm.ws_manager.broadcast_alarm", new_callable=AsyncMock)
    async def test_batch_ack_no_matching(self, mock_ws, client, operator_user, async_db):
        """PUT /alarms/batch-acknowledge — 无匹配告警"""
        _, token = operator_user
        resp = await client.put(
            "/api/v1/alarms/batch-acknowledge",
            json={"alarm_ids": [99998, 99999], "remark": "none"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["count"] == 0


class TestAlarmRulesCoverageExtra:
    """补充告警规则 CRUD 的分页和创建 (L402-405, L429-431, L446-527)"""

    async def test_rules_pagination(self, client, admin_user, async_db):
        """GET /alarms/rules — 分页参数"""
        _, token = admin_user
        for i in range(5):
            rule = AlarmRule(
                rule_name=f"pag_rule_{i}",
                rule_type="and",
                alarm_level="minor",
                is_enabled=True,
            )
            async_db.add(rule)
        await async_db.flush()

        resp = await client.get(
            "/api/v1/alarms/rules",
            params={"page": 2, "page_size": 2},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        assert data["page"] == 2
        assert len(data["items"]) == 2

    async def test_create_rule_minimal(self, client, operator_user, async_db):
        """POST /alarms/rules — 最小参数创建"""
        _, token = operator_user
        resp = await client.post(
            "/api/v1/alarms/rules",
            json={"rule_name": "min_rule", "rule_type": "or", "alarm_level": "info"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["rule_name"] == "min_rule"
        assert data["is_enabled"] is True

    async def test_toggle_rule_enable(self, client, operator_user, async_db):
        """PUT /alarms/rules/{id}/toggle — 禁用后再启用"""
        _, token = operator_user
        rule = AlarmRule(
            rule_name="toggle_enable",
            rule_type="and",
            alarm_level="major",
            is_enabled=False,
        )
        async_db.add(rule)
        await async_db.flush()

        resp = await client.put(
            f"/api/v1/alarms/rules/{rule.id}/toggle",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["is_enabled"] is True


class TestAlarmShieldsCoverageExtra:
    """补充告警屏蔽的点位信息和状态计算 (L553-587, L612-618, L633-641)"""

    async def test_shields_list_with_point_info(self, client, admin_user, async_db):
        """GET /alarms/shields — 屏蔽列表包含点位信息 (L571-577)"""
        _, token = admin_user
        point = Point(
            point_code="SH-EXTRA-001",
            point_name="extra_shield_pt",
            point_type="AI",
            device_type="UPS",
        )
        async_db.add(point)
        await async_db.flush()

        now = datetime.now()
        shield = AlarmShield(
            point_id=point.id,
            alarm_level="critical",
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=1),
            reason="with_point",
        )
        async_db.add(shield)
        await async_db.flush()

        resp = await client.get("/api/v1/alarms/shields", headers=auth_headers(token))
        assert resp.status_code == 200
        items = resp.json()["items"]
        matched = [s for s in items if s["reason"] == "with_point"]
        assert len(matched) == 1
        assert matched[0]["point_code"] == "SH-EXTRA-001"
        assert matched[0]["point_name"] == "extra_shield_pt"
        assert matched[0]["status"] == "active"

    async def test_shields_list_expired_status(self, client, admin_user, async_db):
        """GET /alarms/shields — 过期屏蔽状态计算 (L580-583)"""
        _, token = admin_user
        now = datetime.now()
        shield = AlarmShield(
            alarm_level="minor",
            start_time=now - timedelta(hours=5),
            end_time=now - timedelta(hours=2),
            reason="expired_test",
        )
        async_db.add(shield)
        await async_db.flush()

        resp = await client.get("/api/v1/alarms/shields", headers=auth_headers(token))
        assert resp.status_code == 200
        items = resp.json()["items"]
        matched = [s for s in items if s["reason"] == "expired_test"]
        assert len(matched) == 1
        assert matched[0]["status"] == "expired"

    async def test_shields_filter_by_point_id(self, client, admin_user, async_db):
        """GET /alarms/shields?point_id=X — 按点位筛选 (L552-553)"""
        _, token = admin_user
        point = Point(
            point_code="SH-FILTER-001",
            point_name="filter_pt",
            point_type="AI",
            device_type="TH",
        )
        async_db.add(point)
        await async_db.flush()

        now = datetime.now()
        shield = AlarmShield(
            point_id=point.id,
            alarm_level="major",
            start_time=now,
            end_time=now + timedelta(hours=1),
            reason="filter_test",
        )
        async_db.add(shield)
        await async_db.flush()

        resp = await client.get(
            "/api/v1/alarms/shields",
            params={"point_id": point.id},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    async def test_shields_filter_by_alarm_level(self, client, admin_user, async_db):
        """GET /alarms/shields?alarm_level=critical — 按级别筛选 (L554-555)"""
        _, token = admin_user
        now = datetime.now()
        shield = AlarmShield(
            alarm_level="critical",
            start_time=now,
            end_time=now + timedelta(hours=1),
            reason="level_filter",
        )
        async_db.add(shield)
        await async_db.flush()

        resp = await client.get(
            "/api/v1/alarms/shields",
            params={"alarm_level": "critical"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    async def test_create_shield_expired(self, client, operator_user, async_db):
        """POST /alarms/shields — 创建已过期屏蔽 (L616 expired 分支)"""
        _, token = operator_user
        now = datetime.now()
        resp = await client.post(
            "/api/v1/alarms/shields",
            json={
                "alarm_level": "info",
                "start_time": (now - timedelta(hours=3)).isoformat(),
                "end_time": (now - timedelta(hours=1)).isoformat(),
                "reason": "create_expired",
            },
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "expired"

    async def test_create_shield_no_point(self, client, operator_user, async_db):
        """POST /alarms/shields — 全局屏蔽（无点位）"""
        _, token = operator_user
        now = datetime.now()
        resp = await client.post(
            "/api/v1/alarms/shields",
            json={
                "alarm_level": "major",
                "start_time": now.isoformat(),
                "end_time": (now + timedelta(hours=1)).isoformat(),
                "reason": "global_shield",
            },
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"


class TestAlarmDetailCoverageExtra:
    """补充告警详情的点位信息 (L656-668)"""

    async def test_alarm_detail_with_point(self, client, admin_user, async_db):
        """GET /alarms/{id} — 详情包含点位信息"""
        _, token = admin_user
        _, _, alarms = await _seed_points_and_alarms(async_db)
        resp = await client.get(
            f"/api/v1/alarms/{alarms[0].id}",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["point_code"] == "TH-TEST-001"
        assert data["point_name"] is not None

    async def test_alarm_detail_resolved(self, client, admin_user, async_db):
        """GET /alarms/{id} — 已解决告警详情"""
        _, token = admin_user
        _, _, alarms = await _seed_points_and_alarms(async_db)
        resolved = alarms[3]
        resp = await client.get(
            f"/api/v1/alarms/{resolved.id}",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "resolved"
        assert data["duration_seconds"] == 3600


class TestAcknowledgeCoverageExtra:
    """补充 acknowledge_alarm 的完整流程 (L682-711)"""

    @patch("app.api.v1.alarm.ws_manager.broadcast_alarm", new_callable=AsyncMock)
    async def test_ack_not_found(self, mock_ws, client, operator_user, async_db):
        """PUT /alarms/99999/acknowledge — 不存在"""
        _, token = operator_user
        resp = await client.put(
            "/api/v1/alarms/99999/acknowledge",
            json={"remark": "test"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    @patch("app.api.v1.alarm.ws_manager.broadcast_alarm", new_callable=AsyncMock)
    async def test_ack_ws_payload(self, mock_ws, client, operator_user, async_db):
        """PUT /alarms/{id}/acknowledge — 验证 WS 广播内容"""
        _, token = operator_user
        _, _, alarms = await _seed_points_and_alarms(async_db)
        active = alarms[4]
        resp = await client.put(
            f"/api/v1/alarms/{active.id}/acknowledge",
            json={"remark": "ws_test"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        call_args = mock_ws.call_args[0][0]
        assert call_args["action"] == "ack"
        assert call_args["status"] == "acknowledged"
        assert call_args["ack_remark"] == "ws_test"

    @patch("app.api.v1.alarm.ws_manager.broadcast_alarm", new_callable=AsyncMock)
    async def test_ack_acknowledged_alarm(self, mock_ws, client, operator_user, async_db):
        """PUT /alarms/{id}/acknowledge — acknowledged 状态不可再确认"""
        _, token = operator_user
        _, _, alarms = await _seed_points_and_alarms(async_db)
        acked = alarms[2]
        resp = await client.put(
            f"/api/v1/alarms/{acked.id}/acknowledge",
            json={"remark": "test"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 400


class TestResolveCoverageExtra:
    """补充 resolve_alarm 的完整流程 (L725-760)"""

    @patch("app.api.v1.alarm.ws_manager.broadcast_alarm", new_callable=AsyncMock)
    async def test_resolve_not_found(self, mock_ws, client, operator_user, async_db):
        """PUT /alarms/99999/resolve — 不存在"""
        _, token = operator_user
        resp = await client.put(
            "/api/v1/alarms/99999/resolve",
            json={"remark": "test"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    @patch("app.api.v1.alarm.ws_manager.broadcast_alarm", new_callable=AsyncMock)
    async def test_resolve_ws_payload(self, mock_ws, client, operator_user, async_db):
        """PUT /alarms/{id}/resolve — 验证 WS 广播内容"""
        _, token = operator_user
        _, _, alarms = await _seed_points_and_alarms(async_db)
        active = alarms[0]
        resp = await client.put(
            f"/api/v1/alarms/{active.id}/resolve",
            json={"remark": "ws_resolve", "resolve_type": "auto"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        call_args = mock_ws.call_args[0][0]
        assert call_args["action"] == "resolve"
        assert call_args["status"] == "resolved"
        assert call_args["resolve_type"] == "auto"
        assert "duration_seconds" in call_args

    @patch("app.api.v1.alarm.ws_manager.broadcast_alarm", new_callable=AsyncMock)
    async def test_resolve_acknowledged_alarm(self, mock_ws, client, operator_user, async_db):
        """PUT /alarms/{id}/resolve — acknowledged 状态可以解决"""
        _, token = operator_user
        _, _, alarms = await _seed_points_and_alarms(async_db)
        acked = alarms[2]
        resp = await client.put(
            f"/api/v1/alarms/{acked.id}/resolve",
            json={"remark": "resolve_acked"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["message"] == "告警已解决"

    @patch("app.api.v1.alarm.ws_manager.broadcast_alarm", new_callable=AsyncMock)
    async def test_resolve_default_type(self, mock_ws, client, operator_user, async_db):
        """PUT /alarms/{id}/resolve — 默认 resolve_type=manual"""
        _, token = operator_user
        _, _, alarms = await _seed_points_and_alarms(async_db)
        active = alarms[4]
        resp = await client.put(
            f"/api/v1/alarms/{active.id}/resolve",
            json={"remark": "default_type"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        call_args = mock_ws.call_args[0][0]
        assert call_args["resolve_type"] == "manual"


class TestProcessCoverageExtra:
    """补充 process_alarm 的完整流程 (L774-801)"""

    @patch("app.api.v1.alarm.ws_manager.broadcast_alarm", new_callable=AsyncMock)
    async def test_process_not_found(self, mock_ws, client, operator_user, async_db):
        """PUT /alarms/99999/process — 不存在"""
        _, token = operator_user
        resp = await client.put(
            "/api/v1/alarms/99999/process",
            json={"process_remark": "test"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    @patch("app.api.v1.alarm.ws_manager.broadcast_alarm", new_callable=AsyncMock)
    async def test_process_ws_payload(self, mock_ws, client, operator_user, async_db):
        """PUT /alarms/{id}/process — 验证 WS 广播内容"""
        _, token = operator_user
        _, _, alarms = await _seed_points_and_alarms(async_db)
        active = alarms[0]
        resp = await client.put(
            f"/api/v1/alarms/{active.id}/process",
            json={"process_remark": "ws_process"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        call_args = mock_ws.call_args[0][0]
        assert call_args["action"] == "update"
        assert call_args["process_remark"] == "ws_process"
        assert "processed_at" in call_args

    @patch("app.api.v1.alarm.ws_manager.broadcast_alarm", new_callable=AsyncMock)
    async def test_process_acknowledged_alarm(self, mock_ws, client, operator_user, async_db):
        """PUT /alarms/{id}/process — acknowledged 状态可以处理"""
        _, token = operator_user
        _, _, alarms = await _seed_points_and_alarms(async_db)
        acked = alarms[2]
        resp = await client.put(
            f"/api/v1/alarms/{acked.id}/process",
            json={"process_remark": "process_acked"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["message"] == "告警处理记录已保存"


class TestAlarmStatisticsCoverageExtra:
    """补充告警统计的各种筛选分支 (L179-208)"""

    async def test_statistics_with_time_range(self, client, admin_user, async_db):
        """GET /alarms/statistics — 自定义时间范围"""
        _, token = admin_user
        await _seed_points_and_alarms(async_db)
        now = datetime.now()
        resp = await client.get(
            "/api/v1/alarms/statistics",
            params={
                "start_time": (now - timedelta(hours=12)).isoformat(),
                "end_time": now.isoformat(),
            },
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["by_level"]) >= 1
        assert len(data["by_status"]) >= 1

    async def test_statistics_device_type_only(self, client, admin_user, async_db):
        """GET /alarms/statistics?device_type=UPS — 仅设备类型筛选"""
        _, token = admin_user
        await _seed_points_and_alarms(async_db)
        resp = await client.get(
            "/api/v1/alarms/statistics",
            params={"device_type": "UPS"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    async def test_statistics_alarm_level_only(self, client, admin_user, async_db):
        """GET /alarms/statistics?alarm_level=major — 仅级别筛选"""
        _, token = admin_user
        await _seed_points_and_alarms(async_db)
        resp = await client.get(
            "/api/v1/alarms/statistics",
            params={"alarm_level": "major"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
