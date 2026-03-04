# 电价方案管理系统 - 对抗性审查报告

**审查日期**: 2026-03-01  
**审查人**: Kiro (AI 系统架构师)  
**审查方法**: 红队对抗性分析

---

## 审查摘要

| 维度 | 评分 | 说明 |
|------|------|------|
| 技术可行性 | ⚠️ 7/10 | 存在数据一致性和并发问题 |
| 业务完整性 | ⚠️ 6/10 | 缺少关键业务场景考虑 |
| 用户体验 | ✅ 8/10 | 界面改动最小化，但概念理解有门槛 |
| 向下兼容性 | ⚠️ 7/10 | 兼容模式存在隐患 |
| 可维护性 | ✅ 8/10 | 架构清晰，但增加了复杂度 |
| **总体评分** | **⚠️ 7.2/10** | **可实施，但需解决关键问题** |

---

## 一、致命缺陷（Must Fix）

### 🔴 1. 数据一致性问题：时段被删除后方案失效

**问题描述**：
```
场景：
1. 用户创建方案A，包含时段1、2、3，校验通过，激活
2. 用户在时段列表中直接删除时段2
3. 方案A仍然是激活状态，但实际上已经不完整（缺少时段2）
4. 计费系统使用方案A时，会出现时段缺失，导致某些时间无法计费
```

**设计方案中的处理**：
> "删除时段：检查是否被激活方案引用，如果被引用，禁止删除"

**问题**：
- 如果禁止删除，用户体验差（"为什么我不能删除这个时段？"）
- 如果允许删除，数据一致性无法保证
- 设计文档没有明确说明是"禁止删除"还是"级联删除"

**建议修复**：
```python
# 方案1：禁止删除（推荐）
async def delete_pricing(pricing_id):
    # 检查是否被激活方案引用
    active_scheme = await get_active_scheme()
    if active_scheme:
        relations = await get_scheme_relations(active_scheme.id)
        if pricing_id in [r.pricing_id for r in relations]:
            raise HTTPException(
                status_code=400,
                detail=f"该时段被激活方案'{active_scheme.scheme_name}'引用，无法删除。请先停用方案或从方案中移除该时段。"
            )
    # 继续删除逻辑...

# 方案2：级联更新（复杂但用户友好）
async def delete_pricing(pricing_id):
    # 找到所有引用该时段的方案
    affected_schemes = await get_schemes_by_pricing(pricing_id)
    for scheme in affected_schemes:
        # 从方案中移除该时段
        await remove_pricing_from_scheme(scheme.id, pricing_id)
        # 如果是激活方案，重新校验
        if scheme.is_active:
            validation = await validate_scheme(scheme.id)
            if not validation['valid']:
                # 自动停用方案
                await deactivate_scheme(scheme.id)
                # 通知用户
                await notify_user(f"方案'{scheme.scheme_name}'因时段删除而自动停用")
```

---

### 🔴 2. 并发问题：多用户同时激活方案

**问题描述**：
```
场景：
1. 用户A在 10:00:00.000 激活方案A
2. 用户B在 10:00:00.100 激活方案B
3. 两个请求几乎同时到达后端
4. 可能出现两个方案都被标记为 is_active = true
```

**设计方案中的处理**：
> "将其他方案的 is_active 设为 false，将当前方案的 is_active 设为 true"

**问题**：
- 没有使用数据库事务锁
- 没有使用唯一索引约束（虽然有 `CREATE UNIQUE INDEX`，但 SQLite 的 WHERE 条件索引在并发下可能失效）

**建议修复**：
```python
async def activate_scheme(scheme_id: int):
    async with db.begin():  # 开启事务
        # 1. 加锁：使用 SELECT FOR UPDATE
        await db.execute(
            text("SELECT id FROM pricing_schemes WHERE is_active = TRUE FOR UPDATE")
        )
        
        # 2. 停用所有方案
        await db.execute(
            update(PricingScheme).values(is_active=False)
        )
        
        # 3. 激活目标方案
        await db.execute(
            update(PricingScheme)
            .where(PricingScheme.id == scheme_id)
            .values(is_active=True)
        )
        
        # 4. 验证唯一性（双重保险）
        result = await db.execute(
            select(func.count()).select_from(PricingScheme).where(PricingScheme.is_active == True)
        )
        if result.scalar() != 1:
            raise Exception("激活方案失败：存在多个激活方案")
```

