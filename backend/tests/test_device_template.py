"""设备模板管理测试 — Story 3.4"""
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.gateway import DeviceTemplate, DataSource, DataSourcePoint


# ============================================================
# Fixtures
# ============================================================

@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


SAMPLE_POINT_CONFIG = [
    {"address": "40001", "data_type": "float32", "scale": 1.0, "offset": 0.0, "description": "温度"},
    {"address": "40003", "data_type": "uint16", "scale": 0.1, "offset": 0.0, "description": "湿度"},
]


# ============================================================
# 测试
# ============================================================

class TestDeviceTemplate:
    """设备模板 CRUD 测试"""

    async def test_create_template(self, db_session: AsyncSession):
        """测试创建模板成功"""
        tpl = DeviceTemplate(
            name="温湿度传感器模板",
            manufacturer="海康威视",
            model="DS-TH100",
            protocol_type="modbus_tcp",
            description="温湿度传感器标准模板",
            point_config=SAMPLE_POINT_CONFIG,
        )
        db_session.add(tpl)
        await db_session.commit()
        await db_session.refresh(tpl)

        assert tpl.id is not None
        assert tpl.name == "温湿度传感器模板"
        assert tpl.manufacturer == "海康威视"
        assert tpl.model == "DS-TH100"
        assert tpl.protocol_type == "modbus_tcp"
        assert len(tpl.point_config) == 2
        assert tpl.created_at is not None

    async def test_list_templates_with_filter(self, db_session: AsyncSession):
        """测试获取模板列表（含按厂商筛选）"""
        tpl1 = DeviceTemplate(
            name="模板A", manufacturer="华为", model="M-A",
            protocol_type="modbus_tcp", point_config=[],
        )
        tpl2 = DeviceTemplate(
            name="模板B", manufacturer="海康威视", model="M-B",
            protocol_type="snmp_v2c", point_config=[],
        )
        tpl3 = DeviceTemplate(
            name="模板C", manufacturer="华为", model="M-C",
            protocol_type="modbus_rtu", point_config=[],
        )
        db_session.add_all([tpl1, tpl2, tpl3])
        await db_session.commit()

        # 查全部
        result = await db_session.execute(select(DeviceTemplate))
        all_items = result.scalars().all()
        assert len(all_items) == 3

        # 按厂商筛选
        result = await db_session.execute(
            select(DeviceTemplate).where(DeviceTemplate.manufacturer == "华为")
        )
        huawei_items = result.scalars().all()
        assert len(huawei_items) == 2
        assert all(t.manufacturer == "华为" for t in huawei_items)

    async def test_update_template(self, db_session: AsyncSession):
        """测试更新模板"""
        tpl = DeviceTemplate(
            name="原始名称", manufacturer="厂商A", model="型号A",
            protocol_type="modbus_tcp", point_config=[],
        )
        db_session.add(tpl)
        await db_session.commit()
        await db_session.refresh(tpl)

        tpl.name = "更新后名称"
        tpl.description = "新增描述"
        await db_session.commit()
        await db_session.refresh(tpl)

        assert tpl.name == "更新后名称"
        assert tpl.description == "新增描述"

    async def test_delete_template(self, db_session: AsyncSession):
        """测试删除模板"""
        tpl = DeviceTemplate(
            name="待删除", manufacturer="厂商", model="型号",
            protocol_type="snmp_v2c", point_config=[],
        )
        db_session.add(tpl)
        await db_session.commit()
        tpl_id = tpl.id

        await db_session.delete(tpl)
        await db_session.commit()

        result = await db_session.execute(
            select(DeviceTemplate).where(DeviceTemplate.id == tpl_id)
        )
        assert result.scalar_one_or_none() is None

    async def test_template_not_found(self, db_session: AsyncSession):
        """测试模板不存在返回 None"""
        result = await db_session.execute(
            select(DeviceTemplate).where(DeviceTemplate.id == 99999)
        )
        assert result.scalar_one_or_none() is None

    async def test_create_datasource_from_template(self, db_session: AsyncSession):
        """测试从模板创建数据源（验证 DataSourcePoint 自动填充）"""
        tpl = DeviceTemplate(
            name="UPS模板", manufacturer="施耐德", model="APC-3000",
            protocol_type="modbus_tcp",
            point_config=SAMPLE_POINT_CONFIG,
        )
        db_session.add(tpl)
        await db_session.commit()
        await db_session.refresh(tpl)

        # 创建数据源
        ds = DataSource(
            name="UPS-01",
            protocol_type=tpl.protocol_type,
            connection_config={"host": "192.168.1.100", "port": 502},
            collection_interval=5,
        )
        db_session.add(ds)
        await db_session.flush()

        # 从模板填充点位
        for pt_cfg in tpl.point_config:
            point = DataSourcePoint(
                datasource_id=ds.id,
                address=str(pt_cfg.get("address", "")),
                data_type=pt_cfg.get("data_type"),
                scale=float(pt_cfg.get("scale", 1.0)),
                offset=float(pt_cfg.get("offset", 0.0)),
            )
            db_session.add(point)

        await db_session.commit()
        await db_session.refresh(ds)

        # 验证数据源
        assert ds.id is not None
        assert ds.name == "UPS-01"
        assert ds.protocol_type == "modbus_tcp"

        # 验证点位自动填充
        result = await db_session.execute(
            select(DataSourcePoint).where(DataSourcePoint.datasource_id == ds.id)
        )
        points = result.scalars().all()
        assert len(points) == 2
        assert points[0].address == "40001"
        assert points[0].data_type == "float32"
        assert points[1].address == "40003"
        assert points[1].scale == 0.1

    async def test_create_datasource_from_nonexistent_template(self, db_session: AsyncSession):
        """测试从不存在的模板创建数据源（查询返回 None）"""
        result = await db_session.execute(
            select(DeviceTemplate).where(DeviceTemplate.id == 99999)
        )
        template = result.scalar_one_or_none()
        assert template is None
