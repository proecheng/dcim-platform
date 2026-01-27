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
    PowerDevice, EnergyHourly, EnergyDaily, ElectricityPricing, Demand15MinData
)
from ..data.building_points import get_all_points, get_threshold_for_point
from .floor_map_generator import FloorMapGenerator, FLOOR_CONFIG


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
    {"panel_code": "MDP-001", "panel_name": "主配电柜", "panel_type": "main", "rated_current": 2000, "location": "配电室A", "area_code": "A1", "meter_point_code": "M001"},
    {"panel_code": "ATS-001", "panel_name": "ATS切换柜", "panel_type": "sub", "rated_current": 1600, "location": "配电室A", "area_code": "A1", "parent_code": "MDP-001", "meter_point_code": "M001"},
    {"panel_code": "UPS-IN-001", "panel_name": "UPS输入柜", "panel_type": "ups_input", "rated_current": 800, "location": "UPS室", "area_code": "A1", "parent_code": "ATS-001", "meter_point_code": "M001"},
    {"panel_code": "UPS-OUT-001", "panel_name": "UPS输出柜", "panel_type": "ups_output", "rated_current": 600, "location": "UPS室", "area_code": "A1", "meter_point_code": "M002"},
    {"panel_code": "PDU-A1-001", "panel_name": "A1区列头柜1", "panel_type": "sub", "rated_current": 250, "location": "机房A1区", "area_code": "A1", "parent_code": "UPS-OUT-001", "meter_point_code": "M002"},
    {"panel_code": "PDU-A1-002", "panel_name": "A1区列头柜2", "panel_type": "sub", "rated_current": 250, "location": "机房A1区", "area_code": "A1", "parent_code": "UPS-OUT-001", "meter_point_code": "M002"},
    {"panel_code": "AC-PANEL-001", "panel_name": "空调配电柜", "panel_type": "sub", "rated_current": 400, "location": "配电室B", "area_code": "B1", "parent_code": "MDP-001", "meter_point_code": "M003"},
]

DISTRIBUTION_CIRCUITS = [
    {"circuit_code": "C-A1-01", "circuit_name": "A1机柜列1回路", "panel_code": "PDU-A1-001", "load_type": "IT", "rated_current": 63, "is_shiftable": False},
    {"circuit_code": "C-A1-02", "circuit_name": "A1机柜列2回路", "panel_code": "PDU-A1-001", "load_type": "IT", "rated_current": 63, "is_shiftable": False},
    {"circuit_code": "C-A1-03", "circuit_name": "A1机柜列3回路", "panel_code": "PDU-A1-002", "load_type": "IT", "rated_current": 63, "is_shiftable": False},
    {"circuit_code": "C-AC-01", "circuit_name": "精密空调1回路", "panel_code": "AC-PANEL-001", "load_type": "AC", "rated_current": 100, "is_shiftable": True, "shift_priority": 1},
    {"circuit_code": "C-AC-02", "circuit_name": "精密空调2回路", "panel_code": "AC-PANEL-001", "load_type": "AC", "rated_current": 100, "is_shiftable": True, "shift_priority": 2},
    {"circuit_code": "C-LIGHT", "circuit_name": "照明回路", "panel_code": "MDP-001", "load_type": "LIGHT", "rated_current": 32, "is_shiftable": True, "shift_priority": 3},
]

