# 资产管理模块实施计划 (V3.1)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 基于行业调研发现，实现完整的资产管理功能，包括资产台账、生命周期管理、资产盘点、维保管理

**Architecture:**
- 后端: FastAPI + SQLite + 现有Repository模式
- 前端: Vue 3 + Element Plus + 深色主题
- 与3D数字孪生集成: 资产在机柜U位可视化

**Tech Stack:** Python FastAPI + Vue 3 + TypeScript + Element Plus + SCSS

**基于:** `docs/plans/2026-01-20-dcim-system-restructure-proposal.md` 第3.2.4节

---

## Task 1: 创建资产管理数据库模型

**Files:**
- Create: `backend/app/models/asset.py`
- Modify: `backend/app/models/__init__.py`

**Step 1: 创建资产模型文件**

```python
# backend/app/models/asset.py
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum

class AssetStatus(str, enum.Enum):
    """资产状态"""
    IN_STOCK = "in_stock"       # 在库
    IN_USE = "in_use"           # 在用
    BORROWED = "borrowed"       # 借用中
    MAINTENANCE = "maintenance" # 维修中
    SCRAPPED = "scrapped"       # 已报废

class AssetType(str, enum.Enum):
    """资产类型"""
    SERVER = "server"           # 服务器
    NETWORK = "network"         # 网络设备
    STORAGE = "storage"         # 存储设备
    UPS = "ups"                 # UPS
    PDU = "pdu"                 # PDU
    AIR_CONDITIONER = "ac"      # 空调
    CABINET = "cabinet"         # 机柜
    SENSOR = "sensor"           # 传感器
    OTHER = "other"             # 其他

class Asset(Base):
    """资产台账表"""
    __tablename__ = "assets"

    id = Column(Integer, primary_key=True, index=True)
    asset_code = Column(String(50), unique=True, index=True, nullable=False, comment="资产编码")
    asset_name = Column(String(100), nullable=False, comment="资产名称")
    asset_type = Column(SQLEnum(AssetType), nullable=False, comment="资产类型")
    brand = Column(String(50), comment="品牌")
    model = Column(String(100), comment="型号")
    serial_number = Column(String(100), comment="序列号")

    # 位置信息
    cabinet_id = Column(Integer, ForeignKey("cabinets.id"), comment="所在机柜ID")
    u_position = Column(Integer, comment="U位起始位置")
    u_height = Column(Integer, default=1, comment="占用U数")

    # 资产状态
    status = Column(SQLEnum(AssetStatus), default=AssetStatus.IN_STOCK, comment="资产状态")

    # 购置信息
    purchase_date = Column(DateTime, comment="购置日期")
    purchase_price = Column(Float, comment="购置价格")
    supplier = Column(String(100), comment="供应商")

    # 维保信息
    warranty_start = Column(DateTime, comment="质保开始日期")
    warranty_end = Column(DateTime, comment="质保结束日期")
    maintenance_vendor = Column(String(100), comment="维保供应商")

    # 责任人
    owner = Column(String(50), comment="责任人")
    department = Column(String(50), comment="所属部门")

    # 配置信息(JSON格式)
    specifications = Column(Text, comment="配置规格(JSON)")

    # 备注
    remark = Column(Text, comment="备注")

    # 时间戳
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    # 关联
    cabinet = relationship("Cabinet", back_populates="assets")
    lifecycle_records = relationship("AssetLifecycle", back_populates="asset")
    maintenance_records = relationship("MaintenanceRecord", back_populates="asset")


class Cabinet(Base):
    """机柜表"""
    __tablename__ = "cabinets"

    id = Column(Integer, primary_key=True, index=True)
    cabinet_code = Column(String(50), unique=True, index=True, nullable=False, comment="机柜编码")
    cabinet_name = Column(String(100), nullable=False, comment="机柜名称")
    location = Column(String(100), comment="位置描述")
    row_number = Column(String(10), comment="列号")
    column_number = Column(String(10), comment="排号")
    total_u = Column(Integer, default=42, comment="总U数")
    max_power = Column(Float, comment="最大功率(kW)")
    max_weight = Column(Float, comment="最大承重(kg)")

    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # 关联
    assets = relationship("Asset", back_populates="cabinet")


class AssetLifecycle(Base):
    """资产生命周期记录表"""
    __tablename__ = "asset_lifecycle"

    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)
    action = Column(String(50), nullable=False, comment="操作类型: purchase/receive/install/move/maintenance/scrap")
    action_date = Column(DateTime, default=datetime.now, comment="操作时间")
    operator = Column(String(50), comment="操作人")
    from_location = Column(String(100), comment="原位置")
    to_location = Column(String(100), comment="新位置")
    remark = Column(Text, comment="备注")

    created_at = Column(DateTime, default=datetime.now)

    # 关联
    asset = relationship("Asset", back_populates="lifecycle_records")


class MaintenanceRecord(Base):
    """维保记录表"""
    __tablename__ = "maintenance_records"

    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)
    maintenance_type = Column(String(50), nullable=False, comment="维保类型: repair/inspection/upgrade")
    start_time = Column(DateTime, nullable=False, comment="开始时间")
    end_time = Column(DateTime, comment="结束时间")
    technician = Column(String(50), comment="维修人员")
    vendor = Column(String(100), comment="维保厂商")
    cost = Column(Float, comment="维保费用")
    description = Column(Text, comment="维保内容")
    result = Column(Text, comment="维保结果")

    created_at = Column(DateTime, default=datetime.now)

    # 关联
    asset = relationship("Asset", back_populates="maintenance_records")


class AssetInventory(Base):
    """资产盘点表"""
    __tablename__ = "asset_inventories"

    id = Column(Integer, primary_key=True, index=True)
    inventory_code = Column(String(50), unique=True, index=True, nullable=False, comment="盘点单号")
    inventory_date = Column(DateTime, nullable=False, comment="盘点日期")
    operator = Column(String(50), comment="盘点人")
    status = Column(String(20), default="pending", comment="状态: pending/completed")
    total_count = Column(Integer, default=0, comment="应盘数量")
    checked_count = Column(Integer, default=0, comment="已盘数量")
    matched_count = Column(Integer, default=0, comment="一致数量")
    unmatched_count = Column(Integer, default=0, comment="差异数量")
    remark = Column(Text, comment="备注")

    created_at = Column(DateTime, default=datetime.now)
    completed_at = Column(DateTime, comment="完成时间")

    # 关联
    items = relationship("AssetInventoryItem", back_populates="inventory")


class AssetInventoryItem(Base):
    """资产盘点明细表"""
    __tablename__ = "asset_inventory_items"

    id = Column(Integer, primary_key=True, index=True)
    inventory_id = Column(Integer, ForeignKey("asset_inventories.id"), nullable=False)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)
    expected_location = Column(String(100), comment="预期位置")
    actual_location = Column(String(100), comment="实际位置")
    is_matched = Column(Integer, default=0, comment="是否一致: 0=否, 1=是")
    check_time = Column(DateTime, comment="核对时间")
    remark = Column(Text, comment="备注")

    # 关联
    inventory = relationship("AssetInventory", back_populates="items")
```

**Step 2: 更新模型导出**

在 `backend/app/models/__init__.py` 中添加:

```python
from .asset import (
    Asset, Cabinet, AssetLifecycle, MaintenanceRecord,
    AssetInventory, AssetInventoryItem, AssetStatus, AssetType
)
```

**Step 3: 验证导入无错误**

Run: `cd D:/mytest1/backend && python -c "from app.models.asset import *; print('Models imported successfully')"`

Expected: `Models imported successfully`

---

## Task 2: 创建资产管理Schema定义

