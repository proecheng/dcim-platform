# 电价方案管理系统 - 实施指南

**版本**: v1.2 最终版  
**日期**: 2026-03-01  
**状态**: ✅ 可以开始实施  
**评分**: 9.1/10

---

## 📋 实施清单

### 阶段 0：准备工作（0.5天）

- [ ] 创建功能分支 `feature/pricing-scheme-management`
- [ ] 安装 Redis（用于分布式锁）
- [ ] 配置 Redis 连接
- [ ] 审查所有设计文档

### 阶段 1：数据库迁移（0.5天）

#### 1.1 创建 Alembic 迁移脚本

```bash
cd backend
alembic revision -m "add_pricing_schemes"
```

#### 1.2 编写迁移脚本

文件：`backend/alembic/versions/xxx_add_pricing_schemes.py`

参考：`docs/pricing-scheme-v1.2-supplements.md` 中的迁移脚本

#### 1.3 测试迁移

```bash
# 1. 备份数据库
cp dcim.db dcim.db.backup

# 2. 运行迁移
alembic upgrade head

# 3. 验证表结构
sqlite3 dcim.db ".schema pricing_schemes"
sqlite3 dcim.db ".schema scheme_pricing_relations"
sqlite3 dcim.db ".schema pricing_scheme_audit_logs"

# 4. 验证数据迁移
sqlite3 dcim.db "SELECT * FROM pricing_schemes"
sqlite3 dcim.db "SELECT * FROM scheme_pricing_relations"

# 5. 如果失败，回滚
alembic downgrade -1
cp dcim.db.backup dcim.db
```

---

### 阶段 2：后端核心功能（2天）

#### 2.1 模型定义（0.5天）

**文件**：`backend/app/models/energy.py`

```python
# 新增模型
class PricingScheme(Base):
    __tablename__ = "pricing_schemes"
    # ... 字段定义 ...

class SchemePricingRelation(Base):
    __tablename__ = "scheme_pricing_relations"
    # ... 字段定义 ...

class PricingSchemeAuditLog(Base):
    __tablename__ = "pricing_scheme_audit_logs"
    # ... 字段定义 ...
```

#### 2.2 Schema 定义（0.5天）

**文件**：`backend/app/schemas/energy.py`

```python
# 新增 Schema
class PricingSchemeCreate(BaseModel):
    scheme_name: str
    description: Optional[str]
    effective_date: date
    expire_date: Optional[date]
    pricing_ids: List[int]

class PricingSchemeUpdate(BaseModel):
    scheme_name: Optional[str]
    description: Optional[str]
    effective_date: Optional[date]
    expire_date: Optional[date]
    pricing_ids: Optional[List[int]]

class PricingSchemeResponse(BaseModel):
    id: int
    scheme_name: str
    description: Optional[str]
    is_active: bool
    effective_date: date
    expire_date: Optional[date]
    validation: Optional[dict]
    created_at: datetime
    updated_at: datetime
```

#### 2.3 服务层实现（1天）

**文件**：`backend/app/services/pricing_service.py`

实现以下方法：

```python
class PricingService:
    # 方案管理
    async def create_scheme(self, data: PricingSchemeCreate) -> PricingScheme
    async def update_scheme(self, scheme_id: int, data: PricingSchemeUpdate) -> PricingScheme
    async def delete_scheme(self, scheme_id: int) -> None
    async def get_scheme(self, scheme_id: int) -> PricingScheme
    async def list_schemes(self) -> List[PricingScheme]
    
    # 方案激活/停用
    async def activate_scheme(self, scheme_id: int) -> None
    async def deactivate_scheme(self, scheme_id: int) -> None
    async def get_active_scheme(self) -> Optional[PricingScheme]
    
    # 方案校验
    async def validate_scheme(self, scheme_id: int) -> dict
    
    # 时段管理（修改现有方法）
    async def delete_pricing(self, pricing_id: int) -> None  # 增加引用检查
    async def update_pricing(self, pricing_id: int, data: dict) -> None  # 增加方案失效检查
    
    # 计费逻辑（修改现有方法）
    async def get_current_pricing(self) -> List[ElectricityPricing]  # 增加兼容模式校验
```

**关键实现**：

1. **Redis 分布式锁**（参考 `pricing-scheme-v1.2-supplements.md`）
2. **时段编辑后方案失效检查**
3. **兼容模式增强**（严格/宽松模式）

---

### 阶段 3：后端 API（0.5天）

**文件**：`backend/app/api/v1/energy.py`

```python
# 新增 API 端点
@router.get("/pricing-schemes")
async def list_schemes(...)

@router.post("/pricing-schemes")
async def create_scheme(...)

@router.get("/pricing-schemes/{id}")
async def get_scheme(...)

@router.put("/pricing-schemes/{id}")
async def update_scheme(...)

@router.delete("/pricing-schemes/{id}")
async def delete_scheme(...)

@router.post("/pricing-schemes/{id}/activate")
async def activate_scheme(...)

@router.post("/pricing-schemes/{id}/deactivate")
async def deactivate_scheme(...)

@router.post("/pricing-schemes/{id}/validate")
async def validate_scheme(...)

@router.get("/pricing-schemes/active")
async def get_active_scheme(...)

# 修改现有 API
@router.delete("/pricing/{id}")
async def delete_pricing(...)  # 增加引用检查

@router.put("/pricing/{id}")
async def update_pricing(...)  # 增加方案失效检查
```