---

### 🔴 3. 兼容模式的隐患：无激活方案时的计费错误

**问题描述**：
```
场景：
1. 系统刚升级，还没有创建任何方案
2. 用户启用了时段A（08:00-10:00）和时段B（10:00-12:00）
3. 时段A和B存在重叠（10:00 同时属于两个时段）
4. 计费系统调用 get_current_pricing()，进入兼容模式
5. 返回所有已启用时段，包含重叠的A和B
6. 计费时 10:00 这个时刻匹配到两个电价，不知道用哪个
```

**设计方案中的处理**：
> "兼容模式：返回所有已启用时段（向下兼容）"

**问题**：
- 兼容模式没有进行重叠检查
- 可能返回不完整的时段配置（不足 24 小时）
- 计费逻辑需要处理重叠和缺失的情况，增加复杂度

**建议修复**：
```python
async def get_current_pricing(self):
    active_scheme = await self._get_active_scheme()
    
    if active_scheme:
        return await self._get_scheme_pricings(active_scheme.id)
    else:
        # 兼容模式：返回已启用时段，但进行校验
        enabled_pricings = await self._get_enabled_pricings()
        
        # 校验完整性
        validation = self._validate_pricings(enabled_pricings)
        
        if not validation['valid']:
            # 记录警告日志
            logger.warning(
                f"No active pricing scheme. Enabled pricings are incomplete: "
                f"coverage={validation['coverage']}h, conflicts={len(validation['conflicts'])}"
            )
            
            # 可选：抛出异常，强制用户创建方案
            # raise HTTPException(
            #     status_code=500,
            #     detail="电价配置不完整，请在能源管理-电价配置中创建并激活完整方案"
            # )
        
        return enabled_pricings
```

---

## 二、严重问题（Should Fix）

### 🟠 4. 跨日时段处理不明确

**问题描述**：
设计文档中"待确认问题"提到：
> "跨日时段处理：如'23:00-次日06:00'，是否拆分为两条记录？"

**影响**：
- 如果不拆分，数据库存储 `start_time='23:00', end_time='06:00'`，`end_time < start_time`，违反直觉
- 如果拆分，用户创建一个时段，数据库存储两条记录，删除时需要同时删除两条
- 覆盖检测算法需要特殊处理跨日时段

**建议**：
```
方案1：不拆分，算法处理（推荐）
- 数据库存储：start_time='23:00', end_time='06:00'
- 覆盖检测时：if end < start: end += 1440
- 优点：用户体验好，一个时段就是一条记录
- 缺点：算法复杂度稍高

方案2：拆分存储
- 数据库存储：两条记录
  - 记录1: start_time='23:00', end_time='24:00'
  - 记录2: start_time='00:00', end_time='06:00'
- 增加字段：is_split=true, split_group_id=xxx
- 优点：算法简单
- 缺点：用户体验差，删除/编辑需要同步两条记录
```

---

### 🟠 5. 方案切换时机不明确

**问题描述**：
设计文档中"待确认问题"提到：
> "方案切换时机：激活新方案后，正在执行的优化任务是否立即使用新电价？"

**场景**：
```
1. 10:00 用户启动一个"峰谷转移优化"任务，预计运行 30 分钟
2. 10:10 用户激活了新的电价方案（电价大幅调整）
3. 10:15 优化任务计算收益时，应该用旧方案还是新方案？
```

**影响**：
- 如果立即切换，优化任务的前后计算使用不同电价，结果不一致
- 如果不切换，优化任务完成后，用户看到的电价和任务使用的电价不一致

**建议**：
```python
# 方案1：任务启动时锁定方案（推荐）
class OptimizationTask:
    def __init__(self):
        # 任务启动时记录当前方案ID
        self.pricing_scheme_id = await get_active_scheme_id()
    
    async def calculate_benefit(self):
        # 使用任务启动时的方案
        pricings = await get_scheme_pricings(self.pricing_scheme_id)
        # 计算逻辑...

# 方案2：方案版本化
class PricingScheme:
    version = Column(Integer, default=1)  # 方案版本号
    
# 激活新方案时，旧方案不删除，只是 is_active = false
# 任务可以引用历史版本的方案
```

