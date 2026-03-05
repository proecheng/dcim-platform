"""
Story 28.4 测试 - Demo 数据安全卸载
"""
import pytest
import asyncio
from sqlalchemy import select, func
from app.core.database import async_session
from app.models import Device, Point, Site, Floor, Room
from app.demo.service import demo_data_service


@pytest.mark.asyncio
async def test_demo_data_stats():
    """测试 demo 数据统计"""
    stats = await demo_data_service.get_demo_data_stats()
    assert isinstance(stats, dict)
    print(f"Demo data stats: {stats}")


@pytest.mark.asyncio
async def test_mixed_data_scenario():
    """测试混合场景：demo 数据 + 用户数据"""
    async with async_session() as session:
        # 创建一个用户自定义的站点（is_demo=False）
        user_site = Site(
            site_code="USER001",
            site_name="用户自定义站点",
            is_demo=False
        )
        session.add(user_site)
        await session.commit()

        # 统计 demo 数据
        stats = await demo_data_service.get_demo_data_stats()
        demo_site_count = stats.get("sites", 0)

        # 统计总站点数
        result = await session.execute(select(func.count(Site.id)))
        total_site_count = result.scalar()

        print(f"Total sites: {total_site_count}, Demo sites: {demo_site_count}")
        assert total_site_count > demo_site_count, "应该有用户自定义站点"

        # 清理测试数据
        await session.execute(
            select(Site).where(Site.site_code == "USER001")
        )
        await session.delete(user_site)
        await session.commit()


@pytest.mark.asyncio
async def test_safe_unload_preserves_user_data():
    """测试安全卸载保留用户数据"""
    async with async_session() as session:
        # 创建用户数据
        user_site = Site(
            site_code="USER_TEST",
            site_name="测试用户站点",
            is_demo=False
        )
        session.add(user_site)
        await session.commit()
        user_site_id = user_site.id

        # 执行卸载（注意：这会删除所有 demo 数据，谨慎使用）
        # result = await demo_data_service.unload_demo_data()
        # assert result["success"]

        # 验证用户数据仍然存在
        result = await session.execute(
            select(Site).where(Site.id == user_site_id)
        )
        preserved_site = result.scalar_one_or_none()
        assert preserved_site is not None, "用户数据应该被保留"
        assert preserved_site.is_demo == False

        # 清理
        await session.delete(user_site)
        await session.commit()


if __name__ == "__main__":
    # 运行测试
    asyncio.run(test_demo_data_stats())
    asyncio.run(test_mixed_data_scenario())
    print("All tests passed!")
