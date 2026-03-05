# Story 28.4 对抗性审查报告

**审查时间:** 2026-03-06
**审查范围:** Demo 数据安全卸载与标记功能
**审查方法:** 对抗性审查（Adversarial Review）

---

## 审查发现

### 🔴 P0 - 严重问题

#### 1. 外键约束顺序不完整
**位置:** `backend/app/demo/service.py:_clear_demo_data_safe()`

**问题:** 删除顺序中缺少大量能源相关子表，可能导致外键约束错误。

**当前代码:**
```python
await _execute_delete_where_demo(PowerDevice, "PowerDevice")
await _execute_delete_where_demo(DistributionCircuit, "DistributionCircuit")
```

**缺失的表:**
- ExecutionResult, ExecutionTask, ExecutionPlan
- MeasureExecutionLog, OpportunityMeasure, ProposalMeasure
- EnergyOpportunity, EnergySavingProposal, EnergySuggestion
- RegulationHistory, LoadRegulationConfig
- DispatchSchedule, DispatchableDevice
- DemandAnalysisRecord, Demand15MinData, OverDemandEvent, DemandHistory
- DeviceShiftConfig, DeviceLoadProfile, PowerCurveData
- OptimizationResult, MonthlyStatistics, RealtimeMonitoring
- EnergyMonthly, EnergyDaily, EnergyHourly, PUEHistory
- PricingConfig, StorageSystemConfig, PVSystemConfig

**影响:** 如果这些表中有数据且有外键关联，卸载会失败。

**修复建议:** 补充完整的删除顺序，参考原 `_clear_demo_data()` 方法。

---

#### 2. 缺少 is_demo 字段的表
**位置:** 数据模型

**问题:** 以下表在设计文档中要求添加 `is_demo`，但实际未添加：
- `PointHistory` - 历史数据表
- `PointRealtime` - 实时数据表
- `Alarm` - 告警记录表

**影响:** 这些表的数据无法通过 `is_demo` 标记区分，可能误删用户数据。

**修复建议:**
1. 为这些表添加 `is_demo` 列
2. 或者通过外键关联判断（如 Point.is_demo）

---

### 🟡 P1 - 重要问题

#### 3. 事务回滚不完整
**位置:** `backend/app/demo/service.py:_clear_demo_data_safe()`

**问题:** 虽然使用了 `async with async_session()` 自动回滚，但错误处理不够细致。

**当前代码:**
```python
if errors:
    raise Exception(f"部分清理失败: {'; '.join(errors)}")
```

**问题:**
- 如果某个表删除失败，后续表仍会尝试删除
- 错误信息不够详细，无法定位具体失败的表

**修复建议:**
```python
async def _execute_delete_where_demo(model, label: str):
    try:
        result = await session.execute(
            delete(model).where(model.is_demo == True)
        )
        deleted_counts[label] = result.rowcount
        logger.info(f"删除 {label}: {result.rowcount} 条记录")
    except Exception as e:
        # 立即抛出异常，触发回滚
        logger.error("清理 %s 失败: %s", label, e, exc_info=True)
        raise Exception(f"清理 {label} 失败: {str(e)}") from e
```

---

#### 4. 缺少删除进度提示
**位置:** `backend/app/demo/service.py:unload_demo_data()`

**问题:** 卸载过程可能耗时较长，但没有进度提示。

**当前代码:**
```python
self.progress_message = "正在卸载..."
```

**修复建议:** 在 `_clear_demo_data_safe()` 中添加进度更新：
```python
total_tables = 17
current = 0
for model, label in tables_to_delete:
    await _execute_delete_where_demo(model, label)
    current += 1
    self._update_progress(int(current / total_tables * 100), f"正在删除 {label}...")
```

---

#### 5. 最小种子未标记
**位置:** `backend/app/seeds/minimal_seed.py`

**问题:** 最小种子创建的默认 Site/Floor/Room 应该标记为 `is_demo=False`，但未修改。

**影响:** 最小种子数据可能被误删。

**修复建议:** 修改 `minimal_seed.py`，创建时显式设置 `is_demo=False`。

---

### 🟢 P2 - 次要问题

#### 6. API 权限检查缺失
**位置:** `backend/app/demo/router.py`

**问题:** 新增的 API 端点缺少权限检查。

**当前代码:**
```python
@router.get("/unload-preview")
async def unload_preview():
    """预览将要删除的 demo 数据统计"""
```

**修复建议:** 添加管理员权限检查：
```python
@router.get("/unload-preview")
async def unload_preview(_: User = Depends(require_admin)):
    """预览将要删除的 demo 数据统计"""
```

---

#### 7. 前端未实施
**位置:** `frontend/src/components/DemoDataLoader.vue`

**问题:** 前端组件修改未完成，用户无法通过界面使用新功能。

**影响:** 功能不完整，用户体验差。

**修复建议:** 按照 `28-4-frontend-modification-guide.md` 完成前端修改。

---

#### 8. 测试覆盖不足
**位置:** `backend/tests/demo/test_unload_safe.py`

**问题:** 测试用例不够全面，缺少：
- 外键级联删除测试
- 事务回滚测试
- 大量数据删除性能测试

**修复建议:** 补充测试用例。

---

## 审查总结

### 问题统计
- P0 严重问题: 2 个
- P1 重要问题: 4 个
- P2 次要问题: 3 个

### 风险评估
- **数据安全风险:** 🔴 高 - 外键约束和缺失字段可能导致数据不一致
- **功能完整性:** 🟡 中 - 核心功能已实现，但前端未完成
- **代码质量:** 🟢 良好 - 整体架构合理，需要细节优化

### 建议
1. **立即修复 P0 问题** - 补充完整的删除顺序和缺失字段
2. **优先修复 P1 问题** - 完善错误处理和进度提示
3. **后续优化 P2 问题** - 完成前端和测试

---

## 修复优先级

### 第一轮修复（必须）
1. 补充完整的删除顺序
2. 为 PointHistory/PointRealtime/Alarm 添加 is_demo 字段或外键判断逻辑
3. 完善事务回滚和错误处理

### 第二轮修复（推荐）
4. 添加删除进度提示
5. 修改最小种子标记
6. 添加 API 权限检查

### 第三轮修复（可选）
7. 完成前端修改
8. 补充测试用例

---

**审查结论:** 核心功能已实现，但存在数据安全风险，需要修复 P0 问题后才能上线。
