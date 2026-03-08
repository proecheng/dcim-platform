"""
多传感器融合服务
Story 25.7: 趋势分析与多传感器融合
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
import numpy as np

from app.models.diagnosis import SensorFusionRecord
from app.models.point import Point

logger = logging.getLogger(__name__)


class SensorFusionResult:
    """传感器融合结果"""

    def __init__(
        self,
        zone_id: int,
        sensor_count: int,
        std_dev: Optional[float] = None,
        layer_variances: Optional[Dict[str, float]] = None,
        evidence_type: str = "normal",
        is_evidence: bool = False,
        probability: Optional[float] = None,
        message: Optional[str] = None
    ):
        self.zone_id = zone_id
        self.sensor_count = sensor_count
        self.std_dev = std_dev
        self.layer_variances = layer_variances or {}
        self.evidence_type = evidence_type
        self.is_evidence = is_evidence
        self.probability = probability
        self.message = message


class SensorFusionService:
    """多传感器融合服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def calculate_temperature_variance(
        self,
        zone_id: int
    ) -> SensorFusionResult:
        """
        计算同区域温度传感器加权标准差（改进版：精度加权、高度分组）

        Args:
            zone_id: 区域ID

        Returns:
            SensorFusionResult 包含加权标准差、证据类型、概率
        """
        # 1. 查询同区域所有温度传感器最新值（含精度和高度信息）
        query = text("""
            SELECT p.id, p.name, pr.value, p.height_level, sm.accuracy_class
            FROM points p
            JOIN point_realtime pr ON p.id = pr.point_id
            LEFT JOIN sensor_metadata sm ON p.id = sm.point_id
            WHERE p.zone_id = :zone_id
            AND (p.unit LIKE '%℃%' OR p.unit LIKE '%°C%')
            AND p.enabled = true
            AND (pr.quality_flag IS NULL OR pr.quality_flag != 'poor')
        """)
        result = await self.db.execute(query, {"zone_id": zone_id})
        sensors = result.fetchall()

        if len(sensors) < 2:
            return SensorFusionResult(
                zone_id=zone_id,
                sensor_count=len(sensors),
                evidence_type="insufficient_sensors",
                is_evidence=False
            )

        # 2. 按高度分组（地板层 0-0.5m，机柜层 0.5-2.5m，天花板层 >2.5m）
        groups = {"floor": [], "rack": [], "ceiling": []}
        for s in sensors:
            height = s.height_level or 1.5  # 默认机柜层
            if height < 0.5:
                groups["floor"].append(s)
            elif height <= 2.5:
                groups["rack"].append(s)
            else:
                groups["ceiling"].append(s)

        # 3. 对每层计算加权标准差（使用 Story 25.5 精度加权）
        layer_variances = {}
        for layer, layer_sensors in groups.items():
            if len(layer_sensors) < 2:
                continue

            # 精度加权（0.2级→1.0, 0.5级→0.9, 1.0级→0.8, 无元数据→0.85）
            # 加权公式：weight = 1 / accuracy_class (归一化后)
            weights = []
            values = []
            for s in layer_sensors:
                accuracy = s.accuracy_class or 1.0
                weight = {0.2: 1.0, 0.5: 0.9, 1.0: 0.8}.get(accuracy, 0.85)
                weights.append(weight)
                values.append(s.value)

            # 加权标准差计算公式：
            # weighted_std = sqrt(sum(w_i * (x_i - weighted_mean)^2) / sum(w_i))
            weighted_mean = np.average(values, weights=weights)
            weighted_var = np.average((np.array(values) - weighted_mean)**2, weights=weights)
            weighted_std = np.sqrt(weighted_var)
            layer_variances[layer] = float(weighted_std)

        # 4. 使用机柜层标准差作为主要判断依据（最关键）
        std_dev = layer_variances.get("rack", 0.0)

        # 5. 从配置读取动态阈值（可按区域面积和负载调整）
        threshold = await self._get_dynamic_threshold(zone_id)

        # 6. 判断证据类型
        if std_dev > threshold:
            # 气流不均匀证据
            return SensorFusionResult(
                zone_id=zone_id,
                sensor_count=len(sensors),
                std_dev=std_dev,
                layer_variances=layer_variances,
                evidence_type="airflow_uneven",
                is_evidence=True,
                probability=0.85,
                message=f"区域 {zone_id} 机柜层温度加权标准差 {std_dev:.2f}℃ > {threshold:.2f}℃，气流不均匀"
            )
        elif std_dev >= threshold * 0.4:  # 动态中等阈值
            # 中等程度，不作为证据但记录
            return SensorFusionResult(
                zone_id=zone_id,
                sensor_count=len(sensors),
                std_dev=std_dev,
                layer_variances=layer_variances,
                evidence_type="moderate_variance",
                is_evidence=False,
                message=f"区域 {zone_id} 机柜层温度加权标准差 {std_dev:.2f}℃ 处于中等水平"
            )
        else:
            # 正常
            return SensorFusionResult(
                zone_id=zone_id,
                sensor_count=len(sensors),
                std_dev=std_dev,
                layer_variances=layer_variances,
                evidence_type="normal",
                is_evidence=False
            )

    async def check_differential_pressure(
        self,
        zone_id: int
    ) -> Optional[SensorFusionResult]:
        """
        检查地板下压差传感器（改进版：多传感器平均、故障检测）

        Args:
            zone_id: 区域ID

        Returns:
            SensorFusionResult 或 None（无压差传感器或数据无效）
        """
        # 1. 查询所有压差传感器（过滤 threshold_low 不为 NULL）
        query = text("""
            SELECT p.id, p.name, pr.value, pr.quality_flag, pr.updated_at, p.threshold_low
            FROM points p
            JOIN point_realtime pr ON p.id = pr.point_id
            WHERE p.zone_id = :zone_id
            AND p.point_type = 'AI'
            AND p.unit LIKE '%Pa%'
            AND p.enabled = true
            AND p.threshold_low IS NOT NULL
        """)
        result = await self.db.execute(query, {"zone_id": zone_id})
        sensors = result.fetchall()

        if not sensors:
            return None

        # 2. 过滤有效传感器（数据质量非 poor，通信正常）
        now = datetime.now()
        valid_sensors = []
        for s in sensors:
            # 检查通信状态（5分钟内有更新）
            if (now - s.updated_at).total_seconds() > 300:
                logger.warning(f"Pressure sensor {s.id} communication timeout")
                continue

            # 检查数据质量
            if s.quality_flag == 'poor':
                logger.warning(f"Pressure sensor {s.id} has poor data quality")
                continue

            valid_sensors.append(s)

        # 3. 至少需要 2 个有效传感器
        if len(valid_sensors) < 2:
            logger.warning(
                f"Zone {zone_id} has insufficient valid pressure sensors "
                f"({len(valid_sensors)}/{len(sensors)})"
            )
            return None

        # 4. 计算平均压差
        avg_pressure = sum(s.value for s in valid_sensors) / len(valid_sensors)
        avg_threshold = sum(s.threshold_low for s in valid_sensors) / len(valid_sensors)

        # 5. 判断压差是否低于设定值
        if avg_pressure < avg_threshold:
            return SensorFusionResult(
                zone_id=zone_id,
                sensor_count=len(valid_sensors),
                evidence_type="air_supply_abnormal",
                is_evidence=True,
                probability=0.80,
                message=f"区域 {zone_id} 地板下平均压差 {avg_pressure:.1f}Pa < 设定值 {avg_threshold:.1f}Pa，送风系统异常"
            )

        return None

    async def _get_dynamic_threshold(self, zone_id: int) -> float:
        """从配置读取动态阈值（支持按区域调整）"""
        # 从 system_configs 表读取全局阈值
        query = text("""
            SELECT config_value FROM system_configs
            WHERE config_group = 'diagnosis' AND config_key = 'airflow_variance_threshold'
        """)
        result = await self.db.execute(query)
        row = result.fetchone()

        base_threshold = float(row.config_value) if row else 5.0

        # TODO: 未来可根据 zone_id 查询区域特定配置进行调整
        # 例如：大面积区域阈值 * 1.2，高负载区域阈值 * 0.8
        # 当前版本使用全局阈值
        return base_threshold

    async def save_fusion_record(self, fusion_result: SensorFusionResult):
        """保存融合记录到数据库"""
        record = SensorFusionRecord(
            zone_id=fusion_result.zone_id,
            sensor_count=fusion_result.sensor_count,
            std_dev=fusion_result.std_dev,
            evidence_type=fusion_result.evidence_type,
            is_evidence=fusion_result.is_evidence,
            probability=fusion_result.probability,
            message=fusion_result.message,
            created_at=datetime.now()
        )
        self.db.add(record)
        await self.db.commit()
        logger.info(f"Saved sensor fusion record for zone {fusion_result.zone_id}")


# 全局服务实例（依赖注入时使用）
sensor_fusion_service: Optional[SensorFusionService] = None


def get_sensor_fusion_service(db: AsyncSession) -> SensorFusionService:
    """获取多传感器融合服务实例"""
    return SensorFusionService(db)
