# 容量管理与运维管理实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现容量管理和运维管理两大核心模块，使系统功能与行业DCIM标准对齐

**Architecture:**
- 后端采用FastAPI + SQLAlchemy，遵循现有项目结构
- 前端采用Vue 3 + TypeScript + Element Plus，使用深色主题
- 数据库使用SQLite，模型与现有资产管理模块风格一致

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, Vue 3, TypeScript, Element Plus

---

## Phase 15: 容量管理模块 (Capacity Management)

### Task 1: 创建容量管理数据库模型

**Files:**
- Create: `backend/app/models/capacity.py`
- Modify: `backend/app/models/__init__.py`

**Step 1: 创建容量管理模型文件**

```python
# backend/app/models/capacity.py
"""容量管理数据模型"""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum, Text, Boolean
from sqlalchemy.orm import relationship
from app.core.database import Base


class CapacityType(str, enum.Enum):
    """容量类型"""
    space = "空间容量"
    power = "电力容量"
    cooling = "制冷容量"
    weight = "承重容量"
    network = "网络容量"


class CapacityStatus(str, enum.Enum):
    """容量状态"""
    normal = "正常"
    warning = "预警"
    critical = "紧急"
    full = "已满"


class SpaceCapacity(Base):
    """空间容量 - 机房/机柜空间使用"""
    __tablename__ = "space_capacities"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, comment="名称")
    location = Column(String(200), comment="位置")
    total_area = Column(Float, default=0, comment="总面积(平方米)")
    used_area = Column(Float, default=0, comment="已用面积")
    total_cabinets = Column(Integer, default=0, comment="总机柜数")
    used_cabinets = Column(Integer, default=0, comment="已用机柜数")
    total_u_positions = Column(Integer, default=0, comment="总U位数")
    used_u_positions = Column(Integer, default=0, comment="已用U位数")
    warning_threshold = Column(Float, default=80, comment="预警阈值(%)")
    critical_threshold = Column(Float, default=95, comment="紧急阈值(%)")
    status = Column(Enum(CapacityStatus), default=CapacityStatus.normal)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class PowerCapacity(Base):
    """电力容量 - 配电系统容量"""
    __tablename__ = "power_capacities"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, comment="名称")
    location = Column(String(200), comment="位置")
    capacity_type = Column(String(50), comment="类型(变压器/UPS/PDU/机柜)")
    total_capacity_kva = Column(Float, default=0, comment="总容量(kVA)")
    used_capacity_kva = Column(Float, default=0, comment="已用容量(kVA)")
    total_capacity_kw = Column(Float, default=0, comment="总容量(kW)")
    used_capacity_kw = Column(Float, default=0, comment="已用功率(kW)")
    redundancy_mode = Column(String(20), comment="冗余模式(N/N+1/2N)")
    warning_threshold = Column(Float, default=70, comment="预警阈值(%)")
    critical_threshold = Column(Float, default=85, comment="紧急阈值(%)")
    status = Column(Enum(CapacityStatus), default=CapacityStatus.normal)
    parent_id = Column(Integer, ForeignKey("power_capacities.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class CoolingCapacity(Base):
    """制冷容量 - 空调制冷能力"""
    __tablename__ = "cooling_capacities"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, comment="名称")
    location = Column(String(200), comment="位置")
    total_cooling_kw = Column(Float, default=0, comment="总制冷量(kW)")
    used_cooling_kw = Column(Float, default=0, comment="已用制冷量(kW)")
    target_temperature = Column(Float, default=24, comment="目标温度")
    current_temperature = Column(Float, comment="当前温度")
    humidity_target = Column(Float, default=50, comment="目标湿度")
    current_humidity = Column(Float, comment="当前湿度")
    warning_threshold = Column(Float, default=75, comment="预警阈值(%)")
    critical_threshold = Column(Float, default=90, comment="紧急阈值(%)")
    status = Column(Enum(CapacityStatus), default=CapacityStatus.normal)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class WeightCapacity(Base):
    """承重容量 - 机柜/地板承重"""
    __tablename__ = "weight_capacities"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, comment="名称")
    location = Column(String(200), comment="位置")
    capacity_type = Column(String(50), comment="类型(机柜/地板)")
    total_weight_kg = Column(Float, default=0, comment="最大承重(kg)")
    used_weight_kg = Column(Float, default=0, comment="已用承重(kg)")
    warning_threshold = Column(Float, default=80, comment="预警阈值(%)")
    critical_threshold = Column(Float, default=95, comment="紧急阈值(%)")
    status = Column(Enum(CapacityStatus), default=CapacityStatus.normal)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class CapacityPlan(Base):
    """容量规划 - 上架评估记录"""
    __tablename__ = "capacity_plans"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, comment="规划名称")
    description = Column(Text, comment="描述")
    device_count = Column(Integer, default=1, comment="设备数量")
    required_u = Column(Integer, default=0, comment="需要U位")
    required_power_kw = Column(Float, default=0, comment="需要功率(kW)")
    required_cooling_kw = Column(Float, default=0, comment="需要制冷(kW)")
    required_weight_kg = Column(Float, default=0, comment="设备重量(kg)")
    target_cabinet_id = Column(Integer, comment="目标机柜ID")
    is_feasible = Column(Boolean, default=False, comment="是否可行")
    feasibility_notes = Column(Text, comment="可行性说明")
    created_by = Column(String(100), comment="创建人")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class CapacityHistory(Base):
    """容量历史 - 容量使用趋势"""
    __tablename__ = "capacity_histories"

    id = Column(Integer, primary_key=True, index=True)
    capacity_type = Column(Enum(CapacityType), nullable=False)
    reference_id = Column(Integer, comment="关联ID")
    reference_name = Column(String(100), comment="关联名称")
    total_value = Column(Float, comment="总容量")
    used_value = Column(Float, comment="已用容量")
    usage_rate = Column(Float, comment="使用率(%)")
    recorded_at = Column(DateTime, default=datetime.now)
```

**Step 2: 更新模型导出**

在 `backend/app/models/__init__.py` 添加:

```python
from .capacity import (
    CapacityType, CapacityStatus,
    SpaceCapacity, PowerCapacity, CoolingCapacity, WeightCapacity,
    CapacityPlan, CapacityHistory
)
```

**Step 3: 验证导入**

Run: `cd /d/mytest1/backend && python -c "from app.models.capacity import *; print('OK')"`
Expected: OK

---

### Task 2: 创建容量管理Schema定义

**Files:**
- Create: `backend/app/schemas/capacity.py`

**Step 1: 创建Schema文件**

```python
# backend/app/schemas/capacity.py
"""容量管理Schema定义"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
from app.models.capacity import CapacityType, CapacityStatus


# ========== 空间容量 ==========
class SpaceCapacityBase(BaseModel):
    name: str
    location: Optional[str] = None
    total_area: float = 0
    used_area: float = 0
    total_cabinets: int = 0
    used_cabinets: int = 0
    total_u_positions: int = 0
    used_u_positions: int = 0
    warning_threshold: float = 80
    critical_threshold: float = 95


class SpaceCapacityCreate(SpaceCapacityBase):
    pass


class SpaceCapacityUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    total_area: Optional[float] = None
    used_area: Optional[float] = None
    total_cabinets: Optional[int] = None
    used_cabinets: Optional[int] = None
    total_u_positions: Optional[int] = None
    used_u_positions: Optional[int] = None
    warning_threshold: Optional[float] = None
    critical_threshold: Optional[float] = None


class SpaceCapacityResponse(SpaceCapacityBase):
    id: int
    status: CapacityStatus
    usage_rate: float = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ========== 电力容量 ==========
class PowerCapacityBase(BaseModel):
    name: str
    location: Optional[str] = None
    capacity_type: Optional[str] = None
    total_capacity_kva: float = 0
    used_capacity_kva: float = 0
    total_capacity_kw: float = 0
    used_capacity_kw: float = 0
    redundancy_mode: Optional[str] = None
    warning_threshold: float = 70
    critical_threshold: float = 85
    parent_id: Optional[int] = None


class PowerCapacityCreate(PowerCapacityBase):
    pass


class PowerCapacityUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    capacity_type: Optional[str] = None
    total_capacity_kva: Optional[float] = None
    used_capacity_kva: Optional[float] = None
    total_capacity_kw: Optional[float] = None
    used_capacity_kw: Optional[float] = None
    redundancy_mode: Optional[str] = None
    warning_threshold: Optional[float] = None
    critical_threshold: Optional[float] = None
    parent_id: Optional[int] = None


class PowerCapacityResponse(PowerCapacityBase):
    id: int
    status: CapacityStatus
    usage_rate: float = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ========== 制冷容量 ==========
class CoolingCapacityBase(BaseModel):
    name: str
    location: Optional[str] = None
    total_cooling_kw: float = 0
    used_cooling_kw: float = 0
    target_temperature: float = 24
    current_temperature: Optional[float] = None
    humidity_target: float = 50
    current_humidity: Optional[float] = None
    warning_threshold: float = 75
    critical_threshold: float = 90


class CoolingCapacityCreate(CoolingCapacityBase):
    pass


class CoolingCapacityUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    total_cooling_kw: Optional[float] = None
    used_cooling_kw: Optional[float] = None
    target_temperature: Optional[float] = None
    current_temperature: Optional[float] = None
    humidity_target: Optional[float] = None
    current_humidity: Optional[float] = None
    warning_threshold: Optional[float] = None
    critical_threshold: Optional[float] = None


class CoolingCapacityResponse(CoolingCapacityBase):
    id: int
    status: CapacityStatus
    usage_rate: float = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ========== 承重容量 ==========
class WeightCapacityBase(BaseModel):
    name: str
    location: Optional[str] = None
    capacity_type: Optional[str] = None
    total_weight_kg: float = 0
    used_weight_kg: float = 0
    warning_threshold: float = 80
    critical_threshold: float = 95


class WeightCapacityCreate(WeightCapacityBase):
    pass


class WeightCapacityUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    capacity_type: Optional[str] = None
    total_weight_kg: Optional[float] = None
    used_weight_kg: Optional[float] = None
    warning_threshold: Optional[float] = None
    critical_threshold: Optional[float] = None


class WeightCapacityResponse(WeightCapacityBase):
    id: int
    status: CapacityStatus
    usage_rate: float = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ========== 容量规划 ==========
class CapacityPlanBase(BaseModel):
    name: str
    description: Optional[str] = None
    device_count: int = 1
    required_u: int = 0
    required_power_kw: float = 0
    required_cooling_kw: float = 0
    required_weight_kg: float = 0
    target_cabinet_id: Optional[int] = None


class CapacityPlanCreate(CapacityPlanBase):
    created_by: Optional[str] = None


class CapacityPlanResponse(CapacityPlanBase):
    id: int
    is_feasible: bool
    feasibility_notes: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ========== 容量统计 ==========
class CapacityStatistics(BaseModel):
    """容量统计概览"""
    space: dict  # 空间容量统计
    power: dict  # 电力容量统计
    cooling: dict  # 制冷容量统计
    weight: dict  # 承重容量统计


class CapacityTrend(BaseModel):
    """容量趋势数据"""
    timestamps: List[str]
    values: List[float]
    capacity_type: str
```