**Files:**
- Create: `backend/app/schemas/asset.py`

**Step 1: 创建Schema文件**

```python
# backend/app/schemas/asset.py
from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field
from app.models.asset import AssetStatus, AssetType


# ============= 机柜 Schema =============
class CabinetBase(BaseModel):
    cabinet_code: str = Field(..., description="机柜编码")
    cabinet_name: str = Field(..., description="机柜名称")
    location: Optional[str] = Field(None, description="位置描述")
    row_number: Optional[str] = Field(None, description="列号")
    column_number: Optional[str] = Field(None, description="排号")
    total_u: int = Field(42, description="总U数")
    max_power: Optional[float] = Field(None, description="最大功率(kW)")
    max_weight: Optional[float] = Field(None, description="最大承重(kg)")

class CabinetCreate(CabinetBase):
    pass

class CabinetUpdate(BaseModel):
    cabinet_name: Optional[str] = None
    location: Optional[str] = None
    row_number: Optional[str] = None
    column_number: Optional[str] = None
    total_u: Optional[int] = None
    max_power: Optional[float] = None
    max_weight: Optional[float] = None

class CabinetResponse(CabinetBase):
    id: int
    created_at: datetime
    updated_at: datetime
    used_u: int = Field(0, description="已使用U数")
    available_u: int = Field(42, description="可用U数")

    class Config:
        from_attributes = True


# ============= 资产 Schema =============
class AssetBase(BaseModel):
    asset_code: str = Field(..., description="资产编码")
    asset_name: str = Field(..., description="资产名称")
    asset_type: AssetType = Field(..., description="资产类型")
    brand: Optional[str] = Field(None, description="品牌")
    model: Optional[str] = Field(None, description="型号")
    serial_number: Optional[str] = Field(None, description="序列号")
    cabinet_id: Optional[int] = Field(None, description="所在机柜ID")
    u_position: Optional[int] = Field(None, description="U位起始位置")
    u_height: int = Field(1, description="占用U数")
    status: AssetStatus = Field(AssetStatus.IN_STOCK, description="资产状态")
    purchase_date: Optional[datetime] = Field(None, description="购置日期")
    purchase_price: Optional[float] = Field(None, description="购置价格")
    supplier: Optional[str] = Field(None, description="供应商")
    warranty_start: Optional[datetime] = Field(None, description="质保开始日期")
    warranty_end: Optional[datetime] = Field(None, description="质保结束日期")
    maintenance_vendor: Optional[str] = Field(None, description="维保供应商")
    owner: Optional[str] = Field(None, description="责任人")
    department: Optional[str] = Field(None, description="所属部门")
    specifications: Optional[str] = Field(None, description="配置规格(JSON)")
    remark: Optional[str] = Field(None, description="备注")

class AssetCreate(AssetBase):
    pass

class AssetUpdate(BaseModel):
    asset_name: Optional[str] = None
    asset_type: Optional[AssetType] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    cabinet_id: Optional[int] = None
    u_position: Optional[int] = None
    u_height: Optional[int] = None
    status: Optional[AssetStatus] = None
    purchase_date: Optional[datetime] = None
    purchase_price: Optional[float] = None
    supplier: Optional[str] = None
    warranty_start: Optional[datetime] = None
    warranty_end: Optional[datetime] = None
    maintenance_vendor: Optional[str] = None
    owner: Optional[str] = None
    department: Optional[str] = None
    specifications: Optional[str] = None
    remark: Optional[str] = None

class AssetResponse(AssetBase):
    id: int
    created_at: datetime
    updated_at: datetime
    cabinet_name: Optional[str] = Field(None, description="机柜名称")
    warranty_status: str = Field("unknown", description="质保状态: valid/expired/unknown")

    class Config:
        from_attributes = True


# ============= 生命周期 Schema =============
class LifecycleCreate(BaseModel):
    asset_id: int
    action: str = Field(..., description="操作类型")
    action_date: Optional[datetime] = None
    operator: Optional[str] = None
    from_location: Optional[str] = None
    to_location: Optional[str] = None
    remark: Optional[str] = None

class LifecycleResponse(BaseModel):
    id: int
    asset_id: int
    action: str
    action_date: datetime
    operator: Optional[str]
    from_location: Optional[str]
    to_location: Optional[str]
    remark: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ============= 维保记录 Schema =============
class MaintenanceCreate(BaseModel):
    asset_id: int
    maintenance_type: str = Field(..., description="维保类型: repair/inspection/upgrade")
    start_time: datetime
    end_time: Optional[datetime] = None
    technician: Optional[str] = None
    vendor: Optional[str] = None
    cost: Optional[float] = None
    description: Optional[str] = None
    result: Optional[str] = None

class MaintenanceResponse(BaseModel):
    id: int
    asset_id: int
    maintenance_type: str
    start_time: datetime
    end_time: Optional[datetime]
    technician: Optional[str]
    vendor: Optional[str]
    cost: Optional[float]
    description: Optional[str]
    result: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ============= 盘点 Schema =============
class InventoryCreate(BaseModel):
    inventory_date: datetime
    operator: Optional[str] = None
    remark: Optional[str] = None

class InventoryItemUpdate(BaseModel):
    actual_location: Optional[str] = None
    is_matched: int = 0
    remark: Optional[str] = None

class InventoryResponse(BaseModel):
    id: int
    inventory_code: str
    inventory_date: datetime
    operator: Optional[str]
    status: str
    total_count: int
    checked_count: int
    matched_count: int
    unmatched_count: int
    remark: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


# ============= 统计 Schema =============
class AssetStatistics(BaseModel):
    total_count: int = Field(0, description="资产总数")
    in_stock_count: int = Field(0, description="在库数量")
    in_use_count: int = Field(0, description="在用数量")
    borrowed_count: int = Field(0, description="借用数量")
    maintenance_count: int = Field(0, description="维修数量")
    scrapped_count: int = Field(0, description="报废数量")
    total_value: float = Field(0, description="资产总值")
    warranty_expiring_count: int = Field(0, description="即将过保数量(30天内)")
    by_type: dict = Field(default_factory=dict, description="按类型统计")
    by_department: dict = Field(default_factory=dict, description="按部门统计")
```

**Step 2: 验证Schema定义**

Run: `cd D:/mytest1/backend && python -c "from app.schemas.asset import *; print('Schemas imported successfully')"`

Expected: `Schemas imported successfully`

---

## Task 3: 创建资产管理服务层

**Files:**
- Create: `backend/app/services/asset.py`

**Step 1: 创建服务文件**

