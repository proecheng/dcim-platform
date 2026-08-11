"""Story 39.1 HTTP and WebSocket authorization tests."""

from datetime import date, datetime, time, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from jose import jwt
from sqlalchemy import select

from app.api.deps import (
    SiteAccessContext,
    apply_site_scope,
    build_site_access_context,
    require_context_site_access,
    resolve_device_site_id,
    resolve_point_site_id,
)
from app.core.config import get_settings
from app.core.security import get_password_hash
from app.models.alarm import Alarm, AlarmThreshold
from app.models.asset import Asset, AssetInventory, AssetType, Cabinet, MaintenanceRecord
from app.models.cooling import ColdAisle, CoolingGroup, CoolingUnit
from app.models.command import CommandApproval, CommandAuditLog
from app.models.device import Device
from app.models.drift import DriftDetectionResult
from app.models.diagnosis import (
    BatterySOHRecord,
    DiagnosisAnnotation,
    DiagnosisResult,
    DiagnosisSession,
    SensorMetadata,
    TrendWarning,
)
from app.models.floor_map import FloorMap
from app.models.gateway import DataSource, FirmwarePackage, Gateway, OtaTask, OtaTaskGateway
from app.models.history import PointHistory
from app.models.point import Point, PointRealtime
from app.models.operation import InspectionPlan, WorkOrder
from app.models.power import BatteryGroup, UPSDevice
from app.models.report import DeviceHealthScore, MaintenanceAdvice, ReportRecord, ReportSchedule, ReportTemplate
from app.models.rollback import RollbackEvent
from app.models.energy import PowerDevice
from app.models.spatial import Floor, Room, Row, Site
from app.models.thermal import PrecoolSchedule
from app.models.topology_config import CoolingZone, CoolingZoneCabinet, CoolingZoneUnit, PowerPhaseMapping
from app.models.user import User, UserSession, UserSite
from app.models.video import Camera, NVR, VideoEvent
from tests.conftest import auth_headers


def _token(username: str, *, jti: str | None = None) -> str:
    settings = get_settings()
    payload = {"sub": username, "exp": datetime.now(timezone.utc) + timedelta(minutes=10)}
    if jti is not None:
        payload["jti"] = jti
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


