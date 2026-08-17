"""DeviceHealthScoreCalculator — Story 36.2

加权合并劣化趋势、告警频次、维保记录，生成设备健康度评分。
"""

import json
import logging
from datetime import datetime, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ...models.alarm import Alarm
from ...models.config import SystemConfig
from ...models.device import Device
from ...models.operation import WorkOrder, WorkOrderStatus
from ...models.point import Point
from ...models.report import DeviceHealthScore
from .base import DegradationResult
from .analyzer import DegradationAnalyzer
from .advisor import MaintenanceAdvisor
from .config import DEVICE_TYPE_MAP

logger = logging.getLogger(__name__)

# 设备类型 → 三因子权重（劣化 / 告警 / 维保）
WEIGHT_CONFIG: dict[str, dict[str, float]] = {
    "ups": {"degradation": 0.4, "alarm": 0.3, "maintenance": 0.3},
    "battery": {"degradation": 0.5, "alarm": 0.2, "maintenance": 0.3},
    "hvac": {"degradation": 0.4, "alarm": 0.3, "maintenance": 0.3},
    "pdu": {"degradation": 0.35, "alarm": 0.35, "maintenance": 0.3},
}

# data_sufficiency == "minimal" 时降级权重
MINIMAL_WEIGHTS: dict[str, float] = {"degradation": 0, "alarm": 0.5, "maintenance": 0.5}


def _score_to_level(score: float) -> str:
    """评分 → 健康等级映射"""
    if score >= 80:
        return "健康"
    if score >= 60:
        return "关注"
    if score >= 40:
        return "预警"
    return "危险"


def _calc_alarm_score(alarm_count: int) -> float:
    """告警频次 → 评分（近30天）"""
    if alarm_count == 0:
        return 100.0
    if alarm_count <= 2:
        return 85.0
    if alarm_count <= 5:
        return 70.0
    if alarm_count <= 10:
        return 50.0
    if alarm_count <= 20:
        return 30.0
    return 10.0


def _calc_maintenance_score(days_since_maintenance: int | None) -> float:
    """距最后维保天数 → 评分

    Args:
        days_since_maintenance: 距最后维保天数，None 表示无维保记录
    """
    if days_since_maintenance is None:
        return 50.0
    if days_since_maintenance <= 30:
        return 100.0
    if days_since_maintenance <= 90:
        return 85.0
    if days_since_maintenance <= 180:
        return 70.0
    if days_since_maintenance <= 365:
        return 50.0
    return 30.0


def _safe_json_dumps(obj: dict | None) -> str | None:
    """安全 JSON 序列化"""
    if obj is None:
        return None
    try:
        return json.dumps(obj, ensure_ascii=False)
    except (TypeError, ValueError):
        return None


