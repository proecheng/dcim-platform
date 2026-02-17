"""空间拓扑 API 测试 — Story 8-1"""
import pytest
from io import BytesIO

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import delete
import openpyxl

from app.core.database import Base
from app.models.spatial import Site, Floor, Room, Row, LayoutTemplate
from app.models.asset import Cabinet
from app.models.user import User
from app.api.deps import get_db, require_viewer, require_operator


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture(scope="module")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="module")
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
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
        # 清理所有相关表
        await session.execute(delete(Cabinet))
        await session.execute(delete(Row))
        await session.execute(delete(Room))
        await session.execute(delete(Floor))
        await session.execute(delete(Site))
        await session.execute(delete(LayoutTemplate))
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

    _app.dependency_overrides[get_db] = override_get_db
    _app.dependency_overrides[require_viewer] = override_require_viewer
    _app.dependency_overrides[require_operator] = override_require_operator

    yield _app

    _app.dependency_overrides.clear()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ============================================================
# 测试用例
# ============================================================

class TestSiteCRUD:
    """站点 CRUD 测试"""

    async def test_site_crud(self, client: AsyncClient):
        """创建、查询、更新、删除站点"""
        # 创建
        resp = await client.post("/api/v1/spatial/sites", json={
            "site_code": "S001", "site_name": "北京站点", "address": "北京市"
        })
        assert resp.status_code == 200
        site = resp.json()
        assert site["site_code"] == "S001"
        assert site["site_name"] == "北京站点"
        site_id = site["id"]

        # 查询列表
        resp = await client.get("/api/v1/spatial/sites")
        assert resp.status_code == 200
        sites = resp.json()
        assert len(sites) >= 1

        # 关键词搜索
        resp = await client.get("/api/v1/spatial/sites", params={"keyword": "北京"})
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

        # 更新
        resp = await client.put(f"/api/v1/spatial/sites/{site_id}", json={
            "site_name": "北京站点(更新)"
        })
        assert resp.status_code == 200
        assert resp.json()["site_name"] == "北京站点(更新)"

        # 删除
        resp = await client.delete(f"/api/v1/spatial/sites/{site_id}")
        assert resp.status_code == 200


class TestFloorCRUD:
    """楼层 CRUD 测试"""

    async def test_floor_crud(self, client: AsyncClient):
        """创建、查询楼层"""
        # 先创建站点
        resp = await client.post("/api/v1/spatial/sites", json={
            "site_code": "S-F01", "site_name": "测试站点"
        })
        site_id = resp.json()["id"]

        # 创建楼层
        resp = await client.post("/api/v1/spatial/floors", json={
            "floor_code": "F1", "floor_name": "一楼", "site_id": site_id
        })
        assert resp.status_code == 200
        floor = resp.json()
        assert floor["floor_code"] == "F1"

        # 按站点过滤
        resp = await client.get("/api/v1/spatial/floors", params={"site_id": site_id})
        assert resp.status_code == 200
        assert len(resp.json()) == 1


class TestRoomCRUD:
    """房间 CRUD 测试"""

    async def test_room_crud(self, client: AsyncClient):
        """创建、查询房间（含 grid_cols/grid_rows）"""
        # 创建站点 → 楼层
        resp = await client.post("/api/v1/spatial/sites", json={
            "site_code": "S-R01", "site_name": "测试站点"
        })
        site_id = resp.json()["id"]
        resp = await client.post("/api/v1/spatial/floors", json={
            "floor_code": "F1", "floor_name": "一楼", "site_id": site_id
        })
        floor_id = resp.json()["id"]

        # 创建房间
        resp = await client.post("/api/v1/spatial/rooms", json={
            "room_code": "RM01", "room_name": "机房A",
            "floor_id": floor_id, "grid_cols": 30, "grid_rows": 25
        })
        assert resp.status_code == 200
        room = resp.json()
        assert room["grid_cols"] == 30
        assert room["grid_rows"] == 25

        # 按楼层过滤
        resp = await client.get("/api/v1/spatial/rooms", params={"floor_id": floor_id})
        assert resp.status_code == 200
        assert len(resp.json()) == 1