```python
# backend/app/services/asset.py
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from app.models.asset import (
    Asset, Cabinet, AssetLifecycle, MaintenanceRecord,
    AssetInventory, AssetInventoryItem, AssetStatus, AssetType
)
from app.schemas.asset import (
    AssetCreate, AssetUpdate, CabinetCreate, CabinetUpdate,
    LifecycleCreate, MaintenanceCreate, InventoryCreate,
    InventoryItemUpdate, AssetStatistics
)
import uuid


class AssetService:
    """资产管理服务"""

    def __init__(self, db: Session):
        self.db = db

    # ============= 机柜管理 =============
    def get_cabinets(self, skip: int = 0, limit: int = 100) -> List[Cabinet]:
        """获取机柜列表"""
        return self.db.query(Cabinet).offset(skip).limit(limit).all()

    def get_cabinet(self, cabinet_id: int) -> Optional[Cabinet]:
        """获取单个机柜"""
        return self.db.query(Cabinet).filter(Cabinet.id == cabinet_id).first()

    def get_cabinet_by_code(self, cabinet_code: str) -> Optional[Cabinet]:
        """根据编码获取机柜"""
        return self.db.query(Cabinet).filter(Cabinet.cabinet_code == cabinet_code).first()

    def create_cabinet(self, data: CabinetCreate) -> Cabinet:
        """创建机柜"""
        cabinet = Cabinet(**data.model_dump())
        self.db.add(cabinet)
        self.db.commit()
        self.db.refresh(cabinet)
        return cabinet

    def update_cabinet(self, cabinet_id: int, data: CabinetUpdate) -> Optional[Cabinet]:
        """更新机柜"""
        cabinet = self.get_cabinet(cabinet_id)
        if not cabinet:
            return None
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(cabinet, key, value)
        self.db.commit()
        self.db.refresh(cabinet)
        return cabinet

    def delete_cabinet(self, cabinet_id: int) -> bool:
        """删除机柜"""
        cabinet = self.get_cabinet(cabinet_id)
        if not cabinet:
            return False
        self.db.delete(cabinet)
        self.db.commit()
        return True

    def get_cabinet_u_usage(self, cabinet_id: int) -> Dict[str, Any]:
        """获取机柜U位使用情况"""
        cabinet = self.get_cabinet(cabinet_id)
        if not cabinet:
            return {}

        assets = self.db.query(Asset).filter(
            Asset.cabinet_id == cabinet_id,
            Asset.status.in_([AssetStatus.IN_USE, AssetStatus.BORROWED])
        ).all()

        used_u = sum(a.u_height for a in assets if a.u_height)
        u_map = {}
        for asset in assets:
            if asset.u_position and asset.u_height:
                for u in range(asset.u_position, asset.u_position + asset.u_height):
                    u_map[u] = {
                        "asset_id": asset.id,
                        "asset_name": asset.asset_name,
                        "asset_code": asset.asset_code
                    }

        return {
            "cabinet_id": cabinet_id,
            "cabinet_code": cabinet.cabinet_code,
            "total_u": cabinet.total_u,
            "used_u": used_u,
            "available_u": cabinet.total_u - used_u,
            "usage_rate": round(used_u / cabinet.total_u * 100, 2) if cabinet.total_u else 0,
            "u_map": u_map
        }

    # ============= 资产管理 =============
    def get_assets(
        self,
        skip: int = 0,
        limit: int = 100,
        asset_type: Optional[AssetType] = None,
        status: Optional[AssetStatus] = None,
        cabinet_id: Optional[int] = None,
        keyword: Optional[str] = None
    ) -> List[Asset]:
        """获取资产列表"""
        query = self.db.query(Asset)

        if asset_type:
            query = query.filter(Asset.asset_type == asset_type)
        if status:
            query = query.filter(Asset.status == status)
        if cabinet_id:
            query = query.filter(Asset.cabinet_id == cabinet_id)
        if keyword:
            query = query.filter(
                (Asset.asset_name.contains(keyword)) |
                (Asset.asset_code.contains(keyword)) |
                (Asset.serial_number.contains(keyword))
            )

        return query.order_by(Asset.created_at.desc()).offset(skip).limit(limit).all()

    def get_asset(self, asset_id: int) -> Optional[Asset]:
        """获取单个资产"""
        return self.db.query(Asset).filter(Asset.id == asset_id).first()

    def get_asset_by_code(self, asset_code: str) -> Optional[Asset]:
        """根据编码获取资产"""
        return self.db.query(Asset).filter(Asset.asset_code == asset_code).first()

    def create_asset(self, data: AssetCreate, operator: str = None) -> Asset:
        """创建资产"""
        asset = Asset(**data.model_dump())
        self.db.add(asset)
        self.db.commit()
        self.db.refresh(asset)

        # 记录生命周期
        self._add_lifecycle(asset.id, "purchase", operator, remark="资产入库")

        return asset

    def update_asset(self, asset_id: int, data: AssetUpdate, operator: str = None) -> Optional[Asset]:
        """更新资产"""
        asset = self.get_asset(asset_id)
        if not asset:
            return None

        old_cabinet_id = asset.cabinet_id
        old_status = asset.status

        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(asset, key, value)

        self.db.commit()
        self.db.refresh(asset)

        # 记录位置变更
        if data.cabinet_id and data.cabinet_id != old_cabinet_id:
            old_cabinet = self.get_cabinet(old_cabinet_id) if old_cabinet_id else None
            new_cabinet = self.get_cabinet(data.cabinet_id)
            self._add_lifecycle(
                asset_id, "move", operator,
                from_location=old_cabinet.cabinet_code if old_cabinet else "库房",
                to_location=new_cabinet.cabinet_code if new_cabinet else "未知"
            )

        # 记录状态变更
        if data.status and data.status != old_status:
            action_map = {
                AssetStatus.IN_USE: "install",
                AssetStatus.MAINTENANCE: "maintenance",
                AssetStatus.SCRAPPED: "scrap"
            }
            action = action_map.get(data.status, "status_change")
            self._add_lifecycle(asset_id, action, operator, remark=f"状态变更为{data.status.value}")

        return asset

    def delete_asset(self, asset_id: int) -> bool:
        """删除资产"""
        asset = self.get_asset(asset_id)
        if not asset:
            return False
        self.db.delete(asset)
        self.db.commit()
        return True

    def _add_lifecycle(
        self, asset_id: int, action: str, operator: str = None,
        from_location: str = None, to_location: str = None, remark: str = None
    ):
        """添加生命周期记录"""
        record = AssetLifecycle(
            asset_id=asset_id,
            action=action,
            operator=operator,
            from_location=from_location,
            to_location=to_location,
            remark=remark
        )
        self.db.add(record)
        self.db.commit()

    def get_asset_lifecycle(self, asset_id: int) -> List[AssetLifecycle]:
        """获取资产生命周期记录"""
        return self.db.query(AssetLifecycle).filter(
            AssetLifecycle.asset_id == asset_id
        ).order_by(AssetLifecycle.action_date.desc()).all()

    # ============= 维保管理 =============
    def create_maintenance(self, data: MaintenanceCreate) -> MaintenanceRecord:
        """创建维保记录"""
        record = MaintenanceRecord(**data.model_dump())
        self.db.add(record)

        # 更新资产状态为维修中
        asset = self.get_asset(data.asset_id)
        if asset:
            asset.status = AssetStatus.MAINTENANCE

        self.db.commit()
        self.db.refresh(record)
        return record

    def complete_maintenance(self, record_id: int, result: str = None) -> Optional[MaintenanceRecord]:
        """完成维保"""
        record = self.db.query(MaintenanceRecord).filter(MaintenanceRecord.id == record_id).first()
        if not record:
            return None

        record.end_time = datetime.now()
        record.result = result

        # 恢复资产状态为在用
        asset = self.get_asset(record.asset_id)
        if asset:
            asset.status = AssetStatus.IN_USE

        self.db.commit()
        self.db.refresh(record)
        return record

    def get_maintenance_records(
        self, asset_id: int = None, skip: int = 0, limit: int = 100
    ) -> List[MaintenanceRecord]:
        """获取维保记录列表"""
        query = self.db.query(MaintenanceRecord)
        if asset_id:
            query = query.filter(MaintenanceRecord.asset_id == asset_id)
        return query.order_by(MaintenanceRecord.start_time.desc()).offset(skip).limit(limit).all()

    # ============= 资产盘点 =============
    def create_inventory(self, data: InventoryCreate) -> AssetInventory:
        """创建盘点单"""
        inventory = AssetInventory(
            inventory_code=f"INV{datetime.now().strftime('%Y%m%d%H%M%S')}",
            **data.model_dump()
        )
        self.db.add(inventory)
        self.db.commit()

        # 创建盘点明细(所有在用资产)
        assets = self.db.query(Asset).filter(
            Asset.status.in_([AssetStatus.IN_USE, AssetStatus.BORROWED])
        ).all()

        for asset in assets:
            cabinet = self.get_cabinet(asset.cabinet_id) if asset.cabinet_id else None
            item = AssetInventoryItem(
                inventory_id=inventory.id,
                asset_id=asset.id,
                expected_location=cabinet.cabinet_code if cabinet else "库房"
            )
            self.db.add(item)

        inventory.total_count = len(assets)
        self.db.commit()
        self.db.refresh(inventory)
        return inventory

    def update_inventory_item(
        self, item_id: int, data: InventoryItemUpdate
    ) -> Optional[AssetInventoryItem]:
        """更新盘点明细"""
        item = self.db.query(AssetInventoryItem).filter(AssetInventoryItem.id == item_id).first()
        if not item:
            return None

        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(item, key, value)
        item.check_time = datetime.now()

        self.db.commit()
        self.db.refresh(item)

        # 更新盘点单统计
        self._update_inventory_stats(item.inventory_id)

        return item

    def _update_inventory_stats(self, inventory_id: int):
        """更新盘点单统计"""
        inventory = self.db.query(AssetInventory).filter(AssetInventory.id == inventory_id).first()
        if not inventory:
            return

        items = self.db.query(AssetInventoryItem).filter(
            AssetInventoryItem.inventory_id == inventory_id
        ).all()

        checked = [i for i in items if i.check_time]
        matched = [i for i in checked if i.is_matched == 1]

        inventory.checked_count = len(checked)
        inventory.matched_count = len(matched)
        inventory.unmatched_count = len(checked) - len(matched)

        if len(checked) == len(items):
            inventory.status = "completed"
            inventory.completed_at = datetime.now()

        self.db.commit()

    def get_inventory_list(self, skip: int = 0, limit: int = 100) -> List[AssetInventory]:
        """获取盘点单列表"""
        return self.db.query(AssetInventory).order_by(
            AssetInventory.inventory_date.desc()
        ).offset(skip).limit(limit).all()

    def get_inventory_items(self, inventory_id: int) -> List[AssetInventoryItem]:
        """获取盘点明细"""
        return self.db.query(AssetInventoryItem).filter(
            AssetInventoryItem.inventory_id == inventory_id
        ).all()

    # ============= 统计分析 =============
    def get_statistics(self) -> AssetStatistics:
        """获取资产统计"""
        total = self.db.query(func.count(Asset.id)).scalar() or 0

        # 按状态统计
        status_counts = dict(
            self.db.query(Asset.status, func.count(Asset.id))
            .group_by(Asset.status).all()
        )

        # 按类型统计
        type_counts = dict(
            self.db.query(Asset.asset_type, func.count(Asset.id))
            .group_by(Asset.asset_type).all()
        )

        # 按部门统计
        dept_counts = dict(
            self.db.query(Asset.department, func.count(Asset.id))
            .filter(Asset.department.isnot(None))
            .group_by(Asset.department).all()
        )

        # 总值
        total_value = self.db.query(func.sum(Asset.purchase_price)).scalar() or 0

        # 即将过保(30天内)
        warranty_expiring = self.db.query(func.count(Asset.id)).filter(
            Asset.warranty_end.isnot(None),
            Asset.warranty_end <= datetime.now() + timedelta(days=30),
            Asset.warranty_end > datetime.now()
        ).scalar() or 0

        return AssetStatistics(
            total_count=total,
            in_stock_count=status_counts.get(AssetStatus.IN_STOCK, 0),
            in_use_count=status_counts.get(AssetStatus.IN_USE, 0),
            borrowed_count=status_counts.get(AssetStatus.BORROWED, 0),
            maintenance_count=status_counts.get(AssetStatus.MAINTENANCE, 0),
            scrapped_count=status_counts.get(AssetStatus.SCRAPPED, 0),
            total_value=total_value,
            warranty_expiring_count=warranty_expiring,
            by_type={k.value if hasattr(k, 'value') else k: v for k, v in type_counts.items()},
            by_department=dept_counts
        )

    def get_warranty_expiring_assets(self, days: int = 30) -> List[Asset]:
        """获取即将过保的资产"""
        return self.db.query(Asset).filter(
            Asset.warranty_end.isnot(None),
            Asset.warranty_end <= datetime.now() + timedelta(days=days),
            Asset.warranty_end > datetime.now(),
            Asset.status != AssetStatus.SCRAPPED
        ).all()
```

