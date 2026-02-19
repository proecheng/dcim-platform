"""
空间拓扑数据模型
"""
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime


# ==================== Site Schemas ====================

class SiteCreate(BaseModel):
    """创建站点"""
    site_code: str = Field(..., description="站点编码")
    site_name: str = Field(..., description="站点名称")
    address: Optional[str] = Field(None, description="地址")
    contact_person: Optional[str] = Field(None, description="联系人")
    contact_phone: Optional[str] = Field(None, description="联系电话")
    contact_email: Optional[str] = Field(None, description="联系邮箱")
    network_config: Optional[dict] = Field(None, description="网络配置(VPN/专线信息)")
    description: Optional[str] = Field(None, description="描述")


class SiteUpdate(BaseModel):
    """更新站点"""
    site_code: Optional[str] = Field(None, description="站点编码")
    site_name: Optional[str] = Field(None, description="站点名称")
    address: Optional[str] = Field(None, description="地址")
    contact_person: Optional[str] = Field(None, description="联系人")
    contact_phone: Optional[str] = Field(None, description="联系电话")
    contact_email: Optional[str] = Field(None, description="联系邮箱")
    network_config: Optional[dict] = Field(None, description="网络配置(VPN/专线信息)")
    description: Optional[str] = Field(None, description="描述")


class SiteResponse(BaseModel):
    """站点响应"""
    id: int = Field(..., description="站点ID")
    site_code: str = Field(..., description="站点编码")
    site_name: str = Field(..., description="站点名称")
    address: Optional[str] = Field(None, description="地址")
    contact_person: Optional[str] = Field(None, description="联系人")
    contact_phone: Optional[str] = Field(None, description="联系电话")
    contact_email: Optional[str] = Field(None, description="联系邮箱")
    network_config: Optional[dict] = Field(None, description="网络配置")
    status: str = Field("active", description="状态")
    description: Optional[str] = Field(None, description="描述")
    gateway_count: int = Field(0, description="网关数量")
    device_count: int = Field(0, description="设备数量")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    class Config:
        from_attributes = True


class SiteSummaryItem(BaseModel):
    """站点汇总项"""
    id: int = Field(..., description="站点ID")
    site_code: str = Field(..., description="站点编码")
    site_name: str = Field(..., description="站点名称")
    status: str = Field("active", description="状态")
    gateway_count: int = Field(0, description="网关数量")
    device_count: int = Field(0, description="设备数量")
    active_alarm_count: int = Field(0, description="活跃告警数")


class SiteSummaryResponse(BaseModel):
    """跨站点汇总响应"""
    total_sites: int = Field(0, description="站点总数")
    total_gateways: int = Field(0, description="网关总数")
    total_devices: int = Field(0, description="设备总数")
    total_alarms: int = Field(0, description="活跃告警总数")
    sites: List[SiteSummaryItem] = Field(default_factory=list, description="各站点摘要")


# ==================== Floor Schemas ====================

class FloorCreate(BaseModel):
    """创建楼层"""
    floor_code: str = Field(..., description="楼层编码")
    floor_name: str = Field(..., description="楼层名称")
    site_id: int = Field(..., description="所属站点ID")
    sort_order: int = Field(0, description="排序")


class FloorUpdate(BaseModel):
    """更新楼层"""
    floor_code: Optional[str] = Field(None, description="楼层编码")
    floor_name: Optional[str] = Field(None, description="楼层名称")
    site_id: Optional[int] = Field(None, description="所属站点ID")
    sort_order: Optional[int] = Field(None, description="排序")


class FloorResponse(BaseModel):
    """楼层响应"""
    id: int = Field(..., description="楼层ID")
    floor_code: str = Field(..., description="楼层编码")
    floor_name: str = Field(..., description="楼层名称")
    site_id: int = Field(..., description="所属站点ID")
    sort_order: int = Field(0, description="排序")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    class Config:
        from_attributes = True


# ==================== Room Schemas ====================

class RoomCreate(BaseModel):
    """创建房间"""
    room_code: str = Field(..., description="房间编码")
    room_name: str = Field(..., description="房间名称")
    floor_id: int = Field(..., description="所属楼层ID")
    grid_cols: int = Field(20, description="网格列数")
    grid_rows: int = Field(20, description="网格行数")
    area_sqm: Optional[float] = Field(None, description="面积(平方米)")
    description: Optional[str] = Field(None, description="描述")


class RoomUpdate(BaseModel):
    """更新房间"""
    room_code: Optional[str] = Field(None, description="房间编码")
    room_name: Optional[str] = Field(None, description="房间名称")
    floor_id: Optional[int] = Field(None, description="所属楼层ID")
    grid_cols: Optional[int] = Field(None, description="网格列数")
    grid_rows: Optional[int] = Field(None, description="网格行数")
    area_sqm: Optional[float] = Field(None, description="面积(平方米)")
    description: Optional[str] = Field(None, description="描述")