@pytest.mark.asyncio
async def test_protected_http_rejects_token_without_jti(client, async_db):
    user = User(username="legacy-token", password_hash=get_password_hash("Test@1234"), role="viewer", is_active=True)
    async_db.add(user)
    await async_db.flush()

    response = await client.get("/api/v1/auth/me", headers=auth_headers(_token(user.username)))

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_active_jti_must_belong_to_token_user(client, async_db):
    token_user = User(username="token-owner", password_hash="x", role="viewer", is_active=True)
    session_user = User(username="session-owner", password_hash="x", role="viewer", is_active=True)
    async_db.add_all([token_user, session_user])
    await async_db.flush()
    async_db.add(UserSession(user_id=session_user.id, token_jti="shared-jti", is_active=True))
    await async_db.flush()

    response = await client.get(
        "/api/v1/auth/me",
        headers=auth_headers(_token(token_user.username, jti="shared-jti")),
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_site_access_context_distinguishes_admin_and_empty_scope(async_db):
    admin = User(username="ctx-admin", password_hash="x", role="admin", is_active=True)
    operator = User(username="ctx-operator", password_hash="x", role="operator", is_active=True)
    async_db.add_all([admin, operator])
    await async_db.flush()

    admin_context = await build_site_access_context(admin, "admin-jti", async_db)
    operator_context = await build_site_access_context(operator, "operator-jti", async_db)

    assert admin_context == SiteAccessContext(admin.id, "admin", "admin-jti", None)
    assert operator_context == SiteAccessContext(operator.id, "operator", "operator-jti", frozenset())


def test_explicit_site_and_object_id_use_different_status_codes():
    context = SiteAccessContext(7, "viewer", "jti", frozenset({10}))

    with pytest.raises(HTTPException) as explicit:
        require_context_site_access(20, context)
    assert explicit.value.status_code == 403

    with pytest.raises(HTTPException) as object_lookup:
        require_context_site_access(20, context, hide_existence=True)
    assert object_lookup.value.status_code == 404

    with pytest.raises(HTTPException) as unowned:
        require_context_site_access(None, context, hide_existence=True)
    assert unowned.value.status_code == 404


@pytest.mark.asyncio
async def test_scope_and_trusted_direct_indirect_resolvers(async_db):
    site_a = Site(site_code="AUTHZ-A", site_name="授权站点")
    site_b = Site(site_code="AUTHZ-B", site_name="越权站点")
    async_db.add_all([site_a, site_b])
    await async_db.flush()
    device_a = Device(device_code="AUTHZ-DA", device_name="A", device_type="UPS", area_code="A", site_id=site_a.id)
    device_b = Device(device_code="AUTHZ-DB", device_name="B", device_type="UPS", area_code="B", site_id=site_b.id)
    device_none = Device(device_code="AUTHZ-DN", device_name="N", device_type="UPS", area_code="N", site_id=None)
    async_db.add_all([device_a, device_b, device_none])
    await async_db.flush()
    point_a = Point(point_code="AUTHZ-PA", point_name="PA", point_type="AI", device_id=device_a.id)
    async_db.add(point_a)
    await async_db.flush()

    context = SiteAccessContext(9, "operator", "jti", frozenset({site_a.id}))
    query = apply_site_scope(select(Device), Device.site_id, context)
    visible = (await async_db.execute(query)).scalars().all()

    assert [item.id for item in visible] == [device_a.id]
    assert await resolve_device_site_id(async_db, device_a.id) == site_a.id
    assert await resolve_device_site_id(async_db, device_none.id) is None
    assert await resolve_point_site_id(async_db, point_a.id) == site_a.id


@pytest.mark.asyncio
async def test_non_admin_context_loads_real_user_site_rows(async_db):
    site = Site(site_code="AUTHZ-C", site_name="上下文站点")
    user = User(username="ctx-user", password_hash="x", role="viewer", is_active=True)
    async_db.add_all([site, user])
    await async_db.flush()
    async_db.add(UserSite(user_id=user.id, site_id=site.id))
    await async_db.flush()

    context = await build_site_access_context(user, "ctx-jti", async_db)

    assert context.site_ids == frozenset({site.id})


@pytest.mark.asyncio
async def test_inventory_gate_authenticates_topology_routes(client):
    response = await client.get("/api/v1/topology/export")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_device_http_matrix_is_site_isolated(client, async_db, operator_user):
    operator, token = operator_user
    site_a = Site(site_code="HTTP-DA", site_name="设备授权站点")
    site_b = Site(site_code="HTTP-DB", site_name="设备越权站点")
    async_db.add_all([site_a, site_b])
    await async_db.flush()
    async_db.add(UserSite(user_id=operator.id, site_id=site_a.id))
    device_a = Device(device_code="HTTP-DA", device_name="A", device_type="UPS", area_code="A", site_id=site_a.id)
    device_b = Device(device_code="HTTP-DB", device_name="B", device_type="UPS", area_code="B", site_id=site_b.id)
    device_none = Device(device_code="HTTP-DN", device_name="N", device_type="UPS", area_code="N", site_id=None)
    async_db.add_all([device_a, device_b, device_none])
    await async_db.flush()
    headers = auth_headers(token)

    listing = await client.get("/api/v1/devices", headers=headers)
    assert listing.status_code == 200
    assert [item["id"] for item in listing.json()["items"]] == [device_a.id]

    explicit = await client.get("/api/v1/devices", params={"site_id": site_b.id}, headers=headers)
    assert explicit.status_code == 403

    detail = await client.get(f"/api/v1/devices/{device_b.id}", headers=headers)
    missing = await client.get("/api/v1/devices/999999", headers=headers)
    assert detail.status_code == missing.status_code == 404

    create = await client.post(
        "/api/v1/devices",
        headers=headers,
        json={
            "device_code": "HTTP-D-CROSS",
            "device_name": "越权创建",
            "device_type": "UPS",
            "area_code": "B",
            "site_id": site_b.id,
        },
    )
    assert create.status_code == 403

    rebind = await client.put(f"/api/v1/devices/{device_a.id}", headers=headers, json={"site_id": site_b.id})
    assert rebind.status_code == 403
    await async_db.refresh(device_a)
    assert device_a.site_id == site_a.id


@pytest.mark.asyncio
async def test_point_http_matrix_uses_device_site(client, async_db, operator_user):
    operator, token = operator_user
    site_a = Site(site_code="HTTP-PA", site_name="点位授权站点")
    site_b = Site(site_code="HTTP-PB", site_name="点位越权站点")
    async_db.add_all([site_a, site_b])
    await async_db.flush()
    async_db.add(UserSite(user_id=operator.id, site_id=site_a.id))
    device_a = Device(device_code="HTTP-PA", device_name="A", device_type="UPS", area_code="A", site_id=site_a.id)
    device_b = Device(device_code="HTTP-PB", device_name="B", device_type="UPS", area_code="B", site_id=site_b.id)
    async_db.add_all([device_a, device_b])
    await async_db.flush()
    point_a = Point(
        point_code="HTTP-PA", point_name="A", point_type="AI", device_id=device_a.id, device_type="UPS", area_code="A"
    )
    point_b = Point(
        point_code="HTTP-PB", point_name="B", point_type="AI", device_id=device_b.id, device_type="UPS", area_code="B"
    )
    async_db.add_all([point_a, point_b])
    await async_db.flush()
    headers = auth_headers(token)

    listing = await client.get("/api/v1/points", headers=headers)
    assert listing.status_code == 200
    assert [item["id"] for item in listing.json()["items"]] == [point_a.id]

    detail = await client.get(f"/api/v1/points/{point_b.id}", headers=headers)
    assert detail.status_code == 404

    create = await client.post(
        "/api/v1/points",
        headers=headers,
        json={
            "point_code": "HTTP-P-CROSS",
            "point_name": "越权创建",
            "point_type": "AI",
            "device_id": device_b.id,
            "device_type": "UPS",
            "area_code": "B",
        },
    )
    assert create.status_code == 404

    rebind = await client.put(f"/api/v1/points/{point_a.id}", headers=headers, json={"device_id": device_b.id})
    assert rebind.status_code == 404
    await async_db.refresh(point_a)
    assert point_a.device_id == device_a.id

    enable = await client.put(f"/api/v1/points/{point_b.id}/enable", headers=headers)
    assert enable.status_code == 404


@pytest.mark.asyncio
async def test_alarm_http_matrix_scopes_aggregates_exports_and_batches(client, async_db, operator_user):
    operator, token = operator_user
    site_a = Site(site_code="HTTP-AA", site_name="告警授权站点")
    site_b = Site(site_code="HTTP-AB", site_name="告警越权站点")
    async_db.add_all([site_a, site_b])
    await async_db.flush()
    async_db.add(UserSite(user_id=operator.id, site_id=site_a.id))
    device_a = Device(device_code="HTTP-AA", device_name="A", device_type="UPS", area_code="A", site_id=site_a.id)
    device_b = Device(device_code="HTTP-AB", device_name="B", device_type="UPS", area_code="B", site_id=site_b.id)
    async_db.add_all([device_a, device_b])
    await async_db.flush()
    point_a = Point(
        point_code="HTTP-AA", point_name="A", point_type="AI", device_id=device_a.id, device_type="UPS", area_code="A"
    )
    point_b = Point(
        point_code="HTTP-AB", point_name="B", point_type="AI", device_id=device_b.id, device_type="UPS", area_code="B"
    )
    async_db.add_all([point_a, point_b])
    await async_db.flush()
    alarm_a = Alarm(
        alarm_no="HTTP-ALARM-A",
        point_id=point_a.id,
        alarm_level="major",
        alarm_type="threshold",
        alarm_message="A 站告警",
        status="active",
    )
    alarm_b = Alarm(
        alarm_no="HTTP-ALARM-B",
        point_id=point_b.id,
        alarm_level="critical",
        alarm_type="threshold",
        alarm_message="B 站告警",
        status="active",
    )
    async_db.add_all([alarm_a, alarm_b])
    await async_db.flush()
    headers = auth_headers(token)

    listing = await client.get("/api/v1/alarms", headers=headers)
    detail = await client.get(f"/api/v1/alarms/{alarm_b.id}", headers=headers)
    statistics = await client.get("/api/v1/alarms/statistics", headers=headers)
    exported = await client.get("/api/v1/alarms/export", headers=headers)
    mixed_batch = await client.put(
        "/api/v1/alarms/batch-acknowledge",
        headers=headers,
        json={"alarm_ids": [alarm_a.id, alarm_b.id], "remark": "不得部分确认"},
    )

    assert [item["id"] for item in listing.json()["items"]] == [alarm_a.id]
    assert detail.status_code == 404
    assert statistics.status_code == 200
    assert statistics.json()["total"] == 1
    assert exported.status_code == 200
    assert "HTTP-ALARM-A" in exported.text
    assert "HTTP-ALARM-B" not in exported.text
    assert mixed_batch.status_code == 404
    await async_db.refresh(alarm_a)
    assert alarm_a.status == "active"


@pytest.mark.asyncio
async def test_threshold_realtime_and_history_follow_point_site_scope(client, async_db, operator_user):
    operator, token = operator_user
    site_a = Site(site_code="HTTP-IRA", site_name="间接资源授权站点")
    site_b = Site(site_code="HTTP-IRB", site_name="间接资源越权站点")
    async_db.add_all([site_a, site_b])
    await async_db.flush()
    async_db.add(UserSite(user_id=operator.id, site_id=site_a.id))
    device_a = Device(device_code="HTTP-IRA", device_name="A", device_type="UPS", area_code="A", site_id=site_a.id)
    device_b = Device(device_code="HTTP-IRB", device_name="B", device_type="UPS", area_code="B", site_id=site_b.id)
    async_db.add_all([device_a, device_b])
    await async_db.flush()
    point_a = Point(
        point_code="HTTP-IRA", point_name="A", point_type="AI", device_id=device_a.id, device_type="UPS", area_code="A"
    )
    point_b = Point(
        point_code="HTTP-IRB", point_name="B", point_type="AI", device_id=device_b.id, device_type="UPS", area_code="B"
    )
    async_db.add_all([point_a, point_b])
    await async_db.flush()
    threshold_a = AlarmThreshold(
        point_id=point_a.id, threshold_type="high", threshold_value=80, alarm_level="major"
    )
    threshold_b = AlarmThreshold(
        point_id=point_b.id, threshold_type="high", threshold_value=90, alarm_level="critical"
    )
    async_db.add_all(
        [
            threshold_a,
            threshold_b,
            PointRealtime(point_id=point_a.id, value=10, status="normal"),
            PointRealtime(point_id=point_b.id, value=20, status="alarm"),
            PointHistory(point_id=point_a.id, value=10),
            PointHistory(point_id=point_b.id, value=20),
        ]
    )
    await async_db.flush()
    headers = auth_headers(token)

    thresholds = await client.get("/api/v1/thresholds", headers=headers)
    foreign_thresholds = await client.get(f"/api/v1/thresholds/point/{point_b.id}", headers=headers)
    foreign_update = await client.put(
        f"/api/v1/thresholds/{threshold_b.id}", headers=headers, json={"threshold_value": 99}
    )
    mixed_batch = await client.post(
        "/api/v1/thresholds/batch",
        headers=headers,
        json={
            "point_ids": [point_a.id, point_b.id],
            "threshold_type": "low",
            "threshold_value": 5,
            "alarm_level": "minor",
        },
    )
    realtime = await client.get("/api/v1/realtime", headers=headers)
    realtime_summary = await client.get("/api/v1/realtime/summary", headers=headers)
    foreign_realtime = await client.get(f"/api/v1/realtime/{point_b.id}", headers=headers)
    foreign_history = await client.get(f"/api/v1/history/{point_b.id}", headers=headers)
    mixed_compare = await client.get(
        "/api/v1/history/compare", headers=headers, params={"point_ids": f"{point_a.id},{point_b.id}"}
    )
    foreign_export = await client.get("/api/v1/history/export", headers=headers, params={"point_id": point_b.id})

    assert [item["id"] for item in thresholds.json()["items"]] == [threshold_a.id]
    assert foreign_thresholds.status_code == 404
    assert foreign_update.status_code == 404
    assert mixed_batch.status_code == 404
    assert [item["point_id"] for item in realtime.json()] == [point_a.id]
    assert realtime_summary.json()["total_points"] == 1
    assert foreign_realtime.status_code == 404
    assert foreign_history.status_code == 404
    assert mixed_compare.status_code == 404
    assert foreign_export.status_code == 404
    created_low = (
        await async_db.execute(
            select(AlarmThreshold).where(
                AlarmThreshold.point_id == point_a.id, AlarmThreshold.threshold_type == "low"
            )
        )
    ).scalar_one_or_none()
    assert created_low is None


@pytest.mark.asyncio
async def test_gateway_datasource_and_spatial_objects_are_site_isolated(client, async_db, operator_user):
    operator, token = operator_user
    site_a = Site(site_code="HTTP-GA", site_name="资源授权站点")
    site_b = Site(site_code="HTTP-GB", site_name="资源越权站点")
    async_db.add_all([site_a, site_b])
    await async_db.flush()
    async_db.add(UserSite(user_id=operator.id, site_id=site_a.id))
    gateway_b = Gateway(gateway_id="HTTP-GW-B", name="B 网关", site_id=site_b.id)
    datasource_b = DataSource(
        name="B 数据源", protocol_type="modbus_tcp", connection_config={"host": "127.0.0.1"}, site_id=site_b.id
    )
    floor_b = Floor(floor_code="HTTP-FB", floor_name="B 楼层", site_id=site_b.id)
    async_db.add_all([gateway_b, datasource_b, floor_b])
    await async_db.flush()
    headers = auth_headers(token)

    gateway_detail = await client.get(f"/api/v1/gateways/{gateway_b.id}", headers=headers)
    datasource_detail = await client.get(f"/api/v1/datasources/{datasource_b.id}", headers=headers)
    floor_update = await client.put(
        f"/api/v1/spatial/floors/{floor_b.id}", headers=headers, json={"floor_name": "泄漏"}
    )
    gateway_create = await client.post(
        "/api/v1/gateways",
        headers=headers,
        json={"gateway_id": "HTTP-GW-CROSS", "name": "越权网关", "site_id": site_b.id},
    )

    assert gateway_detail.status_code == 404
    assert datasource_detail.status_code == 404
    assert floor_update.status_code == 404
    assert gateway_create.status_code == 403


@pytest.mark.asyncio
async def test_cooling_objects_and_overview_follow_device_site_scope(client, async_db, operator_user):
    operator, token = operator_user
    site_a = Site(site_code="HTTP-CA", site_name="制冷授权站点")
    site_b = Site(site_code="HTTP-CB", site_name="制冷越权站点")
    async_db.add_all([site_a, site_b])
    await async_db.flush()
    async_db.add(UserSite(user_id=operator.id, site_id=site_a.id))

    device_a = Device(
        device_code="HTTP-CA", device_name="A 空调", device_type="AC", area_code="A", site_id=site_a.id, status="running"
    )
    device_b = Device(
        device_code="HTTP-CB", device_name="B 空调", device_type="AC", area_code="B", site_id=site_b.id, status="alarm"
    )
    async_db.add_all([device_a, device_b])
    await async_db.flush()
    group_a = CoolingGroup(group_name="A 群控", group_mode="linked")
    group_b = CoolingGroup(group_name="B 群控", group_mode="linked")
    unowned_group = CoolingGroup(group_name="未归属群控", group_mode="linked")
    async_db.add_all([group_a, group_b, unowned_group])
    await async_db.flush()
    unit_a = CoolingUnit(device_id=device_a.id, unit_type="indoor", group_id=group_a.id)
    unit_b = CoolingUnit(device_id=device_b.id, unit_type="indoor", group_id=group_b.id)
    aisle_a = ColdAisle(device_id=device_a.id, aisle_code="HTTP-CAA", aisle_name="A 通道")
    aisle_b = ColdAisle(device_id=device_b.id, aisle_code="HTTP-CAB", aisle_name="B 通道")
    async_db.add_all([unit_a, unit_b, aisle_a, aisle_b])
    await async_db.flush()
    headers = auth_headers(token)

    units = await client.get("/api/v1/cooling/units", headers=headers)
    foreign_unit = await client.get(f"/api/v1/cooling/units/{unit_b.id}", headers=headers)
    foreign_create = await client.post(
        "/api/v1/cooling/units", headers=headers, json={"device_id": device_b.id, "unit_type": "indoor"}
    )
    foreign_rebind = await client.put(
        f"/api/v1/cooling/units/{unit_a.id}", headers=headers, json={"device_id": device_b.id}
    )
    aisles = await client.get("/api/v1/cooling/cold-aisles", headers=headers)
    foreign_aisle = await client.get(f"/api/v1/cooling/cold-aisles/{aisle_b.id}", headers=headers)
    overview = await client.get("/api/v1/cooling/overview", headers=headers)
    global_groups = await client.get("/api/v1/cooling/groups", headers=headers)

    assert [item["id"] for item in units.json()["items"]] == [unit_a.id]
    assert foreign_unit.status_code == 404
    assert foreign_create.status_code == 404
    assert foreign_rebind.status_code == 404
    await async_db.refresh(unit_a)
    assert unit_a.device_id == device_a.id
    assert [item["id"] for item in aisles.json()["items"]] == [aisle_a.id]
    assert foreign_aisle.status_code == 404
    assert overview.status_code == 200
    assert overview.json()["ac_total"] == 1
    assert overview.json()["cold_aisle_total"] == 1
    assert overview.json()["group_total"] == 1
    assert global_groups.status_code == 403


@pytest.mark.asyncio
async def test_topology_config_and_precool_follow_trusted_site_relations(client, async_db, operator_user, monkeypatch):
    async def _skip_topology_publish(*_args, **_kwargs):
        return None

    async def _deployment_phase():
        return {"current_phase": 1}

    monkeypatch.setattr("app.api.v1.topology_config._publish_topology_update", _skip_topology_publish)
    monkeypatch.setattr(
        "app.services.precool.deployment_phase.deployment_phase_service.get_current_phase", _deployment_phase
    )
    operator, token = operator_user
    site_a = Site(site_code="HTTP-TCA", site_name="拓扑授权站点")
    site_b = Site(site_code="HTTP-TCB", site_name="拓扑越权站点")
    async_db.add_all([site_a, site_b])
    await async_db.flush()
    async_db.add(UserSite(user_id=operator.id, site_id=site_a.id))

    floor_a = Floor(floor_code="HTTP-TCA", floor_name="A 楼层", site_id=site_a.id)
    floor_b = Floor(floor_code="HTTP-TCB", floor_name="B 楼层", site_id=site_b.id)
    async_db.add_all([floor_a, floor_b])
    await async_db.flush()
    room_a = Room(room_code="HTTP-TCA", room_name="A 机房", floor_id=floor_a.id)
    room_b = Room(room_code="HTTP-TCB", room_name="B 机房", floor_id=floor_b.id)
    async_db.add_all([room_a, room_b])
    await async_db.flush()
    row_a = Row(row_code="HTTP-TCA", row_name="A 排", room_id=room_a.id)
    row_b = Row(row_code="HTTP-TCB", row_name="B 排", room_id=room_b.id)
    async_db.add_all([row_a, row_b])
    await async_db.flush()
    cabinet_a = Cabinet(cabinet_code="HTTP-TCA", cabinet_name="A 机柜", row_id=row_a.id, max_power=10)
    cabinet_b = Cabinet(cabinet_code="HTTP-TCB", cabinet_name="B 机柜", row_id=row_b.id, max_power=20)
    pdu_a = Device(device_code="HTTP-PDU-A", device_name="A PDU", device_type="PDU", area_code="A", site_id=site_a.id)
    pdu_b = Device(device_code="HTTP-PDU-B", device_name="B PDU", device_type="PDU", area_code="B", site_id=site_b.id)
    ac_a = Device(device_code="HTTP-AC-A", device_name="A AC", device_type="AC", area_code="A", site_id=site_a.id)
    ac_b = Device(device_code="HTTP-AC-B", device_name="B AC", device_type="AC", area_code="B", site_id=site_b.id)
    async_db.add_all([cabinet_a, cabinet_b, pdu_a, pdu_b, ac_a, ac_b])
    await async_db.flush()
    unit_a = CoolingUnit(device_id=ac_a.id)
    unit_b = CoolingUnit(device_id=ac_b.id)
    async_db.add_all([unit_a, unit_b])
    await async_db.flush()
    mapping_a = PowerPhaseMapping(cabinet_id=cabinet_a.id, pdu_device_id=pdu_a.id, phase="A", feed_type="primary")
    mapping_b = PowerPhaseMapping(cabinet_id=cabinet_b.id, pdu_device_id=pdu_b.id, phase="B", feed_type="primary")
    zone_a = CoolingZone(zone_code="HTTP-CZ-A", zone_name="A 制冷区", room_id=room_a.id, site_id=site_a.id)
    zone_b = CoolingZone(zone_code="HTTP-CZ-B", zone_name="B 制冷区", room_id=room_b.id, site_id=site_b.id)
    async_db.add_all([mapping_a, mapping_b, zone_a, zone_b])
    await async_db.flush()
    async_db.add_all(
        [
            CoolingZoneCabinet(zone_id=zone_a.id, cabinet_id=cabinet_a.id),
            CoolingZoneCabinet(zone_id=zone_b.id, cabinet_id=cabinet_b.id),
            CoolingZoneUnit(zone_id=zone_a.id, cooling_unit_id=unit_a.id),
            CoolingZoneUnit(zone_id=zone_b.id, cooling_unit_id=unit_b.id),
            RollbackEvent(
                zone_id=zone_a.id,
                trigger_type="sensor_offline",
                action="restore",
                status="resolved",
            ),
            RollbackEvent(
                zone_id=zone_b.id,
                trigger_type="sensor_offline",
                action="restore",
                status="resolved",
            ),
        ]
    )
    foreign_schedule = PrecoolSchedule(
        cooling_zone_id=zone_b.id,
        schedule_date=date.today(),
        precool_start_time=time(1, 0),
        precool_end_time=time(2, 0),
        target_temp=18,
        peak_start_time=time(10, 0),
        peak_end_time=time(11, 0),
        status="pending",
    )
    async_db.add(foreign_schedule)
    await async_db.flush()
    headers = auth_headers(token)

    mappings = await client.get("/api/v1/topology-config/power-phase", headers=headers)
    foreign_mapping = await client.put(
        f"/api/v1/topology-config/power-phase/{mapping_b.id}", headers=headers, json={"phase": "C"}
    )
    mixed_mapping = await client.post(
        "/api/v1/topology-config/power-phase",
        headers=headers,
        json={"cabinet_id": cabinet_a.id, "pdu_device_id": pdu_b.id, "phase": "C", "feed_type": "backup"},
    )
    zones = await client.get("/api/v1/topology-config/cooling-zones", headers=headers)
    foreign_zone = await client.get(f"/api/v1/topology-config/cooling-zones/{zone_b.id}", headers=headers)
    site_selection = await client.post(
        "/api/v1/topology-config/smart-site-selection", headers=headers, json={"required_u": 1}
    )
    foreign_fault = await client.post(
        "/api/v1/topology-config/fault-impact-analysis",
        headers=headers,
        json={"fault_source_type": "pdu", "fault_source_id": pdu_b.id},
    )
    before_zone_count = (await async_db.execute(select(CoolingZone))).scalars().all()
    mixed_zone = await client.post(
        "/api/v1/topology-config/cooling-zones",
        headers=headers,
        json={"zone_name": "不得创建", "room_id": room_a.id, "cabinet_ids": [cabinet_a.id, cabinet_b.id]},
    )
    after_zone_count = (await async_db.execute(select(CoolingZone))).scalars().all()
    foreign_rebind = await client.put(
        f"/api/v1/topology-config/cooling-zones/{zone_a.id}", headers=headers, json={"room_id": room_b.id}
    )
    foreign_config = await client.get(f"/api/v1/precool/zones/{zone_b.id}/config", headers=headers)
    foreign_schedule_detail = await client.get(
        f"/api/v1/precool/schedules/{foreign_schedule.id}", headers=headers
    )
    rollback_overview = await client.get("/api/v1/precool/rollback-overview", headers=headers)
    global_phase = await client.get("/api/v1/precool/deployment-phase", headers=headers)

    assert [item["id"] for item in mappings.json()] == [mapping_a.id]
    assert foreign_mapping.status_code == 404
    assert mixed_mapping.status_code == 404
    assert [item["id"] for item in zones.json()] == [zone_a.id]
    assert foreign_zone.status_code == 404
    assert site_selection.status_code == 200
    assert site_selection.json()["total_evaluated"] == 1
    assert [item["cabinet_id"] for item in site_selection.json()["candidates"]] == [cabinet_a.id]
    assert foreign_fault.status_code == 404
    assert mixed_zone.status_code == 404
    assert len(after_zone_count) == len(before_zone_count)
    assert foreign_rebind.status_code == 404
    await async_db.refresh(zone_a)
    assert zone_a.room_id == room_a.id
    assert foreign_config.status_code == 404
    assert foreign_schedule_detail.status_code == 404
    assert rollback_overview.status_code == 200
    assert rollback_overview.json()["data"]["total_zones"] == 1
    assert rollback_overview.json()["data"]["recent_events_24h"] == 1
    assert global_phase.status_code == 403


@pytest.mark.asyncio
async def test_power_objects_and_aggregates_follow_device_site_scope(client, async_db, operator_user):
    operator, token = operator_user
    site_a = Site(site_code="HTTP-PA", site_name="Power authorized site")
    site_b = Site(site_code="HTTP-PB", site_name="Power foreign site")
    async_db.add_all([site_a, site_b])
    await async_db.flush()
    async_db.add(UserSite(user_id=operator.id, site_id=site_a.id))

    ups_device_a = Device(
        device_code="HTTP-UPS-A", device_name="A UPS", device_type="UPS", area_code="A", site_id=site_a.id
    )
    ups_device_b = Device(
        device_code="HTTP-UPS-B", device_name="B UPS", device_type="UPS", area_code="B", site_id=site_b.id
    )
    ups_device_none = Device(
        device_code="HTTP-UPS-N", device_name="Unowned UPS", device_type="UPS", area_code="N", site_id=None
    )
    cabinet_a = Device(
        device_code="HTTP-CAB-A", device_name="A cabinet", device_type="CABINET", area_code="A", site_id=site_a.id
    )
    cabinet_b = Device(
        device_code="HTTP-CAB-B", device_name="B cabinet", device_type="CABINET", area_code="B", site_id=site_b.id
    )
    pdu_a = Device(
        device_code="HTTP-PWR-PDU-A", device_name="A PDU", device_type="PDU", area_code="A", site_id=site_a.id
    )
    pdu_b = Device(
        device_code="HTTP-PWR-PDU-B", device_name="B PDU", device_type="PDU", area_code="B", site_id=site_b.id
    )
    async_db.add_all([ups_device_a, ups_device_b, ups_device_none, cabinet_a, cabinet_b, pdu_a, pdu_b])
    await async_db.flush()

    ups_a = UPSDevice(device_id=ups_device_a.id, ups_type="standalone")
    ups_b = UPSDevice(device_id=ups_device_b.id, ups_type="modular")
    ups_none = UPSDevice(device_id=ups_device_none.id, ups_type="standalone")
    async_db.add_all([ups_a, ups_b, ups_none])
    await async_db.flush()
    battery_a = BatteryGroup(ups_device_id=ups_a.id, group_name="A battery")
    battery_b = BatteryGroup(ups_device_id=ups_b.id, group_name="B battery")
    battery_none = BatteryGroup(ups_device_id=ups_none.id, group_name="Unowned battery")
    power_a = PowerDevice(
        device_code="HTTP-PD-A", device_name="A power device", device_type="PDU", monitor_device_id=pdu_a.id
    )
    power_b = PowerDevice(
        device_code="HTTP-PD-B", device_name="B power device", device_type="PDU", monitor_device_id=pdu_b.id
    )
    power_none = PowerDevice(
        device_code="HTTP-PD-N", device_name="Unowned power device", device_type="PDU", monitor_device_id=None
    )
    async_db.add_all([battery_a, battery_b, battery_none, power_a, power_b, power_none])
    await async_db.flush()
    headers = auth_headers(token)

    ups_list = await client.get("/api/v1/power/ups", headers=headers)
    foreign_ups = await client.get(f"/api/v1/power/ups/{ups_b.id}", headers=headers)
    unowned_ups = await client.get(f"/api/v1/power/ups/{ups_none.id}", headers=headers)
    foreign_ups_create = await client.post(
        "/api/v1/power/ups", headers=headers, json={"device_id": ups_device_b.id, "ups_type": "standalone"}
    )
    foreign_ups_update = await client.put(
        f"/api/v1/power/ups/{ups_b.id}", headers=headers, json={"description": "must not change"}
    )
    battery_list = await client.get("/api/v1/power/batteries", headers=headers)
    foreign_battery = await client.get(f"/api/v1/power/batteries/{battery_b.id}", headers=headers)
    foreign_battery_create = await client.post(
        "/api/v1/power/batteries",
        headers=headers,
        json={"ups_device_id": ups_b.id, "group_name": "must not create"},
    )
    foreign_battery_update = await client.put(
        f"/api/v1/power/batteries/{battery_b.id}", headers=headers, json={"group_name": "must not change"}
    )
    cabinets = await client.get("/api/v1/power/cabinets", headers=headers)
    foreign_branches = await client.get(f"/api/v1/power/cabinets/{cabinet_b.id}/branches", headers=headers)
    pdus = await client.get("/api/v1/power/pdus", headers=headers)
    overview = await client.get("/api/v1/power/overview", headers=headers)
    redundancy_a = await client.get(f"/api/v1/power/devices/{power_a.id}/redundancy", headers=headers)
    redundancy_b = await client.get(f"/api/v1/power/devices/{power_b.id}/redundancy", headers=headers)
    redundancy_none = await client.get(f"/api/v1/power/devices/{power_none.id}/redundancy", headers=headers)

    assert [item["id"] for item in ups_list.json()["items"]] == [ups_a.id]
    assert foreign_ups.status_code == 404
    assert unowned_ups.status_code == 404
    assert foreign_ups_create.status_code == 404
    assert foreign_ups_update.status_code == 404
    await async_db.refresh(ups_b)
    assert ups_b.description is None
    assert [item["id"] for item in battery_list.json()["items"]] == [battery_a.id]
    assert foreign_battery.status_code == 404
    assert foreign_battery_create.status_code == 404
    assert foreign_battery_update.status_code == 404
    await async_db.refresh(battery_b)
    assert battery_b.group_name == "B battery"
    assert [item["device"]["id"] for item in cabinets.json()["items"]] == [cabinet_a.id]
    assert foreign_branches.status_code == 404
    assert [item["device"]["id"] for item in pdus.json()["items"]] == [pdu_a.id]
    assert overview.status_code == 200
    assert overview.json()["ups_total"] == 1
    assert overview.json()["battery_total"] == 1
    assert overview.json()["cabinet_total"] == 1
    assert overview.json()["pdu_total"] == 1
    assert redundancy_a.status_code == 200
    assert redundancy_b.status_code == 404
    assert redundancy_none.status_code == 404


@pytest.mark.asyncio
async def test_statistics_aggregates_follow_point_device_site_scope(client, async_db, operator_user):
    operator, token = operator_user
    site_a = Site(site_code="HTTP-SA", site_name="Statistics authorized site")
    site_b = Site(site_code="HTTP-SB", site_name="Statistics foreign site")
    async_db.add_all([site_a, site_b])
    await async_db.flush()
    async_db.add(UserSite(user_id=operator.id, site_id=site_a.id))
    device_a = Device(
        device_code="HTTP-STAT-A",
        device_name="A statistics device",
        device_type="PDU",
        area_code="A",
        site_id=site_a.id,
        status="online",
    )
    device_b = Device(
        device_code="HTTP-STAT-B",
        device_name="B statistics device",
        device_type="PDU",
        area_code="B",
        site_id=site_b.id,
        status="offline",
    )
    async_db.add_all([device_a, device_b])
    await async_db.flush()
    point_a = Point(
        point_code="HTTP-STAT-PA",
        point_name="A功率",
        point_type="AI",
        device_id=device_a.id,
        device_type="PDU",
        area_code="A",
        unit="kW",
    )
    point_b = Point(
        point_code="HTTP-STAT-PB",
        point_name="B功率",
        point_type="AI",
        device_id=device_b.id,
        device_type="PDU",
        area_code="B",
        unit="kW",
    )
    async_db.add_all([point_a, point_b])
    await async_db.flush()
    now = datetime.now()
    async_db.add_all(
        [
            PointRealtime(point_id=point_a.id, value=10, status="normal"),
            PointRealtime(point_id=point_b.id, value=20, status="alarm"),
            PointHistory(point_id=point_a.id, value=10, recorded_at=now),
            PointHistory(point_id=point_b.id, value=20, recorded_at=now),
            Alarm(
                alarm_no="HTTP-STAT-AA",
                point_id=point_a.id,
                alarm_level="minor",
                alarm_message="A active alarm",
                status="active",
                created_at=now,
            ),
            Alarm(
                alarm_no="HTTP-STAT-AR",
                point_id=point_a.id,
                alarm_level="major",
                alarm_message="A resolved alarm",
                status="resolved",
                duration_seconds=60,
                created_at=now,
            ),
            Alarm(
                alarm_no="HTTP-STAT-BA",
                point_id=point_b.id,
                alarm_level="critical",
                alarm_message="B active alarm",
                status="active",
                created_at=now,
            ),
            Alarm(
                alarm_no="HTTP-STAT-BR",
                point_id=point_b.id,
                alarm_level="critical",
                alarm_message="B resolved alarm",
                status="resolved",
                duration_seconds=120,
                created_at=now,
            ),
            Alarm(
                alarm_no="HTTP-STAT-UNOWNED",
                point_id=None,
                alarm_level="critical",
                alarm_message="Unowned alarm",
                status="active",
                created_at=now,
            ),
        ]
    )
    await async_db.flush()
    headers = auth_headers(token)

    overview = await client.get("/api/v1/statistics/overview", headers=headers)
    points = await client.get("/api/v1/statistics/points", headers=headers)
    alarms = await client.get("/api/v1/statistics/alarms", headers=headers)
    energy = await client.get("/api/v1/statistics/energy", headers=headers)
    availability = await client.get("/api/v1/statistics/availability", headers=headers)
    comparison = await client.get("/api/v1/statistics/comparison", params={"metric": "alarm"}, headers=headers)

    assert overview.status_code == 200
    assert overview.json()["points"] == {"total": 1, "enabled": 1, "disabled": 0}
    assert overview.json()["devices"] == {"total": 1, "online": 1, "offline": 0}
    assert overview.json()["alarms"] == {"active": 1, "today": 2}
    assert overview.json()["realtime"] == {"normal": 1}
    assert points.json()["by_area"] == {"A": 1}
    assert points.json()["by_status"] == {"normal": 1}
    assert alarms.json()["by_level"] == {"major": 1, "minor": 1}
    assert alarms.json()["by_status"] == {"active": 1, "resolved": 1}
    assert [item["point_id"] for item in alarms.json()["top_alarm_points"]] == [point_a.id]
    assert [item["point_code"] for item in energy.json()["power_points"]] == [point_a.point_code]
    assert availability.json()["total_alarm_duration_seconds"] == 60
    assert comparison.json()["this_week"] == 2
    assert comparison.json()["this_month"] == 2


@pytest.mark.asyncio
async def test_report_globals_are_admin_only_and_device_health_is_site_scoped(client, async_db, operator_user):
    operator, token = operator_user
    site_a = Site(site_code="HTTP-RA", site_name="Report authorized site")
    site_b = Site(site_code="HTTP-RB", site_name="Report foreign site")
    async_db.add_all([site_a, site_b])
    await async_db.flush()
    async_db.add(UserSite(user_id=operator.id, site_id=site_a.id))
    device_a = Device(
        device_code="HTTP-REPORT-A", device_name="A report device", device_type="UPS", area_code="A", site_id=site_a.id
    )
    device_b = Device(
        device_code="HTTP-REPORT-B", device_name="B report device", device_type="UPS", area_code="B", site_id=site_b.id
    )
    async_db.add_all([device_a, device_b])
    await async_db.flush()
    template = ReportTemplate(template_name="Global template", template_type="daily", created_by=operator.id)
    record = ReportRecord(
        report_name="Global record",
        report_type="daily",
        start_time=datetime.now() - timedelta(days=1),
        end_time=datetime.now(),
        status="completed",
        report_data="{}",
        generated_by=operator.id,
    )
    schedule = ReportSchedule(name="Global schedule", report_type="daily", created_by=operator.id)
    foreign_health = DeviceHealthScore(
        device_id=device_b.id,
        device_name=device_b.device_name,
        device_type=device_b.device_type,
        score=55,
        health_level="warning",
    )
    async_db.add_all([template, record, schedule, foreign_health])
    await async_db.flush()
    headers = auth_headers(token)

    global_responses = [
        await client.get("/api/v1/reports/templates", headers=headers),
        await client.post(
            "/api/v1/reports/templates",
            headers=headers,
            json={"template_name": "must not create", "template_type": "daily"},
        ),
        await client.get("/api/v1/reports/records", headers=headers),
        await client.get(f"/api/v1/reports/download/{record.id}", headers=headers),
        await client.get("/api/v1/reports/daily", headers=headers),
        await client.get("/api/v1/reports/weekly", headers=headers),
        await client.get("/api/v1/reports/monthly", headers=headers),
        await client.post("/api/v1/reports/auto-generate", headers=headers, json={"report_type": "daily"}),
        await client.get("/api/v1/reports/schedules", headers=headers),
        await client.post(
            "/api/v1/reports/schedules", headers=headers, json={"name": "must not create", "report_type": "daily"}
        ),
        await client.get("/api/v1/reports/summary-panel", headers=headers),
        await client.get(f"/api/v1/reports/auto-report-pdf/{record.id}", headers=headers),
    ]
    calculate = await client.post("/api/v1/reports/device-health/calculate", headers=headers)
    health_list = await client.get("/api/v1/reports/device-health", headers=headers)
    foreign_detail = await client.get(f"/api/v1/reports/device-health/{device_b.id}", headers=headers)

    assert all(response.status_code == 403 for response in global_responses)
    assert calculate.status_code == 200
    assert calculate.json()["total_devices"] == 1
    assert [item["device_id"] for item in health_list.json()] == [device_a.id]
    assert foreign_detail.status_code == 404
    persisted_foreign = await async_db.get(DeviceHealthScore, foreign_health.id)
    assert persisted_foreign is not None
    assert persisted_foreign.score == 55


@pytest.mark.asyncio
async def test_video_cameras_actions_and_playback_follow_trusted_site_relations(client, async_db, operator_user):
    operator, token = operator_user
    site_a = Site(site_code="HTTP-VA", site_name="Video authorized site")
    site_b = Site(site_code="HTTP-VB", site_name="Video foreign site")
    async_db.add_all([site_a, site_b])
    await async_db.flush()
    async_db.add(UserSite(user_id=operator.id, site_id=site_a.id))
    floor_a = Floor(floor_code="HTTP-VFA", floor_name="A video floor", site_id=site_a.id)
    floor_b = Floor(floor_code="HTTP-VFB", floor_name="B video floor", site_id=site_b.id)
    async_db.add_all([floor_a, floor_b])
    await async_db.flush()
    room_a = Room(room_code="HTTP-VRA", room_name="A video room", floor_id=floor_a.id)
    room_b = Room(room_code="HTTP-VRB", room_name="B video room", floor_id=floor_b.id)
    async_db.add_all([room_a, room_b])
    await async_db.flush()
    row_a = Row(row_code="HTTP-VROWA", row_name="A video row", room_id=room_a.id)
    row_b = Row(row_code="HTTP-VROWB", row_name="B video row", room_id=room_b.id)
    async_db.add_all([row_a, row_b])
    await async_db.flush()
    cabinet_a = Cabinet(cabinet_code="HTTP-VCA", cabinet_name="A video cabinet", row_id=row_a.id)
    cabinet_b = Cabinet(cabinet_code="HTTP-VCB", cabinet_name="B video cabinet", row_id=row_b.id)
    device_a = Device(
        device_code="HTTP-VIDEO-A", device_name="A video device", device_type="PDU", area_code="SHARED", site_id=site_a.id
    )
    device_b = Device(
        device_code="HTTP-VIDEO-B", device_name="B video device", device_type="PDU", area_code="SHARED", site_id=site_b.id
    )
    async_db.add_all([cabinet_a, cabinet_b, device_a, device_b])
    await async_db.flush()
    point_a = Point(
        point_code="HTTP-VIDEO-PA",
        point_name="A video point",
        point_type="DI",
        device_id=device_a.id,
        area_code="SHARED",
    )
    point_b = Point(
        point_code="HTTP-VIDEO-PB",
        point_name="B video point",
        point_type="DI",
        device_id=device_b.id,
        area_code="SHARED",
    )
    async_db.add_all([point_a, point_b])
    await async_db.flush()
    alarm_a = Alarm(
        alarm_no="HTTP-VIDEO-AA",
        point_id=point_a.id,
        alarm_level="major",
        alarm_message="A video alarm",
        status="active",
    )
    alarm_b = Alarm(
        alarm_no="HTTP-VIDEO-AB",
        point_id=point_b.id,
        alarm_level="major",
        alarm_message="B video alarm",
        status="active",
    )
    nvr = NVR(name="Global NVR", ip_address="127.0.0.10")
    async_db.add_all([alarm_a, alarm_b, nvr])
    await async_db.flush()
    camera_a = Camera(name="A camera", code="HTTP-CAM-A", device_id=device_a.id, area_code="SHARED")
    camera_b = Camera(name="B camera", code="HTTP-CAM-B", cabinet_id=cabinet_b.id, area_code="SHARED")
    camera_none = Camera(name="Unowned camera", code="HTTP-CAM-N", nvr_id=nvr.id, area_code="SHARED")
    async_db.add_all([camera_a, camera_b, camera_none])
    await async_db.flush()
    event_a = VideoEvent(camera_id=camera_a.id, event_type="recording_start", trigger_source="manual")
    event_b = VideoEvent(camera_id=camera_b.id, event_type="recording_start", trigger_source="manual")
    async_db.add_all([event_a, event_b])
    await async_db.flush()
    headers = auth_headers(token)

    nvr_list = await client.get("/api/v1/video/nvrs", headers=headers)
    nvr_detail = await client.get(f"/api/v1/video/nvrs/{nvr.id}", headers=headers)
    cameras = await client.get("/api/v1/video/cameras", headers=headers)
    foreign_camera = await client.get(f"/api/v1/video/cameras/{camera_b.id}", headers=headers)
    unowned_camera = await client.get(f"/api/v1/video/cameras/{camera_none.id}", headers=headers)
    shared_area = await client.get("/api/v1/video/cameras/by-area/SHARED", headers=headers)
    foreign_device = await client.get(f"/api/v1/video/cameras/by-device/{device_b.id}", headers=headers)
    authorized_alarm = await client.get(f"/api/v1/video/cameras/by-alarm/{alarm_a.id}", headers=headers)
    foreign_alarm = await client.get(f"/api/v1/video/cameras/by-alarm/{alarm_b.id}", headers=headers)
    before_events = (await async_db.execute(select(VideoEvent))).scalars().all()
    foreign_ptz = await client.post(
        "/api/v1/video/ptz/control",
        headers=headers,
        json={"camera_id": camera_b.id, "action": "left", "speed": 5},
    )
    foreign_recording = await client.post(
        "/api/v1/video/recording/start", headers=headers, json={"camera_id": camera_b.id}
    )
    after_events = (await async_db.execute(select(VideoEvent))).scalars().all()
    events = await client.get("/api/v1/video/events", headers=headers)
    foreign_playback = await client.get(f"/api/v1/video/playback/alarm/{alarm_b.id}", headers=headers)
    foreign_segments = await client.get(
        "/api/v1/video/playback/segments", headers=headers, params={"camera_id": camera_b.id}
    )

    assert nvr_list.status_code == 403
    assert nvr_detail.status_code == 403
    assert [item["id"] for item in cameras.json()["items"]] == [camera_a.id]
    assert foreign_camera.status_code == 404
    assert unowned_camera.status_code == 404
    assert [item["id"] for item in shared_area.json()] == [camera_a.id]
    assert foreign_device.status_code == 404
    assert [item["id"] for item in authorized_alarm.json()] == [camera_a.id]
    assert foreign_alarm.status_code == 404
    assert foreign_ptz.status_code == 404
    assert foreign_recording.status_code == 404
    assert len(after_events) == len(before_events)
    assert [item["id"] for item in events.json()["items"]] == [event_a.id]
    assert foreign_playback.status_code == 404
    assert foreign_segments.status_code == 404


@pytest.mark.asyncio
async def test_ota_packages_and_tasks_follow_full_gateway_site_scope(
    client, async_db, operator_user, admin_user, monkeypatch
):
    operator, operator_token = operator_user
    _, admin_token = admin_user
    site_a = Site(site_code="HTTP-OTA-A", site_name="OTA authorized site")
    site_b = Site(site_code="HTTP-OTA-B", site_name="OTA foreign site")
    async_db.add_all([site_a, site_b])
    await async_db.flush()
    async_db.add(UserSite(user_id=operator.id, site_id=site_a.id))
    gateway_a = Gateway(
        gateway_id="HTTP-OTA-GW-A", name="OTA gateway A", version="1.0.0", status="online", site_id=site_a.id
    )
    gateway_b = Gateway(
        gateway_id="HTTP-OTA-GW-B", name="OTA gateway B", version="1.0.0", status="online", site_id=site_b.id
    )
    gateway_none = Gateway(
        gateway_id="HTTP-OTA-GW-N", name="OTA unowned gateway", version="1.0.0", status="online", site_id=None
    )
    firmware = FirmwarePackage(
        version="39.1.0",
        filename="gateway-39.1.0.bin",
        file_size=1024,
        checksum_sha256="9" * 64,
        download_url="https://firmware.example.com/gateway-39.1.0.bin",
        is_active=True,
    )
    async_db.add_all([gateway_a, gateway_b, gateway_none, firmware])
    await async_db.flush()

    task_a = OtaTask(
        task_id="HTTP-OTA-TASK-A",
        firmware_id=firmware.id,
        target_version=firmware.version,
        status="pending",
        total_gateways=1,
    )
    task_b = OtaTask(
        task_id="HTTP-OTA-TASK-B",
        firmware_id=firmware.id,
        target_version=firmware.version,
        status="pending",
        total_gateways=1,
    )
    task_mixed = OtaTask(
        task_id="HTTP-OTA-TASK-MIXED",
        firmware_id=firmware.id,
        target_version=firmware.version,
        status="pending",
        total_gateways=2,
    )
    task_none = OtaTask(
        task_id="HTTP-OTA-TASK-NONE",
        firmware_id=firmware.id,
        target_version=firmware.version,
        status="pending",
        total_gateways=1,
    )
    async_db.add_all([task_a, task_b, task_mixed, task_none])
    async_db.add_all(
        [
            OtaTaskGateway(task_id=task_a.task_id, gateway_id=gateway_a.gateway_id),
            OtaTaskGateway(task_id=task_b.task_id, gateway_id=gateway_b.gateway_id),
            OtaTaskGateway(task_id=task_mixed.task_id, gateway_id=gateway_a.gateway_id),
            OtaTaskGateway(task_id=task_mixed.task_id, gateway_id=gateway_b.gateway_id),
            OtaTaskGateway(task_id=task_none.task_id, gateway_id=gateway_none.gateway_id),
        ]
    )
    await async_db.flush()
    operator_headers = auth_headers(operator_token)
    admin_headers = auth_headers(admin_token)

    operator_firmware = await client.get("/api/v1/ota/firmware", headers=operator_headers)
    admin_firmware = await client.get("/api/v1/ota/firmware", headers=admin_headers)
    assert operator_firmware.status_code == 403
    assert admin_firmware.status_code == 200

    initial_task_count = (await async_db.execute(select(OtaTask))).scalars().all()
    foreign_create = await client.post(
        "/api/v1/ota/tasks",
        headers=operator_headers,
        json={"firmware_id": firmware.id, "gateway_ids": [gateway_b.id], "strategy": "immediate"},
    )
    mixed_create = await client.post(
        "/api/v1/ota/tasks",
        headers=operator_headers,
        json={
            "firmware_id": firmware.id,
            "gateway_ids": [gateway_a.id, gateway_b.id],
            "strategy": "immediate",
        },
    )
    after_rejected_count = (await async_db.execute(select(OtaTask))).scalars().all()
    assert foreign_create.status_code == 404
    assert mixed_create.status_code == 404
    assert len(after_rejected_count) == len(initial_task_count)

    authorized_create = await client.post(
        "/api/v1/ota/tasks",
        headers=operator_headers,
        json={"firmware_id": firmware.id, "gateway_ids": [gateway_a.id], "strategy": "immediate"},
    )
    assert authorized_create.status_code == 200
    created_task_id = authorized_create.json()["task_id"]

    listing = await client.get("/api/v1/ota/tasks", headers=operator_headers)
    detail = await client.get(f"/api/v1/ota/tasks/{task_a.task_id}", headers=operator_headers)
    foreign_detail = await client.get(f"/api/v1/ota/tasks/{task_b.task_id}", headers=operator_headers)
    mixed_detail = await client.get(f"/api/v1/ota/tasks/{task_mixed.task_id}", headers=operator_headers)
    missing_detail = await client.get("/api/v1/ota/tasks/HTTP-OTA-MISSING", headers=operator_headers)
    assert {item["task_id"] for item in listing.json()["items"]} == {task_a.task_id, created_task_id}
    assert detail.status_code == 200
    assert foreign_detail.status_code == mixed_detail.status_code == missing_detail.status_code == 404

    from app.mqtt import mqtt_service

    publish = AsyncMock()
    monkeypatch.setattr(mqtt_service, "publish", publish)
    foreign_start = await client.post(f"/api/v1/ota/tasks/{task_b.task_id}/start", headers=operator_headers)
    mixed_start = await client.post(f"/api/v1/ota/tasks/{task_mixed.task_id}/start", headers=operator_headers)
    assert foreign_start.status_code == mixed_start.status_code == 404
    publish.assert_not_awaited()
    await async_db.refresh(task_b)
    await async_db.refresh(task_mixed)
    assert task_b.status == task_mixed.status == "pending"


@pytest.mark.asyncio
async def test_data_quality_floor_map_and_predictive_maintenance_authorization(
    client, async_db, operator_user, admin_user
):
    operator, operator_token = operator_user
    _, admin_token = admin_user
    site_a = Site(site_code="HTTP-DQ-A", site_name="Quality authorized site")
    site_b = Site(site_code="HTTP-DQ-B", site_name="Quality foreign site")
    async_db.add_all([site_a, site_b])
    await async_db.flush()
    async_db.add(UserSite(user_id=operator.id, site_id=site_a.id))
    device_a = Device(
        device_code="HTTP-DQ-DA", device_name="Quality A", device_type="UPS", area_code="A", site_id=site_a.id
    )
    device_b = Device(
        device_code="HTTP-DQ-DB", device_name="Quality B", device_type="UPS", area_code="B", site_id=site_b.id
    )
    async_db.add_all([device_a, device_b])
    await async_db.flush()
    point_a = Point(point_code="HTTP-DQ-PA", point_name="Quality A", point_type="AI", device_id=device_a.id)
    point_b = Point(point_code="HTTP-DQ-PB", point_name="Quality B", point_type="AI", device_id=device_b.id)
    point_none = Point(point_code="HTTP-DQ-PN", point_name="Quality unowned", point_type="AI")
    async_db.add_all([point_a, point_b, point_none])
    await async_db.flush()
    async_db.add_all(
        [
            PointRealtime(point_id=point_a.id, value=1, quality=2, status="offline"),
            PointRealtime(point_id=point_b.id, value=2, quality=1, status="normal"),
            PointRealtime(point_id=point_none.id, value=3, quality=0, status="normal"),
            DeviceHealthScore(
                device_id=device_a.id,
                device_name=device_a.device_name,
                device_type=device_a.device_type,
                score=90,
                health_level="健康",
            ),
            DeviceHealthScore(
                device_id=device_b.id,
                device_name=device_b.device_name,
                device_type=device_b.device_type,
                score=50,
                health_level="危险",
            ),
        ]
    )
    advice_a = MaintenanceAdvice(device_id=device_a.id, device_name=device_a.device_name, status="pending")
    advice_b = MaintenanceAdvice(device_id=device_b.id, device_name=device_b.device_name, status="pending")
    floor_map = FloorMap(
        floor_code="F39",
        floor_name="Global floor map",
        map_type="2d",
        map_data="{}",
        is_default=False,
    )
    async_db.add_all([advice_a, advice_b, floor_map])
    await async_db.flush()
    operator_headers = auth_headers(operator_token)
    admin_headers = auth_headers(admin_token)

    quality_status = await client.get("/api/v1/data-quality/status", headers=operator_headers)
    quality_points = await client.get("/api/v1/data-quality/points", headers=operator_headers)
    operator_floor_maps = await client.get("/api/v1/floor-map/floors", headers=operator_headers)
    admin_floor_maps = await client.get("/api/v1/floor-map/floors", headers=admin_headers)
    dashboard = await client.get("/api/v1/predictive-maintenance/dashboard", headers=operator_headers)
    foreign_site = await client.get(
        "/api/v1/predictive-maintenance/dashboard", params={"site_id": site_b.id}, headers=operator_headers
    )
    advices = await client.get("/api/v1/predictive-maintenance/advices", headers=operator_headers)
    foreign_device = await client.get(
        f"/api/v1/predictive-maintenance/devices/{device_b.id}/detail", headers=operator_headers
    )
    foreign_advice = await client.get(
        f"/api/v1/predictive-maintenance/advices/{advice_b.id}", headers=operator_headers
    )
    foreign_reject = await client.post(
        f"/api/v1/predictive-maintenance/advices/{advice_b.id}/reject",
        headers=operator_headers,
        json={"feedback": "cross-site rejection"},
    )

    assert quality_status.status_code == 200
    assert quality_status.json()["total"] == 1
    assert quality_status.json()["unreliable_count"] == 1
    assert [item["point_id"] for item in quality_points.json()] == [point_a.id]
    assert operator_floor_maps.status_code == 403
    assert admin_floor_maps.status_code == 200
    assert dashboard.json()["summary"]["total"] == 1
    assert [item["device_id"] for item in dashboard.json()["devices"]] == [device_a.id]
    assert foreign_site.status_code == 403
    assert [item["id"] for item in advices.json()] == [advice_a.id]
    assert foreign_device.status_code == foreign_advice.status_code == foreign_reject.status_code == 404
    await async_db.refresh(advice_b)
    assert advice_b.status == "pending"


@pytest.mark.asyncio
async def test_command_and_drift_routes_follow_device_and_point_site_scope(
    client, async_db, operator_user, monkeypatch
):
    operator, token = operator_user
    site_a = Site(site_code="HTTP-CD-A", site_name="Command authorized site")
    site_b = Site(site_code="HTTP-CD-B", site_name="Command foreign site")
    async_db.add_all([site_a, site_b])
    await async_db.flush()
    async_db.add(UserSite(user_id=operator.id, site_id=site_a.id))
    device_a = Device(
        device_code="HTTP-CD-DA", device_name="Command A", device_type="UPS", area_code="A", site_id=site_a.id
    )
    device_b = Device(
        device_code="HTTP-CD-DB", device_name="Command B", device_type="UPS", area_code="B", site_id=site_b.id
    )
    async_db.add_all([device_a, device_b])
    await async_db.flush()
    point_a = Point(point_code="HTTP-CD-PA", point_name="Drift A", point_type="AI", device_id=device_a.id)
    point_b = Point(point_code="HTTP-CD-PB", point_name="Drift B", point_type="AI", device_id=device_b.id)
    async_db.add_all([point_a, point_b])
    await async_db.flush()
    approval_a = CommandApproval(
        command_type="power_off",
        risk_level="critical",
        target_device_id=device_a.id,
        target_device_name=device_a.device_name,
        requester_id=operator.id,
        requester_name=operator.username,
        status="pending",
        expired_at=datetime.now() + timedelta(hours=1),
    )
    approval_b = CommandApproval(
        command_type="power_off",
        risk_level="critical",
        target_device_id=device_b.id,
        target_device_name=device_b.device_name,
        requester_id=operator.id,
        requester_name=operator.username,
        status="pending",
        expired_at=datetime.now() + timedelta(hours=1),
    )
    audit_a = CommandAuditLog(
        command_type="power_off",
        risk_level="critical",
        target_device_id=device_a.id,
        target_device_name=device_a.device_name,
        operator_id=operator.id,
        operator_name=operator.username,
        result="pending",
    )
    audit_b = CommandAuditLog(
        command_type="power_off",
        risk_level="critical",
        target_device_id=device_b.id,
        target_device_name=device_b.device_name,
        operator_id=operator.id,
        operator_name=operator.username,
        result="pending",
    )
    drift_a = DriftDetectionResult(
        point_id=point_a.id,
        point_code=point_a.point_code,
        point_name=point_a.point_name,
        status="suspected",
        mean_value=1,
        std_value=1,
        current_value=4,
        deviation_sigma=3,
        diagnosis="A drift",
    )
    drift_b = DriftDetectionResult(
        point_id=point_b.id,
        point_code=point_b.point_code,
        point_name=point_b.point_name,
        status="confirmed",
        mean_value=1,
        std_value=1,
        current_value=5,
        deviation_sigma=4,
        diagnosis="B drift",
    )
    async_db.add_all([approval_a, approval_b, audit_a, audit_b, drift_a, drift_b])
    await async_db.flush()
    headers = auth_headers(token)

    approvals = await client.get("/api/v1/command/approvals", headers=headers)
    foreign_approval = await client.get(f"/api/v1/command/approvals/{approval_b.id}", headers=headers)
    audits = await client.get("/api/v1/command/audit-logs", headers=headers)
    before_approvals = (await async_db.execute(select(CommandApproval))).scalars().all()
    before_audits = (await async_db.execute(select(CommandAuditLog))).scalars().all()
    foreign_submit = await client.post(
        "/api/v1/command/submit",
        headers=headers,
        json={
            "command_type": "power_off",
            "target_device_id": device_b.id,
            "target_device_name": device_b.device_name,
            "command_content": {},
        },
    )
    after_approvals = (await async_db.execute(select(CommandApproval))).scalars().all()
    after_audits = (await async_db.execute(select(CommandAuditLog))).scalars().all()
    drift_results = await client.get("/api/v1/drift/results", headers=headers)
    drift_summary = await client.get("/api/v1/drift/summary", headers=headers)
    foreign_drift = await client.get(f"/api/v1/drift/results/{drift_b.id}", headers=headers)
    foreign_resolve = await client.post(f"/api/v1/drift/results/{drift_b.id}/resolve", headers=headers)

    captured_point_ids = []

    async def capture_detection(db, allowed_point_ids=None):
        if allowed_point_ids is not None:
            captured_point_ids.extend((await db.execute(allowed_point_ids)).scalars().all())
        return {
            "total_checked": 0,
            "new_suspected": 0,
            "new_confirmed": 0,
            "auto_resolved": 0,
            "skipped": 0,
        }

    monkeypatch.setattr("app.api.v1.drift.drift_detection.run_drift_detection", capture_detection)
    detection = await client.post("/api/v1/drift/detect", headers=headers)

    assert [item["id"] for item in approvals.json()["items"]] == [approval_a.id]
    assert approvals.json()["total"] == 1
    assert foreign_approval.status_code == 404
    assert [item["id"] for item in audits.json()["items"]] == [audit_a.id]
    assert audits.json()["total"] == 1
    assert foreign_submit.status_code == 404
    assert len(after_approvals) == len(before_approvals)
    assert len(after_audits) == len(before_audits)
    assert [item["id"] for item in drift_results.json()["items"]] == [drift_a.id]
    assert drift_results.json()["total"] == 1
    assert drift_summary.json()["total_checked"] == 1
    assert foreign_drift.status_code == foreign_resolve.status_code == 404
    assert detection.status_code == 200
    assert captured_point_ids == [point_a.id]
    await async_db.refresh(drift_b)
    assert drift_b.status == "confirmed"


@pytest.mark.asyncio
async def test_asset_routes_follow_spatial_site_scope_and_keep_inventory_admin_only(
    client, async_db, operator_user, admin_user
):
    operator, operator_token = operator_user
    _, admin_token = admin_user
    site_a = Site(site_code="HTTP-ASSET-A", site_name="Asset authorized site")
    site_b = Site(site_code="HTTP-ASSET-B", site_name="Asset foreign site")
    async_db.add_all([site_a, site_b])
    await async_db.flush()
    async_db.add(UserSite(user_id=operator.id, site_id=site_a.id))
    floor_a = Floor(site_id=site_a.id, floor_code="ASSET-FA", floor_name="Asset floor A", sort_order=1)
    floor_b = Floor(site_id=site_b.id, floor_code="ASSET-FB", floor_name="Asset floor B", sort_order=1)
    async_db.add_all([floor_a, floor_b])
    await async_db.flush()
    room_a = Room(floor_id=floor_a.id, room_code="ASSET-RA", room_name="Asset room A")
    room_b = Room(floor_id=floor_b.id, room_code="ASSET-RB", room_name="Asset room B")
    async_db.add_all([room_a, room_b])
    await async_db.flush()
    row_a = Row(room_id=room_a.id, row_code="ASSET-ROWA", row_name="Asset row A")
    row_b = Row(room_id=room_b.id, row_code="ASSET-ROWB", row_name="Asset row B")
    async_db.add_all([row_a, row_b])
    await async_db.flush()
    cabinet_a = Cabinet(cabinet_code="ASSET-CA", cabinet_name="Asset cabinet A", row_id=row_a.id)
    cabinet_b = Cabinet(cabinet_code="ASSET-CB", cabinet_name="Asset cabinet B", row_id=row_b.id)
    async_db.add_all([cabinet_a, cabinet_b])
    await async_db.flush()
    asset_a = Asset(
        asset_code="ASSET-AA",
        asset_name="Asset A",
        asset_type=AssetType.server,
        cabinet_id=cabinet_a.id,
    )
    asset_b = Asset(
        asset_code="ASSET-AB",
        asset_name="Asset B",
        asset_type=AssetType.server,
        cabinet_id=cabinet_b.id,
    )
    async_db.add_all([asset_a, asset_b])
    await async_db.flush()
    async_db.add_all(
        [
            MaintenanceRecord(asset_id=asset_a.id, maintenance_type="routine", start_time=datetime.now()),
            MaintenanceRecord(asset_id=asset_b.id, maintenance_type="routine", start_time=datetime.now()),
            AssetInventory(inventory_code="ASSET-INV", inventory_date=date.today()),
        ]
    )
    await async_db.flush()
    operator_headers = auth_headers(operator_token)
    admin_headers = auth_headers(admin_token)

    cabinets = await client.get("/api/v1/asset/cabinets", headers=operator_headers)
    assets = await client.get("/api/v1/asset/assets", headers=operator_headers)
    maintenance = await client.get("/api/v1/asset/maintenance", headers=operator_headers)
    statistics = await client.get("/api/v1/asset/statistics", headers=operator_headers)
    foreign_detail = await client.get(f"/api/v1/asset/assets/{asset_b.id}", headers=operator_headers)
    foreign_create = await client.post(
        "/api/v1/asset/assets",
        headers=operator_headers,
        json={
            "asset_code": "ASSET-CROSS",
            "asset_name": "Cross-site asset",
            "asset_type": "server",
            "cabinet_id": cabinet_b.id,
        },
    )
    foreign_rebind = await client.put(
        f"/api/v1/asset/assets/{asset_a.id}",
        headers=operator_headers,
        json={"cabinet_id": cabinet_b.id},
    )
    operator_inventory = await client.get("/api/v1/asset/inventory", headers=operator_headers)
    admin_inventory = await client.get("/api/v1/asset/inventory", headers=admin_headers)

    assert [item["id"] for item in cabinets.json()] == [cabinet_a.id]
    assert [item["id"] for item in assets.json()] == [asset_a.id]
    assert [item["asset_id"] for item in maintenance.json()] == [asset_a.id]
    assert statistics.json()["total_count"] == 1
    assert foreign_detail.status_code == foreign_create.status_code == foreign_rebind.status_code == 404
    assert operator_inventory.status_code == 403
    assert admin_inventory.status_code == 200
    await async_db.refresh(asset_a)
    assert asset_a.cabinet_id == cabinet_a.id


@pytest.mark.asyncio
async def test_operation_work_orders_follow_device_scope_and_unowned_families_are_admin_only(
    client, async_db, operator_user, admin_user
):
    operator, operator_token = operator_user
    _, admin_token = admin_user
    site_a = Site(site_code="HTTP-OPS-A", site_name="Operation authorized site")
    site_b = Site(site_code="HTTP-OPS-B", site_name="Operation foreign site")
    async_db.add_all([site_a, site_b])
    await async_db.flush()
    async_db.add(UserSite(user_id=operator.id, site_id=site_a.id))
    device_a = Device(device_code="HTTP-OPS-DA", device_name="Operation A", device_type="UPS", area_code="A", site_id=site_a.id)
    device_b = Device(device_code="HTTP-OPS-DB", device_name="Operation B", device_type="UPS", area_code="B", site_id=site_b.id)
    async_db.add_all([device_a, device_b])
    await async_db.flush()
    order_a = WorkOrder(order_no="WO-39-A", title="Operation A", device_id=device_a.id)
    order_b = WorkOrder(order_no="WO-39-B", title="Operation B", device_id=device_b.id)
    plan = InspectionPlan(name="Global inspection plan")
    async_db.add_all([order_a, order_b, plan])
    await async_db.flush()
    operator_headers = auth_headers(operator_token)
    admin_headers = auth_headers(admin_token)

    listing = await client.get("/api/v1/operation/workorders", headers=operator_headers)
    foreign_detail = await client.get(f"/api/v1/operation/workorders/{order_b.id}", headers=operator_headers)
    before_orders = (await async_db.execute(select(WorkOrder))).scalars().all()
    foreign_create = await client.post(
        "/api/v1/operation/workorders",
        headers=operator_headers,
        json={"title": "Cross-site work order", "device_id": device_b.id},
    )
    foreign_rebind = await client.put(
        f"/api/v1/operation/workorders/{order_a.id}",
        headers=operator_headers,
        json={"device_id": device_b.id},
    )
    after_orders = (await async_db.execute(select(WorkOrder))).scalars().all()
    operator_plans = await client.get("/api/v1/operation/plans", headers=operator_headers)
    admin_plans = await client.get("/api/v1/operation/plans", headers=admin_headers)

    assert [item["id"] for item in listing.json()] == [order_a.id]
    assert foreign_detail.status_code == foreign_create.status_code == foreign_rebind.status_code == 404
    assert len(after_orders) == len(before_orders)
    assert operator_plans.status_code == 403
    assert admin_plans.status_code == 200
    await async_db.refresh(order_a)
    assert order_a.device_id == device_a.id


@pytest.mark.asyncio
async def test_diagnosis_records_follow_device_and_point_scope_while_configuration_is_global_admin(
    client, async_db, operator_user, admin_user
):
    operator, operator_token = operator_user
    _, admin_token = admin_user
    site_a = Site(site_code="HTTP-DIAG-A", site_name="Diagnosis authorized site")
    site_b = Site(site_code="HTTP-DIAG-B", site_name="Diagnosis foreign site")
    async_db.add_all([site_a, site_b])
    await async_db.flush()
    async_db.add(UserSite(user_id=operator.id, site_id=site_a.id))
    device_a = Device(device_code="HTTP-DIAG-DA", device_name="Diagnosis A", device_type="UPS", area_code="A", site_id=site_a.id)
    device_b = Device(device_code="HTTP-DIAG-DB", device_name="Diagnosis B", device_type="UPS", area_code="B", site_id=site_b.id)
    async_db.add_all([device_a, device_b])
    await async_db.flush()
    point_a = Point(point_code="HTTP-DIAG-PA", point_name="Diagnosis A", point_type="AI", device_id=device_a.id)
    point_b = Point(point_code="HTTP-DIAG-PB", point_name="Diagnosis B", point_type="AI", device_id=device_b.id)
    async_db.add_all([point_a, point_b])
    await async_db.flush()
    session_a = DiagnosisSession(device_id=device_a.id, engine_level="L1", start_time=datetime.now())
    session_b = DiagnosisSession(device_id=device_b.id, engine_level="L1", start_time=datetime.now())
    async_db.add_all([session_a, session_b])
    await async_db.flush()
    result_a = DiagnosisResult(device_id=device_a.id, session_id=session_a.id, conclusion="A")
    result_b = DiagnosisResult(device_id=device_b.id, session_id=session_b.id, conclusion="B")
    async_db.add_all(
        [
            result_a,
            result_b,
            BatterySOHRecord(device_id=device_a.id, soh_percent=95, calculated_at=datetime.now()),
            BatterySOHRecord(device_id=device_b.id, soh_percent=55, calculated_at=datetime.now()),
            TrendWarning(
                point_id=point_a.id,
                trend_type="up",
                start_value=1,
                end_value=2,
                total_change=1,
                message="A",
            ),
            TrendWarning(
                point_id=point_b.id,
                trend_type="up",
                start_value=1,
                end_value=3,
                total_change=2,
                message="B",
            ),
            DiagnosisAnnotation(session_id=session_a.id, annotator_id=operator.id, annotation="accurate"),
            DiagnosisAnnotation(session_id=session_b.id, annotator_id=operator.id, annotation="accurate"),
        ]
    )
    await async_db.flush()
    operator_headers = auth_headers(operator_token)
    admin_headers = auth_headers(admin_token)

    sessions = await client.get("/api/v1/diagnosis/sessions", headers=operator_headers)
    results = await client.get("/api/v1/diagnosis/results", headers=operator_headers)
    battery = await client.get("/api/v1/diagnosis/battery-soh/latest", headers=operator_headers)
    warnings = await client.get("/api/v1/diagnosis/trend-warnings", headers=operator_headers)
    annotations = await client.get("/api/v1/diagnosis/annotations", headers=operator_headers)
    foreign_session = await client.get(f"/api/v1/diagnosis/sessions/{session_b.id}", headers=operator_headers)
    foreign_result = await client.get(f"/api/v1/diagnosis/results/{result_b.id}", headers=operator_headers)
    before_annotations = (await async_db.execute(select(DiagnosisAnnotation))).scalars().all()
    foreign_annotation = await client.post(
        "/api/v1/diagnosis/annotations",
        headers=operator_headers,
        json={"session_id": session_b.id, "annotation": "accurate"},
    )
    after_annotations = (await async_db.execute(select(DiagnosisAnnotation))).scalars().all()
    operator_rules = await client.get("/api/v1/diagnosis/rules", headers=operator_headers)
    admin_rules = await client.get("/api/v1/diagnosis/rules", headers=admin_headers)

    assert [item["id"] for item in sessions.json()["items"]] == [session_a.id]
    assert [item["id"] for item in results.json()["items"]] == [result_a.id]
    assert [item["device_id"] for item in battery.json()["records"]] == [device_a.id]
    assert [item["point_id"] for item in warnings.json()["items"]] == [point_a.id]
    assert [item["session_id"] for item in annotations.json()["items"]] == [session_a.id]
    assert foreign_session.status_code == foreign_result.status_code == foreign_annotation.status_code == 404
    assert len(after_annotations) == len(before_annotations)
    assert operator_rules.status_code == 403
    assert admin_rules.status_code == 200


@pytest.mark.asyncio
async def test_sensor_metadata_routes_follow_point_device_site_scope(client, async_db, operator_user, monkeypatch):
    operator, token = operator_user
    site_a = Site(site_code="HTTP-SENSOR-A", site_name="Sensor authorized site")
    site_b = Site(site_code="HTTP-SENSOR-B", site_name="Sensor foreign site")
    async_db.add_all([site_a, site_b])
    await async_db.flush()
    async_db.add(UserSite(user_id=operator.id, site_id=site_a.id))
    device_a = Device(
        device_code="HTTP-SENSOR-DA",
        device_name="Sensor A",
        device_type="UPS",
        area_code="A",
        site_id=site_a.id,
    )
    device_b = Device(
        device_code="HTTP-SENSOR-DB",
        device_name="Sensor B",
        device_type="UPS",
        area_code="B",
        site_id=site_b.id,
    )
    async_db.add_all([device_a, device_b])
    await async_db.flush()
    point_a = Point(point_code="HTTP-SENSOR-PA", point_name="Sensor A", point_type="AI", device_id=device_a.id)
    point_b = Point(point_code="HTTP-SENSOR-PB", point_name="Sensor B", point_type="AI", device_id=device_b.id)
    point_c = Point(point_code="HTTP-SENSOR-PC", point_name="Sensor C", point_type="AI", device_id=device_b.id)
    async_db.add_all([point_a, point_b, point_c])
    await async_db.flush()
    metadata_a = SensorMetadata(point_id=point_a.id, accuracy_class=0.5, calibration_interval_days=365)
    metadata_b = SensorMetadata(point_id=point_b.id, accuracy_class=1.0, calibration_interval_days=365)
    async_db.add_all([metadata_a, metadata_b])
    await async_db.flush()
    monkeypatch.setattr("app.api.v1.sensor_metadata._publish_metadata_update", AsyncMock())
    headers = auth_headers(token)

    listing = await client.get("/api/v1/diagnosis/sensor-metadata/", headers=headers)
    foreign_detail = await client.get(
        f"/api/v1/diagnosis/sensor-metadata/{metadata_b.id}", headers=headers
    )
    foreign_calibration = await client.get(
        f"/api/v1/diagnosis/sensor-metadata/calibration-status/{point_b.id}", headers=headers
    )
    before_metadata = (await async_db.execute(select(SensorMetadata))).scalars().all()
    foreign_create = await client.post(
        "/api/v1/diagnosis/sensor-metadata/",
        headers=headers,
        json={"point_id": point_c.id, "accuracy_class": 0.5},
    )
    foreign_update = await client.put(
        f"/api/v1/diagnosis/sensor-metadata/{metadata_b.id}",
        headers=headers,
        json={"accuracy_class": 0.2},
    )
    foreign_delete = await client.delete(
        f"/api/v1/diagnosis/sensor-metadata/{metadata_b.id}", headers=headers
    )
    after_metadata = (await async_db.execute(select(SensorMetadata))).scalars().all()

    assert [item["id"] for item in listing.json()["items"]] == [metadata_a.id]
    assert foreign_detail.status_code == foreign_calibration.status_code == 404
    assert foreign_create.status_code == foreign_update.status_code == 404
    assert foreign_delete.status_code == 403
    assert len(after_metadata) == len(before_metadata)
    await async_db.refresh(metadata_b)
    assert metadata_b.accuracy_class == 1.0
