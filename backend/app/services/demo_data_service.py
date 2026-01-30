"""
演示数据服务 - 支持按需加载和日期偏移
"""
import asyncio
import json
import random
from datetime import datetime, timedelta
from typing import Optional, Callable
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import async_session, init_db
from ..models import Point, PointRealtime, PointHistory, AlarmThreshold, PUEHistory, FloorMap
from ..models.energy import (
    Transformer, MeterPoint, DistributionPanel, DistributionCircuit,
    PowerDevice, EnergyHourly, EnergyDaily, EnergyMonthly, ElectricityPricing,
    Demand15MinData, PricingConfig, PowerCurveData, DemandHistory, OverDemandEvent,
    DeviceLoadProfile, DeviceShiftConfig, EnergySuggestion, LoadRegulationConfig,
    RegulationHistory, DemandAnalysisRecord, EnergySavingProposal, ProposalMeasure,
    MeasureExecutionLog, EnergyOpportunity, OpportunityMeasure, ExecutionPlan,
    ExecutionTask, ExecutionResult, DispatchableDevice, StorageSystemConfig,
    PVSystemConfig, DispatchSchedule, RealtimeMonitoring, MonthlyStatistics,
    OptimizationResult
)
from ..models.alarm import Alarm
from ..data.building_points import get_all_points, get_threshold_for_point
from .floor_map_generator import FloorMapGenerator, FLOOR_CONFIG
from .point_device_matcher import PointDeviceMatcher

import logging
logger = logging.getLogger(__name__)


# 配电系统配置数据
TRANSFORMERS = [
    {"transformer_code": "TR-001", "transformer_name": "1#变压器", "rated_capacity": 1000, "voltage_high": 10.0, "voltage_low": 0.4, "efficiency": 98.5, "location": "配电室A", "status": "running"},
    {"transformer_code": "TR-002", "transformer_name": "2#变压器", "rated_capacity": 800, "voltage_high": 10.0, "voltage_low": 0.4, "efficiency": 98.0, "location": "配电室B", "status": "running"}
]

METER_POINTS = [
    {"meter_code": "M001", "meter_name": "总进线计量点", "meter_no": "DZ001234567", "transformer_code": "TR-001", "declared_demand": 800, "demand_type": "kW", "customer_no": "GD20240001", "customer_name": "数据中心总表"},
    {"meter_code": "M002", "meter_name": "IT负载计量点", "meter_no": "DZ001234568", "transformer_code": "TR-001", "declared_demand": 500, "demand_type": "kW", "customer_no": "GD20240002", "customer_name": "IT设备分表"},
    {"meter_code": "M003", "meter_name": "制冷系统计量点", "meter_no": "DZ001234569", "transformer_code": "TR-002", "declared_demand": 300, "demand_type": "kW", "customer_no": "GD20240003", "customer_name": "空调系统分表"}
]

DISTRIBUTION_PANELS = [
    # 原有配电柜
    {"panel_code": "MDP-001", "panel_name": "主配电柜", "panel_type": "main", "rated_current": 2000, "location": "配电室A", "area_code": "A1", "meter_point_code": "M001"},
    {"panel_code": "ATS-001", "panel_name": "ATS切换柜", "panel_type": "sub", "rated_current": 1600, "location": "配电室A", "area_code": "A1", "parent_code": "MDP-001", "meter_point_code": "M001"},
    {"panel_code": "UPS-IN-001", "panel_name": "UPS输入柜", "panel_type": "ups_input", "rated_current": 800, "location": "UPS室", "area_code": "A1", "parent_code": "ATS-001", "meter_point_code": "M001"},
    {"panel_code": "UPS-OUT-001", "panel_name": "UPS输出柜", "panel_type": "ups_output", "rated_current": 600, "location": "UPS室", "area_code": "A1", "meter_point_code": "M002"},
    {"panel_code": "PDU-A1-001", "panel_name": "A1区列头柜1", "panel_type": "sub", "rated_current": 250, "location": "机房A1区", "area_code": "A1", "parent_code": "UPS-OUT-001", "meter_point_code": "M002"},
    {"panel_code": "PDU-A1-002", "panel_name": "A1区列头柜2", "panel_type": "sub", "rated_current": 250, "location": "机房A1区", "area_code": "A1", "parent_code": "UPS-OUT-001", "meter_point_code": "M002"},
    {"panel_code": "AC-PANEL-001", "panel_name": "空调配电柜", "panel_type": "sub", "rated_current": 400, "location": "配电室B", "area_code": "B1", "parent_code": "MDP-001", "meter_point_code": "M003"},
    # 新增: B1制冷系统配电柜
    {"panel_code": "COOLING-PANEL-001", "panel_name": "制冷系统配电柜", "panel_type": "sub", "rated_current": 800, "location": "B1制冷机房", "area_code": "B1", "meter_point_code": "M003"},
    # 新增: F1楼层配电柜
    {"panel_code": "F1-PANEL-001", "panel_name": "F1配电柜", "panel_type": "sub", "rated_current": 500, "location": "F1机房", "area_code": "F1", "parent_code": "UPS-OUT-001", "meter_point_code": "M002"},
    # 新增: F2楼层配电柜
    {"panel_code": "F2-PANEL-001", "panel_name": "F2配电柜", "panel_type": "sub", "rated_current": 400, "location": "F2机房", "area_code": "F2", "parent_code": "UPS-OUT-001", "meter_point_code": "M002"},
    # 新增: F3楼层配电柜
    {"panel_code": "F3-PANEL-001", "panel_name": "F3配电柜", "panel_type": "sub", "rated_current": 300, "location": "F3机房", "area_code": "F3", "parent_code": "UPS-OUT-001", "meter_point_code": "M002"},
]

