"""
算力中心智能监控系统 - 主入口
V2.0 架构重构版
"""

import asyncio
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text

from .core.config import get_settings, parse_cors_origins, validate_production_settings
from .core.authorization import validate_authorization_inventory
from .core.database import init_db, async_session
from .models import User
from .api.v1 import api_router
from .api.deps import authenticate_access_token, build_site_access_context, enforce_inventory_authorization
from .services.websocket import ConnectionContext, WebSocketAuthorizationContext, ws_manager
from .demo.lifecycle import startup as demo_startup, shutdown as demo_shutdown
from .core.redis import redis_service
from .services.observability import run_observability_monitor
from .engines.alarm_engine import alarm_engine
from .engines.linkage_engine import linkage_engine
from .engines.event_bus import get_event_bus
from .services.communication_monitor import check_communication_status
from .services.gateway_monitor import check_mstp_gateway_health
from .engines.escalation_engine import check_escalations
from .engines.diagnosis_engine import diagnosis_engine
from .services.pue_calculator import write_pue_history
from .services.energy_aggregator import aggregate_hourly, aggregate_daily, aggregate_monthly
from .services.load_shift.shift_constraint_service import ShiftConstraintService
from .middleware.request_logging import RequestLoggingMiddleware
from .middleware.metrics_middleware import MetricsMiddleware
from .middleware.metrics import metrics_collector
from .middleware.error_handler import register_exception_handlers

import logging

logger = logging.getLogger(__name__)

settings = get_settings()


async def verify_websocket_token(token: str, channel: str, *, db=None) -> WebSocketAuthorizationContext | None:
    """返回严格活动会话授权上下文，不向连接池暴露原始令牌。"""
    if not isinstance(token, str) or not token:
        return None

    async def _verify(session):
        identity = await authenticate_access_token(token, session)
        site_context = await build_site_access_context(identity.user, identity.jti, session)
        return WebSocketAuthorizationContext(
            user_id=identity.user.id,
            jti=identity.jti,
            role=identity.user.role,
            allowed_site_ids=site_context.site_ids,
            channel=channel,
            username=identity.user.username,
            expires_at=identity.expires_at,
        )

    try:
        if db is not None:
            return await _verify(db)
        async with async_session() as session:
            return await _verify(session)
    except HTTPException:
        return None


async def init_default_data():
    """初始化不包含用户凭据的兼容数据。"""
    async with async_session() as session:
        # 初始化角色权限
        from .models import RolePermission

        permissions_result = await session.execute(select(RolePermission))
        if not permissions_result.scalars().all():
            default_permissions = [
                # admin 权限 — 全部资源完整访问
                ("admin", "user:read"),
                ("admin", "user:write"),
                ("admin", "user:delete"),
                ("admin", "point:read"),
                ("admin", "point:write"),
                ("admin", "point:delete"),
                ("admin", "alarm:read"),
                ("admin", "alarm:write"),
                ("admin", "alarm:ack"),
                ("admin", "config:read"),
                ("admin", "config:write"),
                ("admin", "log:read"),
                ("admin", "report:read"),
                ("admin", "report:write"),
                ("admin", "device:read"),
                ("admin", "device:write"),
                ("admin", "device:delete"),
                ("admin", "gateway:read"),
                ("admin", "gateway:write"),
                ("admin", "gateway:delete"),
                ("admin", "energy:read"),
                ("admin", "energy:write"),
                ("admin", "asset:read"),
                ("admin", "asset:write"),
                ("admin", "asset:delete"),
                ("admin", "linkage:read"),
                ("admin", "linkage:write"),
                ("admin", "linkage:delete"),
                ("admin", "diagnosis:read"),
                ("admin", "diagnosis:write"),
                ("admin", "video:read"),
                ("admin", "video:write"),
                ("admin", "site:read"),
                ("admin", "site:write"),
                ("admin", "site:delete"),
                # operator 权限 — 采集配置、策略引擎、运维管理
                ("operator", "point:read"),
                ("operator", "point:write"),
                ("operator", "alarm:read"),
                ("operator", "alarm:ack"),
                ("operator", "report:read"),
                ("operator", "report:write"),
                ("operator", "device:read"),
                ("operator", "device:write"),
                ("operator", "gateway:read"),
                ("operator", "gateway:write"),
                ("operator", "energy:read"),
                ("operator", "energy:write"),
                ("operator", "asset:read"),
                ("operator", "asset:write"),
                ("operator", "linkage:read"),
                ("operator", "linkage:write"),
                ("operator", "diagnosis:read"),
                ("operator", "diagnosis:write"),
                ("operator", "video:read"),
                ("operator", "video:write"),
                ("operator", "site:read"),
                ("operator", "config:read"),
                # viewer 权限 — 监控域 + 管理域只读
                ("viewer", "point:read"),
                ("viewer", "alarm:read"),
                ("viewer", "report:read"),
                ("viewer", "device:read"),
                ("viewer", "energy:read"),
                ("viewer", "asset:read"),
                ("viewer", "video:read"),
                ("viewer", "site:read"),
            ]
            for role, permission in default_permissions:
                perm = RolePermission(role=role, permission=permission)
                session.add(perm)
            await session.commit()
            print("初始化角色权限配置")

        # 初始化负荷转移默认约束（算力中心特殊约束）
        stats = await ShiftConstraintService.ensure_default_constraints(session)
        if stats["created"] > 0:
            print(f"初始化负荷转移默认约束: 新增 {stats['created']} 条")