**Step 2: 验证服务导入**

Run: `cd D:/mytest1/backend && python -c "from app.services.asset import AssetService; print('Service imported successfully')"`

Expected: `Service imported successfully`

---

## Task 4: 创建资产管理API端点

**Files:**
- Create: `backend/app/api/v1/asset.py`
- Modify: `backend/app/api/v1/__init__.py`

**Step 1: 创建API端点文件**

```python
# backend/app/api/v1/asset.py
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.asset import AssetService
from app.models.asset import AssetStatus, AssetType
from app.schemas.asset import (
    AssetCreate, AssetUpdate, AssetResponse,
    CabinetCreate, CabinetUpdate, CabinetResponse,
    LifecycleResponse, MaintenanceCreate, MaintenanceResponse,
    InventoryCreate, InventoryItemUpdate, InventoryResponse,
    AssetStatistics
)

router = APIRouter(prefix="/asset", tags=["资产管理"])


# ============= 机柜管理 =============
@router.get("/cabinets", response_model=List[CabinetResponse], summary="获取机柜列表")
def get_cabinets(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    service = AssetService(db)
    cabinets = service.get_cabinets(skip, limit)
    result = []
    for cab in cabinets:
        usage = service.get_cabinet_u_usage(cab.id)
        cab_dict = {
            **cab.__dict__,
            "used_u": usage.get("used_u", 0),
            "available_u": usage.get("available_u", cab.total_u)
        }
        result.append(cab_dict)
    return result


@router.get("/cabinets/{cabinet_id}", response_model=CabinetResponse, summary="获取单个机柜")
def get_cabinet(cabinet_id: int, db: Session = Depends(get_db)):
    service = AssetService(db)
    cabinet = service.get_cabinet(cabinet_id)
    if not cabinet:
        raise HTTPException(status_code=404, detail="机柜不存在")
    usage = service.get_cabinet_u_usage(cabinet_id)
    return {
        **cabinet.__dict__,
        "used_u": usage.get("used_u", 0),
        "available_u": usage.get("available_u", cabinet.total_u)
    }


@router.get("/cabinets/{cabinet_id}/usage", summary="获取机柜U位使用情况")
def get_cabinet_usage(cabinet_id: int, db: Session = Depends(get_db)):
    service = AssetService(db)
    usage = service.get_cabinet_u_usage(cabinet_id)
    if not usage:
        raise HTTPException(status_code=404, detail="机柜不存在")
    return {"code": 0, "data": usage}


@router.post("/cabinets", response_model=CabinetResponse, summary="创建机柜")
def create_cabinet(data: CabinetCreate, db: Session = Depends(get_db)):
    service = AssetService(db)
    if service.get_cabinet_by_code(data.cabinet_code):
        raise HTTPException(status_code=400, detail="机柜编码已存在")
    cabinet = service.create_cabinet(data)
    return {**cabinet.__dict__, "used_u": 0, "available_u": cabinet.total_u}


@router.put("/cabinets/{cabinet_id}", response_model=CabinetResponse, summary="更新机柜")
def update_cabinet(cabinet_id: int, data: CabinetUpdate, db: Session = Depends(get_db)):
    service = AssetService(db)
    cabinet = service.update_cabinet(cabinet_id, data)
    if not cabinet:
        raise HTTPException(status_code=404, detail="机柜不存在")
    usage = service.get_cabinet_u_usage(cabinet_id)
    return {
        **cabinet.__dict__,
        "used_u": usage.get("used_u", 0),
        "available_u": usage.get("available_u", cabinet.total_u)
    }


@router.delete("/cabinets/{cabinet_id}", summary="删除机柜")
def delete_cabinet(cabinet_id: int, db: Session = Depends(get_db)):
    service = AssetService(db)
    if not service.delete_cabinet(cabinet_id):
        raise HTTPException(status_code=404, detail="机柜不存在")
    return {"code": 0, "message": "删除成功"}


# ============= 资产管理 =============
@router.get("/assets", response_model=List[AssetResponse], summary="获取资产列表")
def get_assets(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    asset_type: Optional[AssetType] = None,
    status: Optional[AssetStatus] = None,
    cabinet_id: Optional[int] = None,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db)
):
    service = AssetService(db)
    assets = service.get_assets(skip, limit, asset_type, status, cabinet_id, keyword)
    result = []
    for asset in assets:
        cabinet = service.get_cabinet(asset.cabinet_id) if asset.cabinet_id else None
        warranty_status = "unknown"
        if asset.warranty_end:
            from datetime import datetime
            if asset.warranty_end > datetime.now():
                warranty_status = "valid"
            else:
                warranty_status = "expired"
        result.append({
            **asset.__dict__,
            "cabinet_name": cabinet.cabinet_name if cabinet else None,
            "warranty_status": warranty_status
        })
    return result


@router.get("/assets/{asset_id}", response_model=AssetResponse, summary="获取单个资产")
def get_asset(asset_id: int, db: Session = Depends(get_db)):
    service = AssetService(db)
    asset = service.get_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="资产不存在")
    cabinet = service.get_cabinet(asset.cabinet_id) if asset.cabinet_id else None
    warranty_status = "unknown"
    if asset.warranty_end:
        from datetime import datetime
        warranty_status = "valid" if asset.warranty_end > datetime.now() else "expired"
    return {
        **asset.__dict__,
        "cabinet_name": cabinet.cabinet_name if cabinet else None,
        "warranty_status": warranty_status
    }


@router.post("/assets", response_model=AssetResponse, summary="创建资产")
def create_asset(data: AssetCreate, db: Session = Depends(get_db)):
    service = AssetService(db)
    if service.get_asset_by_code(data.asset_code):
        raise HTTPException(status_code=400, detail="资产编码已存在")
    asset = service.create_asset(data)
    return {**asset.__dict__, "cabinet_name": None, "warranty_status": "unknown"}


@router.put("/assets/{asset_id}", response_model=AssetResponse, summary="更新资产")
def update_asset(asset_id: int, data: AssetUpdate, db: Session = Depends(get_db)):
    service = AssetService(db)
    asset = service.update_asset(asset_id, data)
    if not asset:
        raise HTTPException(status_code=404, detail="资产不存在")
    cabinet = service.get_cabinet(asset.cabinet_id) if asset.cabinet_id else None
    warranty_status = "unknown"
    if asset.warranty_end:
        from datetime import datetime
        warranty_status = "valid" if asset.warranty_end > datetime.now() else "expired"
    return {
        **asset.__dict__,
        "cabinet_name": cabinet.cabinet_name if cabinet else None,
        "warranty_status": warranty_status
    }


@router.delete("/assets/{asset_id}", summary="删除资产")
def delete_asset(asset_id: int, db: Session = Depends(get_db)):
    service = AssetService(db)
    if not service.delete_asset(asset_id):
        raise HTTPException(status_code=404, detail="资产不存在")
    return {"code": 0, "message": "删除成功"}


@router.get("/assets/{asset_id}/lifecycle", response_model=List[LifecycleResponse], summary="获取资产生命周期")
def get_asset_lifecycle(asset_id: int, db: Session = Depends(get_db)):
    service = AssetService(db)
    return service.get_asset_lifecycle(asset_id)


# ============= 维保管理 =============
@router.post("/maintenance", response_model=MaintenanceResponse, summary="创建维保记录")
def create_maintenance(data: MaintenanceCreate, db: Session = Depends(get_db)):
    service = AssetService(db)
    if not service.get_asset(data.asset_id):
        raise HTTPException(status_code=404, detail="资产不存在")
    return service.create_maintenance(data)


@router.put("/maintenance/{record_id}/complete", response_model=MaintenanceResponse, summary="完成维保")
def complete_maintenance(record_id: int, result: str = None, db: Session = Depends(get_db)):
    service = AssetService(db)
    record = service.complete_maintenance(record_id, result)
    if not record:
        raise HTTPException(status_code=404, detail="维保记录不存在")
    return record


@router.get("/maintenance", response_model=List[MaintenanceResponse], summary="获取维保记录列表")
def get_maintenance_records(
    asset_id: Optional[int] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    service = AssetService(db)
    return service.get_maintenance_records(asset_id, skip, limit)


# ============= 资产盘点 =============
@router.post("/inventory", response_model=InventoryResponse, summary="创建盘点单")
def create_inventory(data: InventoryCreate, db: Session = Depends(get_db)):
    service = AssetService(db)
    return service.create_inventory(data)


@router.get("/inventory", response_model=List[InventoryResponse], summary="获取盘点单列表")
def get_inventory_list(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    service = AssetService(db)
    return service.get_inventory_list(skip, limit)


@router.get("/inventory/{inventory_id}/items", summary="获取盘点明细")
def get_inventory_items(inventory_id: int, db: Session = Depends(get_db)):
    service = AssetService(db)
    items = service.get_inventory_items(inventory_id)
    return {"code": 0, "data": [item.__dict__ for item in items]}


@router.put("/inventory/items/{item_id}", summary="更新盘点明细")
def update_inventory_item(item_id: int, data: InventoryItemUpdate, db: Session = Depends(get_db)):
    service = AssetService(db)
    item = service.update_inventory_item(item_id, data)
    if not item:
        raise HTTPException(status_code=404, detail="盘点明细不存在")
    return {"code": 0, "data": item.__dict__}


# ============= 统计分析 =============
@router.get("/statistics", response_model=AssetStatistics, summary="获取资产统计")
def get_statistics(db: Session = Depends(get_db)):
    service = AssetService(db)
    return service.get_statistics()


@router.get("/warranty-expiring", response_model=List[AssetResponse], summary="获取即将过保资产")
def get_warranty_expiring(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)):
    service = AssetService(db)
    assets = service.get_warranty_expiring_assets(days)
    return [{
        **asset.__dict__,
        "cabinet_name": None,
        "warranty_status": "expiring"
    } for asset in assets]
```

