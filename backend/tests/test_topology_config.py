"""配电与制冷拓扑配置 API 测试 — Story 8-2"""

import pytest

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import delete

from app.core.database import Base
from app.models.device import Device
from app.models.asset import Cabinet
from app.models.cooling import CoolingUnit
from app.models.spatial import Site, Floor, Room, Row
from app.models.topology_config import (
    PowerPhaseMapping,
    CoolingZone,
    CoolingZoneCabinet,
    CoolingZoneUnit,
)
from app.models.user import User
from app.api.deps import get_db, require_viewer, require_operator, require_admin


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture(scope="module")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="module")
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")

    # 启用 SQLite 外键约束
    from sqlalchemy import event

    @event.listens_for(eng.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture(scope="module")
def session_factory(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
async def db_session(session_factory):
    async with session_factory() as session:
        # 清理所有相关表（注意顺序：先子表后父表）
        await session.execute(delete(CoolingZoneUnit))
        await session.execute(delete(CoolingZoneCabinet))
        await session.execute(delete(CoolingZone))
        await session.execute(delete(PowerPhaseMapping))
        await session.execute(delete(CoolingUnit))
        await session.execute(delete(Cabinet))
        await session.execute(delete(Row))
        await session.execute(delete(Room))
        await session.execute(delete(Floor))
        await session.execute(delete(Site))
        await session.execute(delete(Device))
        await session.commit()
        yield session


@pytest.fixture
def mock_user():
    user = User()
    user.id = 1
    user.username = "test_admin"
    user.role = "admin"
    user.is_active = True
    return user


@pytest.fixture
async def app(db_session, mock_user):
    from app.main import app as _app

    async def override_get_db():
        yield db_session

    async def override_require_viewer():
        return mock_user

    async def override_require_operator():
        return mock_user

    async def override_require_admin():
        return mock_user

    _app.dependency_overrides[get_db] = override_get_db
    _app.dependency_overrides[require_viewer] = override_require_viewer
    _app.dependency_overrides[require_operator] = override_require_operator
    _app.dependency_overrides[require_admin] = override_require_admin

    yield _app

    _app.dependency_overrides.clear()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ============================================================
# 辅助函数
# ============================================================


async def _create_pdu_device(db_session: AsyncSession) -> Device:
    """创建 PDU 设备"""
    dev = Device(
        device_code="PDU-TEST-001",
        device_name="测试PDU",
        device_type="PDU",
        area_code="A01",
    )
    db_session.add(dev)
    await db_session.flush()
    return dev


async def _create_cabinet(db_session: AsyncSession, code: str, name: str, max_power: float = 5.0) -> Cabinet:
    """创建机柜"""
    cab = Cabinet(
        cabinet_code=code,
        cabinet_name=name,
        total_u=42,
        max_power=max_power,
    )
    db_session.add(cab)
    await db_session.flush()
    return cab


async def _create_cooling_unit(db_session: AsyncSession, device_code: str) -> CoolingUnit:
    """创建空调（先创建设备再创建空调扩展）"""
    dev = Device(
        device_code=device_code,
        device_name=f"空调-{device_code}",
        device_type="AC",
        area_code="A01",
    )
    db_session.add(dev)
    await db_session.flush()
    unit = CoolingUnit(
        device_id=dev.id,
        unit_type="indoor",
        cooling_capacity_kw=50.0,
    )
    db_session.add(unit)
    await db_session.flush()
    return unit


# ============================================================
# 测试用例
# ============================================================


class TestPowerPhaseMappingCRUD:
    """测试1: 三相接线映射 CRUD"""

    async def test_power_phase_mapping_crud(self, client: AsyncClient, db_session: AsyncSession):
        """创建 PDU 设备→创建机柜→创建接线→查询→删除"""
        pdu = await _create_pdu_device(db_session)
        cab = await _create_cabinet(db_session, "CAB-PPM-01", "测试机柜1")

        # 创建接线映射
        resp = await client.post(
            "/api/v1/topology-config/power-phase",
            json={
                "cabinet_id": cab.id,
                "pdu_device_id": pdu.id,
                "phase": "A",
                "feed_type": "primary",
                "rated_current": 32.0,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["phase"] == "A"
        assert data["feed_type"] == "primary"
        assert data["pdu_device_name"] == "测试PDU"
        assert data["cabinet_code"] == "CAB-PPM-01"
        mapping_id = data["id"]

        # 查询列表
        resp = await client.get("/api/v1/topology-config/power-phase")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

        # 查询机柜接线
        resp = await client.get(f"/api/v1/topology-config/power-phase/cabinet/{cab.id}")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

        # 删除
        resp = await client.delete(f"/api/v1/topology-config/power-phase/{mapping_id}")
        assert resp.status_code == 200


class TestPowerPhaseUniqueConstraint:
    """测试2: 同一机柜同一 feed_type 不能重复"""

    async def test_power_phase_unique_constraint(self, client: AsyncClient, db_session: AsyncSession):
        pdu = await _create_pdu_device(db_session)
        cab = await _create_cabinet(db_session, "CAB-UQ-01", "唯一性测试机柜")
        # 提前保存 ID，避免 commit 后 lazy load 问题
        pdu_id = pdu.id
        cab_id = cab.id

        # 第一次创建 primary
        resp = await client.post(
            "/api/v1/topology-config/power-phase",
            json={
                "cabinet_id": cab_id,
                "pdu_device_id": pdu_id,
                "phase": "A",
                "feed_type": "primary",
            },
        )
        assert resp.status_code == 200

        # 第二次创建 primary → 应冲突
        resp = await client.post(
            "/api/v1/topology-config/power-phase",
            json={
                "cabinet_id": cab_id,
                "pdu_device_id": pdu_id,
                "phase": "B",
                "feed_type": "primary",
            },
        )
        assert resp.status_code == 409

        # backup 应该可以
        resp = await client.post(
            "/api/v1/topology-config/power-phase",
            json={
                "cabinet_id": cab_id,
                "pdu_device_id": pdu_id,
                "phase": "B",
                "feed_type": "backup",
            },
        )
        assert resp.status_code == 200


class TestPhaseBalanceNormal:
    """测试3: 三相不平衡度正常计算"""

    async def test_phase_balance_normal(self, client: AsyncClient, db_session: AsyncSession):
        pdu = await _create_pdu_device(db_session)
        cab_a = await _create_cabinet(db_session, "CAB-BA-01", "A相机柜", max_power=10.0)
        cab_b = await _create_cabinet(db_session, "CAB-BB-01", "B相机柜", max_power=8.0)
        cab_c = await _create_cabinet(db_session, "CAB-BC-01", "C相机柜", max_power=6.0)

        # 分别接 A/B/C 相
        for cab, phase in [(cab_a, "A"), (cab_b, "B"), (cab_c, "C")]:
            resp = await client.post(
                "/api/v1/topology-config/power-phase",
                json={
                    "cabinet_id": cab.id,
                    "pdu_device_id": pdu.id,
                    "phase": phase,
                    "feed_type": "primary",
                },
            )
            assert resp.status_code == 200

        # 查询不平衡度
        resp = await client.get(f"/api/v1/topology-config/power-phase/pdu/{pdu.id}/balance")
        assert resp.status_code == 200
        data = resp.json()
        assert data["phase_a_power"] == 10.0
        assert data["phase_b_power"] == 8.0
        assert data["phase_c_power"] == 6.0
        assert data["data_source"] == "estimated"
        assert data["imbalance_rate"] is not None
        # (10-6) / ((10+8+6)/3) * 100 = 4/8*100 = 50.0
        assert abs(data["imbalance_rate"] - 50.0) < 0.1


class TestPhaseBalanceEdgeCases:
    """测试4: 三相不平衡度边界情况"""

    async def test_phase_balance_edge_cases(self, client: AsyncClient, db_session: AsyncSession):
        pdu = await _create_pdu_device(db_session)

        # 无数据时
        resp = await client.get(f"/api/v1/topology-config/power-phase/pdu/{pdu.id}/balance")
        assert resp.status_code == 200
        data = resp.json()
        assert data["imbalance_rate"] is None
        assert data["data_source"] == "no_data"

        # 只有一相有数据
        cab = await _create_cabinet(db_session, "CAB-EDGE-01", "边界机柜", max_power=10.0)
        resp = await client.post(
            "/api/v1/topology-config/power-phase",
            json={
                "cabinet_id": cab.id,
                "pdu_device_id": pdu.id,
                "phase": "A",
                "feed_type": "primary",
            },
        )
        assert resp.status_code == 200

        resp = await client.get(f"/api/v1/topology-config/power-phase/pdu/{pdu.id}/balance")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data_source"] == "estimated"
        assert data["imbalance_rate"] is not None
        # (10-0) / ((10+0+0)/3) * 100 = 10/3.33*100 = 300.0
        assert abs(data["imbalance_rate"] - 300.0) < 0.1


class TestCoolingZoneCRUD:
    """测试5: 制冷区域 CRUD"""

    async def test_cooling_zone_crud(self, client: AsyncClient, db_session: AsyncSession):
        cab = await _create_cabinet(db_session, "CAB-CZ-01", "制冷区机柜")
        unit = await _create_cooling_unit(db_session, "AC-CZ-01")

        # 创建制冷区域
        resp = await client.post(
            "/api/v1/topology-config/cooling-zones",
            json={
                "zone_name": "制冷区域A",
                "design_capacity_kw": 100.0,
                "cabinet_ids": [cab.id],
                "cooling_unit_ids": [unit.id],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["zone_code"].startswith("CZ-")
        assert data["zone_name"] == "制冷区域A"
        assert len(data["cabinets"]) == 1
        assert len(data["cooling_units"]) == 1
        zone_id = data["id"]

        # 查询列表
        resp = await client.get("/api/v1/topology-config/cooling-zones")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

        # 查询详情
        resp = await client.get(f"/api/v1/topology-config/cooling-zones/{zone_id}")
        assert resp.status_code == 200
        assert resp.json()["zone_name"] == "制冷区域A"

        # 更新：移除机柜关联
        resp = await client.put(
            f"/api/v1/topology-config/cooling-zones/{zone_id}",
            json={
                "zone_name": "制冷区域A(更新)",
                "cabinet_ids": [],
            },
        )
        assert resp.status_code == 200
        assert resp.json()["zone_name"] == "制冷区域A(更新)"
        assert len(resp.json()["cabinets"]) == 0

        # 删除
        resp = await client.delete(f"/api/v1/topology-config/cooling-zones/{zone_id}")
        assert resp.status_code == 200


class TestCoolingZoneCapacity:
    """测试6: 制冷区域容量使用率"""

    async def test_cooling_zone_capacity(self, client: AsyncClient, db_session: AsyncSession):
        cab1 = await _create_cabinet(db_session, "CAB-CAP-01", "容量机柜1", max_power=20.0)
        cab2 = await _create_cabinet(db_session, "CAB-CAP-02", "容量机柜2", max_power=30.0)

        # 创建制冷区域
        resp = await client.post(
            "/api/v1/topology-config/cooling-zones",
            json={
                "zone_name": "容量测试区",
                "design_capacity_kw": 100.0,
                "cabinet_ids": [cab1.id, cab2.id],
            },
        )
        assert resp.status_code == 200
        zone_id = resp.json()["id"]

        # 查询容量
        resp = await client.get(f"/api/v1/topology-config/cooling-zones/{zone_id}/capacity")
        assert resp.status_code == 200
        data = resp.json()
        assert data["design_capacity_kw"] == 100.0
        assert data["total_cabinet_power"] == 50.0
        assert data["utilization_rate"] == 50.0


class TestCabinetTopologySummary:
    """测试7: 机柜拓扑汇总"""

    async def test_cabinet_topology_summary(self, client: AsyncClient, db_session: AsyncSession):
        # 创建空间层级
        site = Site(site_code="S-TOPO-01", site_name="拓扑测试站点")
        db_session.add(site)
        await db_session.flush()
        floor = Floor(floor_code="F1", floor_name="一楼", site_id=site.id)
        db_session.add(floor)
        await db_session.flush()
        room = Room(room_code="RM01", room_name="机房A", floor_id=floor.id)
        db_session.add(room)
        await db_session.flush()
        row = Row(row_code="R1", row_name="第一排", room_id=room.id)
        db_session.add(row)
        await db_session.flush()

        # 创建机柜并关联到行
        cab = Cabinet(
            cabinet_code="CAB-TOPO-01",
            cabinet_name="拓扑机柜",
            total_u=42,
            max_power=10.0,
            row_id=row.id,
        )
        db_session.add(cab)
        await db_session.flush()

        # 创建 PDU 接线
        pdu = Device(device_code="PDU-TOPO-01", device_name="拓扑PDU", device_type="PDU", area_code="A01")
        db_session.add(pdu)
        await db_session.flush()
        mapping = PowerPhaseMapping(
            cabinet_id=cab.id,
            pdu_device_id=pdu.id,
            phase="A",
            feed_type="primary",
        )
        db_session.add(mapping)
        await db_session.flush()

        # 创建制冷区域并关联机柜
        zone = CoolingZone(zone_code="CZ-TOPO-01", zone_name="拓扑制冷区", design_capacity_kw=50.0)
        db_session.add(zone)
        await db_session.flush()
        db_session.add(CoolingZoneCabinet(zone_id=zone.id, cabinet_id=cab.id))
        await db_session.commit()

        # 查询汇总
        resp = await client.get(f"/api/v1/topology-config/cabinet/{cab.id}/topology-summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cabinet_code"] == "CAB-TOPO-01"
        # 空间
        assert data["spatial"] is not None
        assert data["spatial"]["site_name"] == "拓扑测试站点"
        assert data["spatial"]["room_name"] == "机房A"
        # 配电
        assert len(data["power"]) == 1
        assert data["power"][0]["phase"] == "A"
        # 制冷
        assert len(data["cooling"]) == 1
        assert data["cooling"][0]["zone_name"] == "拓扑制冷区"


class TestCascadeDelete:
    """测试8: 级联删除"""

    async def test_cascade_delete(self, client: AsyncClient, db_session: AsyncSession):
        """删除机柜后 PowerPhaseMapping 和 CoolingZoneCabinet 被级联删除"""
        pdu = await _create_pdu_device(db_session)
        cab = await _create_cabinet(db_session, "CAB-DEL-01", "级联删除机柜")
        pdu_id = pdu.id
        cab_id = cab.id

        # 创建接线映射
        mapping = PowerPhaseMapping(
            cabinet_id=cab_id,
            pdu_device_id=pdu_id,
            phase="A",
            feed_type="primary",
        )
        db_session.add(mapping)
        await db_session.flush()

        # 创建制冷区域关联
        zone = CoolingZone(zone_code="CZ-DEL-01", zone_name="级联删除区")
        db_session.add(zone)
        await db_session.flush()
        db_session.add(CoolingZoneCabinet(zone_id=zone.id, cabinet_id=cab_id))
        await db_session.commit()

        # 删除机柜（通过 SQL 直接删除，触发 FK CASCADE）
        from sqlalchemy import text

        await db_session.execute(text(f"DELETE FROM cabinets WHERE id = {cab_id}"))
        await db_session.commit()

        # 验证映射已被级联删除
        from sqlalchemy import select

        result = await db_session.execute(select(PowerPhaseMapping).where(PowerPhaseMapping.cabinet_id == cab_id))
        assert result.scalars().all() == []

        result = await db_session.execute(select(CoolingZoneCabinet).where(CoolingZoneCabinet.cabinet_id == cab_id))
        assert result.scalars().all() == []