**Step 2: 验证导入**

Run: `cd /d/mytest1/backend && python -c "from app.schemas.capacity import *; print('OK')"`
Expected: OK

---

### Task 3: 创建容量管理服务层

**Files:**
- Create: `backend/app/services/capacity.py`

**Step 1: 创建服务文件**

```python
# backend/app/services/capacity.py
"""容量管理服务"""
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.capacity import (
    SpaceCapacity, PowerCapacity, CoolingCapacity, WeightCapacity,
    CapacityPlan, CapacityHistory, CapacityType, CapacityStatus
)
from app.schemas.capacity import (
    SpaceCapacityCreate, SpaceCapacityUpdate,
    PowerCapacityCreate, PowerCapacityUpdate,
    CoolingCapacityCreate, CoolingCapacityUpdate,
    WeightCapacityCreate, WeightCapacityUpdate,
    CapacityPlanCreate
)


class CapacityService:
    """容量管理服务类"""

    # ========== 空间容量 ==========
    def get_space_capacities(self, db: Session, skip: int = 0, limit: int = 100) -> List[SpaceCapacity]:
        return db.query(SpaceCapacity).offset(skip).limit(limit).all()

    def get_space_capacity(self, db: Session, capacity_id: int) -> Optional[SpaceCapacity]:
        return db.query(SpaceCapacity).filter(SpaceCapacity.id == capacity_id).first()

    def create_space_capacity(self, db: Session, data: SpaceCapacityCreate) -> SpaceCapacity:
        capacity = SpaceCapacity(**data.model_dump())
        capacity.status = self._calculate_status(
            capacity.used_u_positions, capacity.total_u_positions,
            capacity.warning_threshold, capacity.critical_threshold
        )
        db.add(capacity)
        db.commit()
        db.refresh(capacity)
        return capacity

    def update_space_capacity(self, db: Session, capacity_id: int, data: SpaceCapacityUpdate) -> Optional[SpaceCapacity]:
        capacity = self.get_space_capacity(db, capacity_id)
        if not capacity:
            return None
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(capacity, key, value)
        capacity.status = self._calculate_status(
            capacity.used_u_positions, capacity.total_u_positions,
            capacity.warning_threshold, capacity.critical_threshold
        )
        db.commit()
        db.refresh(capacity)
        return capacity

    def delete_space_capacity(self, db: Session, capacity_id: int) -> bool:
        capacity = self.get_space_capacity(db, capacity_id)
        if not capacity:
            return False
        db.delete(capacity)
        db.commit()
        return True

    # ========== 电力容量 ==========
    def get_power_capacities(self, db: Session, skip: int = 0, limit: int = 100) -> List[PowerCapacity]:
        return db.query(PowerCapacity).offset(skip).limit(limit).all()

    def get_power_capacity(self, db: Session, capacity_id: int) -> Optional[PowerCapacity]:
        return db.query(PowerCapacity).filter(PowerCapacity.id == capacity_id).first()

    def create_power_capacity(self, db: Session, data: PowerCapacityCreate) -> PowerCapacity:
        capacity = PowerCapacity(**data.model_dump())
        capacity.status = self._calculate_status(
            capacity.used_capacity_kw, capacity.total_capacity_kw,
            capacity.warning_threshold, capacity.critical_threshold
        )
        db.add(capacity)
        db.commit()
        db.refresh(capacity)
        return capacity

    def update_power_capacity(self, db: Session, capacity_id: int, data: PowerCapacityUpdate) -> Optional[PowerCapacity]:
        capacity = self.get_power_capacity(db, capacity_id)
        if not capacity:
            return None
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(capacity, key, value)
        capacity.status = self._calculate_status(
            capacity.used_capacity_kw, capacity.total_capacity_kw,
            capacity.warning_threshold, capacity.critical_threshold
        )
        db.commit()
        db.refresh(capacity)
        return capacity

    def delete_power_capacity(self, db: Session, capacity_id: int) -> bool:
        capacity = self.get_power_capacity(db, capacity_id)
        if not capacity:
            return False
        db.delete(capacity)
        db.commit()
        return True

    # ========== 制冷容量 ==========
    def get_cooling_capacities(self, db: Session, skip: int = 0, limit: int = 100) -> List[CoolingCapacity]:
        return db.query(CoolingCapacity).offset(skip).limit(limit).all()

    def get_cooling_capacity(self, db: Session, capacity_id: int) -> Optional[CoolingCapacity]:
        return db.query(CoolingCapacity).filter(CoolingCapacity.id == capacity_id).first()

    def create_cooling_capacity(self, db: Session, data: CoolingCapacityCreate) -> CoolingCapacity:
        capacity = CoolingCapacity(**data.model_dump())
        capacity.status = self._calculate_status(
            capacity.used_cooling_kw, capacity.total_cooling_kw,
            capacity.warning_threshold, capacity.critical_threshold
        )
        db.add(capacity)
        db.commit()
        db.refresh(capacity)
        return capacity

    def update_cooling_capacity(self, db: Session, capacity_id: int, data: CoolingCapacityUpdate) -> Optional[CoolingCapacity]:
        capacity = self.get_cooling_capacity(db, capacity_id)
        if not capacity:
            return None
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(capacity, key, value)
        capacity.status = self._calculate_status(
            capacity.used_cooling_kw, capacity.total_cooling_kw,
            capacity.warning_threshold, capacity.critical_threshold
        )
        db.commit()
        db.refresh(capacity)
        return capacity

    def delete_cooling_capacity(self, db: Session, capacity_id: int) -> bool:
        capacity = self.get_cooling_capacity(db, capacity_id)
        if not capacity:
            return False
        db.delete(capacity)
        db.commit()
        return True

    # ========== 承重容量 ==========
    def get_weight_capacities(self, db: Session, skip: int = 0, limit: int = 100) -> List[WeightCapacity]:
        return db.query(WeightCapacity).offset(skip).limit(limit).all()

    def get_weight_capacity(self, db: Session, capacity_id: int) -> Optional[WeightCapacity]:
        return db.query(WeightCapacity).filter(WeightCapacity.id == capacity_id).first()

    def create_weight_capacity(self, db: Session, data: WeightCapacityCreate) -> WeightCapacity:
        capacity = WeightCapacity(**data.model_dump())
        capacity.status = self._calculate_status(
            capacity.used_weight_kg, capacity.total_weight_kg,
            capacity.warning_threshold, capacity.critical_threshold
        )
        db.add(capacity)
        db.commit()
        db.refresh(capacity)
        return capacity

    def update_weight_capacity(self, db: Session, capacity_id: int, data: WeightCapacityUpdate) -> Optional[WeightCapacity]:
        capacity = self.get_weight_capacity(db, capacity_id)
        if not capacity:
            return None
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(capacity, key, value)
        capacity.status = self._calculate_status(
            capacity.used_weight_kg, capacity.total_weight_kg,
            capacity.warning_threshold, capacity.critical_threshold
        )
        db.commit()
        db.refresh(capacity)
        return capacity

    def delete_weight_capacity(self, db: Session, capacity_id: int) -> bool:
        capacity = self.get_weight_capacity(db, capacity_id)
        if not capacity:
            return False
        db.delete(capacity)
        db.commit()
        return True

    # ========== 容量规划 ==========
    def get_capacity_plans(self, db: Session, skip: int = 0, limit: int = 100) -> List[CapacityPlan]:
        return db.query(CapacityPlan).order_by(CapacityPlan.created_at.desc()).offset(skip).limit(limit).all()

    def get_capacity_plan(self, db: Session, plan_id: int) -> Optional[CapacityPlan]:
        return db.query(CapacityPlan).filter(CapacityPlan.id == plan_id).first()

    def create_capacity_plan(self, db: Session, data: CapacityPlanCreate) -> CapacityPlan:
        plan = CapacityPlan(**data.model_dump())
        # 评估可行性
        plan.is_feasible, plan.feasibility_notes = self._evaluate_feasibility(db, plan)
        db.add(plan)
        db.commit()
        db.refresh(plan)
        return plan

    def delete_capacity_plan(self, db: Session, plan_id: int) -> bool:
        plan = self.get_capacity_plan(db, plan_id)
        if not plan:
            return False
        db.delete(plan)
        db.commit()
        return True

    # ========== 统计 ==========
    def get_statistics(self, db: Session) -> dict:
        """获取容量统计"""
        # 空间容量统计
        space_list = db.query(SpaceCapacity).all()
        space_stats = {
            "total_u": sum(s.total_u_positions for s in space_list),
            "used_u": sum(s.used_u_positions for s in space_list),
            "total_cabinets": sum(s.total_cabinets for s in space_list),
            "used_cabinets": sum(s.used_cabinets for s in space_list),
            "usage_rate": 0
        }
        if space_stats["total_u"] > 0:
            space_stats["usage_rate"] = round(space_stats["used_u"] / space_stats["total_u"] * 100, 1)

        # 电力容量统计
        power_list = db.query(PowerCapacity).all()
        power_stats = {
            "total_kw": sum(p.total_capacity_kw for p in power_list),
            "used_kw": sum(p.used_capacity_kw for p in power_list),
            "usage_rate": 0
        }
        if power_stats["total_kw"] > 0:
            power_stats["usage_rate"] = round(power_stats["used_kw"] / power_stats["total_kw"] * 100, 1)

        # 制冷容量统计
        cooling_list = db.query(CoolingCapacity).all()
        cooling_stats = {
            "total_kw": sum(c.total_cooling_kw for c in cooling_list),
            "used_kw": sum(c.used_cooling_kw for c in cooling_list),
            "usage_rate": 0
        }
        if cooling_stats["total_kw"] > 0:
            cooling_stats["usage_rate"] = round(cooling_stats["used_kw"] / cooling_stats["total_kw"] * 100, 1)

        # 承重容量统计
        weight_list = db.query(WeightCapacity).all()
        weight_stats = {
            "total_kg": sum(w.total_weight_kg for w in weight_list),
            "used_kg": sum(w.used_weight_kg for w in weight_list),
            "usage_rate": 0
        }
        if weight_stats["total_kg"] > 0:
            weight_stats["usage_rate"] = round(weight_stats["used_kg"] / weight_stats["total_kg"] * 100, 1)

        return {
            "space": space_stats,
            "power": power_stats,
            "cooling": cooling_stats,
            "weight": weight_stats
        }

    # ========== 辅助方法 ==========
    def _calculate_status(self, used: float, total: float, warning: float, critical: float) -> CapacityStatus:
        """计算容量状态"""
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

    def _evaluate_feasibility(self, db: Session, plan: CapacityPlan) -> tuple:
        """评估上架可行性"""
        notes = []
        is_feasible = True

        # 检查空间容量
        space_stats = db.query(SpaceCapacity).first()
        if space_stats:
            remaining_u = space_stats.total_u_positions - space_stats.used_u_positions
            if plan.required_u > remaining_u:
                is_feasible = False
                notes.append(f"U位不足: 需要{plan.required_u}U, 剩余{remaining_u}U")
            else:
                notes.append(f"U位充足: 需要{plan.required_u}U, 剩余{remaining_u}U")

        # 检查电力容量
        power_stats = db.query(PowerCapacity).first()
        if power_stats:
            remaining_kw = power_stats.total_capacity_kw - power_stats.used_capacity_kw
            if plan.required_power_kw > remaining_kw:
                is_feasible = False
                notes.append(f"电力不足: 需要{plan.required_power_kw}kW, 剩余{remaining_kw}kW")
            else:
                notes.append(f"电力充足: 需要{plan.required_power_kw}kW, 剩余{remaining_kw}kW")

        # 检查制冷容量
        cooling_stats = db.query(CoolingCapacity).first()
        if cooling_stats:
            remaining_kw = cooling_stats.total_cooling_kw - cooling_stats.used_cooling_kw
            if plan.required_cooling_kw > remaining_kw:
                is_feasible = False
                notes.append(f"制冷不足: 需要{plan.required_cooling_kw}kW, 剩余{remaining_kw}kW")
            else:
                notes.append(f"制冷充足: 需要{plan.required_cooling_kw}kW, 剩余{remaining_kw}kW")

        return is_feasible, "; ".join(notes)


# 创建服务实例
capacity_service = CapacityService()
```

