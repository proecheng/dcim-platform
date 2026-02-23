"""
资产管理 API 核心测试
"""

import pytest
from datetime import datetime, date, timedelta

from app.models.asset import Asset, Cabinet, AssetLifecycle, AssetStatus, AssetType
from tests.conftest import auth_headers


@pytest.fixture
async def sample_cabinet(async_db):
    """创建测试机柜"""
    cabinet = Cabinet(
        cabinet_code="CAB-TEST-001",
        cabinet_name="测试机柜A",
        total_u=42,
        location="A区1排",
    )
    async_db.add(cabinet)
    await async_db.flush()
    return cabinet


@pytest.fixture
async def sample_asset(async_db, sample_cabinet):
    """创建测试资产"""
    asset = Asset(
        asset_code="AST-TEST-001",
        asset_name="测试服务器",
        asset_type=AssetType.server,
        status=AssetStatus.in_use,
        brand="Dell",
        model="R740",
        cabinet_id=sample_cabinet.id,
        u_position=1,
        u_height=2,
        warranty_end=date.today() + timedelta(days=60),
    )
    async_db.add(asset)
    await async_db.flush()
    return asset


class TestCabinetCRUD:
    """机柜 CRUD 测试"""

    async def test_get_cabinets_empty(self, client, admin_user):
        """测试空机柜列表"""
        _, token = admin_user
        resp = await client.get("/api/v1/asset/cabinets", headers=auth_headers(token))
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_create_cabinet(self, client, admin_user):
        """测试创建机柜"""
        _, token = admin_user
        resp = await client.post(
            "/api/v1/asset/cabinets",
            headers=auth_headers(token),
            json={
                "cabinet_code": "CAB-NEW-001",
                "cabinet_name": "新建机柜",
                "total_u": 42,
                "location": "B区",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["cabinet_code"] == "CAB-NEW-001"
        assert body["available_u"] == 42

    async def test_create_cabinet_duplicate_code(self, client, admin_user, sample_cabinet):
        """测试创建重复编码机柜"""
        _, token = admin_user
        resp = await client.post(
            "/api/v1/asset/cabinets",
            headers=auth_headers(token),
            json={
                "cabinet_code": "CAB-TEST-001",
                "cabinet_name": "重复机柜",
                "total_u": 42,
            },
        )
        assert resp.status_code == 400

    async def test_get_cabinet_detail(self, client, admin_user, sample_cabinet):
        """测试获取机柜详情"""
        _, token = admin_user
        resp = await client.get(
            f"/api/v1/asset/cabinets/{sample_cabinet.id}",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["cabinet_code"] == "CAB-TEST-001"

    async def test_get_cabinet_not_found(self, client, admin_user):
        """测试机柜不存在"""
        _, token = admin_user
        resp = await client.get(
            "/api/v1/asset/cabinets/99999",
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_delete_cabinet_with_assets(self, client, admin_user, sample_asset):
        """测试删除有资产的机柜"""
        _, token = admin_user
        resp = await client.delete(
            f"/api/v1/asset/cabinets/{sample_asset.cabinet_id}",
            headers=auth_headers(token),
        )
        assert resp.status_code == 400
        assert "关联资产" in resp.json()["detail"]


class TestAssetCRUD:
    """资产 CRUD 测试"""

    async def test_get_assets_empty(self, client, admin_user):
        """测试空资产列表"""
        _, token = admin_user
        resp = await client.get("/api/v1/asset/assets", headers=auth_headers(token))
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_create_asset(self, client, admin_user, sample_cabinet):
        """测试创建资产"""
        _, token = admin_user
        resp = await client.post(
            "/api/v1/asset/assets",
            headers=auth_headers(token),
            json={
                "asset_code": "AST-NEW-001",
                "asset_name": "新建服务器",
                "asset_type": "server",
                "brand": "HP",
                "model": "DL380",
                "cabinet_id": sample_cabinet.id,
                "u_position": 10,
                "u_height": 2,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["asset_code"] == "AST-NEW-001"

    async def test_create_asset_duplicate_code(self, client, admin_user, sample_asset):
        """测试创建重复编码资产"""
        _, token = admin_user
        resp = await client.post(
            "/api/v1/asset/assets",
            headers=auth_headers(token),
            json={
                "asset_code": "AST-TEST-001",
                "asset_name": "重复资产",
                "asset_type": "server",
            },
        )
        assert resp.status_code == 400

    async def test_get_asset_detail(self, client, admin_user, sample_asset):
        """测试获取资产详情"""
        _, token = admin_user
        resp = await client.get(
            f"/api/v1/asset/assets/{sample_asset.id}",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["asset_code"] == "AST-TEST-001"

    async def test_get_asset_not_found(self, client, admin_user):
        """测试资产不存在"""
        _, token = admin_user
        resp = await client.get(
            "/api/v1/asset/assets/99999",
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_delete_asset(self, client, admin_user, sample_asset):
        """测试删除资产"""
        _, token = admin_user
        resp = await client.delete(
            f"/api/v1/asset/assets/{sample_asset.id}",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert "删除成功" in resp.json()["message"]


class TestAssetStatistics:
    """资产统计测试"""

    async def test_get_statistics(self, client, admin_user, sample_asset):
        """测试获取资产统计"""
        _, token = admin_user
        resp = await client.get("/api/v1/asset/statistics", headers=auth_headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert "total_count" in body
        assert "by_status" in body
        assert "by_type" in body
        assert body["total_count"] >= 1


class TestAssetLifecycle:
    """资产生命周期测试"""

    async def test_get_lifecycle(self, client, admin_user, sample_asset, async_db):
        """测试获取资产生命周期"""
        # 添加生命周期记录
        lifecycle = AssetLifecycle(
            asset_id=sample_asset.id,
            action="purchase",
            action_date=datetime.now(),
            operator="test_admin",
            remark="测试入库",
        )
        async_db.add(lifecycle)
        await async_db.flush()

        _, token = admin_user
        resp = await client.get(
            f"/api/v1/asset/assets/{sample_asset.id}/lifecycle",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) >= 1


class TestAssetWarranty:
    """保修预警测试"""

    async def test_get_warranty_expiring(self, client, admin_user, sample_asset):
        """测试获取即将过保资产"""
        _, token = admin_user
        resp = await client.get(
            "/api/v1/asset/warranty-expiring?days=90",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)

    async def test_get_warranty_alerts(self, client, admin_user, sample_asset):
        """测试获取保修预警汇总"""
        _, token = admin_user
        resp = await client.get(
            "/api/v1/asset/warranty-alerts",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "within_30_days" in body
        assert "within_60_days" in body
        assert "within_90_days" in body
        assert "total_count" in body


class TestCabinetUsage:
    """机柜 U 位使用情况测试"""

    async def test_get_cabinet_usage(self, client, admin_user, sample_asset):
        """测试获取机柜 U 位使用情况"""
        _, token = admin_user
        resp = await client.get(
            f"/api/v1/asset/cabinets/{sample_asset.cabinet_id}/usage",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "total_u" in body
        assert "used_u" in body
        assert "available_u" in body
        assert "u_map" in body
        assert body["used_u"] >= 2  # sample_asset 占 2U
