"""
故障树版本管理 API 集成测试
"""
import pytest
import json
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fault_tree import FaultTree, FaultTreeVersion


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


VERSION_MANAGER_PATH = "app.api.v1.fault_tree_versions.VersionManager"


async def _create_tree(async_db, created_by=1):
    tree = FaultTree(name="测试故障树", description="测试用", status="active", created_by=created_by)
    async_db.add(tree)
    await async_db.commit()
    await async_db.refresh(tree)
    return tree


async def _create_version(async_db, tree_id, version_number=1, status="draft", created_by=1):
    v = FaultTreeVersion(
        tree_id=tree_id,
        version_number=version_number,
        status=status,
        snapshot=json.dumps({"nodes": [], "edges": []}),
        hmac_signature="test-sig",
        created_by=created_by,
    )
    async_db.add(v)
    await async_db.commit()
    await async_db.refresh(v)
    return v


# ==================== 列表查询 ====================


@pytest.mark.asyncio
async def test_list_versions(client: AsyncClient, admin_token: str, async_db: AsyncSession):
    """测试版本列表查询"""
    tree = await _create_tree(async_db)
    v1 = await _create_version(async_db, tree.id, version_number=1, status="active")
    v2 = await _create_version(async_db, tree.id, version_number=2, status="draft")

    resp = await client.get(
        f"/api/v1/fault-trees/{tree.id}/versions/",
        headers=auth_headers(admin_token),
    )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    # 按版本号降序排列
    assert data[0]["version_number"] == 2
    assert data[1]["version_number"] == 1


@pytest.mark.asyncio
async def test_list_versions_filter_status(client: AsyncClient, admin_token: str, async_db: AsyncSession):
    """测试按状态过滤版本列表"""
    tree = await _create_tree(async_db)
    await _create_version(async_db, tree.id, version_number=1, status="active")
    await _create_version(async_db, tree.id, version_number=2, status="draft")
    await _create_version(async_db, tree.id, version_number=3, status="draft")

    resp = await client.get(
        f"/api/v1/fault-trees/{tree.id}/versions/",
        params={"status": "draft"},
        headers=auth_headers(admin_token),
    )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert all(v["status"] == "draft" for v in data)


# ==================== 审批 ====================