**Step 2: 更新API路由注册**

在 `backend/app/api/v1/__init__.py` 中添加:

```python
from .asset import router as asset_router
# 在router列表中添加
api_router.include_router(asset_router)
```

**Step 3: 验证API导入**

Run: `cd D:/mytest1/backend && python -c "from app.api.v1.asset import router; print('API router imported successfully')"`

Expected: `API router imported successfully`

---

## Task 5: 创建前端资产管理API模块

**Files:**
- Create: `frontend/src/api/modules/asset.ts`
- Modify: `frontend/src/api/modules/index.ts`

**Step 1: 创建前端API模块**

```typescript
// frontend/src/api/modules/asset.ts
import request from '@/api/request'

// ============= 类型定义 =============
export type AssetStatus = 'in_stock' | 'in_use' | 'borrowed' | 'maintenance' | 'scrapped'
export type AssetType = 'server' | 'network' | 'storage' | 'ups' | 'pdu' | 'ac' | 'cabinet' | 'sensor' | 'other'

export interface Cabinet {
  id: number
  cabinet_code: string
  cabinet_name: string
  location?: string
  row_number?: string
  column_number?: string
  total_u: number
  max_power?: number
  max_weight?: number
  used_u: number
  available_u: number
  created_at: string
  updated_at: string
}

export interface CabinetCreate {
  cabinet_code: string
  cabinet_name: string
  location?: string
  row_number?: string
  column_number?: string
  total_u?: number
  max_power?: number
  max_weight?: number
}

export interface Asset {
  id: number
  asset_code: string
  asset_name: string
  asset_type: AssetType
  brand?: string
  model?: string
  serial_number?: string
  cabinet_id?: number
  cabinet_name?: string
  u_position?: number
  u_height: number
  status: AssetStatus
  purchase_date?: string
  purchase_price?: number
  supplier?: string
  warranty_start?: string
  warranty_end?: string
  warranty_status: 'valid' | 'expired' | 'expiring' | 'unknown'
  maintenance_vendor?: string
  owner?: string
  department?: string
  specifications?: string
  remark?: string
  created_at: string
  updated_at: string
}

export interface AssetCreate {
  asset_code: string
  asset_name: string
  asset_type: AssetType
  brand?: string
  model?: string
  serial_number?: string
  cabinet_id?: number
  u_position?: number
  u_height?: number
  status?: AssetStatus
  purchase_date?: string
  purchase_price?: number
  supplier?: string
  warranty_start?: string
  warranty_end?: string
  maintenance_vendor?: string
  owner?: string
  department?: string
  specifications?: string
  remark?: string
}

export interface AssetUpdate extends Partial<AssetCreate> {}

export interface LifecycleRecord {
  id: number
  asset_id: number
  action: string
  action_date: string
  operator?: string
  from_location?: string
  to_location?: string
  remark?: string
  created_at: string
}

export interface MaintenanceRecord {
  id: number
  asset_id: number
  maintenance_type: string
  start_time: string
  end_time?: string
  technician?: string
  vendor?: string
  cost?: number
  description?: string
  result?: string
  created_at: string
}

export interface MaintenanceCreate {
  asset_id: number
  maintenance_type: string
  start_time: string
  end_time?: string
  technician?: string
  vendor?: string
  cost?: number
  description?: string
}

export interface InventoryRecord {
  id: number
  inventory_code: string
  inventory_date: string
  operator?: string
  status: 'pending' | 'completed'
  total_count: number
  checked_count: number
  matched_count: number
  unmatched_count: number
  remark?: string
  created_at: string
  completed_at?: string
}

export interface AssetStatistics {
  total_count: number
  in_stock_count: number
  in_use_count: number
  borrowed_count: number
  maintenance_count: number
  scrapped_count: number
  total_value: number
  warranty_expiring_count: number
  by_type: Record<string, number>
  by_department: Record<string, number>
}

export interface CabinetUsage {
  cabinet_id: number
  cabinet_code: string
  total_u: number
  used_u: number
  available_u: number
  usage_rate: number
  u_map: Record<number, { asset_id: number; asset_name: string; asset_code: string }>
}

// ============= 机柜管理 API =============
export function getCabinets(params?: { skip?: number; limit?: number }) {
  return request.get<Cabinet[]>('/v1/asset/cabinets', { params })
}

export function getCabinet(cabinetId: number) {
  return request.get<Cabinet>(`/v1/asset/cabinets/${cabinetId}`)
}

export function getCabinetUsage(cabinetId: number) {
  return request.get<{ code: number; data: CabinetUsage }>(`/v1/asset/cabinets/${cabinetId}/usage`)
}

export function createCabinet(data: CabinetCreate) {
  return request.post<Cabinet>('/v1/asset/cabinets', data)
}

export function updateCabinet(cabinetId: number, data: Partial<CabinetCreate>) {
  return request.put<Cabinet>(`/v1/asset/cabinets/${cabinetId}`, data)
}

export function deleteCabinet(cabinetId: number) {
  return request.delete(`/v1/asset/cabinets/${cabinetId}`)
}

// ============= 资产管理 API =============
export function getAssets(params?: {
  skip?: number
  limit?: number
  asset_type?: AssetType
  status?: AssetStatus
  cabinet_id?: number
  keyword?: string
}) {
  return request.get<Asset[]>('/v1/asset/assets', { params })
}

export function getAsset(assetId: number) {
  return request.get<Asset>(`/v1/asset/assets/${assetId}`)
}

export function createAsset(data: AssetCreate) {
  return request.post<Asset>('/v1/asset/assets', data)
}

export function updateAsset(assetId: number, data: AssetUpdate) {
  return request.put<Asset>(`/v1/asset/assets/${assetId}`, data)
}

export function deleteAsset(assetId: number) {
  return request.delete(`/v1/asset/assets/${assetId}`)
}

export function getAssetLifecycle(assetId: number) {
  return request.get<LifecycleRecord[]>(`/v1/asset/assets/${assetId}/lifecycle`)
}

// ============= 维保管理 API =============
export function createMaintenance(data: MaintenanceCreate) {
  return request.post<MaintenanceRecord>('/v1/asset/maintenance', data)
}

export function completeMaintenance(recordId: number, result?: string) {
  return request.put<MaintenanceRecord>(`/v1/asset/maintenance/${recordId}/complete`, null, {
    params: { result }
  })
}

export function getMaintenanceRecords(params?: { asset_id?: number; skip?: number; limit?: number }) {
  return request.get<MaintenanceRecord[]>('/v1/asset/maintenance', { params })
}

// ============= 资产盘点 API =============
export function createInventory(data: { inventory_date: string; operator?: string; remark?: string }) {
  return request.post<InventoryRecord>('/v1/asset/inventory', data)
}

export function getInventoryList(params?: { skip?: number; limit?: number }) {
  return request.get<InventoryRecord[]>('/v1/asset/inventory', { params })
}

export function getInventoryItems(inventoryId: number) {
  return request.get<{ code: number; data: any[] }>(`/v1/asset/inventory/${inventoryId}/items`)
}

export function updateInventoryItem(itemId: number, data: { actual_location?: string; is_matched?: number; remark?: string }) {
  return request.put(`/v1/asset/inventory/items/${itemId}`, data)
}

// ============= 统计分析 API =============
export function getAssetStatistics() {
  return request.get<AssetStatistics>('/v1/asset/statistics')
}

export function getWarrantyExpiringAssets(days: number = 30) {
  return request.get<Asset[]>('/v1/asset/warranty-expiring', { params: { days } })
}
```

