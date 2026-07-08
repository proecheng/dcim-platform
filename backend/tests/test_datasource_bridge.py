"""DataSourcePoint 与业务 Point 绑定测试。"""

import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.gateway import DataSource, DataSourcePoint
from app.models.point import Point
from app.services.datasource_bridge import link_datasource_to_point


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite://", echo=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


async def test_link_datasource_to_point_sets_datasource_point_reference(db_session):
    ds = DataSource(
        name="FusionCol5000-A",
        protocol_type="modbus_rtu",
        connection_config={"port": "COM1", "device_id": 1},
        is_enabled=True,
    )
    db_session.add(ds)
    await db_session.flush()

    ds_point = DataSourcePoint(
        datasource_id=ds.id,
        address="HR:0x2801",
        data_type="int16",
        scale=0.1,
    )
    point = Point(
        point_code="fusioncol_current_temperature",
        point_name="Current temperature",
        point_type="AI",
        device_type="AC",
        area_code="A1",
        unit="degC",
        is_enabled=True,
    )
    db_session.add_all([ds_point, point])
    await db_session.commit()

    linked = await link_datasource_to_point(db_session, ds_point.id, point.id)

    assert linked is True
    result = await db_session.execute(select(DataSourcePoint).where(DataSourcePoint.id == ds_point.id))
    linked_ds_point = result.scalar_one()
    assert linked_ds_point.point_id == point.id

    result = await db_session.execute(select(Point).where(Point.id == point.id))
    linked_point = result.scalar_one()
    assert linked_point.energy_device_id is None
    assert linked_point.register_address == "HR:0x2801"
    assert linked_point.scale_factor == 0.1