---

### 🟠 6. 缺少方案生效时间的处理

**问题描述**：
设计中有 `effective_date` 和 `expire_date`，但没有说明如何使用。

**场景**：
```
1. 用户创建"夏季电价方案"，effective_date=2024-06-01
2. 当前日期是 2024-05-15
3. 用户激活该方案
4. 系统应该立即使用夏季电价，还是等到 6月1日？
```

**建议**：
```python
async def get_current_pricing(self):
    active_scheme = await self._get_active_scheme()
    
    if active_scheme:
        # 检查生效日期
        today = date.today()
        if active_scheme.effective_date > today:
            logger.warning(f"Active scheme '{active_scheme.scheme_name}' not yet effective")
            # 选项1：抛出异常
            # 选项2：回退到兼容模式
            # 选项3：查找其他有效方案
        
        if active_scheme.expire_date and active_scheme.expire_date < today:
            logger.warning(f"Active scheme '{active_scheme.scheme_name}' has expired")
            # 自动停用过期方案
            await deactivate_scheme(active_scheme.id)
            return await self.get_current_pricing()  # 递归查找
        
        return await self._get_scheme_pricings(active_scheme.id)
```

---

## 三、中等问题（Could Fix）

### 🟡 7. 时段编辑后方案自动失效

**问题描述**：
```
场景：
1. 方案A包含时段1（08:00-10:00, ¥1.0）
2. 方案A已激活
3. 用户编辑时段1，改为（08:00-09:00, ¥1.2）
4. 方案A仍然引用时段1，但时段内容已变化
5. 方案A可能不再覆盖完整 24 小时（09:00-10:00 缺失）
```

**建议**：
```python
async def update_pricing(pricing_id, new_data):
    # 1. 更新时段
    await db.execute(
        update(ElectricityPricing)
        .where(ElectricityPricing.id == pricing_id)
        .values(**new_data)
    )
    
    # 2. 检查是否被激活方案引用
    active_scheme = await get_active_scheme()
    if active_scheme:
        relations = await get_scheme_relations(active_scheme.id)
        if pricing_id in [r.pricing_id for r in relations]:
            # 重新校验方案
            validation = await validate_scheme(active_scheme.id)
            if not validation['valid']:
                # 选项1：回滚时段修改
                # 选项2：自动停用方案并通知用户
                await deactivate_scheme(active_scheme.id)
                return {
                    "message": "时段更新成功，但导致激活方案失效，已自动停用",
                    "affected_scheme": active_scheme.scheme_name
                }
```

---

### 🟡 8. 缺少方案预览功能

**问题描述**：
用户在激活方案前，无法预览该方案对当前计费的影响。

**建议**：
```python
@router.post("/pricing-schemes/{id}/preview")
async def preview_scheme_impact(scheme_id: int, db: AsyncSession = Depends(get_db)):
    """预览方案激活后的影响"""
    # 1. 获取当前方案和目标方案
    current_scheme = await get_active_scheme()
    target_scheme = await get_scheme_by_id(scheme_id)
    
    # 2. 对比电价差异
    current_pricings = await get_scheme_pricings(current_scheme.id) if current_scheme else []
    target_pricings = await get_scheme_pricings(target_scheme.id)
    
    # 3. 计算影响
    comparison = compare_pricings(current_pricings, target_pricings)
    
    # 4. 估算成本变化（基于历史用电数据）
    cost_impact = await estimate_cost_impact(current_pricings, target_pricings)
    
    return {
        "current_scheme": current_scheme.scheme_name if current_scheme else "无",
        "target_scheme": target_scheme.scheme_name,
        "price_changes": comparison,
        "estimated_monthly_cost_change": cost_impact
    }
```

---

### 🟡 9. 缺少方案审计日志

**问题描述**：
设计文档"待确认问题"提到：
> "方案版本管理：是否需要保留历史方案用于审计？"