**Step 2: 更新API模块导出**

在 `frontend/src/api/modules/index.ts` 中添加:

```typescript
export * from './asset'
```

---

## Task 6: 创建前端资产管理页面

**Files:**
- Create: `frontend/src/views/asset/index.vue`
- Create: `frontend/src/views/asset/cabinet.vue`

**Step 1: 创建资产列表页面**

```vue
<!-- frontend/src/views/asset/index.vue -->
<template>
  <div class="asset-page">
    <!-- 统计卡片 -->
    <el-row :gutter="20" class="stat-cards">
      <el-col :span="4">
        <div class="stat-card">
          <div class="stat-value">{{ statistics.total_count }}</div>
          <div class="stat-label">资产总数</div>
        </div>
      </el-col>
      <el-col :span="4">
        <div class="stat-card">
          <div class="stat-value text-success">{{ statistics.in_use_count }}</div>
          <div class="stat-label">在用</div>
        </div>
      </el-col>
      <el-col :span="4">
        <div class="stat-card">
          <div class="stat-value text-warning">{{ statistics.in_stock_count }}</div>
          <div class="stat-label">在库</div>
        </div>
      </el-col>
      <el-col :span="4">
        <div class="stat-card">
          <div class="stat-value text-error">{{ statistics.maintenance_count }}</div>
          <div class="stat-label">维修中</div>
        </div>
      </el-col>
      <el-col :span="4">
        <div class="stat-card">
          <div class="stat-value">¥{{ (statistics.total_value / 10000).toFixed(1) }}万</div>
          <div class="stat-label">资产总值</div>
        </div>
      </el-col>
      <el-col :span="4">
        <div class="stat-card" :class="{ 'has-warning': statistics.warranty_expiring_count > 0 }">
          <div class="stat-value">{{ statistics.warranty_expiring_count }}</div>
          <div class="stat-label">即将过保</div>
        </div>
      </el-col>
    </el-row>

    <!-- 工具栏 -->
    <el-card class="toolbar-card">
      <el-row :gutter="16">
        <el-col :span="4">
          <el-select v-model="filters.asset_type" placeholder="资产类型" clearable @change="loadAssets">
            <el-option label="服务器" value="server" />
            <el-option label="网络设备" value="network" />
            <el-option label="存储设备" value="storage" />
            <el-option label="UPS" value="ups" />
            <el-option label="PDU" value="pdu" />
            <el-option label="空调" value="ac" />
            <el-option label="机柜" value="cabinet" />
            <el-option label="传感器" value="sensor" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-col>
        <el-col :span="4">
          <el-select v-model="filters.status" placeholder="资产状态" clearable @change="loadAssets">
            <el-option label="在库" value="in_stock" />
            <el-option label="在用" value="in_use" />
            <el-option label="借用中" value="borrowed" />
            <el-option label="维修中" value="maintenance" />
            <el-option label="已报废" value="scrapped" />
          </el-select>
        </el-col>
        <el-col :span="6">
          <el-input v-model="filters.keyword" placeholder="搜索资产名称/编码/序列号" clearable @keyup.enter="loadAssets">
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </el-col>
        <el-col :span="10" class="toolbar-right">
          <el-button type="primary" :icon="Plus" @click="showAddDialog">新增资产</el-button>
          <el-button :icon="Upload">批量导入</el-button>
          <el-button :icon="Download">导出</el-button>
        </el-col>
      </el-row>
    </el-card>

    <!-- 资产列表 -->
    <el-card class="table-card">
      <el-table :data="assets" v-loading="loading" stripe>
        <el-table-column prop="asset_code" label="资产编码" width="140" />
        <el-table-column prop="asset_name" label="资产名称" min-width="150" />
        <el-table-column prop="asset_type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag size="small">{{ getTypeName(row.asset_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="brand" label="品牌" width="100" />
        <el-table-column prop="model" label="型号" width="120" />
        <el-table-column prop="cabinet_name" label="位置" width="120" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusName(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="owner" label="责任人" width="100" />
        <el-table-column prop="warranty_status" label="质保" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.warranty_status === 'valid'" type="success" size="small">有效</el-tag>
            <el-tag v-else-if="row.warranty_status === 'expired'" type="danger" size="small">过期</el-tag>
            <el-tag v-else-if="row.warranty_status === 'expiring'" type="warning" size="small">即将过期</el-tag>
            <span v-else class="text-secondary">-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="viewAsset(row)">详情</el-button>
            <el-button type="primary" link size="small" @click="editAsset(row)">编辑</el-button>
            <el-button type="warning" link size="small" @click="showMaintenanceDialog(row)">维保</el-button>
            <el-button type="danger" link size="small" @click="confirmDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.size"
        :total="pagination.total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @size-change="loadAssets"
        @current-change="loadAssets"
      />
    </el-card>

    <!-- 新增/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑资产' : '新增资产'" width="700px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="资产编码" prop="asset_code">
              <el-input v-model="form.asset_code" :disabled="isEdit" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="资产名称" prop="asset_name">
              <el-input v-model="form.asset_name" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="资产类型" prop="asset_type">
              <el-select v-model="form.asset_type" style="width: 100%">
                <el-option label="服务器" value="server" />
                <el-option label="网络设备" value="network" />
                <el-option label="存储设备" value="storage" />
                <el-option label="UPS" value="ups" />
                <el-option label="PDU" value="pdu" />
                <el-option label="空调" value="ac" />
                <el-option label="机柜" value="cabinet" />
                <el-option label="传感器" value="sensor" />
                <el-option label="其他" value="other" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态" prop="status">
              <el-select v-model="form.status" style="width: 100%">
                <el-option label="在库" value="in_stock" />
                <el-option label="在用" value="in_use" />
                <el-option label="借用中" value="borrowed" />
                <el-option label="维修中" value="maintenance" />
                <el-option label="已报废" value="scrapped" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="品牌">
              <el-input v-model="form.brand" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="型号">
              <el-input v-model="form.model" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="序列号">
              <el-input v-model="form.serial_number" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="责任人">
              <el-input v-model="form.owner" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="所属部门">
              <el-input v-model="form.department" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="供应商">
              <el-input v-model="form.supplier" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="购置日期">
              <el-date-picker v-model="form.purchase_date" type="date" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="购置价格">
              <el-input-number v-model="form.purchase_price" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="质保开始">
              <el-date-picker v-model="form.warranty_start" type="date" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="质保结束">
              <el-date-picker v-model="form.warranty_end" type="date" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="备注">
              <el-input v-model="form.remark" type="textarea" :rows="2" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance } from 'element-plus'
import { Search, Plus, Upload, Download } from '@element-plus/icons-vue'
import {
  getAssets, getAssetStatistics, createAsset, updateAsset, deleteAsset,
  type Asset, type AssetCreate, type AssetStatistics, type AssetType, type AssetStatus
} from '@/api/modules/asset'

const loading = ref(false)
const assets = ref<Asset[]>([])
const statistics = ref<AssetStatistics>({
  total_count: 0, in_stock_count: 0, in_use_count: 0, borrowed_count: 0,
  maintenance_count: 0, scrapped_count: 0, total_value: 0, warranty_expiring_count: 0,
  by_type: {}, by_department: {}
})

const filters = reactive({
  asset_type: '' as AssetType | '',
  status: '' as AssetStatus | '',
  keyword: ''
})

const pagination = reactive({
  page: 1,
  size: 20,
  total: 0
})

const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref<FormInstance>()
const form = reactive<AssetCreate>({
  asset_code: '',
  asset_name: '',
  asset_type: 'server',
  status: 'in_stock'
})

const rules = {
  asset_code: [{ required: true, message: '请输入资产编码', trigger: 'blur' }],
  asset_name: [{ required: true, message: '请输入资产名称', trigger: 'blur' }],
  asset_type: [{ required: true, message: '请选择资产类型', trigger: 'change' }]
}

const typeNameMap: Record<string, string> = {
  server: '服务器', network: '网络设备', storage: '存储设备',
  ups: 'UPS', pdu: 'PDU', ac: '空调', cabinet: '机柜', sensor: '传感器', other: '其他'
}

const statusNameMap: Record<string, string> = {
  in_stock: '在库', in_use: '在用', borrowed: '借用中', maintenance: '维修中', scrapped: '已报废'
}

function getTypeName(type: string) { return typeNameMap[type] || type }
function getStatusName(status: string) { return statusNameMap[status] || status }
function getStatusType(status: string) {
  const map: Record<string, string> = { in_use: 'success', in_stock: 'warning', maintenance: 'danger', scrapped: 'info' }
  return map[status] || 'info'
}

async function loadAssets() {
  loading.value = true
  try {
    const params: any = {
      skip: (pagination.page - 1) * pagination.size,
      limit: pagination.size
    }
    if (filters.asset_type) params.asset_type = filters.asset_type
    if (filters.status) params.status = filters.status
    if (filters.keyword) params.keyword = filters.keyword

    assets.value = await getAssets(params)
    pagination.total = assets.value.length // 简化处理，实际应返回total
  } finally {
    loading.value = false
  }
}

async function loadStatistics() {
  try {
    statistics.value = await getAssetStatistics()
  } catch (e) {
    console.error('加载统计失败', e)
  }
}

function showAddDialog() {
  isEdit.value = false
  Object.assign(form, {
    asset_code: '', asset_name: '', asset_type: 'server', status: 'in_stock',
    brand: '', model: '', serial_number: '', owner: '', department: '', supplier: '',
    purchase_date: undefined, purchase_price: undefined, warranty_start: undefined, warranty_end: undefined, remark: ''
  })
  dialogVisible.value = true
}

function editAsset(asset: Asset) {
  isEdit.value = true
  Object.assign(form, asset)
  dialogVisible.value = true
}

function viewAsset(asset: Asset) {
  // TODO: 显示详情弹窗
  ElMessage.info('查看资产详情: ' + asset.asset_name)
}

function showMaintenanceDialog(asset: Asset) {
  // TODO: 显示维保弹窗
  ElMessage.info('维保记录: ' + asset.asset_name)
}

async function submitForm() {
  const valid = await formRef.value?.validate()
  if (!valid) return

  try {
    if (isEdit.value) {
      await updateAsset((form as any).id, form)
      ElMessage.success('更新成功')
    } else {
      await createAsset(form)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadAssets()
    loadStatistics()
  } catch (e) {
    console.error('保存失败', e)
  }
}

function confirmDelete(asset: Asset) {
  ElMessageBox.confirm(`确定删除资产 "${asset.asset_name}" 吗？`, '删除确认', {
    type: 'warning'
  }).then(async () => {
    await deleteAsset(asset.id)
    ElMessage.success('删除成功')
    loadAssets()
    loadStatistics()
  }).catch(() => {})
}

onMounted(() => {
  loadAssets()
  loadStatistics()
})
</script>

<style scoped lang="scss">
.asset-page {
  .stat-cards {
    margin-bottom: 20px;
  }

  .stat-card {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-lg);
    padding: 20px;
    text-align: center;

    .stat-value {
      font-size: 28px;
      font-weight: bold;
      color: var(--text-primary);
      margin-bottom: 8px;

      &.text-success { color: var(--success-color); }
      &.text-warning { color: var(--warning-color); }
      &.text-error { color: var(--error-color); }
    }

    .stat-label {
      font-size: 14px;
      color: var(--text-secondary);
    }

    &.has-warning {
      border-color: var(--warning-color);
      .stat-value { color: var(--warning-color); }
    }
  }

  .toolbar-card {
    margin-bottom: 20px;
    background: var(--bg-card);
    border-color: var(--border-color);

    .toolbar-right {
      text-align: right;
    }
  }

  .table-card {
    background: var(--bg-card);
    border-color: var(--border-color);

    .el-pagination {
      margin-top: 16px;
      justify-content: flex-end;
    }
  }
}
</style>
```

