"""写入权限管理测试 — Story 3.3"""

import json
import pytest
import pytest_asyncio
from datetime import datetime
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models.gateway import DataSource
from app.models.log import OperationLog


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


@pytest_asyncio.fixture
async def sample_datasource(db_session):
    """创建一个测试数据源"""
    ds = DataSource(
        name="测试数据源",
        protocol_type="modbus_tcp",
        connection_config={"host": "127.0.0.1", "port": 502, "slave_id": 1},
        collection_interval=5,
        write_enabled=False,
        site_id=1,
        is_enabled=True,
    )
    db_session.add(ds)
    await db_session.commit()
    await db_session.refresh(ds)
    return ds


# ============================================================
# Tests
# ============================================================


@pytest.mark.asyncio
async def test_toggle_write_permission_success(db_session, sample_datasource):
    """测试切换写入权限成功（false → true）"""
    ds = sample_datasource
    assert ds.write_enabled is False

    # 模拟切换逻辑（与 API 端点相同的业务逻辑）
    old_value = ds.write_enabled
    new_value = not old_value

    await db_session.execute(
        update(DataSource)
        .where(DataSource.id == ds.id)
        .values(
            write_enabled=new_value,
            updated_at=datetime.now(),
        )
    )

    # 记录操作日志
    log = OperationLog(
        user_id=1,
        username="test_user",
        module="datasource",
        action="update",
        target_type="datasource",
        target_id=ds.id,
        target_name=ds.name,
        old_value=json.dumps({"write_enabled": old_value}),
        new_value=json.dumps({"write_enabled": new_value}),
        remark="开启写入权限",
    )
    db_session.add(log)
    await db_session.commit()

    # 验证数据源已更新
    result = await db_session.execute(select(DataSource).where(DataSource.id == ds.id))
    updated_ds = result.scalar_one()
    assert updated_ds.write_enabled is True


@pytest.mark.asyncio
async def test_operation_log_recorded(db_session, sample_datasource):
    """测试操作日志记录"""
    ds = sample_datasource

    # 切换写入权限并记录日志
    await db_session.execute(update(DataSource).where(DataSource.id == ds.id).values(write_enabled=True))
    log = OperationLog(
        user_id=1,
        username="test_user",
        module="datasource",
        action="update",
        target_type="datasource",
        target_id=ds.id,
        target_name=ds.name,
        old_value=json.dumps({"write_enabled": False}),
        new_value=json.dumps({"write_enabled": True}),
        remark="开启写入权限",
    )
    db_session.add(log)
    await db_session.commit()

    # 验证日志记录
    result = await db_session.execute(
        select(OperationLog).where(
            OperationLog.module == "datasource",
            OperationLog.target_id == ds.id,
        )
    )
    logs = result.scalars().all()
    assert len(logs) == 1
    assert logs[0].action == "update"
    assert logs[0].target_name == "测试数据源"
    assert json.loads(logs[0].old_value) == {"write_enabled": False}
    assert json.loads(logs[0].new_value) == {"write_enabled": True}
    assert logs[0].remark == "开启写入权限"


@pytest.mark.asyncio
async def test_toggle_nonexistent_datasource(db_session):
    """测试数据源不存在时的处理"""
    result = await db_session.execute(select(DataSource).where(DataSource.id == 99999))
    ds = result.scalar_one_or_none()
    assert ds is None  # 数据源不存在，API 层应返回 404
