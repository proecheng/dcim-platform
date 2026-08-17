"""最小化种子 - 创建系统运行所需的最小配置

Story 28.2: Demo 配置分离与最小化种子
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.database import async_session
from app.core.config import get_settings
from app.core.security import get_password_hash
from app.models import Site, Floor, Room, ElectricityPricing, User, DataSourceType, PricingPeriodType
from datetime import date
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

# 常量
DEFAULT_SITE_CODE = "DEFAULT"
DEFAULT_PRICING_NAME = "默认五级分时电价"


async def run_minimal_seed():
    """执行最小化种子（幂等，分阶段提交）"""
    if not settings.seed_enabled:
        raise RuntimeError("SEED_ENABLED must be true to run the minimal seed")

    logger.info("开始执行最小化种子...")

    # 阶段 1: 创建默认管理员用户（独立事务）
    try:
        await _create_default_admin_user()
    except Exception as e:
        logger.error(f"创建默认管理员用户失败: {e}")
        # 用户创建失败不影响后续阶段

    # 阶段 2: 创建站点、机房、电价（同一事务）
    try:
        async with async_session() as session:
            # 检查是否首次启动
            is_first_run = await _is_first_run(session)

            if is_first_run:
                logger.info("检测到首次启动，执行完整种子...")
            else:
                logger.info("检测到已有数据，执行幂等检查...")

            # 1. 创建默认站点
            site = await _create_default_site(session)

            # 2. 创建基础空间结构
            await _create_default_floors_and_rooms(session, site.id)

            # 3. 创建默认电价配置
            await _create_default_pricing(session)

            await session.commit()
            logger.info("✓ 最小化种子执行完成")

    except Exception as e:
        logger.error(f"✗ 最小化种子执行失败: {e}")
        raise


async def _is_first_run(session: AsyncSession) -> bool:
    """检查是否首次启动（数据库为空）"""
    result = await session.execute(select(func.count()).select_from(Site))
    count = result.scalar()
    return count == 0


async def _create_default_admin_user():
    """创建默认管理员用户（幂等，独立事务）"""
    async with async_session() as session:
        result = await session.execute(select(User).where(User.username == "admin"))
        user = result.scalar_one_or_none()

        if user:
            logger.info("默认管理员用户已存在: admin")
            return

        user = User(
            username="admin",
            hashed_password=get_password_hash(settings.default_admin_password),
            role="admin",
            is_active=True,
        )
        session.add(user)
        await session.commit()
        logger.info("✓ 创建默认管理员用户: admin")
        logger.warning("默认管理员用户已创建；请按凭据管理流程保存其密码")


async def _create_default_site(session: AsyncSession) -> Site:
    """创建默认站点（幂等）"""
    result = await session.execute(select(Site).where(Site.site_code == DEFAULT_SITE_CODE))
    site = result.scalar_one_or_none()

    if site:
        logger.info(f"默认站点已存在: {site.site_name}")
        return site

    site = Site(
        site_name=settings.default_site_name, site_code=DEFAULT_SITE_CODE, address="", data_source=DataSourceType.SEED
    )
    session.add(site)
    await session.flush()
    logger.info(f"✓ 创建默认站点: {site.site_name}")
    return site


async def _create_default_floors_and_rooms(session: AsyncSession, site_id: int):
    """创建基础空间结构（幂等）"""
    for floor_num in range(1, settings.default_floor_count + 1):
        floor_code = f"{floor_num}F"
        # 检查楼层是否存在
        result = await session.execute(select(Floor).where(Floor.site_id == site_id, Floor.floor_code == floor_code))
        floor = result.scalar_one_or_none()

        if not floor:
            floor = Floor(
                site_id=site_id,
                floor_name=f"{floor_num}F",
                floor_code=floor_code,
                sort_order=floor_num,
                data_source=DataSourceType.SEED,
            )
            session.add(floor)
            await session.flush()
            logger.info(f"✓ 创建楼层: {floor.floor_name}")

        # 创建机房（使用 ROOM_001 格式）
        for room_num in range(1, settings.default_room_count + 1):
            room_code = f"ROOM_{room_num:03d}"
            result = await session.execute(select(Room).where(Room.floor_id == floor.id, Room.room_code == room_code))
            room = result.scalar_one_or_none()

            if not room:
                room = Room(
                    floor_id=floor.id,
                    room_name=f"机房{room_num:03d}",
                    room_code=room_code,
                    data_source=DataSourceType.SEED,
                )
                session.add(room)
                logger.info(f"✓ 创建机房: {room.room_name}")


async def _create_default_pricing(session: AsyncSession):
    """创建默认五级电价配置（幂等）"""
    result = await session.execute(
        select(func.count())
        .select_from(ElectricityPricing)
        .where(ElectricityPricing.pricing_name == DEFAULT_PRICING_NAME)
    )
    count = result.scalar()

    if count > 0:
        logger.info("默认电价配置已存在")
        return

    # 五级分时电价（中国典型）
    # 尖峰: 10-12, 18-21 (5h)
    # 峰: 8-10, 14-18 (6h)
    # 平: 7-8, 12-14, 21-23 (5h)
    # 谷: 6-7, 23-24 (2h)
    # 深谷: 0-6 (6h)

    pricing_periods = [
        # 尖峰时段
        {
            "period_type": PricingPeriodType.SHARP_PEAK,
            "start_time": "10:00",
            "end_time": "12:00",
            "price": settings.default_sharp_peak_price,
        },
        {
            "period_type": PricingPeriodType.SHARP_PEAK,
            "start_time": "18:00",
            "end_time": "21:00",
            "price": settings.default_sharp_peak_price,
        },
        # 峰时段
        {
            "period_type": PricingPeriodType.PEAK,
            "start_time": "08:00",
            "end_time": "10:00",
            "price": settings.default_peak_price,
        },
        {
            "period_type": PricingPeriodType.PEAK,
            "start_time": "14:00",
            "end_time": "18:00",
            "price": settings.default_peak_price,
        },
        # 平时段
        {
            "period_type": PricingPeriodType.FLAT,
            "start_time": "07:00",
            "end_time": "08:00",
            "price": settings.default_flat_price,
        },
        {
            "period_type": PricingPeriodType.FLAT,
            "start_time": "12:00",
            "end_time": "14:00",
            "price": settings.default_flat_price,
        },
        {
            "period_type": PricingPeriodType.FLAT,
            "start_time": "21:00",
            "end_time": "23:00",
            "price": settings.default_flat_price,
        },
        # 谷时段
        {
            "period_type": PricingPeriodType.VALLEY,
            "start_time": "06:00",
            "end_time": "07:00",
            "price": settings.default_valley_price,
        },
        {
            "period_type": PricingPeriodType.VALLEY,
            "start_time": "23:00",
            "end_time": "24:00",
            "price": settings.default_valley_price,
        },
        # 深谷时段
        {
            "period_type": PricingPeriodType.DEEP_VALLEY,
            "start_time": "00:00",
            "end_time": "06:00",
            "price": settings.default_deep_valley_price,
        },
    ]

    effective_date = date.today()

    for period in pricing_periods:
        pricing = ElectricityPricing(
            pricing_name=DEFAULT_PRICING_NAME,
            period_type=period["period_type"],
            start_time=period["start_time"],
            end_time=period["end_time"],
            price=period["price"],
            effective_date=effective_date,
            is_enabled=True,
            data_source=DataSourceType.SEED,
        )
        session.add(pricing)

    logger.info("✓ 创建默认五级电价配置")