**Step 2: 创建机柜管理页面** (简化版)

```vue
<!-- frontend/src/views/asset/cabinet.vue -->
<template>
  <div class="cabinet-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>机柜管理</span>
          <el-button type="primary" :icon="Plus" @click="showAddDialog">新增机柜</el-button>
        </div>
      </template>

      <el-table :data="cabinets" v-loading="loading" stripe>
        <el-table-column prop="cabinet_code" label="机柜编码" width="120" />
        <el-table-column prop="cabinet_name" label="机柜名称" min-width="150" />
        <el-table-column prop="location" label="位置" width="150" />
        <el-table-column prop="total_u" label="总U数" width="80" />
        <el-table-column label="使用情况" width="180">
          <template #default="{ row }">
            <el-progress
              :percentage="Math.round((row.used_u / row.total_u) * 100)"
              :color="getProgressColor(row.used_u / row.total_u)"
            />
            <span class="usage-text">{{ row.used_u }}/{{ row.total_u }} U</span>
          </template>
        </el-table-column>
        <el-table-column prop="max_power" label="最大功率(kW)" width="120" />
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="viewUsage(row)">U位图</el-button>
            <el-button type="primary" link size="small" @click="editCabinet(row)">编辑</el-button>
            <el-button type="danger" link size="small" @click="confirmDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { getCabinets, deleteCabinet, type Cabinet } from '@/api/modules/asset'

const loading = ref(false)
const cabinets = ref<Cabinet[]>([])

function getProgressColor(rate: number) {
  if (rate < 0.6) return '#52c41a'
  if (rate < 0.8) return '#faad14'
  return '#f5222d'
}

async function loadCabinets() {
  loading.value = true
  try {
    cabinets.value = await getCabinets()
  } finally {
    loading.value = false
  }
}

function showAddDialog() {
  ElMessage.info('新增机柜')
}

function editCabinet(cabinet: Cabinet) {
  ElMessage.info('编辑机柜: ' + cabinet.cabinet_name)
}

function viewUsage(cabinet: Cabinet) {
  ElMessage.info('查看U位图: ' + cabinet.cabinet_name)
}

function confirmDelete(cabinet: Cabinet) {
  ElMessageBox.confirm(`确定删除机柜 "${cabinet.cabinet_name}" 吗？`, '删除确认', {
    type: 'warning'
  }).then(async () => {
    await deleteCabinet(cabinet.id)
    ElMessage.success('删除成功')
    loadCabinets()
  }).catch(() => {})
}

onMounted(() => {
  loadCabinets()
})
</script>

<style scoped lang="scss">
.cabinet-page {
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .usage-text {
    font-size: 12px;
    color: var(--text-secondary);
    margin-left: 8px;
  }
}
</style>
```

