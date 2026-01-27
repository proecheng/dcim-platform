"""
配电系统拓扑服务
Energy Topology Service

提供配电系统拓扑树构建和查询功能
"""
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..models.energy import (
    Transformer, MeterPoint, DistributionPanel,
    DistributionCircuit, PowerDevice
)
from ..models.point import Point, PointRealtime


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


# 单例服务实例
topology_service = EnergyTopologyService()