**Step 2: 验证导入**

Run: `cd /d/mytest1/backend && python -c "from app.services.capacity import capacity_service; print('OK')"`
Expected: OK

---

### Task 4: 创建容量管理API端点

**Files:**
- Create: `backend/app/api/v1/capacity.py`
- Modify: `backend/app/api/v1/__init__.py`

**Step 1: 创建API路由文件**

```python
# backend/app/api/v1/capacity.py
"""容量管理API端点"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.capacity import capacity_service
from app.schemas.capacity import (
    SpaceCapacityCreate, SpaceCapacityUpdate, SpaceCapacityResponse,
    PowerCapacityCreate, PowerCapacityUpdate, PowerCapacityResponse,
    CoolingCapacityCreate, CoolingCapacityUpdate, CoolingCapacityResponse,
    WeightCapacityCreate, WeightCapacityUpdate, WeightCapacityResponse,
    CapacityPlanCreate, CapacityPlanResponse,
    CapacityStatistics
)

router = APIRouter(prefix="/capacity", tags=["容量管理"])


# ========== 空间容量 ==========
@router.get("/space", response_model=List[SpaceCapacityResponse])
def get_space_capacities(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """获取空间容量列表"""
    capacities = capacity_service.get_space_capacities(db, skip, limit)
    result = []
    for c in capacities:
        data = SpaceCapacityResponse.model_validate(c)
        data.usage_rate = round(c.used_u_positions / c.total_u_positions * 100, 1) if c.total_u_positions > 0 else 0
        result.append(data)
    return result


@router.post("/space", response_model=SpaceCapacityResponse)
def create_space_capacity(data: SpaceCapacityCreate, db: Session = Depends(get_db)):
    """创建空间容量"""
    capacity = capacity_service.create_space_capacity(db, data)
    result = SpaceCapacityResponse.model_validate(capacity)
    result.usage_rate = round(capacity.used_u_positions / capacity.total_u_positions * 100, 1) if capacity.total_u_positions > 0 else 0
    return result


@router.get("/space/{capacity_id}", response_model=SpaceCapacityResponse)
def get_space_capacity(capacity_id: int, db: Session = Depends(get_db)):
    """获取空间容量详情"""
    capacity = capacity_service.get_space_capacity(db, capacity_id)
    if not capacity:
        raise HTTPException(status_code=404, detail="空间容量不存在")
    result = SpaceCapacityResponse.model_validate(capacity)
    result.usage_rate = round(capacity.used_u_positions / capacity.total_u_positions * 100, 1) if capacity.total_u_positions > 0 else 0
    return result


@router.put("/space/{capacity_id}", response_model=SpaceCapacityResponse)
def update_space_capacity(capacity_id: int, data: SpaceCapacityUpdate, db: Session = Depends(get_db)):
    """更新空间容量"""
    capacity = capacity_service.update_space_capacity(db, capacity_id, data)
    if not capacity:
        raise HTTPException(status_code=404, detail="空间容量不存在")
    result = SpaceCapacityResponse.model_validate(capacity)
    result.usage_rate = round(capacity.used_u_positions / capacity.total_u_positions * 100, 1) if capacity.total_u_positions > 0 else 0
    return result


@router.delete("/space/{capacity_id}")
def delete_space_capacity(capacity_id: int, db: Session = Depends(get_db)):
    """删除空间容量"""
    if not capacity_service.delete_space_capacity(db, capacity_id):
        raise HTTPException(status_code=404, detail="空间容量不存在")
    return {"message": "删除成功"}


# ========== 电力容量 ==========
@router.get("/power", response_model=List[PowerCapacityResponse])
def get_power_capacities(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """获取电力容量列表"""
    capacities = capacity_service.get_power_capacities(db, skip, limit)
    result = []
    for c in capacities:
        data = PowerCapacityResponse.model_validate(c)
        data.usage_rate = round(c.used_capacity_kw / c.total_capacity_kw * 100, 1) if c.total_capacity_kw > 0 else 0
        result.append(data)
    return result


@router.post("/power", response_model=PowerCapacityResponse)
def create_power_capacity(data: PowerCapacityCreate, db: Session = Depends(get_db)):
    """创建电力容量"""
    capacity = capacity_service.create_power_capacity(db, data)
    result = PowerCapacityResponse.model_validate(capacity)
    result.usage_rate = round(capacity.used_capacity_kw / capacity.total_capacity_kw * 100, 1) if capacity.total_capacity_kw > 0 else 0
    return result


@router.get("/power/{capacity_id}", response_model=PowerCapacityResponse)
def get_power_capacity(capacity_id: int, db: Session = Depends(get_db)):
    """获取电力容量详情"""
    capacity = capacity_service.get_power_capacity(db, capacity_id)
    if not capacity:
        raise HTTPException(status_code=404, detail="电力容量不存在")
    result = PowerCapacityResponse.model_validate(capacity)
    result.usage_rate = round(capacity.used_capacity_kw / capacity.total_capacity_kw * 100, 1) if capacity.total_capacity_kw > 0 else 0
    return result


@router.put("/power/{capacity_id}", response_model=PowerCapacityResponse)
def update_power_capacity(capacity_id: int, data: PowerCapacityUpdate, db: Session = Depends(get_db)):
    """更新电力容量"""
    capacity = capacity_service.update_power_capacity(db, capacity_id, data)
    if not capacity:
        raise HTTPException(status_code=404, detail="电力容量不存在")
    result = PowerCapacityResponse.model_validate(capacity)
    result.usage_rate = round(capacity.used_capacity_kw / capacity.total_capacity_kw * 100, 1) if capacity.total_capacity_kw > 0 else 0
    return result


@router.delete("/power/{capacity_id}")
def delete_power_capacity(capacity_id: int, db: Session = Depends(get_db)):
    """删除电力容量"""
    if not capacity_service.delete_power_capacity(db, capacity_id):
        raise HTTPException(status_code=404, detail="电力容量不存在")
    return {"message": "删除成功"}


# ========== 制冷容量 ==========
@router.get("/cooling", response_model=List[CoolingCapacityResponse])
def get_cooling_capacities(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """获取制冷容量列表"""
    capacities = capacity_service.get_cooling_capacities(db, skip, limit)
    result = []
    for c in capacities:
        data = CoolingCapacityResponse.model_validate(c)
        data.usage_rate = round(c.used_cooling_kw / c.total_cooling_kw * 100, 1) if c.total_cooling_kw > 0 else 0
        result.append(data)
    return result


@router.post("/cooling", response_model=CoolingCapacityResponse)
def create_cooling_capacity(data: CoolingCapacityCreate, db: Session = Depends(get_db)):
    """创建制冷容量"""
    capacity = capacity_service.create_cooling_capacity(db, data)
    result = CoolingCapacityResponse.model_validate(capacity)
    result.usage_rate = round(capacity.used_cooling_kw / capacity.total_cooling_kw * 100, 1) if capacity.total_cooling_kw > 0 else 0
    return result


@router.get("/cooling/{capacity_id}", response_model=CoolingCapacityResponse)
def get_cooling_capacity(capacity_id: int, db: Session = Depends(get_db)):
    """获取制冷容量详情"""
    capacity = capacity_service.get_cooling_capacity(db, capacity_id)
    if not capacity:
        raise HTTPException(status_code=404, detail="制冷容量不存在")
    result = CoolingCapacityResponse.model_validate(capacity)
    result.usage_rate = round(capacity.used_cooling_kw / capacity.total_cooling_kw * 100, 1) if capacity.total_cooling_kw > 0 else 0
    return result


@router.put("/cooling/{capacity_id}", response_model=CoolingCapacityResponse)
def update_cooling_capacity(capacity_id: int, data: CoolingCapacityUpdate, db: Session = Depends(get_db)):
    """更新制冷容量"""
    capacity = capacity_service.update_cooling_capacity(db, capacity_id, data)
    if not capacity:
        raise HTTPException(status_code=404, detail="制冷容量不存在")
    result = CoolingCapacityResponse.model_validate(capacity)
    result.usage_rate = round(capacity.used_cooling_kw / capacity.total_cooling_kw * 100, 1) if capacity.total_cooling_kw > 0 else 0
    return result


@router.delete("/cooling/{capacity_id}")
def delete_cooling_capacity(capacity_id: int, db: Session = Depends(get_db)):
    """删除制冷容量"""
    if not capacity_service.delete_cooling_capacity(db, capacity_id):
        raise HTTPException(status_code=404, detail="制冷容量不存在")
    return {"message": "删除成功"}


# ========== 承重容量 ==========
@router.get("/weight", response_model=List[WeightCapacityResponse])
def get_weight_capacities(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """获取承重容量列表"""
    capacities = capacity_service.get_weight_capacities(db, skip, limit)
    result = []
    for c in capacities:
        data = WeightCapacityResponse.model_validate(c)
        data.usage_rate = round(c.used_weight_kg / c.total_weight_kg * 100, 1) if c.total_weight_kg > 0 else 0
        result.append(data)
    return result


@router.post("/weight", response_model=WeightCapacityResponse)
def create_weight_capacity(data: WeightCapacityCreate, db: Session = Depends(get_db)):
    """创建承重容量"""
    capacity = capacity_service.create_weight_capacity(db, data)
    result = WeightCapacityResponse.model_validate(capacity)
    result.usage_rate = round(capacity.used_weight_kg / capacity.total_weight_kg * 100, 1) if capacity.total_weight_kg > 0 else 0
    return result


@router.get("/weight/{capacity_id}", response_model=WeightCapacityResponse)
def get_weight_capacity(capacity_id: int, db: Session = Depends(get_db)):
    """获取承重容量详情"""
    capacity = capacity_service.get_weight_capacity(db, capacity_id)
    if not capacity:
        raise HTTPException(status_code=404, detail="承重容量不存在")
    result = WeightCapacityResponse.model_validate(capacity)
    result.usage_rate = round(capacity.used_weight_kg / capacity.total_weight_kg * 100, 1) if capacity.total_weight_kg > 0 else 0
    return result


@router.put("/weight/{capacity_id}", response_model=WeightCapacityResponse)
def update_weight_capacity(capacity_id: int, data: WeightCapacityUpdate, db: Session = Depends(get_db)):
    """更新承重容量"""
    capacity = capacity_service.update_weight_capacity(db, capacity_id, data)
    if not capacity:
        raise HTTPException(status_code=404, detail="承重容量不存在")
    result = WeightCapacityResponse.model_validate(capacity)
    result.usage_rate = round(capacity.used_weight_kg / capacity.total_weight_kg * 100, 1) if capacity.total_weight_kg > 0 else 0
    return result


@router.delete("/weight/{capacity_id}")
def delete_weight_capacity(capacity_id: int, db: Session = Depends(get_db)):
    """删除承重容量"""
    if not capacity_service.delete_weight_capacity(db, capacity_id):
        raise HTTPException(status_code=404, detail="承重容量不存在")
    return {"message": "删除成功"}


# ========== 容量规划 ==========
@router.get("/plans", response_model=List[CapacityPlanResponse])
def get_capacity_plans(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """获取容量规划列表"""
    return capacity_service.get_capacity_plans(db, skip, limit)


@router.post("/plans", response_model=CapacityPlanResponse)
def create_capacity_plan(data: CapacityPlanCreate, db: Session = Depends(get_db)):
    """创建容量规划(上架评估)"""
    return capacity_service.create_capacity_plan(db, data)


@router.get("/plans/{plan_id}", response_model=CapacityPlanResponse)
def get_capacity_plan(plan_id: int, db: Session = Depends(get_db)):
    """获取容量规划详情"""
    plan = capacity_service.get_capacity_plan(db, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="容量规划不存在")
    return plan


@router.delete("/plans/{plan_id}")
def delete_capacity_plan(plan_id: int, db: Session = Depends(get_db)):
    """删除容量规划"""
    if not capacity_service.delete_capacity_plan(db, plan_id):
        raise HTTPException(status_code=404, detail="容量规划不存在")
    return {"message": "删除成功"}


# ========== 统计 ==========
@router.get("/statistics")
def get_statistics(db: Session = Depends(get_db)):
    """获取容量统计"""
    return capacity_service.get_statistics(db)
```

