"""
告警引擎 — 内存阈值缓存 + 实时越限检测
Story 5.2: 实时告警触发与通知
"""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Tuple

from sqlalchemy import select

from ..core.database import async_session
from ..models.alarm import AlarmThreshold
from ..models.point import Point, PointRealtime

logger = logging.getLogger(__name__)


@dataclass
class ThresholdCache:
    """单条阈值缓存"""

    id: int
    point_id: int
    threshold_type: str  # high_high/high/low/low_low/equal/change
    threshold_value: float
    alarm_level: str  # critical/major/minor/info
    alarm_message: str
    delay_seconds: int
    dead_band: float
    priority: int


@dataclass
class EvaluateResult:
    """单次越限检测结果"""

    threshold_id: int
    threshold_type: str
    threshold_value: float
    alarm_level: str
    alarm_message: str
    is_communication_suspect: bool = False  # 疑似通信异常标记
    threshold_metadata: dict = None  # 动态阈值元数据（Story 25.6）

    def __post_init__(self):
        """初始化后处理"""
        if self.threshold_metadata is None:
            self.threshold_metadata = {}


class AlarmEngine:
    """告警引擎 — 核心类"""

    STORM_WINDOW = 60  # 告警风暴抑制窗口（秒）
    MASS_ALARM_RATIO = 0.5  # 大面积告警阈值比例

    def __init__(self) -> None:
        # 阈值缓存: {point_id: [ThresholdCache, ...]}
        self._thresholds: Dict[int, List[ThresholdCache]] = defaultdict(list)
        # 当前已知的阈值版本号
        self._known_version: int = -1
        # 风暴防护: {(point_id, threshold_id): 上次告警时间戳}
        self._last_alarm_time: Dict[Tuple[int, int], float] = {}
        # 延迟触发: {(point_id, threshold_id): 首次越限时间戳}
        self._delay_first_exceed: Dict[Tuple[int, int], float] = {}
        # 死区状态: {(point_id, threshold_id): 是否处于已触发状态}
        self._dead_band_triggered: Dict[Tuple[int, int], bool] = {}
        # 上一次值缓存（用于 change 类型检测）
        self._prev_values: Dict[int, float] = {}
        # 点位 -> device_type 映射
        self._point_device_type: Dict[int, str] = {}
        # device_type -> 点位 ID 集合
        self._device_type_points: Dict[str, set] = defaultdict(set)
        # 本轮越限点位（用于大面积告警检测）
        self._current_cycle_triggered: Dict[str, set] = defaultdict(set)
        # 点位数据质量缓存: {point_id: quality}  0=好 1=不确定 2=坏
        self._point_quality: Dict[int, int] = {}
        self._loaded = False

    async def load_thresholds(self) -> int:
        """从数据库批量加载所有启用的阈值配置到内存"""
        async with async_session() as session:
            result = await session.execute(
                select(AlarmThreshold).where(AlarmThreshold.is_enabled == True)  # noqa: E712
            )
            thresholds = result.scalars().all()

            points_result = await session.execute(
                select(Point.id, Point.device_type).where(Point.is_enabled == True)  # noqa: E712
            )
            points = points_result.all()

            # 重建缓存
            new_cache: Dict[int, List[ThresholdCache]] = defaultdict(list)
            for t in thresholds:
                cache_item = ThresholdCache(
                    id=t.id,
                    point_id=t.point_id,
                    threshold_type=t.threshold_type,
                    threshold_value=t.threshold_value or 0,
                    alarm_level=t.alarm_level or "minor",
                    alarm_message=t.alarm_message or "",
                    delay_seconds=t.delay_seconds or 0,
                    dead_band=t.dead_band or 0,
                    priority=t.priority or 0,
                )
                new_cache[t.point_id].append(cache_item)

            # 按 priority 降序排列
            for point_id in new_cache:
                new_cache[point_id].sort(key=lambda x: x.priority, reverse=True)

            self._thresholds = new_cache

            # 重建点位 -> device_type 映射
            self._point_device_type.clear()
            self._device_type_points.clear()
            for point_id, device_type in points:
                if device_type:
                    self._point_device_type[point_id] = device_type
                    self._device_type_points[device_type].add(point_id)

            # 加载点位数据质量缓存
            quality_result = await session.execute(select(PointRealtime.point_id, PointRealtime.quality))
            self._point_quality = {row[0]: (row[1] or 0) for row in quality_result.all()}

            self._loaded = True

            # 清理已失效的状态缓存（防止内存无限增长）
            valid_keys = set()
            for pid, tc_list in new_cache.items():
                for tc in tc_list:
                    valid_keys.add((pid, tc.id))
            valid_point_ids = set(new_cache.keys()) | set(self._point_device_type.keys())

            self._last_alarm_time = {k: v for k, v in self._last_alarm_time.items() if k in valid_keys}
            self._delay_first_exceed = {k: v for k, v in self._delay_first_exceed.items() if k in valid_keys}
            self._dead_band_triggered = {k: v for k, v in self._dead_band_triggered.items() if k in valid_keys}
            self._prev_values = {k: v for k, v in self._prev_values.items() if k in valid_point_ids}

            count = sum(len(v) for v in new_cache.values())
            logger.info("告警引擎: 已加载 %d 条阈值配置（覆盖 %d 个点位）", count, len(new_cache))
            return count

    async def check_version(self) -> bool:
        """检查阈值版本号，版本变化时重新加载"""
        try:
            from ..api.v1.threshold import _threshold_version

            # 先捕获版本快照，避免加载期间版本再次变化导致遗漏
            snapshot_version = _threshold_version
            if snapshot_version != self._known_version:
                old_ver = self._known_version
                await self.load_thresholds()
                self._known_version = snapshot_version
                logger.info("告警引擎: 阈值版本 %d -> %d，已重新加载", old_ver, snapshot_version)
                return True
        except Exception as e:
            logger.warning("告警引擎: 检查版本失败: %s", e)
        return False

    def get_point_quality(self, point_id: int) -> int:
        """获取点位数据质量"""
        return self._point_quality.get(point_id, 0)

    def update_point_quality(self, point_id: int, quality: int) -> None:
        """更新单个点位数据质量缓存"""
        self._point_quality[point_id] = quality

    def update_points_quality(self, point_ids: List[int], quality: int) -> None:
        """批量更新点位数据质量缓存"""
        for pid in point_ids:
            self._point_quality[pid] = quality

    def evaluate(self, point_id: int, value: float, point_type: str = "AI") -> List[EvaluateResult]:
        """检测点位值是否越限，返回触发的告警列表"""
        if not self._loaded:
            return []

        # 数据质量检查：quality==2 (坏) 跳过告警检测
        quality = self._point_quality.get(point_id, 0)
        if quality == 2:
            self._prev_values[point_id] = value  # still track value for change detection
            return []

        cached = self._thresholds.get(point_id)
        if not cached:
            self._prev_values[point_id] = value
            return []

        results: List[EvaluateResult] = []
        now = time.time()

        for tc in cached:
            # 风暴防护检查（按 point_id + threshold_id 粒度）
            storm_key = (point_id, tc.id)
            if self._check_storm(storm_key):
                continue

            # 使用动态阈值检测
            triggered, threshold_metadata = self._check_threshold_with_dynamic(point_id, value, tc, now)
            if triggered:
                results.append(
                    EvaluateResult(
                        threshold_id=tc.id,
                        threshold_type=tc.threshold_type,
                        threshold_value=tc.threshold_value,
                        alarm_level=tc.alarm_level,
                        alarm_message=tc.alarm_message or f"点位 {point_id} {tc.threshold_type} 告警",
                        threshold_metadata=threshold_metadata,  # 添加动态阈值元数据
                    )
                )
                # 更新风暴防护时间戳
                self._last_alarm_time[storm_key] = now

        # 记录本轮越限点位（用于大面积告警检测）
        if results:
            device_type = self._point_device_type.get(point_id)
            if device_type:
                self._current_cycle_triggered[device_type].add(point_id)

        # 数据质量检查：quality==1 (不确定) 添加前缀标记
        if quality == 1:
            for r in results:
                r.alarm_message = f"[数据质量不确定] {r.alarm_message}"

        self._prev_values[point_id] = value
        return results

    def _check_threshold(self, point_id: int, value: float, tc: ThresholdCache, now: float) -> bool:
        """检测单条阈值是否越限（含死区和延迟逻辑）"""
        key = (point_id, tc.id)
        exceeded = False

        # 1. 判断是否越限
        if tc.threshold_type in ("high_high", "high"):
            exceeded = value > tc.threshold_value
        elif tc.threshold_type in ("low", "low_low"):
            exceeded = value < tc.threshold_value
        elif tc.threshold_type == "equal":
            exceeded = abs(value - tc.threshold_value) < 0.001
        elif tc.threshold_type == "change":
            prev = self._prev_values.get(point_id)
            if prev is not None:
                exceeded = abs(value - prev) > tc.threshold_value
        else:
            return False

        # 2. 死区逻辑
        if tc.dead_band > 0:
            was_triggered = self._dead_band_triggered.get(key, False)
            if was_triggered:
                if tc.threshold_type in ("high_high", "high"):
                    recovered = value < (tc.threshold_value - tc.dead_band)
                elif tc.threshold_type in ("low", "low_low"):
                    recovered = value > (tc.threshold_value + tc.dead_band)
                else:
                    recovered = not exceeded
                if recovered:
                    self._dead_band_triggered[key] = False
                return False  # 已触发状态下不重复触发
            elif exceeded:
                self._dead_band_triggered[key] = True
            else:
                return False

        if not exceeded:
            self._delay_first_exceed.pop(key, None)
            return False

        # 3. 延迟触发逻辑
        if tc.delay_seconds > 0:
            first_time = self._delay_first_exceed.get(key)
            if first_time is None:
                self._delay_first_exceed[key] = now
                return False
            elif (now - first_time) < tc.delay_seconds:
                return False
            else:
                self._delay_first_exceed.pop(key, None)
                return True
        return True

    def _check_threshold_with_dynamic(
        self, point_id: int, value: float, tc: ThresholdCache, now: float
    ) -> tuple[bool, dict]:
        """
        检测单条阈值是否越限（含动态阈值调整）

        Returns:
            tuple[bool, dict]: (是否触发, 动态阈值元数据)
        """
        key = (point_id, tc.id)

        # ===== 动态阈值调整 =====
        threshold_value = tc.threshold_value
        threshold_metadata = {}

        try:
            from ..services.diagnosis.dynamic_threshold_service import DynamicThresholdService
            import asyncio

            # 异步调用动态阈值服务
            adjusted_threshold, metadata = asyncio.run(
                DynamicThresholdService.calculate_dynamic_threshold(
                    point_id, tc.threshold_value, tc.threshold_type
                )
            )
            threshold_value = adjusted_threshold
            threshold_metadata = metadata
        except Exception as e:
            logger.warning(f"动态阈值调整失败: {e}，使用静态阈值")
        # ===== 动态阈值调整结束 =====

        exceeded = False

        # 1. 判断是否越限（使用调整后的阈值）
        if tc.threshold_type in ("high_high", "high"):
            exceeded = value > threshold_value
        elif tc.threshold_type in ("low", "low_low"):
            exceeded = value < threshold_value
        elif tc.threshold_type == "equal":
            exceeded = abs(value - threshold_value) < 0.001
        elif tc.threshold_type == "change":
            prev = self._prev_values.get(point_id)
            if prev is not None:
                exceeded = abs(value - prev) > threshold_value
        else:
            return False, threshold_metadata

        # 2. 死区逻辑（使用调整后的阈值）
        if tc.dead_band > 0:
            was_triggered = self._dead_band_triggered.get(key, False)
            if was_triggered:
                if tc.threshold_type in ("high_high", "high"):
                    recovered = value < (threshold_value - tc.dead_band)
                elif tc.threshold_type in ("low", "low_low"):
                    recovered = value > (threshold_value + tc.dead_band)
                else:
                    recovered = not exceeded
                if recovered:
                    self._dead_band_triggered[key] = False
                return False, threshold_metadata  # 已触发状态下不重复触发
            elif exceeded:
                self._dead_band_triggered[key] = True
            else:
                return False, threshold_metadata

        if not exceeded:
            self._delay_first_exceed.pop(key, None)
            return False, threshold_metadata

        # 3. 延迟触发逻辑
        if tc.delay_seconds > 0:
            first_time = self._delay_first_exceed.get(key)
            if first_time is None:
                self._delay_first_exceed[key] = now
                return False, threshold_metadata
            elif (now - first_time) < tc.delay_seconds:
                return False, threshold_metadata
            else:
                self._delay_first_exceed.pop(key, None)
                return True, threshold_metadata
        return True, threshold_metadata

    def _check_storm(self, key: Tuple[int, int]) -> bool:
        """告警风暴防护：同一点位+阈值 60 秒内不重复产生告警"""
        last_time = self._last_alarm_time.get(key)
        if last_time is None:
            return False
        return (time.time() - last_time) < self.STORM_WINDOW

    def check_mass_alarm(self, device_type: str) -> bool:
        """大面积告警检测：同一 device_type 下 >50% 点位同时越限"""
        total_points = self._device_type_points.get(device_type, set())
        triggered_points = self._current_cycle_triggered.get(device_type, set())
        if not total_points:
            return False
        ratio = len(triggered_points) / len(total_points)
        if ratio > self.MASS_ALARM_RATIO:
            logger.warning(
                "大面积告警: device_type=%s, 越限 %d/%d (%.1f%%), 疑似通信异常",
                device_type,
                len(triggered_points),
                len(total_points),
                ratio * 100,
            )
            return True
        return False

    def reset_cycle_stats(self) -> None:
        """重置本轮统计（每个采集周期结束后调用）"""
        self._current_cycle_triggered.clear()

    def is_value_safe(self, point_id: int, value: float) -> bool:
        """检查点位值是否在所有阈值的安全范围内（用于自动恢复判断）"""
        cached = self._thresholds.get(point_id)
        if not cached:
            return True
        for tc in cached:
            if tc.threshold_type in ("high_high", "high") and value > tc.threshold_value:
                return False
            elif tc.threshold_type in ("low", "low_low") and value < tc.threshold_value:
                return False
            elif tc.threshold_type == "equal" and abs(value - tc.threshold_value) < 0.001:
                return False
        return True


# 全局单例
alarm_engine = AlarmEngine()
