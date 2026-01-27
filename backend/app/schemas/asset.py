"""
资产管理数据模型
"""
from typing import Optional, List, Dict
from pydantic import BaseModel, Field
from datetime import datetime, date

from app.models.asset import AssetStatus, AssetType


# ==================== 机柜 Schemas ====================

class CabinetBase(BaseModel):
    """机柜基础模型"""
    cabinet_code: str = Field(..., description="机柜编码")
    cabinet_name: str = Field(..., description="机柜名称")
    location: Optional[str] = Field(None, description="位置")
    row_number: Optional[str] = Field(None, description="列号")
    column_number: Optional[str] = Field(None, description="排号")
    total_u: int = Field(42, description="总U数")
    max_power: Optional[float] = Field(None, description="最大功率 kW")
    max_weight: Optional[float] = Field(None, description="最大承重 kg")


class CabinetCreate(CabinetBase):
    """创建机柜"""
    pass


class CabinetUpdate(BaseModel):
    """更新机柜"""
    cabinet_code: Optional[str] = Field(None, description="机柜编码")
    cabinet_name: Optional[str] = Field(None, description="机柜名称")
    location: Optional[str] = Field(None, description="位置")
    row_number: Optional[str] = Field(None, description="列号")
    column_number: Optional[str] = Field(None, description="排号")
    total_u: Optional[int] = Field(None, description="总U数")
    max_power: Optional[float] = Field(None, description="最大功率 kW")
    max_weight: Optional[float] = Field(None, description="最大承重 kg")


class CabinetResponse(CabinetBase):
    """机柜响应"""
    id: int = Field(..., description="机柜ID")
    used_u: int = Field(0, description="已使用U数")
    available_u: int = Field(42, description="可用U数")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    class Config:
        from_attributes = True


# ==================== 资产 Schemas ====================

class AssetBase(BaseModel):
    """资产基础模型"""
    asset_code: str = Field(..., description="资产编码")
    asset_name: str = Field(..., description="资产名称")
    asset_type: AssetType = Field(..., description="资产类型")
    brand: Optional[str] = Field(None, description="品牌")
    model: Optional[str] = Field(None, description="型号")
    serial_number: Optional[str] = Field(None, description="序列号")
    # 机柜位置
    cabinet_id: Optional[int] = Field(None, description="机柜ID")
    u_position: Optional[int] = Field(None, description="U位起始位置")
    u_height: Optional[int] = Field(None, description="占用U数")
    # 资产状态
    status: AssetStatus = Field(AssetStatus.in_stock, description="资产状态")
    # 采购信息
    purchase_date: Optional[date] = Field(None, description="采购日期")
    purchase_price: Optional[float] = Field(None, description="采购价格")
    supplier: Optional[str] = Field(None, description="供应商")
    # 保修信息
    warranty_start: Optional[date] = Field(None, description="保修开始日期")
    warranty_end: Optional[date] = Field(None, description="保修结束日期")
    maintenance_vendor: Optional[str] = Field(None, description="维保厂商")
    # 归属信息
    owner: Optional[str] = Field(None, description="负责人")
    department: Optional[str] = Field(None, description="所属部门")
    # 其他信息
    specifications: Optional[str] = Field(None, description="规格参数(JSON格式)")
    remark: Optional[str] = Field(None, description="备注")


class AssetCreate(AssetBase):
    """创建资产"""
    pass


class AssetUpdate(BaseModel):
    """更新资产"""
    asset_code: Optional[str] = Field(None, description="资产编码")
    asset_name: Optional[str] = Field(None, description="资产名称")
    asset_type: Optional[AssetType] = Field(None, description="资产类型")
    brand: Optional[str] = Field(None, description="品牌")
    model: Optional[str] = Field(None, description="型号")
    serial_number: Optional[str] = Field(None, description="序列号")
    # 机柜位置
    cabinet_id: Optional[int] = Field(None, description="机柜ID")
    u_position: Optional[int] = Field(None, description="U位起始位置")
    u_height: Optional[int] = Field(None, description="占用U数")
    # 资产状态
    status: Optional[AssetStatus] = Field(None, description="资产状态")
    # 采购信息
    purchase_date: Optional[date] = Field(None, description="采购日期")
    purchase_price: Optional[float] = Field(None, description="采购价格")
    supplier: Optional[str] = Field(None, description="供应商")
    # 保修信息
    warranty_start: Optional[date] = Field(None, description="保修开始日期")
    warranty_end: Optional[date] = Field(None, description="保修结束日期")
    maintenance_vendor: Optional[str] = Field(None, description="维保厂商")
    # 归属信息
    owner: Optional[str] = Field(None, description="负责人")
    department: Optional[str] = Field(None, description="所属部门")
    # 其他信息
    specifications: Optional[str] = Field(None, description="规格参数(JSON格式)")
    remark: Optional[str] = Field(None, description="备注")


class AssetResponse(AssetBase):
    """资产响应"""
    id: int = Field(..., description="资产ID")
    cabinet_name: Optional[str] = Field(None, description="机柜名称")
    warranty_status: str = Field("unknown", description="保修状态: valid/expiring/expired/unknown")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    class Config:
        from_attributes = True


# ==================== 资产生命周期 Schemas ====================

