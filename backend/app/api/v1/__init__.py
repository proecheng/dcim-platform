"""
API v1 路由模块
"""
from fastapi import APIRouter

from .auth import router as auth_router
from .user import router as user_router
from .device import router as device_router
from .point import router as point_router
from .realtime import router as realtime_router
from .alarm import router as alarm_router
from .threshold import router as threshold_router
from .history import router as history_router
from .report import router as report_router
from .log import router as log_router
from .statistics import router as statistics_router
from .config import router as config_router
from .energy import router as energy_router
from .regulation import router as regulation_router
from .asset import router as asset_router
from .capacity import router as capacity_router
from .operation import router as operation_router
from .demo import router as demo_router
from .floor_map import router as floor_map_router
from .proposal import router as proposal_router
from .vpp import router as vpp_router
from .pricing import router as pricing_router
from .opportunities import router as opportunities_router
from .execution import router as execution_router
from .demand import router as demand_router
from .dispatch import router as dispatch_router
from .monitoring import router as monitoring_router
from .topology import router as topology_router
# TODO: Enable after installing numpy
# from .optimization import router as optimization_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["认证"])
api_router.include_router(user_router, prefix="/users", tags=["用户管理"])
api_router.include_router(device_router, prefix="/devices", tags=["设备管理"])
api_router.include_router(point_router, prefix="/points", tags=["点位管理"])
api_router.include_router(realtime_router, prefix="/realtime", tags=["实时数据"])
api_router.include_router(alarm_router, prefix="/alarms", tags=["告警管理"])
api_router.include_router(threshold_router, prefix="/thresholds", tags=["阈值配置"])
api_router.include_router(history_router, prefix="/history", tags=["历史数据"])
api_router.include_router(report_router, prefix="/reports", tags=["报表"])
api_router.include_router(log_router, prefix="/logs", tags=["日志"])
api_router.include_router(statistics_router, prefix="/statistics", tags=["统计分析"])
api_router.include_router(config_router, prefix="/configs", tags=["系统配置"])
api_router.include_router(energy_router, prefix="/energy", tags=["用电管理"])
api_router.include_router(regulation_router, prefix="/regulation", tags=["负荷调节"])
api_router.include_router(asset_router)
api_router.include_router(capacity_router)
api_router.include_router(operation_router)
api_router.include_router(demo_router)
api_router.include_router(floor_map_router, prefix="/floor-map", tags=["楼层图"])
api_router.include_router(proposal_router)
api_router.include_router(vpp_router, prefix="/vpp", tags=["VPP方案分析"])
api_router.include_router(pricing_router, prefix="/pricing", tags=["电价配置"])
api_router.include_router(opportunities_router, prefix="/opportunities", tags=["节能机会"])
api_router.include_router(execution_router, prefix="/execution", tags=["执行管理"])
api_router.include_router(demand_router, tags=["需量嵌入式API"])
api_router.include_router(dispatch_router, prefix="/dispatch", tags=["可调度资源配置"])
api_router.include_router(monitoring_router, prefix="/monitoring", tags=["电费监控"])
api_router.include_router(topology_router, prefix="/topology", tags=["拓扑编辑"])
# TODO: Enable after installing numpy
# api_router.include_router(optimization_router, prefix="/optimization", tags=["日前调度优化"])