class TestRowCRUD:
    """行 CRUD 测试"""

    async def test_row_crud(self, client: AsyncClient):
        """创建、查询行"""
        # 创建站点 → 楼层 → 房间
        resp = await client.post("/api/v1/spatial/sites", json={
            "site_code": "S-RW01", "site_name": "测试站点"
        })
        site_id = resp.json()["id"]
        resp = await client.post("/api/v1/spatial/floors", json={
            "floor_code": "F1", "floor_name": "一楼", "site_id": site_id
        })
        floor_id = resp.json()["id"]
        resp = await client.post("/api/v1/spatial/rooms", json={
            "room_code": "RM01", "room_name": "机房A", "floor_id": floor_id
        })
        room_id = resp.json()["id"]

        # 创建行
        resp = await client.post("/api/v1/spatial/rows", json={
            "row_code": "R1", "row_name": "第一排",
            "room_id": room_id, "aisle_type": "cold"
        })
        assert resp.status_code == 200
        row = resp.json()
        assert row["aisle_type"] == "cold"

        # 按房间过滤
        resp = await client.get("/api/v1/spatial/rows", params={"room_id": room_id})
        assert resp.status_code == 200
        assert len(resp.json()) == 1


class TestSpatialTree:
    """空间拓扑树测试"""

    async def test_spatial_tree(self, client: AsyncClient):
        """创建完整层级后查询 tree"""
        # 创建完整层级
        resp = await client.post("/api/v1/spatial/sites", json={
            "site_code": "S-T01", "site_name": "树测试站点"
        })
        site_id = resp.json()["id"]

        resp = await client.post("/api/v1/spatial/floors", json={
            "floor_code": "F1", "floor_name": "一楼", "site_id": site_id
        })
        floor_id = resp.json()["id"]

        resp = await client.post("/api/v1/spatial/rooms", json={
            "room_code": "RM01", "room_name": "机房A", "floor_id": floor_id
        })
        room_id = resp.json()["id"]

        resp = await client.post("/api/v1/spatial/rows", json={
            "row_code": "R1", "row_name": "第一排", "room_id": room_id
        })
        assert resp.status_code == 200

        # 查询树
        resp = await client.get("/api/v1/spatial/tree")
        assert resp.status_code == 200
        tree = resp.json()
        assert len(tree) >= 1
        site_node = [s for s in tree if s["site_code"] == "S-T01"][0]
        assert len(site_node["floors"]) >= 1
        assert len(site_node["floors"][0]["rooms"]) >= 1
        assert len(site_node["floors"][0]["rooms"][0]["rows"]) >= 1


class TestCabinetPosition:
    """机柜位置更新测试"""

    async def test_cabinet_position(self, client: AsyncClient, db_session):
        """更新机柜位置"""
        # 创建层级
        resp = await client.post("/api/v1/spatial/sites", json={
            "site_code": "S-CP01", "site_name": "位置测试"
        })
        site_id = resp.json()["id"]
        resp = await client.post("/api/v1/spatial/floors", json={
            "floor_code": "F1", "floor_name": "一楼", "site_id": site_id
        })
        floor_id = resp.json()["id"]
        resp = await client.post("/api/v1/spatial/rooms", json={
            "room_code": "RM01", "room_name": "机房A", "floor_id": floor_id
        })
        room_id = resp.json()["id"]
        resp = await client.post("/api/v1/spatial/rows", json={
            "row_code": "R1", "row_name": "第一排", "room_id": room_id
        })
        row_id = resp.json()["id"]

        # 直接创建机柜
        cab = Cabinet(cabinet_code="CAB-POS-01", cabinet_name="测试机柜", total_u=42)
        db_session.add(cab)
        await db_session.flush()
        cab_id = cab.id

        # 更新位置
        resp = await client.put(f"/api/v1/spatial/cabinets/{cab_id}/position", json={
            "row_id": row_id, "aisle_type": "cold", "grid_x": 5, "grid_y": 3
        })
        assert resp.status_code == 200


