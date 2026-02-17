"""点位批量导入与预校验测试 — Story 3.2"""
import io
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from openpyxl import Workbook
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.main import app
from app.models.gateway import DataSource, DataSourcePoint
from app.services.point_import import parse_excel, validate_points, import_points


# ============================================================
# 辅助函数
# ============================================================

def create_test_excel(rows: list[list]) -> bytes:
    """创建测试用 Excel 文件"""
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def async_db():
    """创建测试用异步数据库"""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    yield session_factory
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest_asyncio.fixture
async def client(async_db):
    """创建测试 HTTP 客户端（跳过认证）"""
    from app.api.deps import require_viewer, require_operator, require_admin
    from app.models.user import User

    mock_user = User(id=1, username="test_admin", role="admin", is_active=True)

    app.dependency_overrides[require_viewer] = lambda: mock_user
    app.dependency_overrides[require_operator] = lambda: mock_user
    app.dependency_overrides[require_admin] = lambda: mock_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


async def create_datasource(client: AsyncClient) -> int:
    """创建测试数据源，返回 ID"""
    resp = await client.post("/api/v1/datasources", json={
        "name": "测试数据源",
        "protocol_type": "modbus_tcp",
        "connection_config": {"host": "192.168.1.1", "port": 502},
    })
    return resp.json()["id"]


# ============================================================
# 服务层测试
# ============================================================

class TestValidatePoints:
    """校验服务测试"""

    async def test_valid_excel(self, async_db):
        """测试1: 正常 Excel 校验通过"""
        excel_data = create_test_excel([
            ["address", "data_type", "scale", "offset"],
            ["40001", "int16", 1.0, 0.0],
            ["40002", "float32", 0.1, 0.0],
        ])
        async with async_db() as session:
            # 创建数据源
            ds = DataSource(
                name="测试源", protocol_type="modbus_tcp",
                connection_config={"host": "127.0.0.1", "port": 502},
            )
            session.add(ds)
            await session.commit()
            await session.refresh(ds)

            report = await validate_points(excel_data, ds.id, session)
            assert report["total"] == 2
            assert report["passed"] == 2
            assert report["failed"] == 0
            assert report["errors"] == []

    async def test_duplicate_address_in_excel(self, async_db):
        """测试2: Excel 内部地址重复检测"""
        excel_data = create_test_excel([
            ["address", "data_type"],
            ["40001", "int16"],
            ["40001", "float32"],
        ])
        async with async_db() as session:
            ds = DataSource(
                name="测试源", protocol_type="modbus_tcp",
                connection_config={"host": "127.0.0.1", "port": 502},
            )
            session.add(ds)
            await session.commit()
            await session.refresh(ds)

            report = await validate_points(excel_data, ds.id, session)
            assert report["failed"] > 0
            addr_errors = [e for e in report["errors"] if "重复" in e["message"]]
            assert len(addr_errors) >= 1

    async def test_duplicate_address_in_db(self, async_db):
        """测试3: 与数据库已有地址冲突检测"""
        excel_data = create_test_excel([
            ["address", "data_type"],
            ["40001", "int16"],
        ])
        async with async_db() as session:
            ds = DataSource(
                name="测试源", protocol_type="modbus_tcp",
                connection_config={"host": "127.0.0.1", "port": 502},
            )
            session.add(ds)
            await session.commit()
            await session.refresh(ds)

            # 预先插入一个同地址的点位
            existing_point = DataSourcePoint(
                datasource_id=ds.id, address="40001", data_type="int16",
            )
            session.add(existing_point)
            await session.commit()

            report = await validate_points(excel_data, ds.id, session)
            assert report["failed"] > 0
            addr_errors = [e for e in report["errors"] if "已存在" in e["message"]]
            assert len(addr_errors) >= 1

    async def test_invalid_data_type(self, async_db):
        """测试4: 无效数据类型"""
        excel_data = create_test_excel([
            ["address", "data_type"],
            ["40001", "invalid_type"],
        ])
        async with async_db() as session:
            ds = DataSource(
                name="测试源", protocol_type="modbus_tcp",
                connection_config={"host": "127.0.0.1", "port": 502},
            )
            session.add(ds)
            await session.commit()
            await session.refresh(ds)

            report = await validate_points(excel_data, ds.id, session)
            assert report["failed"] > 0
            type_errors = [e for e in report["errors"] if "无效数据类型" in e["message"]]
            assert len(type_errors) >= 1

    async def test_invalid_scale_offset(self, async_db):
        """测试5: scale/offset 非数值"""
        excel_data = create_test_excel([
            ["address", "data_type", "scale", "offset"],
            ["40001", "int16", "abc", "xyz"],
        ])
        async with async_db() as session:
            ds = DataSource(
                name="测试源", protocol_type="modbus_tcp",
                connection_config={"host": "127.0.0.1", "port": 502},
            )
            session.add(ds)
            await session.commit()
            await session.refresh(ds)

            report = await validate_points(excel_data, ds.id, session)
            assert report["failed"] > 0
            scale_errors = [e for e in report["errors"] if "scale" in e["field"] or "offset" in e["field"]]
            assert len(scale_errors) >= 2

    async def test_empty_excel(self, async_db):
        """测试6: 空文件/无数据行"""
        excel_data = create_test_excel([
            ["address", "data_type"],
        ])
        async with async_db() as session:
            ds = DataSource(
                name="测试源", protocol_type="modbus_tcp",
                connection_config={"host": "127.0.0.1", "port": 502},
            )
            session.add(ds)
            await session.commit()
            await session.refresh(ds)

            report = await validate_points(excel_data, ds.id, session)
            assert report["total"] == 0
            assert report["errors"][0]["message"] == "Excel 文件无数据行"


