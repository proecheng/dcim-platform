# 电价方案管理系统设计方案

**版本**: v1.0  
**日期**: 2026-03-01  
**状态**: 待审查

---

## 一、背景与问题

### 1.1 现状

当前系统电价配置存在以下问题：

1. **时段独立管理**：每个电价时段独立配置，缺乏整体性约束
2. **无完整性校验**：
   - 多个"启用"时段可能存在时间重叠
   - 所有时段加起来可能不足 24 小时
   - 剩余时间段电价性质不明确
3. **计费歧义**：当某个时刻匹配多个时段时，无明确优先级规则

### 1.2 用户需求

- 尽量少改动现有界面
- 启用时段时只能检查重叠，不能强制要求 24 小时完整（因为其他时段可能未启用）
- 需要一种机制确保实际计费时使用的是完整、无冲突的电价配置

---

## 二、解决方案：电价方案管理

### 2.1 核心思路

**将"电价时段"和"电价方案"分离**：

- **电价时段**（ElectricityPricing）：单个时段配置，可独立存在
- **电价方案**（PricingScheme）：一组时段的组合，作为完整的 24 小时配置方案
- **激活机制**：只有通过完整性校验的方案才能激活，全局只能有一个激活方案

### 2.2 设计原则

1. **最小化界面改动**：保持现有时段列表，只增加"方案管理"入口
2. **灵活配置**：时段可独立创建、编辑，不强制归属方案
3. **严格激活**：方案激活时强制校验 24 小时完整覆盖且无重叠
4. **向下兼容**：现有数据和 API 保持兼容

---

## 三、数据模型设计

### 3.1 新增表结构

#### PricingScheme（电价方案表）

```sql
CREATE TABLE pricing_schemes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scheme_name VARCHAR(100) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT FALSE,
    effective_date DATE NOT NULL,
    expire_date DATE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX idx_active_scheme ON pricing_schemes(is_active) WHERE is_active = TRUE;
```

#### SchemePricingRelation（方案-时段关联表）

```sql
CREATE TABLE scheme_pricing_relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scheme_id INTEGER NOT NULL,
    pricing_id INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (scheme_id) REFERENCES pricing_schemes(id) ON DELETE CASCADE,
    FOREIGN KEY (pricing_id) REFERENCES electricity_pricing(id) ON DELETE CASCADE,
    UNIQUE(scheme_id, pricing_id)
);
```

### 3.2 现有表调整

```sql
ALTER TABLE electricity_pricing ADD COLUMN scheme_id INTEGER;
-- is_enabled 语义调整：旧=是否激活使用，新=是否可用（可被方案引用）
```

---

## 四、业务逻辑设计

### 4.1 时段管理（保持现有逻辑）

**创建/编辑时段**：
- 如果 is_enabled = true，检查是否与其他已启用时段重叠
- 存在重叠时给出警告但允许保存

**删除时段**：
- 检查是否被激活方案引用
- 如果被引用，禁止删除

### 4.2 方案管理（新增）

**校验方案**：
- 时段不能重叠
- 必须覆盖完整 24 小时（包括跨日时段）

**激活方案**：
- 校验通过后才能激活
- 全局只能有一个激活方案

### 4.3 计费逻辑（修改）

```python
async def get_current_pricing(self):
    active_scheme = await self._get_active_scheme()
    if active_scheme:
        return await self._get_scheme_pricings(active_scheme.id)
    else:
        # 兼容模式：返回所有已启用时段
        return await self._get_enabled_pricings()
```

---

## 五、API 设计

### 5.1 新增 API

```
GET    /api/v1/energy/pricing-schemes              # 获取所有方案
POST   /api/v1/energy/pricing-schemes              # 创建方案
GET    /api/v1/energy/pricing-schemes/{id}         # 获取方案详情
PUT    /api/v1/energy/pricing-schemes/{id}         # 更新方案
DELETE /api/v1/energy/pricing-schemes/{id}         # 删除方案
POST   /api/v1/energy/pricing-schemes/{id}/activate    # 激活方案
POST   /api/v1/energy/pricing-schemes/{id}/validate    # 校验方案
GET    /api/v1/energy/pricing-schemes/active       # 获取当前激活方案
```

### 5.2 时段管理（增强现有 API）

```
POST   /api/v1/energy/pricing                      # 创建时段（增加重叠检查）
PUT    /api/v1/energy/pricing/{id}                 # 更新时段（增加重叠检查）
DELETE /api/v1/energy/pricing/{id}                 # 删除时段（检查方案引用）
POST   /api/v1/energy/pricing/check-overlap        # 检查时段重叠
```

---

## 六、前端界面设计

