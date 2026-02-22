"""
算力中心智能监控系统 - 主入口
V2.0 架构重构版
"""

import asyncio
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from jose import jwt, JWTError

from .core.config import get_settings
from .core.database import init_db, async_session
from .core.security import get_password_hash
from .models import User
from .api.v1 import api_router
from .services.websocket import ws_manager
from .services.simulator import simulator
from .services.power_seed import seed_power_devices
from .services.cooling_seed import seed_cooling_devices
from .core.redis import redis_service
from .engines.alarm_engine import alarm_engine
from .engines.linkage_engine import linkage_engine
from .engines.event_bus import get_event_bus
from .services.communication_monitor import check_communication_status
from .engines.escalation_engine import check_escalations
from .engines.diagnosis_engine import diagnosis_engine
from .services.pue_calculator import write_pue_history
from .services.energy_aggregator import aggregate_hourly, aggregate_daily, aggregate_monthly

import logging

logger = logging.getLogger(__name__)

settings = get_settings()


async def verify_websocket_token(token: str) -> bool:
    """验证 WebSocket 连接的 JWT 令牌"""
    if not token:
        return False
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        username = payload.get("sub")
        if username is None:
            return False
        # 验证用户是否存在且活跃
        async with async_session() as session:
            result = await session.execute(select(User).where(User.username == username))
            user = result.scalar_one_or_none()
            return user is not None and user.is_active
    except JWTError:
        return False


async def init_default_data():
    """初始化默认数据"""
    async with async_session() as session:
        # 创建默认管理员账户
        result = await session.execute(select(User).where(User.username == "admin"))
        if not result.scalar_one_or_none():
            admin = User(
                username="admin",
                password_hash=get_password_hash("admin123"),
                real_name="系统管理员",
                email="admin@dcim.local",
                role="admin",
            )
            session.add(admin)
            await session.commit()
            print("创建默认管理员账户: admin / admin123")

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
    """应用生命周期管理"""
    # 启动时初始化数据库
    await init_db()
    await init_default_data()
    await init_default_configs()
    await seed_power_devices()
    await seed_cooling_devices()

    # 连接 Redis 缓存
    if settings.redis_enabled:
        await redis_service.connect(settings.redis_url)

    # 加载告警引擎阈值缓存
    await alarm_engine.load_thresholds()

    # 同步消防策略 YAML 到数据库（Story 9-2）
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

    # 同步诊断规则 YAML 到数据库并启动诊断引擎（Story 9-3）
    try:
        from .services.diagnosis_loader import sync_to_database as diag_sync

        async with async_session() as session:
            await diag_sync(session)
    except Exception as e:
        logger.warning("诊断规则同步失败: %s", e)

    await diagnosis_engine.load_rules()
    await event_bus.subscribe("linkage", diagnosis_engine.on_alarm_event)

    # 启动数据模拟器（后台任务）
    simulator_task = asyncio.create_task(simulator.start(interval=5))

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

    # 启动 PUE 历史记录定时写入（每 15 分钟）
    async def _pue_history_loop():
        await asyncio.sleep(10)  # 启动后短暂等待
        # 先执行一次
        if not settings.simulation_enabled:
            try:
                async with async_session() as session:
                    await write_pue_history(session)
            except Exception as e:
                logger.warning("PUE历史写入失败: %s", e)
        while True:
            await asyncio.sleep(900)  # 15分钟
            if not settings.simulation_enabled:
                try:
                    async with async_session() as session:
                        await write_pue_history(session)
                except Exception as e:
                    logger.warning("PUE历史写入失败: %s", e)

    pue_history_task = asyncio.create_task(_pue_history_loop())

    # 启动能耗数据聚合定时任务（仅在非模拟模式下）
    async def _energy_aggregation_loop():
        await asyncio.sleep(30)  # 启动后等待
        _last_daily_date = None
        _last_monthly_key = None
        while True:
            if not settings.simulation_enabled:
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

    print(f"{'=' * 50}")
    print(f"{settings.app_name} v{settings.app_version} 启动成功")
    print(f"{'=' * 50}")
    print("数据模拟器已启动，每5秒采集一次")
    print("告警引擎已加载阈值缓存")
    print("联动引擎已加载策略缓存")
    print("通信监控已启动，每30秒检查一次")
    print("告警升级引擎已启动，每60秒检查一次")
    print("PUE历史记录任务已启动，每15分钟记录一次")
    print("能耗聚合任务已启动，每30分钟检查一次")
    print("节能机会自动检测已启动，每小时检查一次")
    print("效果追踪任务已启动，每6小时检查一次")

    # 启动 WebSocket 心跳检测
    ws_manager.start_heartbeat()
    print("WebSocket 心跳检测已启动，每30秒检查一次")

    print("API文档: http://localhost:8000/docs")

    yield

    # 停止模拟器和刷新任务
    simulator.stop()
    simulator_task.cancel()
    refresh_task.cancel()
    comm_monitor_task.cancel()
    escalation_task.cancel()
    pue_history_task.cancel()
    energy_agg_task.cancel()
    detection_task.cancel()
    effect_tracking_task.cancel()
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
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS 配置 - 只允许配置的前端地址
cors_origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
    expose_headers=["X-Degraded", "X-Degraded-Message"],
)

# 注册 API v1 路由
app.include_router(api_router, prefix="/api/v1")


@app.get("/", tags=["系统"])
async def root():
    """根路径 - 返回系统信息"""
    return {"name": settings.app_name, "version": settings.app_version, "api_version": "v1", "status": "running"}


@app.get("/api/health", tags=["系统"])
async def health():
    """健康检查"""
    return {"status": "healthy"}


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


# WebSocket 路由 - 需要 JWT 令牌认证
@app.websocket("/ws/realtime")
async def websocket_realtime(websocket: WebSocket, token: str = Query(None)):
    """实时数据 WebSocket（需要认证）"""
    if not await verify_websocket_token(token):
        await websocket.close(code=4001, reason="Unauthorized")
        return
    await ws_manager.connect(websocket, "realtime")
    try:
        while True:
            await websocket.receive_text()
            # 可以处理客户端发来的订阅请求
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, "realtime")


@app.websocket("/ws/alarms")
async def websocket_alarms(websocket: WebSocket, token: str = Query(None)):
    """告警 WebSocket（需要认证）"""
    if not await verify_websocket_token(token):
        await websocket.close(code=4001, reason="Unauthorized")
        return
    await ws_manager.connect(websocket, "alarms")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, "alarms")


@app.websocket("/ws/system")
async def websocket_system(websocket: WebSocket, token: str = Query(None)):
    """系统状态 WebSocket（需要认证）"""
    if not await verify_websocket_token(token):
        await websocket.close(code=4001, reason="Unauthorized")
        return
    await ws_manager.connect(websocket, "system")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, "system")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