DISTRIBUTION_CIRCUITS = [
    # 原有回路
    {"circuit_code": "C-A1-01", "circuit_name": "A1机柜列1回路", "panel_code": "PDU-A1-001", "load_type": "IT", "rated_current": 63, "is_shiftable": False},
    {"circuit_code": "C-A1-02", "circuit_name": "A1机柜列2回路", "panel_code": "PDU-A1-001", "load_type": "IT", "rated_current": 63, "is_shiftable": False},
    {"circuit_code": "C-A1-03", "circuit_name": "A1机柜列3回路", "panel_code": "PDU-A1-002", "load_type": "IT", "rated_current": 63, "is_shiftable": False},
    {"circuit_code": "C-AC-01", "circuit_name": "精密空调1回路", "panel_code": "AC-PANEL-001", "load_type": "AC", "rated_current": 100, "is_shiftable": True, "shift_priority": 1},
    {"circuit_code": "C-AC-02", "circuit_name": "精密空调2回路", "panel_code": "AC-PANEL-001", "load_type": "AC", "rated_current": 100, "is_shiftable": True, "shift_priority": 2},
    {"circuit_code": "C-LIGHT", "circuit_name": "照明回路", "panel_code": "MDP-001", "load_type": "LIGHT", "rated_current": 32, "is_shiftable": True, "shift_priority": 3},
    # 新增: B1制冷系统回路
    {"circuit_code": "C-CH-01", "circuit_name": "冷水机组回路", "panel_code": "COOLING-PANEL-001", "load_type": "AC", "rated_current": 400, "is_shiftable": True, "shift_priority": 4},
    {"circuit_code": "C-CT-01", "circuit_name": "冷却塔回路", "panel_code": "COOLING-PANEL-001", "load_type": "AC", "rated_current": 100, "is_shiftable": True, "shift_priority": 5},
    {"circuit_code": "C-CHWP-01", "circuit_name": "冷冻水泵回路", "panel_code": "COOLING-PANEL-001", "load_type": "AC", "rated_current": 80, "is_shiftable": True, "shift_priority": 6},
    {"circuit_code": "C-CWP-01", "circuit_name": "冷却水泵回路", "panel_code": "COOLING-PANEL-001", "load_type": "AC", "rated_current": 80, "is_shiftable": True, "shift_priority": 7},
    # 新增: F1楼层回路
    {"circuit_code": "C-F1-UPS-01", "circuit_name": "F1 UPS回路", "panel_code": "F1-PANEL-001", "load_type": "UPS", "rated_current": 200, "is_shiftable": False},
    {"circuit_code": "C-F1-AC-01", "circuit_name": "F1空调回路", "panel_code": "F1-PANEL-001", "load_type": "AC", "rated_current": 200, "is_shiftable": True, "shift_priority": 8},
    # 新增: F2楼层回路
    {"circuit_code": "C-F2-UPS-01", "circuit_name": "F2 UPS回路", "panel_code": "F2-PANEL-001", "load_type": "UPS", "rated_current": 200, "is_shiftable": False},
    {"circuit_code": "C-F2-AC-01", "circuit_name": "F2空调回路", "panel_code": "F2-PANEL-001", "load_type": "AC", "rated_current": 200, "is_shiftable": True, "shift_priority": 9},
    # 新增: F3楼层回路
    {"circuit_code": "C-F3-UPS-01", "circuit_name": "F3 UPS回路", "panel_code": "F3-PANEL-001", "load_type": "UPS", "rated_current": 100, "is_shiftable": False},
    {"circuit_code": "C-F3-AC-01", "circuit_name": "F3空调回路", "panel_code": "F3-PANEL-001", "load_type": "AC", "rated_current": 100, "is_shiftable": True, "shift_priority": 10},
]