**Step 2: 注册路由**

在 `backend/app/api/v1/__init__.py` 添加:

```python
from .capacity import router as capacity_router
api_router.include_router(capacity_router)
```

**Step 3: 验证导入**

Run: `cd /d/mytest1/backend && python -c "from app.api.v1.capacity import router; print('OK')"`
Expected: OK

---

### Task 5: 创建前端容量管理API模块

**Files:**
- Create: `frontend/src/api/modules/capacity.ts`
- Modify: `frontend/src/api/modules/index.ts`

**Step 1: 创建前端API模块**

```typescript
// frontend/src/api/modules/capacity.ts
import request from '../request'

// 容量状态枚举
export type CapacityStatus = 'normal' | 'warning' | 'critical' | 'full'

// ========== 空间容量 ==========
export interface SpaceCapacity {
  id: number
  name: string
  location?: string
  total_area: number
  used_area: number
  total_cabinets: number
  used_cabinets: number
  total_u_positions: number
  used_u_positions: number
  warning_threshold: number
  critical_threshold: number
  status: CapacityStatus
  usage_rate: number
  created_at: string
  updated_at: string
}

export interface SpaceCapacityCreate {
  name: string
  location?: string
  total_area?: number
  used_area?: number
  total_cabinets?: number
  used_cabinets?: number
  total_u_positions?: number
  used_u_positions?: number
  warning_threshold?: number
  critical_threshold?: number
}

// ========== 电力容量 ==========
export interface PowerCapacity {
  id: number
  name: string
  location?: string
  capacity_type?: string
  total_capacity_kva: number
  used_capacity_kva: number
  total_capacity_kw: number
  used_capacity_kw: number
  redundancy_mode?: string
  warning_threshold: number
  critical_threshold: number
  status: CapacityStatus
  usage_rate: number
  parent_id?: number
  created_at: string
  updated_at: string
}

export interface PowerCapacityCreate {
  name: string
  location?: string
  capacity_type?: string
  total_capacity_kva?: number
  used_capacity_kva?: number
  total_capacity_kw?: number
  used_capacity_kw?: number
  redundancy_mode?: string
  warning_threshold?: number
  critical_threshold?: number
  parent_id?: number
}

// ========== 制冷容量 ==========
export interface CoolingCapacity {
  id: number
  name: string
  location?: string
  total_cooling_kw: number
  used_cooling_kw: number
  target_temperature: number
  current_temperature?: number
  humidity_target: number
  current_humidity?: number
  warning_threshold: number
  critical_threshold: number
  status: CapacityStatus
  usage_rate: number
  created_at: string
  updated_at: string
}

export interface CoolingCapacityCreate {
  name: string
  location?: string
  total_cooling_kw?: number
  used_cooling_kw?: number
  target_temperature?: number
  humidity_target?: number
  warning_threshold?: number
  critical_threshold?: number
}

// ========== 承重容量 ==========
export interface WeightCapacity {
  id: number
  name: string
  location?: string
  capacity_type?: string
  total_weight_kg: number
  used_weight_kg: number
  warning_threshold: number
  critical_threshold: number
  status: CapacityStatus
  usage_rate: number
  created_at: string
  updated_at: string
}

export interface WeightCapacityCreate {
  name: string
  location?: string
  capacity_type?: string
  total_weight_kg?: number
  used_weight_kg?: number
  warning_threshold?: number
  critical_threshold?: number
}

// ========== 容量规划 ==========
export interface CapacityPlan {
  id: number
  name: string
  description?: string
  device_count: number
  required_u: number
  required_power_kw: number
  required_cooling_kw: number
  required_weight_kg: number
  target_cabinet_id?: number
  is_feasible: boolean
  feasibility_notes?: string
  created_by?: string
  created_at: string
  updated_at: string
}

export interface CapacityPlanCreate {
  name: string
  description?: string
  device_count?: number
  required_u?: number
  required_power_kw?: number
  required_cooling_kw?: number
  required_weight_kg?: number
  target_cabinet_id?: number
  created_by?: string
}

// ========== 统计 ==========
export interface CapacityStatistics {
  space: {
    total_u: number
    used_u: number
    total_cabinets: number
    used_cabinets: number
    usage_rate: number
  }
  power: {
    total_kw: number
    used_kw: number
    usage_rate: number
  }
  cooling: {
    total_kw: number
    used_kw: number
    usage_rate: number
  }
  weight: {
    total_kg: number
    used_kg: number
    usage_rate: number
  }
}

// ========== API函数 ==========

// 空间容量
export const getSpaceCapacities = () => request.get<SpaceCapacity[]>('/v1/capacity/space')
export const createSpaceCapacity = (data: SpaceCapacityCreate) => request.post<SpaceCapacity>('/v1/capacity/space', data)
export const getSpaceCapacity = (id: number) => request.get<SpaceCapacity>(`/v1/capacity/space/${id}`)
export const updateSpaceCapacity = (id: number, data: Partial<SpaceCapacityCreate>) => request.put<SpaceCapacity>(`/v1/capacity/space/${id}`, data)
export const deleteSpaceCapacity = (id: number) => request.delete(`/v1/capacity/space/${id}`)

// 电力容量
export const getPowerCapacities = () => request.get<PowerCapacity[]>('/v1/capacity/power')
export const createPowerCapacity = (data: PowerCapacityCreate) => request.post<PowerCapacity>('/v1/capacity/power', data)
export const getPowerCapacity = (id: number) => request.get<PowerCapacity>(`/v1/capacity/power/${id}`)
export const updatePowerCapacity = (id: number, data: Partial<PowerCapacityCreate>) => request.put<PowerCapacity>(`/v1/capacity/power/${id}`, data)
export const deletePowerCapacity = (id: number) => request.delete(`/v1/capacity/power/${id}`)

// 制冷容量
export const getCoolingCapacities = () => request.get<CoolingCapacity[]>('/v1/capacity/cooling')
export const createCoolingCapacity = (data: CoolingCapacityCreate) => request.post<CoolingCapacity>('/v1/capacity/cooling', data)
export const getCoolingCapacity = (id: number) => request.get<CoolingCapacity>(`/v1/capacity/cooling/${id}`)
export const updateCoolingCapacity = (id: number, data: Partial<CoolingCapacityCreate>) => request.put<CoolingCapacity>(`/v1/capacity/cooling/${id}`, data)
export const deleteCoolingCapacity = (id: number) => request.delete(`/v1/capacity/cooling/${id}`)

// 承重容量
export const getWeightCapacities = () => request.get<WeightCapacity[]>('/v1/capacity/weight')
export const createWeightCapacity = (data: WeightCapacityCreate) => request.post<WeightCapacity>('/v1/capacity/weight', data)
export const getWeightCapacity = (id: number) => request.get<WeightCapacity>(`/v1/capacity/weight/${id}`)
export const updateWeightCapacity = (id: number, data: Partial<WeightCapacityCreate>) => request.put<WeightCapacity>(`/v1/capacity/weight/${id}`, data)
export const deleteWeightCapacity = (id: number) => request.delete(`/v1/capacity/weight/${id}`)

// 容量规划
export const getCapacityPlans = () => request.get<CapacityPlan[]>('/v1/capacity/plans')
export const createCapacityPlan = (data: CapacityPlanCreate) => request.post<CapacityPlan>('/v1/capacity/plans', data)
export const getCapacityPlan = (id: number) => request.get<CapacityPlan>(`/v1/capacity/plans/${id}`)
export const deleteCapacityPlan = (id: number) => request.delete(`/v1/capacity/plans/${id}`)

// 统计
export const getCapacityStatistics = () => request.get<CapacityStatistics>('/v1/capacity/statistics')
```

