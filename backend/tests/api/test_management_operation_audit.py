import json

from sqlalchemy import select

from app.models.log import OperationLog
from tests.conftest import auth_headers


async def test_user_create_and_update_are_audited(client, admin_user, async_db):
    admin, token = admin_user

    create_response = await client.post(
        "/api/v1/users",
        headers=auth_headers(token),
        json={
            "username": "audit_target_user",
            "password": "Test@1234",
            "real_name": "审计目标用户",
            "role": "operator",
        },
    )
    assert create_response.status_code == 200
    user_id = create_response.json()["id"]

    update_response = await client.put(
        f"/api/v1/users/{user_id}",
        headers=auth_headers(token),
        json={"department": "审计测试部"},
    )
    assert update_response.status_code == 200

    result = await async_db.execute(
        select(OperationLog)
        .where(OperationLog.module == "user", OperationLog.target_id == user_id)
        .order_by(OperationLog.id)
    )
    logs = list(result.scalars().all())

    assert [log.action for log in logs] == ["create", "update"]
    assert all(log.user_id == admin.id and log.username == admin.username for log in logs)
    assert json.loads(logs[1].new_value)["department"] == "审计测试部"
    assert "Test@1234" not in (logs[0].new_value or "")


async def test_site_create_and_update_are_audited(client, admin_user, async_db):
    admin, token = admin_user

    create_response = await client.post(
        "/api/v1/spatial/sites",
        headers=auth_headers(token),
        json={"site_code": "AUDIT-SITE", "site_name": "审计测试站点"},
    )
    assert create_response.status_code == 200
    site_id = create_response.json()["id"]

    update_response = await client.put(
        f"/api/v1/spatial/sites/{site_id}",
        headers=auth_headers(token),
        json={"address": "审计测试地址"},
    )
    assert update_response.status_code == 200

    result = await async_db.execute(
        select(OperationLog)
        .where(OperationLog.target_type == "site", OperationLog.target_id == site_id)
        .order_by(OperationLog.id)
    )
    logs = list(result.scalars().all())

    assert [log.action for log in logs] == ["create", "update"]
    assert all(log.module == "config" for log in logs)
    assert all(log.user_id == admin.id and log.username == admin.username for log in logs)
    assert json.loads(logs[1].new_value)["address"] == "审计测试地址"
