"""
Story 34.1 — 用户通知联系方式 API 测试
"""

import pytest
from tests.conftest import auth_headers


@pytest.fixture
async def target_user(async_db):
    """创建一个被管理的目标用户（有 phone 和 email）"""
    from app.models.user import User
    from app.core.security import get_password_hash

    user = User(
        username="target_user",
        password_hash=get_password_hash("test_secure_pwd_!@#"),
        real_name="目标用户",
        email="target@test.local",
        phone="13800138000",
        role="viewer",
        is_active=True,
    )
    async_db.add(user)
    await async_db.flush()
    return user


class TestCreateNotificationContact:
    """POST /{user_id}/notification-contacts"""

    async def test_create_sms_contact(self, client, admin_user, target_user):
        _, token = admin_user
        resp = await client.post(
            f"/api/v1/users/{target_user.id}/notification-contacts",
            json={
                "channel_type": "sms",
                "contact_value": "13900139000",
            },
            headers=auth_headers(token),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["channel_type"] == "sms"
        assert data["contact_value"] == "13900139000"
        assert data["is_enabled"] is True
        assert data["platform"] is None
        assert "id" in data

    async def test_create_im_contact_with_platform(self, client, admin_user, target_user):
        _, token = admin_user
        resp = await client.post(
            f"/api/v1/users/{target_user.id}/notification-contacts",
            json={
                "channel_type": "im",
                "platform": "dingtalk",
                "contact_value": "user_dingtalk_id_123",
            },
            headers=auth_headers(token),
        )
        assert resp.status_code == 201
        assert resp.json()["platform"] == "dingtalk"

    async def test_create_email_contact(self, client, admin_user, target_user):
        _, token = admin_user
        resp = await client.post(
            f"/api/v1/users/{target_user.id}/notification-contacts",
            json={
                "channel_type": "email",
                "contact_value": "notify@example.com",
            },
            headers=auth_headers(token),
        )
        assert resp.status_code == 201
        assert resp.json()["channel_type"] == "email"

    async def test_create_voice_contact(self, client, admin_user, target_user):
        _, token = admin_user
        resp = await client.post(
            f"/api/v1/users/{target_user.id}/notification-contacts",
            json={
                "channel_type": "voice",
                "contact_value": "13700137000",
            },
            headers=auth_headers(token),
        )
        assert resp.status_code == 201
        assert resp.json()["channel_type"] == "voice"

    async def test_create_im_without_platform_fails(self, client, admin_user, target_user):
        _, token = admin_user
        resp = await client.post(
            f"/api/v1/users/{target_user.id}/notification-contacts",
            json={
                "channel_type": "im",
                "contact_value": "some_id",
            },
            headers=auth_headers(token),
        )
        assert resp.status_code == 422

    async def test_create_sms_invalid_phone_fails(self, client, admin_user, target_user):
        _, token = admin_user
        resp = await client.post(
            f"/api/v1/users/{target_user.id}/notification-contacts",
            json={
                "channel_type": "sms",
                "contact_value": "12345",
            },
            headers=auth_headers(token),
        )
        assert resp.status_code == 422

    async def test_create_email_invalid_format_fails(self, client, admin_user, target_user):
        _, token = admin_user
        resp = await client.post(
            f"/api/v1/users/{target_user.id}/notification-contacts",
            json={
                "channel_type": "email",
                "contact_value": "not-an-email",
            },
            headers=auth_headers(token),
        )
        assert resp.status_code == 422

    async def test_create_non_im_with_platform_fails(self, client, admin_user, target_user):
        _, token = admin_user
        resp = await client.post(
            f"/api/v1/users/{target_user.id}/notification-contacts",
            json={
                "channel_type": "sms",
                "platform": "dingtalk",
                "contact_value": "13900139000",
            },
            headers=auth_headers(token),
        )
        assert resp.status_code == 422

    async def test_create_invalid_channel_type_fails(self, client, admin_user, target_user):
        _, token = admin_user
        resp = await client.post(
            f"/api/v1/users/{target_user.id}/notification-contacts",
            json={
                "channel_type": "fax",
                "contact_value": "12345",
            },
            headers=auth_headers(token),
        )
        assert resp.status_code == 422

    async def test_create_for_nonexistent_user_fails(self, client, admin_user):
        _, token = admin_user
        resp = await client.post(
            "/api/v1/users/99999/notification-contacts",
            json={
                "channel_type": "sms",
                "contact_value": "13900139000",
            },
            headers=auth_headers(token),
        )
        assert resp.status_code == 404


class TestGetNotificationContacts:
    """GET /{user_id}/notification-contacts"""

    async def test_get_empty_list(self, client, admin_user, target_user):
        _, token = admin_user
        resp = await client.get(
            f"/api/v1/users/{target_user.id}/notification-contacts",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_get_contacts_after_create(self, client, admin_user, target_user):
        _, token = admin_user
        # 创建两条
        await client.post(
            f"/api/v1/users/{target_user.id}/notification-contacts",
            json={"channel_type": "sms", "contact_value": "13900139000"},
            headers=auth_headers(token),
        )
        await client.post(
            f"/api/v1/users/{target_user.id}/notification-contacts",
            json={"channel_type": "email", "contact_value": "a@b.com"},
            headers=auth_headers(token),
        )
        resp = await client.get(
            f"/api/v1/users/{target_user.id}/notification-contacts",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    async def test_get_for_nonexistent_user_fails(self, client, admin_user):
        _, token = admin_user
        resp = await client.get(
            "/api/v1/users/99999/notification-contacts",
            headers=auth_headers(token),
        )
        assert resp.status_code == 404


class TestUpdateNotificationContact:
    """PUT /{user_id}/notification-contacts/{contact_id}"""

    async def test_update_contact_value(self, client, admin_user, target_user):
        _, token = admin_user
        create_resp = await client.post(
            f"/api/v1/users/{target_user.id}/notification-contacts",
            json={"channel_type": "sms", "contact_value": "13900139000"},
            headers=auth_headers(token),
        )
        contact_id = create_resp.json()["id"]

        resp = await client.put(
            f"/api/v1/users/{target_user.id}/notification-contacts/{contact_id}",
            json={"contact_value": "13800138001"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["contact_value"] == "13800138001"

    async def test_update_is_enabled(self, client, admin_user, target_user):
        _, token = admin_user
        create_resp = await client.post(
            f"/api/v1/users/{target_user.id}/notification-contacts",
            json={"channel_type": "email", "contact_value": "a@b.com"},
            headers=auth_headers(token),
        )
        contact_id = create_resp.json()["id"]

        resp = await client.put(
            f"/api/v1/users/{target_user.id}/notification-contacts/{contact_id}",
            json={"is_enabled": False},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["is_enabled"] is False

    async def test_update_sms_with_invalid_phone_fails(self, client, admin_user, target_user):
        _, token = admin_user
        create_resp = await client.post(
            f"/api/v1/users/{target_user.id}/notification-contacts",
            json={"channel_type": "sms", "contact_value": "13900139000"},
            headers=auth_headers(token),
        )
        contact_id = create_resp.json()["id"]

        resp = await client.put(
            f"/api/v1/users/{target_user.id}/notification-contacts/{contact_id}",
            json={"contact_value": "invalid"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 422

    async def test_update_nonexistent_contact_fails(self, client, admin_user, target_user):
        _, token = admin_user
        resp = await client.put(
            f"/api/v1/users/{target_user.id}/notification-contacts/99999",
            json={"is_enabled": False},
            headers=auth_headers(token),
        )
        assert resp.status_code == 404


class TestDeleteNotificationContact:
    """DELETE /{user_id}/notification-contacts/{contact_id}"""

    async def test_delete_contact(self, client, admin_user, target_user):
        _, token = admin_user
        create_resp = await client.post(
            f"/api/v1/users/{target_user.id}/notification-contacts",
            json={"channel_type": "sms", "contact_value": "13900139000"},
            headers=auth_headers(token),
        )
        contact_id = create_resp.json()["id"]

        resp = await client.delete(
            f"/api/v1/users/{target_user.id}/notification-contacts/{contact_id}",
            headers=auth_headers(token),
        )
        assert resp.status_code == 204

        # 确认已删除
        get_resp = await client.get(
            f"/api/v1/users/{target_user.id}/notification-contacts",
            headers=auth_headers(token),
        )
        assert len(get_resp.json()) == 0

    async def test_delete_nonexistent_contact_fails(self, client, admin_user, target_user):
        _, token = admin_user
        resp = await client.delete(
            f"/api/v1/users/{target_user.id}/notification-contacts/99999",
            headers=auth_headers(token),
        )
        assert resp.status_code == 404


class TestImportFromProfile:
    """POST /{user_id}/notification-contacts/import-from-profile"""

    async def test_import_creates_contacts(self, client, admin_user, target_user):
        _, token = admin_user
        resp = await client.post(
            f"/api/v1/users/{target_user.id}/notification-contacts/import-from-profile",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        # target_user 有 phone + email → sms, voice, email = 3 条
        assert len(data["created"]) == 3
        assert data["skipped"] == 0

        channels = {c["channel_type"] for c in data["created"]}
        assert channels == {"sms", "voice", "email"}

    async def test_import_idempotent(self, client, admin_user, target_user):
        _, token = admin_user
        # 第一次导入
        await client.post(
            f"/api/v1/users/{target_user.id}/notification-contacts/import-from-profile",
            headers=auth_headers(token),
        )
        # 第二次导入 — 全部跳过
        resp = await client.post(
            f"/api/v1/users/{target_user.id}/notification-contacts/import-from-profile",
            headers=auth_headers(token),
        )
        data = resp.json()
        assert len(data["created"]) == 0
        assert data["skipped"] == 3


class TestPermission:
    """权限控制测试"""

    async def test_non_admin_forbidden(self, client, operator_user, target_user):
        _, token = operator_user
        resp = await client.get(
            f"/api/v1/users/{target_user.id}/notification-contacts",
            headers=auth_headers(token),
        )
        assert resp.status_code == 403

    async def test_no_auth_unauthorized(self, client, target_user):
        resp = await client.get(
            f"/api/v1/users/{target_user.id}/notification-contacts",
        )
        assert resp.status_code in (401, 403)
