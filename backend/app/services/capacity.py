"""
容量管理服务
Capacity Management Service

提供空间、电力、制冷、承重容量管理及容量规划功能
"""
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..models.capacity import (
    SpaceCapacity, PowerCapacity, CoolingCapacity, WeightCapacity,
    CapacityPlan, CapacityStatus
)
from ..schemas.capacity import (
    SpaceCapacityCreate, SpaceCapacityUpdate,
    PowerCapacityCreate, PowerCapacityUpdate,
    CoolingCapacityCreate, CoolingCapacityUpdate,
    WeightCapacityCreate, WeightCapacityUpdate,
    CapacityPlanCreate
)


class CapacityService:
    """容量管理服务"""

    # ==================== 辅助方法 ====================

    def _calculate_status(
        self,
        used: float,
        total: float,
        warning: float,
        critical: float
    ) -> CapacityStatus:
        """
        根据使用率计算容量状态

        Args:
            used: 已用量
            total: 总量
            warning: 警告阈值(%)
            critical: 严重阈值(%)

        Returns:
            容量状态枚举值
        """
        if total <= 0:
            return CapacityStatus.normal

        rate = used / total * 100

        if rate >= 100:
            return CapacityStatus.full
        elif rate >= critical:
            return CapacityStatus.critical
        elif rate >= warning:
            return CapacityStatus.warning

        return CapacityStatus.normal

    def _evaluate_feasibility(
        self,
        db: Session,
        plan: CapacityPlan
    ) -> Tuple[bool, str]:
        """
        评估容量规划的可行性

        Args:
            db: 数据库会话
            plan: 容量规划对象

        Returns:
            (是否可行, 可行性说明)
        """
        notes = []
        is_feasible = True

        # 检查空间容量（U位）
        if plan.required_u:
            space_capacities = db.query(SpaceCapacity).all()
            total_available_u = sum(
                (sc.total_u_positions or 0) - (sc.used_u_positions or 0)
                for sc in space_capacities
            )
            if total_available_u >= plan.required_u:
                notes.append(f"空间容量检查通过: 可用U位 {total_available_u}U >= 所需 {plan.required_u}U")
            else:
                notes.append(f"空间容量不足: 可用U位 {total_available_u}U < 所需 {plan.required_u}U")
                is_feasible = False

        # 检查电力容量
        if plan.required_power_kw:
            power_capacities = db.query(PowerCapacity).all()
            total_available_power = sum(
                (pc.total_capacity_kw or 0) - (pc.used_capacity_kw or 0)
                for pc in power_capacities
            )
            if total_available_power >= plan.required_power_kw:
                notes.append(f"电力容量检查通过: 可用电力 {total_available_power:.2f}kW >= 所需 {plan.required_power_kw:.2f}kW")
            else:
                notes.append(f"电力容量不足: 可用电力 {total_available_power:.2f}kW < 所需 {plan.required_power_kw:.2f}kW")
                is_feasible = False

        # 检查制冷容量
        if plan.required_cooling_kw:
            cooling_capacities = db.query(CoolingCapacity).all()
            total_available_cooling = sum(
                (cc.total_cooling_kw or 0) - (cc.used_cooling_kw or 0)
                for cc in cooling_capacities
            )
            if total_available_cooling >= plan.required_cooling_kw:
                notes.append(f"制冷容量检查通过: 可用制冷 {total_available_cooling:.2f}kW >= 所需 {plan.required_cooling_kw:.2f}kW")
            else:
                notes.append(f"制冷容量不足: 可用制冷 {total_available_cooling:.2f}kW < 所需 {plan.required_cooling_kw:.2f}kW")
                is_feasible = False

        # 检查承重容量
        if plan.required_weight_kg:
            weight_capacities = db.query(WeightCapacity).all()
            total_available_weight = sum(
                (wc.total_weight_kg or 0) - (wc.used_weight_kg or 0)
                for wc in weight_capacities
            )
            if total_available_weight >= plan.required_weight_kg:
                notes.append(f"承重容量检查通过: 可用承重 {total_available_weight:.2f}kg >= 所需 {plan.required_weight_kg:.2f}kg")
            else:
                notes.append(f"承重容量不足: 可用承重 {total_available_weight:.2f}kg < 所需 {plan.required_weight_kg:.2f}kg")
                is_feasible = False

        if not notes:
            notes.append("无容量需求，规划可行")

        return is_feasible, "\n".join(notes)

    # ==================== 空间容量管理 ====================

    def get_space_capacities(
        self,
        db: Session,
        skip: int = 0,
        limit: int = 100
    ) -> List[SpaceCapacity]:
        """
        获取空间容量列表

        Args:
            db: 数据库会话
            skip: 跳过记录数
            limit: 返回记录数

        Returns:
            空间容量列表
        """
        return db.query(SpaceCapacity).offset(skip).limit(limit).all()

    def get_space_capacity(
        self,
        db: Session,
        capacity_id: int
    ) -> Optional[SpaceCapacity]:
        """
        根据ID获取空间容量

        Args:
            db: 数据库会话
            capacity_id: 容量ID

        Returns:
            空间容量对象或None
        """
        return db.query(SpaceCapacity).filter(SpaceCapacity.id == capacity_id).first()

    def create_space_capacity(
        self,
        db: Session,
        data: SpaceCapacityCreate
    ) -> SpaceCapacity:
        """
        创建空间容量

        Args:
            db: 数据库会话
            data: 空间容量创建数据

        Returns:
            创建的空间容量对象
        """
        capacity = SpaceCapacity(**data.model_dump())

        # 计算状态 - 基于U位使用率
        used = data.used_u_positions or 0
        total = data.total_u_positions or 0
        warning = data.warning_threshold or 80
        critical = data.critical_threshold or 95
        capacity.status = self._calculate_status(used, total, warning, critical)

        db.add(capacity)
        db.commit()
        db.refresh(capacity)
        return capacity

    def update_space_capacity(
        self,
        db: Session,
        capacity_id: int,
        data: SpaceCapacityUpdate
    ) -> Optional[SpaceCapacity]:
        """
        更新空间容量

        Args:
            db: 数据库会话
            capacity_id: 容量ID
            data: 更新数据

        Returns:
            更新后的空间容量对象或None
        """
        capacity = self.get_space_capacity(db, capacity_id)
        if not capacity:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if value is not None:
                setattr(capacity, key, value)

        # 重新计算状态
        used = capacity.used_u_positions or 0
        total = capacity.total_u_positions or 0
        warning = capacity.warning_threshold or 80
        critical = capacity.critical_threshold or 95
        capacity.status = self._calculate_status(used, total, warning, critical)

        capacity.updated_at = datetime.now()
        db.commit()
        db.refresh(capacity)
        return capacity

    def delete_space_capacity(
        self,
        db: Session,
        capacity_id: int
    ) -> bool:
        """
        删除空间容量

        Args:
            db: 数据库会话
            capacity_id: 容量ID

        Returns:
            是否删除成功
        """
        capacity = self.get_space_capacity(db, capacity_id)
        if not capacity:
            return False

        db.delete(capacity)
        db.commit()
        return True

    # ==================== 电力容量管理 ====================

    def get_power_capacities(
        self,
        db: Session,
        skip: int = 0,
        limit: int = 100
    ) -> List[PowerCapacity]:
        """
        获取电力容量列表

        Args:
            db: 数据库会话
            skip: 跳过记录数
            limit: 返回记录数

        Returns:
            电力容量列表
        """
        return db.query(PowerCapacity).offset(skip).limit(limit).all()

    def get_power_capacity(
        self,
        db: Session,
        capacity_id: int
    ) -> Optional[PowerCapacity]:
        """
        根据ID获取电力容量

        Args:
            db: 数据库会话
            capacity_id: 容量ID

        Returns:
            电力容量对象或None
        """
        return db.query(PowerCapacity).filter(PowerCapacity.id == capacity_id).first()

    def create_power_capacity(
        self,
        db: Session,
        data: PowerCapacityCreate
    ) -> PowerCapacity:
        """
        创建电力容量

        Args:
            db: 数据库会话
            data: 电力容量创建数据

        Returns:
            创建的电力容量对象
        """
        capacity = PowerCapacity(**data.model_dump())

        # 计算状态 - 基于kW使用率
        used = data.used_capacity_kw or 0
        total = data.total_capacity_kw or 0
        warning = data.warning_threshold or 70
        critical = data.critical_threshold or 85
        capacity.status = self._calculate_status(used, total, warning, critical)

        db.add(capacity)
        db.commit()
        db.refresh(capacity)
        return capacity

    def update_power_capacity(
        self,
        db: Session,
        capacity_id: int,
        data: PowerCapacityUpdate
    ) -> Optional[PowerCapacity]:
        """
        更新电力容量

        Args:
            db: 数据库会话
            capacity_id: 容量ID
            data: 更新数据

        Returns:
            更新后的电力容量对象或None
        """
        capacity = self.get_power_capacity(db, capacity_id)
        if not capacity:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if value is not None:
                setattr(capacity, key, value)

        # 重新计算状态
        used = capacity.used_capacity_kw or 0
        total = capacity.total_capacity_kw or 0
        warning = capacity.warning_threshold or 70
        critical = capacity.critical_threshold or 85
        capacity.status = self._calculate_status(used, total, warning, critical)

        capacity.updated_at = datetime.now()
        db.commit()
        db.refresh(capacity)
        return capacity

    def delete_power_capacity(
        self,
        db: Session,
        capacity_id: int
    ) -> bool:
        """
        删除电力容量

        Args:
            db: 数据库会话
            capacity_id: 容量ID

        Returns:
            是否删除成功
        """
        capacity = self.get_power_capacity(db, capacity_id)
        if not capacity:
            return False

        db.delete(capacity)
        db.commit()
        return True

    # ==================== 制冷容量管理 ====================

    def get_cooling_capacities(
        self,
        db: Session,
        skip: int = 0,
        limit: int = 100
    ) -> List[CoolingCapacity]:
        """
        获取制冷容量列表

        Args:
            db: 数据库会话
            skip: 跳过记录数
            limit: 返回记录数

        Returns:
            制冷容量列表
        """
        return db.query(CoolingCapacity).offset(skip).limit(limit).all()

    def get_cooling_capacity(
        self,
        db: Session,
        capacity_id: int
    ) -> Optional[CoolingCapacity]:
        """
        根据ID获取制冷容量

        Args:
            db: 数据库会话
            capacity_id: 容量ID

        Returns:
            制冷容量对象或None
        """
        return db.query(CoolingCapacity).filter(CoolingCapacity.id == capacity_id).first()

    def create_cooling_capacity(
        self,
        db: Session,
        data: CoolingCapacityCreate
    ) -> CoolingCapacity:
        """
        创建制冷容量

        Args:
            db: 数据库会话
            data: 制冷容量创建数据

        Returns:
            创建的制冷容量对象
        """
        capacity = CoolingCapacity(**data.model_dump())

        # 计算状态 - 基于制冷量使用率
        used = data.used_cooling_kw or 0
        total = data.total_cooling_kw or 0
        warning = data.warning_threshold or 75
        critical = data.critical_threshold or 90
        capacity.status = self._calculate_status(used, total, warning, critical)

        db.add(capacity)
        db.commit()
        db.refresh(capacity)
        return capacity

    def update_cooling_capacity(
        self,
        db: Session,
        capacity_id: int,
        data: CoolingCapacityUpdate
    ) -> Optional[CoolingCapacity]:
        """
        更新制冷容量

        Args:
            db: 数据库会话
            capacity_id: 容量ID
            data: 更新数据

        Returns:
            更新后的制冷容量对象或None
        """
        capacity = self.get_cooling_capacity(db, capacity_id)
        if not capacity:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if value is not None:
                setattr(capacity, key, value)

        # 重新计算状态
        used = capacity.used_cooling_kw or 0
        total = capacity.total_cooling_kw or 0
        warning = capacity.warning_threshold or 75
        critical = capacity.critical_threshold or 90
        capacity.status = self._calculate_status(used, total, warning, critical)

        capacity.updated_at = datetime.now()
        db.commit()
        db.refresh(capacity)
        return capacity

    def delete_cooling_capacity(
        self,
        db: Session,
        capacity_id: int
    ) -> bool:
        """
        删除制冷容量

        Args:
            db: 数据库会话
            capacity_id: 容量ID

        Returns:
            是否删除成功
        """
        capacity = self.get_cooling_capacity(db, capacity_id)
        if not capacity:
            return False

        db.delete(capacity)
        db.commit()
        return True

    # ==================== 承重容量管理 ====================

    def get_weight_capacities(
        self,
        db: Session,
        skip: int = 0,
        limit: int = 100
    ) -> List[WeightCapacity]:
        """
        获取承重容量列表

        Args:
            db: 数据库会话
            skip: 跳过记录数
            limit: 返回记录数

        Returns:
            承重容量列表
        """
        return db.query(WeightCapacity).offset(skip).limit(limit).all()

    def get_weight_capacity(
        self,
        db: Session,
        capacity_id: int
    ) -> Optional[WeightCapacity]:
        """
        根据ID获取承重容量

        Args:
            db: 数据库会话
            capacity_id: 容量ID

        Returns:
            承重容量对象或None
        """
        return db.query(WeightCapacity).filter(WeightCapacity.id == capacity_id).first()

    def create_weight_capacity(
        self,
        db: Session,
        data: WeightCapacityCreate
    ) -> WeightCapacity:
        """
        创建承重容量

        Args:
            db: 数据库会话
            data: 承重容量创建数据

        Returns:
            创建的承重容量对象
        """
        capacity = WeightCapacity(**data.model_dump())

        # 计算状态 - 基于承重使用率
        used = data.used_weight_kg or 0
        total = data.total_weight_kg or 0
        warning = data.warning_threshold or 80
        critical = data.critical_threshold or 95
        capacity.status = self._calculate_status(used, total, warning, critical)

        db.add(capacity)
        db.commit()
        db.refresh(capacity)
        return capacity

    def update_weight_capacity(
        self,
        db: Session,
        capacity_id: int,
        data: WeightCapacityUpdate
    ) -> Optional[WeightCapacity]:
        """
        更新承重容量

        Args:
            db: 数据库会话
            capacity_id: 容量ID
            data: 更新数据

        Returns:
            更新后的承重容量对象或None
        """
        capacity = self.get_weight_capacity(db, capacity_id)
        if not capacity:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if value is not None:
                setattr(capacity, key, value)

        # 重新计算状态
        used = capacity.used_weight_kg or 0
        total = capacity.total_weight_kg or 0
        warning = capacity.warning_threshold or 80
        critical = capacity.critical_threshold or 95
        capacity.status = self._calculate_status(used, total, warning, critical)

        capacity.updated_at = datetime.now()
        db.commit()
        db.refresh(capacity)
        return capacity

    def delete_weight_capacity(
        self,
        db: Session,
        capacity_id: int
    ) -> bool:
        """
        删除承重容量

        Args:
            db: 数据库会话
            capacity_id: 容量ID

        Returns:
            是否删除成功
        """
        capacity = self.get_weight_capacity(db, capacity_id)
        if not capacity:
            return False

        db.delete(capacity)
        db.commit()
        return True

    # ==================== 容量规划管理 ====================

    def get_capacity_plans(
        self,
        db: Session,
        skip: int = 0,
        limit: int = 100
    ) -> List[CapacityPlan]:
        """
        获取容量规划列表

        Args:
            db: 数据库会话
            skip: 跳过记录数
            limit: 返回记录数

        Returns:
            容量规划列表
        """
        return db.query(CapacityPlan).offset(skip).limit(limit).all()

    def get_capacity_plan(
        self,
        db: Session,
        plan_id: int
    ) -> Optional[CapacityPlan]:
        """
        根据ID获取容量规划

        Args:
            db: 数据库会话
            plan_id: 规划ID

        Returns:
            容量规划对象或None
        """
        return db.query(CapacityPlan).filter(CapacityPlan.id == plan_id).first()

    def create_capacity_plan(
        self,
        db: Session,
        data: CapacityPlanCreate
    ) -> CapacityPlan:
        """
        创建容量规划

        Args:
            db: 数据库会话
            data: 容量规划创建数据

        Returns:
            创建的容量规划对象
        """
        plan = CapacityPlan(**data.model_dump())
        db.add(plan)
        db.flush()  # 获取ID但不提交

        # 评估可行性
        is_feasible, notes = self._evaluate_feasibility(db, plan)
        plan.is_feasible = is_feasible
        plan.feasibility_notes = notes

        db.commit()
        db.refresh(plan)
        return plan

    def delete_capacity_plan(
        self,
        db: Session,
        plan_id: int
    ) -> bool:
        """
        删除容量规划

        Args:
            db: 数据库会话
            plan_id: 规划ID

        Returns:
            是否删除成功
        """
        plan = self.get_capacity_plan(db, plan_id)
        if not plan:
            return False

        db.delete(plan)
        db.commit()
        return True

    # ==================== 统计分析 ====================

    def get_statistics(self, db: Session) -> Dict[str, Any]:
        """
        获取容量统计信息

        Args:
            db: 数据库会话

        Returns:
            包含各类容量统计的字典
        """
        # 空间容量统计
        space_capacities = db.query(SpaceCapacity).all()
        total_u = sum(sc.total_u_positions or 0 for sc in space_capacities)
        used_u = sum(sc.used_u_positions or 0 for sc in space_capacities)
        space_stats = {
            "total_u_positions": total_u,
            "used_u_positions": used_u,
            "available_u_positions": total_u - used_u,
            "usage_rate": round(used_u / total_u * 100, 2) if total_u > 0 else 0,
            "count": len(space_capacities)
        }

        # 电力容量统计
        power_capacities = db.query(PowerCapacity).all()
        total_power = sum(pc.total_capacity_kw or 0 for pc in power_capacities)
        used_power = sum(pc.used_capacity_kw or 0 for pc in power_capacities)
        power_stats = {
            "total_capacity_kw": total_power,
            "used_capacity_kw": used_power,
            "available_capacity_kw": total_power - used_power,
            "usage_rate": round(used_power / total_power * 100, 2) if total_power > 0 else 0,
            "count": len(power_capacities)
        }

        # 制冷容量统计
        cooling_capacities = db.query(CoolingCapacity).all()
        total_cooling = sum(cc.total_cooling_kw or 0 for cc in cooling_capacities)
        used_cooling = sum(cc.used_cooling_kw or 0 for cc in cooling_capacities)
        cooling_stats = {
            "total_cooling_kw": total_cooling,
            "used_cooling_kw": used_cooling,
            "available_cooling_kw": total_cooling - used_cooling,
            "usage_rate": round(used_cooling / total_cooling * 100, 2) if total_cooling > 0 else 0,
            "count": len(cooling_capacities)
        }

        # 承重容量统计
        weight_capacities = db.query(WeightCapacity).all()
        total_weight = sum(wc.total_weight_kg or 0 for wc in weight_capacities)
        used_weight = sum(wc.used_weight_kg or 0 for wc in weight_capacities)
        weight_stats = {
            "total_weight_kg": total_weight,
            "used_weight_kg": used_weight,
            "available_weight_kg": total_weight - used_weight,
            "usage_rate": round(used_weight / total_weight * 100, 2) if total_weight > 0 else 0,
            "count": len(weight_capacities)
        }

        # 状态统计
        status_counts = {
            "normal": 0,
            "warning": 0,
            "critical": 0,
            "full": 0
        }

        for sc in space_capacities:
            if sc.status:
                status_counts[sc.status.value] = status_counts.get(sc.status.value, 0) + 1
        for pc in power_capacities:
            if pc.status:
                status_counts[pc.status.value] = status_counts.get(pc.status.value, 0) + 1
        for cc in cooling_capacities:
            if cc.status:
                status_counts[cc.status.value] = status_counts.get(cc.status.value, 0) + 1
        for wc in weight_capacities:
            if wc.status:
                status_counts[wc.status.value] = status_counts.get(wc.status.value, 0) + 1

        return {
            "space": space_stats,
            "power": power_stats,
            "cooling": cooling_stats,
            "weight": weight_stats,
            "status_summary": status_counts,
            "total_capacity_records": (
                len(space_capacities) + len(power_capacities) +
                len(cooling_capacities) + len(weight_capacities)
            )
        }


# 单例实例
capacity_service = CapacityService()
