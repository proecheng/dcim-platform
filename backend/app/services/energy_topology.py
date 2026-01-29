"""
配电系统拓扑服务
Energy Topology Service

提供配电系统拓扑树构建、查询和编辑功能
"""
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from datetime import datetime

from ..models.energy import (
    Transformer, MeterPoint, DistributionPanel,
    DistributionCircuit, PowerDevice
)
from ..models.point import Point, PointRealtime
from ..schemas.energy import (
    TopologyNodeType, TopologyNodeCreate, TopologyNodeUpdate,
    TopologyNodeDelete, TopologyBatchOperation, TopologyBatchResult,
    TopologyExport, TopologyImport
)


class EnergyTopologyService:
    """配电系统拓扑服务"""

    @staticmethod
    async def get_full_topology(db: AsyncSession) -> Dict[str, Any]:
        """
        获取完整的配电系统拓扑
        返回树形结构数据
        """
        # 获取所有变压器及其关联数据
        result = await db.execute(
            select(Transformer)
            .options(selectinload(Transformer.meter_points))
            .where(Transformer.is_enabled == True)
            .order_by(Transformer.transformer_code)
        )
        transformers = result.scalars().all()

        topology = {
            "transformers": []
        }

        for transformer in transformers:
            transformer_node = await EnergyTopologyService._build_transformer_node(
                db, transformer
            )
            topology["transformers"].append(transformer_node)

        return topology

    @staticmethod
    async def _build_transformer_node(
        db: AsyncSession,
        transformer: Transformer
    ) -> Dict[str, Any]:
        """构建变压器节点"""
        node = {
            "id": transformer.id,
            "code": transformer.transformer_code,
            "name": transformer.transformer_name,
            "type": "transformer",
            "rated_capacity": transformer.rated_capacity,
            "voltage_high": transformer.voltage_high,
            "voltage_low": transformer.voltage_low,
            "status": transformer.status,
            "location": transformer.location,
            "meter_points": []
        }

        # 获取计量点
        meter_points_result = await db.execute(
            select(MeterPoint)
            .where(
                MeterPoint.transformer_id == transformer.id,
                MeterPoint.is_enabled == True
            )
            .order_by(MeterPoint.meter_code)
        )
        meter_points = meter_points_result.scalars().all()

        for mp in meter_points:
            mp_node = await EnergyTopologyService._build_meter_point_node(db, mp)
            node["meter_points"].append(mp_node)

        return node

    @staticmethod
    async def _build_meter_point_node(
        db: AsyncSession,
        meter_point: MeterPoint
    ) -> Dict[str, Any]:
        """构建计量点节点"""
        node = {
            "id": meter_point.id,
            "code": meter_point.meter_code,
            "name": meter_point.meter_name,
            "type": "meter_point",
            "meter_no": meter_point.meter_no,
            "declared_demand": meter_point.declared_demand,
            "demand_type": meter_point.demand_type,
            "customer_no": meter_point.customer_no,
            "status": meter_point.status,
            "panels": []
        }

        # 获取配电柜（顶级配电柜，即没有上级的）
        panels_result = await db.execute(
            select(DistributionPanel)
            .where(
                DistributionPanel.meter_point_id == meter_point.id,
                DistributionPanel.parent_panel_id.is_(None),
                DistributionPanel.is_enabled == True
            )
            .order_by(DistributionPanel.panel_code)
        )
        panels = panels_result.scalars().all()

        for panel in panels:
            panel_node = await EnergyTopologyService._build_panel_node(db, panel)
            node["panels"].append(panel_node)

        return node

    @staticmethod
    async def _build_panel_node(
        db: AsyncSession,
        panel: DistributionPanel,
        depth: int = 0
    ) -> Dict[str, Any]:
        """构建配电柜节点（递归处理子配电柜）"""
        if depth > 10:  # 防止无限递归
            return {}

        node = {
            "id": panel.id,
            "code": panel.panel_code,
            "name": panel.panel_name,
            "type": "panel",
            "panel_type": panel.panel_type,
            "rated_current": panel.rated_current,
            "rated_voltage": panel.rated_voltage,
            "location": panel.location,
            "status": panel.status,
            "circuits": [],
            "sub_panels": []
        }

        # 获取配电回路
        circuits_result = await db.execute(
            select(DistributionCircuit)
            .where(
                DistributionCircuit.panel_id == panel.id,
                DistributionCircuit.is_enabled == True
            )
            .order_by(DistributionCircuit.circuit_code)
        )
        circuits = circuits_result.scalars().all()

        for circuit in circuits:
            circuit_node = await EnergyTopologyService._build_circuit_node(db, circuit)
            node["circuits"].append(circuit_node)

        # 获取子配电柜
        sub_panels_result = await db.execute(
            select(DistributionPanel)
            .where(
                DistributionPanel.parent_panel_id == panel.id,
                DistributionPanel.is_enabled == True
            )
            .order_by(DistributionPanel.panel_code)
        )
        sub_panels = sub_panels_result.scalars().all()

        for sub_panel in sub_panels:
            sub_panel_node = await EnergyTopologyService._build_panel_node(
                db, sub_panel, depth + 1
            )
            node["sub_panels"].append(sub_panel_node)

        return node

    @staticmethod
    async def _build_circuit_node(
        db: AsyncSession,
        circuit: DistributionCircuit
    ) -> Dict[str, Any]:
        """构建配电回路节点"""
        node = {
            "id": circuit.id,
            "code": circuit.circuit_code,
            "name": circuit.circuit_name,
            "type": "circuit",
            "load_type": circuit.load_type,
            "rated_current": circuit.rated_current,
            "breaker_type": circuit.breaker_type,
            "is_shiftable": circuit.is_shiftable,
            "shift_priority": circuit.shift_priority,
            "devices": []
        }

        # 获取用电设备
        devices_result = await db.execute(
            select(PowerDevice)
            .where(
                PowerDevice.circuit_id == circuit.id,
                PowerDevice.is_enabled == True
            )
            .order_by(PowerDevice.device_code)
        )
        devices = devices_result.scalars().all()

        for device in devices:
            device_node = await EnergyTopologyService._build_device_node(db, device)
            node["devices"].append(device_node)

        return node

    @staticmethod
    async def _build_device_node(
        db: AsyncSession,
        device: PowerDevice
    ) -> Dict[str, Any]:
        """构建用电设备节点"""
        node = {
            "id": device.id,
            "code": device.device_code,
            "name": device.device_name,
            "type": "device",
            "device_type": device.device_type,
            "rated_power": device.rated_power,
            "is_it_load": device.is_it_load,
            "is_critical": device.is_critical,
            "is_metered": device.is_metered,
            "realtime_data": None
        }

        # 如果设备关联了功率点位，获取实时数据
        if device.power_point_id:
            realtime_result = await db.execute(
                select(PointRealtime)
                .where(PointRealtime.point_id == device.power_point_id)
            )
            realtime = realtime_result.scalar_one_or_none()
            if realtime:
                node["realtime_data"] = {
                    "power": realtime.value,
                    "update_time": realtime.update_time.isoformat() if realtime.update_time else None
                }

        return node

    @staticmethod
    async def get_node_detail(
        db: AsyncSession,
        node_type: str,
        node_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        获取指定节点的详细信息

        Args:
            node_type: 节点类型 (transformer/meter_point/panel/circuit/device)
            node_id: 节点ID
        """
        if node_type == "transformer":
            result = await db.execute(
                select(Transformer).where(Transformer.id == node_id)
            )
            item = result.scalar_one_or_none()
            if item:
                return await EnergyTopologyService._build_transformer_node(db, item)

        elif node_type == "meter_point":
            result = await db.execute(
                select(MeterPoint).where(MeterPoint.id == node_id)
            )
            item = result.scalar_one_or_none()
            if item:
                return await EnergyTopologyService._build_meter_point_node(db, item)

        elif node_type == "panel":
            result = await db.execute(
                select(DistributionPanel).where(DistributionPanel.id == node_id)
            )
            item = result.scalar_one_or_none()
            if item:
                return await EnergyTopologyService._build_panel_node(db, item)

        elif node_type == "circuit":
            result = await db.execute(
                select(DistributionCircuit).where(DistributionCircuit.id == node_id)
            )
            item = result.scalar_one_or_none()
            if item:
                return await EnergyTopologyService._build_circuit_node(db, item)

        elif node_type == "device":
            result = await db.execute(
                select(PowerDevice).where(PowerDevice.id == node_id)
            )
            item = result.scalar_one_or_none()
            if item:
                return await EnergyTopologyService._build_device_node(db, item)

        return None

    @staticmethod
    async def get_topology_for_echarts(db: AsyncSession) -> Dict[str, Any]:
        """
        获取适用于ECharts树图的拓扑数据格式
        """
        topology = await EnergyTopologyService.get_full_topology(db)

        def convert_to_echarts_node(node: Dict[str, Any], level: int = 0) -> Dict[str, Any]:
            """转换为ECharts树节点格式"""
            echarts_node = {
                "name": node.get("name", ""),
                "value": node.get("id"),
                "itemStyle": {
                    "color": EnergyTopologyService._get_node_color(node.get("type"))
                },
                "data": {
                    "type": node.get("type"),
                    "code": node.get("code"),
                    "status": node.get("status")
                },
                "children": []
            }

            # 处理子节点
            if "meter_points" in node:
                for mp in node["meter_points"]:
                    echarts_node["children"].append(convert_to_echarts_node(mp, level + 1))
            if "panels" in node:
                for panel in node["panels"]:
                    echarts_node["children"].append(convert_to_echarts_node(panel, level + 1))
            if "sub_panels" in node:
                for sub_panel in node["sub_panels"]:
                    echarts_node["children"].append(convert_to_echarts_node(sub_panel, level + 1))
            if "circuits" in node:
                for circuit in node["circuits"]:
                    echarts_node["children"].append(convert_to_echarts_node(circuit, level + 1))
            if "devices" in node:
                for device in node["devices"]:
                    echarts_node["children"].append(convert_to_echarts_node(device, level + 1))

            return echarts_node

        # 构建根节点
        root = {
            "name": "配电系统",
            "children": []
        }

        for transformer in topology.get("transformers", []):
            root["children"].append(convert_to_echarts_node(transformer))

        return root

    @staticmethod
    def _get_node_color(node_type: str) -> str:
        """获取节点颜色"""
        colors = {
            "transformer": "#f5222d",    # 红色 - 变压器
            "meter_point": "#fa8c16",    # 橙色 - 计量点
            "panel": "#1890ff",          # 蓝色 - 配电柜
            "circuit": "#52c41a",        # 绿色 - 回路
            "device": "#722ed1"          # 紫色 - 设备
        }
        return colors.get(node_type, "#8c8c8c")

    # ==================== CRUD 操作 ====================

    @staticmethod
    async def create_node(
        db: AsyncSession,
        data: TopologyNodeCreate
    ) -> Tuple[int, str]:
        """
        创建拓扑节点

        Args:
            db: 数据库会话
            data: 创建数据

        Returns:
            (节点ID, 节点类型)
        """
        now = datetime.now()

        if data.node_type == TopologyNodeType.TRANSFORMER:
            # 验证必填字段
            if not data.transformer_code:
                raise ValueError("变压器编码不能为空")
            if not data.transformer_name:
                raise ValueError("变压器名称不能为空")
            if data.rated_capacity is None or data.rated_capacity <= 0:
                raise ValueError("变压器额定容量必须大于0")

            node = Transformer(
                transformer_code=data.transformer_code,
                transformer_name=data.transformer_name,
                rated_capacity=data.rated_capacity,
                voltage_high=data.voltage_high or 10.0,
                voltage_low=data.voltage_low or 0.4,
                status="normal",
                is_enabled=True,
                created_at=now,
                updated_at=now
            )
            db.add(node)
            await db.flush()
            return node.id, "transformer"

        elif data.node_type == TopologyNodeType.METER_POINT:
            # 验证必填字段
            if not data.meter_code:
                raise ValueError("计量点编码不能为空")
            if not data.meter_name:
                raise ValueError("计量点名称不能为空")

            node = MeterPoint(
                meter_code=data.meter_code,
                meter_name=data.meter_name,
                ct_ratio=str(data.ct_ratio) if data.ct_ratio else "1",
                pt_ratio=str(data.pt_ratio) if data.pt_ratio else "1",
                transformer_id=data.parent_id,
                status="normal",
                is_enabled=True,
                created_at=now,
                updated_at=now
            )
            db.add(node)
            await db.flush()
            return node.id, "meter_point"

        elif data.node_type == TopologyNodeType.PANEL:
            # 验证必填字段
            if not data.panel_code:
                raise ValueError("配电柜编码不能为空")
            if not data.panel_name:
                raise ValueError("配电柜名称不能为空")

            node = DistributionPanel(
                panel_code=data.panel_code,
                panel_name=data.panel_name,
                panel_type=data.panel_type or "distribution",
                meter_point_id=data.parent_id if data.parent_type == TopologyNodeType.METER_POINT else None,
                parent_panel_id=data.parent_id if data.parent_type == TopologyNodeType.PANEL else None,
                status="normal",
                is_enabled=True,
                created_at=now,
                updated_at=now
            )
            db.add(node)
            await db.flush()
            return node.id, "panel"

        elif data.node_type == TopologyNodeType.CIRCUIT:
            # 验证必填字段
            if not data.circuit_code:
                raise ValueError("回路编码不能为空")
            if not data.circuit_name:
                raise ValueError("回路名称不能为空")
            # 回路必须属于一个配电柜
            if data.parent_id is None:
                raise ValueError("创建回路必须指定所属配电柜(parent_id)")
            # 验证配电柜是否存在
            panel_result = await db.execute(
                select(DistributionPanel).where(DistributionPanel.id == data.parent_id)
            )
            if not panel_result.scalar_one_or_none():
                raise ValueError(f"配电柜不存在: ID={data.parent_id}")

            node = DistributionCircuit(
                circuit_code=data.circuit_code,
                circuit_name=data.circuit_name,
                load_type=data.circuit_type or "general",
                rated_current=data.rated_current,
                panel_id=data.parent_id,
                is_shiftable=False,
                shift_priority=99,
                is_enabled=True,
                created_at=now,
                updated_at=now
            )
            db.add(node)
            await db.flush()
            return node.id, "circuit"

        elif data.node_type == TopologyNodeType.DEVICE:
            # 验证必填字段
            if not data.device_code:
                raise ValueError("设备编码不能为空")
            if not data.device_name:
                raise ValueError("设备名称不能为空")

            node = PowerDevice(
                device_code=data.device_code,
                device_name=data.device_name,
                device_type=data.device_type or "OTHER",
                rated_power=data.rated_power,
                circuit_id=data.parent_id,
                phase_type="3P",
                power_factor=0.9,
                is_metered=True,
                is_it_load=False,
                is_critical=False,
                is_enabled=True,
                created_at=now,
                updated_at=now
            )
            db.add(node)
            await db.flush()
            return node.id, "device"

        elif data.node_type == TopologyNodeType.POINT:
            # 验证必填字段
            if not data.point_code:
                raise ValueError("点位编码不能为空")
            if not data.point_name:
                raise ValueError("点位名称不能为空")

            # 获取父设备类型
            device_type = "IT"  # 默认为IT设备
            area_code = ""  # 默认空区域
            if data.parent_id:
                parent_device = await db.execute(
                    select(PowerDevice).where(PowerDevice.id == data.parent_id)
                )
                parent = parent_device.scalar_one_or_none()
                if parent:
                    if parent.device_type:
                        device_type = parent.device_type
                    if parent.area_code:
                        area_code = parent.area_code

            node = Point(
                point_code=data.point_code,
                point_name=data.point_name,
                point_type=data.point_type or "AI",
                device_type=device_type,
                area_code=area_code,
                energy_device_id=data.parent_id,
                register_address=data.register_address,
                data_type=data.data_type or "float",
                scale_factor=data.scale_factor or 1.0,
                unit=data.measurement_type or "",
                is_enabled=True,
                created_at=now,
                updated_at=now
            )
            db.add(node)
            await db.flush()
            return node.id, "point"

        raise ValueError(f"不支持的节点类型: {data.node_type}")

    @staticmethod
    async def update_node(
        db: AsyncSession,
        data: TopologyNodeUpdate
    ) -> bool:
        """
        更新拓扑节点

        Args:
            db: 数据库会话
            data: 更新数据

        Returns:
            是否成功
        """
        now = datetime.now()

        if data.node_type == TopologyNodeType.TRANSFORMER:
            result = await db.execute(
                select(Transformer).where(Transformer.id == data.node_id)
            )
            node = result.scalar_one_or_none()
            if not node:
                return False

            if data.name is not None:
                node.transformer_name = data.name
            if data.code is not None:
                node.transformer_code = data.code
            if data.status is not None:
                node.status = data.status
            if data.is_enabled is not None:
                node.is_enabled = data.is_enabled
            if data.location is not None:
                node.location = data.location
            if data.rated_capacity is not None:
                node.rated_capacity = data.rated_capacity
            if data.voltage_high is not None:
                node.voltage_high = data.voltage_high
            if data.voltage_low is not None:
                node.voltage_low = data.voltage_low
            if data.declared_demand is not None:
                node.declared_demand = data.declared_demand
            node.updated_at = now

        elif data.node_type == TopologyNodeType.METER_POINT:
            result = await db.execute(
                select(MeterPoint).where(MeterPoint.id == data.node_id)
            )
            node = result.scalar_one_or_none()
            if not node:
                return False

            if data.name is not None:
                node.meter_name = data.name
            if data.code is not None:
                node.meter_code = data.code
            if data.status is not None:
                node.status = data.status
            if data.is_enabled is not None:
                node.is_enabled = data.is_enabled
            if data.ct_ratio is not None:
                node.ct_ratio = data.ct_ratio
            if data.pt_ratio is not None:
                node.pt_ratio = data.pt_ratio
            if data.declared_demand is not None:
                node.declared_demand = data.declared_demand
            if data.remark is not None:
                node.remark = data.remark
            node.updated_at = now

        elif data.node_type == TopologyNodeType.PANEL:
            result = await db.execute(
                select(DistributionPanel).where(DistributionPanel.id == data.node_id)
            )
            node = result.scalar_one_or_none()
            if not node:
                return False

            if data.name is not None:
                node.panel_name = data.name
            if data.code is not None:
                node.panel_code = data.code
            if data.status is not None:
                node.status = data.status
            if data.is_enabled is not None:
                node.is_enabled = data.is_enabled
            if data.location is not None:
                node.location = data.location
            if data.remark is not None:
                node.remark = data.remark
            node.updated_at = now

        elif data.node_type == TopologyNodeType.CIRCUIT:
            result = await db.execute(
                select(DistributionCircuit).where(DistributionCircuit.id == data.node_id)
            )
            node = result.scalar_one_or_none()
            if not node:
                return False

            if data.name is not None:
                node.circuit_name = data.name
            if data.code is not None:
                node.circuit_code = data.code
            if data.is_enabled is not None:
                node.is_enabled = data.is_enabled
            if data.rated_current is not None:
                node.rated_current = data.rated_current
            if data.remark is not None:
                node.remark = data.remark
            node.updated_at = now

        elif data.node_type == TopologyNodeType.DEVICE:
            result = await db.execute(
                select(PowerDevice).where(PowerDevice.id == data.node_id)
            )
            node = result.scalar_one_or_none()
            if not node:
                return False

            if data.name is not None:
                node.device_name = data.name
            if data.code is not None:
                node.device_code = data.code
            if data.is_enabled is not None:
                node.is_enabled = data.is_enabled
            if data.rated_power is not None:
                node.rated_power = data.rated_power
            if data.remark is not None:
                node.remark = data.remark
            node.updated_at = now

        elif data.node_type == TopologyNodeType.POINT:
            result = await db.execute(
                select(Point).where(Point.id == data.node_id)
            )
            node = result.scalar_one_or_none()
            if not node:
                return False

            if data.name is not None:
                node.point_name = data.name
            if data.code is not None:
                node.point_code = data.code
            if data.is_enabled is not None:
                node.is_enabled = data.is_enabled
            node.updated_at = now

        else:
            return False

        return True

    @staticmethod
    async def delete_node(
        db: AsyncSession,
        data: TopologyNodeDelete,
        cascade: bool = False
    ) -> Dict[str, int]:
        """
        删除拓扑节点

        Args:
            db: 数据库会话
            data: 删除数据
            cascade: 是否级联删除子节点

        Returns:
            删除统计 {node_type: count}
        """
        deleted = {}

        if data.node_type == TopologyNodeType.TRANSFORMER:
            if cascade:
                # 获取下级计量点并级联删除
                result = await db.execute(
                    select(MeterPoint).where(MeterPoint.transformer_id == data.node_id)
                )
                meter_points = result.scalars().all()
                for mp in meter_points:
                    sub_deleted = await EnergyTopologyService.delete_node(
                        db,
                        TopologyNodeDelete(
                            node_id=mp.id,
                            node_type=TopologyNodeType.METER_POINT,
                            cascade=True
                        ),
                        cascade=True
                    )
                    for k, v in sub_deleted.items():
                        deleted[k] = deleted.get(k, 0) + v
                deleted["meter_points"] = len(meter_points)
                await db.execute(
                    delete(MeterPoint).where(MeterPoint.transformer_id == data.node_id)
                )

            await db.execute(
                delete(Transformer).where(Transformer.id == data.node_id)
            )
            deleted["transformers"] = 1

        elif data.node_type == TopologyNodeType.METER_POINT:
            if cascade:
                result = await db.execute(
                    select(DistributionPanel).where(DistributionPanel.meter_point_id == data.node_id)
                )
                panels = result.scalars().all()
                for panel in panels:
                    sub_deleted = await EnergyTopologyService.delete_node(
                        db,
                        TopologyNodeDelete(
                            node_id=panel.id,
                            node_type=TopologyNodeType.PANEL,
                            cascade=True
                        ),
                        cascade=True
                    )
                    for k, v in sub_deleted.items():
                        deleted[k] = deleted.get(k, 0) + v
                deleted["panels"] = deleted.get("panels", 0) + len(panels)
                await db.execute(
                    delete(DistributionPanel).where(DistributionPanel.meter_point_id == data.node_id)
                )

            await db.execute(
                delete(MeterPoint).where(MeterPoint.id == data.node_id)
            )
            deleted["meter_points"] = deleted.get("meter_points", 0) + 1

        elif data.node_type == TopologyNodeType.PANEL:
            if cascade:
                # 删除子配电柜
                result = await db.execute(
                    select(DistributionPanel).where(DistributionPanel.parent_panel_id == data.node_id)
                )
                sub_panels = result.scalars().all()
                for sub_panel in sub_panels:
                    sub_deleted = await EnergyTopologyService.delete_node(
                        db,
                        TopologyNodeDelete(
                            node_id=sub_panel.id,
                            node_type=TopologyNodeType.PANEL,
                            cascade=True
                        ),
                        cascade=True
                    )
                    for k, v in sub_deleted.items():
                        deleted[k] = deleted.get(k, 0) + v

                # 删除回路
                result = await db.execute(
                    select(DistributionCircuit).where(DistributionCircuit.panel_id == data.node_id)
                )
                circuits = result.scalars().all()
                for circuit in circuits:
                    sub_deleted = await EnergyTopologyService.delete_node(
                        db,
                        TopologyNodeDelete(
                            node_id=circuit.id,
                            node_type=TopologyNodeType.CIRCUIT,
                            cascade=True
                        ),
                        cascade=True
                    )
                    for k, v in sub_deleted.items():
                        deleted[k] = deleted.get(k, 0) + v
                deleted["circuits"] = deleted.get("circuits", 0) + len(circuits)
                await db.execute(
                    delete(DistributionCircuit).where(DistributionCircuit.panel_id == data.node_id)
                )

            await db.execute(
                delete(DistributionPanel).where(DistributionPanel.id == data.node_id)
            )
            deleted["panels"] = deleted.get("panels", 0) + 1

        elif data.node_type == TopologyNodeType.CIRCUIT:
            if cascade:
                result = await db.execute(
                    select(PowerDevice).where(PowerDevice.circuit_id == data.node_id)
                )
                devices = result.scalars().all()
                deleted["devices"] = len(devices)
                await db.execute(
                    delete(PowerDevice).where(PowerDevice.circuit_id == data.node_id)
                )

            await db.execute(
                delete(DistributionCircuit).where(DistributionCircuit.id == data.node_id)
            )
            deleted["circuits"] = deleted.get("circuits", 0) + 1

        elif data.node_type == TopologyNodeType.DEVICE:
            await db.execute(
                delete(PowerDevice).where(PowerDevice.id == data.node_id)
            )
            deleted["devices"] = deleted.get("devices", 0) + 1

        elif data.node_type == TopologyNodeType.POINT:
            await db.execute(
                delete(Point).where(Point.id == data.node_id)
            )
            deleted["points"] = deleted.get("points", 0) + 1

        return deleted

    @staticmethod
    async def batch_operation(
        db: AsyncSession,
        data: TopologyBatchOperation
    ) -> TopologyBatchResult:
        """
        批量拓扑操作

        Args:
            db: 数据库会话
            data: 批量操作数据

        Returns:
            操作结果
        """
        result = TopologyBatchResult(
            success=True,
            created_count=0,
            updated_count=0,
            deleted_count=0,
            errors=[],
            created_ids={}
        )

        # 执行创建操作
        for i, create_data in enumerate(data.creates):
            try:
                node_id, node_type = await EnergyTopologyService.create_node(db, create_data)
                result.created_count += 1
                result.created_ids[f"create_{i}"] = node_id
            except Exception as e:
                result.errors.append(f"创建节点失败 [{i}]: {str(e)}")
                result.success = False

        # 执行更新操作
        for i, update_data in enumerate(data.updates):
            try:
                success = await EnergyTopologyService.update_node(db, update_data)
                if success:
                    result.updated_count += 1
                else:
                    result.errors.append(f"更新节点未找到 [{update_data.node_type}:{update_data.node_id}]")
            except Exception as e:
                result.errors.append(f"更新节点失败 [{i}]: {str(e)}")
                result.success = False

        # 执行删除操作
        for i, delete_data in enumerate(data.deletes):
            try:
                deleted = await EnergyTopologyService.delete_node(
                    db, delete_data, cascade=delete_data.cascade
                )
                result.deleted_count += sum(deleted.values())
            except Exception as e:
                result.errors.append(f"删除节点失败 [{i}]: {str(e)}")
                result.success = False

        # 提交事务
        if result.success:
            await db.commit()
        else:
            await db.rollback()

        return result

    @staticmethod
    async def export_topology(db: AsyncSession) -> TopologyExport:
        """
        导出拓扑数据

        Args:
            db: 数据库会话

        Returns:
            导出数据
        """
        # 获取所有数据
        transformers_result = await db.execute(select(Transformer))
        transformers = transformers_result.scalars().all()

        meter_points_result = await db.execute(select(MeterPoint))
        meter_points = meter_points_result.scalars().all()

        panels_result = await db.execute(select(DistributionPanel))
        panels = panels_result.scalars().all()

        circuits_result = await db.execute(select(DistributionCircuit))
        circuits = circuits_result.scalars().all()

        devices_result = await db.execute(select(PowerDevice))
        devices = devices_result.scalars().all()

        # 构建导出数据
        export_data = TopologyExport(
            version="1.0",
            export_time=datetime.now(),
            transformers=[{
                "id": t.id,
                "code": t.transformer_code,
                "name": t.transformer_name,
                "rated_capacity": t.rated_capacity,
                "voltage_high": t.voltage_high,
                "voltage_low": t.voltage_low,
                "location": t.location,
                "status": t.status,
                "is_enabled": t.is_enabled
            } for t in transformers],
            meter_points=[{
                "id": mp.id,
                "code": mp.meter_code,
                "name": mp.meter_name,
                "transformer_id": mp.transformer_id,
                "ct_ratio": mp.ct_ratio,
                "pt_ratio": mp.pt_ratio,
                "status": mp.status,
                "is_enabled": mp.is_enabled
            } for mp in meter_points],
            panels=[{
                "id": p.id,
                "code": p.panel_code,
                "name": p.panel_name,
                "panel_type": p.panel_type,
                "meter_point_id": p.meter_point_id,
                "parent_panel_id": p.parent_panel_id,
                "status": p.status,
                "is_enabled": p.is_enabled
            } for p in panels],
            circuits=[{
                "id": c.id,
                "code": c.circuit_code,
                "name": c.circuit_name,
                "load_type": c.load_type,
                "panel_id": c.panel_id,
                "rated_current": c.rated_current,
                "is_enabled": c.is_enabled
            } for c in circuits],
            devices=[{
                "id": d.id,
                "code": d.device_code,
                "name": d.device_name,
                "device_type": d.device_type,
                "circuit_id": d.circuit_id,
                "rated_power": d.rated_power,
                "is_enabled": d.is_enabled
            } for d in devices],
            connections=[]  # 连接关系通过外键体现
        )

        return export_data

    @staticmethod
    async def import_topology(
        db: AsyncSession,
        data: TopologyImport
    ) -> TopologyBatchResult:
        """
        导入拓扑数据

        Args:
            db: 数据库会话
            data: 导入数据

        Returns:
            导入结果
        """
        result = TopologyBatchResult(
            success=True,
            created_count=0,
            errors=[],
            created_ids={}
        )

        # ID映射（旧ID -> 新ID）
        id_map = {
            "transformer": {},
            "meter_point": {},
            "panel": {},
            "circuit": {},
            "device": {}
        }

        try:
            if data.clear_existing:
                # 清除现有数据（按依赖顺序）
                await db.execute(delete(PowerDevice))
                await db.execute(delete(DistributionCircuit))
                await db.execute(delete(DistributionPanel))
                await db.execute(delete(MeterPoint))
                await db.execute(delete(Transformer))

            now = datetime.now()

            # 导入变压器
            for t in data.transformers:
                node = Transformer(
                    transformer_code=t.get("code"),
                    transformer_name=t.get("name"),
                    rated_capacity=t.get("rated_capacity"),
                    voltage_high=t.get("voltage_high"),
                    voltage_low=t.get("voltage_low"),
                    location=t.get("location"),
                    status=t.get("status", "normal"),
                    is_enabled=t.get("is_enabled", True),
                    created_at=now,
                    updated_at=now
                )
                db.add(node)
                await db.flush()
                id_map["transformer"][t.get("id")] = node.id
                result.created_count += 1

            # 导入计量点
            for mp in data.meter_points:
                old_transformer_id = mp.get("transformer_id")
                new_transformer_id = id_map["transformer"].get(old_transformer_id)
                node = MeterPoint(
                    meter_code=mp.get("code"),
                    meter_name=mp.get("name"),
                    transformer_id=new_transformer_id,
                    ct_ratio=str(mp.get("ct_ratio", 1)),
                    pt_ratio=str(mp.get("pt_ratio", 1)),
                    status=mp.get("status", "normal"),
                    is_enabled=mp.get("is_enabled", True),
                    created_at=now,
                    updated_at=now
                )
                db.add(node)
                await db.flush()
                id_map["meter_point"][mp.get("id")] = node.id
                result.created_count += 1

            # 导入配电柜（需要两次遍历处理父子关系）
            for p in data.panels:
                old_mp_id = p.get("meter_point_id")
                new_mp_id = id_map["meter_point"].get(old_mp_id)
                node = DistributionPanel(
                    panel_code=p.get("code"),
                    panel_name=p.get("name"),
                    panel_type=p.get("panel_type", "distribution"),
                    meter_point_id=new_mp_id,
                    parent_panel_id=None,  # 先设为空，后面再更新
                    status=p.get("status", "normal"),
                    is_enabled=p.get("is_enabled", True),
                    created_at=now,
                    updated_at=now
                )
                db.add(node)
                await db.flush()
                id_map["panel"][p.get("id")] = node.id
                result.created_count += 1

            # 更新配电柜父子关系
            for p in data.panels:
                old_parent_id = p.get("parent_panel_id")
                if old_parent_id:
                    new_parent_id = id_map["panel"].get(old_parent_id)
                    new_id = id_map["panel"].get(p.get("id"))
                    if new_id and new_parent_id:
                        panel_result = await db.execute(
                            select(DistributionPanel).where(DistributionPanel.id == new_id)
                        )
                        panel = panel_result.scalar_one_or_none()
                        if panel:
                            panel.parent_panel_id = new_parent_id

            # 导入回路
            for c in data.circuits:
                old_panel_id = c.get("panel_id")
                new_panel_id = id_map["panel"].get(old_panel_id)
                node = DistributionCircuit(
                    circuit_code=c.get("code"),
                    circuit_name=c.get("name"),
                    load_type=c.get("load_type", "general"),
                    panel_id=new_panel_id,
                    rated_current=c.get("rated_current"),
                    is_enabled=c.get("is_enabled", True),
                    created_at=now,
                    updated_at=now
                )
                db.add(node)
                await db.flush()
                id_map["circuit"][c.get("id")] = node.id
                result.created_count += 1

            # 导入设备
            for d in data.devices:
                old_circuit_id = d.get("circuit_id")
                new_circuit_id = id_map["circuit"].get(old_circuit_id)
                node = PowerDevice(
                    device_code=d.get("code"),
                    device_name=d.get("name"),
                    device_type=d.get("device_type", "general"),
                    circuit_id=new_circuit_id,
                    rated_power=d.get("rated_power"),
                    is_enabled=d.get("is_enabled", True),
                    created_at=now,
                    updated_at=now
                )
                db.add(node)
                await db.flush()
                id_map["device"][d.get("id")] = node.id
                result.created_count += 1

            await db.commit()
            result.created_ids = {
                f"{k}_map": v for k, v in id_map.items()
            }

        except Exception as e:
            await db.rollback()
            result.success = False
            result.errors.append(str(e))

        return result

    @staticmethod
    async def get_node_by_id(
        db: AsyncSession,
        node_type: TopologyNodeType,
        node_id: int
    ) -> Optional[Any]:
        """
        根据类型和ID获取节点

        Args:
            db: 数据库会话
            node_type: 节点类型
            node_id: 节点ID

        Returns:
            节点对象或None
        """
        model_map = {
            TopologyNodeType.TRANSFORMER: Transformer,
            TopologyNodeType.METER_POINT: MeterPoint,
            TopologyNodeType.PANEL: DistributionPanel,
            TopologyNodeType.CIRCUIT: DistributionCircuit,
            TopologyNodeType.DEVICE: PowerDevice
        }

        model = model_map.get(node_type)
        if not model:
            return None

        result = await db.execute(
            select(model).where(model.id == node_id)
        )
        return result.scalar_one_or_none()


# 单例服务实例
topology_service = EnergyTopologyService()