async def init_default_configs():
    """初始化默认系统配置"""
    async with async_session() as session:
        from .models import SystemConfig, Dictionary

        # 检查是否已有配置
        result = await session.execute(select(SystemConfig))
        if not result.scalars().all():
            default_configs = [
                ("system", "app_name", "算力中心智能监控系统", "string", "系统名称"),
                ("system", "app_version", "2.0.0", "string", "系统版本"),
                ("alarm", "sound_enabled", "true", "boolean", "告警声音开关"),
                ("alarm", "popup_enabled", "true", "boolean", "告警弹窗开关"),
                ("data", "history_retention_days", "30", "number", "历史数据保留天数"),
                ("data", "collect_interval", "5", "number", "数据采集间隔(秒)"),
            ]
            for group, key, value, vtype, desc in default_configs:
                config = SystemConfig(
                    config_group=group, config_key=key, config_value=value, value_type=vtype, description=desc
                )
                session.add(config)
            await session.commit()
            print("初始化系统配置")

        # 初始化数据字典
        dict_result = await session.execute(select(Dictionary))
        if not dict_result.scalars().all():
            default_dicts = [
                ("device_type", "UPS", "UPS电源", None, 1),
                ("device_type", "AC", "精密空调", None, 2),
                ("device_type", "PDU", "配电柜", None, 3),
                ("device_type", "TH", "温湿度传感器", None, 4),
                ("device_type", "DOOR", "门禁", None, 5),
                ("device_type", "SMOKE", "烟感", None, 6),
                ("device_type", "WATER", "漏水检测", None, 7),
                ("point_type", "AI", "模拟量输入", None, 1),
                ("point_type", "DI", "开关量输入", None, 2),
                ("point_type", "AO", "模拟量输出", None, 3),
                ("point_type", "DO", "开关量输出", None, 4),
                ("alarm_level", "critical", "紧急", "#ff4d4f", 1),
                ("alarm_level", "major", "重要", "#faad14", 2),
                ("alarm_level", "minor", "次要", "#1890ff", 3),
                ("alarm_level", "info", "提示", "#8c8c8c", 4),
            ]
            for dtype, code, name, value, sort in default_dicts:
                d = Dictionary(dict_type=dtype, dict_code=code, dict_name=name, dict_value=value, sort_order=sort)
                session.add(d)
            await session.commit()
            print("初始化数据字典")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 配置和清单漂移时，在数据库或任何监听器之前失败。
    validate_production_settings(settings)
    validate_authorization_inventory(app)

    """应用生命周期管理 - Story 28.2: 分层启动"""
    # 启动时初始化数据库
    await init_db()

    # Story 29.3: 初始化 THM 配置项
    try:
        from app.models.config import SystemConfig

        async with async_session() as session:
            thm_configs = {
                "thm_safety_factor": "0.8",
                "thm_absolute_max_ratio": "0.6",
                "thm_min_headroom_celsius": "2.0",
            }

            for key, value in thm_configs.items():
                existing = (
                    await session.execute(
                        select(SystemConfig).where(
                            SystemConfig.config_group == "thm",
                            SystemConfig.config_key == key,
                        )
                    )
                ).scalar_one_or_none()

                if existing is None:
                    new_config = SystemConfig(
                        config_group="thm",
                        config_key=key,
                        config_value=value,
                        value_type="number",
                        description=f"THM 参数: {key}",
                    )
                    session.add(new_config)
                    logger.info(f"✓ 初始化 THM 配置项: {key}={value}")

            await session.commit()
    except Exception as e:
        logger.warning(f"⚠️  THM 配置项初始化失败: {e}")

    # Story 30.1: 初始化约束检查配置项
    try:
        from app.models.config import SystemConfig as SysConfig301
        from app.core.database import async_session as async_session_301

        async with async_session_301() as session:
            constraint_configs = {
                "constraint_temp_max": "27.0",
                "constraint_temp_min": "18.0",
                "constraint_power_multiplier": "1.5",
                "constraint_rate_limit": "5.0",
            }

            for key, value in constraint_configs.items():
                existing = (
                    await session.execute(select(SysConfig301).where(SysConfig301.config_key == key))
                ).scalar_one_or_none()

                if existing is None:
                    new_config = SysConfig301(
                        config_group="constraint",
                        config_key=key,
                        config_value=value,
                        value_type="number",
                        description=f"约束检查参数: {key}",
                    )
                    session.add(new_config)
                    logger.info(f"✓ 初始化约束配置项: {key}={value}")

            await session.commit()
    except Exception as e:
        logger.warning(f"⚠️  约束配置项初始化失败: {e}")

    # Story 30.2: 初始化回退保护配置项
    try:
        from app.models.config import SystemConfig as SysConfig302
        from app.core.database import async_session as async_session_302

        async with async_session_302() as session:
            rollback_configs = {
                "rollback_predicted_rate": "2.0",
            }

            for key, value in rollback_configs.items():
                existing = (
                    await session.execute(select(SysConfig302).where(SysConfig302.config_key == key))
                ).scalar_one_or_none()

                if existing is None:
                    new_config = SysConfig302(
                        config_group="rollback",
                        config_key=key,
                        config_value=value,
                        value_type="number",
                        description=f"回退保护参数: {key}",
                    )
                    session.add(new_config)
                    logger.info(f"✓ 初始化回退配置项: {key}={value}")

            await session.commit()
    except Exception as e:
        logger.warning(f"⚠️  回退配置项初始化失败: {e}")

    # 初始化邮件服务（Story 26.2）
    if settings.smtp_enabled:
        from app.services.email_service import email_service

        email_service.configure(
            smtp_host=settings.smtp_host,
            smtp_port=settings.smtp_port,
            smtp_user=settings.smtp_user,
            smtp_password=settings.smtp_password,
            from_email=settings.smtp_from_email,
        )
        logger.info("✓ 邮件服务已配置")

    # === Story 28.2: 分层启动 ===
    seed_success = False

    # 1. Seed 阶段
    if settings.seed_enabled:
        logger.info("=== Seed 阶段：执行最小化种子 ===")
        try:
            from app.seeds.minimal_seed import run_minimal_seed

            await run_minimal_seed()
            logger.info("✓ 最小化种子执行成功")
            seed_success = True
        except Exception as e:
            logger.error(f"✗ 最小化种子执行失败: {e}")
            seed_success = False
    else:
        # 如果未启用 seed，执行旧的默认数据初始化（向后兼容）
        await init_default_data()
        await init_default_configs()

    # 2. Demo 阶段
    if settings.demo_enabled:
        if not settings.seed_enabled or seed_success:
            logger.info("=== Demo 阶段：加载 Demo 数据 ===")
            try:
                await demo_startup()
                logger.info("✓ Demo 数据加载成功")
            except Exception as e:
                logger.error(f"✗ Demo 数据加载失败: {e}")
        else:
            logger.warning("⚠️  Seed 阶段失败，跳过 Demo 阶段")

    # 3. Simulation 阶段
    if settings.simulation_enabled:
        logger.info("=== Simulation 阶段：启动数据模拟器 ===")
        try:
            # 模拟器启动逻辑在 demo_startup() 中处理
            if not settings.demo_enabled:
                # 如果 demo 未启用，单独启动模拟器
                from app.demo.lifecycle import start_simulator

                await start_simulator()
            logger.info("✓ 数据模拟器启动成功")
        except Exception as e:
            logger.error(f"✗ 数据模拟器启动失败: {e}")

    # 连接 Redis 缓存
    if settings.redis_enabled:
        await redis_service.connect(settings.effective_redis_url)

    # 加载告警引擎阈值缓存
    await alarm_engine.load_thresholds()

    # 加载传感器元数据缓存（Story 25.5）
    try:
        from app.services.diagnosis.sensor_metadata_service import SensorMetadataCache

        async with async_session() as session:
            await SensorMetadataCache.load_all(session)
        logger.info("✓ 传感器元数据缓存加载成功")
    except Exception as e:
        logger.error(f"✗ 传感器元数据缓存加载失败: {e}")

    # 同步消防策略 YAML 到数据库（Story 9-2） — 仅演示模式
    from .demo.config import is_demo_enabled

    if is_demo_enabled():
        try:
            from .services.fire_protection import sync_to_database as fp_sync

            async with async_session() as session:
                await fp_sync(session)
        except Exception as e:
            logger.warning("消防策略同步失败: %s", e)

    # 加载联动引擎策略缓存并订阅事件
    await linkage_engine.load_policies()
    event_bus = get_event_bus()

    # 订阅交叉确认服务（Story 9-2）
    from .engines.cross_confirmation import cross_confirmation_service

    await event_bus.subscribe("linkage", cross_confirmation_service.on_alarm_event)

    await event_bus.subscribe("linkage", linkage_engine.on_event)

    # 同步诊断规则 YAML 到数据库并启动诊断引擎（Story 9-3） — 仅演示模式
    if is_demo_enabled():
        try:
            from .services.diagnosis_loader import sync_to_database as diag_sync

            async with async_session() as session:
                await diag_sync(session)
        except Exception as e:
            logger.warning("诊断规则同步失败: %s", e)

    await diagnosis_engine.load_rules()
    await event_bus.subscribe("linkage", diagnosis_engine.on_alarm_event)

    # 初始化配电拓扑图（Story 25.1）
    try:
        from app.services.diagnosis.power_topology_service import initialize_power_topology_graph

        await initialize_power_topology_graph()
        logger.info("✓ 配电拓扑图初始化成功")
    except Exception as e:
        logger.error(f"✗ 配电拓扑图初始化失败: {e}")

    # 启动拓扑变更监听器（Story 25.1）
    listener_task = None
    if settings.redis_enabled:
        from app.services.diagnosis.device_sync_service import start_device_sync_listener, stop_device_sync_listener

        listener_task = asyncio.create_task(start_device_sync_listener())

    # 启动传感器元数据 Redis 监听器（Story 25.5）
    redis_listener_task = None
    if settings.redis_enabled:
        try:
            from app.services.diagnosis.sensor_metadata_service import SensorMetadataCache

            redis_listener_task = await SensorMetadataCache.start_listener()
            logger.info("✓ 传感器元数据 Redis 监听器启动成功")
        except Exception as e:
            logger.error(f"✗ 传感器元数据 Redis 监听器启动失败: {e}")

    # 启动告警引擎定时刷新（每 30 秒检查阈值版本）
    async def _alarm_engine_refresh_loop():
        while True:
            await asyncio.sleep(30)
            try:
                await alarm_engine.check_version()
            except Exception as e:
                logger.warning("告警引擎刷新失败: %s", e)

    refresh_task = asyncio.create_task(_alarm_engine_refresh_loop())

    # 启动通信监控定时检查（每 30 秒）
    async def _communication_monitor_loop():
        while True:
            await asyncio.sleep(30)
            try:
                async with async_session() as session:
                    await check_communication_status(session)
            except Exception as e:
                logger.warning("通信监控检查失败: %s", e)

    comm_monitor_task = asyncio.create_task(_communication_monitor_loop())

    # 启动 MS/TP 网关健康检查（每 30 秒，初始延迟 45s 错开通信监控）— Story 35.2
    async def _mstp_gateway_health_loop():
        await asyncio.sleep(45)  # 错开 comm_monitor 的 30s 周期
        while True:
            await asyncio.sleep(30)
            try:
                async with async_session() as session:
                    await check_mstp_gateway_health(session)
            except Exception as e:
                logger.warning("MS/TP 网关健康检查失败: %s", e)

    mstp_health_task = asyncio.create_task(_mstp_gateway_health_loop())

    # 启动告警升级引擎（每 60 秒检查）
    async def _escalation_engine_loop():
        while True:
            await asyncio.sleep(60)
            try:
                async with async_session() as session:
                    await check_escalations(session)
            except Exception as e:
                logger.warning("告警升级检查失败: %s", e)

    escalation_task = asyncio.create_task(_escalation_engine_loop())

    # 启动渠道升级扫描（每 60 秒检查）— Story 34.5
    async def _channel_escalation_loop():
        while True:
            await asyncio.sleep(60)
            try:
                async with async_session() as session:
                    from app.services.notification.dispatcher import check_channel_escalations

                    await check_channel_escalations(session)
            except Exception as e:
                logger.warning("渠道升级检查失败: %s", e)

    channel_escalation_task = asyncio.create_task(_channel_escalation_loop())

    # 启动 PUE 历史记录定时写入（每 15 分钟）
    async def _pue_history_loop():
        await asyncio.sleep(10)  # 启动后短暂等待
        # 先执行一次
        try:
            async with async_session() as session:
                await write_pue_history(session)
        except Exception as e:
            logger.warning("PUE历史写入失败: %s", e)
        while True:
            await asyncio.sleep(900)  # 15分钟
            try:
                async with async_session() as session:
                    await write_pue_history(session)
            except Exception as e:
                logger.warning("PUE历史写入失败: %s", e)

    pue_history_task = asyncio.create_task(_pue_history_loop())

    # 启动能耗数据聚合定时任务
    async def _energy_aggregation_loop():
        await asyncio.sleep(30)  # 启动后等待
        _last_daily_date = None
        _last_monthly_key = None
        while True:
            # 小时聚合（每次循环都执行）
            try:
                async with async_session() as session:
                    await aggregate_hourly(session)
            except Exception as e:
                logger.warning("小时能耗聚合失败: %s", e)
            # 日聚合（每天执行一次，聚合前一天）
            today = datetime.now().date()
            if _last_daily_date != today:
                try:
                    async with async_session() as session:
                        await aggregate_daily(session)
                    _last_daily_date = today
                except Exception as e:
                    logger.warning("日能耗聚合失败: %s", e)
            # 月聚合（每月执行一次，聚合上月）
            month_key = (today.year, today.month)
            if _last_monthly_key != month_key:
                try:
                    async with async_session() as session:
                        await aggregate_monthly(session)
                    _last_monthly_key = month_key
                except Exception as e:
                    logger.warning("月能耗聚合失败: %s", e)
            await asyncio.sleep(1800)  # 30分钟检查一次

    energy_agg_task = asyncio.create_task(_energy_aggregation_loop())

    # 启动节能机会自动检测定时任务（每小时执行）
    async def _opportunity_detection_loop():
        """节能机会自动检测定时任务 - 每小时执行"""
        await asyncio.sleep(60)
        while True:
            try:
                async with async_session() as db:
                    from .services.opportunity_detector import OpportunityDetector

                    detector = OpportunityDetector(db)
                    result = await detector.run_detection()
                    logger.info(f"节能机会自动检测完成: 新发现{result.get('new_opportunities', 0)}个机会")
            except Exception as e:
                logger.error(f"节能机会自动检测失败: {e}")
            await asyncio.sleep(3600)

    detection_task = asyncio.create_task(_opportunity_detection_loop())

    # 启动效果追踪定时任务（每6小时执行）
    async def _effect_tracking_loop():
        """效果追踪定时任务 - 每6小时检查"""
        await asyncio.sleep(300)  # 启动后延迟5分钟
        while True:
            try:
                async with async_session() as db:
                    from .services.effect_tracker import EffectTracker

                    tracker = EffectTracker(db)
                    result = await tracker.run_tracking()
                    logger.info(
                        f"效果追踪完成: 新追踪{result.get('new_tracking', 0)}个, 标记完成{result.get('marked_completed', 0)}个"
                    )
            except Exception as e:
                logger.error(f"效果追踪失败: {e}")
            await asyncio.sleep(21600)  # 6小时

    effect_tracking_task = asyncio.create_task(_effect_tracking_loop())

    # 启动 UPS 电池 SOH 计算定时任务（每日凌晨 3:00）- Story 25.3
    async def _battery_soh_calculation_loop():
        """UPS 电池 SOH 计算定时任务 - 每日凌晨 3:00"""
        await asyncio.sleep(60)  # 启动后延迟1分钟
        while True:
            try:
                now = datetime.now()
                # 计算距离下一个凌晨 3:00 的秒数
                target_time = now.replace(hour=3, minute=0, second=0, microsecond=0)
                if now >= target_time:
                    # 如果已经过了今天的 3:00，则计算明天的 3:00
                    target_time = target_time + timedelta(days=1)

                wait_seconds = (target_time - now).total_seconds()
                logger.info(f"UPS 电池 SOH 计算任务将在 {wait_seconds / 3600:.1f} 小时后执行（{target_time}）")

                await asyncio.sleep(wait_seconds)

                # 执行 SOH 计算
                from app.services.diagnosis.battery_soh_service import run_daily_soh_calculation

                await run_daily_soh_calculation()

            except Exception as e:
                logger.error(f"UPS 电池 SOH 计算任务失败: {e}")
                # 失败后等待 1 小时再重试
                await asyncio.sleep(3600)

    soh_calculation_task = asyncio.create_task(_battery_soh_calculation_loop())

    # 启动传感器校准过期检查定时任务（每日凌晨 2:00）- Story 25.5
    # 使用 APScheduler AsyncIOScheduler
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from app.services.diagnosis.sensor_metadata_service import check_expired_calibrations

        scheduler = AsyncIOScheduler()

        async def _run_calibration_check():
            """执行校准过期检查"""
            try:
                async with async_session() as session:
                    await check_expired_calibrations(session)
            except Exception as e:
                logger.error(f"传感器校准过期检查任务失败: {e}")

        scheduler.add_job(
            _run_calibration_check, "cron", hour=2, minute=0, id="calibration_check", name="传感器校准过期检查"
        )

        # 启动趋势分析定时任务（每小时执行）- Story 25.7
        async def _run_trend_analysis():
            """执行趋势分析任务"""
            try:
                logger.info("开始执行趋势分析任务")
                async with async_session() as session:
                    from app.services.diagnosis.trend_analysis_service import get_trend_analysis_service
                    from app.models.point import Point

                    # 查询所有启用的温湿度点位
                    result = await session.execute(
                        select(Point).where(
                            Point.enabled == True,
                            (Point.unit.like("%℃%")) | (Point.unit.like("%°C%")) | (Point.unit.like("%RH%")),
                        )
                    )
                    points = result.scalars().all()

                    trend_service = get_trend_analysis_service(session)
                    warnings = []
                    for point in points:
                        warning = await trend_service.analyze_point_trend(point.id)
                        if warning:
                            warnings.append(warning)
                            # 保存趋势预警到数据库
                            session.add(warning)

                    await session.commit()
                    logger.info(f"趋势分析任务完成，生成 {len(warnings)} 条预警")
            except Exception as e:
                logger.error(f"趋势分析任务执行失败: {e}", exc_info=True)

        scheduler.add_job(
            _run_trend_analysis,
            "cron",
            minute=0,  # 每小时整点执行
            id="trend_analysis",
            name="趋势分析任务",
        )

        # 启动反事实分析定时任务（每小时执行）- Story 26.1
        async def _run_counterfactual_analysis():
            """执行反事实分析任务"""
            try:
                from app.services.diagnosis.counterfactual_service import analyze_counterfactual
                from app.models.diagnosis import DiagnosisSession

                async with async_session() as session:
                    # 查询最近1小时内的高置信度诊断会话
                    one_hour_ago = datetime.now() - timedelta(hours=1)
                    result = await session.execute(
                        select(DiagnosisSession).where(
                            DiagnosisSession.created_at >= one_hour_ago,
                            DiagnosisSession.max_confidence >= 0.7,
                            DiagnosisSession.status == "success",
                        )
                    )
                    sessions = result.scalars().all()

                    # 为每个会话执行反事实分析
                    analyzed_count = 0
                    for sess in sessions:
                        # 检查是否已存在分析结果
                        from app.models.diagnosis import CounterfactualAnalysis

                        existing = await session.execute(
                            select(CounterfactualAnalysis).where(
                                CounterfactualAnalysis.session_id == sess.id,
                                CounterfactualAnalysis.deleted_at.is_(None),
                            )
                        )
                        if existing.scalar_one_or_none():
                            continue  # 已存在，跳过

                        # 执行分析
                        analysis = await analyze_counterfactual(sess.id, top_n=5, db=session)
                        if analysis:
                            analyzed_count += 1

                    logger.info(f"反事实分析任务完成，分析 {analyzed_count}/{len(sessions)} 个会话")
            except Exception as e:
                logger.error(f"反事实分析任务执行失败: {e}", exc_info=True)

        scheduler.add_job(
            _run_counterfactual_analysis,
            "cron",
            minute=30,  # 每小时30分执行
            id="counterfactual_analysis",
            name="反事实分析任务",
        )

        # 启动误诊报告月度定时任务（每月1日凌晨 0:00）- Story 26.2
        async def _run_misdiagnosis_report():
            """执行误诊报告生成任务"""
            try:
                from app.services.diagnosis.misdiagnosis_report_service import MisdiagnosisReportService
                from app.services.email_service import email_service
                from datetime import datetime
                from jinja2 import Template
                import os

                # 生成上月报告
                last_month = datetime.now().replace(day=1) - timedelta(days=1)
                period = last_month.strftime("%Y-%m")

                logger.info(f"开始生成误诊分析报告: period={period}")
                async with async_session() as session:
                    report = await MisdiagnosisReportService.generate_monthly_report(period, session)
                    if report:
                        logger.info(f"误诊分析报告生成成功: report_id={report.id}")

                        # 发送邮件通知管理员
                        if email_service.is_available:
                            # 查询管理员邮箱
                            admin_result = await session.execute(
                                select(User).where(User.role == "admin", User.is_active == True, User.email.isnot(None))
                            )
                            admins = admin_result.scalars().all()
                            admin_emails = [admin.email for admin in admins if admin.email]

                            if admin_emails:
                                # 加载邮件模板
                                template_path = os.path.join(
                                    os.path.dirname(__file__), "templates/emails/misdiagnosis_report.html"
                                )
                                with open(template_path, "r", encoding="utf-8") as f:
                                    template_content = f.read()

                                template = Template(template_content)
                                summary = report.summary or {}
                                top_node = ""
                                if summary.get("top_misdiagnosed_nodes"):
                                    top_node = summary["top_misdiagnosed_nodes"][0].get("node_id", "")

                                html_content = template.render(
                                    period=period,
                                    total_diagnoses=summary.get("total_diagnoses", 0),
                                    accuracy_rate=summary.get("accuracy_rate"),
                                    false_positive_count=summary.get("false_positive_count", 0),
                                    false_negative_count=summary.get("false_negative_count", 0),
                                    top_misdiagnosed_node=top_node,
                                    report_url=f"http://localhost:3000/diagnosis/reports/misdiagnosis?period={period}",
                                )

                                success = await email_service.send_html_email(
                                    to_emails=admin_emails,
                                    subject=f"[DCIM] 误诊分析报告 - {period}",
                                    html_content=html_content,
                                )
                                if success:
                                    logger.info(f"误诊报告邮件发送成功: to={admin_emails}")
                                else:
                                    logger.warning("误诊报告邮件发送失败")
                            else:
                                logger.warning("未找到管理员邮箱，跳过邮件发送")
                        else:
                            logger.info("邮件服务未配置，跳过邮件发送")
                    else:
                        logger.warning(f"误诊分析报告生成失败或数据不足: period={period}")
            except Exception as e:
                logger.error(f"误诊报告生成任务执行失败: {e}", exc_info=True)

        scheduler.add_job(
            _run_misdiagnosis_report,
            "cron",
            day=1,
            hour=0,
            minute=0,
            id="misdiagnosis_report",
            name="误诊分析报告生成任务",
        )

        # Story 26.4: 时间窗口自适应调参任务（每月1日凌晨3:00）
        async def _run_time_window_tuning():
            """时间窗口调参分析任务"""
            try:
                from app.services.diagnosis.time_window_tuning_service import TimeWindowTuningService

                tuning_service = TimeWindowTuningService()
                result = await tuning_service.analyze_all_device_types()
                logger.info(f"时间窗口调参分析完成: {result}")

                # 如果有待审批的调参建议，发送通知
                if result["pending_approvals"] > 0:
                    try:
                        await tuning_service.notify_admins(result)
                    except Exception as notify_error:
                        logger.error(f"通知管理员失败: {notify_error}", exc_info=True)
            except Exception as e:
                logger.error(f"时间窗口调参分析任务执行失败: {e}", exc_info=True)

        scheduler.add_job(
            _run_time_window_tuning,
            "cron",
            day=1,
            hour=3,
            minute=0,
            coalesce=True,
            max_instances=1,
            misfire_grace_time=300,
            id="time_window_tuning",
            name="时间窗口调参分析任务",
        )

        # Story 29.5: 精度回填定时任务（每 5 分钟）
        async def _run_accuracy_backfill():
            """回填实际温度"""
            try:
                from app.services.precool.accuracy_monitor import backfill_actual_temperatures

                await backfill_actual_temperatures()
            except Exception as e:
                logger.error(f"精度回填任务失败: {e}")

        scheduler.add_job(_run_accuracy_backfill, "interval", minutes=5, id="accuracy_backfill", name="精度回填任务")

        # Story 29.5: 每日精度统计（凌晨 1:00）
        async def _run_accuracy_daily_report():
            """每日精度统计"""
            try:
                from app.services.precool.accuracy_monitor import run_daily_accuracy_report

                await run_daily_accuracy_report()
            except Exception as e:
                logger.error(f"每日精度统计任务失败: {e}")

        scheduler.add_job(
            _run_accuracy_daily_report, "cron", hour=1, minute=0, id="accuracy_daily_report", name="每日精度统计任务"
        )

        # Story 31.2: 预冷计划扫描（每分钟）
        async def _run_precool_scan():
            """扫描 pending 预冷计划"""
            try:
                from app.services.precool.executor import precool_executor

                await precool_executor.scan_and_execute_plans()
            except Exception as e:
                logger.error(f"预冷扫描异常: {e}")

        scheduler.add_job(
            _run_precool_scan,
            "interval",
            minutes=1,
            max_instances=1,
            coalesce=True,
            id="precool_scan",
            name="预冷计划扫描任务",
        )

        # Story 31.2: 预冷计划执行推进（每 5 分钟）
        async def _run_precool_tick():
            """推进 executing 预冷计划"""
            try:
                from app.services.precool.executor import precool_executor

                await precool_executor.tick_executing_plans()
            except Exception as e:
                logger.error(f"预冷推进异常: {e}")

        scheduler.add_job(
            _run_precool_tick,
            "interval",
            minutes=5,
            max_instances=1,
            coalesce=True,
            id="precool_tick",
            name="预冷计划执行推进任务",
        )

        # Story 32.1: 月度 RC 参数自动校准
        try:
            from app.services.precool.calibrator import rc_calibrator

            async def _run_monthly_rc_calibration():
                try:
                    logger.info("开始月度 RC 参数自动校准...")
                    results = await rc_calibrator.run_monthly_calibration()
                    logger.info(
                        f"月度 RC 校准完成: 成功={len(results.get('success', []))}, "
                        f"跳过={len(results.get('skipped', []))}, "
                        f"失败={len(results.get('failed', []))}"
                    )
                except Exception as e:
                    logger.error(f"月度 RC 校准任务异常: {e}", exc_info=True)

            scheduler.add_job(
                _run_monthly_rc_calibration,
                "cron",
                day=1,
                hour=3,
                minute=37,
                id="monthly_rc_calibration",
                max_instances=1,
                replace_existing=True,
                name="月度RC参数自动校准",
            )
        except ImportError:
            logger.warning("⚠️  calibrator 模块不可用（scipy 未安装），跳过月度RC校准任务")

        # Story 33.1: VPP 可调容量定时刷新（每 5 分钟）
        try:
            from app.services.precool.vpp_capacity import vpp_capacity_service

            async def _refresh_vpp_capacity():
                try:
                    await vpp_capacity_service.refresh_capacity_cache()
                except Exception as e:
                    logger.error(f"VPP 容量刷新失败: {e}", exc_info=True)

            scheduler.add_job(
                _refresh_vpp_capacity,
                "interval",
                minutes=5,
                max_instances=1,
                coalesce=True,
                id="vpp_capacity_refresh",
                replace_existing=True,
                name="VPP可调容量刷新",
            )
        except ImportError:
            logger.warning("⚠️  vpp_capacity 模块不可用，跳过 VPP 容量刷新任务")

        # Story 26.8: 依赖安全扫描 — 每周一凌晨 3:30
        try:
            from app.services.diagnosis.dependency_audit_service import dependency_audit_service

            async def _run_dependency_audit():
                try:
                    result = await dependency_audit_service.run_audit()
                    vuln_count = result.get("total_vulnerabilities", 0)
                    logger.info(f"依赖安全扫描完成: 发现 {vuln_count} 个漏洞")
                except Exception as e:
                    logger.error(f"依赖安全扫描任务失败: {e}", exc_info=True)

            scheduler.add_job(
                _run_dependency_audit,
                "cron",
                day_of_week="mon",
                hour=3,
                minute=30,
                id="dependency_audit_weekly",
                max_instances=1,
                replace_existing=True,
                name="依赖安全审计",
            )
        except ImportError:
            logger.warning("⚠️  dependency_audit_service 模块不可用，跳过依赖安全扫描任务")

        scheduler.start()
        logger.info("✓ 依赖安全审计任务已启动（每周一凌晨 3:30）")
        logger.info("✓ 传感器校准过期检查定时任务已启动（每日凌晨 2:00）")
        logger.info("✓ 趋势分析定时任务已启动（每小时整点执行）")
        logger.info("✓ 反事实分析定时任务已启动（每小时30分执行）")
        logger.info("✓ 误诊分析报告生成任务已启动（每月1日凌晨 0:00）")
        logger.info("✓ 时间窗口调参分析任务已启动（每月1日凌晨 3:00）")
        logger.info("✓ 精度回填任务已启动（每 5 分钟执行）")
        logger.info("✓ 每日精度统计任务已启动（每日凌晨 1:00）")
        logger.info("✓ 预冷计划扫描任务已启动（每分钟执行）")
        logger.info("✓ 预冷计划执行推进任务已启动（每 5 分钟执行）")
        logger.info("✓ 月度RC参数自动校准任务已注册（每月1日 03:37）")

        # Story 36.1: Hourly 归档定时任务
        async def _run_archive_hourly():
            """聚合上一小时 PointHistory 写入 PointHistoryArchive"""
            try:
                from app.services.predictive_maintenance.archiver import archive_hourly

                async with async_session() as session:
                    await archive_hourly(session)
                    await session.commit()
            except Exception as e:
                logger.error("Hourly 归档任务失败: %s", e)

        scheduler.add_job(
            _run_archive_hourly,
            "cron",
            minute=5,  # 每小时第5分钟执行，避开整点其他任务
            id="archive_hourly",
            max_instances=1,
            coalesce=True,
            name="Hourly 数据归档",
        )
        logger.info("✓ Hourly 数据归档任务已启动（每小时第5分钟执行）")

        # Story 36.2: 每日健康度评分定时任务
        async def _run_health_score_calculation():
            """全量设备健康度评分计算"""
            try:
                from app.services.predictive_maintenance.health_calculator import DeviceHealthScoreCalculator

                async with async_session() as session:
                    calculator = DeviceHealthScoreCalculator(session)
                    await calculator.calculate_all_health_scores()
                    await session.commit()
            except Exception as e:
                logger.error("健康度评分计算任务失败: %s", e)

        scheduler.add_job(
            _run_health_score_calculation,
            "cron",
            hour=2,
            minute=7,
            id="health_score_calculation",
            max_instances=1,
            coalesce=True,
            name="每日健康度评分计算",
        )
        logger.info("✓ 每日健康度评分计算任务已启动（每日 02:07 执行）")
    except ImportError:
        logger.warning("⚠️  APScheduler 未安装，使用降级方案（asyncio.create_task）")

        async def _calibration_check_loop():
            """传感器校准过期检查定时任务 - 每日凌晨 2:00"""
            await asyncio.sleep(60)  # 启动后延迟1分钟
            while True:
                try:
                    now = datetime.now()
                    # 计算距离下一个凌晨 2:00 的秒数
                    target_time = now.replace(hour=2, minute=0, second=0, microsecond=0)
                    if now >= target_time:
                        # 如果已经过了今天的 2:00，则计算明天的 2:00
                        target_time = target_time + timedelta(days=1)

                    wait_seconds = (target_time - now).total_seconds()
                    logger.info(f"传感器校准过期检查任务将在 {wait_seconds / 3600:.1f} 小时后执行（{target_time}）")

                    await asyncio.sleep(wait_seconds)

                    # 执行校准过期检查
                    from app.services.diagnosis.sensor_metadata_service import check_expired_calibrations

                    async with async_session() as session:
                        await check_expired_calibrations(session)

                except Exception as e:
                    logger.error(f"传感器校准过期检查任务失败: {e}")
                    # 失败后等待 1 小时再重试
                    await asyncio.sleep(3600)

        calibration_check_task = asyncio.create_task(_calibration_check_loop())

        # Story 29.5: 精度回填降级方案（每 5 分钟）
        async def _accuracy_backfill_loop():
            await asyncio.sleep(120)  # 启动后延迟 2 分钟
            while True:
                try:
                    from app.services.precool.accuracy_monitor import backfill_actual_temperatures

                    await backfill_actual_temperatures()
                except Exception as e:
                    logger.error(f"精度回填任务失败: {e}")
                await asyncio.sleep(300)  # 5 分钟

        asyncio.create_task(_accuracy_backfill_loop())

        # Story 29.5: 每日精度统计降级方案（凌晨 1:00）
        async def _accuracy_daily_loop():
            await asyncio.sleep(60)
            while True:
                try:
                    now = datetime.now()
                    target = now.replace(hour=1, minute=0, second=0, microsecond=0)
                    if now >= target:
                        target = target + timedelta(days=1)
                    await asyncio.sleep((target - now).total_seconds())
                    from app.services.precool.accuracy_monitor import run_daily_accuracy_report

                    await run_daily_accuracy_report()
                except Exception as e:
                    logger.error(f"每日精度统计任务失败: {e}")
                    await asyncio.sleep(3600)

        asyncio.create_task(_accuracy_daily_loop())

        # Story 36.1: Hourly 归档降级方案（每小时第5分钟）
        async def _archive_hourly_loop():
            await asyncio.sleep(300)  # 启动后延迟5分钟
            while True:
                try:
                    from app.services.predictive_maintenance.archiver import archive_hourly

                    async with async_session() as session:
                        await archive_hourly(session)
                        await session.commit()
                except Exception as e:
                    logger.error("Hourly 归档任务失败: %s", e)
                await asyncio.sleep(3600)

        asyncio.create_task(_archive_hourly_loop())

        # Story 36.2: 健康度评分降级方案（每日凌晨 02:07）
        async def _health_score_loop():
            await asyncio.sleep(600)  # 启动后延迟10分钟
            while True:
                try:
                    now = datetime.now()
                    target = now.replace(hour=2, minute=7, second=0, microsecond=0)
                    if now >= target:
                        target = target + timedelta(days=1)
                    await asyncio.sleep((target - now).total_seconds())
                    from app.services.predictive_maintenance.health_calculator import DeviceHealthScoreCalculator

                    async with async_session() as session:
                        calculator = DeviceHealthScoreCalculator(session)
                        await calculator.calculate_all_health_scores()
                        await session.commit()
                except Exception as e:
                    logger.error("健康度评分计算任务失败: %s", e)
                    await asyncio.sleep(3600)

        asyncio.create_task(_health_score_loop())

        scheduler = None
    except Exception as e:
        logger.error(f"✗ 传感器校准过期检查定时任务启动失败: {e}")
        scheduler = None

    print(f"{'=' * 50}")
    print(f"{settings.app_name} v{settings.app_version} 启动成功")
    print(f"{'=' * 50}")
    print("告警引擎已加载阈值缓存")
    print("联动引擎已加载策略缓存")
    print("通信监控已启动，每30秒检查一次")
    print("告警升级引擎已启动，每60秒检查一次")
    print("PUE历史记录任务已启动，每15分钟记录一次")
    print("能耗聚合任务已启动，每30分钟检查一次")
    print("节能机会自动检测已启动，每小时检查一次")
    print("效果追踪任务已启动，每6小时检查一次")
    print("UPS 电池 SOH 计算任务已启动，每日凌晨 3:00 执行")
    print("传感器校准过期检查任务已启动，每日凌晨 2:00 执行")
    print("趋势分析任务已启动，每小时整点执行")

    # 启动 WebSocket 心跳检测
    ws_manager.start_heartbeat()
    print("WebSocket 心跳检测已启动，每30秒检查一次")

    # Story 30.2: 回退保护监控
    async def _rollback_monitor_loop():
        """回退保护监控循环 — 每 10 秒检查所有 zone"""
        from app.services.precool.rollback_manager import rollback_manager
        from app.core.database import async_session as rollback_session
        from app.models.topology_config import CoolingZone

        await asyncio.sleep(15)
        logger.info("🛡️ 回退保护监控已启动")

        while True:
            try:
                async with rollback_session() as session:
                    zones = (await session.execute(select(CoolingZone.id))).scalars().all()

                    for zone_id in zones:
                        try:
                            await rollback_manager.check_zone(zone_id, session)
                        except Exception as e:
                            logger.error(f"Zone {zone_id} 回退检测异常: {e}")

                    await session.commit()
            except Exception as e:
                logger.error(f"回退监控循环异常: {e}")

            await asyncio.sleep(10)

    rollback_task = asyncio.create_task(_rollback_monitor_loop())
    observability_task = asyncio.create_task(run_observability_monitor(async_session))
    print("回退保护监控已启动，每10秒检查一次")

    print("API文档: http://localhost:8000/docs")

    yield

    # 停止拓扑变更监听器（Story 25.1）
    if listener_task:
        from app.services.diagnosis.device_sync_service import stop_device_sync_listener

        await stop_device_sync_listener()
        try:
            await asyncio.wait_for(listener_task, timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning("拓扑监听器停止超时")

    # 停止传感器元数据 Redis 监听器（Story 25.5）
    if redis_listener_task:
        try:
            from app.services.diagnosis.sensor_metadata_service import SensorMetadataCache

            await SensorMetadataCache.stop_listener()
            logger.info("✓ 传感器元数据 Redis 监听器已停止")
        except Exception as e:
            logger.error(f"✗ 传感器元数据 Redis 监听器停止失败: {e}")

    # 关闭演示模块
    if settings.demo_enabled or settings.simulation_enabled:
        await demo_shutdown()
    refresh_task.cancel()
    comm_monitor_task.cancel()
    mstp_health_task.cancel()  # Story 35.2
    escalation_task.cancel()
    pue_history_task.cancel()
    energy_agg_task.cancel()
    detection_task.cancel()
    effect_tracking_task.cancel()
    soh_calculation_task.cancel()
    channel_escalation_task.cancel()  # Story 34.5
    rollback_task.cancel()  # Story 30.2
    observability_task.cancel()

    # 停止校准检查定时任务
    if scheduler:
        scheduler.shutdown(wait=False)
        logger.info("✓ 传感器校准过期检查定时任务已停止")
    else:
        calibration_check_task.cancel()

    ws_manager.stop_heartbeat()
    # 关闭 Redis 连接
    await redis_service.close()
    print("应用关闭")


# 创建 FastAPI 应用
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="机房动力环境监测系统 API - V2.0",
    lifespan=lifespan,
    dependencies=[Depends(enforce_inventory_authorization)],
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS 配置 - 只允许配置的前端地址
cors_origins = parse_cors_origins(settings.cors_origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
    expose_headers=["X-Degraded", "X-Degraded-Message"],
)

# 性能指标中间件
app.add_middleware(MetricsMiddleware)

# 请求日志中间件
app.add_middleware(RequestLoggingMiddleware)

# 全局异常处理器
register_exception_handlers(app)

# 注册 API v1 路由
app.include_router(api_router, prefix="/api/v1")


@app.get("/", tags=["系统"])
async def root():
    """根路径 - 返回系统信息"""
    return {"name": settings.app_name, "version": settings.app_version, "api_version": "v1", "status": "running"}


@app.get("/api/health", tags=["系统"])
async def health():
    """健康检查 — 含数据库连通性检测"""
    now = datetime.now().isoformat()
    version = settings.app_version
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": now,
            "version": version,
        }
    except Exception:
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "database": "disconnected",
                "timestamp": now,
                "version": version,
            },
        )


