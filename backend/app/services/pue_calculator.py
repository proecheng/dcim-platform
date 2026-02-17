"""
PUE 计算服务
基于 PowerDevice 关联的真实点位数据计算 PUE
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..models.energy import PowerDevice, PUEHistory
from ..models.point import PointRealtime

import logging

logger = logging.getLogger(__name__)

# 制冷设备类型集合
COOLING_DEVICE_TYPES = {"AC", "CHILLER", "CT", "PUMP"}

# 数据过期阈值（秒）
DATA_EXPIRY_SECONDS = 300


@dataclass
class PUEResult:
    """PUE 计算结果"""
    current_pue: Optional[float]
    total_power: float
    it_power: float
    cooling_power: float
    ups_loss: float
    data_source: str
    unreliable_count: int


async def calculate_realtime_pue(db: AsyncSession) -> PUEResult:
    """
    基于真实点位数据计算实时 PUE

    批量查询所有 PowerDevice 的 power_point_id，一次性从 PointRealtime 加载（避免 N+1）
    """
    # 查询所有启用的 PowerDevice
    result = await db.execute(
        select(PowerDevice).where(PowerDevice.is_enabled == True)
    )
    devices = result.scalars().all()

    # 批量查询所有关联的 PointRealtime
    point_ids = [d.power_point_id for d in devices if d.power_point_id]
    realtime_map: Dict[int, PointRealtime] = {}
    if point_ids:
        rt_result = await db.execute(
            select(PointRealtime).where(PointRealtime.point_id.in_(point_ids))
        )
        realtime_map = {r.point_id: r for r in rt_result.scalars().all()}

    now = datetime.now()
    total_power = 0.0
    it_power = 0.0
    cooling_power = 0.0
    ups_total = 0.0
    unreliable_count = 0

    for device in devices:
        if not device.power_point_id:
            continue

        rt = realtime_map.get(device.power_point_id)
        if not rt or rt.value is None:
            continue

        # 数据质量检查: quality==2 (中断) 跳过
        if rt.quality == 2:
            continue

        # quality==1 (不可靠) 或数据过期标记不可靠
        is_unreliable = rt.quality == 1
        if rt.updated_at:
            elapsed = (now - rt.updated_at).total_seconds()
            if elapsed > DATA_EXPIRY_SECONDS:
                is_unreliable = True

        if is_unreliable:
            unreliable_count += 1

        power = rt.value
        total_power += power

        if device.is_it_load or device.device_type == "IT":
            it_power += power
        elif device.device_type in COOLING_DEVICE_TYPES:
            cooling_power += power
        elif device.device_type == "UPS":
            ups_total += power

    # UPS 损耗 = UPS 总功率 - IT 功率（负值归零）
    ups_loss = max(0, ups_total - it_power)

    if it_power <= 0:
        return PUEResult(
            current_pue=None,
            total_power=round(total_power, 2),
            it_power=0,
            cooling_power=round(cooling_power, 2),
            ups_loss=0,
            data_source="realtime",
            unreliable_count=unreliable_count,
        )

    current_pue = round(total_power / it_power, 3)

    return PUEResult(
        current_pue=current_pue,
        total_power=round(total_power, 2),
        it_power=round(it_power, 2),
        cooling_power=round(cooling_power, 2),
        ups_loss=round(ups_loss, 2),
        data_source="realtime",
        unreliable_count=unreliable_count,
    )


async def write_pue_history(db: AsyncSession) -> None:
    """
    将当前 PUE 写入 PUEHistory 表
    仅在 PUE 有效时（非 None）写入
    """
    pue_result = await calculate_realtime_pue(db)

    if pue_result.current_pue is None:
        logger.info("PUE 无效（IT 负载为 0），跳过历史写入")
        return

    record = PUEHistory(
        record_time=datetime.now(),
        pue=pue_result.current_pue,
        total_power=pue_result.total_power,
        it_power=pue_result.it_power,
        cooling_power=pue_result.cooling_power,
        ups_loss=pue_result.ups_loss,
    )
    try:
        db.add(record)
        await db.commit()
        logger.info("PUE 历史记录已写入: PUE=%.3f", pue_result.current_pue)
    except Exception:
        await db.rollback()
        raise
