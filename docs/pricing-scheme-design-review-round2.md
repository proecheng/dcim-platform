# 电价方案管理系统 - 第二轮对抗性审查报告

**审查日期**: 2026-03-01  
**审查版本**: v1.1 (修复版)  
**审查人**: Kiro (红队视角)  
**审查方法**: 深度对抗性分析

---

## 审查摘要

| 维度 | v1.0 | v1.1 | v1.2 (建议) |
|------|------|------|-------------|
| 技术可行性 | 7/10 | 9/10 | 9.5/10 |
| 业务完整性 | 6/10 | 8/10 | 9/10 |
| 用户体验 | 8/10 | 8/10 | 9/10 |
| 向下兼容性 | 7/10 | 9/10 | 9/10 |
| 可维护性 | 8/10 | 8/10 | 9/10 |
| **总体评分** | **7.2/10** | **8.4/10** | **9.1/10** |

**结论**: ⚠️ 发现 2 个新的致命缺陷，5 个严重问题

---

## 一、新发现的致命缺陷

### 🔴 缺陷 #7：时段编辑后方案失效（未修复）

**问题描述**：
```
场景：
1. 方案A包含时段1（08:00-10:00）、时段2（10:00-12:00）、时段3（12:00-24:00）
2. 方案A已激活，覆盖24小时
3. 用户编辑时段1，改为（08:00-09:00）
4. 方案A仍然是激活状态，但实际上已经不完整（09:00-10:00 缺失）
5. 计费系统使用方案A时，09:00-10:00 无法计费
```

**v1.1 的处理**：
> 文档中提到"时段编辑后方案自动失效"是中等问题（#7），但**没有提供修复方案**

**为什么这是致命缺陷**：
- 用户编辑时段是常见操作
- 激活方案失效后，计费系统会进入兼容模式
- 兼容模式会抛出异常，导致**所有计费功能停止工作**
- 用户可能不知道编辑时段会导致方案失效

**影响范围**：
- 所有使用电价的功能：能耗统计、节能建议、优化任务、报表生成
- 生产环境中，这会导致**系统不可用**

**必须修复**：✅

---

### 🔴 缺陷 #8：方案激活时的竞态条件（未完全修复）

**问题描述**：
```
场景：
1. 用户A在 10:00:00.000 开始激活方案A（事务T1）
2. T1 执行到 SELECT FOR UPDATE，获取锁
3. 用户B在 10:00:00.100 开始激活方案B（事务T2）
4. T2 等待锁释放
5. T1 激活方案A成功，提交事务，释放锁
6. T2 获取锁，执行 UPDATE ... SET is_active=False（停用所有方案，包括刚激活的A）
7. T2 激活方案B成功
8. 结果：方案A被激活了100ms后就被停用，用户A看到"激活成功"，但实际上方案B是激活的
```

**v1.1 的处理**：
```python
async with db.begin():
    await db.execute(text("SELECT id FROM pricing_schemes FOR UPDATE"))
    await db.execute(update(PricingScheme).values(is_active=False))  # ❌ 问题在这里
    await db.execute(
        update(PricingScheme)
        .where(PricingScheme.id == scheme_id)
        .values(is_active=True)
    )
```

**问题**：
- `SELECT FOR UPDATE` 锁定的是**读取的行**，不是整个表
- 如果查询返回0行（所有方案都是 is_active=False），则没有锁定任何行
- 后续的 `UPDATE ... SET is_active=False` 不受锁保护

**正确的做法**：
```python
# 方案1：锁定整个表（推荐）
await db.execute(text("LOCK TABLE pricing_schemes IN EXCLUSIVE MODE"))

# 方案2：使用应用层锁
async with redis_lock("pricing_scheme_activation"):
    # 激活逻辑...

# 方案3：使用乐观锁
# 增加 version 字段，更新时检查版本号
```

**必须修复**：✅

---

## 二、严重问题

### 🟠 问题 #9：数据迁移脚本缺失

**问题描述**：
设计文档提到"数据迁移：将现有时段组合成默认方案"，但**没有提供迁移脚本**。

