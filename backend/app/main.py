"""
算力中心智能监控系统 - 主入口
V2.0 架构重构版
"""
import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from .core.config import get_settings
from .core.database import init_db, async_session
from .core.security import get_password_hash
from .models import User
from .api.v1 import api_router
from .services.websocket import ws_manager
from .services.simulator import simulator

settings = get_settings()


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
                role="admin"
            )
            session.add(admin)
            await session.commit()
            print("创建默认管理员账户: admin / admin123")

        # 初始化角色权限
        from .models import RolePermission
        permissions_result = await session.execute(select(RolePermission))
        if not permissions_result.scalars().all():
            default_permissions = [
                # admin 权限
                ("admin", "user:read"), ("admin", "user:write"), ("admin", "user:delete"),
                ("admin", "point:read"), ("admin", "point:write"), ("admin", "point:delete"),
                ("admin", "alarm:read"), ("admin", "alarm:write"), ("admin", "alarm:ack"),
                ("admin", "config:read"), ("admin", "config:write"),
                ("admin", "log:read"), ("admin", "report:read"), ("admin", "report:write"),
                # operator 权限
                ("operator", "point:read"), ("operator", "point:write"),
                ("operator", "alarm:read"), ("operator", "alarm:ack"),
                ("operator", "report:read"), ("operator", "report:write"),
                # viewer 权限
                ("viewer", "point:read"), ("viewer", "alarm:read"), ("viewer", "report:read"),
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
                    config_group=group,
                    config_key=key,
                    config_value=value,
                    value_type=vtype,
                    description=desc
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
                d = Dictionary(
                    dict_type=dtype,
                    dict_code=code,
                    dict_name=name,
                    dict_value=value,
                    sort_order=sort
                )
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

    # 启动数据模拟器（后台任务）
    simulator_task = asyncio.create_task(simulator.start(interval=5))

    print(f"{'='*50}")
    print(f"{settings.app_name} v{settings.app_version} 启动成功")
    print(f"{'='*50}")
    print("数据模拟器已启动，每5秒采集一次")
    print(f"API文档: http://localhost:8000/docs")

    yield

    # 停止模拟器
    simulator.stop()
    simulator_task.cancel()
    print("应用关闭")


# 创建 FastAPI 应用
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="机房动力环境监测系统 API - V2.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册 API v1 路由
app.include_router(api_router, prefix="/api/v1")


@app.get("/", tags=["系统"])
async def root():
    """根路径 - 返回系统信息"""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "api_version": "v1",
        "status": "running"
    }


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
            select(
                func.count(Point.id).label("total"),
                func.sum(func.cast(Point.is_enabled, Integer)).label("enabled")
            )
        )
        point_row = point_result.first()

        # 按类型统计
        type_result = await session.execute(
            select(Point.point_type, func.count(Point.id)).group_by(Point.point_type)
        )
        type_counts = {row[0]: row[1] for row in type_result.all()}

        return {
            "points": {
                "total": point_row[0] or 0,
                "enabled": point_row[1] or 0,
                "by_type": type_counts
            },
            "license": {
                "type": "standard",
                "max_points": settings.max_points,
                "used_points": point_row[0] or 0
            }
        }


# WebSocket 路由
@app.websocket("/ws/realtime")
async def websocket_realtime(websocket: WebSocket):
    """实时数据 WebSocket"""
    await ws_manager.connect(websocket, "realtime")
    try:
        while True:
            data = await websocket.receive_text()
            # 可以处理客户端发来的订阅请求
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, "realtime")


@app.websocket("/ws/alarms")
async def websocket_alarms(websocket: WebSocket):
    """告警 WebSocket"""
    await ws_manager.connect(websocket, "alarms")
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, "alarms")


@app.websocket("/ws/system")
async def websocket_system(websocket: WebSocket):
    """系统状态 WebSocket"""
    await ws_manager.connect(websocket, "system")
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, "system")




if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