POWER_DEVICES = [
    {"device_code": "SRV-001", "device_name": "服务器机柜1", "device_type": "IT", "rated_power": 20, "is_it_load": True, "area_code": "A1", "circuit_code": "C-A1-01"},
    {"device_code": "SRV-002", "device_name": "服务器机柜2", "device_type": "IT", "rated_power": 20, "is_it_load": True, "area_code": "A1", "circuit_code": "C-A1-01"},
    {"device_code": "SRV-003", "device_name": "服务器机柜3", "device_type": "IT", "rated_power": 25, "is_it_load": True, "area_code": "A1", "circuit_code": "C-A1-02"},
    {"device_code": "SRV-004", "device_name": "服务器机柜4", "device_type": "IT", "rated_power": 25, "is_it_load": True, "area_code": "A1", "circuit_code": "C-A1-02"},
    {"device_code": "NET-001", "device_name": "网络机柜1", "device_type": "IT", "rated_power": 10, "is_it_load": True, "area_code": "A1", "circuit_code": "C-A1-03"},
    {"device_code": "STO-001", "device_name": "存储机柜1", "device_type": "IT", "rated_power": 30, "is_it_load": True, "area_code": "A1", "circuit_code": "C-A1-03"},
    {"device_code": "UPS-001", "device_name": "UPS主机1", "device_type": "UPS", "rated_power": 200, "is_it_load": False, "area_code": "A1"},
    {"device_code": "UPS-002", "device_name": "UPS主机2", "device_type": "UPS", "rated_power": 200, "is_it_load": False, "area_code": "A1"},
    {"device_code": "AC-001", "device_name": "精密空调1", "device_type": "AC", "rated_power": 50, "is_it_load": False, "area_code": "B1", "circuit_code": "C-AC-01"},
    {"device_code": "AC-002", "device_name": "精密空调2", "device_type": "AC", "rated_power": 50, "is_it_load": False, "area_code": "B1", "circuit_code": "C-AC-02"},
    {"device_code": "AC-003", "device_name": "精密空调3", "device_type": "AC", "rated_power": 45, "is_it_load": False, "area_code": "B1", "circuit_code": "C-AC-02"},
    {"device_code": "LIGHT-001", "device_name": "机房照明", "device_type": "LIGHT", "rated_power": 5, "is_it_load": False, "area_code": "A1", "circuit_code": "C-LIGHT"},
]

ELECTRICITY_PRICING = [
    {"pricing_name": "峰时电价", "period_type": "peak", "start_time": "08:00", "end_time": "11:00", "price": 1.2},
    {"pricing_name": "峰时电价", "period_type": "peak", "start_time": "18:00", "end_time": "21:00", "price": 1.2},
    {"pricing_name": "平时电价", "period_type": "normal", "start_time": "07:00", "end_time": "08:00", "price": 0.8},
    {"pricing_name": "平时电价", "period_type": "normal", "start_time": "11:00", "end_time": "18:00", "price": 0.8},
    {"pricing_name": "平时电价", "period_type": "normal", "start_time": "21:00", "end_time": "23:00", "price": 0.8},
    {"pricing_name": "谷时电价", "period_type": "valley", "start_time": "23:00", "end_time": "07:00", "price": 0.4},
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
            # 演示数据点位编码以B1_/F1_/F2_/F3_开头
            result = await session.execute(
                select(func.count(Point.id)).where(
                    Point.point_code.like("B1_%") |
                    Point.point_code.like("F1_%") |
                    Point.point_code.like("F2_%") |
                    Point.point_code.like("F3_%")
                )
            )
            demo_point_count = result.scalar() or 0

            # 检查历史数据
            result = await session.execute(select(func.count(PointHistory.id)))
            history_count = result.scalar() or 0

            self.is_loaded = demo_point_count > 300

            return {
                "is_loaded": self.is_loaded,
                "point_count": point_count,
                "demo_point_count": demo_point_count,
                "history_count": history_count,
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
        """清理演示数据"""
        async with async_session() as session:
            # 获取演示点位ID
            result = await session.execute(
                select(Point.id).where(
                    Point.point_code.like("B1_%") |
                    Point.point_code.like("F1_%") |
                    Point.point_code.like("F2_%") |
                    Point.point_code.like("F3_%")
                )
            )
            demo_point_ids = [r[0] for r in result.fetchall()]

            if demo_point_ids:
                # 删除相关历史数据
                await session.execute(
                    delete(PointHistory).where(PointHistory.point_id.in_(demo_point_ids))
                )
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

            # 删除PUE历史
            await session.execute(delete(PUEHistory))

            # 清理配电系统数据
            await session.execute(delete(Demand15MinData))
            await session.execute(delete(EnergyHourly))
            await session.execute(delete(EnergyDaily))
            await session.execute(delete(ElectricityPricing))
            await session.execute(delete(PowerDevice))
            await session.execute(delete(DistributionCircuit))
            await session.execute(delete(DistributionPanel))
            await session.execute(delete(MeterPoint))
            await session.execute(delete(Transformer))

            # 清理楼层图数据
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
        """创建配电系统数据"""
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

            # 5. 创建用电设备
            for d in POWER_DEVICES:
                data = d.copy()
                circuit_code = data.pop("circuit_code", None)
                if circuit_code and circuit_code in circuit_map:
                    data["circuit_id"] = circuit_map[circuit_code]
                device = PowerDevice(**data)
                session.add(device)
            self._update_progress(44, f"创建 {len(POWER_DEVICES)} 个用电设备", progress_callback)

            # 6. 创建电价配置
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