**风险**：
```
场景：
1. 系统升级到 v1.1
2. 数据库增加了 pricing_schemes 和 scheme_pricing_relations 表
3. 现有的 electricity_pricing 表有10条已启用时段
4. 没有激活方案
5. 用户访问系统，调用 get_current_pricing()
6. 进入兼容模式，校验失败（假设时段不完整）
7. 抛出异常："电价配置不完整，请创建并激活完整方案"
8. 用户不知道如何操作，系统不可用
```

**必须提供**：
1. 自动迁移脚本（Alembic migration）
2. 手动迁移指南（如果自动迁移失败）
3. 回滚脚本（如果迁移出错）

---

### 🟠 问题 #10：兼容模式的异常处理过于严格

**问题描述**：
v1.1 的兼容模式在时段不完整时**直接抛出 500 异常**，这会导致：

```python
# v1.1 的实现
if not validation['valid']:
    raise HTTPException(500, "电价配置不完整...")  # ❌ 过于严格
```

**问题**：
- 用户可能正在逐步配置时段（先配置几个，测试后再补充）
- 抛出 500 异常会导致所有功能不可用
- 用户体验差："我只是想测试一下，为什么系统就崩溃了？"

**建议**：
```python
if not validation['valid']:
    # 记录警告日志
    logger.warning(f"Incomplete pricing config: {validation}")
    
    # 返回已有时段 + 默认电价填补缺失
    return self._fill_gaps_with_default(enabled_pricings, validation['gaps'])
```

**或者提供配置选项**：
```python
# 配置文件
PRICING_STRICT_MODE = False  # 开发环境：宽松模式，生产环境：严格模式
```

---

### 🟠 问题 #11：方案删除的级联影响未考虑

**问题描述**：
设计文档没有说明删除方案时的处理逻辑。

**场景**：
```
1. 方案A是激活方案
2. 用户删除方案A
3. 系统应该如何处理？
   - 选项1：禁止删除激活方案
   - 选项2：允许删除，自动停用
   - 选项3：允许删除，自动激活其他方案
```

**建议**：
```python
async def delete_scheme(scheme_id: int):
    scheme = await db.get(PricingScheme, scheme_id)
    
    if scheme.is_active:
        # 禁止删除激活方案
        raise HTTPException(
            400,
            "无法删除激活方案，请先激活其他方案或停用当前方案"
        )
    
    # 删除方案（级联删除关联关系）
    await db.delete(scheme)
```

---

### 🟠 问题 #12：时段重叠检查的边界条件

**问题描述**：
时段重叠检查算法没有考虑边界条件。

**场景**：
```
时段A: 08:00-10:00
时段B: 10:00-12:00

问题：10:00 这个时刻是否算重叠？
- 如果算重叠：用户无法配置连续时段
- 如果不算重叠：10:00 这个时刻属于哪个时段？
```

**当前算法**：
```python
return not (t1_end <= t2_start or t2_end <= t1_start)
# t1_end=600, t2_start=600
# 600 <= 600 为 True
# not True = False（不重叠）✅ 正确
```

**但是**：
- 文档没有明确说明边界条件的处理
- 用户可能不理解"10:00 属于哪个时段"

**建议**：
- 文档中明确说明：**左闭右开区间** `[start, end)`
- 时段A: `[08:00, 10:00)` 包含 08:00，不包含 10:00
- 时段B: `[10:00, 12:00)` 包含 10:00，不包含 12:00
- 10:00 属于时段B

---

### 🟠 问题 #13：缺少方案停用功能

**问题描述**：
设计文档只有"激活方案"，没有"停用方案"。

**场景**：
```
1. 用户激活了方案A
2. 用户发现方案A有问题，想临时停用
3. 但是没有"停用"按钮，只能激活其他方案
4. 如果没有其他可用方案，用户无法停用
```

