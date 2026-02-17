# Story 3.4: 设备模板管理

Status: done

## Story

As a 集成工程师,
I want 创建和管理设备模板,
So that 同厂商同型号的设备可以复用点位配置，避免重复配置。

## Acceptance Criteria (验收标准)

1. **AC-1: DeviceTemplate 模型** — 新增设备模板模型，包含厂商、型号、协议类型、描述、预置点位配置（JSON）
2. **AC-2: 模板 CRUD API** — POST/GET/PUT/DELETE `/api/v1/device-templates`，支持按厂商/型号查询
3. **AC-3: 从模板创建数据源** — POST `/api/v1/device-templates/{id}/create-datasource`，自动填充点位配置到 DataSourcePoint
4. **AC-4: 前端模板管理页面** — `/device-templates` 页面，展示模板列表、CRUD 对话框、按厂商/型号筛选
5. **AC-5: 前端"从模板创建"** — 模板列表操作列中提供"创建数据源"按钮，弹出对话框填写连接参数后一键创建
6. **AC-6: 后端测试** — 测试模板 CRUD 和从模板创建数据源

## Tasks / Subtasks (任务分解)

- [ ] Task 1: 后端模型 (AC: #1)
  - [ ] 1.1 在 `backend/app/models/gateway.py` 新增 DeviceTemplate 模型

- [ ] Task 2: 后端 Schema (AC: #2)
  - [ ] 2.1 在 `backend/app/schemas/gateway.py` 新增 DeviceTemplateCreate/Update/Response

- [ ] Task 3: 后端 API (AC: #2, #3)
  - [ ] 3.1 创建 `backend/app/api/v1/device_templates.py`
  - [ ] 3.2 实现 CRUD + 按厂商/型号查询 + 从模板创建数据源
  - [ ] 3.3 在 `backend/app/api/v1/__init__.py` 注册路由

- [ ] Task 4: 前端 API (AC: #4)
  - [ ] 4.1 创建 `frontend/src/api/device-template.ts`

- [ ] Task 5: 前端页面 (AC: #4, #5)
  - [ ] 5.1 创建 `frontend/src/views/device-template/index.vue`
  - [ ] 5.2 在路由中注册

- [ ] Task 6: 后端测试 (AC: #6)
  - [ ] 6.1 测试创建模板成功
  - [ ] 6.2 测试获取模板列表（含按厂商/型号筛选）
  - [ ] 6.3 测试更新模板
  - [ ] 6.4 测试删除模板
  - [ ] 6.5 测试模板不存在返回 404
  - [ ] 6.6 测试从模板创建数据源（验证 DataSourcePoint 自动填充）
  - [ ] 6.7 测试从不存在的模板创建数据源返回 404

## Dev Notes (开发指南)

### 1. 文件位置

```
backend/app/models/gateway.py               # 修改 — 新增 DeviceTemplate 模型
backend/app/schemas/gateway.py              # 修改 — 新增模板 Schema
backend/app/api/v1/device_templates.py      # 新建 — 模板 API
backend/app/api/v1/__init__.py              # 修改 — 注册路由
backend/tests/test_device_template.py       # 新建 — 测试
frontend/src/api/device-template.ts         # 新建 — 前端 API
frontend/src/views/device-template/index.vue # 新建 — 前端页面
frontend/src/router/index.ts               # 修改 — 注册路由
```

### 2. DeviceTemplate 模型

在 `backend/app/models/gateway.py` 末尾新增：

```python
class DeviceTemplate(Base):
    """设备模板 — 预置点位配置"""
    __tablename__ = "device_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="模板名称")
    manufacturer = Column(String(100), nullable=False, comment="厂商")
    model = Column(String(100), nullable=False, comment="型号")
    protocol_type = Column(String(30), nullable=False, comment="协议类型")
    description = Column(String(500), comment="描述")
    point_config = Column(JSON, nullable=False, comment="预置点位配置列表")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")
```

`point_config` 格式（JSON 数组）：
```json
[
  {"address": "40001", "data_type": "float32", "scale": 1.0, "offset": 0.0, "description": "温度"},
  {"address": "40003", "data_type": "uint16", "scale": 0.1, "offset": 0.0, "description": "湿度"}
]
```

### 3. Schema

在 `backend/app/schemas/gateway.py` 末尾新增：

```python
# --- DeviceTemplate ---
class DeviceTemplateBase(BaseModel):
    name: str
    manufacturer: str
    model: str
    protocol_type: str
    description: Optional[str] = None
    point_config: list[dict]


class DeviceTemplateCreate(DeviceTemplateBase):
    pass


class DeviceTemplateUpdate(BaseModel):
    name: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    protocol_type: Optional[str] = None
    description: Optional[str] = None
    point_config: Optional[list[dict]] = None


class DeviceTemplateResponse(DeviceTemplateBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
```

### 4. 后端 API

```python
# backend/app/api/v1/device_templates.py

"""设备模板管理 API"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, delete

from ..deps import get_db, require_viewer, require_operator, require_admin
from ...models.user import User
from ...models.gateway import DeviceTemplate, DataSource, DataSourcePoint
from ...schemas.gateway import (
    DeviceTemplateCreate, DeviceTemplateUpdate, DeviceTemplateResponse,
    DataSourceCreate, DataSourceResponse,
)
from ...schemas.common import PageResponse

router = APIRouter()


@router.get("", response_model=PageResponse[DeviceTemplateResponse], summary="获取设备模板列表")
async def list_templates(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    manufacturer: Optional[str] = Query(None, description="厂商"),
    model_name: Optional[str] = Query(None, description="型号"),
    protocol_type: Optional[str] = Query(None, description="协议类型"),
    keyword: Optional[str] = Query(None, description="关键词"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    query = select(DeviceTemplate)
    if manufacturer:
        query = query.where(DeviceTemplate.manufacturer == manufacturer)
    if model_name:
        query = query.where(DeviceTemplate.model == model_name)
    if protocol_type:
        query = query.where(DeviceTemplate.protocol_type == protocol_type)
    if keyword:
        from sqlalchemy import or_
        query = query.where(or_(
            DeviceTemplate.name.contains(keyword),
            DeviceTemplate.manufacturer.contains(keyword),
            DeviceTemplate.model.contains(keyword),
        ))

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    query = query.order_by(DeviceTemplate.id.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()

    return PageResponse(
        items=[DeviceTemplateResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=DeviceTemplateResponse, summary="创建设备模板")
async def create_template(
    data: DeviceTemplateCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    obj = DeviceTemplate(**data.model_dump())
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return DeviceTemplateResponse.model_validate(obj)


@router.get("/{template_id}", response_model=DeviceTemplateResponse, summary="获取模板详情")
async def get_template(
    template_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer),
):
    result = await db.execute(select(DeviceTemplate).where(DeviceTemplate.id == template_id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="模板不存在")
    return DeviceTemplateResponse.model_validate(obj)


@router.put("/{template_id}", response_model=DeviceTemplateResponse, summary="更新模板")
async def update_template(
    template_id: int,
    data: DeviceTemplateUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    result = await db.execute(select(DeviceTemplate).where(DeviceTemplate.id == template_id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="模板不存在")

    update_data = data.model_dump(exclude_unset=True)
    update_data["updated_at"] = datetime.now()
    await db.execute(update(DeviceTemplate).where(DeviceTemplate.id == template_id).values(**update_data))
    await db.commit()

    result = await db.execute(select(DeviceTemplate).where(DeviceTemplate.id == template_id))
    obj = result.scalar_one()
    return DeviceTemplateResponse.model_validate(obj)


@router.delete("/{template_id}", summary="删除模板")
async def delete_template(
    template_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(DeviceTemplate).where(DeviceTemplate.id == template_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="模板不存在")

    await db.execute(delete(DeviceTemplate).where(DeviceTemplate.id == template_id))
    await db.commit()
    return {"message": "模板已删除"}


@router.post("/{template_id}/create-datasource", response_model=DataSourceResponse, summary="从模板创建数据源")
async def create_datasource_from_template(
    template_id: int,
    data: DataSourceCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    # 获取模板
    result = await db.execute(select(DeviceTemplate).where(DeviceTemplate.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    # 创建数据源
    ds = DataSource(**data.model_dump())
    db.add(ds)
    await db.flush()  # 获取 ds.id

    # 从模板填充点位
    for pt_cfg in (template.point_config or []):
        point = DataSourcePoint(
            datasource_id=ds.id,
            address=str(pt_cfg.get("address", "")),
            data_type=pt_cfg.get("data_type"),
            scale=float(pt_cfg.get("scale", 1.0)),
            offset=float(pt_cfg.get("offset", 0.0)),
            enum_mapping=pt_cfg.get("enum_mapping"),
            is_dry_contact=pt_cfg.get("is_dry_contact", False),
        )
        db.add(point)

    await db.commit()
    await db.refresh(ds)
    return DataSourceResponse.model_validate(ds)
```

### 5. 路由注册

在 `backend/app/api/v1/__init__.py` 中新增：

```python
from .device_templates import router as device_template_router
api_router.include_router(device_template_router, prefix="/device-templates", tags=["设备模板"])
```

### 6. 前端 API

```typescript
// frontend/src/api/device-template.ts
import request from '@/utils/request'

export interface DeviceTemplate {
  id: number
  name: string
  manufacturer: string
  model: string
  protocol_type: string
  description: string | null
  point_config: Array<Record<string, any>>
  created_at: string
  updated_at: string
}

export function getTemplates(params?: any) {
  return request.get('/v1/device-templates', { params })
}

export function getTemplate(id: number) {
  return request.get(`/v1/device-templates/${id}`)
}

export function createTemplate(data: Partial<DeviceTemplate>) {
  return request.post('/v1/device-templates', data)
}

export function updateTemplate(id: number, data: Partial<DeviceTemplate>) {
  return request.put(`/v1/device-templates/${id}`, data)
}

export function deleteTemplate(id: number) {
  return request.delete(`/v1/device-templates/${id}`)
}

export function createDatasourceFromTemplate(templateId: number, data: any) {
  return request.post(`/v1/device-templates/${templateId}/create-datasource`, data)
}
```

### 7. 前端路由

在 `frontend/src/router/index.ts` 的 `datasources` 路由之后新增：

```typescript
{
  path: 'device-templates',
  name: 'DeviceTemplates',
  component: () => import('@/views/device-template/index.vue'),
  meta: { title: '设备模板', icon: 'Files' }
},
```

### 8. 前端页面

`frontend/src/views/device-template/index.vue` — 严格参照 `views/datasource/index.vue` 的风格：

- el-card 包裹，header 含"设备模板管理"标题 + "新增模板"按钮
- 筛选栏：厂商输入、型号输入、协议类型下拉、关键词搜索
- el-table：名称、厂商、型号、协议类型（el-tag）、点位数量（point_config.length）、操作列（编辑/创建数据源/删除）
- 创建/编辑 el-dialog：名称、厂商、型号、协议类型、描述、点位配置（JSON 文本域或简单表格编辑）
- "创建数据源" el-dialog：选择模板后填写连接参数（复用协议动态表单），确认后调用 createDatasourceFromTemplate

点位配置编辑：使用 el-input type="textarea" 编辑 JSON 字符串，提交时 JSON.parse 校验。

"创建数据源"对话框：
- 显示模板名称（只读）
- 数据源名称（必填）
- 协议类型（从模板自动填充，只读）
- 协议动态配置区域（复用 datasource/index.vue 中的 v-if 协议表单：modbus_tcp/modbus_rtu/snmp_v2c/snmp_v3）
- 采集周期（默认 5 秒）
- 确认后调用 createDatasourceFromTemplate，传入 DataSourceCreate 格式数据

### 9. 关键约束

- DeviceTemplate 是全新模型，不影响现有模型
- point_config 用 JSON 列存储点位配置数组
- 从模板创建数据源时，先创建 DataSource，再批量创建 DataSourcePoint
- 前端页面风格与 datasource/index.vue 一致
- 测试使用内存 SQLite

### References

- [Source: models/gateway.py] DataSource, DataSourcePoint 模型
- [Source: schemas/gateway.py] DataSourceCreate, DataSourceResponse
- [Source: api/v1/datasources.py] 数据源 API 风格参照
- [Source: views/datasource/index.vue] 前端页面风格参照
- [Source: epics.md#Story 3.4] Acceptance Criteria

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