POWER_DEVICES = [
    # 原有IT设备
    {"device_code": "SRV-001", "device_name": "服务器机柜1", "device_type": "IT", "rated_power": 20, "is_it_load": True, "area_code": "A1", "circuit_code": "C-A1-01"},
    {"device_code": "SRV-002", "device_name": "服务器机柜2", "device_type": "IT", "rated_power": 20, "is_it_load": True, "area_code": "A1", "circuit_code": "C-A1-01"},
    {"device_code": "SRV-003", "device_name": "服务器机柜3", "device_type": "IT", "rated_power": 25, "is_it_load": True, "area_code": "A1", "circuit_code": "C-A1-02"},
    {"device_code": "SRV-004", "device_name": "服务器机柜4", "device_type": "IT", "rated_power": 25, "is_it_load": True, "area_code": "A1", "circuit_code": "C-A1-02"},
    {"device_code": "NET-001", "device_name": "网络机柜1", "device_type": "IT", "rated_power": 10, "is_it_load": True, "area_code": "A1", "circuit_code": "C-A1-03"},
    {"device_code": "STO-001", "device_name": "存储机柜1", "device_type": "IT", "rated_power": 30, "is_it_load": True, "area_code": "A1", "circuit_code": "C-A1-03"},
    # 原有UPS
    {"device_code": "UPS-001", "device_name": "UPS主机1", "device_type": "UPS", "rated_power": 200, "is_it_load": False, "area_code": "A1"},
    {"device_code": "UPS-002", "device_name": "UPS主机2", "device_type": "UPS", "rated_power": 200, "is_it_load": False, "area_code": "A1"},
    # 原有空调
    {"device_code": "AC-001", "device_name": "精密空调1", "device_type": "AC", "rated_power": 50, "is_it_load": False, "area_code": "B1", "circuit_code": "C-AC-01"},
    {"device_code": "AC-002", "device_name": "精密空调2", "device_type": "AC", "rated_power": 50, "is_it_load": False, "area_code": "B1", "circuit_code": "C-AC-02"},
    {"device_code": "AC-003", "device_name": "精密空调3", "device_type": "AC", "rated_power": 45, "is_it_load": False, "area_code": "B1", "circuit_code": "C-AC-02"},
    # 原有照明
    {"device_code": "LIGHT-001", "device_name": "机房照明", "device_type": "LIGHT", "rated_power": 5, "is_it_load": False, "area_code": "A1", "circuit_code": "C-LIGHT"},

    # ===== 新增: B1制冷系统设备 (与点位B1_CH_*, B1_CT_*, B1_CHWP_*, B1_CWP_*对应) =====
    # 冷水机组 (对应点位: B1_CH_AI_001~006, B1_CH_AI_011~016)
    {"device_code": "CH-001", "device_name": "1#冷水机组", "device_type": "CHILLER", "rated_power": 350, "is_it_load": False, "area_code": "B1", "circuit_code": "C-CH-01"},
    {"device_code": "CH-002", "device_name": "2#冷水机组", "device_type": "CHILLER", "rated_power": 350, "is_it_load": False, "area_code": "B1", "circuit_code": "C-CH-01"},
    # 冷却塔 (对应点位: B1_CT_AI_001~004)
    {"device_code": "CT-001", "device_name": "1#冷却塔", "device_type": "CT", "rated_power": 30, "is_it_load": False, "area_code": "B1", "circuit_code": "C-CT-01"},
    {"device_code": "CT-002", "device_name": "2#冷却塔", "device_type": "CT", "rated_power": 30, "is_it_load": False, "area_code": "B1", "circuit_code": "C-CT-01"},
    # 冷冻水泵 (对应点位: B1_CHWP_AI_001~004)
    {"device_code": "CHWP-001", "device_name": "1#冷冻水泵", "device_type": "PUMP", "rated_power": 45, "is_it_load": False, "area_code": "B1", "circuit_code": "C-CHWP-01"},
    {"device_code": "CHWP-002", "device_name": "2#冷冻水泵", "device_type": "PUMP", "rated_power": 45, "is_it_load": False, "area_code": "B1", "circuit_code": "C-CHWP-01"},
    # 冷却水泵 (对应点位: B1_CWP_AI_001~004)
    {"device_code": "CWP-001", "device_name": "1#冷却水泵", "device_type": "PUMP", "rated_power": 37, "is_it_load": False, "area_code": "B1", "circuit_code": "C-CWP-01"},
    {"device_code": "CWP-002", "device_name": "2#冷却水泵", "device_type": "PUMP", "rated_power": 37, "is_it_load": False, "area_code": "B1", "circuit_code": "C-CWP-01"},

    # ===== 新增: F1楼层设备 (与点位F1_UPS_*, F1_AC_*对应) =====
    # F1 UPS (对应点位: F1_UPS_AI_0011~0015, F1_UPS_AI_0021~0025)
    {"device_code": "F1-UPS-001", "device_name": "F1 UPS-1", "device_type": "UPS", "rated_power": 100, "is_it_load": False, "area_code": "F1", "circuit_code": "C-F1-UPS-01"},
    {"device_code": "F1-UPS-002", "device_name": "F1 UPS-2", "device_type": "UPS", "rated_power": 100, "is_it_load": False, "area_code": "F1", "circuit_code": "C-F1-UPS-01"},
    # F1精密空调 (对应点位: F1_AC_AI_0011~0013, F1_AC_AI_0021~0023, etc.)
    {"device_code": "F1-AC-001", "device_name": "F1 精密空调-1", "device_type": "AC", "rated_power": 30, "is_it_load": False, "area_code": "F1", "circuit_code": "C-F1-AC-01"},
    {"device_code": "F1-AC-002", "device_name": "F1 精密空调-2", "device_type": "AC", "rated_power": 30, "is_it_load": False, "area_code": "F1", "circuit_code": "C-F1-AC-01"},
    {"device_code": "F1-AC-003", "device_name": "F1 精密空调-3", "device_type": "AC", "rated_power": 30, "is_it_load": False, "area_code": "F1", "circuit_code": "C-F1-AC-01"},
    {"device_code": "F1-AC-004", "device_name": "F1 精密空调-4", "device_type": "AC", "rated_power": 30, "is_it_load": False, "area_code": "F1", "circuit_code": "C-F1-AC-01"},

    # ===== 新增: F2楼层设备 (与点位F2_UPS_*, F2_AC_*对应) =====
    # F2 UPS (对应点位: F2_UPS_AI_0011~0015, F2_UPS_AI_0021~0025)
    {"device_code": "F2-UPS-001", "device_name": "F2 UPS-1", "device_type": "UPS", "rated_power": 100, "is_it_load": False, "area_code": "F2", "circuit_code": "C-F2-UPS-01"},
    {"device_code": "F2-UPS-002", "device_name": "F2 UPS-2", "device_type": "UPS", "rated_power": 100, "is_it_load": False, "area_code": "F2", "circuit_code": "C-F2-UPS-01"},
    # F2精密空调 (对应点位: F2_AC_AI_0011~0013, etc.)
    {"device_code": "F2-AC-001", "device_name": "F2 精密空调-1", "device_type": "AC", "rated_power": 30, "is_it_load": False, "area_code": "F2", "circuit_code": "C-F2-AC-01"},
    {"device_code": "F2-AC-002", "device_name": "F2 精密空调-2", "device_type": "AC", "rated_power": 30, "is_it_load": False, "area_code": "F2", "circuit_code": "C-F2-AC-01"},
    {"device_code": "F2-AC-003", "device_name": "F2 精密空调-3", "device_type": "AC", "rated_power": 30, "is_it_load": False, "area_code": "F2", "circuit_code": "C-F2-AC-01"},
    {"device_code": "F2-AC-004", "device_name": "F2 精密空调-4", "device_type": "AC", "rated_power": 30, "is_it_load": False, "area_code": "F2", "circuit_code": "C-F2-AC-01"},

    # ===== 新增: F3楼层设备 (与点位F3_UPS_*, F3_AC_*对应) =====
    # F3 UPS (对应点位: F3_UPS_AI_0011~0015)
    {"device_code": "F3-UPS-001", "device_name": "F3 UPS-1", "device_type": "UPS", "rated_power": 60, "is_it_load": False, "area_code": "F3", "circuit_code": "C-F3-UPS-01"},
    # F3精密空调 (对应点位: F3_AC_AI_0011~0013, F3_AC_AI_0021~0023)
    {"device_code": "F3-AC-001", "device_name": "F3 精密空调-1", "device_type": "AC", "rated_power": 20, "is_it_load": False, "area_code": "F3", "circuit_code": "C-F3-AC-01"},
    {"device_code": "F3-AC-002", "device_name": "F3 精密空调-2", "device_type": "AC", "rated_power": 20, "is_it_load": False, "area_code": "F3", "circuit_code": "C-F3-AC-01"},
]