**Step 2: 更新模块导出**

在 `frontend/src/api/modules/index.ts` 添加:

```typescript
export * from './capacity'
```

---

### Task 6: 创建前端容量管理页面

**Files:**
- Create: `frontend/src/views/capacity/index.vue`

**Step 1: 创建容量管理页面**

```vue
<!-- frontend/src/views/capacity/index.vue -->
<template>
  <div class="capacity-page">
    <!-- 统计卡片 -->
    <el-row :gutter="20" class="stat-cards">
      <el-col :span="6">
        <el-card class="stat-card space-card">
          <div class="stat-icon"><el-icon :size="32"><Grid /></el-icon></div>
          <div class="stat-content">
            <div class="stat-title">空间容量</div>
            <div class="stat-value">{{ statistics.space?.usage_rate || 0 }}%</div>
            <div class="stat-desc">{{ statistics.space?.used_u || 0 }} / {{ statistics.space?.total_u || 0 }} U</div>
          </div>
          <el-progress :percentage="statistics.space?.usage_rate || 0" :stroke-width="6" :show-text="false" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card power-card">
          <div class="stat-icon"><el-icon :size="32"><Lightning /></el-icon></div>
          <div class="stat-content">
            <div class="stat-title">电力容量</div>
            <div class="stat-value">{{ statistics.power?.usage_rate || 0 }}%</div>
            <div class="stat-desc">{{ statistics.power?.used_kw || 0 }} / {{ statistics.power?.total_kw || 0 }} kW</div>
          </div>
          <el-progress :percentage="statistics.power?.usage_rate || 0" :stroke-width="6" :show-text="false" status="warning" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card cooling-card">
          <div class="stat-icon"><el-icon :size="32"><Odometer /></el-icon></div>
          <div class="stat-content">
            <div class="stat-title">制冷容量</div>
            <div class="stat-value">{{ statistics.cooling?.usage_rate || 0 }}%</div>
            <div class="stat-desc">{{ statistics.cooling?.used_kw || 0 }} / {{ statistics.cooling?.total_kw || 0 }} kW</div>
          </div>
          <el-progress :percentage="statistics.cooling?.usage_rate || 0" :stroke-width="6" :show-text="false" status="success" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card weight-card">
          <div class="stat-icon"><el-icon :size="32"><Box /></el-icon></div>
          <div class="stat-content">
            <div class="stat-title">承重容量</div>
            <div class="stat-value">{{ statistics.weight?.usage_rate || 0 }}%</div>
            <div class="stat-desc">{{ statistics.weight?.used_kg || 0 }} / {{ statistics.weight?.total_kg || 0 }} kg</div>
          </div>
          <el-progress :percentage="statistics.weight?.usage_rate || 0" :stroke-width="6" :show-text="false" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 标签页 -->
    <el-card class="main-card">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="空间容量" name="space">
          <div class="tab-toolbar">
            <el-button type="primary" @click="openSpaceDialog()">
              <el-icon><Plus /></el-icon> 新增空间
            </el-button>
          </div>
          <el-table :data="spaceList" stripe>
            <el-table-column prop="name" label="名称" />
            <el-table-column prop="location" label="位置" />
            <el-table-column label="U位使用">
              <template #default="{ row }">
                {{ row.used_u_positions }} / {{ row.total_u_positions }} U
              </template>
            </el-table-column>
            <el-table-column label="使用率">
              <template #default="{ row }">
                <el-progress :percentage="row.usage_rate" :stroke-width="10" />
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)">{{ getStatusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150">
              <template #default="{ row }">
                <el-button type="primary" link @click="openSpaceDialog(row)">编辑</el-button>
                <el-button type="danger" link @click="handleDeleteSpace(row.id)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="电力容量" name="power">
          <div class="tab-toolbar">
            <el-button type="primary" @click="openPowerDialog()">
              <el-icon><Plus /></el-icon> 新增电力
            </el-button>
          </div>
          <el-table :data="powerList" stripe>
            <el-table-column prop="name" label="名称" />
            <el-table-column prop="capacity_type" label="类型" />
            <el-table-column label="功率使用">
              <template #default="{ row }">
                {{ row.used_capacity_kw }} / {{ row.total_capacity_kw }} kW
              </template>
            </el-table-column>
            <el-table-column prop="redundancy_mode" label="冗余模式" />
            <el-table-column label="使用率">
              <template #default="{ row }">
                <el-progress :percentage="row.usage_rate" :stroke-width="10" status="warning" />
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)">{{ getStatusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150">
              <template #default="{ row }">
                <el-button type="primary" link @click="openPowerDialog(row)">编辑</el-button>
                <el-button type="danger" link @click="handleDeletePower(row.id)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="制冷容量" name="cooling">
          <div class="tab-toolbar">
            <el-button type="primary" @click="openCoolingDialog()">
              <el-icon><Plus /></el-icon> 新增制冷
            </el-button>
          </div>
          <el-table :data="coolingList" stripe>
            <el-table-column prop="name" label="名称" />
            <el-table-column prop="location" label="位置" />
            <el-table-column label="制冷量">
              <template #default="{ row }">
                {{ row.used_cooling_kw }} / {{ row.total_cooling_kw }} kW
              </template>
            </el-table-column>
            <el-table-column label="温度">
              <template #default="{ row }">
                {{ row.current_temperature ?? '-' }} / {{ row.target_temperature }}°C
              </template>
            </el-table-column>
            <el-table-column label="使用率">
              <template #default="{ row }">
                <el-progress :percentage="row.usage_rate" :stroke-width="10" status="success" />
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)">{{ getStatusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150">
              <template #default="{ row }">
                <el-button type="primary" link @click="openCoolingDialog(row)">编辑</el-button>
                <el-button type="danger" link @click="handleDeleteCooling(row.id)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="上架评估" name="plan">
          <div class="tab-toolbar">
            <el-button type="primary" @click="openPlanDialog()">
              <el-icon><Plus /></el-icon> 新建评估
            </el-button>
          </div>
          <el-table :data="planList" stripe>
            <el-table-column prop="name" label="规划名称" />
            <el-table-column prop="device_count" label="设备数量" />
            <el-table-column prop="required_u" label="需要U位" />
            <el-table-column prop="required_power_kw" label="需要功率(kW)" />
            <el-table-column label="可行性">
              <template #default="{ row }">
                <el-tag :type="row.is_feasible ? 'success' : 'danger'">
                  {{ row.is_feasible ? '可行' : '不可行' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="feasibility_notes" label="评估说明" show-overflow-tooltip />
            <el-table-column label="操作" width="100">
              <template #default="{ row }">
                <el-button type="danger" link @click="handleDeletePlan(row.id)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 空间容量对话框 -->
    <el-dialog v-model="spaceDialogVisible" :title="editingSpace ? '编辑空间容量' : '新增空间容量'" width="500px">
      <el-form :model="spaceForm" label-width="100px">
        <el-form-item label="名称" required>
          <el-input v-model="spaceForm.name" />
        </el-form-item>
        <el-form-item label="位置">
          <el-input v-model="spaceForm.location" />
        </el-form-item>
        <el-form-item label="总U位数">
          <el-input-number v-model="spaceForm.total_u_positions" :min="0" />
        </el-form-item>
        <el-form-item label="已用U位数">
          <el-input-number v-model="spaceForm.used_u_positions" :min="0" />
        </el-form-item>
        <el-form-item label="预警阈值(%)">
          <el-input-number v-model="spaceForm.warning_threshold" :min="0" :max="100" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="spaceDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSaveSpace">保存</el-button>
      </template>
    </el-dialog>

    <!-- 电力容量对话框 -->
    <el-dialog v-model="powerDialogVisible" :title="editingPower ? '编辑电力容量' : '新增电力容量'" width="500px">
      <el-form :model="powerForm" label-width="100px">
        <el-form-item label="名称" required>
          <el-input v-model="powerForm.name" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="powerForm.capacity_type">
            <el-option label="变压器" value="变压器" />
            <el-option label="UPS" value="UPS" />
            <el-option label="PDU" value="PDU" />
            <el-option label="机柜" value="机柜" />
          </el-select>
        </el-form-item>
        <el-form-item label="总容量(kW)">
          <el-input-number v-model="powerForm.total_capacity_kw" :min="0" :precision="1" />
        </el-form-item>
        <el-form-item label="已用功率(kW)">
          <el-input-number v-model="powerForm.used_capacity_kw" :min="0" :precision="1" />
        </el-form-item>
        <el-form-item label="冗余模式">
          <el-select v-model="powerForm.redundancy_mode">
            <el-option label="N" value="N" />
            <el-option label="N+1" value="N+1" />
            <el-option label="2N" value="2N" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="powerDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSavePower">保存</el-button>
      </template>
    </el-dialog>

    <!-- 制冷容量对话框 -->
    <el-dialog v-model="coolingDialogVisible" :title="editingCooling ? '编辑制冷容量' : '新增制冷容量'" width="500px">
      <el-form :model="coolingForm" label-width="100px">
        <el-form-item label="名称" required>
          <el-input v-model="coolingForm.name" />
        </el-form-item>
        <el-form-item label="位置">
          <el-input v-model="coolingForm.location" />
        </el-form-item>
        <el-form-item label="总制冷量(kW)">
          <el-input-number v-model="coolingForm.total_cooling_kw" :min="0" :precision="1" />
        </el-form-item>
        <el-form-item label="已用制冷(kW)">
          <el-input-number v-model="coolingForm.used_cooling_kw" :min="0" :precision="1" />
        </el-form-item>
        <el-form-item label="目标温度(°C)">
          <el-input-number v-model="coolingForm.target_temperature" :min="16" :max="30" :precision="1" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="coolingDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSaveCooling">保存</el-button>
      </template>
    </el-dialog>

    <!-- 上架评估对话框 -->
    <el-dialog v-model="planDialogVisible" title="新建上架评估" width="500px">
      <el-form :model="planForm" label-width="120px">
        <el-form-item label="规划名称" required>
          <el-input v-model="planForm.name" placeholder="例如: 新增10台服务器" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="planForm.description" type="textarea" />
        </el-form-item>
        <el-form-item label="设备数量">
          <el-input-number v-model="planForm.device_count" :min="1" />
        </el-form-item>
        <el-form-item label="需要U位">
          <el-input-number v-model="planForm.required_u" :min="0" />
        </el-form-item>
        <el-form-item label="需要功率(kW)">
          <el-input-number v-model="planForm.required_power_kw" :min="0" :precision="1" />
        </el-form-item>
        <el-form-item label="需要制冷(kW)">
          <el-input-number v-model="planForm.required_cooling_kw" :min="0" :precision="1" />
        </el-form-item>
        <el-form-item label="设备重量(kg)">
          <el-input-number v-model="planForm.required_weight_kg" :min="0" :precision="1" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="planDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSavePlan">评估</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Grid, Lightning, Odometer, Box, Plus } from '@element-plus/icons-vue'
import {
  getCapacityStatistics,
  getSpaceCapacities, createSpaceCapacity, updateSpaceCapacity, deleteSpaceCapacity,
  getPowerCapacities, createPowerCapacity, updatePowerCapacity, deletePowerCapacity,
  getCoolingCapacities, createCoolingCapacity, updateCoolingCapacity, deleteCoolingCapacity,
  getCapacityPlans, createCapacityPlan, deleteCapacityPlan,
  type SpaceCapacity, type PowerCapacity, type CoolingCapacity, type CapacityPlan, type CapacityStatistics
} from '@/api/modules/capacity'

const activeTab = ref('space')
const statistics = ref<Partial<CapacityStatistics>>({})
const spaceList = ref<SpaceCapacity[]>([])
const powerList = ref<PowerCapacity[]>([])
const coolingList = ref<CoolingCapacity[]>([])
const planList = ref<CapacityPlan[]>([])

// 对话框
const spaceDialogVisible = ref(false)
const powerDialogVisible = ref(false)
const coolingDialogVisible = ref(false)
const planDialogVisible = ref(false)

const editingSpace = ref<SpaceCapacity | null>(null)
const editingPower = ref<PowerCapacity | null>(null)
const editingCooling = ref<CoolingCapacity | null>(null)

const spaceForm = ref({ name: '', location: '', total_u_positions: 0, used_u_positions: 0, warning_threshold: 80 })
const powerForm = ref({ name: '', capacity_type: '', total_capacity_kw: 0, used_capacity_kw: 0, redundancy_mode: 'N' })
const coolingForm = ref({ name: '', location: '', total_cooling_kw: 0, used_cooling_kw: 0, target_temperature: 24 })
const planForm = ref({ name: '', description: '', device_count: 1, required_u: 0, required_power_kw: 0, required_cooling_kw: 0, required_weight_kg: 0 })

const getStatusType = (status: string) => {
  const map: Record<string, string> = { normal: 'success', warning: 'warning', critical: 'danger', full: 'danger' }
  return map[status] || 'info'
}

const getStatusLabel = (status: string) => {
  const map: Record<string, string> = { normal: '正常', warning: '预警', critical: '紧急', full: '已满' }
  return map[status] || status
}

const loadData = async () => {
  try {
    const [statsRes, spaceRes, powerRes, coolingRes, planRes] = await Promise.all([
      getCapacityStatistics(),
      getSpaceCapacities(),
      getPowerCapacities(),
      getCoolingCapacities(),
      getCapacityPlans()
    ])
    statistics.value = statsRes.data
    spaceList.value = spaceRes.data
    powerList.value = powerRes.data
    coolingList.value = coolingRes.data
    planList.value = planRes.data
  } catch (e) {
    console.error('加载数据失败', e)
  }
}

// 空间容量操作
const openSpaceDialog = (row?: SpaceCapacity) => {
  editingSpace.value = row || null
  if (row) {
    spaceForm.value = { name: row.name, location: row.location || '', total_u_positions: row.total_u_positions, used_u_positions: row.used_u_positions, warning_threshold: row.warning_threshold }
  } else {
    spaceForm.value = { name: '', location: '', total_u_positions: 0, used_u_positions: 0, warning_threshold: 80 }
  }
  spaceDialogVisible.value = true
}

const handleSaveSpace = async () => {
  try {
    if (editingSpace.value) {
      await updateSpaceCapacity(editingSpace.value.id, spaceForm.value)
      ElMessage.success('更新成功')
    } else {
      await createSpaceCapacity(spaceForm.value)
      ElMessage.success('创建成功')
    }
    spaceDialogVisible.value = false
    loadData()
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

const handleDeleteSpace = async (id: number) => {
  await ElMessageBox.confirm('确定删除该空间容量?', '提示', { type: 'warning' })
  await deleteSpaceCapacity(id)
  ElMessage.success('删除成功')
  loadData()
}

// 电力容量操作
const openPowerDialog = (row?: PowerCapacity) => {
  editingPower.value = row || null
  if (row) {
    powerForm.value = { name: row.name, capacity_type: row.capacity_type || '', total_capacity_kw: row.total_capacity_kw, used_capacity_kw: row.used_capacity_kw, redundancy_mode: row.redundancy_mode || 'N' }
  } else {
    powerForm.value = { name: '', capacity_type: '', total_capacity_kw: 0, used_capacity_kw: 0, redundancy_mode: 'N' }
  }
  powerDialogVisible.value = true
}

const handleSavePower = async () => {
  try {
    if (editingPower.value) {
      await updatePowerCapacity(editingPower.value.id, powerForm.value)
      ElMessage.success('更新成功')
    } else {
      await createPowerCapacity(powerForm.value)
      ElMessage.success('创建成功')
    }
    powerDialogVisible.value = false
    loadData()
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

const handleDeletePower = async (id: number) => {
  await ElMessageBox.confirm('确定删除该电力容量?', '提示', { type: 'warning' })
  await deletePowerCapacity(id)
  ElMessage.success('删除成功')
  loadData()
}

// 制冷容量操作
const openCoolingDialog = (row?: CoolingCapacity) => {
  editingCooling.value = row || null
  if (row) {
    coolingForm.value = { name: row.name, location: row.location || '', total_cooling_kw: row.total_cooling_kw, used_cooling_kw: row.used_cooling_kw, target_temperature: row.target_temperature }
  } else {
    coolingForm.value = { name: '', location: '', total_cooling_kw: 0, used_cooling_kw: 0, target_temperature: 24 }
  }
  coolingDialogVisible.value = true
}

const handleSaveCooling = async () => {
  try {
    if (editingCooling.value) {
      await updateCoolingCapacity(editingCooling.value.id, coolingForm.value)
      ElMessage.success('更新成功')
    } else {
      await createCoolingCapacity(coolingForm.value)
      ElMessage.success('创建成功')
    }
    coolingDialogVisible.value = false
    loadData()
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

const handleDeleteCooling = async (id: number) => {
  await ElMessageBox.confirm('确定删除该制冷容量?', '提示', { type: 'warning' })
  await deleteCoolingCapacity(id)
  ElMessage.success('删除成功')
  loadData()
}

// 上架评估操作
const openPlanDialog = () => {
  planForm.value = { name: '', description: '', device_count: 1, required_u: 0, required_power_kw: 0, required_cooling_kw: 0, required_weight_kg: 0 }
  planDialogVisible.value = true
}

const handleSavePlan = async () => {
  try {
    await createCapacityPlan(planForm.value)
    ElMessage.success('评估完成')
    planDialogVisible.value = false
    loadData()
  } catch (e) {
    ElMessage.error('评估失败')
  }
}

const handleDeletePlan = async (id: number) => {
  await ElMessageBox.confirm('确定删除该评估记录?', '提示', { type: 'warning' })
  await deleteCapacityPlan(id)
  ElMessage.success('删除成功')
  loadData()
}

onMounted(() => {
  loadData()
})
</script>

<style scoped lang="scss">
.capacity-page {
  padding: 0;
}

.stat-cards {
  margin-bottom: 20px;
}

.stat-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  display: flex;
  flex-wrap: wrap;
  padding: 16px;
  gap: 12px;
  align-items: center;

  .stat-icon {
    width: 56px;
    height: 56px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(0, 204, 255, 0.1);
    color: var(--accent-color);
  }

  .stat-content {
    flex: 1;

    .stat-title {
      font-size: 14px;
      color: var(--text-secondary);
    }

    .stat-value {
      font-size: 28px;
      font-weight: bold;
      color: var(--text-primary);
    }

    .stat-desc {
      font-size: 12px;
      color: var(--text-secondary);
    }
  }

  :deep(.el-progress) {
    width: 100%;
  }
}

.main-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
}

.tab-toolbar {
  margin-bottom: 16px;
}
</style>
```

