"""
冗余路径检测服务
Story 25.4: N+X冗余拓扑与断路器保护逻辑
"""

import time
import logging
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from prometheus_client import Counter, Histogram, REGISTRY

from app.models.energy import PowerDevice

logger = logging.getLogger(__name__)

# Prometheus 监控指标（条件注册，避免重复）
try:
    diagnosis_redundancy_check_duration_seconds = Histogram(
        'diagnosis_redundancy_check_duration_seconds',
        'Duration of redundancy check operations in seconds',
        buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]
    )
except ValueError:
    diagnosis_redundancy_check_duration_seconds = REGISTRY._names_to_collectors['diagnosis_redundancy_check_duration_seconds']

try:
    diagnosis_redundancy_check_total = Counter(
        'diagnosis_redundancy_check_total',
        'Total number of redundancy checks',
        ['has_backup']
    )
except ValueError:
    diagnosis_redundancy_check_total = REGISTRY._names_to_collectors['diagnosis_redundancy_check_total']


class RedundancyStatus(BaseModel):
    """冗余状态"""
    has_backup: bool
    redundancy_type: Optional[str] = None
    backup_devices: List[int] = []
    backup_count: int = 0
    error: Optional[str] = None


async def check_redundancy_backup(device_id: int, session: AsyncSession) -> RedundancyStatus:
    """
    检查设备是否有活跃的冗余备用路径

    Args:
        device_id: 设备ID
        session: 数据库会话

    Returns:
        RedundancyStatus: 冗余状态对象
    """
    start_time = time.time()

    try:
        # 查询该设备的冗余配置
        result = await session.execute(
            select(PowerDevice).where(PowerDevice.id == device_id)
        )
        device = result.scalar_one_or_none()

        if not device:
            status = RedundancyStatus(
                has_backup=False,
                error=f"Device {device_id} not found",
                backup_devices=[],
                backup_count=0
            )
            diagnosis_redundancy_check_total.labels(has_backup='false').inc()
            return status

        # 如果没有配置冗余类型，返回无冗余
        if not device.redundancy_type:
            status = RedundancyStatus(
                has_backup=False,
                redundancy_type=None,
                backup_devices=[],
                backup_count=0
            )
            diagnosis_redundancy_check_total.labels(has_backup='false').inc()
            return status

        # 查询备用设备
        backup_query = select(PowerDevice).where(
            PowerDevice.id != device_id,  # 排除自身
            PowerDevice.device_type == device.device_type,  # 同类设备
            PowerDevice.is_enabled == True  # 设备可用
        )

        # 优先按 redundancy_group_id 查询
        if device.redundancy_group_id:
            backup_query = backup_query.where(
                PowerDevice.redundancy_group_id == device.redundancy_group_id
            )
        # 否则按 circuit_id 查询
        elif device.circuit_id:
            backup_query = backup_query.where(
                PowerDevice.circuit_id == device.circuit_id
            )
        else:
            # 既没有冗余组也没有回路ID，无法判断冗余
            return RedundancyStatus(
                has_backup=False,
                redundancy_type=device.redundancy_type,
                backup_devices=[],
                backup_count=0,
                error="No redundancy_group_id or circuit_id configured"
            )

        result = await session.execute(backup_query)
        backup_devices_list = result.scalars().all()
        backup_count = len(backup_devices_list)
        backup_device_ids = [d.id for d in backup_devices_list]

        # 判断备用路径是否充足
        has_backup = False
        if device.redundancy_type == 'N+1':
            # N+1: 至少 1 台备用设备可用
            has_backup = backup_count >= 1
        elif device.redundancy_type == '2N':
            # 2N: 至少与当前设备数量相等的备用设备可用
            # 计算同组/同回路设备总数
            total_query = select(PowerDevice).where(
                PowerDevice.device_type == device.device_type,
                PowerDevice.is_enabled == True
            )
            if device.redundancy_group_id:
                total_query = total_query.where(
                    PowerDevice.redundancy_group_id == device.redundancy_group_id
                )
            elif device.circuit_id:
                total_query = total_query.where(
                    PowerDevice.circuit_id == device.circuit_id
                )

            result = await session.execute(total_query)
            total_devices = len(result.scalars().all())

            # 至少一半设备正常（向上取整）
            import math
            required_backup = math.ceil(total_devices / 2)
            has_backup = backup_count >= required_backup

        status = RedundancyStatus(
            has_backup=has_backup,
            redundancy_type=device.redundancy_type,
            backup_devices=backup_device_ids,
            backup_count=backup_count
        )

        # 记录监控指标
        diagnosis_redundancy_check_total.labels(has_backup=str(has_backup).lower()).inc()

        return status

    except Exception as e:
        # 数据库查询失败时记录错误日志，返回默认值
        logger.error(f"Redundancy check failed for device {device_id}: {e}")
        status = RedundancyStatus(
            has_backup=False,
            error=f"Database query failed: {str(e)}",
            backup_devices=[],
            backup_count=0
        )
        diagnosis_redundancy_check_total.labels(has_backup='false').inc()
        return status

    finally:
        # 记录耗时
        duration = time.time() - start_time
        diagnosis_redundancy_check_duration_seconds.observe(duration)
        logger.error(f"冗余检测失败 device_id={device_id}: {str(e)}")

        return RedundancyStatus(
            has_backup=False,
            error=f"Database query failed: {str(e)}",
            backup_devices=[],
            backup_count=0
        )
