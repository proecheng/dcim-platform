"""
点位与设备智能匹配引擎
Point-Device Smart Matching Engine

用通用规则替代硬编码映射，实现双向关联
"""

import re
import logging
from threading import RLock
from typing import Dict, Optional, Any, Set
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from ..models.point import Point
from ..models.energy import PowerDevice

logger = logging.getLogger(__name__)


class MatcherRegistry:
    """点位匹配规则注册表（线程安全）

    Story 28.3: 支持动态注册和卸载规则，实现 Demo 与主系统解耦
    """
    _rules: Dict[str, Dict] = {}
    _lock = RLock()
    _registered_sources: Set[str] = set()

    @classmethod
    def register(cls, rules: Dict[str, Dict], source: str = "default"):
        """注册自定义规则（自动添加 _source 标记）

        Args:
            rules: 规则字典
            source: 规则来源标识（用于后续卸载）
        """
        with cls._lock:
            for key, value in rules.items():
                rule_copy = value.copy()
                rule_copy["_source"] = source
                cls._rules[key] = rule_copy
            cls._registered_sources.add(source)
            logger.debug(f"注册规则来源 '{source}': {len(rules)} 条规则")

    @classmethod
    def unregister(cls, source: str):
        """卸载指定来源的规则

        Args:
            source: 规则来源标识
        """
        with cls._lock:
            keys_to_remove = [
                k for k, v in cls._rules.items()
                if v.get("_source") == source
            ]
            for key in keys_to_remove:
                del cls._rules[key]
            cls._registered_sources.discard(source)
            logger.debug(f"卸载规则来源 '{source}': {len(keys_to_remove)} 条规则")

    @classmethod
    def clear(cls):
        """清空所有规则（用于测试）"""
        with cls._lock:
            cls._rules.clear()
            cls._registered_sources.clear()

    @classmethod
    def get_rule(cls, point_code: str) -> Optional[Dict]:
        """获取单个规则（返回副本避免修改）"""
        with cls._lock:
            rule = cls._rules.get(point_code)
            return rule.copy() if rule else None

    @classmethod
    def has_rules(cls) -> bool:
        """检查是否有注册的规则"""
        with cls._lock:
            return len(cls._rules) > 0


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
        match = re.match(r"^([A-Z]+)", device_code.upper())
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
        cls, device_code: str, device_name: str, area_code: str, point_map: Dict[str, Dict[str, Any]]
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

        # 首先尝试使用注册的规则（支持 Demo 动态注册）
        legacy_rule = MatcherRegistry.get_rule(device_code)
        if legacy_rule:
            prefix = legacy_rule.get("prefix")
            if prefix:
                for field, suffix in [
                    ("power", "power_point_id"),
                    ("current", "current_point_id"),
                    ("energy", "energy_point_id"),
                ]:
                    if field in legacy_rule:
                        point_code = f"{prefix}{legacy_rule[field]}"
                        if point_code in point_map:
                            result[suffix] = point_map[point_code]["id"]

                # 如果注册规则已找到至少一个点位，直接返回
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
                    matching_points[usage].append(
                        {
                            "code": point_code,
                            "id": point_info["id"],
                            "name": point_info.get("name", ""),
                        }
                    )

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
            await session.execute(update(Point).where(Point.id.in_(point_ids)).values(energy_device_id=device_id))
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
        result = await session.execute(select(Point).where(Point.energy_device_id == device_id))
        points = result.scalars().all()

        if points:
            await session.execute(
                update(Point).where(Point.energy_device_id == device_id).values(energy_device_id=None)
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
            select(func.count(PowerDevice.id)).where(PowerDevice.power_point_id.isnot(None))
        )
        linked_devices = linked_devices_result.scalar() or 0

        # 总点位数
        total_points_result = await session.execute(select(func.count(Point.id)))
        total_points = total_points_result.scalar() or 0

        # 已关联设备的点位数
        linked_points_result = await session.execute(
            select(func.count(Point.id)).where(Point.energy_device_id.isnot(None))
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
                device.device_code, device.device_name, device.area_code or "", point_map
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
                matched_relations.append(
                    {
                        "device_code": device.device_code,
                        "device_name": device.device_name,
                        "power_point_id": point_ids["power_point_id"],
                        "current_point_id": point_ids["current_point_id"],
                        "energy_point_id": point_ids["energy_point_id"],
                    }
                )

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