class DeviceHealthScoreCalculator:
    """设备健康度评分计算器"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._weight_cache: dict[str, dict[str, float]] | None = None

    async def _load_weight_config(self, plugin_key: str) -> dict[str, float]:
        """从 SystemConfig 读取动态权重，fallback 到默认值"""
        if self._weight_cache is None:
            self._weight_cache = {}
            try:
                result = await self.db.execute(
                    select(SystemConfig).where(
                        SystemConfig.config_group == "predictive_maintenance",
                        SystemConfig.config_key.like("weights.%"),
                    )
                )
                for cfg in result.scalars().all():
                    key = cfg.config_key.replace("weights.", "")
                    try:
                        self._weight_cache[key] = json.loads(cfg.config_value)
                    except (json.JSONDecodeError, TypeError):
                        logger.warning("权重配置解析失败: %s = %s", cfg.config_key, cfg.config_value)
            except Exception:
                logger.warning("权重配置加载失败，使用默认值")
                self._weight_cache = {}

        if plugin_key in self._weight_cache:
            return self._weight_cache[plugin_key]
        return WEIGHT_CONFIG.get(plugin_key, WEIGHT_CONFIG["hvac"])

    def calculate(
        self,
        degradation_result: DegradationResult,
        alarm_count: int,
        days_since_maintenance: int | None,
        plugin_key: str,
        weights: dict[str, float],
    ) -> tuple[float, str, dict]:
        """计算加权健康度评分

        Returns:
            (score, health_level, score_factors)
        """
        degradation_score = degradation_result.score
        alarm_score = _calc_alarm_score(alarm_count)
        maintenance_score = _calc_maintenance_score(days_since_maintenance)

        # data_sufficiency == "minimal" 时降级
        if degradation_result.data_sufficiency == "minimal":
            w = MINIMAL_WEIGHTS
        else:
            w = weights

        score = w["degradation"] * degradation_score + w["alarm"] * alarm_score + w["maintenance"] * maintenance_score
        score = round(min(100.0, max(0.0, score)), 1)
        health_level = _score_to_level(score)

        score_factors = {
            "degradation": {"score": degradation_score, "weight": w["degradation"]},
            "alarm": {"score": alarm_score, "weight": w["alarm"], "count": alarm_count},
            "maintenance": {
                "score": maintenance_score,
                "weight": w["maintenance"],
                "days_since": days_since_maintenance,
            },
            "data_sufficiency": degradation_result.data_sufficiency,
            "plugin_key": plugin_key,
        }

        return score, health_level, score_factors

    async def calculate_all_health_scores(self, device_ids: list[int] | None = None) -> int:
        """全量设备批量计算健康度评分

        Returns:
            计算的设备数
        """
        # 1. 查询所有支持的设备
        supported_types = list(DEVICE_TYPE_MAP.keys())
        query = select(Device).where(Device.device_type.in_(supported_types))
        if device_ids is not None:
            query = query.where(Device.id.in_(device_ids))
        result = await self.db.execute(query)
        devices = result.scalars().all()
        if not devices:
            return 0

        device_ids = [d.id for d in devices]

        # 2. 批量预查询告警计数（近30天，通过 Point 关联）
        cutoff_30d = datetime.now() - timedelta(days=30)
        alarm_counts = await self._batch_alarm_counts(device_ids, cutoff_30d)

        # 3. 批量预查询最后维保时间
        maintenance_map = await self._batch_maintenance_dates(device_ids)

        # 3.5 批量预加载已有 DeviceHealthScore 记录（避免 upsert N+1）
        existing_result = await self.db.execute(
            select(DeviceHealthScore).where(DeviceHealthScore.device_id.in_(device_ids))
        )
        self._existing_scores: dict[int, DeviceHealthScore] = {r.device_id: r for r in existing_result.scalars().all()}

        # 4. 劣化分析 + 加权计算
        analyzer = DegradationAnalyzer(self.db)
        advisor = MaintenanceAdvisor(self.db)
        count = 0
        auto_close_ids = []  # 健康度≥60 的设备 ID，批量关闭 pending 建议

        for device in devices:
            try:
                # 劣化分析
                dr = await analyzer.analyze_device(device.id, device=device)
                if dr is None:
                    # 设备类型无插件或设备不存在 → 构造 minimal
                    dr = DegradationResult(
                        device_id=device.id,
                        score=100.0,
                        confidence=0.0,
                        available_points=0,
                        total_points=0,
                        data_sufficiency="minimal",
                    )

                plugin_key = DEVICE_TYPE_MAP.get(device.device_type, "hvac")
                weights = await self._load_weight_config(plugin_key)

                alarm_count = alarm_counts.get(device.id, 0)

                last_maint = maintenance_map.get(device.id)
                days_since = None
                if last_maint:
                    days_since = (datetime.now() - last_maint).days

                score, health_level, score_factors = self.calculate(dr, alarm_count, days_since, plugin_key, weights)

                # Upsert DeviceHealthScore
                await self._upsert_health_score(
                    device=device,
                    score=score,
                    health_level=health_level,
                    alarm_count=alarm_count,
                    days_since=days_since,
                    last_maint=last_maint,
                    score_factors=score_factors,
                    data_sufficiency=dr.data_sufficiency,
                    degradation_score=dr.score,
                )

                if score < 60:
                    logger.warning(
                        "设备健康度预警: device_id=%d, name=%s, score=%.1f, level=%s",
                        device.id,
                        device.device_name,
                        score,
                        health_level,
                    )
                    await advisor.evaluate(device, score, dr, plugin_key)
                elif score >= 60:
                    auto_close_ids.append(device.id)

                count += 1
            except Exception as e:
                logger.error("设备 %d (%s) 健康度计算失败: %s", device.id, device.device_name, e)
                continue

        # 5. 批量自动关闭健康度≥60 设备的 pending 建议
        if auto_close_ids:
            await advisor.auto_close_pending_batch(auto_close_ids)

        await self.db.flush()
        logger.info("健康度评分计算完成: %d/%d 设备", count, len(devices))
        return count

    async def _batch_alarm_counts(self, device_ids: list[int], cutoff: datetime) -> dict[int, int]:
        """批量查询设备近30天告警数（通过 Alarm.point_id → Point.device_id）

        注意：仅统计有 point_id 的告警，datasource 级告警（point_id=NULL）被排除。
        这是本 Story 的设计简化，不影响大多数设备类型的评分准确性。
        """
        stmt = (
            select(Point.device_id, func.count(Alarm.id))
            .join(Alarm, Alarm.point_id == Point.id)
            .where(
                Point.device_id.in_(device_ids),
                Alarm.created_at >= cutoff,
            )
            .group_by(Point.device_id)
        )
        result = await self.db.execute(stmt)
        return {row[0]: row[1] for row in result.fetchall()}

    async def _batch_maintenance_dates(self, device_ids: list[int]) -> dict[int, datetime | None]:
        """批量查询设备最后维保时间（WorkOrder status=已完成）"""
        stmt = (
            select(WorkOrder.device_id, func.max(WorkOrder.completed_at))
            .where(
                WorkOrder.device_id.in_(device_ids),
                WorkOrder.status == WorkOrderStatus.completed,
            )
            .group_by(WorkOrder.device_id)
        )
        result = await self.db.execute(stmt)
        return {row[0]: row[1] for row in result.fetchall()}

    async def _upsert_health_score(
        self,
        device: Device,
        score: float,
        health_level: str,
        alarm_count: int,
        days_since: int | None,
        last_maint: datetime | None,
        score_factors: dict,
        data_sufficiency: str,
        degradation_score: float,
    ):
        """Upsert DeviceHealthScore 记录"""
        # 优先使用批量预加载的缓存
        record = getattr(self, "_existing_scores", {}).get(device.id)
        if record is None:
            result = await self.db.execute(select(DeviceHealthScore).where(DeviceHealthScore.device_id == device.id))
            record = result.scalar_one_or_none()

        if record is None:
            record = DeviceHealthScore(device_id=device.id)
            self.db.add(record)

        record.device_name = device.device_name
        record.device_type = device.device_type
        record.score = score
        record.health_level = health_level
        record.alarm_count = alarm_count
        record.maintenance_count = 0  # 简化：仅记录告警数
        record.last_maintenance_at = last_maint
        record.score_factors = _safe_json_dumps(score_factors)
        record.data_sufficiency = data_sufficiency
        record.degradation_score = degradation_score
        record.calculated_at = datetime.now()