@app.get("/api/readiness", tags=["系统"])
async def readiness():
    """就绪检查 — 数据库 / Redis / WebSocket 综合检测"""
    now = datetime.now().isoformat()
    checks = {}
    ready = True

    # 数据库检查
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "fail"
        ready = False

    # Redis 检查
    try:
        if not settings.redis_enabled:
            checks["redis"] = "disabled"
        elif redis_service.is_available:
            await redis_service._pool.ping()
            checks["redis"] = "ok"
        else:
            checks["redis"] = "fail"
            ready = False
    except Exception:
        checks["redis"] = "fail"
        ready = False

    # WebSocket 检查
    checks["websocket"] = {
        "status": "ok",
        "connections": ws_manager.total_connections,
    }

    payload = {"ready": ready, "checks": checks, "timestamp": now}

    if not ready:
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=503, content=payload)

    return payload


@app.get("/api/stats", tags=["系统"])
async def get_stats():
    """获取系统统计信息"""
    from sqlalchemy import func, Integer
    from .models import Point

    async with async_session() as session:
        # 点位统计
        point_result = await session.execute(
            select(func.count(Point.id).label("total"), func.sum(func.cast(Point.is_enabled, Integer)).label("enabled"))
        )
        point_row = point_result.first()

        # 按类型统计
        type_result = await session.execute(select(Point.point_type, func.count(Point.id)).group_by(Point.point_type))
        type_counts = {row[0]: row[1] for row in type_result.all()}

        return {
            "points": {"total": point_row[0] or 0, "enabled": point_row[1] or 0, "by_type": type_counts},
            "license": {"type": "standard", "max_points": settings.max_points, "used_points": point_row[0] or 0},
        }