---

### Task 7: 添加路由配置和菜单

**Files:**
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/layouts/MainLayout.vue`

**Step 1: 添加路由**

在 `frontend/src/router/index.ts` 的 MainLayout children 中添加:

```typescript
{
  path: 'capacity',
  name: 'Capacity',
  component: () => import('@/views/capacity/index.vue'),
  meta: { title: '容量管理' }
},
```

**Step 2: 添加菜单**

在 `frontend/src/layouts/MainLayout.vue` 的菜单中，在资产管理后添加:

```vue
<el-menu-item index="/capacity">
  <el-icon><DataAnalysis /></el-icon>
  <template #title>容量管理</template>
</el-menu-item>
```

并在 icons 导入中添加 `DataAnalysis`。

---

### Task 8: 构建验证

**Step 1: 运行构建**

Run: `cd /d/mytest1/frontend && npm run build`
Expected: 构建成功，无编译错误

---

## Phase 16: 运维管理模块 (Operation Management)

### Task 9: 创建运维管理数据库模型

**Files:**
- Create: `backend/app/models/operation.py`
- Modify: `backend/app/models/__init__.py`

**Step 1: 创建运维管理模型文件**

```python
# backend/app/models/operation.py
"""运维管理数据模型"""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum, Text, Boolean
from sqlalchemy.orm import relationship
from app.core.database import Base


