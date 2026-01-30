"""
点位与设备智能匹配引擎
Point-Device Smart Matching Engine

用通用规则替代硬编码映射，实现双向关联
"""
import re
import logging
from typing import Dict, List, Optional, Tuple, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from ..models.point import Point
from ..models.energy import PowerDevice

logger = logging.getLogger(__name__)


class PointDeviceMatcher:
    """点位与设备智能匹配引擎"""

    # 点位名称关键词到用途的映射
    KEYWORD_TO_USAGE = {
        "power": ["功率", "有功功率", "power", "输出功率", "负载率"],
        "current": ["电流", "current", "电流值"],
        "energy": ["电能", "电量", "累计电量", "energy", "kWh"],
        "voltage": ["电压", "voltage", "输入电压", "输出电压"],
        "power_factor": ["功率因数", "power factor", "cos", "pf"],
    }

    # 设备编码到点位前缀的已知映射（作为 fallback）
    LEGACY_MAPPING_RULES = {
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
        "UPS-001": {"prefix": "A1_UPS_AI_", "power": "002", "current": "003"},
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
        "F1-UPS-001": {"prefix": "F1_UPS_AI_", "power": "0013"},
        "F1-UPS-002": {"prefix": "F1_UPS_AI_", "power": "0023"},
        "F2-UPS-001": {"prefix": "F2_UPS_AI_", "power": "0013"},
        "F2-UPS-002": {"prefix": "F2_UPS_AI_", "power": "0023"},
        "F3-UPS-001": {"prefix": "F3_UPS_AI_", "power": "0013"},
        # F1/F2/F3 精密空调使用回风温度点位
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
    }

    # 设备类型到点位前缀类型的映射
    DEVICE_TYPE_TO_POINT_PREFIX = {
        "IT": "SRV",
        "CHILLER": "CH",
        "CT": "CT",
        "PUMP": ["CHWP", "CWP"],  # 可能是冷冻水泵或冷却水泵
        "UPS": "UPS",
        "AC": "AC",
        "LIGHT": "LIGHT",
    }

    @classmethod
    def derive_point_prefix(cls, device_code: str, device_type: str, area_code: str) -> Optional[str]:
        """
        从设备编码和区域推导点位前缀模式

        例如:
        - 设备 CH-001 (area=B1, type=CHILLER) → 前缀 B1_CH_AI_
        - 设备 SRV-001 (area=A1, type=IT) → 前缀 A1_SRV_AI_
        """
        if not device_code or not area_code:
            return None

        # 从设备编码中提取前缀部分（如 CH-001 -> CH）
        match = re.match(r'^([A-Z]+)', device_code.upper())
        if match:
            device_prefix = match.group(1)
            return f"{area_code}_{device_prefix}_AI_"

        # 如果无法从编码提取，尝试从设备类型获取
        prefix_type = cls.DEVICE_TYPE_TO_POINT_PREFIX.get(device_type)
        if prefix_type:
            if isinstance(prefix_type, list):
                prefix_type = prefix_type[0]  # 使用第一个作为默认
            return f"{area_code}_{prefix_type}_AI_"

        return None

    @classmethod
    def identify_point_usage(cls, point_name: str) -> Optional[str]:
        """
        根据点位名称中的关键词识别点位用途

        返回值: 'power', 'current', 'energy', 'voltage', 'power_factor', 或 None
        """
        point_name_lower = point_name.lower()

        for usage, keywords in cls.KEYWORD_TO_USAGE.items():
            for keyword in keywords:
                if keyword in point_name_lower or keyword.lower() in point_name_lower:
                    return usage

        return None

    @classmethod
    def find_matching_points(
        cls,
        device_code: str,
        device_name: str,
        area_code: str,
        point_map: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Optional[int]]:
        """
        根据设备编码和名称查找匹配的点位

        Args:
            device_code: 设备编码 (如 CH-001)
            device_name: 设备名称 (如 1#冷水机组)
            area_code: 区域代码 (如 B1)
            point_map: 点位映射表 {point_code: {id, name, unit}}

        Returns:
            {"power_point_id": id, "current_point_id": id, "energy_point_id": id}
        """
        result = {
            "power_point_id": None,
            "current_point_id": None,
            "energy_point_id": None,
        }

        # 首先尝试使用遗留映射规则（保证向后兼容）
        legacy_rule = cls.LEGACY_MAPPING_RULES.get(device_code)
        if legacy_rule:
            prefix = legacy_rule["prefix"]
            for field, suffix in [("power", "power_point_id"), ("current", "current_point_id"), ("energy", "energy_point_id")]:
                if field in legacy_rule:
                    point_code = f"{prefix}{legacy_rule[field]}"
                    if point_code in point_map:
                        result[suffix] = point_map[point_code]["id"]

            # 如果遗留规则已找到至少一个点位，直接返回
            if any(result.values()):
                return result

        # 智能匹配：根据设备编码和区域推导点位前缀
        prefix = cls.derive_point_prefix(device_code, "", area_code)
        if not prefix:
            return result

        # 在点位映射表中搜索匹配的点位
        matching_points = {
            "power": [],
            "current": [],
            "energy": [],
        }

        for point_code, point_info in point_map.items():
            if point_code.startswith(prefix):
                usage = cls.identify_point_usage(point_info.get("name", ""))
                if usage and usage in matching_points:
                    matching_points[usage].append({
                        "code": point_code,
                        "id": point_info["id"],
                        "name": point_info.get("name", ""),
                    })

        # 从匹配结果中选择最合适的（取第一个）
        if matching_points["power"]:
            result["power_point_id"] = matching_points["power"][0]["id"]
        if matching_points["current"]:
            result["current_point_id"] = matching_points["current"][0]["id"]
        if matching_points["energy"]:
            result["energy_point_id"] = matching_points["energy"][0]["id"]

        return result

    @classmethod
    async def sync_bidirectional_relations(
        cls,
        session: AsyncSession,
        device_id: int,
        power_point_id: Optional[int],
        current_point_id: Optional[int],
        energy_point_id: Optional[int],
    ) -> int:
        """
        同步双向关联关系

        设置 PowerDevice 的点位字段的同时，也设置 Point 的 energy_device_id

        Returns:
            更新的点位数量
        """
        updated_count = 0

        point_ids = [pid for pid in [power_point_id, current_point_id, energy_point_id] if pid]

        if point_ids:
            # 批量更新点位的 energy_device_id
            await session.execute(
                update(Point)
                .where(Point.id.in_(point_ids))
                .values(energy_device_id=device_id)
            )
            updated_count = len(point_ids)

        return updated_count

    @classmethod
    async def clear_device_point_relations(
        cls,
        session: AsyncSession,
        device_id: int,
    ) -> int:
        """
        清除设备的所有点位关联

        将所有关联到该设备的点位的 energy_device_id 设为 None

        Returns:
            清除关联的点位数量
        """
        result = await session.execute(
            select(Point).where(Point.energy_device_id == device_id)
        )
        points = result.scalars().all()

        if points:
            await session.execute(
                update(Point)
                .where(Point.energy_device_id == device_id)
                .values(energy_device_id=None)
            )

        return len(points)

    @classmethod
    async def get_sync_statistics(cls, session: AsyncSession) -> Dict[str, Any]:
        """
        获取同步统计信息

        Returns:
            统计信息字典
        """
        from sqlalchemy import func

        # 总设备数
        total_devices_result = await session.execute(select(func.count(PowerDevice.id)))
        total_devices = total_devices_result.scalar() or 0

        # 已关联点位的设备数
        linked_devices_result = await session.execute(
            select(func.count(PowerDevice.id)).where(
                PowerDevice.power_point_id.isnot(None)
            )
        )
        linked_devices = linked_devices_result.scalar() or 0

        # 总点位数
        total_points_result = await session.execute(select(func.count(Point.id)))
        total_points = total_points_result.scalar() or 0

        # 已关联设备的点位数
        linked_points_result = await session.execute(
            select(func.count(Point.id)).where(
                Point.energy_device_id.isnot(None)
            )
        )
        linked_points = linked_points_result.scalar() or 0

        # 孤立设备（有设备无点位关联）
        orphan_devices_result = await session.execute(
            select(func.count(PowerDevice.id)).where(
                PowerDevice.power_point_id.is_(None),
                PowerDevice.current_point_id.is_(None),
                PowerDevice.energy_point_id.is_(None),
            )
        )
        orphan_devices = orphan_devices_result.scalar() or 0

        return {
            "total_devices": total_devices,
            "linked_devices": linked_devices,
            "orphan_devices": orphan_devices,
            "total_points": total_points,
            "linked_points": linked_points,
            "device_link_rate": round(linked_devices / total_devices * 100, 1) if total_devices > 0 else 0,
            "point_link_rate": round(linked_points / total_points * 100, 1) if total_points > 0 else 0,
        }

    @classmethod
    async def full_sync(
        cls,
        session: AsyncSession,
        progress_callback=None,
    ) -> Dict[str, Any]:
        """
        执行完整的双向同步

        1. 读取所有设备和点位
        2. 为每个设备查找匹配点位
        3. 双向更新关联关系

        Returns:
            同步结果统计
        """
        # 1. 构建点位映射
        result = await session.execute(select(Point))
        points = result.scalars().all()

        point_map = {}
        for p in points:
            point_map[p.point_code] = {
                "id": p.id,
                "name": p.point_name,
                "unit": p.unit,
            }

        # 2. 获取所有设备
        result = await session.execute(select(PowerDevice))
        devices = result.scalars().all()

        # 3. 逐个处理设备
        updated_devices = 0
        updated_points = 0
        matched_relations = []

        for device in devices:
            # 查找匹配点位
            point_ids = cls.find_matching_points(
                device.device_code,
                device.device_name,
                device.area_code or "",
                point_map
            )

            # 更新设备端关联
            need_update = False
            if point_ids["power_point_id"] and device.power_point_id != point_ids["power_point_id"]:
                device.power_point_id = point_ids["power_point_id"]
                need_update = True
            if point_ids["current_point_id"] and device.current_point_id != point_ids["current_point_id"]:
                device.current_point_id = point_ids["current_point_id"]
                need_update = True
            if point_ids["energy_point_id"] and device.energy_point_id != point_ids["energy_point_id"]:
                device.energy_point_id = point_ids["energy_point_id"]
                need_update = True

            if need_update:
                updated_devices += 1

            # 双向更新：设置点位的 energy_device_id
            point_count = await cls.sync_bidirectional_relations(
                session,
                device.id,
                point_ids["power_point_id"],
                point_ids["current_point_id"],
                point_ids["energy_point_id"],
            )
            updated_points += point_count

            if any(point_ids.values()):
                matched_relations.append({
                    "device_code": device.device_code,
                    "device_name": device.device_name,
                    "power_point_id": point_ids["power_point_id"],
                    "current_point_id": point_ids["current_point_id"],
                    "energy_point_id": point_ids["energy_point_id"],
                })

        await session.commit()

        # 获取最终统计
        stats = await cls.get_sync_statistics(session)

        logger.info(
            f"同步完成: 更新 {updated_devices} 个设备, "
            f"{updated_points} 个点位关联, "
            f"设备关联率 {stats['device_link_rate']}%, "
            f"点位关联率 {stats['point_link_rate']}%"
        )

        return {
            "success": True,
            "updated_devices": updated_devices,
            "updated_points": updated_points,
            "matched_count": len(matched_relations),
            "statistics": stats,
        }
