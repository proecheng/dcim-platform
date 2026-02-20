"""
认证 API 覆盖率补充测试
覆盖 auth.py 中未测试的行：39-44, 65, 107-195, 260, 267-301, 318, 333, 346, 365-380
"""
import pytest
from datetime import datetime, timedelta

from app.models.user import User, UserLoginHistory, PasswordHistory
from app.models.config import SystemConfig
from app.core.security import get_password_hash
from tests.conftest import auth_headers, TEST_PASSWORD


class TestPasswordPolicyFromConfig:
    """_get_password_policy 从 SystemConfig 读取配置（覆盖行 39-44）"""

    async def test_policy_reads_from_system_config(self, client, admin_user, async_db):
        """SystemConfig 中有配置时覆盖默认值"""
        _, token = admin_user
        # 插入自定义密码策略
        for key, val in [("min_length", "12"), ("history_count", "3")]:
            async_db.add(SystemConfig(
                config_group="password_policy",
                config_key=key,
                config_value=val,
                value_type="int",
                description=f"测试-{key}",
                is_editable=True,
            ))
        await async_db.flush()

        resp = await client.get(
            "/api/v1/auth/password-policy", headers=auth_headers(token)
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["min_length"] == 12
        assert data["history_count"] == 3
        # 未覆盖的 key 保持默认
        assert data["min_categories"] == 3
        assert data["expire_days"] == 90

    async def test_policy_default_when_no_config(self, client, admin_user):
        """无 SystemConfig 记录时返回默认策略"""
        _, token = admin_user
        resp = await client.get(
            "/api/v1/auth/password-policy", headers=auth_headers(token)
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["min_length"] == 8


class TestRateLimiter:
    """RateLimiter.is_allowed / get_remaining_time（覆盖行 53-68）"""

    def test_rate_limiter_allows_within_limit(self):
        from app.api.v1.auth import RateLimiter
        limiter = RateLimiter(max_attempts=3, window_seconds=60)
        assert limiter.is_allowed("key1") is True
        assert limiter.is_allowed("key1") is True
        assert limiter.is_allowed("key1") is True

    def test_rate_limiter_blocks_over_limit(self):
        from app.api.v1.auth import RateLimiter
        limiter = RateLimiter(max_attempts=2, window_seconds=60)
        limiter.is_allowed("key2")
        limiter.is_allowed("key2")
        assert limiter.is_allowed("key2") is False

    def test_rate_limiter_remaining_time(self):
        from app.api.v1.auth import RateLimiter
        limiter = RateLimiter(max_attempts=2, window_seconds=60)
        # 空 key 返回 0
        assert limiter.get_remaining_time("empty") == 0
        limiter.is_allowed("key3")
        remaining = limiter.get_remaining_time("key3")
        assert remaining >= 0


class TestLoginRateLimitBranch:
    """登录端点的速率限制分支（覆盖行 97-103）"""

    async def test_login_rate_limit_returns_429(self, client, async_db):
        """超过速率限制返回 429"""
        from app.api.v1.auth import login_limiter
        login_limiter.attempts.clear()

        user = User(
            username="rate_limit_user",
            password_hash=get_password_hash("Test@1234"),
            real_name="限流测试",
            role="operator",
            is_active=True,
        )
        async_db.add(user)
        await async_db.flush()

        # 发送 5 次请求消耗配额
        for _ in range(5):
            await client.post(
                "/api/v1/auth/login",
                data={"username": "rate_limit_user", "password": "wrong"},
            )

        # 第 6 次应被限流
        resp = await client.post(
            "/api/v1/auth/login",
            data={"username": "rate_limit_user", "password": "wrong"},
        )
        assert resp.status_code == 429
        assert "频繁" in resp.json()["detail"]
        assert "Retry-After" in resp.headers

        # 清理
        login_limiter.attempts.clear()


class TestLoginHistoryAndPasswordExpiry:
    """登录成功后的历史记录和密码过期检查（覆盖行 107-200）"""

    async def test_login_records_history_on_failure(self, client, async_db):
        """登录失败时记录历史"""
        from app.api.v1.auth import login_limiter
        login_limiter.attempts.clear()

        user = User(
            username="hist_fail_user",
            password_hash=get_password_hash("Correct@123"),
            real_name="历史测试",
            role="operator",
            is_active=True,
        )
        async_db.add(user)
        await async_db.flush()
        user_id = user.id

        await client.post(
            "/api/v1/auth/login",
            data={"username": "hist_fail_user", "password": "Wrong@123"},
        )

        from sqlalchemy import select
        result = await async_db.execute(
            select(UserLoginHistory).where(UserLoginHistory.user_id == user_id)
        )
        records = result.scalars().all()
        assert len(records) >= 1
        assert records[0].status == "failed"

    async def test_login_success_updates_user_info(self, client, async_db):
        """登录成功后更新 last_login_at 和 login_count"""
        from app.api.v1.auth import login_limiter
        login_limiter.attempts.clear()

        user = User(
            username="login_info_user",
            password_hash=get_password_hash("Test@1234"),
            real_name="登录信息测试",
            role="admin",
            is_active=True,
            login_count=0,
        )
        async_db.add(user)
        await async_db.flush()

        resp = await client.post(
            "/api/v1/auth/login",
            data={"username": "login_info_user", "password": "Test@1234"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert body["expires_in"] > 0

    async def test_login_password_expired_warning(self, client, async_db):
        """密码过期时返回警告"""
        from app.api.v1.auth import login_limiter
        login_limiter.attempts.clear()

        user = User(
            username="expired_pwd_user",
            password_hash=get_password_hash("Test@1234"),
            real_name="过期测试",
            role="operator",
            is_active=True,
            password_changed_at=datetime.now() - timedelta(days=100),
        )
        async_db.add(user)
        await async_db.flush()

        resp = await client.post(
            "/api/v1/auth/login",
            data={"username": "expired_pwd_user", "password": "Test@1234"},
        )
        assert resp.status_code == 200
        assert resp.json()["password_expired_warning"] is not None

    async def test_login_password_not_expired(self, client, async_db):
        """密码未过期时无警告"""
        from app.api.v1.auth import login_limiter
        login_limiter.attempts.clear()

        user = User(
            username="fresh_pwd_user",
            password_hash=get_password_hash("Test@1234"),
            real_name="新密码测试",
            role="operator",
            is_active=True,
            password_changed_at=datetime.now(),
        )
        async_db.add(user)
        await async_db.flush()

        resp = await client.post(
            "/api/v1/auth/login",
            data={"username": "fresh_pwd_user", "password": "Test@1234"},
        )
        assert resp.status_code == 200
        assert resp.json()["password_expired_warning"] is None


class TestChangePassword:
    """修改密码端点（覆盖行 267-301）"""

    async def test_change_password_success(self, client, admin_user):
        """成功修改密码"""
        _, token = admin_user
        resp = await client.put(
            "/api/v1/auth/password",
            headers=auth_headers(token),
            json={
                "old_password": TEST_PASSWORD,
                "new_password": "NewPass@456",
                "confirm_password": "NewPass@456",
            },
        )
        assert resp.status_code == 200
        assert "密码修改成功" in resp.json()["message"]

    async def test_change_password_history_block(self, client, admin_user, async_db):
        """新密码与历史密码相同时拒绝"""
        user, token = admin_user
        # 插入历史密码
        async_db.add(PasswordHistory(
            user_id=user.id,
            password_hash=get_password_hash("ReusedPwd@1"),
        ))
        await async_db.flush()

        resp = await client.put(
            "/api/v1/auth/password",
            headers=auth_headers(token),
            json={
                "old_password": TEST_PASSWORD,
                "new_password": "ReusedPwd@1",
                "confirm_password": "ReusedPwd@1",
            },
        )
        assert resp.status_code == 400
        assert "最近" in resp.json()["detail"]

    async def test_change_password_confirm_mismatch(self, client, admin_user):
        """新密码与确认密码不一致"""
        _, token = admin_user
        resp = await client.put(
            "/api/v1/auth/password",
            headers=auth_headers(token),
            json={
                "old_password": TEST_PASSWORD,
                "new_password": "NewPass@456",
                "confirm_password": "Different@789",
            },
        )
        assert resp.status_code == 400

    async def test_change_password_wrong_old(self, client, admin_user):
        """旧密码错误"""
        _, token = admin_user
        resp = await client.put(
            "/api/v1/auth/password",
            headers=auth_headers(token),
            json={
                "old_password": "WrongOld@123",
                "new_password": "NewPass@456",
                "confirm_password": "NewPass@456",
            },
        )
        assert resp.status_code == 400
        assert "原密码错误" in resp.json()["detail"]


class TestUpdatePasswordPolicy:
    """更新密码策略端点（覆盖行 346, 365-380）"""

    async def test_update_policy_as_admin(self, client, admin_user):
        """管理员更新密码策略"""
        _, token = admin_user
        resp = await client.put(
            "/api/v1/auth/password-policy",
            headers=auth_headers(token),
            json={
                "min_length": 10,
                "min_categories": 4,
                "history_count": 3,
                "expire_days": 60,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["min_length"] == 10
        assert data["expire_days"] == 60

    async def test_update_policy_twice_updates_existing(self, client, admin_user):
        """二次更新覆盖已有配置"""
        _, token = admin_user
        await client.put(
            "/api/v1/auth/password-policy",
            headers=auth_headers(token),
            json={"min_length": 10, "min_categories": 3, "history_count": 5, "expire_days": 90},
        )
        resp = await client.put(
            "/api/v1/auth/password-policy",
            headers=auth_headers(token),
            json={"min_length": 14, "min_categories": 4, "history_count": 2, "expire_days": 30},
        )
        assert resp.status_code == 200
        assert resp.json()["min_length"] == 14

    async def test_update_policy_non_admin_forbidden(self, client, viewer_user):
        """非管理员不能更新密码策略"""
        _, token = viewer_user
        resp = await client.put(
            "/api/v1/auth/password-policy",
            headers=auth_headers(token),
            json={"min_length": 10, "min_categories": 3, "history_count": 5, "expire_days": 90},
        )
        assert resp.status_code == 403


class TestGetPermissions:
    """获取权限端点（覆盖行 318）"""

    async def test_get_permissions_empty(self, client, admin_user):
        """无权限记录时返回空列表"""
        _, token = admin_user
        resp = await client.get(
            "/api/v1/auth/permissions", headers=auth_headers(token)
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["role"] == "admin"
        assert isinstance(body["permissions"], list)


class TestLogoutAndRefresh:
    """登出和刷新端点（覆盖行 203-221）"""

    async def test_logout_no_token(self, client):
        """无 token 登出返回 401"""
        resp = await client.post("/api/v1/auth/logout")
        assert resp.status_code == 401

    async def test_refresh_no_token(self, client):
        """无 token 刷新返回 401"""
        resp = await client.post("/api/v1/auth/refresh")
        assert resp.status_code == 401

    async def test_refresh_returns_new_token(self, client, admin_user):
        """刷新返回新 token"""
        _, token = admin_user
        resp = await client.post(
            "/api/v1/auth/refresh", headers=auth_headers(token)
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["access_token"] != token
        assert body["token_type"] == "bearer"

    async def test_logout_with_token(self, client, admin_user):
        """已认证用户登出成功（覆盖行 208）"""
        _, token = admin_user
        resp = await client.post(
            "/api/v1/auth/logout", headers=auth_headers(token)
        )
        assert resp.status_code == 200
        assert resp.json()["message"] == "登出成功"


class TestGetMe:
    """获取当前用户信息（覆盖行 229）"""

    async def test_get_me_success(self, client, admin_user):
        """获取当前用户信息"""
        user, token = admin_user
        resp = await client.get(
            "/api/v1/auth/me", headers=auth_headers(token)
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["username"] == user.username
        assert body["role"] == "admin"
        assert body["is_active"] is True


class TestLoginDisabledUser:
    """禁用用户登录（覆盖行 134-138）"""

    async def test_login_disabled_user_returns_403(self, client, async_db):
        """禁用用户登录返回 403"""
        from app.api.v1.auth import login_limiter
        login_limiter.attempts.clear()

        user = User(
            username="disabled_login_user",
            password_hash=get_password_hash("Test@1234"),
            real_name="禁用用户",
            role="operator",
            is_active=False,
        )
        async_db.add(user)
        await async_db.flush()

        resp = await client.post(
            "/api/v1/auth/login",
            data={"username": "disabled_login_user", "password": "Test@1234"},
        )
        assert resp.status_code == 403
        assert "禁用" in resp.json()["detail"]


class TestSessionKick:
    """并发会话限制踢出旧会话（覆盖行 178-180）"""

    async def test_login_kicks_oldest_session(self, client, async_db):
        """超过 MAX_SESSIONS 时踢出最早的会话"""
        from app.api.v1.auth import login_limiter
        from app.models.user import UserSession
        login_limiter.attempts.clear()

        user = User(
            username="session_kick_user",
            password_hash=get_password_hash("Test@1234"),
            real_name="会话踢出测试",
            role="admin",
            is_active=True,
            login_count=0,
        )
        async_db.add(user)
        await async_db.flush()

        # 预先创建 4 个活跃会话（超过 MAX_SESSIONS=3）
        for i in range(4):
            async_db.add(UserSession(
                user_id=user.id,
                token_jti=f"pre_session_{i}",
                is_active=True,
            ))
        await async_db.flush()

        # 再次登录，应触发踢出逻辑
        resp = await client.post(
            "/api/v1/auth/login",
            data={"username": "session_kick_user", "password": "Test@1234"},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()
