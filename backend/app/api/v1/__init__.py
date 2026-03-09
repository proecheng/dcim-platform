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
from .test_endpoint import router as test_router
from .power import router as power_router
from .power_redundancy import router as power_redundancy_router
from .regulation import router as regulation_router
from .asset import router as asset_router
from .capacity import router as capacity_router
from .operation import router as operation_router
from ...demo.router import router as demo_router
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
from .trace import router as trace_router
from .optimization import router as optimization_router
from .cooling import router as cooling_router
from .datasources import router as datasource_router
from .gateways import router as gateway_router
from .device_templates import router as device_template_router
from .system_health import router as system_health_router
from .data_quality import router as data_quality_router
from .escalation import router as escalation_router
from .spatial import router as spatial_router
from .topology_config import router as topology_config_router
from .linkage import router as linkage_router
from .diagnosis import router as diagnosis_router
from .command import router as command_router
from .drift import router as drift_router
from .video import router as video_router
from .ota import router as ota_router
from .shift import router as shift_router
from .fault_tree_versions import router as fault_tree_versions_router
from .sensor_metadata import router as sensor_metadata_router
from .probability_tuning import router as probability_tuning_router
from .ab_testing import router as ab_testing_router

# 深度学习节能优化模块 (需要安装 torch)
try:
    from .ml import router as ml_router

    _ml_available = True
except ImportError:
    _ml_available = False

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
api_router.include_router(test_router, tags=["测试"])
api_router.include_router(power_router, prefix="/power", tags=["供配电管理"])
api_router.include_router(power_redundancy_router, prefix="/power", tags=["供配电管理"])
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
api_router.include_router(trace_router, tags=["数据追溯链"])
api_router.include_router(optimization_router, prefix="/optimization", tags=["日前调度优化"])
api_router.include_router(cooling_router, prefix="/cooling", tags=["制冷系统"])
api_router.include_router(datasource_router, prefix="/datasources", tags=["数据源管理"])
api_router.include_router(gateway_router, prefix="/gateways", tags=["网关管理"])
api_router.include_router(device_template_router, prefix="/device-templates", tags=["设备模板"])
api_router.include_router(system_health_router, prefix="/system", tags=["系统"])
api_router.include_router(data_quality_router, prefix="/data-quality", tags=["数据质量"])
api_router.include_router(escalation_router, prefix="/escalations", tags=["告警升级"])
api_router.include_router(spatial_router)
api_router.include_router(topology_config_router, prefix="/topology-config", tags=["拓扑配置"])
api_router.include_router(linkage_router, prefix="/linkage", tags=["联动管理"])
api_router.include_router(diagnosis_router, prefix="/diagnosis", tags=["智能诊断"])
api_router.include_router(command_router, prefix="/command", tags=["控制命令"])
api_router.include_router(drift_router, prefix="/drift", tags=["漂移检测"])
api_router.include_router(video_router, prefix="/video", tags=["视频监控"])
api_router.include_router(ota_router, prefix="/ota", tags=["OTA升级"])
api_router.include_router(shift_router, prefix="/energy/shift", tags=["负荷转移"])
api_router.include_router(fault_tree_versions_router, tags=["故障树版本管理"])
api_router.include_router(sensor_metadata_router, prefix="/diagnosis/sensor-metadata", tags=["传感器元数据"])
api_router.include_router(probability_tuning_router, tags=["概率调参"])
api_router.include_router(ab_testing_router, prefix="/api/v1", tags=["A/B Testing"])

# 深度学习节能优化API
if _ml_available:
    api_router.include_router(ml_router, prefix="/ml", tags=["深度学习节能优化"])

# reload 1769696750.1147227
