# Story 28.4 实施进度报告

**Story ID:** 28-4-demo-data-safe-unload-and-tagging
**状态:** 实施中 (80% 完成)
**日期:** 2026-03-06

---

## 已完成工作

### 1. 数据库迁移 ✅
- **文件:** `backend/alembic/versions/b74705769037_add_is_demo_column_to_core_tables.py`
- **内容:** 为 17 个核心表添加 `is_demo` 列
- **执行状态:** 已完成并标记为 `b74705769037`
- **验证:** 所有表已成功添加 `is_demo` 列，现有数据已标记为 `is_demo=True`

**涉及表:**
- 设备: devices, points
- 空间: sites, floors, rooms, rows
- 配电: transformers, meter_points, distribution_panels, distribution_circuits, power_devices
- 制冷: cooling_groups, cooling_units, cold_aisles
- 告警: alarm_thresholds
- 其他: floor_maps, electricity_pricing

### 2. 模型字段添加 ✅
已为以下模型添加 `is_demo` 字段：
- `backend/app/models/device.py` - Device
- `backend/app/models/point.py` - Point
- `backend/app/models/spatial.py` - Site, Floor, Room, Row
- `backend/app/models/energy.py` - Transformer, MeterPoint, DistributionPanel, DistributionCircuit, PowerDevice, ElectricityPricing
- `backend/app/models/cooling.py` - CoolingGroup, CoolingUnit, ColdAisle
- `backend/app/models/alarm.py` - AlarmThreshold
- `backend/app/models/floor_map.py` - FloorMap

### 3. Demo 种子脚本更新 ✅
已更新以下种子脚本，创建时标记 `is_demo=True`：
- `backend/app/demo/seeds/datacenter_seed.py`
- `backend/app/demo/seeds/power_seed.py`
- `backend/app/demo/seeds/cooling_seed.py`

---

## 待完成工作

### 4. 卸载逻辑重构 ⏳
**文件:** `backend/app/demo/service.py`

**需要修改:**
1. 将 `_clear_demo_data()` 方法重命名为 `_clear_demo_data_legacy()`
2. 添加新方法 `_clear_demo_data_safe()` - 仅删除 `is_demo=True` 的记录
3. 添加新方法 `get_demo_data_stats()` - 统计 demo 数据数量
4. 修改 `unload_demo_data()` 方法，调用新的安全卸载方法

**实现要点:**
- 按外键依赖顺序删除（子表→父表）
- 使用 `delete(Model).where(Model.is_demo == True)` 批量删除
- 使用事务确保原子性
- 记录删除统计信息

**参考实现:** 见 `/tmp/new_unload_method.py`

### 5. API 端点实现 ⏳
**文件:** `backend/app/api/v1/demo.py`

**需要添加:**
```python
@router.get("/unload-preview")
async def unload_preview(current_user: User = Depends(get_current_admin_user)):
    """预览将要删除的 demo 数据统计"""
    stats = await demo_service.get_demo_data_stats()
    return {"success": True, "stats": stats}

@router.post("/unload")
async def unload_demo(current_user: User = Depends(get_current_admin_user)):
    """执行 demo 数据卸载"""
    result = await demo_service.unload_demo_data()
    return result

@router.get("/stats")
async def get_stats(current_user: User = Depends(get_current_admin_user)):
    """获取当前 demo 数据统计"""
    stats = await demo_service.get_demo_data_stats()
    return {"success": True, "stats": stats}
```

### 6. 前端组件修改 ⏳
**文件:** `frontend/src/components/DemoDataLoader.vue`

**需要修改:**
1. 添加 `unloadPreview()` 方法调用 `/api/v1/demo/unload-preview`
2. 修改卸载确认对话框，显示删除预览统计
3. 添加二次确认机制

**文件:** `frontend/src/api/modules/demo.ts`

**需要添加:**
```typescript
export const demoApi = {
  unloadPreview: () => request.get('/demo/unload-preview'),
  unload: () => request.post('/demo/unload'),
  getStats: () => request.get('/demo/stats'),
}
```

### 7. 测试编写 ⏳
**文件:** `backend/tests/demo/test_unload_safe.py`

**测试用例:**
- 测试 `is_demo=True` 的记录被正确删除
- 测试 `is_demo=False` 的记录被保留
- 测试外键级联删除顺序正确
- 测试事务回滚机制
- 测试删除预览统计准确性
- 测试混合场景（demo 数据 + 用户数据共存）

---

## 实施步骤（剩余工作）

### Step 1: 重构卸载逻辑
```bash
# 1. 备份现有 service.py
cp backend/app/demo/service.py backend/app/demo/service.py.bak

# 2. 在 DemoService 类中添加新方法
# - _clear_demo_data_safe()
# - get_demo_data_stats()

# 3. 修改 unload_demo_data() 调用新方法
# 将 await self._clear_demo_data() 改为 await self._clear_demo_data_safe()
```

### Step 2: 实现 API 端点
```bash
# 编辑 backend/app/api/v1/demo.py
# 添加三个新端点: unload-preview, unload, stats
```

### Step 3: 修改前端组件
```bash
# 1. 编辑 frontend/src/api/modules/demo.ts
# 2. 编辑 frontend/src/components/DemoDataLoader.vue
```

### Step 4: 编写测试
```bash
# 创建 backend/tests/demo/test_unload_safe.py
# 运行测试: pytest backend/tests/demo/test_unload_safe.py
```

### Step 5: 手动测试
```bash
# 1. 启动服务
start.bat

# 2. 加载 demo 数据
# 3. 手动创建一些自定义数据（is_demo=False）
# 4. 调用卸载预览 API
# 5. 执行卸载
# 6. 验证自定义数据被保留
```

---

## 技术要点

### 外键依赖删除顺序
```
PointHistory/PointRealtime/AlarmThreshold
  ↓
Point
  ↓
Device
  ↓
PowerDevice → DistributionCircuit → DistributionPanel
  ↓
Row → Room → Floor → Site
```

### 批量删除示例
```python
from sqlalchemy import delete

# 批量删除 is_demo=True 的记录
result = await session.execute(
    delete(Device).where(Device.is_demo == True)
)
deleted_count = result.rowcount
```

### 事务管理
```python
async with async_session() as session:
    try:
        # 执行所有删除操作
        await _execute_delete_where_demo(...)
        # 提交事务
        await session.commit()
    except Exception as e:
        # 自动回滚
        await session.rollback()
        raise
```

---

## 验收标准

- [ ] 所有 AC 通过验证
- [ ] 单元测试覆盖率 ≥ 80%
- [ ] 集成测试全部通过
- [ ] 代码审查通过（无 P0/P1 问题）
- [ ] 在 demo 和生产环境中手动测试通过
- [ ] 文档更新完成

---

## 风险与注意事项

1. **外键约束:** 必须按照正确的顺序删除，否则会触发外键约束错误
2. **事务原子性:** 确保所有删除操作在同一事务中，失败时全部回滚
3. **性能考虑:** 大量数据删除可能耗时较长，需要添加进度提示
4. **数据安全:** 删除前必须有明确的预览和确认机制

---

**下一步行动:** 完成剩余的 4-7 步骤，然后进行对抗性审查和代码审查。