---

## Task 7: 添加路由配置

**Files:**
- Modify: `frontend/src/router/index.ts`

**Step 1: 添加资产管理路由**

在路由配置中添加:

```typescript
// 在能源管理路由后添加
{
  path: '/asset',
  name: 'Asset',
  component: MainLayout,
  redirect: '/asset/list',
  meta: { title: '资产管理' },
  children: [
    {
      path: 'list',
      name: 'AssetList',
      component: () => import('@/views/asset/index.vue'),
      meta: { title: '资产台账' }
    },
    {
      path: 'cabinet',
      name: 'CabinetManage',
      component: () => import('@/views/asset/cabinet.vue'),
      meta: { title: '机柜管理' }
    }
  ]
}
```

**Step 2: 更新主布局菜单**

在 `MainLayout.vue` 的菜单中添加资产管理入口。

---

## Task 8: 构建验证

**Step 1: 验证后端**

Run: `cd D:/mytest1/backend && python -c "from app.models.asset import *; from app.services.asset import *; from app.api.v1.asset import *; print('Backend OK')"`

Expected: `Backend OK`

**Step 2: 验证前端构建**

Run: `cd D:/mytest1/frontend && npm run build`

Expected: 构建成功，无错误

---

## 总结

本计划实现了完整的资产管理模块，包括:

1. **数据库模型**: Asset, Cabinet, AssetLifecycle, MaintenanceRecord, AssetInventory
2. **后端服务**: AssetService 提供完整的CRUD和业务逻辑
3. **API端点**: 机柜管理、资产管理、维保管理、盘点管理、统计分析
4. **前端页面**: 资产列表页、机柜管理页

与行业DCIM系统对齐的功能:
- 资产台账管理
- 资产全生命周期追踪
- 资产盘点
- 维保管理
- 资产统计分析
- 质保到期预警