class TestImportPoints:
    """导入服务测试"""

    async def test_import_success(self, async_db):
        """测试7: 校验通过后批量插入"""
        excel_data = create_test_excel([
            ["address", "data_type", "scale", "offset"],
            ["40001", "int16", 1.0, 0.0],
            ["40002", "float32", 0.1, 0.0],
            ["40003", "bool", None, None],
        ])
        async with async_db() as session:
            ds = DataSource(
                name="测试源", protocol_type="modbus_tcp",
                connection_config={"host": "127.0.0.1", "port": 502},
            )
            session.add(ds)
            await session.commit()
            await session.refresh(ds)

            result = await import_points(excel_data, ds.id, session)
            assert result["success"] is True
            assert result["imported"] == 3

            # 验证数据库中确实有 3 条记录
            from sqlalchemy import select, func
            count = (await session.execute(
                select(func.count()).select_from(DataSourcePoint).where(
                    DataSourcePoint.datasource_id == ds.id
                )
            )).scalar()
            assert count == 3


# ============================================================
# API 端点测试
# ============================================================

class TestPointImportAPI:
    """点位导入 API 端点测试"""

    async def test_validate_rejects_non_xlsx(self, client):
        """测试8: 文件格式校验 — 非 xlsx 返回 400"""
        ds_id = await create_datasource(client)
        resp = await client.post(
            f"/api/v1/datasources/{ds_id}/points/validate",
            files={"file": ("test.csv", b"some,csv,data", "text/csv")},
        )
        assert resp.status_code == 400
        assert "xlsx" in resp.json()["detail"]

    async def test_validate_rejects_large_file(self, client):
        """测试9: 文件大小校验 — >10MB 返回 400"""
        ds_id = await create_datasource(client)
        # 创建一个超过 10MB 的假文件
        large_content = b"x" * (10 * 1024 * 1024 + 1)
        resp = await client.post(
            f"/api/v1/datasources/{ds_id}/points/validate",
            files={"file": ("test.xlsx", large_content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert resp.status_code == 400
        assert "10MB" in resp.json()["detail"]
