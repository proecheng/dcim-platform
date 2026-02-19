"""
认证 API 核心测试
"""
import pytest
from unittest.mock import patch, AsyncMock
from app.models.user import User, UserSession, RolePermission
from app.core.security import get_password_hash
from tests.conftest import auth_headers


class TestAuthLogin:
    """登录端点测试"""

    async def test_login_success(self, client, async_db):
        """测试正常登录"""
        user = User(
            username="login_user",
            password_hash=get_password_hash("test123"),
            real_name="登录测试",
            role="admin",
            is_active=True,
        )
        async_db.add(user)
        await async_db.flush()

        resp = await client.post(
            "/api/v1/auth/login",
            data={"username": "login_user", "password": "test123"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"
        assert body["expires_in"] > 0

    async def test_login_wrong_password(self, client, async_db):
        """测试密码错误"""
        user = User(
            username="wrong_pwd_user",
            password_hash=get_password_hash("correct"),
            real_name="密码错误测试",
            role="operator",
            is_active=True,
        )
        async_db.add(user)
        await async_db.flush()

        resp = await client.post(
            "/api/v1/auth/login",
            data={"username": "wrong_pwd_user", "password": "wrong"},
        )
        assert resp.status_code == 401
        assert "用户名或密码错误" in resp.json()["detail"]

    async def test_login_nonexistent_user(self, client):
        """测试不存在的用户"""
        resp = await client.post(
            "/api/v1/auth/login",
            data={"username": "ghost_user", "password": "any"},
        )
        assert resp.status_code == 401

    async def test_login_disabled_user(self, client, async_db):
        """测试被禁用的用户"""
        user = User(
            username="disabled_user",
            password_hash=get_password_hash("test123"),
            real_name="禁用用户",
            role="operator",
            is_active=False,
        )
        async_db.add(user)
        await async_db.flush()

        resp = await client.post(
            "/api/v1/auth/login",
            data={"username": "disabled_user", "password": "test123"},
        )
        assert resp.status_code == 403
        assert "禁用" in resp.json()["detail"]


class TestAuthMe:
    """获取当前用户信息测试"""

    async def test_get_me_success(self, client, admin_user):
        """测试获取当前用户信息"""
        user, token = admin_user
        resp = await client.get("/api/v1/auth/me", headers=auth_headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert body["username"] == "test_admin"
        assert body["role"] == "admin"

    async def test_get_me_no_token(self, client):
        """测试无 token 访问"""
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 401


class TestAuthRefresh:
    """刷新令牌测试"""

    async def test_refresh_token(self, client, admin_user):
        """测试刷新令牌"""
        _, token = admin_user
        resp = await client.post(
            "/api/v1/auth/refresh", headers=auth_headers(token)
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"


class TestAuthLogout:
    """登出测试"""

    async def test_logout(self, client, admin_user):
        """测试登出"""
        _, token = admin_user
        resp = await client.post(
            "/api/v1/auth/logout", headers=auth_headers(token)
        )
        assert resp.status_code == 200
        assert "登出成功" in resp.json()["message"]


class TestAuthPermissions:
    """权限测试"""

    async def test_get_permissions(self, client, admin_user, async_db):
        """测试获取权限列表"""
        user, token = admin_user
        # 添加权限记录
        perm = RolePermission(role="admin", permission="alarm:read")
        async_db.add(perm)
        await async_db.flush()

        resp = await client.get(
            "/api/v1/auth/permissions", headers=auth_headers(token)
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["role"] == "admin"
        assert isinstance(body["permissions"], list)


class TestAuthPasswordChange:
    """修改密码测试"""

    async def test_change_password_wrong_old(self, client, admin_user):
        """测试旧密码错误"""
        _, token = admin_user
        resp = await client.put(
            "/api/v1/auth/password",
            headers=auth_headers(token),
            json={
                "old_password": "wrong_old",
                "new_password": "NewPass@123",
                "confirm_password": "NewPass@123",
            },
        )
        assert resp.status_code == 400
        assert "原密码错误" in resp.json()["detail"]

    async def test_change_password_mismatch(self, client, admin_user):
        """测试新密码不一致"""
        _, token = admin_user
        resp = await client.put(
            "/api/v1/auth/password",
            headers=auth_headers(token),
            json={
                "old_password": "admin123",
                "new_password": "NewPass@123",
                "confirm_password": "Different@456",
            },
        )
        assert resp.status_code == 400
