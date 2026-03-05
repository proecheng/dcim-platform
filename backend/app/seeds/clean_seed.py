"""清理种子数据工具

Story 28.2: 提供清理种子数据的工具

使用方法:
    python -m app.seeds.clean_seed
"""
import asyncio
from sqlalchemy import delete
from app.core.database import async_session
from app.models import Site, Floor, Room, ElectricityPricing, User, DataSourceType
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def clean_seed_data():
    """删除所有种子数据"""
    logger.info("开始清理种子数据...")

    async with async_session() as session:
        try:
            # 删除种子数据（按依赖顺序）
            result = await session.execute(delete(Room).where(Room.data_source == DataSourceType.SEED))
            logger.info(f"✓ 删除 {result.rowcount} 个种子机房")

            result = await session.execute(delete(Floor).where(Floor.data_source == DataSourceType.SEED))
            logger.info(f"✓ 删除 {result.rowcount} 个种子楼层")

            result = await session.execute(delete(Site).where(Site.data_source == DataSourceType.SEED))
            logger.info(f"✓ 删除 {result.rowcount} 个种子站点")

            result = await session.execute(delete(ElectricityPricing).where(ElectricityPricing.data_source == DataSourceType.SEED))
            logger.info(f"✓ 删除 {result.rowcount} 个种子电价配置")

            # 删除默认管理员
            result = await session.execute(delete(User).where(User.username == 'admin'))
            logger.info(f"✓ 删除 {result.rowcount} 个默认管理员用户")

            await session.commit()
            logger.info("✓ 种子数据清理完成")

        except Exception as e:
            logger.error(f"✗ 种子数据清理失败: {e}")
            await session.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(clean_seed_data())