class TestCascadeDeleteProtection:
    """级联删除保护测试"""

    async def test_cascade_delete_protection(self, client: AsyncClient):
        """删除含子实体的父实体返回 400"""
        # 创建站点 → 楼层
        resp = await client.post("/api/v1/spatial/sites", json={
            "site_code": "S-DEL01", "site_name": "删除测试"
        })
        site_id = resp.json()["id"]
        resp = await client.post("/api/v1/spatial/floors", json={
            "floor_code": "F1", "floor_name": "一楼", "site_id": site_id
        })
        assert resp.status_code == 200

        # 尝试删除站点 → 应返回 400
        resp = await client.delete(f"/api/v1/spatial/sites/{site_id}")
        assert resp.status_code == 400
        assert "楼层" in resp.json()["detail"]


class TestTemplateList:
    """模板列表测试"""

    async def test_template_list(self, client: AsyncClient):
        """获取模板列表"""
        resp = await client.get("/api/v1/spatial/templates")
        assert resp.status_code == 200
        templates = resp.json()
        assert len(templates) >= 3
        codes = [t["template_code"] for t in templates]
        assert "2n_cold_aisle" in codes
        assert "single_row" in codes
        assert "double_row" in codes


class TestTemplateApply:
    """模板应用测试"""

    async def test_template_apply(self, client: AsyncClient):
        """应用模板到房间"""
        # 创建层级
        resp = await client.post("/api/v1/spatial/sites", json={
            "site_code": "S-TPL01", "site_name": "模板测试"
        })
        site_id = resp.json()["id"]
        resp = await client.post("/api/v1/spatial/floors", json={
            "floor_code": "F1", "floor_name": "一楼", "site_id": site_id
        })
        floor_id = resp.json()["id"]
        resp = await client.post("/api/v1/spatial/rooms", json={
            "room_code": "RM-TPL", "room_name": "模板机房", "floor_id": floor_id
        })
        room_id = resp.json()["id"]

        # 获取模板列表，找到 single_row
        resp = await client.get("/api/v1/spatial/templates")
        templates = resp.json()
        single_row_tpl = [t for t in templates if t["template_code"] == "single_row"][0]

        # 应用模板
        resp = await client.post(
            f"/api/v1/spatial/templates/{single_row_tpl['id']}/apply",
            json={"room_id": room_id}
        )
        assert resp.status_code == 200
        result = resp.json()
        assert result["created_rows"] == 1
        assert result["created_cabinets"] == 10
        assert result["skipped_cabinets"] == 0

        # 再次应用 → 机柜应全部跳过
        resp = await client.post(
            f"/api/v1/spatial/templates/{single_row_tpl['id']}/apply",
            json={"room_id": room_id}
        )
        assert resp.status_code == 200
        result2 = resp.json()
        assert result2["created_rows"] == 0
        assert result2["created_cabinets"] == 0
        assert result2["skipped_cabinets"] == 10


class TestExcelImport:
    """Excel 导入测试"""

    async def test_excel_import(self, client: AsyncClient):
        """Excel 导入空间拓扑"""
        # 创建临时 xlsx
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append([
            "站点编码", "楼层编码", "房间编码", "行编码",
            "通道类型", "机柜编码", "机柜名称", "列号",
            "总U数", "最大功率", "最大承重",
        ])
        ws.append(["IMP-S1", "IMP-F1", "IMP-RM1", "IMP-R1", "cold", "IMP-CAB-01", "导入机柜1", "A01", 42, 5.0, 500])
        ws.append(["IMP-S1", "IMP-F1", "IMP-RM1", "IMP-R1", "cold", "IMP-CAB-02", "导入机柜2", "A02", 42, 5.0, 500])

        buf = BytesIO()
        wb.save(buf)
        buf.seek(0)

        resp = await client.post(
            "/api/v1/spatial/import",
            files={"file": ("test.xlsx", buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert resp.status_code == 200
        result = resp.json()
        assert result["total"] == 2
        assert result["success"] == 2
        assert result["failed"] == 0

        # 验证站点/楼层/房间/行已创建
        resp = await client.get("/api/v1/spatial/sites")
        site_codes = [s["site_code"] for s in resp.json()]
        assert "IMP-S1" in site_codes

        # 再次导入同样数据 → 机柜应跳过
        buf.seek(0)
        resp = await client.post(
            "/api/v1/spatial/import",
            files={"file": ("test.xlsx", buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert resp.status_code == 200
        result2 = resp.json()
        assert result2["skipped"] == 2
        assert result2["success"] == 0