### 6.1 电价配置页面（最小改动）

**改动点**：
1. 顶部增加按钮：`[方案管理]`
2. 增加提示条：显示当前激活方案
3. 保存时段增强：检查重叠并给出警告

### 6.2 方案管理对话框（新增）

**方案列表**：显示所有方案及状态（激活/草稿/未完整）

**方案编辑**：
- 24 小时时间轴可视化
- 覆盖率和冲突检测
- 时段拖拽排序

---

## 七、影响范围分析

### 7.1 后端文件

**核心修改**：
- `models/energy.py` - 新增模型
- `schemas/energy.py` - 新增 Schema
- `api/v1/energy.py` - 新增 API
- `services/pricing_service.py` - 修改获取电价逻辑 ⚠️

**兼容性调整**：
- `services/simulation_service.py`
- `services/formula_calculator.py`
- `services/suggestion_engine.py`
- `services/energy_report_service.py`
- `demo/service.py`

### 7.2 前端文件

**核心修改**：
- `views/energy/config.vue` - 增加方案管理入口
- `api/modules/energy.ts` - 新增 API 调用
- `components/energy/PricingSchemeManager.vue` - 新建组件
- `components/energy/PricingTimeline.vue` - 新建组件

**只读展示（无需改动）**：
- `components/energy/CalculationDetails.vue`
- `views/energy/monitor.vue`
- `views/energy/analysis.vue`

---

## 八、实施计划

### 阶段 1：数据库和后端 API（2 天）
- 创建数据库迁移脚本
- 新增模型和 API
- 修改 PricingService
- 编写单元测试

### 阶段 2：前端方案管理界面（2 天）
- 新建组件
- 修改 config.vue
- 编写前端测试

### 阶段 3：数据迁移和兼容性（1 天）
- 数据迁移脚本
- 修改 Demo 数据
- 测试所有功能

### 阶段 4：集成测试和文档（1 天）
- 端到端测试
- 更新文档

---

## 九、风险评估

### 9.1 技术风险

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| 数据迁移失败 | 低 | 高 | 提供回滚脚本 |
| 计费逻辑错误 | 中 | 高 | 单元测试覆盖 |
| 前端性能问题 | 低 | 中 | 虚拟滚动 |

### 9.2 业务风险

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| 用户不理解方案概念 | 中 | 中 | 详细说明和示例 |
| 现有工作流被打断 | 低 | 中 | 保持时段独立管理 |

---

## 十、待确认问题

1. **跨日时段处理**：如"23:00-次日06:00"，是否拆分为两条记录？
2. **方案版本管理**：是否需要保留历史方案用于审计？
3. **方案切换时机**：激活新方案后，正在执行的优化任务是否立即使用新电价？
4. **时段删除策略**：被方案引用的时段是否允许删除（级联删除 vs 禁止删除）？

---

## 十一、附录

### A. 时段重叠检测算法

```python
def check_overlap(time1_start, time1_end, time2_start, time2_end):
    """检查两个时段是否重叠"""
    t1_start = time_to_minutes(time1_start)
    t1_end = time_to_minutes(time1_end)
    t2_start = time_to_minutes(time2_start)
    t2_end = time_to_minutes(time2_end)
    
    # 处理跨日时段
    if t1_end < t1_start:
        t1_end += 1440
    if t2_end < t2_start:
        t2_end += 1440
    
    return not (t1_end <= t2_start or t2_end <= t1_start)
```

### B. 24 小时覆盖检测算法

```python
def check_24h_coverage(pricings):
    """检查时段是否覆盖完整 24 小时"""
    # 1. 转换为分钟区间
    intervals = []
    for p in pricings:
        start = time_to_minutes(p.start_time)
        end = time_to_minutes(p.end_time)
        if end < start:  # 跨日
            intervals.append((start, 1440))
            intervals.append((0, end))
        else:
            intervals.append((start, end))
    
    # 2. 合并重叠区间
    intervals.sort()
    merged = []
    for start, end in intervals:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    
    # 3. 检查是否覆盖 [0, 1440)
    if len(merged) == 1 and merged[0] == (0, 1440):
        return True, 24.0, []
    
    # 4. 计算缺失时段
    gaps = []
    if merged[0][0] > 0:
        gaps.append((0, merged[0][0]))
    for i in range(len(merged) - 1):
        if merged[i][1] < merged[i+1][0]:
            gaps.append((merged[i][1], merged[i+1][0]))
    if merged[-1][1] < 1440:
        gaps.append((merged[-1][1], 1440))
    
    coverage = sum(end - start for start, end in merged) / 60.0
    return len(gaps) == 0, coverage, gaps
```

---

**文档结束**