@app.get("/api/metrics", tags=["系统"])
async def get_app_metrics():
    """性能指标"""
    import platform

    metrics = await metrics_collector.get_metrics()
    metrics["system"] = {
        "python_version": platform.python_version(),
        "websocket_connections": ws_manager.total_connections,
    }
    try:
        import psutil

        process = psutil.Process()
        metrics["system"]["memory_mb"] = round(process.memory_info().rss / 1024 / 1024, 1)
        metrics["system"]["cpu_percent"] = process.cpu_percent()
    except ImportError:
        pass
    return metrics


# WebSocket 使用首帧认证，避免原始 JWT 进入 URL。
WS_AUTH_TIMEOUT_SECONDS = 5


async def _serve_authorized_websocket(websocket: WebSocket, channel: str) -> None:
    await websocket.accept()
    context = None
    try:
        try:
            auth_frame = await asyncio.wait_for(websocket.receive_json(), timeout=WS_AUTH_TIMEOUT_SECONDS)
        except Exception:
            await websocket.close(code=4001, reason="Unauthorized")
            return
        if (
            not isinstance(auth_frame, dict)
            or set(auth_frame) != {"action", "token"}
            or auth_frame.get("action") != "authenticate"
            or not isinstance(auth_frame.get("token"), str)
        ):
            await websocket.close(code=4001, reason="Unauthorized")
            return

        authorization = await verify_websocket_token(auth_frame["token"], channel)
        if authorization is None:
            await websocket.close(code=4001, reason="Unauthorized")
            return
        context = ConnectionContext(
            websocket=websocket,
            user_id=authorization.user_id,
            jti=authorization.jti,
            role=authorization.role,
            allowed_site_ids=authorization.allowed_site_ids,
            channel=authorization.channel,
            expires_at=authorization.expires_at,
            username=authorization.username,
        )
        await ws_manager.connect(context, already_accepted=True)
        await websocket.send_json({"type": "authenticated"})

        while True:
            try:
                message = await websocket.receive_json()
                await ws_manager.handle_client_message(context, message)
            except ValueError:
                await websocket.close(code=4001, reason="Unauthorized")
                return
    except WebSocketDisconnect:
        pass
    finally:
        if context is not None:
            ws_manager.disconnect(context)


@app.websocket("/ws/realtime")
async def websocket_realtime(websocket: WebSocket):
    await _serve_authorized_websocket(websocket, "realtime")


@app.websocket("/ws/alarms")
async def websocket_alarms(websocket: WebSocket):
    await _serve_authorized_websocket(websocket, "alarms")


@app.websocket("/ws/system")
async def websocket_system(websocket: WebSocket):
    await _serve_authorized_websocket(websocket, "system")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