class WorkOrderStatus(str, enum.Enum):
    """工单状态"""
    pending = "待处理"
    assigned = "已派单"
    processing = "处理中"
    completed = "已完成"
    closed = "已关闭"
    cancelled = "已取消"


class WorkOrderType(str, enum.Enum):
    """工单类型"""
    fault = "故障报修"
    maintenance = "日常维护"
    inspection = "巡检任务"
    change = "变更请求"
    other = "其他"


class WorkOrderPriority(str, enum.Enum):
    """工单优先级"""
    critical = "紧急"
    high = "高"
    medium = "中"
    low = "低"


class InspectionStatus(str, enum.Enum):
    """巡检状态"""
    pending = "待巡检"
    in_progress = "巡检中"
    completed = "已完成"
    overdue = "已逾期"


class WorkOrder(Base):
    """工单"""
    __tablename__ = "work_orders"

    id = Column(Integer, primary_key=True, index=True)
    order_no = Column(String(50), unique=True, index=True, comment="工单编号")
    title = Column(String(200), nullable=False, comment="工单标题")
    description = Column(Text, comment="问题描述")
    order_type = Column(Enum(WorkOrderType), default=WorkOrderType.fault, comment="工单类型")
    priority = Column(Enum(WorkOrderPriority), default=WorkOrderPriority.medium, comment="优先级")
    status = Column(Enum(WorkOrderStatus), default=WorkOrderStatus.pending, comment="状态")

    # 关联信息
    device_id = Column(Integer, comment="关联设备ID")
    device_name = Column(String(100), comment="关联设备名称")
    location = Column(String(200), comment="位置")

    # 人员信息
    reporter = Column(String(100), comment="报修人")
    reporter_phone = Column(String(20), comment="报修人电话")
    assignee = Column(String(100), comment="处理人")

    # 时间信息
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    assigned_at = Column(DateTime, comment="派单时间")
    started_at = Column(DateTime, comment="开始处理时间")
    completed_at = Column(DateTime, comment="完成时间")
    closed_at = Column(DateTime, comment="关闭时间")
    deadline = Column(DateTime, comment="截止时间")

    # 处理信息
    solution = Column(Text, comment="解决方案")
    root_cause = Column(Text, comment="根本原因")
    remarks = Column(Text, comment="备注")

    # 评价
    satisfaction = Column(Integer, comment="满意度(1-5)")
    feedback = Column(Text, comment="反馈")


