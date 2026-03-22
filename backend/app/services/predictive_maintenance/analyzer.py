"""DegradationAnalyzer 调度器 — Story 36.1 / 36.5"""

import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...models.device import Device
from ...models.point import Point
from ...models.history import PointHistoryArchive, PointHistory
from ...models.diagnosis import BatterySOHRecord
from .base import DegradationResult
from .registry import get_degradation_plugin
from .config import DEVICE_TYPE_MAP, DEFAULT_WINDOW_DAYS, FALLBACK_HISTORY_DAYS, VALID_QUALITY_THRESHOLD

logger = logging.getLogger(__name__)


class DegradationAnalyzer:
    """劣化分析调度器 — 管理设备与插件的映射和批量分析"""

    def __init__(self, db: AsyncSession, window_days: int = DEFAULT_WINDOW_DAYS):
        self.db = db
        self.window_days = window_days

    async def analyze_device(self, device_id: int, device: Device | None = None) -> DegradationResult | None:
        """对单个设备执行劣化分析"""
        if device is None:
            result = await self.db.execute(
                select(Device).where(Device.id == device_id)
            )
            device = result.scalar_one_or_none()
        if not device:
            logger.warning("设备 %d 不存在", device_id)
            return None

        plugin_key = DEVICE_TYPE_MAP.get(device.device_type)
        if not plugin_key:
            logger.debug("设备类型 %s 无对应劣化分析插件", device.device_type)
            return None

        plugin_cls = get_degradation_plugin(plugin_key)
        if not plugin_cls:
            logger.debug("插件 %s 未注册", plugin_key)
            return None

        plugin = plugin_cls()
        point_history = await self._fetch_point_history(
            device_id, plugin.get_required_points() + plugin.get_optional_points(),
            plugin_key=plugin_key,
        )

        return await plugin.analyze(device_id, point_history, self.window_days)

    async def analyze_all_devices(self) -> list[DegradationResult]:
        """批量分析所有支持的设备类型"""
        supported_types = list(DEVICE_TYPE_MAP.keys())
        result = await self.db.execute(
            select(Device).where(Device.device_type.in_(supported_types))
        )
        devices = result.scalars().all()

        results: list[DegradationResult] = []
        for device in devices:
            try:
                dr = await self.analyze_device(device.id, device=device)
                if dr:
                    results.append(dr)
            except Exception as e:
                logger.error("设备 %d (%s) 劣化分析失败: %s", device.id, device.device_name, e)
                continue

        logger.info("劣化分析完成: %d/%d 设备", len(results), len(devices))
        return results

    async def _fetch_point_history(
        self, device_id: int, point_suffixes: list[str],
        plugin_key: str | None = None,
    ) -> dict[str, list]:
        """获取设备的点位历史数据

        优先从 PointHistoryArchive(hourly) 获取，不足时降级到 PointHistory(最近7天)
        返回: {point_code_suffix: [(day_offset, value), ...]}
        """
        # 查找设备关联的点位
        result = await self.db.execute(
            select(Point).where(Point.device_id == device_id, Point.is_enabled == True)
        )
        points = result.scalars().all()
        if not points:
            return {}

        # 按后缀匹配点位
        matched: dict[str, Point] = {}
        for suffix in point_suffixes:
            for p in points:
                if suffix in (p.point_code or ""):
                    matched[suffix] = p
                    break
            # 备选：通过 point_name 匹配（旧体系兼容）
            if suffix not in matched and suffix == "return_temp":
                for p in points:
                    if "回风温度" in (p.point_name or ""):
                        matched[suffix] = p
                        break

        if not matched:
            return {}

        now = datetime.now()
        cutoff = now - timedelta(days=self.window_days)
        point_history: dict[str, list] = {}

        for suffix, point in matched.items():
            # 优先查 PointHistoryArchive (hourly)
            archive_result = await self.db.execute(
                select(PointHistoryArchive)
                .where(
                    PointHistoryArchive.point_id == point.id,
                    PointHistoryArchive.archive_type == "hourly",
                    PointHistoryArchive.recorded_at >= cutoff,
                )
                .order_by(PointHistoryArchive.recorded_at)
            )
            archives = archive_result.scalars().all()

            if archives and len(archives) >= 24:  # 至少1天的hourly数据
                data = []
                for a in archives:
                    if a.value_avg is not None and a.recorded_at:
                        day_offset = (a.recorded_at - cutoff).total_seconds() / 86400
                        data.append((round(day_offset, 2), a.value_avg))
                point_history[suffix] = data
            else:
                # 降级到 PointHistory（限最近7天，小时采样）
                fallback_cutoff = now - timedelta(days=FALLBACK_HISTORY_DAYS)
                raw_result = await self.db.execute(
                    select(PointHistory)
                    .where(
                        PointHistory.point_id == point.id,
                        PointHistory.recorded_at >= fallback_cutoff,
                        PointHistory.quality < VALID_QUALITY_THRESHOLD,
                    )
                    .order_by(PointHistory.recorded_at)
                )
                raws = raw_result.scalars().all()

                if raws:
                    # 小时采样：每小时取第一条
                    sampled: dict[str, float] = {}
                    for r in raws:
                        if r.recorded_at:
                            hour_key = r.recorded_at.strftime("%Y-%m-%d %H")
                            if hour_key not in sampled:
                                sampled[hour_key] = r.value
                    data = []
                    for i, (_, v) in enumerate(sorted(sampled.items())):
                        day_offset = i / 24.0
                        data.append((round(day_offset, 2), v))
                    point_history[suffix] = data
                else:
                    point_history[suffix] = []

        # Battery 插件：注入 BatterySOHRecord 数据为虚拟 point_history 条目
        if plugin_key == "battery":
            soh_result = await self.db.execute(
                select(BatterySOHRecord)
                .where(
                    BatterySOHRecord.device_id == device_id,
                    BatterySOHRecord.calculated_at >= cutoff,
                )
                .order_by(BatterySOHRecord.calculated_at)
            )
            soh_records = soh_result.scalars().all()
            if soh_records:
                soh_data = []
                for r in soh_records:
                    if r.calculated_at:
                        day_offset = (r.calculated_at - cutoff).total_seconds() / 86400
                        soh_data.append((round(day_offset, 2), r.soh_percent))
                point_history["soh_percent"] = soh_data

        return point_history
