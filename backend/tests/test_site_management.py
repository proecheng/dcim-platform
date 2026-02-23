"""
Story 16-1: 站点管理测试
- Site CRUD（含新字段: contact_person, contact_phone, contact_email, network_config, status）
- 站点列表统计（gateway_count, device_count）
- 站点删除关联检查（Floor/Gateway/Device/DataSource）
- 站点状态管理
- EMQX ACL 规则自动创建/查询
- site_id 权限过滤（Gateway/DataSource 列表）
- require_site_access 依赖
- EmqxAclService 单元测试
"""

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers


# ==================== 辅助函数 ====================


async def create_site(client: AsyncClient, token: str, **kwargs) -> dict:
    """创建站点并返回响应数据"""
    data = {
        "site_code": kwargs.get("site_code", "SITE-001"),
        "site_name": kwargs.get("site_name", "测试站点"),
        "address": kwargs.get("address", "北京市海淀区"),
        "contact_person": kwargs.get("contact_person", "张三"),
        "contact_phone": kwargs.get("contact_phone", "13800138000"),
        "contact_email": kwargs.get("contact_email", "test@example.com"),
        "network_config": kwargs.get("network_config", {"vpn_ip": "10.0.0.1", "type": "ipsec"}),
        "description": kwargs.get("description", "测试站点描述"),
    }
    resp = await client.post("/api/v1/spatial/sites", json=data, headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    return resp.json()


async def create_gateway_for_site(db, site_id: int, gateway_id: str = "gw-test-001"):
    """在指定站点下创建网关"""
    from app.models.gateway import Gateway

    gw = Gateway(gateway_id=gateway_id, name="测试网关", site_id=site_id)
    db.add(gw)
    await db.flush()
    return gw


async def create_device_for_site(db, site_id: int, name: str = "测试设备"):
    """在指定站点下创建设备"""
    from app.models.device import Device
    import uuid

    code = f"DEV-{uuid.uuid4().hex[:8]}"
    dev = Device(device_code=code, device_name=name, device_type="UPS", area_code="A01", site_id=site_id)
    db.add(dev)
    await db.flush()
    return dev


async def create_datasource_for_site(db, site_id: int, name: str = "测试数据源"):
    """在指定站点下创建数据源"""
    from app.models.gateway import DataSource

    ds = DataSource(
        name=name, protocol_type="modbus_tcp", site_id=site_id, connection_config={"host": "127.0.0.1", "port": 502}
    )
    db.add(ds)
    await db.flush()
    return ds


# ==================== Site CRUD 测试 ====================


class TestSiteCRUD:
    """站点 CRUD 基础测试"""

    @pytest.mark.asyncio
    async def test_create_site_with_new_fields(self, client, admin_user):
        """创建站点 — 包含联系人、网络配置等新字段"""
        _, token = admin_user
        site = await create_site(client, token)
        assert site["site_code"] == "SITE-001"
        assert site["site_name"] == "测试站点"
        assert site["contact_person"] == "张三"
        assert site["contact_phone"] == "13800138000"
        assert site["contact_email"] == "test@example.com"
        assert site["network_config"]["vpn_ip"] == "10.0.0.1"
        assert site["status"] == "active"
        assert site["gateway_count"] == 0
        assert site["device_count"] == 0

    @pytest.mark.asyncio
    async def test_create_site_minimal(self, client, admin_user):
        """创建站点 — 仅必填字段"""
        _, token = admin_user
        resp = await client.post(
            "/api/v1/spatial/sites",
            json={"site_code": "SITE-MIN", "site_name": "最小站点"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["contact_person"] is None
        assert data["network_config"] is None

    @pytest.mark.asyncio
    async def test_list_sites_with_status_filter(self, client, admin_user):
        """站点列表 — 按状态过滤"""
        _, token = admin_user
        await create_site(client, token, site_code="S1", site_name="站点1")
        await create_site(client, token, site_code="S2", site_name="站点2")

        resp = await client.get(
            "/api/v1/spatial/sites",
            params={"status": "active"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        sites = resp.json()
        assert len(sites) >= 2
        assert all(s["status"] == "active" for s in sites)

    @pytest.mark.asyncio
    async def test_update_site_new_fields(self, client, admin_user):
        """更新站点 — 修改联系人和网络配置"""
        _, token = admin_user
        site = await create_site(client, token)
        resp = await client.put(
            f"/api/v1/spatial/sites/{site['id']}",
            json={
                "contact_person": "李四",
                "network_config": {"vpn_ip": "10.0.0.2", "type": "wireguard"},
            },
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["contact_person"] == "李四"
        assert updated["network_config"]["type"] == "wireguard"

    @pytest.mark.asyncio
    async def test_update_site_status_not_in_update_schema(self, client, admin_user):
        """更新站点 — status 字段不应通过 PUT /sites/{id} 修改（应使用专用状态接口）"""
        _, token = admin_user
        site = await create_site(client, token)
        resp = await client.put(
            f"/api/v1/spatial/sites/{site['id']}",
            json={"status": "maintenance"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        updated = resp.json()
        # status 不应被修改（SiteUpdate 已移除 status 字段）
        assert updated["status"] == "active"

    @pytest.mark.asyncio
    async def test_update_site_returns_stats(self, client, admin_user, async_db):
        """更新站点 — 响应包含 gateway_count 和 device_count"""
        _, token = admin_user
        site = await create_site(client, token)
        site_id = site["id"]

        # 创建网关和设备
        await create_gateway_for_site(async_db, site_id, "gw-upd-001")
        await create_device_for_site(async_db, site_id, "设备-upd-001")
        await create_device_for_site(async_db, site_id, "设备-upd-002")

        resp = await client.put(
            f"/api/v1/spatial/sites/{site_id}",
            json={"site_name": "更新后站点"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["gateway_count"] == 1
        assert updated["device_count"] == 2

    @pytest.mark.asyncio
    async def test_update_site_not_found(self, client, admin_user):
        """更新不存在的站点"""
        _, token = admin_user
        resp = await client.put(
            "/api/v1/spatial/sites/99999",
            json={"site_name": "不存在"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 404


class TestSiteStatistics:
    """站点列表统计测试"""

    @pytest.mark.asyncio
    async def test_site_list_with_gateway_count(self, client, admin_user, async_db):
        """站点列表 — 包含网关数量统计"""
        _, token = admin_user
        site = await create_site(client, token)
        site_id = site["id"]

        # 创建网关
        await create_gateway_for_site(async_db, site_id, "gw-stat-001")
        await create_gateway_for_site(async_db, site_id, "gw-stat-002")

        resp = await client.get("/api/v1/spatial/sites", headers=auth_headers(token))
        assert resp.status_code == 200
        sites = resp.json()
        target = next(s for s in sites if s["id"] == site_id)
        assert target["gateway_count"] == 2

    @pytest.mark.asyncio
    async def test_site_list_with_device_count(self, client, admin_user, async_db):
        """站点列表 — 包含设备数量统计"""
        _, token = admin_user
        site = await create_site(client, token)
        site_id = site["id"]

        await create_device_for_site(async_db, site_id, "设备1")
        await create_device_for_site(async_db, site_id, "设备2")
        await create_device_for_site(async_db, site_id, "设备3")

        resp = await client.get("/api/v1/spatial/sites", headers=auth_headers(token))
        assert resp.status_code == 200
        sites = resp.json()
        target = next(s for s in sites if s["id"] == site_id)
        assert target["device_count"] == 3


class TestSiteDelete:
    """站点删除关联检查测试"""

    @pytest.mark.asyncio
    async def test_delete_empty_site(self, client, admin_user):
        """删除无关联数据的站点 — 成功"""
        _, token = admin_user
        site = await create_site(client, token)
        resp = await client.delete(f"/api/v1/spatial/sites/{site['id']}", headers=auth_headers(token))
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_delete_site_with_gateway_blocked(self, client, admin_user, async_db):
        """删除有网关的站点 — 被阻止"""
        _, token = admin_user
        site = await create_site(client, token)
        await create_gateway_for_site(async_db, site["id"])

        resp = await client.delete(f"/api/v1/spatial/sites/{site['id']}", headers=auth_headers(token))
        assert resp.status_code == 400
        assert "网关" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_delete_site_with_device_blocked(self, client, admin_user, async_db):
        """删除有设备的站点 — 被阻止"""
        _, token = admin_user
        site = await create_site(client, token)
        await create_device_for_site(async_db, site["id"])

        resp = await client.delete(f"/api/v1/spatial/sites/{site['id']}", headers=auth_headers(token))
        assert resp.status_code == 400
        assert "设备" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_delete_site_with_datasource_blocked(self, client, admin_user, async_db):
        """删除有数据源的站点 — 被阻止"""
        _, token = admin_user
        site = await create_site(client, token)
        await create_datasource_for_site(async_db, site["id"])

        resp = await client.delete(f"/api/v1/spatial/sites/{site['id']}", headers=auth_headers(token))
        assert resp.status_code == 400
        assert "数据源" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_delete_nonexistent_site(self, client, admin_user):
        """删除不存在的站点"""
        _, token = admin_user
        resp = await client.delete("/api/v1/spatial/sites/99999", headers=auth_headers(token))
        assert resp.status_code == 404


class TestSiteStatus:
    """站点状态管理测试"""

    @pytest.mark.asyncio
    async def test_update_site_status(self, client, admin_user):
        """更新站点状态"""
        _, token = admin_user
        site = await create_site(client, token)
        resp = await client.put(
            f"/api/v1/spatial/sites/{site['id']}/status",
            params={"status": "maintenance"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert "maintenance" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_update_site_status_invalid(self, client, admin_user):
        """更新站点状态 — 无效状态"""
        _, token = admin_user
        site = await create_site(client, token)
        resp = await client.put(
            f"/api/v1/spatial/sites/{site['id']}/status",
            params={"status": "invalid_status"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_update_site_status_not_found(self, client, admin_user):
        """更新不存在站点的状态"""
        _, token = admin_user
        resp = await client.put(
            "/api/v1/spatial/sites/99999/status",
            params={"status": "active"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 404


class TestSiteAclRules:
    """站点 ACL 规则测试"""

    @pytest.mark.asyncio
    async def test_acl_rules_auto_created(self, client, admin_user):
        """创建站点时自动生成 ACL 规则"""
        _, token = admin_user
        site = await create_site(client, token)
        resp = await client.get(
            f"/api/v1/spatial/sites/{site['id']}/acl-rules",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        rules = resp.json()
        assert len(rules) >= 2  # allow + deny 规则
        # 验证 allow 规则
        allow_rules = [r for r in rules if r["permission"] == "allow"]
        assert len(allow_rules) >= 1
        assert f"dcim/{site['id']}/gw/+/#" in allow_rules[0]["topic_pattern"]

    @pytest.mark.asyncio
    async def test_acl_rules_cleaned_on_delete(self, client, admin_user, async_db):
        """删除站点时清理 ACL 规则"""
        _, token = admin_user
        site = await create_site(client, token)
        site_id = site["id"]

        # 确认规则存在
        resp = await client.get(
            f"/api/v1/spatial/sites/{site_id}/acl-rules",
            headers=auth_headers(token),
        )
        assert len(resp.json()) >= 2

        # 删除站点
        resp = await client.delete(f"/api/v1/spatial/sites/{site_id}", headers=auth_headers(token))
        assert resp.status_code == 200

        # 验证规则已清理（通过直接查询数据库）
        from sqlalchemy import select, func
        from app.models.gateway import MqttAclRule

        result = await async_db.execute(select(func.count(MqttAclRule.id)).where(MqttAclRule.site_id == site_id))
        assert result.scalar() == 0


class TestGatewaySiteFilter:
    """网关 API site_id 过滤测试"""

    @pytest.mark.asyncio
    async def test_gateway_list_filter_by_site(self, client, admin_user, async_db):
        """网关列表 — 按 site_id 过滤"""
        _, token = admin_user
        site1 = await create_site(client, token, site_code="GW-S1", site_name="站点1")
        site2 = await create_site(client, token, site_code="GW-S2", site_name="站点2")

        await create_gateway_for_site(async_db, site1["id"], "gw-s1-001")
        await create_gateway_for_site(async_db, site2["id"], "gw-s2-001")
        await create_gateway_for_site(async_db, site2["id"], "gw-s2-002")

        # 过滤站点1
        resp = await client.get(
            "/api/v1/gateways",
            params={"site_id": site1["id"]},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1

        # 过滤站点2
        resp = await client.get(
            "/api/v1/gateways",
            params={"site_id": site2["id"]},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2

    @pytest.mark.asyncio
    async def test_gateway_summary_filter_by_site(self, client, admin_user, async_db):
        """网关汇总 — 按 site_id 过滤"""
        _, token = admin_user
        site = await create_site(client, token, site_code="GW-SUM", site_name="汇总站点")
        await create_gateway_for_site(async_db, site["id"], "gw-sum-001")

        resp = await client.get(
            "/api/v1/gateways/summary",
            params={"site_id": site["id"]},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1


class TestDatasourceSiteFilter:
    """数据源 API site_id 过滤测试"""

    @pytest.mark.asyncio
    async def test_datasource_list_filter_by_site(self, client, admin_user, async_db):
        """数据源列表 — 按 site_id 过滤"""
        _, token = admin_user
        site1 = await create_site(client, token, site_code="DS-S1", site_name="数据源站点1")
        site2 = await create_site(client, token, site_code="DS-S2", site_name="数据源站点2")

        await create_datasource_for_site(async_db, site1["id"], "数据源1")
        await create_datasource_for_site(async_db, site2["id"], "数据源2")
        await create_datasource_for_site(async_db, site2["id"], "数据源3")

        resp = await client.get(
            "/api/v1/datasources",
            params={"site_id": site1["id"]},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1

        resp = await client.get(
            "/api/v1/datasources",
            params={"site_id": site2["id"]},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2


class TestSiteAccessPermission:
    """站点访问权限测试"""

    @pytest.mark.asyncio
    async def test_require_site_access_blocks_unauthorized_operator(self, client, operator_user, admin_user, async_db):
        """operator 无站点权限时，update/delete/status 被 require_site_access 拦截"""
        _, admin_token = admin_user
        operator, operator_token = operator_user

        # admin 创建站点（operator 未被授权）
        site = await create_site(client, admin_token, site_code="ACCESS-BLK", site_name="权限拦截站点")
        site_id = site["id"]

        # operator 尝试更新站点 — 应被拦截
        resp = await client.put(
            f"/api/v1/spatial/sites/{site_id}",
            json={"site_name": "非法修改"},
            headers=auth_headers(operator_token),
        )
        assert resp.status_code == 403
        assert "无权访问" in resp.json()["detail"]

        # operator 尝试删除站点 — 应被拦截
        resp = await client.delete(
            f"/api/v1/spatial/sites/{site_id}",
            headers=auth_headers(operator_token),
        )
        assert resp.status_code == 403

        # operator 尝试更新站点状态 — 应被拦截
        resp = await client.put(
            f"/api/v1/spatial/sites/{site_id}/status",
            params={"status": "maintenance"},
            headers=auth_headers(operator_token),
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_require_site_access_allows_authorized_operator(self, client, operator_user, admin_user, async_db):
        """operator 有站点权限时，可以正常操作"""
        _, admin_token = admin_user
        operator, operator_token = operator_user

        site = await create_site(client, admin_token, site_code="ACCESS-OK", site_name="授权站点")
        site_id = site["id"]

        # 给 operator 分配站点权限
        from app.models.user import UserSite

        us = UserSite(user_id=operator.id, site_id=site_id)
        async_db.add(us)
        await async_db.flush()

        # operator 更新站点 — 应成功
        resp = await client.put(
            f"/api/v1/spatial/sites/{site_id}",
            json={"site_name": "合法修改"},
            headers=auth_headers(operator_token),
        )
        assert resp.status_code == 200
        assert resp.json()["site_name"] == "合法修改"

        # operator 更新站点状态 — 应成功
        resp = await client.put(
            f"/api/v1/spatial/sites/{site_id}/status",
            params={"status": "maintenance"},
            headers=auth_headers(operator_token),
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_viewer_list_sites_filtered(self, client, viewer_user, admin_user, async_db):
        """viewer 用户只能看到被授权的站点"""
        _, admin_token = admin_user
        viewer, viewer_token = viewer_user

        site1 = await create_site(client, admin_token, site_code="LIST-S1", site_name="列表站点1")
        site2 = await create_site(client, admin_token, site_code="LIST-S2", site_name="列表站点2")

        # 给 viewer 分配站点1权限
        from app.models.user import UserSite

        us = UserSite(user_id=viewer.id, site_id=site1["id"])
        async_db.add(us)
        await async_db.flush()

        # viewer 查看站点列表 — 只能看到站点1
        resp = await client.get("/api/v1/spatial/sites", headers=auth_headers(viewer_token))
        assert resp.status_code == 200
        sites = resp.json()
        site_codes = [s["site_code"] for s in sites]
        assert "LIST-S1" in site_codes
        assert "LIST-S2" not in site_codes

    @pytest.mark.asyncio
    async def test_viewer_filtered_by_user_sites(self, client, viewer_user, admin_user, async_db):
        """viewer 用户只能看到被授权站点的网关"""
        _, admin_token = admin_user
        viewer, viewer_token = viewer_user

        # admin 创建两个站点
        site1 = await create_site(client, admin_token, site_code="PERM-S1", site_name="权限站点1")
        site2 = await create_site(client, admin_token, site_code="PERM-S2", site_name="权限站点2")

        # 创建网关
        await create_gateway_for_site(async_db, site1["id"], "gw-perm-001")
        await create_gateway_for_site(async_db, site2["id"], "gw-perm-002")

        # 给 viewer 分配站点1权限
        from app.models.user import UserSite

        us = UserSite(user_id=viewer.id, site_id=site1["id"])
        async_db.add(us)
        await async_db.flush()

        # viewer 查看网关列表 — 只能看到站点1的网关
        resp = await client.get("/api/v1/gateways", headers=auth_headers(viewer_token))
        assert resp.status_code == 200
        data = resp.json()
        # viewer 只能看到被授权站点的网关
        gw_ids = [item["gateway_id"] for item in data["items"]]
        assert "gw-perm-001" in gw_ids
        assert "gw-perm-002" not in gw_ids

    @pytest.mark.asyncio
    async def test_admin_sees_all_gateways(self, client, admin_user, async_db):
        """admin 用户可以看到所有站点的网关"""
        _, token = admin_user
        site1 = await create_site(client, token, site_code="ADM-S1", site_name="管理站点1")
        site2 = await create_site(client, token, site_code="ADM-S2", site_name="管理站点2")

        await create_gateway_for_site(async_db, site1["id"], "gw-adm-001")
        await create_gateway_for_site(async_db, site2["id"], "gw-adm-002")

        resp = await client.get("/api/v1/gateways", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        gw_ids = [item["gateway_id"] for item in data["items"]]
        assert "gw-adm-001" in gw_ids
        assert "gw-adm-002" in gw_ids


class TestEmqxAclService:
    """EmqxAclService 单元测试"""

    @pytest.mark.asyncio
    async def test_generate_acl_rules(self):
        """生成 ACL 规则"""
        from app.services.emqx_acl import EmqxAclService

        svc = EmqxAclService()
        rules = svc.generate_acl_rules(1, "SITE-001")
        assert len(rules) == 2
        assert rules[0]["permission"] == "allow"
        assert rules[1]["permission"] == "deny"
        assert "dcim/1/gw/+/#" in rules[0]["topic_pattern"]

    @pytest.mark.asyncio
    async def test_match_topic_exact(self):
        """Topic 匹配 — 精确匹配"""
        from app.services.emqx_acl import EmqxAclService

        assert EmqxAclService._match_topic("dcim/1/gw/abc/data", "dcim/1/gw/abc/data")
        assert not EmqxAclService._match_topic("dcim/1/gw/abc/data", "dcim/2/gw/abc/data")

    @pytest.mark.asyncio
    async def test_match_topic_plus_wildcard(self):
        """Topic 匹配 — + 通配符"""
        from app.services.emqx_acl import EmqxAclService

        assert EmqxAclService._match_topic("dcim/+/gw/+/data", "dcim/1/gw/abc/data")
        assert EmqxAclService._match_topic("dcim/+/gw/+/data", "dcim/2/gw/xyz/data")
        assert not EmqxAclService._match_topic("dcim/+/gw/+/data", "dcim/1/gw/abc/status")

    @pytest.mark.asyncio
    async def test_match_topic_hash_wildcard(self):
        """Topic 匹配 — # 通配符"""
        from app.services.emqx_acl import EmqxAclService

        assert EmqxAclService._match_topic("dcim/1/gw/+/#", "dcim/1/gw/abc/data")
        assert EmqxAclService._match_topic("dcim/1/gw/+/#", "dcim/1/gw/abc/ota/status")
        assert not EmqxAclService._match_topic("dcim/1/gw/+/#", "dcim/2/gw/abc/data")

    @pytest.mark.asyncio
    async def test_match_client_wildcard(self):
        """客户端 ID 匹配 — 通配符"""
        from app.services.emqx_acl import EmqxAclService

        assert EmqxAclService._match_client("gw-SITE001-*", "gw-SITE001-abc")
        assert EmqxAclService._match_client("gw-SITE001-*", "gw-SITE001-xyz")
        assert not EmqxAclService._match_client("gw-SITE001-*", "gw-SITE002-abc")
        assert EmqxAclService._match_client(None, "any-client")

    @pytest.mark.asyncio
    async def test_on_site_created(self, async_db):
        """站点创建时自动生成 ACL 规则"""
        from app.services.emqx_acl import emqx_acl_service
        from app.models.spatial import Site

        site = Site(site_code="ACL-TEST", site_name="ACL测试站点")
        async_db.add(site)
        await async_db.flush()

        rules = await emqx_acl_service.on_site_created(site.id, site.site_code, async_db)
        assert len(rules) == 2

        # 验证数据库中有规则
        db_rules = await emqx_acl_service.get_site_rules(site.id, async_db)
        assert len(db_rules) == 2

    @pytest.mark.asyncio
    async def test_on_site_deleted(self, async_db):
        """站点删除时清理 ACL 规则"""
        from app.services.emqx_acl import emqx_acl_service
        from app.models.spatial import Site

        site = Site(site_code="ACL-DEL", site_name="ACL删除测试")
        async_db.add(site)
        await async_db.flush()

        await emqx_acl_service.on_site_created(site.id, site.site_code, async_db)
        count = await emqx_acl_service.on_site_deleted(site.id, async_db)
        assert count == 2

        remaining = await emqx_acl_service.get_site_rules(site.id, async_db)
        assert len(remaining) == 0

    @pytest.mark.asyncio
    async def test_refresh_site_rules(self, async_db):
        """刷新站点 ACL 规则"""
        from app.services.emqx_acl import emqx_acl_service
        from app.models.spatial import Site

        site = Site(site_code="ACL-REF", site_name="ACL刷新测试")
        async_db.add(site)
        await async_db.flush()

        await emqx_acl_service.on_site_created(site.id, site.site_code, async_db)
        new_rules = await emqx_acl_service.refresh_site_rules(site.id, site.site_code, async_db)
        assert len(new_rules) == 2

    @pytest.mark.asyncio
    async def test_check_topic_permission(self, async_db):
        """检查 Topic 访问权限"""
        from app.services.emqx_acl import emqx_acl_service
        from app.models.spatial import Site

        site = Site(site_code="ACL-CHK", site_name="ACL权限检查")
        async_db.add(site)
        await async_db.flush()

        await emqx_acl_service.on_site_created(site.id, site.site_code, async_db)

        # 站点内网关 — 允许
        allowed = await emqx_acl_service.check_topic_permission(
            site.id, "gw-ACL-CHK-001", f"dcim/{site.id}/gw/001/data", "publish", async_db
        )
        assert allowed is True


class TestSiteSummary:
    """跨站点汇总 API 测试"""

    @pytest.mark.asyncio
    async def test_summary_empty(self, client, admin_user):
        """无站点时汇总返回零值"""
        _, token = admin_user
        resp = await client.get("/api/v1/spatial/sites/summary", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_sites"] == 0
        assert data["total_gateways"] == 0
        assert data["total_devices"] == 0
        assert data["total_alarms"] == 0
        assert data["sites"] == []

    @pytest.mark.asyncio
    async def test_summary_with_sites(self, client, admin_user, async_db):
        """有站点时汇总包含统计数据"""
        _, token = admin_user
        site1 = await create_site(client, token, site_code="SUM-S1", site_name="汇总站点1")
        site2 = await create_site(client, token, site_code="SUM-S2", site_name="汇总站点2")

        await create_gateway_for_site(async_db, site1["id"], "gw-sum-s1-001")
        await create_gateway_for_site(async_db, site2["id"], "gw-sum-s2-001")
        await create_gateway_for_site(async_db, site2["id"], "gw-sum-s2-002")
        await create_device_for_site(async_db, site1["id"], "设备-sum-1")

        resp = await client.get("/api/v1/spatial/sites/summary", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_sites"] >= 2
        assert data["total_gateways"] >= 3
        assert data["total_devices"] >= 1
        # 验证各站点摘要
        site_map = {s["site_code"]: s for s in data["sites"]}
        assert site_map["SUM-S1"]["gateway_count"] == 1
        assert site_map["SUM-S2"]["gateway_count"] == 2

    @pytest.mark.asyncio
    async def test_summary_viewer_filtered(self, client, viewer_user, admin_user, async_db):
        """viewer 只能看到授权站点的汇总"""
        _, admin_token = admin_user
        viewer, viewer_token = viewer_user

        site1 = await create_site(client, admin_token, site_code="SUMV-S1", site_name="汇总V站点1")
        site2 = await create_site(client, admin_token, site_code="SUMV-S2", site_name="汇总V站点2")

        # 给 viewer 分配站点1权限
        from app.models.user import UserSite

        us = UserSite(user_id=viewer.id, site_id=site1["id"])
        async_db.add(us)
        await async_db.flush()

        resp = await client.get("/api/v1/spatial/sites/summary", headers=auth_headers(viewer_token))
        assert resp.status_code == 200
        data = resp.json()
        site_codes = [s["site_code"] for s in data["sites"]]
        assert "SUMV-S1" in site_codes
        assert "SUMV-S2" not in site_codes
