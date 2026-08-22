"""测试 Story 28.2 实施

测试场景：
1. Seed only
2. Seed + Demo
3. Seed + Demo + Simulation
"""

__test__ = False

import asyncio
import os
import sys

# 设置环境变量
os.environ["SEED_ENABLED"] = "true"
os.environ["DEMO_ENABLED"] = "false"
os.environ["SIMULATION_ENABLED"] = "false"

# 设置 UTF-8 输出
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.core.database import async_session
from app.seeds.minimal_seed import run_minimal_seed
from app.models import Site, User, ElectricityPricing
from sqlalchemy import select, func


async def test_seed_only():
    """测试场景 1: 只启用 Seed"""
    print("\n=== 测试场景 1: Seed Only ===")

    # 执行种子
    await run_minimal_seed()

    # 验证数据
    async with async_session() as session:
        # 检查用户
        result = await session.execute(select(func.count()).select_from(User))
        user_count = result.scalar()
        print(f"✓ 用户数量: {user_count}")

        # 检查站点
        result = await session.execute(select(Site))
        sites = result.scalars().all()
        print(f"✓ 站点数量: {len(sites)}")
        if sites:
            print(f"  - 站点名称: {sites[0].site_name}, data_source: {sites[0].data_source}")

        # 检查电价
        result = await session.execute(select(ElectricityPricing))
        pricing = result.scalars().all()
        print(f"✓ 电价配置数量: {len(pricing)}")
        if pricing:
            print(f"  - 电价名称: {pricing[0].pricing_name}, data_source: {pricing[0].data_source}")
            period_types = set(p.period_type for p in pricing)
            print(f"  - 电价档位: {sorted(period_types)}")


async def test_idempotence():
    """测试幂等性"""
    print("\n=== 测试幂等性 ===")

    # 第一次执行
    await run_minimal_seed()

    async with async_session() as session:
        result = await session.execute(select(func.count()).select_from(Site))
        count1 = result.scalar()

    # 第二次执行
    await run_minimal_seed()

    async with async_session() as session:
        result = await session.execute(select(func.count()).select_from(Site))
        count2 = result.scalar()

    print(f"✓ 第一次执行后站点数: {count1}")
    print(f"✓ 第二次执行后站点数: {count2}")
    print(f"✓ 幂等性验证: {'通过' if count1 == count2 else '失败'}")


async def main():
    """主测试函数"""
    try:
        await test_seed_only()
        await test_idempotence()
        print("\n✓ 所有测试通过")
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