class WorkOrderLog(Base):
    """工单日志"""
    __tablename__ = "work_order_logs"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("work_orders.id"), nullable=False)
    action = Column(String(50), comment="操作类型")
    content = Column(Text, comment="日志内容")
    operator = Column(String(100), comment="操作人")
    created_at = Column(DateTime, default=datetime.now)


class InspectionPlan(Base):
    """巡检计划"""
    __tablename__ = "inspection_plans"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, comment="计划名称")
    description = Column(Text, comment="描述")
    frequency = Column(String(50), comment="频率(daily/weekly/monthly)")
    location = Column(String(200), comment="巡检区域")
    check_items = Column(Text, comment="检查项(JSON)")
    assignee = Column(String(100), comment="负责人")
    is_active = Column(Boolean, default=True, comment="是否启用")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class InspectionTask(Base):
    """巡检任务"""
    __tablename__ = "inspection_tasks"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, ForeignKey("inspection_plans.id"), nullable=False)
    task_no = Column(String(50), unique=True, index=True, comment="任务编号")
    status = Column(Enum(InspectionStatus), default=InspectionStatus.pending)
    assignee = Column(String(100), comment="执行人")
    scheduled_date = Column(DateTime, comment="计划执行日期")
    started_at = Column(DateTime, comment="开始时间")
    completed_at = Column(DateTime, comment="完成时间")
    result = Column(Text, comment="巡检结果(JSON)")
    abnormal_count = Column(Integer, default=0, comment="异常项数")
    remarks = Column(Text, comment="备注")
    created_at = Column(DateTime, default=datetime.now)


class KnowledgeBase(Base):
    """知识库"""
    __tablename__ = "knowledge_base"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False, comment="标题")
    category = Column(String(50), comment="分类")
    content = Column(Text, comment="内容")
    tags = Column(String(200), comment="标签")
    view_count = Column(Integer, default=0, comment="查看次数")
    is_published = Column(Boolean, default=True, comment="是否发布")
    author = Column(String(100), comment="作者")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
```

**Step 2: 更新模型导出**

在 `backend/app/models/__init__.py` 添加:

```python
from .operation import (
    WorkOrderStatus, WorkOrderType, WorkOrderPriority, InspectionStatus,
    WorkOrder, WorkOrderLog, InspectionPlan, InspectionTask, KnowledgeBase
)
```

**Step 3: 验证导入**

Run: `cd /d/mytest1/backend && python -c "from app.models.operation import *; print('OK')"`
Expected: OK

---

### Task 10: 创建运维管理Schema定义

**Files:**
- Create: `backend/app/schemas/operation.py`

**Step 1: 创建Schema文件**

```python
# backend/app/schemas/operation.py
"""运维管理Schema定义"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
from app.models.operation import WorkOrderStatus, WorkOrderType, WorkOrderPriority, InspectionStatus


# ========== 工单 ==========
class WorkOrderBase(BaseModel):
    title: str
    description: Optional[str] = None
    order_type: WorkOrderType = WorkOrderType.fault
    priority: WorkOrderPriority = WorkOrderPriority.medium
    device_id: Optional[int] = None
    device_name: Optional[str] = None
    location: Optional[str] = None
    reporter: Optional[str] = None
    reporter_phone: Optional[str] = None
    deadline: Optional[datetime] = None


class WorkOrderCreate(WorkOrderBase):
    pass


class WorkOrderUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[WorkOrderPriority] = None
    status: Optional[WorkOrderStatus] = None
    assignee: Optional[str] = None
    solution: Optional[str] = None
    root_cause: Optional[str] = None
    remarks: Optional[str] = None


class WorkOrderResponse(WorkOrderBase):
    id: int
    order_no: str
    status: WorkOrderStatus
    assignee: Optional[str] = None
    created_at: datetime
    assigned_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    solution: Optional[str] = None
    root_cause: Optional[str] = None

    class Config:
        from_attributes = True


class WorkOrderLogResponse(BaseModel):
    id: int
    order_id: int
    action: str
    content: Optional[str] = None
    operator: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ========== 巡检计划 ==========
class InspectionPlanBase(BaseModel):
    name: str
    description: Optional[str] = None
    frequency: str = "daily"
    location: Optional[str] = None
    check_items: Optional[str] = None
    assignee: Optional[str] = None
    is_active: bool = True


class InspectionPlanCreate(InspectionPlanBase):
    pass


class InspectionPlanUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    frequency: Optional[str] = None
    location: Optional[str] = None
    check_items: Optional[str] = None
    assignee: Optional[str] = None
    is_active: Optional[bool] = None


class InspectionPlanResponse(InspectionPlanBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ========== 巡检任务 ==========
class InspectionTaskBase(BaseModel):
    plan_id: int
    assignee: Optional[str] = None
    scheduled_date: Optional[datetime] = None


class InspectionTaskCreate(InspectionTaskBase):
    pass


class InspectionTaskUpdate(BaseModel):
    status: Optional[InspectionStatus] = None
    assignee: Optional[str] = None
    result: Optional[str] = None
    abnormal_count: Optional[int] = None
    remarks: Optional[str] = None


class InspectionTaskResponse(InspectionTaskBase):
    id: int
    task_no: str
    status: InspectionStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[str] = None
    abnormal_count: int
    remarks: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ========== 知识库 ==========
class KnowledgeBase_(BaseModel):
    title: str
    category: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[str] = None
    is_published: bool = True
    author: Optional[str] = None


class KnowledgeCreate(KnowledgeBase_):
    pass


class KnowledgeUpdate(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[str] = None
    is_published: Optional[bool] = None


class KnowledgeResponse(KnowledgeBase_):
    id: int
    view_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ========== 统计 ==========
class OperationStatistics(BaseModel):
    total_orders: int
    pending_orders: int
    processing_orders: int
    completed_orders: int
    overdue_inspections: int
    knowledge_count: int
```

**Step 2: 验证导入**

Run: `cd /d/mytest1/backend && python -c "from app.schemas.operation import *; print('OK')"`
Expected: OK

---

### Task 11: 创建运维管理服务层

**Files:**
- Create: `backend/app/services/operation.py`

(服务层代码详见完整实现，包含工单CRUD、巡检计划/任务管理、知识库管理、统计)

---

### Task 12: 创建运维管理API端点

**Files:**
- Create: `backend/app/api/v1/operation.py`
- Modify: `backend/app/api/v1/__init__.py`

(API端点代码详见完整实现，约30个端点)

---

### Task 13: 创建前端运维管理API模块

**Files:**
- Create: `frontend/src/api/modules/operation.ts`
- Modify: `frontend/src/api/modules/index.ts`

---

### Task 14: 创建前端运维管理页面

**Files:**
- Create: `frontend/src/views/operation/workorder.vue` - 工单管理
- Create: `frontend/src/views/operation/inspection.vue` - 巡检管理
- Create: `frontend/src/views/operation/knowledge.vue` - 知识库

---

### Task 15: 添加路由配置和菜单

**Files:**
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/layouts/MainLayout.vue`

添加运维管理子菜单:
- /operation/workorder - 工单管理
- /operation/inspection - 巡检管理
- /operation/knowledge - 知识库

---

### Task 16: 最终构建验证

**Step 1: 后端验证**

Run: `cd /d/mytest1/backend && python -c "from app.models import *; from app.services import *; print('Backend OK')"`

**Step 2: 前端构建**

Run: `cd /d/mytest1/frontend && npm run build`
Expected: 构建成功

---

## Summary

本计划实现两个核心模块:

**Phase 15: 容量管理 (Tasks 1-8)**
- 4种容量类型: 空间/电力/制冷/承重
- 容量规划(上架评估)功能
- 统计仪表盘
- 21个API端点

**Phase 16: 运维管理 (Tasks 9-16)**
- 工单管理: 报修→派单→处理→完成
- 巡检管理: 计划→任务→执行
- 知识库: 文档管理
- 约30个API端点

执行完成后，系统将与行业DCIM标准功能对齐。