**建议**：
```python
@router.post("/pricing-schemes/{id}/deactivate")
async def deactivate_scheme(scheme_id: int):
    """停用方案（进入兼容模式）"""
    async with db.begin():
        await db.execute(
            update(PricingScheme)
            .where(PricingScheme.id == scheme_id)
            .values(is_active=False)
        )
    
    return {"message": "方案已停用，系统进入兼容模式"}
```

---

## 三、中等问题

### 🟡 问题 #14：方案校验的性能问题

**问题描述**：
每次激活方案时都要校验完整性，如果方案包含大量时段（如100个），校验可能很慢。

**建议**：
- 方案创建/编辑时就进行校验，并缓存结果
- 激活时只需检查缓存的校验结果

```python
class PricingScheme:
    validation_result = Column(JSON)  # 缓存校验结果
    validation_time = Column(DateTime)  # 校验时间

async def validate_and_cache(scheme_id):
    validation = await validate_scheme(scheme_id)
    await db.execute(
        update(PricingScheme)
        .where(PricingScheme.id == scheme_id)
        .values(
            validation_result=validation,
            validation_time=datetime.now()
        )
    )
```

---

### 🟡 问题 #15：缺少方案对比功能

**问题描述**：
用户可能想对比两个方案的差异（如夏季电价 vs 冬季电价）。

**建议**：
```python
@router.get("/pricing-schemes/compare")
async def compare_schemes(scheme_id_1: int, scheme_id_2: int):
    """对比两个方案的差异"""
    scheme1 = await get_scheme_pricings(scheme_id_1)
    scheme2 = await get_scheme_pricings(scheme_id_2)
    
    return {
        "price_changes": compare_prices(scheme1, scheme2),
        "coverage_diff": compare_coverage(scheme1, scheme2),
        "estimated_cost_impact": estimate_cost_diff(scheme1, scheme2)
    }
```

---

### 🟡 问题 #16：缺少方案复制功能

**问题描述**：
用户可能想基于现有方案创建新方案（如复制"2024年夏季电价"创建"2025年夏季电价"）。

**建议**：
```python
@router.post("/pricing-schemes/{id}/clone")
async def clone_scheme(scheme_id: int, new_name: str):
    """复制方案"""
    original = await get_scheme(scheme_id)
    new_scheme = PricingScheme(
        scheme_name=new_name,
        description=f"复制自: {original.scheme_name}",
        effective_date=date.today()
    )
    # 复制时段关联...
```

---

## 四、修复建议

### 必须修复（阻塞发布）

1. **缺陷 #7：时段编辑后方案失效**
   ```python
   async def update_pricing(pricing_id, new_data):
       # 更新时段
       await db.execute(update(ElectricityPricing).values(**new_data))
       
       # 检查是否被激活方案引用
       active_scheme = await get_active_scheme()
       if active_scheme and pricing_id in active_scheme.pricing_ids:
           # 重新校验方案
           validation = await validate_scheme(active_scheme.id)
           if not validation['valid']:
               # 自动停用方案
               await deactivate_scheme(active_scheme.id)
               # 发送通知
               await notify_admin(
                   f"方案'{active_scheme.scheme_name}'因时段编辑而自动停用"
               )
   ```

2. **缺陷 #8：方案激活的竞态条件**
   ```python
   async def activate_scheme(scheme_id: int):
       # 使用应用层分布式锁
       async with redis_lock("pricing_scheme_activation", timeout=10):
           async with db.begin():
               # 停用所有方案
               await db.execute(update(PricingScheme).values(is_active=False))
               # 激活目标方案
               await db.execute(
                   update(PricingScheme)
                   .where(PricingScheme.id == scheme_id)
                   .values(is_active=True)
               )
   ```

