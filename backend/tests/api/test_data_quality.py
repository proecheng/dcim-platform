"""
数据质量 API 集成测试

测试 GET /api/v1/data-quality/status 和 /api/v1/data-quality/points 端点
"""

import pytest
from datetime import datetime

from app.models.point import Point, PointRealtime
from tests.conftest import auth_headers

URL_PREFIX = "/api/v1/data-quality"


async def _create_point_with_quality(async_db, point_code: str, quality: int = 0):
    """创建测试点位及其实时数据"""
    point = Point(
        point_code=point_code,
        point_name=f"测试点位-{point_code}",
        point_type="AI",
        unit="℃",
        is_enabled=True,
    )
    async_db.add(point)
    await async_db.commit()
    await async_db.refresh(point)

    realtime = PointRealtime(
        point_id=point.id,
        value=25.0,
        quality=quality,
        status="normal",
        source="demo",
        updated_at=datetime.now(),
    )
    async_db.add(realtime)
    await async_db.commit()
    return point


# ==================== GET /status ====================


@pytest.mark.asyncio
async def test_status_empty(client, viewer_token):
    """无数据时返回全零统计"""
    resp = await client.get(
        f"{URL_PREFIX}/status",
        headers=auth_headers(viewer_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["normal_count"] == 0
    assert data["uncertain_count"] == 0
    assert data["unreliable_count"] == 0
    assert data["unreliable_points"] == []


@pytest.mark.asyncio
async def test_status_with_mixed_quality(client, async_db, viewer_token):
    """混合质量点位时统计正确"""
    await _create_point_with_quality(async_db, "DQ_GOOD_1", quality=0)
    await _create_point_with_quality(async_db, "DQ_GOOD_2", quality=0)
    await _create_point_with_quality(async_db, "DQ_UNCERTAIN_1", quality=1)
    await _create_point_with_quality(async_db, "DQ_BAD_1", quality=2)

    resp = await client.get(
        f"{URL_PREFIX}/status",
        headers=auth_headers(viewer_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 4
    assert data["normal_count"] == 2
    assert data["uncertain_count"] == 1
    assert data["unreliable_count"] == 1
    assert len(data["unreliable_points"]) == 1


@pytest.mark.asyncio
async def test_status_counts_correct(client, async_db, admin_token):
    """精确验证各质量等级计数"""
    # 3 good, 2 uncertain, 1 bad
    for i in range(3):
        await _create_point_with_quality(async_db, f"CNT_GOOD_{i}", quality=0)
    for i in range(2):
        await _create_point_with_quality(async_db, f"CNT_UNC_{i}", quality=1)
    await _create_point_with_quality(async_db, "CNT_BAD_0", quality=2)

    resp = await client.get(
        f"{URL_PREFIX}/status",
        headers=auth_headers(admin_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 6
    assert data["normal_count"] == 3
    assert data["uncertain_count"] == 2
    assert data["unreliable_count"] == 1


# ==================== GET /points ====================


@pytest.mark.asyncio
async def test_points_list_all(client, async_db, viewer_token):
    """不带过滤条件时返回全部点位"""
    await _create_point_with_quality(async_db, "PL_A", quality=0)
    await _create_point_with_quality(async_db, "PL_B", quality=1)
    await _create_point_with_quality(async_db, "PL_C", quality=2)

    resp = await client.get(
        f"{URL_PREFIX}/points",
        headers=auth_headers(viewer_token),
    )
    assert resp.status_code == 200
    items = resp.json()
    # 返回应为列表或包含列表的结构
    if isinstance(items, dict):
        items = items.get("items", items.get("data", []))
    assert len(items) >= 3


@pytest.mark.asyncio
async def test_points_filter_by_quality(client, async_db, viewer_token):
    """按 quality 参数过滤点位"""
    await _create_point_with_quality(async_db, "FQ_GOOD", quality=0)
    await _create_point_with_quality(async_db, "FQ_BAD", quality=2)

    # 只获取 quality=2 (bad)
    resp = await client.get(
        f"{URL_PREFIX}/points",
        params={"quality": 2},
        headers=auth_headers(viewer_token),
    )
    assert resp.status_code == 200
    items = resp.json()
    if isinstance(items, dict):
        items = items.get("items", items.get("data", []))
    # 应当只包含 quality=2 的点位
    assert all(
        item.get("quality", item.get("quality_code")) == 2
        for item in items
    )
    assert len(items) >= 1


# ==================== 权限测试 ====================


@pytest.mark.asyncio
async def test_status_unauthorized(client):
    """未认证请求应返回 401 或 403"""
    resp = await client.get(f"{URL_PREFIX}/status")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_points_unauthorized(client):
    """未认证请求点位列表应返回 401 或 403"""
    resp = await client.get(f"{URL_PREFIX}/points")
    assert resp.status_code in (401, 403)
