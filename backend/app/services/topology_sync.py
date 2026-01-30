"""
拓扑同步服务
负责拓扑变更时的数据同步、测点创建、数据模拟器更新等
"""
from typing import List, Dict, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from datetime import datetime

from app.models.energy import (
    Transformer, MeterPoint, DistributionPanel, DistributionCircuit, PowerDevice
)
from app.models.point import Point, PointRealtime
from app.schemas.energy import (
    TopologyNodeType, DevicePointConfig, DevicePointConfigCreate
)


class TopologySyncService:
    """拓扑同步服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def sync_device_points(
        self,
        device_id: int,
        device_code: str,
        points_config: List[DevicePointConfig]
    ) -> List[int]:
        """
        同步设备测点到点位管理模块

        Args:
            device_id: 用能设备ID
            device_code: 设备编码
            points_config: 测点配置列表

        Returns:
            创建的点位ID列表
        """
        # 获取设备信息以获取 device_type
        device_result = await self.db.execute(
            select(PowerDevice).where(PowerDevice.id == device_id)
        )
        device = device_result.scalar_one_or_none()
        device_type = device.device_type if device else "OTHER"
        area_code = device.area_code if device and device.area_code else "A1"

        created_point_ids = []

        for point_config in points_config:
            # 使用传入的编码或自动生成
            point_code = point_config.point_code
            if not point_code.startswith(device_code):
                point_code = f"{device_code}_{point_config.point_code}"

            result = await self.db.execute(
                select(Point).where(Point.point_code == point_code)
            )
            existing_point = result.scalar_one_or_none()

            # 点位类型处理：支持字符串或枚举
            point_type_value = point_config.point_type
            if hasattr(point_type_value, 'value'):
                point_type_value = point_type_value.value

            # 使用配置中的 device_type 和 area_code，如果没有则使用设备默认值
            config_device_type = getattr(point_config, 'device_type', None) or device_type
            config_area_code = getattr(point_config, 'area_code', None) or area_code
            config_min_range = getattr(point_config, 'min_range', None)
            config_max_range = getattr(point_config, 'max_range', None)
            config_collect_interval = getattr(point_config, 'collect_interval', 10)

            if existing_point:
                # 更新现有点位
                existing_point.point_name = point_config.point_name
                existing_point.point_type = point_type_value
                existing_point.data_type = point_config.data_type
                existing_point.unit = point_config.unit
                existing_point.min_range = config_min_range
                existing_point.max_range = config_max_range
                existing_point.collect_interval = config_collect_interval
                existing_point.description = point_config.description
                existing_point.device_id = point_config.device_id
                existing_point.register_address = point_config.register_address
                existing_point.function_code = point_config.function_code
                existing_point.scale_factor = point_config.scale_factor
                existing_point.offset = point_config.offset
                existing_point.updated_at = datetime.now()
                created_point_ids.append(existing_point.id)
            else:
                # 创建新点位
                new_point = Point(
                    point_code=point_code,
                    point_name=point_config.point_name,
                    point_type=point_type_value,
                    device_type=config_device_type,
                    area_code=config_area_code,
                    data_type=point_config.data_type,
                    unit=point_config.unit,
                    min_range=config_min_range,
                    max_range=config_max_range,
                    collect_interval=config_collect_interval,
                    description=point_config.description,
                    device_id=point_config.device_id,
                    register_address=point_config.register_address,
                    function_code=point_config.function_code,
                    scale_factor=point_config.scale_factor,
                    offset=point_config.offset,
                    is_enabled=True,
                    energy_device_id=device_id,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                self.db.add(new_point)
                await self.db.flush()
                created_point_ids.append(new_point.id)

                # 创建实时数据记录
                realtime = PointRealtime(
                    point_id=new_point.id,
                    value=0.0,
                    quality=0,
                    status="normal",
                    updated_at=datetime.now()
                )
                self.db.add(realtime)

        await self.db.commit()
        return created_point_ids

    async def remove_device_points(self, device_id: int) -> int:
        """
        删除设备关联的所有测点

        Args:
            device_id: 用能设备ID

        Returns:
            删除的点位数量
        """
        # 查找所有关联点位
        result = await self.db.execute(
            select(Point).where(Point.energy_device_id == device_id)
        )
        points = result.scalars().all()

        if not points:
            return 0

        point_ids = [p.id for p in points]

        # 删除实时数据
        await self.db.execute(
            delete(PointRealtime).where(PointRealtime.point_id.in_(point_ids))
        )

        # 删除点位
        await self.db.execute(
            delete(Point).where(Point.id.in_(point_ids))
        )

        await self.db.commit()
        return len(point_ids)

    async def update_meter_point_hierarchy(
        self,
        meter_point_id: int,
        new_transformer_id: Optional[int]
    ) -> bool:
        """
        更新计量点的变压器归属关系

        Args:
            meter_point_id: 计量点ID
            new_transformer_id: 新的变压器ID

        Returns:
            是否成功
        """
        result = await self.db.execute(
            select(MeterPoint).where(MeterPoint.id == meter_point_id)
        )
        meter_point = result.scalar_one_or_none()

        if not meter_point:
            return False

        meter_point.transformer_id = new_transformer_id
        meter_point.updated_at = datetime.now()
        await self.db.commit()
        return True

    async def update_panel_hierarchy(
        self,
        panel_id: int,
        new_meter_point_id: Optional[int]
    ) -> bool:
        """
        更新配电柜的计量点归属关系

        Args:
            panel_id: 配电柜ID
            new_meter_point_id: 新的计量点ID

        Returns:
            是否成功
        """
        result = await self.db.execute(
            select(DistributionPanel).where(DistributionPanel.id == panel_id)
        )
        panel = result.scalar_one_or_none()

        if not panel:
            return False

        panel.meter_point_id = new_meter_point_id
        panel.updated_at = datetime.now()
        await self.db.commit()
        return True

    async def update_circuit_hierarchy(
        self,
        circuit_id: int,
        new_panel_id: Optional[int]
    ) -> bool:
        """
        更新回路的配电柜归属关系

        Args:
            circuit_id: 回路ID
            new_panel_id: 新的配电柜ID

        Returns:
            是否成功
        """
        result = await self.db.execute(
            select(DistributionCircuit).where(DistributionCircuit.id == circuit_id)
        )
        circuit = result.scalar_one_or_none()

        if not circuit:
            return False

        circuit.panel_id = new_panel_id
        circuit.updated_at = datetime.now()
        await self.db.commit()
        return True

    async def update_device_hierarchy(
        self,
        device_id: int,
        new_circuit_id: Optional[int]
    ) -> bool:
        """
        更新设备的回路归属关系

        Args:
            device_id: 设备ID
            new_circuit_id: 新的回路ID

        Returns:
            是否成功
        """
        result = await self.db.execute(
            select(PowerDevice).where(PowerDevice.id == device_id)
        )
        device = result.scalar_one_or_none()

        if not device:
            return False

        device.circuit_id = new_circuit_id
        device.updated_at = datetime.now()
        await self.db.commit()
        return True

    async def cascade_delete_check(
        self,
        node_id: int,
        node_type: TopologyNodeType
    ) -> Dict[str, int]:
        """
        检查级联删除影响范围

        Args:
            node_id: 节点ID
            node_type: 节点类型

        Returns:
            影响范围统计 {node_type: count}
        """
        impact = {}

        if node_type == TopologyNodeType.TRANSFORMER:
            # 统计下级计量点
            result = await self.db.execute(
                select(MeterPoint).where(MeterPoint.transformer_id == node_id)
            )
            meter_points = result.scalars().all()
            impact["meter_points"] = len(meter_points)

            # 统计下级配电柜
            meter_point_ids = [mp.id for mp in meter_points]
            if meter_point_ids:
                result = await self.db.execute(
                    select(DistributionPanel).where(DistributionPanel.meter_point_id.in_(meter_point_ids))
                )
                panels = result.scalars().all()
                impact["panels"] = len(panels)

                # 统计下级回路
                panel_ids = [p.id for p in panels]
                if panel_ids:
                    result = await self.db.execute(
                        select(DistributionCircuit).where(DistributionCircuit.panel_id.in_(panel_ids))
                    )
                    circuits = result.scalars().all()
                    impact["circuits"] = len(circuits)

                    # 统计下级设备
                    circuit_ids = [c.id for c in circuits]
                    if circuit_ids:
                        result = await self.db.execute(
                            select(PowerDevice).where(PowerDevice.circuit_id.in_(circuit_ids))
                        )
                        devices = result.scalars().all()
                        impact["devices"] = len(devices)

        elif node_type == TopologyNodeType.METER_POINT:
            result = await self.db.execute(
                select(DistributionPanel).where(DistributionPanel.meter_point_id == node_id)
            )
            panels = result.scalars().all()
            impact["panels"] = len(panels)

            panel_ids = [p.id for p in panels]
            if panel_ids:
                result = await self.db.execute(
                    select(DistributionCircuit).where(DistributionCircuit.panel_id.in_(panel_ids))
                )
                circuits = result.scalars().all()
                impact["circuits"] = len(circuits)

                circuit_ids = [c.id for c in circuits]
                if circuit_ids:
                    result = await self.db.execute(
                        select(PowerDevice).where(PowerDevice.circuit_id.in_(circuit_ids))
                    )
                    devices = result.scalars().all()
                    impact["devices"] = len(devices)

        elif node_type == TopologyNodeType.PANEL:
            result = await self.db.execute(
                select(DistributionCircuit).where(DistributionCircuit.panel_id == node_id)
            )
            circuits = result.scalars().all()
            impact["circuits"] = len(circuits)

            circuit_ids = [c.id for c in circuits]
            if circuit_ids:
                result = await self.db.execute(
                    select(PowerDevice).where(PowerDevice.circuit_id.in_(circuit_ids))
                )
                devices = result.scalars().all()
                impact["devices"] = len(devices)

        elif node_type == TopologyNodeType.CIRCUIT:
            result = await self.db.execute(
                select(PowerDevice).where(PowerDevice.circuit_id == node_id)
            )
            devices = result.scalars().all()
            impact["devices"] = len(devices)

        return impact

    async def cascade_delete(
        self,
        node_id: int,
        node_type: TopologyNodeType
    ) -> Dict[str, int]:
        """
        执行级联删除

        Args:
            node_id: 节点ID
            node_type: 节点类型

        Returns:
            删除统计 {node_type: count}
        """
        deleted = {}

        if node_type == TopologyNodeType.TRANSFORMER:
            # 查找下级计量点
            result = await self.db.execute(
                select(MeterPoint).where(MeterPoint.transformer_id == node_id)
            )
            meter_points = result.scalars().all()

            for mp in meter_points:
                sub_deleted = await self.cascade_delete(mp.id, TopologyNodeType.METER_POINT)
                for k, v in sub_deleted.items():
                    deleted[k] = deleted.get(k, 0) + v

            # 删除计量点
            await self.db.execute(
                delete(MeterPoint).where(MeterPoint.transformer_id == node_id)
            )
            deleted["meter_points"] = len(meter_points)

            # 删除变压器
            await self.db.execute(
                delete(Transformer).where(Transformer.id == node_id)
            )
            deleted["transformers"] = 1

        elif node_type == TopologyNodeType.METER_POINT:
            # 查找下级配电柜
            result = await self.db.execute(
                select(DistributionPanel).where(DistributionPanel.meter_point_id == node_id)
            )
            panels = result.scalars().all()

            for panel in panels:
                sub_deleted = await self.cascade_delete(panel.id, TopologyNodeType.PANEL)
                for k, v in sub_deleted.items():
                    deleted[k] = deleted.get(k, 0) + v

            # 删除配电柜
            await self.db.execute(
                delete(DistributionPanel).where(DistributionPanel.meter_point_id == node_id)
            )
            deleted["panels"] = len(panels)

            # 删除计量点
            await self.db.execute(
                delete(MeterPoint).where(MeterPoint.id == node_id)
            )
            deleted["meter_points"] = 1

        elif node_type == TopologyNodeType.PANEL:
            # 查找下级回路
            result = await self.db.execute(
                select(DistributionCircuit).where(DistributionCircuit.panel_id == node_id)
            )
            circuits = result.scalars().all()

            for circuit in circuits:
                sub_deleted = await self.cascade_delete(circuit.id, TopologyNodeType.CIRCUIT)
                for k, v in sub_deleted.items():
                    deleted[k] = deleted.get(k, 0) + v

            # 删除回路
            await self.db.execute(
                delete(DistributionCircuit).where(DistributionCircuit.panel_id == node_id)
            )
            deleted["circuits"] = len(circuits)

            # 删除配电柜
            await self.db.execute(
                delete(DistributionPanel).where(DistributionPanel.id == node_id)
            )
            deleted["panels"] = 1

        elif node_type == TopologyNodeType.CIRCUIT:
            # 查找下级设备
            result = await self.db.execute(
                select(PowerDevice).where(PowerDevice.circuit_id == node_id)
            )
            devices = result.scalars().all()

            # 删除设备的测点
            for device in devices:
                await self.remove_device_points(device.id)

            # 删除设备
            await self.db.execute(
                delete(PowerDevice).where(PowerDevice.circuit_id == node_id)
            )
            deleted["devices"] = len(devices)

            # 删除回路
            await self.db.execute(
                delete(DistributionCircuit).where(DistributionCircuit.id == node_id)
            )
            deleted["circuits"] = 1

        elif node_type == TopologyNodeType.DEVICE:
            # 删除设备测点
            await self.remove_device_points(node_id)

            # 删除设备
            await self.db.execute(
                delete(PowerDevice).where(PowerDevice.id == node_id)
            )
            deleted["devices"] = 1

        await self.db.commit()
        return deleted

    async def notify_data_simulator(
        self,
        operation: str,
        node_type: str,
        node_id: int,
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        通知数据模拟器更新

        Args:
            operation: 操作类型 (create/update/delete)
            node_type: 节点类型
            node_id: 节点ID
            data: 附加数据

        Returns:
            是否成功
        """
        # TODO: 实现与数据模拟器的通信
        # 可以通过消息队列、HTTP回调等方式通知
        # 这里暂时只打印日志
        print(f"[DataSimulator] {operation} {node_type} #{node_id}: {data}")
        return True
