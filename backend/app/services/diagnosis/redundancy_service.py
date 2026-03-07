"""
冗余路径检测服务
Story 25.4: N+X冗余拓扑与断路器保护逻辑

本模块实现配电设备冗余路径的智能检测，支持 N+1 和 2N 冗余配置，
用于诊断引擎判断设备故障时是否有备用路径可用。

主要功能:
- 支持 N+1 和 2N 两种冗余类型
- 基于冗余组或回路查询备用设备
- 判断备用路径是否充足
- Prometheus 监控指标记录性能和统计数据
"""

import time
import logging
import math
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
    """
    冗余状态检测结果

    Attributes:
        has_backup: 是否有备用路径
        redundancy_type: 冗余类型（N+1/2N/None）
        backup_devices: 备用设备 ID 列表
        backup_count: 备用设备数量
        error: 错误信息（仅在发生错误时）
    """
    has_backup: bool
    redundancy_type: Optional[str] = None
    backup_devices: List[int] = []
    backup_count: int = 0
    error: Optional[str] = None


async def check_redundancy_backup(device_id: int, session: AsyncSession) -> RedundancyStatus:
    """
    检查配电设备是否有活跃的冗余备用路径

    查询逻辑:
    1. 查询设备的 redundancy_type, redundancy_group_id, device_type, circuit_id
    2. 如果 redundancy_type 为 NULL，返回无冗余
    3. 如果有 redundancy_group_id，查询同组中 device_type 相同且 is_enabled=True 的其他设备
    4. 如果没有 redundancy_group_id，查询同 circuit_id 中 device_type 相同且 is_enabled=True 的其他设备
    5. 根据 redundancy_type 判断备用路径是否充足:
       - N+1: 至少 1 台备用设备可用
       - 2N: 至少与当前设备数量相等的备用设备可用

    Args:
        device_id: 配电设备 ID
        session: 数据库会话

    Returns:
        RedundancyStatus: 冗余状态检测结果

    Examples:
        >>> status = await check_redundancy_backup(1, session)
        >>> status.has_backup
        True
        >>> status.redundancy_type
        'N+1'
        >>> status.backup_count
        2
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
            # 计算同组/同回路设备总数（包括自身）
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
            # backup_count 已排除自身，所以需要 +1 才是实际可用设备数
            required_backup = math.ceil(total_devices / 2) - 1  # -1 因为 backup_count 不包括自身
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