ELECTRICITY_PRICING = [
    {"pricing_name": "尖峰电价", "period_type": "sharp", "start_time": "11:00", "end_time": "12:00", "price": 1.5},
    {"pricing_name": "尖峰电价", "period_type": "sharp", "start_time": "18:00", "end_time": "19:00", "price": 1.5},
    {"pricing_name": "高峰电价", "period_type": "peak", "start_time": "08:00", "end_time": "11:00", "price": 1.2},
    {"pricing_name": "高峰电价", "period_type": "peak", "start_time": "12:00", "end_time": "14:00", "price": 1.2},
    {"pricing_name": "高峰电价", "period_type": "peak", "start_time": "19:00", "end_time": "21:00", "price": 1.2},
    {"pricing_name": "平段电价", "period_type": "flat", "start_time": "07:00", "end_time": "08:00", "price": 0.8},
    {"pricing_name": "平段电价", "period_type": "flat", "start_time": "14:00", "end_time": "18:00", "price": 0.8},
    {"pricing_name": "平段电价", "period_type": "flat", "start_time": "21:00", "end_time": "22:00", "price": 0.8},
    {"pricing_name": "低谷电价", "period_type": "valley", "start_time": "22:00", "end_time": "00:00", "price": 0.4},
    {"pricing_name": "低谷电价", "period_type": "valley", "start_time": "06:00", "end_time": "07:00", "price": 0.4},
    {"pricing_name": "深谷电价", "period_type": "deep_valley", "start_time": "00:00", "end_time": "06:00", "price": 0.25},
]