---

### 阶段 4：前端组件（1.5天）

#### 4.1 API 模块（0.5天）

**文件**：`frontend/src/api/modules/energy.ts`

```typescript
// 新增 API 调用
export const getPricingSchemes = () => request.get('/energy/pricing-schemes')
export const createPricingScheme = (data: any) => request.post('/energy/pricing-schemes', data)
export const updatePricingScheme = (id: number, data: any) => request.put(`/energy/pricing-schemes/${id}`, data)
export const deletePricingScheme = (id: number) => request.delete(`/energy/pricing-schemes/${id}`)
export const activatePricingScheme = (id: number) => request.post(`/energy/pricing-schemes/${id}/activate`)
export const deactivatePricingScheme = (id: number) => request.post(`/energy/pricing-schemes/${id}/deactivate`)
export const validatePricingScheme = (id: number) => request.post(`/energy/pricing-schemes/${id}/validate`)
export const getActivePricingScheme = () => request.get('/energy/pricing-schemes/active')
```

#### 4.2 方案管理组件（0.5天）

**文件**：`frontend/src/components/energy/PricingSchemeManager.vue`

```vue
<template>
  <el-dialog v-model="visible" title="电价方案管理" width="900px">
    <!-- 方案列表 -->
    <el-table :data="schemes">
      <el-table-column prop="scheme_name" label="方案名称" />
      <el-table-column prop="pricing_count" label="时段数" />
      <el-table-column label="状态">
        <template #default="{ row }">
          <el-tag v-if="row.is_active" type="success">激活</el-tag>
          <el-tag v-else-if="row.validation?.valid" type="info">草稿</el-tag>
          <el-tag v-else type="warning">未完整</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作">
        <template #default="{ row }">
          <el-button link @click="editScheme(row)">编辑</el-button>
          <el-button link type="primary" @click="activateScheme(row)" v-if="!row.is_active">激活</el-button>
          <el-button link type="warning" @click="deactivateScheme(row)" v-if="row.is_active">停用</el-button>
          <el-button link type="danger" @click="deleteScheme(row)" v-if="!row.is_active">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-dialog>
</template>
```

#### 4.3 时间轴组件（0.5天）

**文件**：`frontend/src/components/energy/PricingTimeline.vue`

```vue
<template>
  <div class="pricing-timeline">
    <!-- 24小时时间轴 -->
    <div class="timeline-header">
      <span v-for="hour in 24" :key="hour">{{ hour }}:00</span>
    </div>
    <div class="timeline-body">
      <div
        v-for="pricing in pricings"
        :key="pricing.id"
        class="timeline-segment"
        :style="getSegmentStyle(pricing)"
        :class="getPeriodClass(pricing.period_type)"
      >
        {{ pricing.pricing_name }}
      </div>
    </div>
    <!-- 覆盖率和冲突提示 -->
    <div class="timeline-footer">
      <el-tag :type="validation.valid ? 'success' : 'danger'">
        覆盖率: {{ validation.coverage }}/24 小时
      </el-tag>
      <el-tag v-if="validation.conflicts.length > 0" type="warning">
        冲突: {{ validation.conflicts.length }} 处
      </el-tag>
      <el-tag v-if="validation.gaps.length > 0" type="danger">
        缺失: {{ validation.gaps.length }} 处
      </el-tag>
    </div>
  </div>
</template>
```

#### 4.4 修改配置页面（0.5天）

**文件**：`frontend/src/views/energy/config.vue`

```vue
<template>
  <el-tab-pane label="电价配置" name="pricing">
    <div class="tab-header">
      <el-button type="primary" @click="showPricingDialog()">新增时段</el-button>
      <el-upload ...>上传电费单识别</el-upload>
      
      <!-- 新增：方案管理按钮 -->
      <el-button @click="showSchemeManager">
        <el-icon><Operation /></el-icon>方案管理
      </el-button>
    </div>

    <!-- 新增：当前激活方案提示 -->
    <el-alert v-if="activeScheme" type="success" :closable="false">
      <template #title>
        当前激活方案: <strong>{{ activeScheme.scheme_name }}</strong>
        <el-tag type="success" size="small">生效中</el-tag>
      </template>
    </el-alert>

    <!-- 现有时段列表 -->
    <el-table :data="pricingList" ...>
      ...
    </el-table>
  </el-tab-pane>
</template>

<script setup lang="ts">
import PricingSchemeManager from '@/components/energy/PricingSchemeManager.vue'

const activeScheme = ref(null)
const schemeManagerVisible = ref(false)

const loadActiveScheme = async () => {
  const res = await getActivePricingScheme()
  if (res.code === 0) {
    activeScheme.value = res.data
  }
}

const showSchemeManager = () => {
  schemeManagerVisible.value = true
}

onMounted(() => {
  loadActiveScheme()
  loadPricing()
})
</script>
```