@pytest.mark.asyncio
async def test_review_version_success(client: AsyncClient, admin_token: str, admin_user, async_db: AsyncSession):
    """测试成功审批版本（审批者与创建者不同）"""
    user, _ = admin_user
    tree = await _create_tree(async_db, created_by=user.id)
    # 创建版本时 created_by 使用不同于 admin_user 的 ID
    version = await _create_version(async_db, tree.id, version_number=1, status="draft", created_by=999)

    resp = await client.post(
        f"/api/v1/fault-trees/{tree.id}/versions/{version.id}/review",
        headers=auth_headers(admin_token),
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "reviewed"
    assert data["reviewed_by"] == user.id


@pytest.mark.asyncio
async def test_review_version_same_creator(client: AsyncClient, admin_token: str, admin_user, async_db: AsyncSession):
    """测试审批自己创建的版本 - 应失败"""
    user, _ = admin_user
    tree = await _create_tree(async_db, created_by=user.id)
    # created_by 设为当前用户 ID，审批时应被拒绝
    version = await _create_version(async_db, tree.id, version_number=1, status="draft", created_by=user.id)

    resp = await client.post(
        f"/api/v1/fault-trees/{tree.id}/versions/{version.id}/review",
        headers=auth_headers(admin_token),
    )

    assert resp.status_code == 400
    assert "不能审批自己创建的版本" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_review_version_not_draft(client: AsyncClient, admin_token: str, async_db: AsyncSession):
    """测试审批非 draft 状态的版本 - 应失败"""
    tree = await _create_tree(async_db)
    version = await _create_version(async_db, tree.id, version_number=1, status="reviewed", created_by=999)

    resp = await client.post(
        f"/api/v1/fault-trees/{tree.id}/versions/{version.id}/review",
        headers=auth_headers(admin_token),
    )

    assert resp.status_code == 400
    assert "draft" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_review_version_not_found(client: AsyncClient, admin_token: str, async_db: AsyncSession):
    """测试审批不存在的版本 - 应返回 404"""
    tree = await _create_tree(async_db)

    resp = await client.post(
        f"/api/v1/fault-trees/{tree.id}/versions/99999/review",
        headers=auth_headers(admin_token),
    )

    assert resp.status_code == 404


# ==================== 创建版本（mock） ====================


@pytest.mark.asyncio
async def test_create_version_with_mock(client: AsyncClient, admin_token: str, admin_user, async_db: AsyncSession):
    """测试创建版本 - mock VersionManager"""
    user, _ = admin_user
    tree = await _create_tree(async_db, created_by=user.id)

    mock_version = MagicMock()
    mock_version.id = 1
    mock_version.tree_id = tree.id
    mock_version.version_number = 1
    mock_version.status = "draft"
    mock_version.snapshot = json.dumps({"nodes": [], "edges": []})
    mock_version.hmac_signature = "mock-sig"
    mock_version.created_by = user.id
    mock_version.created_at = datetime.now()
    mock_version.reviewed_by = None
    mock_version.reviewed_at = None
    mock_version.activated_at = None

    with patch(f"{VERSION_MANAGER_PATH}.create_version", new_callable=AsyncMock, return_value=mock_version):
        resp = await client.post(
            f"/api/v1/fault-trees/{tree.id}/versions/",
            headers=auth_headers(admin_token),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["version_number"] == 1
    assert data["status"] == "draft"


# ==================== 激活版本（mock） ====================


@pytest.mark.asyncio
async def test_activate_version_with_mock(client: AsyncClient, admin_token: str, async_db: AsyncSession):
    """测试激活版本 - mock VersionManager"""
    tree = await _create_tree(async_db)
    version = await _create_version(async_db, tree.id, version_number=1, status="reviewed", created_by=999)

    mock_version = MagicMock()
    mock_version.id = version.id
    mock_version.tree_id = tree.id
    mock_version.version_number = 1
    mock_version.status = "active"
    mock_version.snapshot = json.dumps({"nodes": [], "edges": []})
    mock_version.hmac_signature = "mock-sig"
    mock_version.created_by = 999
    mock_version.created_at = datetime.now()
    mock_version.reviewed_by = None
    mock_version.reviewed_at = None
    mock_version.activated_at = datetime.now()

    with patch(f"{VERSION_MANAGER_PATH}.activate_version", new_callable=AsyncMock, return_value=mock_version):
        resp = await client.post(
            f"/api/v1/fault-trees/{tree.id}/versions/{version.id}/activate",
            headers=auth_headers(admin_token),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "active"
    assert data["activated_at"] is not None


# ==================== 回滚（mock） ====================


@pytest.mark.asyncio
async def test_rollback_with_mock(client: AsyncClient, admin_token: str, async_db: AsyncSession):
    """测试回滚版本 - mock VersionManager"""
    tree = await _create_tree(async_db)

    mock_version = MagicMock()
    mock_version.id = 10
    mock_version.tree_id = tree.id
    mock_version.version_number = 2
    mock_version.status = "active"
    mock_version.snapshot = json.dumps({"nodes": [], "edges": []})
    mock_version.hmac_signature = "mock-sig"
    mock_version.created_by = 1
    mock_version.created_at = datetime.now()
    mock_version.reviewed_by = None
    mock_version.reviewed_at = None
    mock_version.activated_at = datetime.now()

    with patch(f"{VERSION_MANAGER_PATH}.rollback_version", new_callable=AsyncMock, return_value=mock_version):
        resp = await client.post(
            f"/api/v1/fault-trees/{tree.id}/versions/rollback",
            headers=auth_headers(admin_token),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "active"
    assert data["version_number"] == 2


@pytest.mark.asyncio
async def test_rollback_no_versions(client: AsyncClient, admin_token: str, async_db: AsyncSession):
    """测试回滚无可用版本 - 应返回 404"""
    tree = await _create_tree(async_db)

    with patch(
        f"{VERSION_MANAGER_PATH}.rollback_version",
        new_callable=AsyncMock,
        side_effect=ValueError("没有可回滚的版本"),
    ):
        resp = await client.post(
            f"/api/v1/fault-trees/{tree.id}/versions/rollback",
            headers=auth_headers(admin_token),
        )

    assert resp.status_code == 404
    assert "没有可回滚的版本" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_review_version_wrong_tree_id(client: AsyncClient, admin_token: str, async_db: AsyncSession):
    """测试审批版本时 tree_id 不匹配 - 应返回 404"""
    tree = await _create_tree(async_db)
    version = await _create_version(async_db, tree.id, version_number=1, status="draft", created_by=999)

    # 使用不存在的 tree_id
    resp = await client.post(
        f"/api/v1/fault-trees/99999/versions/{version.id}/review",
        headers=auth_headers(admin_token),
    )

    assert resp.status_code == 404
