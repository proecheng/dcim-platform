"""
灾难恢复演练 API 集成测试
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone

from tests.conftest import auth_headers

# Mock 路径
DRILL_SERVICE_PATH = "app.api.v1.chaos_drill.ChaosDrillService"
BREAKER_PATH = "app.api.v1.chaos_drill._get_breaker"

PREFIX = "/api/v1/diagnosis/chaos"

MOCK_SCHEDULE = {
    "enabled": True,
    "cron_expression": "0 2 * * 0",
    "window_minutes": 120,
    "scenarios": ["circuit_breaker_degradation", "db_timeout_fallback"],
    "confirmed": False,
    "confirmed_by": None,
    "confirmed_at": None,
    "next_run_time": None,
}


# ---------- GET /schedule ----------


@pytest.mark.asyncio
@patch(DRILL_SERVICE_PATH)
async def test_get_schedule_success(MockService, client, admin_token):
    """管理员获取演练计划 — 成功"""
    instance = MockService.return_value
    instance.get_drill_schedule = AsyncMock(return_value=MOCK_SCHEDULE)

    resp = await client.get(f"{PREFIX}/schedule", headers=auth_headers(admin_token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["enabled"] is True
    assert data["cron_expression"] == "0 2 * * 0"


@pytest.mark.asyncio
async def test_get_schedule_viewer_forbidden(client, viewer_token):
    """只读用户获取演练计划 — 403"""
    resp = await client.get(f"{PREFIX}/schedule", headers=auth_headers(viewer_token))
    assert resp.status_code == 403


# ---------- PUT /schedule ----------


@pytest.mark.asyncio
@patch(DRILL_SERVICE_PATH)
async def test_update_schedule_success(MockService, client, admin_token):
    """管理员更新演练计划 — 成功"""
    updated = {**MOCK_SCHEDULE, "window_minutes": 60}
    instance = MockService.return_value
    instance.update_drill_schedule = AsyncMock(return_value=updated)

    resp = await client.put(
        f"{PREFIX}/schedule",
        json={"window_minutes": 60},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["window_minutes"] == 60


@pytest.mark.asyncio
@patch(DRILL_SERVICE_PATH)
async def test_update_schedule_value_error(MockService, client, admin_token):
    """更新演练计划参数非法 — 400"""
    instance = MockService.return_value
    instance.update_drill_schedule = AsyncMock(side_effect=ValueError("无效的 cron 表达式"))

    resp = await client.put(
        f"{PREFIX}/schedule",
        json={"cron_expression": "bad"},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 400
    assert "无效的 cron 表达式" in resp.json()["detail"]


# ---------- POST /schedule/confirm ----------


@pytest.mark.asyncio
@patch(DRILL_SERVICE_PATH)
async def test_confirm_schedule_success(MockService, client, admin_token):
    """管理员确认演练计划 — 成功"""
    instance = MockService.return_value
    instance.confirm_drill_schedule = AsyncMock(return_value=None)

    resp = await client.post(f"{PREFIX}/schedule/confirm", headers=auth_headers(admin_token))
    assert resp.status_code == 200
    assert resp.json()["message"] == "演练计划已确认"


@pytest.mark.asyncio
@patch(DRILL_SERVICE_PATH)
async def test_confirm_schedule_value_error(MockService, client, admin_token):
    """确认演练计划失败（如未配置） — 400"""
    instance = MockService.return_value
    instance.confirm_drill_schedule = AsyncMock(side_effect=ValueError("计划尚未配置"))

    resp = await client.post(f"{PREFIX}/schedule/confirm", headers=auth_headers(admin_token))
    assert resp.status_code == 400
    assert "计划尚未配置" in resp.json()["detail"]


# ---------- POST /trigger ----------


@pytest.mark.asyncio
@patch(BREAKER_PATH, return_value=MagicMock())
@patch(DRILL_SERVICE_PATH)
async def test_trigger_drill_success(MockService, mock_breaker, client, admin_token):
    """管理员触发演练 — 202"""
    instance = MockService.return_value
    instance.trigger_drill = AsyncMock(return_value="drill-001")

    resp = await client.post(
        f"{PREFIX}/trigger",
        json={"scenarios": ["circuit_breaker_degradation"]},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 202
    data = resp.json()
    assert data["drill_id"] == "drill-001"
    assert "已启动" in data["message"]


@pytest.mark.asyncio
async def test_trigger_drill_viewer_forbidden(client, viewer_token):
    """只读用户触发演练 — 403"""
    resp = await client.post(
        f"{PREFIX}/trigger",
        json={"scenarios": ["circuit_breaker_degradation"]},
        headers=auth_headers(viewer_token),
    )
    assert resp.status_code == 403


# ---------- POST /stop ----------


@pytest.mark.asyncio
@patch(BREAKER_PATH, return_value=None)
@patch(DRILL_SERVICE_PATH)
async def test_stop_drill_success(MockService, mock_breaker, client, admin_token):
    """管理员终止演练 — 成功"""
    instance = MockService.return_value
    instance.stop_drill = AsyncMock(return_value="drill-001")

    resp = await client.post(f"{PREFIX}/stop", headers=auth_headers(admin_token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["drill_id"] == "drill-001"
    assert "已终止" in data["message"]


# ---------- GET /history ----------


@pytest.mark.asyncio
@patch(DRILL_SERVICE_PATH)
async def test_get_history_success(MockService, client, admin_token):
    """管理员查看演练历史 — 成功"""
    now = datetime.now(timezone.utc)
    instance = MockService.return_value
    instance.get_drill_history = AsyncMock(return_value={
        "total": 1,
        "items": [
            MagicMock(
                id=1,
                report_name="演练报告-001",
                report_type="chaos_drill",
                status="completed",
                report_data=None,
                created_at=now,
            )
        ],
    })

    resp = await client.get(
        f"{PREFIX}/history",
        params={"page": 1, "page_size": 10},
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["report_type"] == "chaos_drill"