3. **问题 #9：数据迁移脚本**
   ```python
   # alembic/versions/xxx_add_pricing_schemes.py
   def upgrade():
       # 1. 创建表
       op.create_table('pricing_schemes', ...)
       op.create_table('scheme_pricing_relations', ...)
       
       # 2. 迁移数据
       conn = op.get_bind()
       enabled_pricings = conn.execute(
           "SELECT * FROM electricity_pricing WHERE is_enabled = 1"
       ).fetchall()
       
       if enabled_pricings:
           # 创建默认方案
           conn.execute(
               "INSERT INTO pricing_schemes (scheme_name, is_active, effective_date) "
               "VALUES ('默认方案', 1, date('now'))"
           )
           scheme_id = conn.execute("SELECT last_insert_rowid()").scalar()
           
           # 关联时段
           for pricing in enabled_pricings:
               conn.execute(
                   "INSERT INTO scheme_pricing_relations (scheme_id, pricing_id) "
                   f"VALUES ({scheme_id}, {pricing.id})"
               )
   ```

### 强烈建议修复

4. **问题 #10：兼容模式过于严格** - 提供宽松模式选项
5. **问题 #11：方案删除处理** - 禁止删除激活方案
6. **问题 #13：方案停用功能** - 增加停用 API

---

## 五、测试补充

### 新增必须测试的场景

1. **时段编辑后方案失效测试**
   ```python
   def test_pricing_edit_invalidates_scheme():
       # 1. 创建并激活方案
       scheme = create_and_activate_scheme()
       
       # 2. 编辑时段，导致方案不完整
       edit_pricing(pricing_id, start="08:00", end="09:00")
       
       # 3. 验证方案已自动停用
       active_scheme = get_active_scheme()
       assert active_scheme is None
   ```

2. **方案激活竞态条件测试**
   ```python
   async def test_concurrent_activation_with_lock():
       # 100个并发请求
       tasks = [activate_scheme(i) for i in range(100)]
       results = await asyncio.gather(*tasks, return_exceptions=True)
       
       # 验证：只有1个成功
       success_count = sum(1 for r in results if not isinstance(r, Exception))
       assert success_count == 1
       
       # 验证：只有1个激活方案
       active_schemes = await db.execute(
           select(PricingScheme).where(PricingScheme.is_active == True)
       )
       assert len(active_schemes.all()) == 1
   ```

3. **数据迁移测试**
   ```python
   def test_migration_creates_default_scheme():
       # 1. 准备旧数据
       create_old_pricings()
       
       # 2. 运行迁移
       alembic.upgrade("head")
       
       # 3. 验证默认方案已创建
       scheme = get_active_scheme()
       assert scheme is not None
       assert scheme.scheme_name == "默认方案"
       
       # 4. 验证时段已关联
       pricings = get_scheme_pricings(scheme.id)
       assert len(pricings) > 0
   ```

---

## 六、文档改进建议

### 需要补充的内容

1. **边界条件说明**
   - 时段区间定义：左闭右开 `[start, end)`
   - 重叠判断规则
   - 跨日时段的边界处理

2. **错误处理指南**
   - 各种异常的含义和解决方法
   - 用户操作指南（如何创建完整方案）

3. **运维指南**
   - 如何监控方案状态
   - 如何处理方案失效
   - 如何回滚方案

4. **性能优化建议**
   - 方案校验结果缓存
   - 电价查询缓存策略
   - 大量时段的处理

---

## 七、总体评价

### v1.1 的优点

✅ 修复了原有的3个致命缺陷  
✅ 解决了3个严重问题  
✅ 架构清晰，代码质量高  
✅ 向下兼容性好

### v1.1 的不足

⚠️ 发现2个新的致命缺陷（时段编辑、竞态条件）  
⚠️ 缺少数据迁移脚本  
⚠️ 兼容模式过于严格  
⚠️ 缺少方案停用功能

---

## 八、审查结论

### 🟡 建议：有条件通过，需修复新发现的缺陷

**必须修复（阻塞发布）**：
1. 时段编辑后方案失效的处理（#7）
2. 方案激活的竞态条件（#8）
3. 数据迁移脚本（#9）

**强烈建议修复**：
4. 兼容模式过于严格（#10）
5. 方案删除处理（#11）
6. 方案停用功能（#13）

### 修复后预期评分：9.1/10

---

**审查人签名**: Kiro  
**审查完成时间**: 2026-03-01 17:30  
**下一步**: 修复新发现的缺陷，更新设计文档至 v1.2
