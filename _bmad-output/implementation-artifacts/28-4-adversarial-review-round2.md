# Story 28.4 对抗性审查报告 - 第二轮

**审查时间:** 2026-03-06
**审查范围:** Demo 数据安全卸载与标记功能（P0 修复后）
**审查方法:** 对抗性审查（Adversarial Review - Round 2）

---

## 第一轮 P0 问题修复验证

### ✅ P0-1: 外键约束顺序 - 已修复
- 补充了完整的能源相关子表删除顺序
- 共 30+ 个能源相关表按依赖顺序删除
- 删除顺序：PointHistory → Point → 能源子表 → PowerDevice → DistributionCircuit → DistributionPanel → Device → Row → Room → Floor → Site

### ✅ P0-2: API 权限检查 - 已修复
- `unload_preview` 和 `get_stats` 端点已添加 `require_admin` 依赖
- 确保只有管理员可以访问敏感操作

---

## 第二轮审查发现

### 🔴 P0 - 严重问题

#### 1. PointHistory/PointRealtime 缺少 is_demo 字段
**位置:** 数据模型

**问题:** 这两个表没有 `is_demo` 字段，但在删除逻辑中使用了 `where(model.is_demo == True)`。

**影响:**
- 运行时会抛出 `AttributeError: 'PointHistory' object has no attribute 'is_demo'`
- 卸载功能完全无法使用

**解决方案:**
有两种方案：

**方案 A（推荐）:** 通过外键关联判断
```python
# 删除 is_demo=True 的 Point 关联的历史数据
await session.execute(
    delete(PointHistory).where(
        PointHistory.point_id.in_(
            select(Point.id).where(Point.is_demo == True)
        )
    )
)
```

**方案 B:** 为这两个表添加 is_demo 字段
- 需要新的数据库迁移
- 需要修改模型
- 需要修改种子脚本

**推荐方案 A**，因为历史数据和实时数据本质上是从属于 Point 的，应该跟随 Point 的 is_demo 属性。

---

#### 2. Alarm 表的处理缺失
**位置:** `_clear_demo_data_safe()`

**问题:** Alarm（告警记录）表没有在删除逻辑中处理。

**分析:**
- Alarm 是运行时产生的数据，不是配置数据
- Alarm 有外键 `point_id` 指向 Point
- 如果删除 Point 但不删除 Alarm，会违反外键约束

**解决方案:**
```python
# 在删除 Point 之前，先删除关联的 Alarm
await session.execute(
    delete(Alarm).where(
        Alarm.point_id.in_(
            select(Point.id).where(Point.is_demo == True)
        )
    )
)
```

---

### 🟡 P1 - 重要问题

#### 3. 能源相关表可能没有 is_demo 字段
**位置:** 能源相关子表

**问题:** 以下表在删除逻辑中使用，但可能没有 `is_demo` 字段：
- ExecutionResult, ExecutionTask, ExecutionPlan
- MeasureExecutionLog, OpportunityMeasure, ProposalMeasure
- EnergyOpportunity, EnergySavingProposal, EnergySuggestion
- 等 20+ 个表

**验证方法:**
```bash
cd backend
python -c "
from app.models.energy import ExecutionResult
print(hasattr(ExecutionResult, 'is_demo'))
"
```

**解决方案:**
如果这些表没有 `is_demo` 字段，应该：
1. 直接全部删除（因为是运行时数据）
2. 或者通过外键关联判断

---

#### 4. 删除顺序可能仍有问题
**位置:** `_clear_demo_data_safe()`

**问题:** 能源相关表之间的外键依赖关系未明确验证。

**风险:**
- ExecutionResult 可能依赖 ExecutionTask
- ExecutionTask 可能依赖 ExecutionPlan
- 如果顺序错误，仍会触发外键约束错误

**建议:**
- 查看每个表的外键定义
- 按照实际依赖关系调整删除顺序
- 或者使用 `CASCADE` 删除

---

#### 5. 事务超时风险
**位置:** `_clear_demo_data_safe()`

**问题:** 删除 40+ 个表在一个事务中，如果数据量大可能超时。

**建议:**
- 添加超时配置
- 或者分批提交（但会失去原子性）
- 添加进度提示

---

### 🟢 P2 - 次要问题

#### 6. 缺少删除前数据备份机制
**位置:** 整体设计

**问题:** 一旦删除，数据无法恢复。

**建议:**
- 添加删除前导出功能
- 或者软删除机制

---

#### 7. 缺少删除后验证
**位置:** `_clear_demo_data_safe()`

**问题:** 删除后没有验证是否还有遗漏的 demo 数据。

**建议:**
```python
# 删除后验证
remaining_stats = await self.get_demo_data_stats()
if remaining_stats:
    logger.warning(f"仍有 demo 数据未删除: {remaining_stats}")
```

---

## 修复优先级

### 立即修复（阻塞上线）
1. **P0-1:** 修复 PointHistory/PointRealtime 的删除逻辑（使用外键关联）
2. **P0-2:** 添加 Alarm 表的删除逻辑

### 第二优先级（建议修复）
3. **P1-3:** 验证所有能源表是否有 is_demo 字段
4. **P1-4:** 验证并调整删除顺序

### 第三优先级（后续优化）
5. **P1-5:** 添加事务超时配置
6. **P2-6:** 添加数据备份机制
7. **P2-7:** 添加删除后验证

---

## 修复方案

### 方案 1: 通过外键关联删除（推荐）

```python
async def _clear_demo_data_safe(self):
    """安全清理演示数据 - 仅删除 is_demo=True 的记录"""
    async with async_session() as session:
        deleted_counts = {}

        try:
            # 1. 删除 demo Point 关联的历史数据和实时数据
            # PointHistory
            result = await session.execute(
                delete(PointHistory).where(
                    PointHistory.point_id.in_(
                        select(Point.id).where(Point.is_demo == True)
                    )
                )
            )
            deleted_counts["PointHistory"] = result.rowcount

            # PointRealtime
            result = await session.execute(
                delete(PointRealtime).where(
                    PointRealtime.point_id.in_(
                        select(Point.id).where(Point.is_demo == True)
                    )
                )
            )
            deleted_counts["PointRealtime"] = result.rowcount

            # Alarm
            result = await session.execute(
                delete(Alarm).where(
                    Alarm.point_id.in_(
                        select(Point.id).where(Point.is_demo == True)
                    )
                )
            )
            deleted_counts["Alarm"] = result.rowcount

            # 2. 删除有 is_demo 字段的表
            await _execute_delete_where_demo(AlarmThreshold, "AlarmThreshold")
            await _execute_delete_where_demo(Point, "Point")

            # 3. 能源相关表 - 直接全部删除（运行时数据）
            await session.execute(delete(ExecutionResult))
            await session.execute(delete(ExecutionTask))
            # ... 其他能源表

            # 4. 有 is_demo 字段的配置表
            await _execute_delete_where_demo(PowerDevice, "PowerDevice")
            # ... 其他表

            await session.commit()
            return deleted_counts

        except Exception as e:
            logger.error("Demo 数据清理失败: %s", e, exc_info=True)
            raise
```

---

## 审查结论

**严重程度:** 🔴 高危 - 存在阻塞性 P0 问题

**建议:**
1. 立即修复 P0 问题（PointHistory/PointRealtime/Alarm 的删除逻辑）
2. 验证所有能源表的 is_demo 字段
3. 修复后再次测试
4. 通过测试后才能上线

**预计修复时间:** 30-45 分钟
