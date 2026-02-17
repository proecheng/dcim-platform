# Dev Notes 编写模板

本文档定义BMAD Story文件中Dev Notes section的标准结构和内容要求，确保所有story具有统一的文档质量和实现指导。

---

## 模板类型

根据story复杂度，分为三种模板：

1. **复杂Story**（Backend API + Models + Frontend Page）
2. **中等Story**（单个Frontend Page或Backend模块）
3. **简单Story**（配置修改、小型功能）

---

## 模板1：复杂Story（Backend API + Models）

适用于：需要创建后端模型、Schema、API路由的story

```markdown
## Dev Notes

### 现有代码分析 — 严格遵循 [参考模式] 模式

[描述参考的实现模式，为什么遵循该模式，1:1对照表]

| 参考实现 | 本Story |
|---------|---------|
| `models/xxx.py` | `models/yyy.py` |
| `schemas/xxx.py` | `schemas/yyy.py` |
| `api/v1/xxx.py` | `api/v1/yyy.py` |

### 模型定义 (models/xxx.py)

严格遵循参考实现的Column定义风格：

```python
"""
模块描述
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, Float, Text, DateTime, ForeignKey

from ..core.database import Base


class ModelName(Base):
    """模型描述"""
    __tablename__ = "table_name"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # ... 完整字段定义
```

**注意**: [外键依赖说明、特殊约束等]

### Schema 定义 (schemas/xxx.py)

严格遵循参考实现的Pydantic v2风格：

- 使用 `ConfigDict(from_attributes=True)` 替代旧版 `class Config: orm_mode = True`
- Create schema 包含所有必填字段
- Update schema 所有字段Optional（支持部分更新）
- Info schema 包含id + 所有字段 + created_at/updated_at

```python
class OverviewSummary(BaseModel):
    """统计Schema"""
    field1: int = 0
    field2: float = 0.0
```

### API 路由 (api/v1/xxx.py)

严格遵循参考实现的路由模式：

```python
from ..deps import get_db, require_viewer, require_operator, require_admin
```

| 端点 | 方法 | 权限 | 说明 |
|------|------|------|------|
| /overview | GET | require_viewer | 总览统计 |
| /items | GET | require_viewer | 列表（分页，支持筛选） |
| /items/{id} | GET | require_viewer | 详情 |
| /items | POST | require_operator | 创建 |
| /items/{id} | PUT | require_operator | 更新 |
| /items/{id} | DELETE | require_admin | 删除 |

**端点实现要点**：
- 总览统计：[描述查询逻辑]
- 详情端点：[描述关联查询逻辑]

### 路由注册 (api/v1/__init__.py)

```python
from .xxx import router as xxx_router
# ...
api_router.include_router(xxx_router, prefix="/xxx", tags=["标签名"])
```

### 模型注册 (models/__init__.py)

```python
from .xxx import Model1, Model2
```

在 `__all__` 列表中添加：
```python
    # 模块名
    "Model1",
    "Model2",
```

### 种子数据 (services/xxx_seed.py)

严格遵循参考实现的种子数据模式：

**设备定义**：
```python
DEVICES = [
    {"device_code": "XXX-001", "device_name": "设备1", ...},
]
```

**点位定义**：
- AI: [点位列表]
- DI: [点位列表]

**种子函数模式**：
1. 检查设备是否已存在（按device_code查询）
2. 创建Device记录
3. 创建扩展记录
4. 创建Point记录
5. 调用seed函数

### 架构约束

- **技术栈**: FastAPI + SQLAlchemy 2.0 (async) + Pydantic v2 + aiosqlite
- **数据库会话**: `from ..core.database import async_session`
- **分页**: 使用 `PageResponse[T]` 通用分页响应
- **权限**: `require_viewer`(查看), `require_operator`(创建/编辑), `require_admin`(删除)
- **中文注释**: 所有代码注释使用中文
- **Alembic**: 迁移文件在 `backend/alembic/versions/` 目录

### 关键防错指南

1. **[具体错误1]** — [预防措施]
2. **[具体错误2]** — [预防措施]
3. **[具体错误3]** — [预防措施]
4. **[具体错误4]** — [预防措施]
5. **[具体错误5]** — [预防措施]

### 参考实现教训（必须遵循）

- [从参考实现中学到的具体教训]

### 需要修改/创建的文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/models/xxx.py` | 新建 | 模型定义 |
| `backend/app/schemas/xxx.py` | 新建 | Schema定义 |
| `backend/app/api/v1/xxx.py` | 新建 | API路由 |
| `backend/app/services/xxx_seed.py` | 新建 | 种子数据 |
| `backend/app/models/__init__.py` | 修改 | 注册模型 |
| `backend/app/api/v1/__init__.py` | 修改 | 注册路由 |
| `backend/app/main.py` | 修改 | 调用seed |

### Project Structure Notes

- [文件放置位置说明]
- [命名规范]

### References

- [Source: epics-v4-huawei.md#Story X.X] — Story定义
- [Source: prd-v4-huawei.md#FR-XX] — 功能需求
- [Source: architecture-v4-huawei.md#X.X] — 架构设计
- [Source: backend/app/models/reference.py] — 参考实现
```

---

## 模板2：中等Story（Frontend Page）

适用于：创建前端页面的story

```markdown
## Dev Notes

### 严格遵循 [参考页面] 模式

本页面是 `[参考页面路径]` 的[功能域]版本。必须1:1复制其结构。

**页面结构**：
```
<div class="page-class">
  <!-- 统计卡片行 (el-row + el-col) -->
  <!-- 详情行 (el-row + el-col) -->
</div>
```

**statCards 数组定义**：
```typescript
const statCards = [
  { key: 'field1', label: '标签1', icon: IconName, iconBg: 'rgba(24, 144, 255, 0.15)', valueClass: 'primary', route: '/path' },
  // ...
]
```

**详情卡片**：
- [卡片1描述]
- [卡片2描述]

**数据加载模式**：
```typescript
onMounted(async () => {
  loading.value = true
  try {
    const res = await getOverview()
    // 处理数据
  } catch {
    console.warn('API未就绪，使用模拟数据')
    overview.value = mockData
  } finally {
    loading.value = false
  }
})
```

### API 模块 (api/modules/xxx.ts)

严格遵循参考实现的API模块模式：

```typescript
/**
 * [功能域] API
 */
import request from '@/utils/request'

export interface OverviewSummary {
  field1: number
  field2: number
  // ...
}

export function getOverview() {
  return request.get<any, OverviewSummary>('/v1/xxx/overview')
}
```

### 现有文件状态

- `[文件路径]` — [状态说明：已存在/不存在/需要重写]
- 路由 `[路由路径]` — [状态说明]

### 架构约束

- **技术栈**: Vue 3.4 + TypeScript 5.9 + Element Plus 2.5
- **自动导入**: ref, computed, onMounted等无需手动import
- **Element Plus**: 组件自动导入，仅需手动import图标
- **暗色主题**: 使用CSS变量（var(--bg-card), var(--text-primary)等）
- **中文注释**: 所有代码注释使用中文
- **无Pinia Store**: overview页面不需要store，直接在组件内管理状态

### 关键防错指南

1. **[错误1]** — [预防措施]
2. **[错误2]** — [预防措施]
3. **[错误3]** — [预防措施]
4. **[错误4]** — [预防措施]
5. **[错误5]** — [预防措施]
6. **[错误6]** — [预防措施]
7. **[错误7]** — [预防措施]

### Story依赖说明

本Story依赖Story X.X的[后端API/前端组件]。但前端页面应能在依赖未就绪时使用mock数据正常展示，因此可以并行开发。

### 需要修改/创建的文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `frontend/src/api/modules/xxx.ts` | 新建 | API模块 |
| `frontend/src/views/xxx/overview.vue` | 新建/重写 | 页面 |

### References

- [Source: epics-v4-huawei.md#Story X.X] — Story定义
- [Source: frontend/src/views/reference.vue] — 参考页面
- [Source: _bmad-output/implementation-artifacts/X-X-xxx.md] — 依赖Story
```

---

## 模板3：简单Story（配置修改）

适用于：小型功能、配置修改、启用已有代码

```markdown
## Dev Notes

### 现有代码分析

**[模块/功能]已完整实现。** `[文件路径]` 包含：
- [功能描述1]
- [功能描述2]

**当前状态：** [为什么需要本story，如：路由被注释、依赖未安装等]

```python
# 示例：当前被注释的代码
# from .xxx import router as xxx_router
# api_router.include_router(xxx_router, prefix="/xxx", tags=["标签"])
```

**前端API模块：** `[文件路径]` 已封装相关接口，无需修改前端。

### 架构约束

- [技术约束1]
- [技术约束2]
- [版本兼容性要求]

### 需要修改/创建的文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `[文件路径]` | 修改 | [具体修改内容] |

### References

- [Source: epics-v4-huawei.md#Story X.X] — Story定义
- [Source: 文件路径] — 参考文件
```

---

## Dev Agent Record 标准格式

所有story必须包含完整的Dev Agent Record：

```markdown
## Dev Agent Record

### Agent Model Used

[使用的AI模型名称，如：claude-opus-4-6, kimi-k2.5-free等]

### Debug Log References

- [相关调试日志链接或文件路径]
- [问题追踪记录]

### Completion Notes List

- [完成情况说明1：如：已实现所有AC]
- [完成情况说明2：如：发现并修复了XX问题]
- [遗留问题或注意事项]

### File List

#### Created
- `[文件路径]` — [文件描述]

#### Modified
- `[文件路径]` — [修改描述]

#### Deleted
- `[文件路径]` — [删除原因]

### Retroactive Documentation

**Note**: This story was implemented before the story file was created. Documentation added retroactively on [日期].
```

---

## 质量检查清单

在提交story前，检查以下项目：

- [ ] Dev Notes包含"现有代码分析"
- [ ] 有参考实现时包含1:1对照表
- [ ] 包含完整的代码示例（模型/Schema/API）
- [ ] 包含架构约束说明
- [ ] 包含关键防错指南（至少5条）
- [ ] 包含需要修改/创建的文件清单（表格形式）
- [ ] References链接到正确的源文件
- [ ] Dev Agent Record完整填写
- [ ] 使用中文注释和描述
- [ ] 对于已完成的story，标记"retroactively documented"

---

## 示例参考

高质量Dev Notes示例：

1. **Backend API Story**: `9-1-backend-cooling-models-api.md` (292行)
2. **Frontend Page Story**: `9-2-frontend-cooling-overview-page.md` (192行)
3. **Simulator Story**: `9-5-simulator-cooling-domain-data-generation.md` (156行)

---

*模板版本: 1.0*
*最后更新: 2026-02-14*