class LifecycleCreate(BaseModel):
    """创建资产生命周期记录"""
    asset_id: int = Field(..., description="资产ID")
    action: str = Field(..., description="操作类型: purchase/deploy/move/maintain/scrap等")
    action_date: datetime = Field(..., description="操作日期")
    operator: Optional[str] = Field(None, description="操作人")
    from_location: Optional[str] = Field(None, description="原位置")
    to_location: Optional[str] = Field(None, description="新位置")
    remark: Optional[str] = Field(None, description="备注")


class LifecycleResponse(BaseModel):
    """资产生命周期响应"""
    id: int = Field(..., description="记录ID")
    asset_id: int = Field(..., description="资产ID")
    action: str = Field(..., description="操作类型")
    action_date: datetime = Field(..., description="操作日期")
    operator: Optional[str] = Field(None, description="操作人")
    from_location: Optional[str] = Field(None, description="原位置")
    to_location: Optional[str] = Field(None, description="新位置")
    remark: Optional[str] = Field(None, description="备注")
    created_at: datetime = Field(..., description="创建时间")

    class Config:
        from_attributes = True


# ==================== 维护记录 Schemas ====================

class MaintenanceCreate(BaseModel):
    """创建维护记录"""
    asset_id: int = Field(..., description="资产ID")
    maintenance_type: str = Field(..., description="维护类型: routine/repair/upgrade等")
    start_time: datetime = Field(..., description="开始时间")
    end_time: Optional[datetime] = Field(None, description="结束时间")
    technician: Optional[str] = Field(None, description="维护人员")
    vendor: Optional[str] = Field(None, description="维护厂商")
    cost: Optional[float] = Field(None, description="维护费用")
    description: Optional[str] = Field(None, description="维护描述")
    result: Optional[str] = Field(None, description="维护结果")


class MaintenanceResponse(BaseModel):
    """维护记录响应"""
    id: int = Field(..., description="记录ID")
    asset_id: int = Field(..., description="资产ID")
    maintenance_type: str = Field(..., description="维护类型")
    start_time: datetime = Field(..., description="开始时间")
    end_time: Optional[datetime] = Field(None, description="结束时间")
    technician: Optional[str] = Field(None, description="维护人员")
    vendor: Optional[str] = Field(None, description="维护厂商")
    cost: Optional[float] = Field(None, description="维护费用")
    description: Optional[str] = Field(None, description="维护描述")
    result: Optional[str] = Field(None, description="维护结果")
    created_at: datetime = Field(..., description="创建时间")

    class Config:
        from_attributes = True


# ==================== 资产盘点 Schemas ====================

class InventoryCreate(BaseModel):
    """创建资产盘点"""
    inventory_code: str = Field(..., description="盘点编码")
    inventory_date: date = Field(..., description="盘点日期")
    operator: Optional[str] = Field(None, description="盘点人")
    remark: Optional[str] = Field(None, description="备注")


class InventoryItemUpdate(BaseModel):
    """更新盘点明细"""
    actual_location: Optional[str] = Field(None, description="实际位置")
    is_matched: bool = Field(..., description="是否匹配")
    check_time: Optional[datetime] = Field(None, description="盘点时间")
    remark: Optional[str] = Field(None, description="备注")


class InventoryItemResponse(BaseModel):
    """盘点明细响应"""
    id: int = Field(..., description="明细ID")
    inventory_id: int = Field(..., description="盘点ID")
    asset_id: int = Field(..., description="资产ID")
    expected_location: Optional[str] = Field(None, description="预期位置")
    actual_location: Optional[str] = Field(None, description="实际位置")
    is_matched: bool = Field(False, description="是否匹配")
    check_time: Optional[datetime] = Field(None, description="盘点时间")
    remark: Optional[str] = Field(None, description="备注")

    class Config:
        from_attributes = True


class InventoryResponse(BaseModel):
    """资产盘点响应"""
    id: int = Field(..., description="盘点ID")
    inventory_code: str = Field(..., description="盘点编码")
    inventory_date: date = Field(..., description="盘点日期")
    operator: Optional[str] = Field(None, description="盘点人")
    status: str = Field("pending", description="盘点状态: pending/in_progress/completed")
    total_count: int = Field(0, description="总数量")
    checked_count: int = Field(0, description="已盘点数量")
    matched_count: int = Field(0, description="匹配数量")
    unmatched_count: int = Field(0, description="不匹配数量")
    remark: Optional[str] = Field(None, description="备注")
    created_at: datetime = Field(..., description="创建时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    items: List[InventoryItemResponse] = Field(default_factory=list, description="盘点明细")

    class Config:
        from_attributes = True


# ==================== 资产统计 Schemas ====================

class AssetStatistics(BaseModel):
    """资产统计信息"""
    total_count: int = Field(..., description="资产总数")
    by_status: Dict[str, int] = Field(default_factory=dict, description="按状态统计")
    by_type: Dict[str, int] = Field(default_factory=dict, description="按类型统计")
    by_department: Dict[str, int] = Field(default_factory=dict, description="按部门统计")
    total_value: float = Field(0, description="资产总价值")
    warranty_expiring_count: int = Field(0, description="保修即将到期数量(30天内)")