**建议**：
```python
# 新增：方案变更日志表
class PricingSchemeAuditLog(Base):
    __tablename__ = "pricing_scheme_audit_logs"
    
    id = Column(Integer, primary_key=True)
    scheme_id = Column(Integer, ForeignKey("pricing_schemes.id"))
    action = Column(String(20))  # created/updated/activated/deactivated/deleted
    user_id = Column(Integer, ForeignKey("users.id"))
    changes = Column(JSON)  # 变更内容
    timestamp = Column(DateTime, default=datetime.now)

# 激活方案时记录日志
async def activate_scheme(scheme_id, user_id):
    # ... 激活逻辑 ...
    
    # 记录审计日志
    log = PricingSchemeAuditLog(
        scheme_id=scheme_id,
        action="activated",
        user_id=user_id,
        changes={"previous_active_scheme_id": previous_scheme_id}
    )
    db.add(log)
```

---

## 四、轻微问题（Nice to Have）

### 🟢 10. 时间轴可视化性能问题

**问题描述**：
如果方案包含大量时段（如每小时一个时段，共 24 个），时间轴渲染可能卡顿。

**建议**：
- 使用 Canvas 而非 DOM 渲染
- 时段数量超过 50 时，使用虚拟滚动

---

### 🟢 11. 缺少方案模板功能

**建议**：
```python
# 新增：方案模板
class PricingSchemeTemplate(Base):
    __tablename__ = "pricing_scheme_templates"
    
    id = Column(Integer, primary_key=True)
    template_name = Column(String(100))  # "工业用电标准模板"
    description = Column(Text)
    pricings_json = Column(JSON)  # 预定义的时段配置
    is_builtin = Column(Boolean, default=False)  # 是否内置模板

# 用户可以从模板快速创建方案
@router.post("/pricing-schemes/from-template/{template_id}")
async def create_scheme_from_template(template_id: int):
    template = await get_template(template_id)
    # 根据模板创建时段和方案
    ...
```

---

## 五、架构建议

### 建议 1：引入状态机

方案的状态转换应该使用状态机模式：

```
草稿 (draft) → 待激活 (ready) → 激活 (active) → 已过期 (expired)
     ↓                              ↓
   已删除 (deleted)            已停用 (deactivated)
```

### 建议 2：事件驱动架构

方案激活/停用应该发布事件，让其他模块订阅：

```python
# 发布事件
await event_bus.publish(PricingSchemeActivatedEvent(
    scheme_id=scheme_id,
    scheme_name=scheme.scheme_name,
    activated_at=datetime.now()
))

# 订阅事件
@event_bus.subscribe(PricingSchemeActivatedEvent)
async def on_scheme_activated(event):
    # 清除电价缓存
    await cache.delete("current_pricing")
    # 通知正在运行的优化任务
    await notify_optimization_tasks(event.scheme_id)
```

---

## 六、测试建议

### 必须覆盖的测试场景

1. **并发激活测试**：100 个并发请求激活不同方案，验证只有一个成功
2. **时段删除测试**：删除被激活方案引用的时段，验证是否正确阻止
3. **跨日时段测试**：创建 23:00-06:00 时段，验证覆盖检测正确
4. **方案切换测试**：激活新方案后，验证计费逻辑立即使用新电价
5. **兼容模式测试**：无激活方案时，验证兼容模式的行为
6. **数据迁移测试**：模拟现有数据，验证迁移脚本正确性

---

## 七、总体评价

### 优点

✅ **架构清晰**：时段和方案分离的设计合理  
✅ **向下兼容**：考虑了现有数据的迁移  
✅ **用户体验**：最小化界面改动  
✅ **可扩展性**：方案管理为未来功能（如方案模板、方案对比）留下空间

### 缺点

⚠️ **数据一致性**：时段删除、编辑后方案失效的处理不完善  
⚠️ **并发安全**：缺少事务锁和并发控制  
⚠️ **兼容模式**：兼容模式存在计费错误风险  
⚠️ **业务场景**：跨日时段、方案切换时机等关键场景未明确

---

## 八、审查结论

### 🟡 建议：有条件通过，需修复致命缺陷

**必须修复（阻塞发布）**：
1. 时段删除后方案失效的处理（#1）
2. 并发激活方案的事务锁（#2）
3. 兼容模式的校验逻辑（#3）

**强烈建议修复（影响稳定性）**：
4. 跨日时段处理方案明确（#4）
5. 方案切换时机明确（#5）
6. 方案生效时间处理（#6）

**可选修复（增强功能）**：
7-11. 其他中等和轻微问题

### 修复后预期评分：8.5/10

---

**审查人签名**: Kiro  
**审查完成时间**: 2026-03-01 16:45
