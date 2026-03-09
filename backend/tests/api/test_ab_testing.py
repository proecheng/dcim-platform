"""
A/B 测试 API 单元测试 - Story 26.5
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ab_test_config import ABTestConfig
from app.models.fault_tree import FaultTree, FaultTreeVersion
from app.models.user import User


@pytest.mark.asyncio
async def test_create_ab_test_api(client: AsyncClient, admin_token: str, async_db: AsyncSession):
    """测试创建 A/B 测试 API"""
    # 创建故障树和版本
    fault_tree = FaultTree(name="API测试故障树", status="active")
    async_db.add(fault_tree)
    await async_db.flush()

    version_a = FaultTreeVersion(
        tree_id=fault_tree.id,
        version_number=2,
        status="reviewed",
        snapshot="{}",
        created_by=1,
    )
    version_b = FaultTreeVersion(
        tree_id=fault_tree.id,
        version_number=1,
        status="active",
        snapshot="{}",
        created_by=1,
    )
    async_db.add_all([version_a, version_b])
    await async_db.commit()

    # 调用 API
    response = await client.post(
        "/api/v1/diagnosis/ab-tests",
        json={
            "name": "API测试",
            "fault_tree_id": fault_tree.id,
            "version_a_id": version_a.id,
            "version_b_id": version_b.id,
            "strategy": "percentage",
            "strategy_params": {"percentage": 10},
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "API测试"
    assert data["status"] == "active"


@pytest.mark.asyncio
async def test_create_ab_test_unauthorized(client: AsyncClient, async_db: AsyncSession):
    """测试未授权创建 A/B 测试"""
    response = await client.post(
        "/api/v1/diagnosis/ab-tests",
        json={
            "name": "未授权测试",
            "fault_tree_id": 1,
            "version_a_id": 1,
            "version_b_id": 2,
            "strategy": "percentage",
            "strategy_params": {"percentage": 10},
        },
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_ab_tests_api(client: AsyncClient, admin_token: str, async_db: AsyncSession):
    """测试列出 A/B 测试 API"""
    # 创建测试数据
    fault_tree = FaultTree(name="列表测试故障树", status="active")
    async_db.add(fault_tree)
    await async_db.flush()

    version_a = FaultTreeVersion(
        tree_id=fault_tree.id,
        version_number=2,
        status="reviewed",
        snapshot="{}",
        created_by=1,
    )
    version_b = FaultTreeVersion(
        tree_id=fault_tree.id,
        version_number=1,
        status="active",
        snapshot="{}",
        created_by=1,
    )
    async_db.add_all([version_a, version_b])
    await async_db.flush()

    ab_test = ABTestConfig(
        name="列表测试",
        fault_tree_id=fault_tree.id,
        version_a_id=version_a.id,
        version_b_id=version_b.id,
        strategy="percentage",
        strategy_params={"percentage": 10},
        created_by=1,
    )
    async_db.add(ab_test)
    await async_db.commit()

    # 调用 API
    response = await client.get(
        "/api/v1/diagnosis/ab-tests",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0


@pytest.mark.asyncio
async def test_get_ab_test_api(client: AsyncClient, admin_token: str, async_db: AsyncSession):
    """测试查询单个 A/B 测试 API"""
    # 创建测试数据
    fault_tree = FaultTree(name="查询测试故障树", status="active")
    async_db.add(fault_tree)
    await async_db.flush()

    version_a = FaultTreeVersion(
        tree_id=fault_tree.id,
        version_number=2,
        status="reviewed",
        snapshot="{}",
        created_by=1,
    )
    version_b = FaultTreeVersion(
        tree_id=fault_tree.id,
        version_number=1,
        status="active",
        snapshot="{}",
        created_by=1,
    )
    async_db.add_all([version_a, version_b])
    await async_db.flush()

    ab_test = ABTestConfig(
        name="查询测试",
        fault_tree_id=fault_tree.id,
        version_a_id=version_a.id,
        version_b_id=version_b.id,
        strategy="percentage",
        strategy_params={"percentage": 10},
        created_by=1,
    )
    async_db.add(ab_test)
    await async_db.commit()

    # 调用 API
    response = await client.get(
        f"/api/v1/diagnosis/ab-tests/{ab_test.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == ab_test.id
    assert data["name"] == "查询测试"


@pytest.mark.asyncio
async def test_update_ab_test_api(client: AsyncClient, admin_token: str, async_db: AsyncSession):
    """测试更新 A/B 测试 API"""
    # 创建测试数据
    fault_tree = FaultTree(name="更新测试故障树", status="active")
    async_db.add(fault_tree)
    await async_db.flush()

    version_a = FaultTreeVersion(
        tree_id=fault_tree.id,
        version_number=2,
        status="reviewed",
        snapshot="{}",
        created_by=1,
    )
    version_b = FaultTreeVersion(
        tree_id=fault_tree.id,
        version_number=1,
        status="active",
        snapshot="{}",
        created_by=1,
    )
    async_db.add_all([version_a, version_b])
    await async_db.flush()

    ab_test = ABTestConfig(
        name="更新测试",
        fault_tree_id=fault_tree.id,
        version_a_id=version_a.id,
        version_b_id=version_b.id,
        strategy="percentage",
        strategy_params={"percentage": 10},
        created_by=1,
    )
    async_db.add(ab_test)
    await async_db.commit()

    # 调用 API
    response = await client.patch(
        f"/api/v1/diagnosis/ab-tests/{ab_test.id}",
        json={
            "strategy_params": {"percentage": 20},
            "version": 1,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["strategy_params"]["percentage"] == 20
    assert data["version"] == 2


@pytest.mark.asyncio
async def test_update_ab_test_version_conflict_api(
    client: AsyncClient, admin_token: str, async_db: AsyncSession
):
    """测试更新 A/B 测试版本冲突 API"""
    # 创建测试数据
    fault_tree = FaultTree(name="冲突测试故障树", status="active")
    async_db.add(fault_tree)
    await async_db.flush()

    version_a = FaultTreeVersion(
        tree_id=fault_tree.id,
        version_number=2,
        status="reviewed",
        snapshot="{}",
        created_by=1,
    )
    version_b = FaultTreeVersion(
        tree_id=fault_tree.id,
        version_number=1,
        status="active",
        snapshot="{}",
        created_by=1,
    )
    async_db.add_all([version_a, version_b])
    await async_db.flush()

    ab_test = ABTestConfig(
        name="冲突测试",
        fault_tree_id=fault_tree.id,
        version_a_id=version_a.id,
        version_b_id=version_b.id,
        strategy="percentage",
        strategy_params={"percentage": 10},
        created_by=1,
    )
    async_db.add(ab_test)
    await async_db.commit()

    # 调用 API（使用错误的版本号）
    response = await client.patch(
        f"/api/v1/diagnosis/ab-tests/{ab_test.id}",
        json={
            "strategy_params": {"percentage": 20},
            "version": 999,  # 错误的版本号
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 409  # Conflict


@pytest.mark.asyncio
async def test_delete_ab_test_api(client: AsyncClient, admin_token: str, async_db: AsyncSession):
    """测试删除 A/B 测试 API"""
    # 创建测试数据
    fault_tree = FaultTree(name="删除测试故障树", status="active")
    async_db.add(fault_tree)
    await async_db.flush()

    version_a = FaultTreeVersion(
        tree_id=fault_tree.id,
        version_number=2,
        status="reviewed",
        snapshot="{}",
        created_by=1,
    )
    version_b = FaultTreeVersion(
        tree_id=fault_tree.id,
        version_number=1,
        status="active",
        snapshot="{}",
        created_by=1,
    )
    async_db.add_all([version_a, version_b])
    await async_db.flush()

    ab_test = ABTestConfig(
        name="删除测试",
        fault_tree_id=fault_tree.id,
        version_a_id=version_a.id,
        version_b_id=version_b.id,
        strategy="percentage",
        strategy_params={"percentage": 10},
        status="paused",  # 只能删除 paused 状态
        created_by=1,
    )
    async_db.add(ab_test)
    await async_db.commit()

    # 调用 API
    response = await client.delete(
        f"/api/v1/diagnosis/ab-tests/{ab_test.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 204
