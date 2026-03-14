"""
设备生命周期统一管理服务
DeviceLifecycleService - 级联删除、影响分析、自动扩展
"""

import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func

from ..models.device import Device
from ..models.point import Point, PointRealtime
from ..models.history import PointHistory
from ..models.alarm import AlarmThreshold
from ..models.power import UPSDevice, BatteryGroup
from ..models.cooling import CoolingUnit, ColdAisle
from ..models.energy import DistributionPanel, PowerDevice
from ..models.report import DeviceHealthScore
from ..models.topology_config import PowerPhaseMapping

logger = logging.getLogger(__name__)


class DeviceLifecycleService:
    """统一设备生命周期管理"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def analyze_delete_impact(self, device_id: int) -> dict:
        """查询所有 FK 依赖表，返回影响摘要"""

        # 获取设备信息
        result = await self.db.execute(select(Device).where(Device.id == device_id))
        device = result.scalar_one_or_none()
        if not device:
            return None

        # 获取该设备下所有点位 ID
        point_ids_result = await self.db.execute(
            select(Point.id).where(Point.device_id == device_id)
        )
        point_ids = [row[0] for row in point_ids_result.all()]

        impacts = []

        # 1. 点位
        point_count = len(point_ids)
        if point_count > 0:
            impacts.append(
                {
                    "table_name": "points",
                    "display_name": "监控点位",
                    "count": point_count,
                    "action": "delete",
                }
            )

        if point_ids:
            # 2. 点位实时数据
            rt_count = (
                await self.db.execute(
                    select(func.count(PointRealtime.point_id)).where(PointRealtime.point_id.in_(point_ids))
                )
            ).scalar() or 0
            if rt_count > 0:
                impacts.append(
                    {
                        "table_name": "point_realtime",
                        "display_name": "实时数据",
                        "count": rt_count,
                        "action": "delete",
                    }
                )

            # 3. 点位历史数据
            hist_count = (
                await self.db.execute(select(func.count(PointHistory.id)).where(PointHistory.point_id.in_(point_ids)))
            ).scalar() or 0
            if hist_count > 0:
                impacts.append(
                    {
                        "table_name": "point_history",
                        "display_name": "历史数据",
                        "count": hist_count,
                        "action": "delete",
                    }
                )

            # 4. 告警阈值
            threshold_count = (
                await self.db.execute(
                    select(func.count(AlarmThreshold.id)).where(AlarmThreshold.point_id.in_(point_ids))
                )
            ).scalar() or 0
            if threshold_count > 0:
                impacts.append(
                    {
                        "table_name": "alarm_thresholds",
                        "display_name": "告警阈值",
                        "count": threshold_count,
                        "action": "delete",
                    }
                )

        # 5. UPS 扩展
        ups_result = await self.db.execute(select(UPSDevice).where(UPSDevice.device_id == device_id))
        ups_devices = ups_result.scalars().all()
        if ups_devices:
            impacts.append(
                {
                    "table_name": "ups_devices",
                    "display_name": "UPS扩展记录",
                    "count": len(ups_devices),
                    "action": "delete",
                }
            )
            # 6. 电池组
            ups_ids = [u.id for u in ups_devices]
            bat_count = (
                await self.db.execute(
                    select(func.count(BatteryGroup.id)).where(BatteryGroup.ups_device_id.in_(ups_ids))
                )
            ).scalar() or 0
            if bat_count > 0:
                impacts.append(
                    {
                        "table_name": "battery_groups",
                        "display_name": "电池组",
                        "count": bat_count,
                        "action": "delete",
                    }
                )

        # 7. 制冷扩展
        cu_count = (
            await self.db.execute(select(func.count(CoolingUnit.id)).where(CoolingUnit.device_id == device_id))
        ).scalar() or 0
        if cu_count > 0:
            impacts.append(
                {
                    "table_name": "cooling_units",
                    "display_name": "制冷机组",
                    "count": cu_count,
                    "action": "delete",
                }
            )

        # 8. 冷通道
        ca_count = (
            await self.db.execute(select(func.count(ColdAisle.id)).where(ColdAisle.device_id == device_id))
        ).scalar() or 0
        if ca_count > 0:
            impacts.append(
                {
                    "table_name": "cold_aisles",
                    "display_name": "冷通道",
                    "count": ca_count,
                    "action": "delete",
                }
            )

        # 9. 设备健康评分
        hs_count = (
            await self.db.execute(
                select(func.count(DeviceHealthScore.id)).where(DeviceHealthScore.device_id == device_id)
            )
        ).scalar() or 0
        if hs_count > 0:
            impacts.append(
                {
                    "table_name": "device_health_scores",
                    "display_name": "健康评分",
                    "count": hs_count,
                    "action": "delete",
                }
            )

        # 10. 三相接线映射
        pm_count = (
            await self.db.execute(
                select(func.count(PowerPhaseMapping.id)).where(PowerPhaseMapping.pdu_device_id == device_id)
            )
        ).scalar() or 0
        if pm_count > 0:
            impacts.append(
                {
                    "table_name": "power_phase_mappings",
                    "display_name": "三相接线映射",
                    "count": pm_count,
                    "action": "delete",
                }
            )

        # 11. 配电面板（解除关联，不删除）
        dp_count = (
            await self.db.execute(
                select(func.count(DistributionPanel.id)).where(DistributionPanel.device_id == device_id)
            )
        ).scalar() or 0
        if dp_count > 0:
            impacts.append(
                {
                    "table_name": "distribution_panels",
                    "display_name": "配电面板",
                    "count": dp_count,
                    "action": "unlink",
                }
            )

        # 12. 能源拓扑设备（解除关联，不删除）
        pd_count = (
            await self.db.execute(select(func.count(PowerDevice.id)).where(PowerDevice.monitor_device_id == device_id))
        ).scalar() or 0
        if pd_count > 0:
            impacts.append(
                {
                    "table_name": "power_devices",
                    "display_name": "能源拓扑设备",
                    "count": pd_count,
                    "action": "unlink",
                }
            )
        # 13. 工单软关联（WorkOrder.device_id）
        from ..models.operation import WorkOrder

        wo_count = (
            await self.db.execute(select(func.count(WorkOrder.id)).where(WorkOrder.device_id == device_id))
        ).scalar() or 0
        if wo_count > 0:
            impacts.append(
                {
                    "table_name": "work_orders",
                    "display_name": "工单软关联",
                    "count": wo_count,
                    "action": "warn",  # 软关联，仅警告
                }
            )

        # 14. 控制命令软关联（CommandApproval.target_device_id）
        from ..models.command import CommandApproval

        ca_count = (
            await self.db.execute(
                select(func.count(CommandApproval.id)).where(CommandApproval.target_device_id == device_id)
            )
        ).scalar() or 0
        if ca_count > 0:
            impacts.append(
                {
                    "table_name": "command_approvals",
                    "display_name": "控制命令软关联",
                    "count": ca_count,
                    "action": "warn",
                }
            )

        # 15. 点位能源设备软关联（Point.energy_device_id）
        if point_ids:
            # 查找关联到 PowerDevice 的点位
            pd_result = await self.db.execute(select(PowerDevice.id).where(PowerDevice.monitor_device_id == device_id))
            power_device_ids = [row[0] for row in pd_result.all()]

            if power_device_ids:
                energy_point_count = (
                    await self.db.execute(
                        select(func.count(Point.id)).where(Point.energy_device_id.in_(power_device_ids))
                    )
                ).scalar() or 0
                if energy_point_count > 0:
                    impacts.append(
                        {
                            "table_name": "points",
                            "display_name": "点位能源设备软关联",
                            "count": energy_point_count,
                            "action": "warn",
                        }
                    )

        total_affected = sum(item["count"] for item in impacts)

        return {
            "device_id": device.id,
            "device_code": device.device_code,
            "device_name": device.device_name,
            "impacts": impacts,
            "total_affected_records": total_affected,
        }

    async def cascade_delete(self, device_id: int) -> dict:
        """按 FK 顺序级联删除"""

        # 获取设备信息
        result = await self.db.execute(select(Device).where(Device.id == device_id))
        device = result.scalar_one_or_none()
        if not device:
            return {"error": "设备不存在"}

        deleted = {}

        # 获取该设备下所有点位 ID
        point_ids_result = await self.db.execute(select(Point.id).where(Point.device_id == device_id))
        point_ids = [row[0] for row in point_ids_result.all()]

        if point_ids:
            # 1. alarm_thresholds
            r = await self.db.execute(delete(AlarmThreshold).where(AlarmThreshold.point_id.in_(point_ids)))
            deleted["alarm_thresholds"] = r.rowcount

            # 2. point_realtime
            r = await self.db.execute(delete(PointRealtime).where(PointRealtime.point_id.in_(point_ids)))
            deleted["point_realtime"] = r.rowcount

            # 3. point_history
            r = await self.db.execute(delete(PointHistory).where(PointHistory.point_id.in_(point_ids)))
            deleted["point_history"] = r.rowcount

        # 4-5. battery_groups → ups_devices
        ups_result = await self.db.execute(select(UPSDevice.id).where(UPSDevice.device_id == device_id))
        ups_ids = [row[0] for row in ups_result.all()]
        if ups_ids:
            r = await self.db.execute(delete(BatteryGroup).where(BatteryGroup.ups_device_id.in_(ups_ids)))
            deleted["battery_groups"] = r.rowcount

        r = await self.db.execute(delete(UPSDevice).where(UPSDevice.device_id == device_id))
        deleted["ups_devices"] = r.rowcount

        # 6. cooling_units
        r = await self.db.execute(delete(CoolingUnit).where(CoolingUnit.device_id == device_id))
        deleted["cooling_units"] = r.rowcount

        # 7. cold_aisles
        r = await self.db.execute(delete(ColdAisle).where(ColdAisle.device_id == device_id))
        deleted["cold_aisles"] = r.rowcount

        # 8. device_health_scores
        r = await self.db.execute(delete(DeviceHealthScore).where(DeviceHealthScore.device_id == device_id))
        deleted["device_health_scores"] = r.rowcount

        # 9. power_phase_mappings
        r = await self.db.execute(delete(PowerPhaseMapping).where(PowerPhaseMapping.pdu_device_id == device_id))
        deleted["power_phase_mappings"] = r.rowcount

        # 10. points
        if point_ids:
            r = await self.db.execute(delete(Point).where(Point.device_id == device_id))
            deleted["points"] = r.rowcount

        # 11. distribution_panels → 解除关联，禁用
        panels_result = await self.db.execute(select(DistributionPanel).where(DistributionPanel.device_id == device_id))
        panels = panels_result.scalars().all()
        for panel in panels:
            panel.device_id = None
            panel.is_enabled = False
            panel.updated_at = datetime.now()
        deleted["distribution_panels_unlinked"] = len(panels)

        # 12. power_devices → 解除关联，禁用
        pd_result = await self.db.execute(select(PowerDevice).where(PowerDevice.monitor_device_id == device_id))
        pds = pd_result.scalars().all()
        for pd in pds:
            pd.monitor_device_id = None
            pd.is_enabled = False
            pd.updated_at = datetime.now()
        deleted["power_devices_unlinked"] = len(pds)

        # 13. 软关联警告（不删除，仅记录）
        from ..models.operation import WorkOrder
        from ..models.command import CommandApproval

        wo_count = (
            await self.db.execute(select(func.count(WorkOrder.id)).where(WorkOrder.device_id == device_id))
        ).scalar() or 0
        deleted["work_orders_soft_ref"] = wo_count

        ca_count = (
            await self.db.execute(
                select(func.count(CommandApproval.id)).where(CommandApproval.target_device_id == device_id)
            )
        ).scalar() or 0
        deleted["command_approvals_soft_ref"] = ca_count

        # 14. 删除 Device 本身
        await self.db.execute(delete(Device).where(Device.id == device_id))
        deleted["device"] = 1

        logger.info(f"级联删除设备 {device.device_code}: {deleted}")

        return deleted

    async def on_device_created(self, device: Device) -> None:
        """创建设备后自动创建扩展记录"""
        if device.device_type == "UPS":
            # 检查是否已有 UPSDevice 扩展
            existing = await self.db.execute(select(UPSDevice).where(UPSDevice.device_id == device.id))
            if not existing.scalar_one_or_none():
                ups = UPSDevice(
                    device_id=device.id,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )
                self.db.add(ups)

        elif device.device_type in ("PRECISION_AC_INDOOR", "PRECISION_AC_OUTDOOR"):
            existing = await self.db.execute(select(CoolingUnit).where(CoolingUnit.device_id == device.id))
            if not existing.scalar_one_or_none():
                unit_type = "indoor" if device.device_type == "PRECISION_AC_INDOOR" else "outdoor"
                cu = CoolingUnit(
                    device_id=device.id,
                    unit_type=unit_type,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )
                self.db.add(cu)

        elif device.device_type == "COLD_AISLE":
            existing = await self.db.execute(select(ColdAisle).where(ColdAisle.device_id == device.id))
            if not existing.scalar_one_or_none():
                ca = ColdAisle(
                    device_id=device.id,
                    aisle_code=device.device_code,
                    aisle_name=device.device_name,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )
                self.db.add(ca)

    async def on_device_updated(self, device: Device, old_code: str = None) -> None:
        """编辑设备后同步关联记录"""
        # UPSDevice/CoolingUnit/ColdAisle 没有独立的 name 字段需要同步
        # 拓扑侧的同步已由 DeviceSyncService.on_device_updated() 处理
        pass

    async def analyze_power_device_delete_impact(self, power_device_id: int) -> dict:
        """分析 PowerDevice 删除影响，与 Device 删除保持一致的检查逻辑"""

        result = await self.db.execute(select(PowerDevice).where(PowerDevice.id == power_device_id))
        power_device = result.scalar_one_or_none()
        if not power_device:
            return None

        impacts = []

        # 1. 子设备（parent_device_id）
        child_count = (
            await self.db.execute(
                select(func.count(PowerDevice.id)).where(PowerDevice.parent_device_id == power_device_id)
            )
        ).scalar() or 0
        if child_count > 0:
            impacts.append(
                {
                    "table_name": "power_devices",
                    "display_name": "子设备",
                    "count": child_count,
                    "action": "block",  # 阻断删除
                }
            )

        # 2. 能耗数据（EnergyHourly/Daily/Monthly）
        from ..models.energy import EnergyHourly, EnergyDaily, EnergyMonthly

        hourly_count = (
            await self.db.execute(select(func.count(EnergyHourly.id)).where(EnergyHourly.device_id == power_device_id))
        ).scalar() or 0
        daily_count = (
            await self.db.execute(select(func.count(EnergyDaily.id)).where(EnergyDaily.device_id == power_device_id))
        ).scalar() or 0
        monthly_count = (
            await self.db.execute(
                select(func.count(EnergyMonthly.id)).where(EnergyMonthly.device_id == power_device_id)
            )
        ).scalar() or 0

        total_energy = hourly_count + daily_count + monthly_count
        if total_energy > 0:
            impacts.append(
                {
                    "table_name": "energy_data",
                    "display_name": "能耗历史数据",
                    "count": total_energy,
                    "action": "delete",
                }
            )

        # 3. 负载配置（DeviceLoadProfile）
        from ..models.energy import DeviceLoadProfile

        profile_count = (
            await self.db.execute(
                select(func.count(DeviceLoadProfile.id)).where(DeviceLoadProfile.device_id == power_device_id)
            )
        ).scalar() or 0
        if profile_count > 0:
            impacts.append(
                {
                    "table_name": "device_load_profiles",
                    "display_name": "负载配置",
                    "count": profile_count,
                    "action": "delete",
                }
            )

        # 4. 转移配置（DeviceShiftConfig）
        from ..models.energy import DeviceShiftConfig

        shift_count = (
            await self.db.execute(
                select(func.count(DeviceShiftConfig.id)).where(DeviceShiftConfig.device_id == power_device_id)
            )
        ).scalar() or 0
        if shift_count > 0:
            impacts.append(
                {
                    "table_name": "device_shift_configs",
                    "display_name": "转移配置",
                    "count": shift_count,
                    "action": "delete",
                }
            )

        # 5. 调节配置（LoadRegulationConfig）
        from ..models.energy import LoadRegulationConfig

        reg_count = (
            await self.db.execute(
                select(func.count(LoadRegulationConfig.id)).where(LoadRegulationConfig.device_id == power_device_id)
            )
        ).scalar() or 0
        if reg_count > 0:
            impacts.append(
                {
                    "table_name": "load_regulation_configs",
                    "display_name": "调节配置",
                    "count": reg_count,
                    "action": "delete",
                }
            )

        # 6. 关联的 Device（monitor_device_id）
        if power_device.monitor_device_id:
            impacts.append(
                {
                    "table_name": "devices",
                    "display_name": "关联监控设备",
                    "count": 1,
                    "action": "unlink",  # 解除关联，不删除
                }
            )

        total_affected = sum(item["count"] for item in impacts)

        return {
            "power_device_id": power_device.id,
            "device_code": power_device.device_code,
            "device_name": power_device.device_name,
            "impacts": impacts,
            "total_affected_records": total_affected,
        }