---

### 阶段 5：单元测试（1天）

#### 5.1 后端测试（0.5天）

**文件**：`backend/tests/services/test_pricing_service.py`

```python
# 测试方案管理
async def test_create_scheme()
async def test_activate_scheme()
async def test_concurrent_activation()  # 并发测试
async def test_delete_active_scheme_fails()

# 测试时段管理
async def test_delete_pricing_in_active_scheme_fails()
async def test_edit_pricing_invalidates_scheme()

# 测试兼容模式
async def test_strict_mode_raises_exception()
async def test_loose_mode_fills_gaps()

# 测试数据迁移
async def test_migration_creates_default_scheme()
```

#### 5.2 前端测试（0.5天）

**文件**：`frontend/src/__tests__/components/pricing-scheme-manager.test.ts`

```typescript
describe('PricingSchemeManager', () => {
  it('should list all schemes', async () => { ... })
  it('should activate scheme', async () => { ... })
  it('should deactivate scheme', async () => { ... })
  it('should delete non-active scheme', async () => { ... })
  it('should prevent deleting active scheme', async () => { ... })
})
```

---

### 阶段 6：集成测试（0.5天）

#### 6.1 端到端测试

```bash
# 1. 启动后端
cd backend && uvicorn app.main:app --reload

# 2. 启动前端
cd frontend && npm run dev

# 3. 测试流程
# - 创建时段
# - 创建方案
# - 激活方案
# - 编辑时段（验证方案失效）
# - 停用方案
# - 删除方案
```

#### 6.2 性能测试

```python
# 并发激活测试
async def test_100_concurrent_activations():
    tasks = [activate_scheme(i % 10) for i in range(100)]
    start = time.time()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    duration = time.time() - start
    
    # 验证：只有10个成功，耗时<5秒
    assert sum(1 for r in results if not isinstance(r, Exception)) == 10
    assert duration < 5.0
```

---

### 阶段 7：文档和部署（0.5天）

#### 7.1 更新 API 文档

**文件**：`docs/api-contracts-backend.md`

添加方案管理 API 文档

#### 7.2 更新用户手册

**文件**：`docs/用户使用说明书.md`

添加"电价方案管理"章节

#### 7.3 编写迁移指南

**文件**：`docs/pricing-scheme-migration-guide.md`

说明如何从旧版本升级

---

## 📊 进度跟踪

| 阶段 | 预计时间 | 实际时间 | 状态 |
|------|---------|---------|------|
| 0. 准备工作 | 0.5天 | - | ⏳ 待开始 |
| 1. 数据库迁移 | 0.5天 | - | ⏳ 待开始 |
| 2. 后端核心功能 | 2天 | - | ⏳ 待开始 |
| 3. 后端 API | 0.5天 | - | ⏳ 待开始 |
| 4. 前端组件 | 1.5天 | - | ⏳ 待开始 |
| 5. 单元测试 | 1天 | - | ⏳ 待开始 |
| 6. 集成测试 | 0.5天 | - | ⏳ 待开始 |
| 7. 文档和部署 | 0.5天 | - | ⏳ 待开始 |
| **总计** | **7天** | **-** | **⏳ 待开始** |

---

## 🔍 验收标准

### 功能验收

- [ ] 可以创建、编辑、删除电价方案
- [ ] 可以激活、停用电价方案
- [ ] 激活方案时自动校验完整性
- [ ] 删除被激活方案引用的时段时给出错误提示
- [ ] 编辑时段后自动检查方案失效
- [ ] 100个并发激活请求只有1个成功
- [ ] 兼容模式可配置（严格/宽松）
- [ ] 数据迁移成功创建默认方案

### 性能验收

- [ ] 方案激活响应时间 < 1秒
- [ ] 100个并发激活请求总耗时 < 5秒
- [ ] 时间轴组件渲染 < 500ms

### 测试验收

- [ ] 后端单元测试覆盖率 > 80%
- [ ] 前端单元测试覆盖率 > 70%
- [ ] 所有集成测试通过

---

## 🚨 风险和应对

| 风险 | 概率 | 影响 | 应对措施 |
|------|------|------|---------|
| Redis 未安装 | 中 | 高 | 提供 Redis 安装指南 |
| 数据迁移失败 | 低 | 高 | 提供回滚脚本和手动迁移指南 |
| 并发测试失败 | 低 | 中 | 调整锁超时时间 |
| 前端性能问题 | 低 | 中 | 使用虚拟滚动优化时间轴 |

---

## 📞 支持和反馈

如果在实施过程中遇到问题，请参考：

1. **设计文档**：`docs/pricing-scheme-design-v1.2-final.md`
2. **补充方案**：`docs/pricing-scheme-v1.2-supplements.md`
3. **审查报告**：`docs/pricing-scheme-design-review-round2.md`

---

**实施指南完成时间**: 2026-03-01 18:30  
**状态**: ✅ 可以开始实施  
**预计完成时间**: 2026-03-08（7个工作日）
