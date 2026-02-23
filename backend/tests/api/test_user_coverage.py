"""
用户管理 API 覆盖率补充测试
覆盖 user.py 中未测试的行：40-58, 78-88, 102-141, 155-299, 320-367
"""

from app.models.user import User, UserLoginHistory, UserSite
from app.models.spatial import Site
from app.core.security import get_password_hash
from tests.conftest import auth_headers

USERS_URL = "/api/v1/users"


class TestGetUsers:
    """用户列表端点（覆盖行 40-58 筛选分支）"""

    async def test_list_users_basic(self, client, admin_user, async_db):
        """基本分页查询"""
        _, token = admin_user
        resp = await client.get(USERS_URL, headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert data["page"] == 1

    async def test_list_users_keyword_filter(self, client, admin_user, async_db):
        """关键词搜索（username/real_name/email）"""
        _, token = admin_user
        # 创建可搜索的用户
        async_db.add(
            User(
                username="searchable_user",
                password_hash=get_password_hash("Test@1234"),
                real_name="可搜索用户",
                email="searchable@test.com",
                role="operator",
                is_active=True,
            )
        )
        await async_db.flush()

        resp = await client.get(
            USERS_URL,
            headers=auth_headers(token),
            params={"keyword": "searchable"},
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert any("searchable" in u["username"] for u in items)

    async def test_list_users_role_filter(self, client, admin_user, async_db):
        """角色筛选"""
        _, token = admin_user
        async_db.add(
            User(
                username="viewer_filter_user",
                password_hash=get_password_hash("Test@1234"),
                role="viewer",
                is_active=True,
            )
        )
        await async_db.flush()

        resp = await client.get(
            USERS_URL,
            headers=auth_headers(token),
            params={"role": "viewer"},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["role"] == "viewer"

    async def test_list_users_is_active_filter(self, client, admin_user, async_db):
        """启用状态筛选"""
        _, token = admin_user
        async_db.add(
            User(
                username="inactive_filter_user",
                password_hash=get_password_hash("Test@1234"),
                role="operator",
                is_active=False,
            )
        )
        await async_db.flush()

        resp = await client.get(
            USERS_URL,
            headers=auth_headers(token),
            params={"is_active": False},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["is_active"] is False

    async def test_list_users_pagination(self, client, admin_user, async_db):
        """分页参数"""
        _, token = admin_user
        resp = await client.get(
            USERS_URL,
            headers=auth_headers(token),
            params={"page": 1, "page_size": 2},
        )
        assert resp.status_code == 200
        assert resp.json()["page_size"] == 2

    async def test_list_users_non_admin_forbidden(self, client, viewer_user):
        """非管理员不能查看用户列表"""
        _, token = viewer_user
        resp = await client.get(USERS_URL, headers=auth_headers(token))
        assert resp.status_code == 403


class TestGetSiteUsers:
    """站点用户列表端点（覆盖行 77-89）"""

    async def test_get_site_users_success(self, client, admin_user, async_db):
        """获取站点下的用户列表"""
        _, token = admin_user
        site = Site(site_code="SITE_USR01", site_name="站点用户测试")
        async_db.add(site)
        user = User(
            username="site_member_user",
            password_hash=get_password_hash("Test@1234"),
            role="operator",
            is_active=True,
        )
        async_db.add(user)
        await async_db.flush()

        async_db.add(UserSite(user_id=user.id, site_id=site.id))
        await async_db.flush()

        resp = await client.get(
            f"{USERS_URL}/sites/{site.id}/users",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert any(u["username"] == "site_member_user" for u in data)

    async def test_get_site_users_empty(self, client, admin_user, async_db):
        """站点无关联用户"""
        _, token = admin_user
        site = Site(site_code="SITE_USR02", site_name="空站点")
        async_db.add(site)
        await async_db.flush()

        resp = await client.get(
            f"{USERS_URL}/sites/{site.id}/users",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_get_site_users_not_found(self, client, admin_user):
        """站点不存在"""
        _, token = admin_user
        resp = await client.get(
            f"{USERS_URL}/sites/99999/users",
            headers=auth_headers(token),
        )
        assert resp.status_code == 404


class TestGetUser:
    """用户详情端点（覆盖行 102-105）"""

    async def test_get_user_success(self, client, admin_user, async_db):
        """获取用户详情"""
        admin, token = admin_user
        user = User(
            username="detail_user",
            password_hash=get_password_hash("Test@1234"),
            real_name="详情用户",
            role="operator",
            is_active=True,
        )
        async_db.add(user)
        await async_db.flush()

        resp = await client.get(f"{USERS_URL}/{user.id}", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["username"] == "detail_user"

    async def test_get_user_not_found(self, client, admin_user):
        """用户不存在"""
        _, token = admin_user
        resp = await client.get(f"{USERS_URL}/99999", headers=auth_headers(token))
        assert resp.status_code == 404


class TestCreateUser:
    """创建用户端点（覆盖行 108-141）"""

    async def test_create_user_success(self, client, admin_user):
        """成功创建用户"""
        _, token = admin_user
        resp = await client.post(
            USERS_URL,
            headers=auth_headers(token),
            json={
                "username": "new_created_user",
                "password": "Test@1234",
                "real_name": "新用户",
                "email": "newuser@test.com",
                "phone": "13800138000",
                "role": "operator",
                "department": "运维部",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "new_created_user"
        assert data["is_active"] is True

    async def test_create_user_duplicate_username(self, client, admin_user, async_db):
        """用户名重复"""
        _, token = admin_user
        async_db.add(
            User(
                username="dup_create_user",
                password_hash=get_password_hash("Test@1234"),
                role="operator",
                is_active=True,
            )
        )
        await async_db.flush()

        resp = await client.post(
            USERS_URL,
            headers=auth_headers(token),
            json={"username": "dup_create_user", "password": "Test@1234", "role": "operator"},
        )
        assert resp.status_code == 400
        assert "用户名已存在" in resp.json()["detail"]

    async def test_create_user_duplicate_email(self, client, admin_user, async_db):
        """邮箱重复"""
        _, token = admin_user
        async_db.add(
            User(
                username="email_dup_user1",
                password_hash=get_password_hash("Test@1234"),
                email="dup@test.com",
                role="operator",
                is_active=True,
            )
        )
        await async_db.flush()

        resp = await client.post(
            USERS_URL,
            headers=auth_headers(token),
            json={
                "username": "email_dup_user2",
                "password": "Test@1234",
                "email": "dup@test.com",
                "role": "operator",
            },
        )
        assert resp.status_code == 400
        assert "邮箱已被使用" in resp.json()["detail"]


class TestUpdateUser:
    """更新用户端点（覆盖行 155-170）"""

    async def test_update_user_success(self, client, admin_user, async_db):
        """成功更新用户"""
        _, token = admin_user
        user = User(
            username="update_target",
            password_hash=get_password_hash("Test@1234"),
            role="operator",
            is_active=True,
        )
        async_db.add(user)
        await async_db.flush()

        resp = await client.put(
            f"{USERS_URL}/{user.id}",
            headers=auth_headers(token),
            json={"real_name": "更新后姓名", "department": "技术部"},
        )
        assert resp.status_code == 200
        assert resp.json()["real_name"] == "更新后姓名"

    async def test_update_user_not_found(self, client, admin_user):
        """更新不存在的用户"""
        _, token = admin_user
        resp = await client.put(
            f"{USERS_URL}/99999",
            headers=auth_headers(token),
            json={"real_name": "不存在"},
        )
        assert resp.status_code == 404


class TestDeleteUser:
    """删除用户端点（覆盖行 173-193）"""

    async def test_delete_user_success(self, client, admin_user, async_db):
        """成功删除用户"""
        _, token = admin_user
        user = User(
            username="delete_target",
            password_hash=get_password_hash("Test@1234"),
            role="viewer",
            is_active=True,
        )
        async_db.add(user)
        await async_db.flush()

        resp = await client.delete(f"{USERS_URL}/{user.id}", headers=auth_headers(token))
        assert resp.status_code == 200
        assert "已删除" in resp.json()["message"]

    async def test_delete_self_forbidden(self, client, admin_user):
        """不能删除自己"""
        user, token = admin_user
        resp = await client.delete(f"{USERS_URL}/{user.id}", headers=auth_headers(token))
        assert resp.status_code == 400
        assert "不能删除自己" in resp.json()["detail"]

    async def test_delete_user_not_found(self, client, admin_user):
        """删除不存在的用户"""
        _, token = admin_user
        resp = await client.delete(f"{USERS_URL}/99999", headers=auth_headers(token))
        assert resp.status_code == 404


class TestToggleUserStatus:
    """启用/禁用用户端点（覆盖行 221-247）"""

    async def test_toggle_disable_user(self, client, admin_user, async_db):
        """禁用用户"""
        _, token = admin_user
        user = User(
            username="toggle_target",
            password_hash=get_password_hash("Test@1234"),
            role="operator",
            is_active=True,
        )
        async_db.add(user)
        await async_db.flush()

        resp = await client.put(
            f"{USERS_URL}/{user.id}/status",
            headers=auth_headers(token),
            params={"is_active": False},
        )
        assert resp.status_code == 200
        assert "禁用" in resp.json()["message"]

    async def test_toggle_enable_user(self, client, admin_user, async_db):
        """启用用户"""
        _, token = admin_user
        user = User(
            username="toggle_enable_target",
            password_hash=get_password_hash("Test@1234"),
            role="operator",
            is_active=False,
        )
        async_db.add(user)
        await async_db.flush()

        resp = await client.put(
            f"{USERS_URL}/{user.id}/status",
            headers=auth_headers(token),
            params={"is_active": True},
        )
        assert resp.status_code == 200
        assert "启用" in resp.json()["message"]

    async def test_toggle_self_forbidden(self, client, admin_user):
        """不能禁用自己"""
        user, token = admin_user
        resp = await client.put(
            f"{USERS_URL}/{user.id}/status",
            headers=auth_headers(token),
            params={"is_active": False},
        )
        assert resp.status_code == 400

    async def test_toggle_not_found(self, client, admin_user):
        """用户不存在"""
        _, token = admin_user
        resp = await client.put(
            f"{USERS_URL}/99999/status",
            headers=auth_headers(token),
            params={"is_active": False},
        )
        assert resp.status_code == 404


class TestResetPassword:
    """重置密码端点（覆盖行 250-273）"""

    async def test_reset_password_success(self, client, admin_user, async_db):
        """成功重置密码"""
        _, token = admin_user
        user = User(
            username="reset_pwd_target",
            password_hash=get_password_hash("OldPass@123"),
            role="operator",
            is_active=True,
        )
        async_db.add(user)
        await async_db.flush()

        resp = await client.put(
            f"{USERS_URL}/{user.id}/reset-password",
            headers=auth_headers(token),
            params={"new_password": "NewPass@456"},
        )
        assert resp.status_code == 200
        assert "已重置" in resp.json()["message"]

    async def test_reset_password_not_found(self, client, admin_user):
        """用户不存在"""
        _, token = admin_user
        resp = await client.put(
            f"{USERS_URL}/99999/reset-password",
            headers=auth_headers(token),
            params={"new_password": "NewPass@456"},
        )
        assert resp.status_code == 404


class TestLoginHistory:
    """登录历史端点（覆盖行 276-304）"""

    async def test_get_login_history(self, client, admin_user, async_db):
        """获取登录历史"""
        _, token = admin_user
        user = User(
            username="history_user",
            password_hash=get_password_hash("Test@1234"),
            role="operator",
            is_active=True,
        )
        async_db.add(user)
        await async_db.flush()

        # 插入登录历史
        async_db.add(
            UserLoginHistory(
                user_id=user.id,
                login_ip="127.0.0.1",
                user_agent="test-agent",
                status="success",
            )
        )
        async_db.add(
            UserLoginHistory(
                user_id=user.id,
                login_ip="192.168.1.1",
                user_agent="test-agent-2",
                status="failed",
                fail_reason="密码错误",
            )
        )
        await async_db.flush()

        resp = await client.get(
            f"{USERS_URL}/{user.id}/login-history",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    async def test_get_login_history_pagination(self, client, admin_user, async_db):
        """登录历史分页"""
        _, token = admin_user
        user = User(
            username="history_page_user",
            password_hash=get_password_hash("Test@1234"),
            role="operator",
            is_active=True,
        )
        async_db.add(user)
        await async_db.flush()

        resp = await client.get(
            f"{USERS_URL}/{user.id}/login-history",
            headers=auth_headers(token),
            params={"page": 1, "page_size": 5},
        )
        assert resp.status_code == 200
        assert resp.json()["page"] == 1
        assert resp.json()["page_size"] == 5


class TestUserSites:
    """用户站点管理端点（覆盖行 310-367）"""

    async def test_get_user_sites_empty(self, client, admin_user, async_db):
        """获取用户站点（无关联）"""
        _, token = admin_user
        user = User(
            username="site_user",
            password_hash=get_password_hash("Test@1234"),
            role="operator",
            is_active=True,
        )
        async_db.add(user)
        await async_db.flush()

        resp = await client.get(
            f"{USERS_URL}/{user.id}/sites",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_get_user_sites_not_found(self, client, admin_user):
        """用户不存在"""
        _, token = admin_user
        resp = await client.get(
            f"{USERS_URL}/99999/sites",
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_update_user_sites(self, client, admin_user, async_db):
        """设置用户站点权限"""
        _, token = admin_user
        user = User(
            username="site_update_user",
            password_hash=get_password_hash("Test@1234"),
            role="operator",
            is_active=True,
        )
        async_db.add(user)
        site = Site(site_code="SITE001", site_name="测试站点1")
        async_db.add(site)
        await async_db.flush()

        resp = await client.put(
            f"{USERS_URL}/{user.id}/sites",
            headers=auth_headers(token),
            json={"site_ids": [site.id]},
        )
        assert resp.status_code == 200
        assert "1 个站点" in resp.json()["message"]

    async def test_update_user_sites_empty(self, client, admin_user, async_db):
        """清空用户站点"""
        _, token = admin_user
        user = User(
            username="site_clear_user",
            password_hash=get_password_hash("Test@1234"),
            role="operator",
            is_active=True,
        )
        async_db.add(user)
        await async_db.flush()

        resp = await client.put(
            f"{USERS_URL}/{user.id}/sites",
            headers=auth_headers(token),
            json={"site_ids": []},
        )
        assert resp.status_code == 200
        assert "0 个站点" in resp.json()["message"]

    async def test_update_user_sites_invalid_site(self, client, admin_user, async_db):
        """站点不存在"""
        _, token = admin_user
        user = User(
            username="site_invalid_user",
            password_hash=get_password_hash("Test@1234"),
            role="operator",
            is_active=True,
        )
        async_db.add(user)
        await async_db.flush()

        resp = await client.put(
            f"{USERS_URL}/{user.id}/sites",
            headers=auth_headers(token),
            json={"site_ids": [99999]},
        )
        assert resp.status_code == 400
        assert "站点不存在" in resp.json()["detail"]

    async def test_update_user_sites_user_not_found(self, client, admin_user):
        """用户不存在"""
        _, token = admin_user
        resp = await client.put(
            f"{USERS_URL}/99999/sites",
            headers=auth_headers(token),
            json={"site_ids": []},
        )
        assert resp.status_code == 404

    async def test_get_user_sites_with_data(self, client, admin_user, async_db):
        """获取有站点关联的用户站点列表"""
        _, token = admin_user
        user = User(
            username="site_data_user",
            password_hash=get_password_hash("Test@1234"),
            role="operator",
            is_active=True,
        )
        async_db.add(user)
        site = Site(site_code="SITE002", site_name="测试站点2")
        async_db.add(site)
        await async_db.flush()

        # 创建关联
        async_db.add(UserSite(user_id=user.id, site_id=site.id))
        await async_db.flush()

        resp = await client.get(
            f"{USERS_URL}/{user.id}/sites",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["site_code"] == "SITE002"
        assert data[0]["site_name"] == "测试站点2"


class TestBatchDeleteUsers:
    """批量删除端点（覆盖行 196-218）"""

    async def test_batch_delete_success(self, client, admin_user, async_db):
        """批量删除用户"""
        _, token = admin_user
        ids = []
        for i in range(3):
            u = User(
                username=f"batch_del_{i}",
                password_hash=get_password_hash("Test@1234"),
                role="viewer",
                is_active=True,
            )
            async_db.add(u)
            await async_db.flush()
            ids.append(u.id)

        resp = await client.post(
            f"{USERS_URL}/batch-delete",
            headers=auth_headers(token),
            json=ids,
        )
        assert resp.status_code == 200
        assert resp.json()["deleted_count"] == 3

    async def test_batch_delete_self_forbidden(self, client, admin_user):
        """批量删除不能包含自己"""
        user, token = admin_user
        resp = await client.post(
            f"{USERS_URL}/batch-delete",
            headers=auth_headers(token),
            json=[user.id],
        )
        assert resp.status_code == 400

    async def test_batch_delete_not_found(self, client, admin_user):
        """批量删除不存在的用户"""
        _, token = admin_user
        resp = await client.post(
            f"{USERS_URL}/batch-delete",
            headers=auth_headers(token),
            json=[99998, 99999],
        )
        assert resp.status_code == 404
