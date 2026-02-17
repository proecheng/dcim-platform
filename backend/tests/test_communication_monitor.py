"""通信中断检测服务测试"""
import pytest
from datetime import datetime, timedelta
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select

from app.core.database import Base
from app.main import app
from app.api.deps import get_db
from app.models.gateway import DataSource, DataSourcePoint
from app.models.point import Point, PointRealtime
from app.services.communication_monitor import check_communication_status, mark_unreliable_points

# 内存数据库
engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
TestSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db():
    async with TestSession() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def _create_test_user(session: AsyncSession):
    """创建测试用户用于 API 认证"""
    from app.models.user import User
    from app.core.security import get_password_hash
    user = User(
        username="admin",
        password_hash=get_password_hash("admin123"),
        role="admin",
        is_active=True,
    )
    session.add(user)
    await session.commit()
    return user


async def _get_token() -> str:
    """获取 JWT token"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/auth/login",
            data={"username": "admin", "password": "admin123"},
        )
        return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_check_communication_marks_interrupted():
    """连续失败达到阈值时标记 interrupted"""
    async with TestSession() as session:
        ds = DataSource(
            name="测试数据源",
            protocol_type="modbus_tcp",
            connection_config={"host": "127.0.0.1", "port": 502},
            status="connected",
            is_enabled=True,
            consecutive_failures=5,
            retry_max_failures=5,
        )
        session.add(ds)
        await session.commit()
        ds_id = ds.id

        await check_communication_status(session)

        result = await session.execute(select(DataSource).where(DataSource.id == ds_id))
        updated = result.scalar_one()
        assert updated.status == "interrupted"


@pytest.mark.asyncio
async def test_mark_unreliable_points():
    """受影响点位 quality 更新为 2"""
    async with TestSession() as session:
        # 创建设备
        from app.models.device import Device
        device = Device(
            device_code="DEV001",
            device_name="测试设备",
            device_type="UPS",
            area_code="A1",
        )
        session.add(device)
        await session.flush()

        # 创建点位
        point = Point(
            point_code="PT001",
            point_name="测试点位",
            point_type="AI",
            device_id=device.id,
        )
        session.add(point)
        await session.flush()

        # 创建实时值
        pr = PointRealtime(point_id=point.id, value=25.0, quality=0)
        session.add(pr)

        # 创建数据源
        ds = DataSource(
            name="测试数据源",
            protocol_type="modbus_tcp",
            connection_config={"host": "127.0.0.1", "port": 502},
            status="connected",
            is_enabled=True,
        )
        session.add(ds)
        await session.flush()

        # 创建数据源点位映射
        dsp = DataSourcePoint(
            datasource_id=ds.id,
            point_id=point.id,
            address="40001",
        )
        session.add(dsp)
        await session.commit()

        # 标记不可靠
        await mark_unreliable_points(session, ds.id, quality=2)
        await session.commit()

        result = await session.execute(
            select(PointRealtime).where(PointRealtime.point_id == point.id)
        )
        updated_pr = result.scalar_one()
        assert updated_pr.quality == 2


@pytest.mark.asyncio
async def test_communication_status_api():
    """通信状态 API 返回正确结构"""
    async with TestSession() as session:
        await _create_test_user(session)

        ds1 = DataSource(
            name="数据源A",
            protocol_type="modbus_tcp",
            connection_config={"host": "10.0.0.1", "port": 502},
            status="connected",
            is_enabled=True,
            consecutive_failures=0,
        )
        ds2 = DataSource(
            name="数据源B",
            protocol_type="snmp_v2c",
            connection_config={"host": "10.0.0.2", "port": 161},
            status="interrupted",
            is_enabled=True,
            consecutive_failures=6,
            last_communication=datetime.now() - timedelta(hours=1),
        )
        session.add_all([ds1, ds2])
        await session.commit()

    token = await _get_token()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/datasources/communication-status",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 2

        # 验证字段结构
        for item in data:
            assert "id" in item
            assert "name" in item
            assert "status" in item
            assert "affected_points" in item
            assert "affected_devices" in item
            assert "interruption_duration_seconds" in item


@pytest.mark.asyncio
async def test_communication_status_interruption_duration():
    """中断时长计算正确"""
    async with TestSession() as session:
        await _create_test_user(session)

        last_comm = datetime.now() - timedelta(hours=2, minutes=30)
        ds = DataSource(
            name="中断数据源",
            protocol_type="modbus_tcp",
            connection_config={"host": "10.0.0.3", "port": 502},
            status="interrupted",
            is_enabled=True,
            consecutive_failures=10,
            last_communication=last_comm,
        )
        session.add(ds)
        await session.commit()

    token = await _get_token()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/datasources/communication-status",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1

        item = data[0]
        assert item["interruption_duration_seconds"] is not None
        # 约 2.5 小时 = 9000 秒，允许几秒误差
        assert 8990 <= item["interruption_duration_seconds"] <= 9060
