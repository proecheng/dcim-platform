"""
配电系统配置服务
Energy Configuration Service

提供变压器、计量点、配电柜、配电回路的CRUD操作
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload

from ..models.energy import (
    Transformer, MeterPoint, DistributionPanel,
    DistributionCircuit, PowerDevice
)


class TransformerService:
    """变压器配置服务"""

    @staticmethod
    async def get_list(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
        is_enabled: Optional[bool] = None
    ) -> tuple[List[Transformer], int]:
        """获取变压器列表"""
        query = select(Transformer)
        count_query = select(func.count(Transformer.id))

        if status:
            query = query.where(Transformer.status == status)
            count_query = count_query.where(Transformer.status == status)
        if is_enabled is not None:
            query = query.where(Transformer.is_enabled == is_enabled)
            count_query = count_query.where(Transformer.is_enabled == is_enabled)

        # 获取总数
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # 获取分页数据
        query = query.order_by(Transformer.created_at.desc()).offset(skip).limit(limit)
        result = await db.execute(query)
        items = result.scalars().all()

        return list(items), total

    @staticmethod
    async def get_by_id(db: AsyncSession, transformer_id: int) -> Optional[Transformer]:
        """根据ID获取变压器"""
        result = await db.execute(
            select(Transformer)
            .options(selectinload(Transformer.meter_points))
            .where(Transformer.id == transformer_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_code(db: AsyncSession, code: str) -> Optional[Transformer]:
        """根据编码获取变压器"""
        result = await db.execute(
            select(Transformer).where(Transformer.transformer_code == code)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create(db: AsyncSession, data: Dict[str, Any]) -> Transformer:
        """创建变压器"""
        transformer = Transformer(**data)
        db.add(transformer)
        await db.commit()
        await db.refresh(transformer)
        return transformer

    @staticmethod
    async def update(
        db: AsyncSession,
        transformer_id: int,
        data: Dict[str, Any]
    ) -> Optional[Transformer]:
        """更新变压器"""
        transformer = await TransformerService.get_by_id(db, transformer_id)
        if not transformer:
            return None

        for key, value in data.items():
            if hasattr(transformer, key) and value is not None:
                setattr(transformer, key, value)

        transformer.updated_at = datetime.now()
        await db.commit()
        await db.refresh(transformer)
        return transformer

    @staticmethod
    async def delete(db: AsyncSession, transformer_id: int) -> bool:
        """删除变压器"""
        transformer = await TransformerService.get_by_id(db, transformer_id)
        if not transformer:
            return False

        # 检查是否有关联的计量点
        if transformer.meter_points and len(transformer.meter_points) > 0:
            raise ValueError("变压器下存在计量点，无法删除")

        await db.delete(transformer)
        await db.commit()
        return True


class MeterPointService:
    """计量点配置服务"""

    @staticmethod
    async def get_list(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        transformer_id: Optional[int] = None,
        status: Optional[str] = None,
        is_enabled: Optional[bool] = None
    ) -> tuple[List[MeterPoint], int]:
        """获取计量点列表"""
        query = select(MeterPoint).options(selectinload(MeterPoint.transformer))
        count_query = select(func.count(MeterPoint.id))

        conditions = []
        if transformer_id:
            conditions.append(MeterPoint.transformer_id == transformer_id)
        if status:
            conditions.append(MeterPoint.status == status)
        if is_enabled is not None:
            conditions.append(MeterPoint.is_enabled == is_enabled)

        if conditions:
            query = query.where(and_(*conditions))
            count_query = count_query.where(and_(*conditions))

        # 获取总数
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # 获取分页数据
        query = query.order_by(MeterPoint.created_at.desc()).offset(skip).limit(limit)
        result = await db.execute(query)
        items = result.scalars().all()

        return list(items), total

    @staticmethod
    async def get_by_id(db: AsyncSession, meter_point_id: int) -> Optional[MeterPoint]:
        """根据ID获取计量点"""
        result = await db.execute(
            select(MeterPoint)
            .options(
                selectinload(MeterPoint.transformer),
                selectinload(MeterPoint.panels)
            )
            .where(MeterPoint.id == meter_point_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_code(db: AsyncSession, code: str) -> Optional[MeterPoint]:
        """根据编码获取计量点"""
        result = await db.execute(
            select(MeterPoint).where(MeterPoint.meter_code == code)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create(db: AsyncSession, data: Dict[str, Any]) -> MeterPoint:
        """创建计量点"""
        meter_point = MeterPoint(**data)
        db.add(meter_point)
        await db.commit()
        await db.refresh(meter_point)
        return meter_point

    @staticmethod
    async def update(
        db: AsyncSession,
        meter_point_id: int,
        data: Dict[str, Any]
    ) -> Optional[MeterPoint]:
        """更新计量点"""
        meter_point = await MeterPointService.get_by_id(db, meter_point_id)
        if not meter_point:
            return None

        for key, value in data.items():
            if hasattr(meter_point, key) and value is not None:
                setattr(meter_point, key, value)

        meter_point.updated_at = datetime.now()
        await db.commit()
        await db.refresh(meter_point)
        return meter_point

    @staticmethod
    async def delete(db: AsyncSession, meter_point_id: int) -> bool:
        """删除计量点"""
        meter_point = await MeterPointService.get_by_id(db, meter_point_id)
        if not meter_point:
            return False

        # 检查是否有关联的配电柜
        if meter_point.panels and len(meter_point.panels) > 0:
            raise ValueError("计量点下存在配电柜，无法删除")

        await db.delete(meter_point)
        await db.commit()
        return True


class DistributionPanelService:
    """配电柜配置服务"""

    @staticmethod
    async def get_list(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        panel_type: Optional[str] = None,
        meter_point_id: Optional[int] = None,
        transformer_id: Optional[int] = None,
        parent_panel_id: Optional[int] = None,
        status: Optional[str] = None,
        is_enabled: Optional[bool] = None
    ) -> tuple[List[DistributionPanel], int]:
        """获取配电柜列表"""
        query = select(DistributionPanel).options(selectinload(DistributionPanel.meter_point))
        count_query = select(func.count(DistributionPanel.id))

        conditions = []
        if panel_type:
            conditions.append(DistributionPanel.panel_type == panel_type)
        if meter_point_id:
            conditions.append(DistributionPanel.meter_point_id == meter_point_id)
        if transformer_id:
            conditions.append(DistributionPanel.transformer_id == transformer_id)
        if parent_panel_id is not None:
            if parent_panel_id == 0:
                conditions.append(DistributionPanel.parent_panel_id.is_(None))
            else:
                conditions.append(DistributionPanel.parent_panel_id == parent_panel_id)
        if status:
            conditions.append(DistributionPanel.status == status)
        if is_enabled is not None:
            conditions.append(DistributionPanel.is_enabled == is_enabled)

        if conditions:
            query = query.where(and_(*conditions))
            count_query = count_query.where(and_(*conditions))

        # 获取总数
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # 获取分页数据
        query = query.order_by(DistributionPanel.created_at.desc()).offset(skip).limit(limit)
        result = await db.execute(query)
        items = result.scalars().all()

        return list(items), total

    @staticmethod
    async def get_by_id(db: AsyncSession, panel_id: int) -> Optional[DistributionPanel]:
        """根据ID获取配电柜"""
        result = await db.execute(
            select(DistributionPanel)
            .options(
                selectinload(DistributionPanel.meter_point),
                selectinload(DistributionPanel.circuits)
            )
            .where(DistributionPanel.id == panel_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_code(db: AsyncSession, code: str) -> Optional[DistributionPanel]:
        """根据编码获取配电柜"""
        result = await db.execute(
            select(DistributionPanel).where(DistributionPanel.panel_code == code)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create(db: AsyncSession, data: Dict[str, Any]) -> DistributionPanel:
        """创建配电柜"""
        panel = DistributionPanel(**data)
        db.add(panel)
        await db.commit()
        await db.refresh(panel)
        return panel

    @staticmethod
    async def update(
        db: AsyncSession,
        panel_id: int,
        data: Dict[str, Any]
    ) -> Optional[DistributionPanel]:
        """更新配电柜"""
        panel = await DistributionPanelService.get_by_id(db, panel_id)
        if not panel:
            return None

        for key, value in data.items():
            if hasattr(panel, key) and value is not None:
                setattr(panel, key, value)

        panel.updated_at = datetime.now()
        await db.commit()
        await db.refresh(panel)
        return panel

    @staticmethod
    async def delete(db: AsyncSession, panel_id: int) -> bool:
        """删除配电柜"""
        panel = await DistributionPanelService.get_by_id(db, panel_id)
        if not panel:
            return False

        # 检查是否有关联的回路
        if panel.circuits and len(panel.circuits) > 0:
            raise ValueError("配电柜下存在配电回路，无法删除")

        # 检查是否有下级配电柜
        sub_panels_result = await db.execute(
            select(func.count(DistributionPanel.id))
            .where(DistributionPanel.parent_panel_id == panel_id)
        )
        sub_count = sub_panels_result.scalar() or 0
        if sub_count > 0:
            raise ValueError("配电柜下存在下级配电柜，无法删除")

        await db.delete(panel)
        await db.commit()
        return True


class DistributionCircuitService:
    """配电回路配置服务"""

    @staticmethod
    async def get_list(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        panel_id: Optional[int] = None,
        load_type: Optional[str] = None,
        is_shiftable: Optional[bool] = None,
        is_enabled: Optional[bool] = None
    ) -> tuple[List[DistributionCircuit], int]:
        """获取配电回路列表"""
        query = select(DistributionCircuit).options(selectinload(DistributionCircuit.panel))
        count_query = select(func.count(DistributionCircuit.id))

        conditions = []
        if panel_id:
            conditions.append(DistributionCircuit.panel_id == panel_id)
        if load_type:
            conditions.append(DistributionCircuit.load_type == load_type)
        if is_shiftable is not None:
            conditions.append(DistributionCircuit.is_shiftable == is_shiftable)
        if is_enabled is not None:
            conditions.append(DistributionCircuit.is_enabled == is_enabled)

        if conditions:
            query = query.where(and_(*conditions))
            count_query = count_query.where(and_(*conditions))

        # 获取总数
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # 获取分页数据
        query = query.order_by(DistributionCircuit.created_at.desc()).offset(skip).limit(limit)
        result = await db.execute(query)
        items = result.scalars().all()

        return list(items), total

    @staticmethod
    async def get_by_id(db: AsyncSession, circuit_id: int) -> Optional[DistributionCircuit]:
        """根据ID获取配电回路"""
        result = await db.execute(
            select(DistributionCircuit)
            .options(
                selectinload(DistributionCircuit.panel),
                selectinload(DistributionCircuit.devices)
            )
            .where(DistributionCircuit.id == circuit_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_code(db: AsyncSession, code: str) -> Optional[DistributionCircuit]:
        """根据编码获取配电回路"""
        result = await db.execute(
            select(DistributionCircuit).where(DistributionCircuit.circuit_code == code)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create(db: AsyncSession, data: Dict[str, Any]) -> DistributionCircuit:
        """创建配电回路"""
        circuit = DistributionCircuit(**data)
        db.add(circuit)
        await db.commit()
        await db.refresh(circuit)
        return circuit

    @staticmethod
    async def update(
        db: AsyncSession,
        circuit_id: int,
        data: Dict[str, Any]
    ) -> Optional[DistributionCircuit]:
        """更新配电回路"""
        circuit = await DistributionCircuitService.get_by_id(db, circuit_id)
        if not circuit:
            return None

        for key, value in data.items():
            if hasattr(circuit, key) and value is not None:
                setattr(circuit, key, value)

        circuit.updated_at = datetime.now()
        await db.commit()
        await db.refresh(circuit)
        return circuit

    @staticmethod
    async def delete(db: AsyncSession, circuit_id: int) -> bool:
        """删除配电回路"""
        circuit = await DistributionCircuitService.get_by_id(db, circuit_id)
        if not circuit:
            return False

        # 检查是否有关联的设备
        if circuit.devices and len(circuit.devices) > 0:
            raise ValueError("配电回路下存在用电设备，无法删除")

        await db.delete(circuit)
        await db.commit()
        return True


# 单例服务实例
transformer_service = TransformerService()
meter_point_service = MeterPointService()
panel_service = DistributionPanelService()
circuit_service = DistributionCircuitService()
