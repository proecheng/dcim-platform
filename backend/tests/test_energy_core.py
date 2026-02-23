"""
能源管理 API 核心测试
"""

import pytest
from datetime import date, timedelta

from app.models.energy import PowerDevice, ElectricityPricing
from tests.conftest import auth_headers


@pytest.fixture
async def sample_power_device(async_db):
    """创建测试用电设备"""
    device = PowerDevice(
        device_code="PD-TEST-001",
        device_name="测试IT设备",
        device_type="IT",
        rated_power=100.0,
        is_enabled=True,
        phase_type="3P",
    )
    async_db.add(device)
    await async_db.flush()
    return device


@pytest.fixture
async def sample_pricing(async_db):
    """创建测试电价配置"""
    pricing = ElectricityPricing(
        pricing_name="测试电价",
        period_type="peak",
        price=1.2,
        start_time="08:00",
        end_time="12:00",
        is_active=True,
    )
    async_db.add(pricing)
    await async_db.flush()
    return pricing


class TestEnergyDevices:
    """用电设备管理测试"""

    async def test_get_devices_empty(self, client, admin_user):
        """测试空设备列表"""
        _, token = admin_user
        resp = await client.get("/api/v1/energy/devices", headers=auth_headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body

    async def test_get_devices_with_data(self, client, admin_user, sample_power_device):
        """测试有数据的设备列表"""
        _, token = admin_user
        resp = await client.get("/api/v1/energy/devices", headers=auth_headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) >= 1
        assert body["data"][0]["device_code"] == "PD-TEST-001"

    async def test_get_device_detail(self, client, admin_user, sample_power_device):
        """测试获取设备详情"""
        _, token = admin_user
        resp = await client.get(
            f"/api/v1/energy/devices/{sample_power_device.id}",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["device_name"] == "测试IT设备"

    async def test_get_device_not_found(self, client, admin_user):
        """测试设备不存在"""
        _, token = admin_user
        resp = await client.get(
            "/api/v1/energy/devices/99999",
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_create_device(self, client, admin_user):
        """测试创建设备"""
        _, token = admin_user
        resp = await client.post(
            "/api/v1/energy/devices",
            headers=auth_headers(token),
            json={
                "device_code": "PD-NEW-001",
                "device_name": "新建测试设备",
                "device_type": "AC",
                "rated_power": 50.0,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["device_code"] == "PD-NEW-001"

    async def test_create_device_duplicate_code(self, client, admin_user, sample_power_device):
        """测试创建重复编码设备"""
        _, token = admin_user
        resp = await client.post(
            "/api/v1/energy/devices",
            headers=auth_headers(token),
            json={
                "device_code": "PD-TEST-001",
                "device_name": "重复设备",
                "device_type": "IT",
                "rated_power": 50.0,
            },
        )
        assert resp.status_code == 400

    async def test_delete_device(self, client, admin_user, sample_power_device):
        """测试删除设备"""
        _, token = admin_user
        resp = await client.delete(
            f"/api/v1/energy/devices/{sample_power_device.id}",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200

    async def test_get_devices_unauthorized(self, client):
        """测试未认证访问"""
        resp = await client.get("/api/v1/energy/devices")
        assert resp.status_code == 401


class TestEnergyRealtime:
    """实时电力数据测试"""

    async def test_get_realtime_power(self, client, admin_user, sample_power_device):
        """测试获取实时电力数据"""
        _, token = admin_user
        resp = await client.get("/api/v1/energy/realtime", headers=auth_headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body
        assert isinstance(body["data"], list)

    async def test_get_power_summary(self, client, admin_user):
        """测试获取电力汇总"""
        _, token = admin_user
        resp = await client.get(
            "/api/v1/energy/realtime/summary",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        data = body["data"]
        assert "total_power" in data
        assert "current_pue" in data


class TestEnergyPUE:
    """PUE 测试"""

    async def test_get_current_pue(self, client, admin_user):
        """测试获取当前 PUE"""
        _, token = admin_user
        resp = await client.get("/api/v1/energy/pue", headers=auth_headers(token))
        assert resp.status_code == 200
        body = resp.json()
        data = body["data"]
        assert "current_pue" in data
        assert "total_power" in data
        assert "it_power" in data

    async def test_get_pue_trend(self, client, admin_user):
        """测试获取 PUE 趋势"""
        _, token = admin_user
        resp = await client.get(
            "/api/v1/energy/pue/trend?period=day",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        data = body["data"]
        assert "period" in data
        assert "data" in data
        assert "avg_pue" in data


class TestEnergyStatistics:
    """能耗统计测试"""

    async def test_get_daily_statistics(self, client, admin_user):
        """测试获取日能耗统计"""
        _, token = admin_user
        today = date.today()
        start = (today - timedelta(days=7)).isoformat()
        end = today.isoformat()
        resp = await client.get(
            f"/api/v1/energy/statistics/daily?start_date={start}&end_date={end}",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body

    async def test_get_monthly_statistics(self, client, admin_user):
        """测试获取月能耗统计"""
        _, token = admin_user
        year = date.today().year
        resp = await client.get(
            f"/api/v1/energy/statistics/monthly?year={year}",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body

    async def test_get_energy_summary(self, client, admin_user):
        """测试获取能耗汇总"""
        _, token = admin_user
        today = date.today()
        start = (today - timedelta(days=30)).isoformat()
        end = today.isoformat()
        resp = await client.get(
            f"/api/v1/energy/statistics/summary?start_date={start}&end_date={end}",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        data = body["data"]
        assert "total_energy" in data
        assert "total_cost" in data

    async def test_get_energy_trend(self, client, admin_user):
        """测试获取能耗趋势"""
        _, token = admin_user
        today = date.today()
        start = (today - timedelta(days=7)).isoformat()
        end = today.isoformat()
        resp = await client.get(
            f"/api/v1/energy/statistics/trend?start_date={start}&end_date={end}&granularity=daily",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        data = body["data"]
        assert "granularity" in data
        assert "data" in data

    async def test_get_energy_comparison(self, client, admin_user):
        """测试获取能耗对比"""
        _, token = admin_user
        resp = await client.get(
            "/api/v1/energy/statistics/comparison?comparison_type=mom&period=month",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body
