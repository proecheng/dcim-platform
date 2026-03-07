"""
测试冗余配置 API - Story 25.4
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.energy import PowerDevice


@pytest.mark.asyncio
async def test_get_device_redundancy_success(client: AsyncClient, async_db: AsyncSession, admin_user):
    """测试查询设备冗余配置 - 成功"""
    user, token = admin_user
    headers = {"Authorization": f"Bearer {token}"}

    # 创建测试设备
    device = PowerDevice(
        device_code="PDU-TEST-001",
        device_name="Test PDU",
        device_type="PDU",
        redundancy_type="N+1",
        redundancy_group_id="group-test"
    )
    async_db.add(device)
    await async_db.commit()
    await async_db.refresh(device)

    # 查询冗余配置
    response = await client.get(
        f"/api/v1/power/devices/{device.id}/redundancy",
        headers=headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["device_id"] == device.id
    assert data["device_code"] == "PDU-TEST-001"
    assert data["redundancy_type"] == "N+1"
    assert data["redundancy_group_id"] == "group-test"


@pytest.mark.asyncio
async def test_get_device_redundancy_not_found(client: AsyncClient, admin_user):
    """测试查询不存在的设备"""
    user, token = admin_user
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get(
        "/api/v1/power/devices/99999/redundancy",
        headers=headers
    )

    assert response.status_code == 404
    assert "不存在" in response.json()["detail"]


@pytest.mark.asyncio
async def test_update_device_redundancy_success(client: AsyncClient, async_db: AsyncSession, admin_user):
    """测试更新设备冗余配置 - 成功"""
    user, token = admin_user
    headers = {"Authorization": f"Bearer {token}"}

    # 创建测试设备
    device = PowerDevice(
        device_code="PDU-TEST-002",
        device_name="Test PDU 2",
        device_type="PDU",
        redundancy_type=None,
        redundancy_group_id=None
    )
    async_db.add(device)
    await async_db.commit()
    await async_db.refresh(device)

    # 更新冗余配置
    response = await client.put(
        f"/api/v1/power/devices/{device.id}/redundancy",
        headers=headers,
        json={
            "redundancy_type": "2N",
            "redundancy_group_id": "group-2n"
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["redundancy_type"] == "2N"
    assert data["redundancy_group_id"] == "group-2n"

    # 验证数据库已更新
    await async_db.refresh(device)
    assert device.redundancy_type == "2N"
    assert device.redundancy_group_id == "group-2n"


@pytest.mark.asyncio
async def test_update_device_redundancy_invalid_type(client: AsyncClient, async_db: AsyncSession, admin_user):
    """测试更新设备冗余配置 - 无效类型"""
    user, token = admin_user
    headers = {"Authorization": f"Bearer {token}"}

    # 创建测试设备
    device = PowerDevice(
        device_code="PDU-TEST-003",
        device_name="Test PDU 3",
        device_type="PDU"
    )
    async_db.add(device)
    await async_db.commit()
    await async_db.refresh(device)

    # 尝试使用无效的冗余类型
    response = await client.put(
        f"/api/v1/power/devices/{device.id}/redundancy",
        headers=headers,
        json={
            "redundancy_type": "INVALID",
            "redundancy_group_id": "group-test"
        }
    )

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_update_device_redundancy_not_found(client: AsyncClient, admin_user):
    """测试更新不存在的设备"""
    user, token = admin_user
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.put(
        "/api/v1/power/devices/99999/redundancy",
        headers=headers,
        json={
            "redundancy_type": "N+1",
            "redundancy_group_id": "group-test"
        }
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_device_redundancy_requires_admin(client: AsyncClient, async_db: AsyncSession, viewer_user):
    """测试更新冗余配置需要管理员权限"""
    user, token = viewer_user
    headers = {"Authorization": f"Bearer {token}"}

    # 创建测试设备
    device = PowerDevice(
        device_code="PDU-TEST-004",
        device_name="Test PDU 4",
        device_type="PDU"
    )
    async_db.add(device)
    await async_db.commit()
    await async_db.refresh(device)

    # 使用 viewer 权限尝试更新
    response = await client.put(
        f"/api/v1/power/devices/{device.id}/redundancy",
        headers=headers,
        json={
            "redundancy_type": "N+1",
            "redundancy_group_id": "group-test"
        }
    )

    assert response.status_code == 403  # Forbidden