class RoomResponse(BaseModel):
    """房间响应"""
    id: int = Field(..., description="房间ID")
    room_code: str = Field(..., description="房间编码")
    room_name: str = Field(..., description="房间名称")
    floor_id: int = Field(..., description="所属楼层ID")
    grid_cols: int = Field(20, description="网格列数")
    grid_rows: int = Field(20, description="网格行数")
    area_sqm: Optional[float] = Field(None, description="面积(平方米)")
    description: Optional[str] = Field(None, description="描述")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    class Config:
        from_attributes = True


# ==================== Row Schemas ====================

class RowCreate(BaseModel):
    """创建行"""
    row_code: str = Field(..., description="行编码")
    row_name: str = Field(..., description="行名称")
    room_id: int = Field(..., description="所属房间ID")
    aisle_type: str = Field("none", description="通道类型: cold/hot/none")
    sort_order: int = Field(0, description="排序")


class RowUpdate(BaseModel):
    """更新行"""
    row_code: Optional[str] = Field(None, description="行编码")
    row_name: Optional[str] = Field(None, description="行名称")
    room_id: Optional[int] = Field(None, description="所属房间ID")
    aisle_type: Optional[str] = Field(None, description="通道类型: cold/hot/none")
    sort_order: Optional[int] = Field(None, description="排序")


class RowResponse(BaseModel):
    """行响应"""
    id: int = Field(..., description="行ID")
    row_code: str = Field(..., description="行编码")
    row_name: str = Field(..., description="行名称")
    room_id: int = Field(..., description="所属房间ID")
    aisle_type: str = Field("none", description="通道类型: cold/hot/none")
    sort_order: int = Field(0, description="排序")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    class Config:
        from_attributes = True


# ==================== LayoutTemplate Schemas ====================

class LayoutTemplateResponse(BaseModel):
    """布局模板响应"""
    id: int = Field(..., description="模板ID")
    template_code: str = Field(..., description="模板编码")
    template_name: str = Field(..., description="模板名称")
    description: Optional[str] = Field(None, description="描述")
    template_data: Optional[str] = Field(None, description="JSON格式模板数据")
    created_at: datetime = Field(..., description="创建时间")

    class Config:
        from_attributes = True


# ==================== Cabinet Position ====================

class CabinetPositionUpdate(BaseModel):
    """更新机柜空间位置"""
    row_id: Optional[int] = Field(None, description="所属行ID")
    aisle_type: Optional[str] = Field(None, description="通道类型: cold/hot/none")
    grid_x: Optional[int] = Field(None, description="网格X坐标")
    grid_y: Optional[int] = Field(None, description="网格Y坐标")


# ==================== Tree Response ====================

class TreeCabinetItem(BaseModel):
    """树形结构中的机柜简要信息"""
    id: int
    cabinet_code: str
    cabinet_name: str
    aisle_type: Optional[str] = None
    grid_x: Optional[int] = None
    grid_y: Optional[int] = None

    class Config:
        from_attributes = True


class TreeRowItem(BaseModel):
    """树形结构中的行"""
    id: int
    row_code: str
    row_name: str
    aisle_type: str = "none"
    cabinets: List[TreeCabinetItem] = []

    class Config:
        from_attributes = True


class TreeRoomItem(BaseModel):
    """树形结构中的房间"""
    id: int
    room_code: str
    room_name: str
    grid_cols: int = 20
    grid_rows: int = 20
    rows: List[TreeRowItem] = []

    class Config:
        from_attributes = True


class TreeFloorItem(BaseModel):
    """树形结构中的楼层"""
    id: int
    floor_code: str
    floor_name: str
    sort_order: int = 0
    rooms: List[TreeRoomItem] = []

    class Config:
        from_attributes = True


class SpatialTreeResponse(BaseModel):
    """空间拓扑树形响应"""
    id: int
    site_code: str
    site_name: str
    floors: List[TreeFloorItem] = []

    class Config:
        from_attributes = True


# ==================== Import/Export ====================

class ImportResultResponse(BaseModel):
    """导入结果响应"""
    total: int = Field(0, description="总行数")
    success: int = Field(0, description="成功数")
    failed: int = Field(0, description="失败数")
    skipped: int = Field(0, description="跳过数")
    errors: List[str] = Field(default_factory=list, description="错误信息列表")


# ==================== Template Apply ====================

class TemplateApplyRequest(BaseModel):
    """应用模板请求"""
    room_id: int = Field(..., description="目标房间ID")
    cabinet_prefix: Optional[str] = Field(None, description="机柜编码前缀")


class TemplateApplyResponse(BaseModel):
    """应用模板响应"""
    created_rows: int = Field(0, description="创建的行数")
    created_cabinets: int = Field(0, description="创建的机柜数")
    skipped_cabinets: int = Field(0, description="跳过的机柜数(编码冲突)")
    errors: List[str] = Field(default_factory=list, description="错误信息列表")