class DemoDataService:
    """演示数据服务"""

    def __init__(self):
        self.is_loaded = False
        self.loading = False
        self.progress = 0
        self.progress_message = ""
        self._lock = asyncio.Lock()  # 防止并发操作

    async def check_demo_data_status(self) -> dict:
        """检查演示数据状态"""
        async with async_session() as session:
            # 检查点位数量
            result = await session.execute(select(func.count(Point.id)))
            point_count = result.scalar() or 0

            # 检查是否有模拟数据标记
            # 演示数据点位编码以B1_/F1_/F2_/F3_/A1_开头
            result = await session.execute(
                select(func.count(Point.id)).where(
                    Point.point_code.like("B1_%") |
                    Point.point_code.like("F1_%") |
                    Point.point_code.like("F2_%") |
                    Point.point_code.like("F3_%") |
                    Point.point_code.like("A1_%")
                )
            )
            demo_point_count = result.scalar() or 0

            # 检查历史数据
            result = await session.execute(select(func.count(PointHistory.id)))
            history_count = result.scalar() or 0

            # 检查配电设备数量
            result = await session.execute(select(func.count(PowerDevice.id)))
            device_count = result.scalar() or 0

            # 检查设备与点位关联状态
            result = await session.execute(
                select(func.count(PowerDevice.id)).where(
                    PowerDevice.power_point_id.isnot(None)
                )
            )
            linked_device_count = result.scalar() or 0

            self.is_loaded = demo_point_count > 300

            return {
                "is_loaded": self.is_loaded,
                "point_count": point_count,
                "demo_point_count": demo_point_count,
                "history_count": history_count,
                "device_count": device_count,
                "linked_device_count": linked_device_count,
                "sync_status": "synced" if linked_device_count > 0 else "not_synced",
                "loading": self.loading,
                "progress": self.progress,
                "progress_message": self.progress_message
            }

    async def load_demo_data(
        self,
        days: int = 30,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> dict:
        """加载演示数据（带进度回调）"""
        if self._lock.locked():
            return {"success": False, "message": "正在加载中，请稍候"}

        async with self._lock:
            self.loading = True
            self.progress = 0
            self.progress_message = "初始化..."

            try:
                await init_db()

                # Phase 1: 检查并清理旧数据 (0-10%)
                self._update_progress(5, "检查现有数据...", progress_callback)
                status = await self.check_demo_data_status()

                if status["demo_point_count"] > 0:
                    self._update_progress(8, "清理旧演示数据...", progress_callback)
                    await self._clear_demo_data()

                # Phase 2: 创建点位 (10-35%)
                self._update_progress(10, "创建监控点位...", progress_callback)
                point_count = await self._create_points(progress_callback)

                # Phase 3: 创建配电系统 (35-45%)
                self._update_progress(35, "创建配电系统...", progress_callback)
                await self._create_distribution_system(progress_callback)

                # Phase 4: 生成历史数据 (45-85%)
                self._update_progress(45, "生成历史数据...", progress_callback)
                history_count = await self._generate_history(days, progress_callback)

                # Phase 5: 生成需量数据 (85-88%)
                self._update_progress(85, "生成需量数据...", progress_callback)
                await self._generate_demand_data(progress_callback)

                # Phase 6: 生成楼层图 (88-92%)
                self._update_progress(88, "生成楼层平面图...", progress_callback)
                await self._generate_floor_maps(progress_callback)

                # Phase 7: 生成PUE历史 (92-100%)
                self._update_progress(92, "生成能耗数据...", progress_callback)
                await self._generate_pue_history(days, progress_callback)

                self._update_progress(100, "加载完成", progress_callback)
                self.is_loaded = True

                return {
                    "success": True,
                    "message": f"成功加载演示数据",
                    "point_count": point_count,
                    "history_count": history_count,
                    "days": days
                }

            except Exception as e:
                self._update_progress(0, f"加载失败: {str(e)}", progress_callback)
                return {"success": False, "message": str(e)}
            finally:
                self.loading = False

    async def sync_device_point_relations(self) -> dict:
        """
        同步配电设备与点位的关联关系（双向同步）
        这个方法可以在系统运行时调用，用于修复或更新关联关系
        """
        if self._lock.locked():
            return {"success": False, "message": "正在操作中，请稍候"}

        async with self._lock:
            self.loading = True
            self.progress = 0
            self.progress_message = "开始同步..."

            try:
                async with async_session() as session:
                    # 使用新的智能匹配引擎执行完整双向同步
                    self._update_progress(10, "执行双向同步...")
                    result = await PointDeviceMatcher.full_sync(session)

                    self._update_progress(100, "同步完成")

                    # 输出同步统计日志
                    stats = result.get("statistics", {})
                    logger.info(
                        f"设备点位同步完成: "
                        f"更新 {result['updated_devices']} 个设备, "
                        f"{result['updated_points']} 个点位关联, "
                        f"设备关联率 {stats.get('device_link_rate', 0)}%, "
                        f"点位关联率 {stats.get('point_link_rate', 0)}%"
                    )

                    return {
                        "success": True,
                        "message": f"同步完成，更新了 {result['updated_devices']} 个设备关联，{result['updated_points']} 个点位反向关联",
                        "total_devices": stats.get("total_devices", 0),
                        "linked_devices": stats.get("linked_devices", 0),
                        "updated_count": result["updated_devices"],
                        "updated_points": result["updated_points"],
                        "statistics": stats
                    }

            except Exception as e:
                self._update_progress(0, f"同步失败: {str(e)}")
                logger.error(f"设备点位同步失败: {str(e)}")
                return {"success": False, "message": str(e)}
            finally:
                self.loading = False

    async def unload_demo_data(self) -> dict:
        """卸载演示数据"""
        if self._lock.locked():
            return {"success": False, "message": "正在操作中，请稍候"}

        async with self._lock:
            self.loading = True
            self.progress = 0
            self.progress_message = "正在卸载..."

            try:
                await self._clear_demo_data()
                self.is_loaded = False
                return {"success": True, "message": "演示数据已卸载"}
            except Exception as e:
                return {"success": False, "message": str(e)}
            finally:
                self.loading = False

    async def refresh_dates(self) -> dict:
        """刷新历史数据日期到最近30天（后台任务）"""
        if self._lock.locked():
            return {"success": False, "message": "正在操作中，请稍候"}

        async with self._lock:
            self.loading = True
            self.progress = 0
            self.progress_message = "开始刷新日期..."

            try:
                async with async_session() as session:
                    # 获取历史数据的时间范围
                    self._update_progress(10, "获取历史数据时间范围...")
                    result = await session.execute(
                        select(func.min(PointHistory.recorded_at), func.max(PointHistory.recorded_at))
                    )
                    min_date, max_date = result.one()

                    if not min_date or not max_date:
                        self.loading = False
                        return {"success": False, "message": "没有历史数据"}

                    # 计算偏移量：将max_date调整到当前时间
                    now = datetime.now()
                    offset = now - max_date

                    # 获取总记录数
                    self._update_progress(20, "统计数据量...")
                    count_result = await session.execute(select(func.count(PointHistory.id)))
                    total_history = count_result.scalar() or 0

                    # 更新PointHistory日期
                    self._update_progress(30, f"更新 {total_history:,} 条历史数据...")
                    await session.execute(
                        update(PointHistory).values(
                            recorded_at=PointHistory.recorded_at + offset
                        )
                    )
                    await session.commit()

                    # 更新PUEHistory日期
                    self._update_progress(85, "更新能耗数据日期...")
                    await session.execute(
                        update(PUEHistory).values(
                            record_time=PUEHistory.record_time + offset
                        )
                    )
                    await session.commit()

                    self._update_progress(100, "日期刷新完成")

                    return {
                        "success": True,
                        "message": f"日期已更新，偏移 {offset.days} 天",
                        "offset_days": offset.days
                    }

            except Exception as e:
                self._update_progress(0, f"刷新失败: {str(e)}")
                return {"success": False, "message": str(e)}
            finally:
                self.loading = False

    async def _clear_demo_data(self):
        """清理演示数据 - 清理所有相关表"""
        async with async_session() as session:
            # ========== 清理点位相关数据 ==========
            # 注意：演示系统中，历史数据都是由演示数据生成器创建的，所以全部清除

            # 删除所有历史数据（演示数据产生的）
            await session.execute(delete(PointHistory))

            # 获取演示点位ID (包含新增的A1_开头的点位)
            result = await session.execute(
                select(Point.id).where(
                    Point.point_code.like("B1_%") |
                    Point.point_code.like("F1_%") |
                    Point.point_code.like("F2_%") |
                    Point.point_code.like("F3_%") |
                    Point.point_code.like("A1_%")
                )
            )
            demo_point_ids = [r[0] for r in result.fetchall()]

            if demo_point_ids:
                # 删除告警阈值
                await session.execute(
                    delete(AlarmThreshold).where(AlarmThreshold.point_id.in_(demo_point_ids))
                )
                # 删除实时数据
                await session.execute(
                    delete(PointRealtime).where(PointRealtime.point_id.in_(demo_point_ids))
                )
                # 删除点位
                await session.execute(
                    delete(Point).where(Point.id.in_(demo_point_ids))
                )

            # ========== 清理告警数据（模拟器产生的）==========
            await session.execute(delete(Alarm))

            # ========== 清理能源管理相关数据（按依赖顺序删除）==========

            # 1. 清理执行相关表（最底层）
            await session.execute(delete(ExecutionResult))
            await session.execute(delete(ExecutionTask))
            await session.execute(delete(ExecutionPlan))

            # 2. 清理措施相关表
            await session.execute(delete(MeasureExecutionLog))
            await session.execute(delete(OpportunityMeasure))
            await session.execute(delete(ProposalMeasure))

            # 3. 清理方案/机会表
            await session.execute(delete(EnergyOpportunity))
            await session.execute(delete(EnergySavingProposal))
            await session.execute(delete(EnergySuggestion))

            # 4. 清理调节/调度表
            await session.execute(delete(RegulationHistory))
            await session.execute(delete(LoadRegulationConfig))
            await session.execute(delete(DispatchSchedule))
            await session.execute(delete(DispatchableDevice))

            # 5. 清理需量分析表
            await session.execute(delete(DemandAnalysisRecord))
            await session.execute(delete(Demand15MinData))
            await session.execute(delete(OverDemandEvent))
            await session.execute(delete(DemandHistory))

            # 6. 清理设备负荷/曲线表
            await session.execute(delete(DeviceShiftConfig))
            await session.execute(delete(DeviceLoadProfile))
            await session.execute(delete(PowerCurveData))

            # 7. 清理能耗统计表
            await session.execute(delete(OptimizationResult))
            await session.execute(delete(MonthlyStatistics))
            await session.execute(delete(RealtimeMonitoring))
            await session.execute(delete(EnergyMonthly))
            await session.execute(delete(EnergyDaily))
            await session.execute(delete(EnergyHourly))
            await session.execute(delete(PUEHistory))

            # 8. 清理电价配置表
            await session.execute(delete(PricingConfig))
            await session.execute(delete(ElectricityPricing))

            # 9. 清理系统配置表
            await session.execute(delete(StorageSystemConfig))
            await session.execute(delete(PVSystemConfig))

            # 10. 清理配电系统（按层级顺序删除）
            await session.execute(delete(PowerDevice))
            await session.execute(delete(DistributionCircuit))
            await session.execute(delete(DistributionPanel))
            await session.execute(delete(MeterPoint))
            await session.execute(delete(Transformer))

            # 11. 清理楼层图数据
            await session.execute(delete(FloorMap))

            await session.commit()

    async def _create_points(self, progress_callback) -> int:
        """创建点位"""
        async with async_session() as session:
            points = get_all_points()
            total_created = 0
            total_points = sum(len(plist) for plist in points.values())

            for point_type, point_list in points.items():
                for i, p in enumerate(point_list):
                    point = Point(
                        point_code=p["point_code"],
                        point_name=p["point_name"],
                        point_type=point_type,
                        device_type=p["device_type"],
                        area_code=p["point_code"].split("_")[0],
                        unit=p.get("unit", ""),
                        data_type=p.get("data_type", "float" if point_type == "AI" else "boolean"),
                        min_range=p.get("min_range"),
                        max_range=p.get("max_range"),
                        collect_interval=p.get("collect_interval", 10),
                        is_enabled=True,
                    )
                    session.add(point)
                    await session.flush()

                    # 创建实时数据
                    realtime = PointRealtime(
                        point_id=point.id,
                        value=0,
                        status="normal",
                    )
                    session.add(realtime)

                    # 创建告警阈值
                    thresholds = get_threshold_for_point(p["point_code"], p["point_name"])
                    for t in thresholds:
                        threshold = AlarmThreshold(
                            point_id=point.id,
                            threshold_type=t["type"],
                            threshold_value=t["value"],
                            alarm_level=t["level"],
                            alarm_message=t["message"],
                            is_enabled=True,
                        )
                        session.add(threshold)

                    total_created += 1

                    # 每50个点位更新一次进度
                    if total_created % 50 == 0:
                        progress = 10 + int((total_created / total_points) * 30)
                        self._update_progress(progress, f"创建点位 {total_created}/{total_points}", progress_callback)

            await session.commit()
            return total_created

    async def _create_distribution_system(self, progress_callback):
        """创建配电系统数据（使用智能匹配引擎，支持双向关联）"""
        async with async_session() as session:
            # 1. 创建变压器
            transformer_map = {}
            for t in TRANSFORMERS:
                transformer = Transformer(**t)
                session.add(transformer)
                await session.flush()
                transformer_map[t["transformer_code"]] = transformer.id
            self._update_progress(37, f"创建 {len(TRANSFORMERS)} 个变压器", progress_callback)

            # 2. 创建计量点
            meter_point_map = {}
            for mp in METER_POINTS:
                data = mp.copy()
                transformer_code = data.pop("transformer_code")
                data["transformer_id"] = transformer_map.get(transformer_code)
                meter_point = MeterPoint(**data)
                session.add(meter_point)
                await session.flush()
                meter_point_map[mp["meter_code"]] = meter_point.id
            self._update_progress(38, f"创建 {len(METER_POINTS)} 个计量点", progress_callback)

            # 3. 创建配电柜
            panel_map = {}
            for p in DISTRIBUTION_PANELS:
                data = p.copy()
                parent_code = data.pop("parent_code", None)
                meter_point_code = data.pop("meter_point_code", None)
                if parent_code and parent_code in panel_map:
                    data["parent_panel_id"] = panel_map[parent_code]
                if meter_point_code and meter_point_code in meter_point_map:
                    data["meter_point_id"] = meter_point_map[meter_point_code]
                panel = DistributionPanel(**data)
                session.add(panel)
                await session.flush()
                panel_map[p["panel_code"]] = panel.id
            self._update_progress(40, f"创建 {len(DISTRIBUTION_PANELS)} 个配电柜", progress_callback)

            # 4. 创建配电回路
            circuit_map = {}
            for c in DISTRIBUTION_CIRCUITS:
                data = c.copy()
                panel_code = data.pop("panel_code")
                data["panel_id"] = panel_map.get(panel_code)
                circuit = DistributionCircuit(**data)
                session.add(circuit)
                await session.flush()
                circuit_map[c["circuit_code"]] = circuit.id
            self._update_progress(42, f"创建 {len(DISTRIBUTION_CIRCUITS)} 个配电回路", progress_callback)

            # 5. 先获取所有点位，用于后续关联
            point_map = await self._build_point_map(session)

            # 6. 创建用电设备并使用智能匹配引擎关联点位
            linked_count = 0
            linked_points = 0
            device_objects = []

            for d in POWER_DEVICES:
                data = d.copy()
                circuit_code = data.pop("circuit_code", None)
                if circuit_code and circuit_code in circuit_map:
                    data["circuit_id"] = circuit_map[circuit_code]

                # 使用智能匹配引擎查找匹配的点位
                point_ids = PointDeviceMatcher.find_matching_points(
                    d["device_code"],
                    d["device_name"],
                    d.get("area_code", ""),
                    point_map
                )

                if point_ids["power_point_id"]:
                    data["power_point_id"] = point_ids["power_point_id"]
                    linked_count += 1
                if point_ids["current_point_id"]:
                    data["current_point_id"] = point_ids["current_point_id"]
                if point_ids["energy_point_id"]:
                    data["energy_point_id"] = point_ids["energy_point_id"]

                device = PowerDevice(**data)
                session.add(device)
                await session.flush()

                # 双向同步：设置点位的 energy_device_id
                point_count = await PointDeviceMatcher.sync_bidirectional_relations(
                    session,
                    device.id,
                    point_ids["power_point_id"],
                    point_ids["current_point_id"],
                    point_ids["energy_point_id"],
                )
                linked_points += point_count

            self._update_progress(
                44,
                f"创建 {len(POWER_DEVICES)} 个用电设备 (关联 {linked_count} 个设备, {linked_points} 个点位)",
                progress_callback
            )

            # 输出同步统计日志
            logger.info(
                f"配电系统创建完成: "
                f"{len(POWER_DEVICES)} 个设备, "
                f"{linked_count} 个设备已关联点位, "
                f"{linked_points} 个点位反向关联"
            )

            # 7. 创建电价配置
            for ep in ELECTRICITY_PRICING:
                pricing = ElectricityPricing(
                    **ep,
                    effective_date=datetime.now().date()
                )
                session.add(pricing)
            self._update_progress(45, f"创建 {len(ELECTRICITY_PRICING)} 条电价配置", progress_callback)

            await session.commit()

            # 保存计量点映射供后续使用
            self._meter_point_map = meter_point_map

    async def _build_point_map(self, session) -> dict:
        """构建点位映射表，用于设备关联"""
        result = await session.execute(select(Point))
        points = result.scalars().all()

        point_map = {}
        for p in points:
            point_map[p.point_code] = {
                "id": p.id,
                "name": p.point_name,
                "unit": p.unit
            }
        return point_map

    def _find_matching_points(self, device_code: str, device_name: str, area_code: str, point_map: dict) -> dict:
        """
        根据设备编码和名称查找匹配的点位
        返回: {"power_point_id": id, "current_point_id": id, "energy_point_id": id}
        """
        result = {
            "power_point_id": None,
            "current_point_id": None,
            "energy_point_id": None
        }

        # 设备编码到点位前缀的映射规则
        mapping_rules = {
            # 服务器机柜 SRV-001~004 -> A1_SRV_AI_001~012
            "SRV-001": {"prefix": "A1_SRV_AI_", "power": "001", "current": "002", "energy": "003"},
            "SRV-002": {"prefix": "A1_SRV_AI_", "power": "004", "current": "005", "energy": "006"},
            "SRV-003": {"prefix": "A1_SRV_AI_", "power": "007", "current": "008", "energy": "009"},
            "SRV-004": {"prefix": "A1_SRV_AI_", "power": "010", "current": "011", "energy": "012"},
            # 网络机柜 NET-001 -> A1_NET_AI_001~003
            "NET-001": {"prefix": "A1_NET_AI_", "power": "001", "current": "002", "energy": "003"},
            # 存储机柜 STO-001 -> A1_STO_AI_001~003
            "STO-001": {"prefix": "A1_STO_AI_", "power": "001", "current": "002", "energy": "003"},
            # UPS主机 UPS-001/002 -> A1_UPS_AI_001~008
            "UPS-001": {"prefix": "A1_UPS_AI_", "power": "002", "current": "003"},  # 输出功率
            "UPS-002": {"prefix": "A1_UPS_AI_", "power": "006", "current": "007"},
            # 照明 LIGHT-001 -> A1_LIGHT_AI_001~003
            "LIGHT-001": {"prefix": "A1_LIGHT_AI_", "power": "001", "current": "002"},
            # 冷水机组 CH-001/002 -> B1_CH_AI_005/015 (功率), B1_CH_AI_007/017 (电流)
            "CH-001": {"prefix": "B1_CH_AI_", "power": "005", "current": "007"},
            "CH-002": {"prefix": "B1_CH_AI_", "power": "015", "current": "017"},
            # 冷却塔 CT-001/002 -> B1_CT_AI_005/006 (功率)
            "CT-001": {"prefix": "B1_CT_AI_", "power": "005"},
            "CT-002": {"prefix": "B1_CT_AI_", "power": "006"},
            # 冷冻水泵 CHWP-001/002 -> B1_CHWP_AI_005/006 (功率), B1_CHWP_AI_002/004 (电流)
            "CHWP-001": {"prefix": "B1_CHWP_AI_", "power": "005", "current": "002"},
            "CHWP-002": {"prefix": "B1_CHWP_AI_", "power": "006", "current": "004"},
            # 冷却水泵 CWP-001/002 -> B1_CWP_AI_005/006 (功率), B1_CWP_AI_002/004 (电流)
            "CWP-001": {"prefix": "B1_CWP_AI_", "power": "005", "current": "002"},
            "CWP-002": {"prefix": "B1_CWP_AI_", "power": "006", "current": "004"},
            # F1/F2/F3 UPS -> F*_UPS_AI_*
            "F1-UPS-001": {"prefix": "F1_UPS_AI_", "power": "0013"},  # 负载率作为功率指标
            "F1-UPS-002": {"prefix": "F1_UPS_AI_", "power": "0023"},
            "F2-UPS-001": {"prefix": "F2_UPS_AI_", "power": "0013"},
            "F2-UPS-002": {"prefix": "F2_UPS_AI_", "power": "0023"},
            "F3-UPS-001": {"prefix": "F3_UPS_AI_", "power": "0013"},
            # F1/F2/F3 精密空调使用回风温度点位 (用于状态监控)
            "F1-AC-001": {"prefix": "F1_AC_AI_", "power": "0011"},
            "F1-AC-002": {"prefix": "F1_AC_AI_", "power": "0021"},
            "F1-AC-003": {"prefix": "F1_AC_AI_", "power": "0031"},
            "F1-AC-004": {"prefix": "F1_AC_AI_", "power": "0041"},
            "F2-AC-001": {"prefix": "F2_AC_AI_", "power": "0011"},
            "F2-AC-002": {"prefix": "F2_AC_AI_", "power": "0021"},
            "F2-AC-003": {"prefix": "F2_AC_AI_", "power": "0031"},
            "F2-AC-004": {"prefix": "F2_AC_AI_", "power": "0041"},
            "F3-AC-001": {"prefix": "F3_AC_AI_", "power": "0011"},
            "F3-AC-002": {"prefix": "F3_AC_AI_", "power": "0021"},
            # 原有精密空调 AC-001~003 没有专用点位，暂不关联
        }

        rule = mapping_rules.get(device_code)
        if rule:
            prefix = rule["prefix"]
            if rule.get("power"):
                point_code = f"{prefix}{rule['power']}"
                if point_code in point_map:
                    result["power_point_id"] = point_map[point_code]["id"]
            if rule.get("current"):
                point_code = f"{prefix}{rule['current']}"
                if point_code in point_map:
                    result["current_point_id"] = point_map[point_code]["id"]
            if rule.get("energy"):
                point_code = f"{prefix}{rule['energy']}"
                if point_code in point_map:
                    result["energy_point_id"] = point_map[point_code]["id"]

        return result

    async def _generate_demand_data(self, progress_callback):
        """生成15分钟需量数据"""
        if not hasattr(self, '_meter_point_map') or not self._meter_point_map:
            return

        async with async_session() as session:
            now = datetime.now()
            records = []

            for meter_code, meter_point_id in self._meter_point_map.items():
                declared_demand = 800 if meter_code == "M001" else 500 if meter_code == "M002" else 300

                # 生成7天数据
                for day_offset in range(7):
                    date = now - timedelta(days=day_offset)

                    for hour in range(24):
                        for minute in [0, 15, 30, 45]:
                            timestamp = date.replace(hour=hour, minute=minute, second=0, microsecond=0)

                            base_ratio = 0.7 if 8 <= hour <= 18 else 0.4
                            fluctuation = random.uniform(-0.1, 0.1)
                            demand = declared_demand * (base_ratio + fluctuation)

                            is_over = random.random() < 0.05
                            if is_over:
                                demand = declared_demand * random.uniform(1.0, 1.15)

                            if 8 <= hour < 11 or 18 <= hour < 21:
                                time_period = "peak"
                                is_peak = True
                            elif 23 <= hour or hour < 7:
                                time_period = "valley"
                                is_peak = False
                            else:
                                time_period = "flat"
                                is_peak = False

                            record = Demand15MinData(
                                meter_point_id=meter_point_id,
                                timestamp=timestamp,
                                average_power=round(demand, 2),
                                max_power=round(demand * random.uniform(1.0, 1.1), 2),
                                min_power=round(demand * random.uniform(0.9, 1.0), 2),
                                rolling_demand=round(demand, 2),
                                declared_demand=declared_demand,
                                demand_ratio=round(demand / declared_demand * 100, 2),
                                is_peak_period=is_peak,
                                time_period=time_period,
                                is_over_declared=is_over
                            )
                            records.append(record)

            session.add_all(records)
            await session.commit()
            self._update_progress(88, f"生成 {len(records)} 条需量数据", progress_callback)

    async def _generate_history(self, days: int, progress_callback) -> int:
        """生成历史数据"""
        from ..services.history_generator import HistoryGenerator

        generator = HistoryGenerator(days=days)
        total_hours = days * 24

        async with async_session() as session:
            result = await session.execute(select(Point).where(Point.is_enabled == True))
            points = result.scalars().all()

            total_records = 0
            batch_records = []
            batch_size = 1000

            for i, point in enumerate(points):
                records = generator.generate_point_history(point, total_hours)

                for r in records:
                    batch_records.append(PointHistory(**r))

                    if len(batch_records) >= batch_size:
                        session.add_all(batch_records)
                        await session.commit()
                        total_records += len(batch_records)
                        batch_records = []

                        # 更新进度 45-85%
                        progress = 45 + int((total_records / (len(points) * total_hours)) * 40)
                        self._update_progress(
                            min(progress, 84),
                            f"生成历史数据 {total_records} 条...",
                            progress_callback
                        )

            if batch_records:
                session.add_all(batch_records)
                await session.commit()
                total_records += len(batch_records)

            return total_records

    async def _generate_floor_maps(self, progress_callback):
        """生成楼层平面图数据"""
        generator = FloorMapGenerator()

        async with async_session() as session:
            floor_codes = ["B1", "F1", "F2", "F3"]

            for floor_code in floor_codes:
                config = FLOOR_CONFIG.get(floor_code, {})

                # 生成2D图
                map_2d = generator.generate_2d_map(floor_code)
                floor_map_2d = FloorMap(
                    floor_code=floor_code,
                    floor_name=config.get("name", f"Floor {floor_code}"),
                    map_type="2d",
                    map_data=json.dumps(map_2d, ensure_ascii=False),
                    is_default=(floor_code == "F1")
                )
                session.add(floor_map_2d)

                # 生成3D图
                map_3d = generator.generate_3d_map(floor_code)
                floor_map_3d = FloorMap(
                    floor_code=floor_code,
                    floor_name=config.get("name", f"Floor {floor_code}"),
                    map_type="3d",
                    map_data=json.dumps(map_3d, ensure_ascii=False),
                    is_default=False
                )
                session.add(floor_map_3d)

            await session.commit()
            self._update_progress(91, "生成 8 张楼层图 (4层 x 2类型)", progress_callback)

    async def _generate_pue_history(self, days: int, progress_callback):
        """生成PUE历史数据"""
        from ..services.history_generator import HistoryGenerator

        generator = HistoryGenerator(days=days)
        await generator.generate_energy_history()

    def _update_progress(self, progress: int, message: str, callback: Optional[Callable] = None):
        """更新进度"""
        self.progress = progress
        self.progress_message = message
        if callback:
            callback(progress, message)


# 全局服务实例
demo_data_service = DemoDataService()
