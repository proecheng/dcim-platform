# Story 5.4: 数据质量标记与误告警防护

Status: ready-for-dev

## Story

As a 运维工程师,
I want 系统在通信中断时自动标记数据质量,
So that 不会基于过期数据产生误告警。

## Acceptance Criteria (验收标准)

1. **AC-1: 告警引擎跳过不可靠点位** — 告警引擎在执行阈值检测前，检查点位的数据质量标记。当 `PointRealtime.quality == 2`（坏/不可靠）时，跳过该点位的所有阈值检测，不产生告警。当 `quality == 1`（不确定）时，正常检测但在告警消息中附加"[数据质量不确定]"前缀
2. **AC-2: 通信中断时自动标记不可靠** — 当数据源通信中断（`DataSource.status == "interrupted"`）时，受影响点位的 `PointRealtime.quality` 自动设为 2（坏），`PointRealtime.status` 设为 "offline"。同时通过 WebSocket system 通道（`/ws/system` 端点已存在于 main.py 第325行）广播数据质量变更事件（`type: "data_quality_changed"`），前端实时更新显示
3. **AC-3: 通信恢复后自动解除标记** — 当数据源通信恢复（`DataSource.consecutive_failures == 0`）时，受影响点位的 `PointRealtime.quality` 自动恢复为 0（好），`PointRealtime.status` 恢复为 "normal"。告警引擎恢复对这些点位的阈值检测。同时广播恢复事件
4. **AC-4: 模拟器数据质量集成** — 模拟器（`simulator.py`）在采集点位数据前，从告警引擎质量缓存获取 quality 值。如果 quality == 2，跳过 `alarm_engine.evaluate()` 调用和自动恢复逻辑（仍然更新实时值和历史数据，但不触发告警检测）。Redis 缓存写入使用实际 quality 值替代硬编码 0
5. **AC-5: 数据质量 API** — 新增 `GET /api/v1/data-quality/status` 端点，返回所有点位的数据质量状态汇总（正常/不确定/不可靠的点位数量）。新增 `GET /api/v1/data-quality/points` 端点，支持按 quality 值筛选，JOIN Point 表返回点位详情
6. **AC-6: 前端数据质量展示** — 实时监控页面的点位列表中，显示数据质量标记列（使用 Element Plus Tag 组件：绿色"正常" / 橙色"不确定" / 红色"不可靠"）。不可靠点位行高亮显示（浅红色背景 `#FEF0F0`）
7. **AC-7: 数据质量变更通知** — 当点位数据质量从正常变为不可靠时，通过 WebSocket system 通道推送通知消息（`type: "data_quality_changed"`），前端收到后使用 `ElNotification` 显示警告："N个点位数据质量变为不可靠"。恢复时显示成功通知
8. **AC-8: 告警引擎质量缓存** — 告警引擎维护点位质量状态的内存缓存（`_point_quality: Dict[int, int]`），在 `load_thresholds()` 时同步加载 `PointRealtime` 的 quality 值，避免每次 evaluate 都查询数据库。通信监控服务标记质量变更时，同步调用 `alarm_engine.update_points_quality()` 更新引擎缓存
9. **AC-9: 后端测试** — 测试告警引擎跳过不可靠点位（quality==2 返回空列表）、测试 quality==1 消息带前缀、测试质量缓存更新方法、测试数据质量 API 端点、测试通信恢复后恢复检测

## Tasks / Subtasks (任务分解)

- [ ] Task 1: 后端 — 告警引擎质量缓存 (AC: #1, #8)
  - [ ] 1.1 在 `backend/app/engines/alarm_engine.py` 的 `AlarmEngine.__init__` 中新增 `_point_quality: Dict[int, int] = {}`（点位ID → 质量值映射）。注意：`PointRealtime` 已在第16行导入，无需额外 import
  - [ ] 1.2 在 `load_thresholds()` 方法中，在现有 session 内加载所有 `PointRealtime` 的 quality 值到 `_point_quality` 缓存：`select(PointRealtime.point_id, PointRealtime.quality)`
  - [ ] 1.3 新增 `get_point_quality(point_id: int) -> int` 方法，返回 `_point_quality.get(point_id, 0)`
  - [ ] 1.4 新增 `update_point_quality(point_id: int, quality: int)` 方法，更新单个点位的质量缓存
  - [ ] 1.5 新增 `update_points_quality(point_ids: List[int], quality: int)` 方法，批量更新多个点位的质量缓存
  - [ ] 1.6 在 `evaluate()` 方法开头，检查 `_point_quality.get(point_id, 0)`：如果 == 2 则直接返回空列表（跳过检测）；如果 == 1 则正常检测，但在返回的 `EvaluateResult.alarm_message` 前加 "[数据质量不确定] " 前缀

- [ ] Task 2: 后端 — WebSocket broadcast_system 方法 (AC: #2, #7)
  - [ ] 2.1 在 `backend/app/services/websocket.py` 的 `ConnectionManager` 类中新增 `broadcast_system()` 方法（CRITICAL — 当前不存在，只有 broadcast_realtime 和 broadcast_alarm）：
    ```python
    async def broadcast_system(self, system_data: dict):
        """广播系统状态消息"""
        message = {"type": "system", "data": system_data}
        await self.broadcast(message, "system")
    ```
  - [ ] 2.2 确认 `active_connections` 初始化 dict 中添加 `"system": []`（当前只有 realtime/alarms/control，虽然 connect() 会动态创建，但显式初始化更安全）

- [ ] Task 3: 后端 — 通信监控服务增强 (AC: #2, #3, #7, #8)
  - [ ] 3.1 修改 `backend/app/services/communication_monitor.py` 的 `mark_unreliable_points()` 函数签名，改为返回 `List[int]`（返回 point_ids 列表，当前是 fire-and-forget 不返回值）
  - [ ] 3.2 在 `mark_unreliable_points()` 的 `update(PointRealtime)...values()` 调用中，增加 `status` 字段更新：quality==2 时 `status="offline"`，quality==0 时 `status="normal"`
  - [ ] 3.3 在 `mark_unreliable_points()` 末尾，调用 `alarm_engine.update_points_quality(point_ids, quality)` 同步更新告警引擎缓存
  - [ ] 3.4 在 `check_communication_status()` 中，获取 `mark_unreliable_points()` 的返回值 `point_ids`，然后通过 WebSocket 广播：`await ws_manager.broadcast_system({"type": "data_quality_changed", "datasource_id": ds.id, "datasource_name": ds.name, "quality": 2, "affected_point_ids": point_ids, "affected_count": len(point_ids), "message": f"数据源 {ds.name} 通信中断，{len(point_ids)} 个点位标记为不可靠", "timestamp": datetime.now().isoformat()})`
  - [ ] 3.5 通信恢复时同样获取 point_ids 并广播恢复事件：`{"type": "data_quality_changed", "quality": 0, ...}`
  - [ ] 3.6 导入依赖：`from ..engines.alarm_engine import alarm_engine`、`from .websocket import ws_manager`、`from datetime import datetime`

- [ ] Task 4: 后端 — 模拟器数据质量集成 (AC: #4)
  - [ ] 4.1 修改 `backend/app/services/simulator.py` 的 `collect_and_save()` 方法，在告警检测前检查质量：从告警引擎缓存获取 `quality = alarm_engine.get_point_quality(point.id)`
  - [ ] 4.2 当 quality == 2 时，跳过 `alarm_engine.evaluate()` 调用和自动恢复逻辑，但仍然更新实时值和历史数据
  - [ ] 4.3 在 Redis 缓存写入中，将 quality 值从硬编码的 `0` 改为实际的 `quality` 值

- [ ] Task 5: 后端 — 数据质量 API (AC: #5)
  - [ ] 5.1 新建 `backend/app/api/v1/data_quality.py` 路由文件
  - [ ] 5.2 实现 `GET /api/v1/data-quality/status` 端点：查询 `PointRealtime` 表，按 quality 分组统计（0=正常, 1=不确定, 2=不可靠），返回各组的数量和点位ID列表
  - [ ] 5.3 实现 `GET /api/v1/data-quality/points` 端点：支持 `quality` 查询参数筛选，JOIN Point 表返回点位详情（point_code, point_name, device_type, quality, status, updated_at）
  - [ ] 5.4 新建 `backend/app/schemas/data_quality.py`，定义 `DataQualityStatus`（total, normal_count, uncertain_count, unreliable_count）和 `DataQualityPoint`（point_id, point_code, point_name, device_type, quality, quality_text, status, updated_at）schema
  - [ ] 5.5 在 `backend/app/api/v1/__init__.py` 中注册路由：`from .data_quality import router as data_quality_router`，挂载到 `/data-quality` 前缀

- [ ] Task 6: 前端 — 数据质量展示组件 (AC: #6)
  - [ ] 6.1 在 `frontend/src/components/common/` 新建 `DataQualityTag.vue` 组件：接收 `quality: number` prop，显示对应的 Tag（0=绿色"正常", 1=橙色"不确定", 2=红色"不可靠"），使用 Element Plus 的 `<el-tag>` 组件
  - [ ] 6.2 在 `frontend/src/views/environment/overview.vue` 的传感器列表表格中，新增"数据质量"列，使用 `DataQualityTag` 组件渲染（该页面已有 point_name/status 列，在 status 列后添加 quality 列）
  - [ ] 6.3 在 `frontend/src/views/device-manage/detail.vue` 的点位实时数据表格中，新增"数据质量"列（该页面使用 `PointRealtimeItem` 类型，需确认 quality 字段已包含在 API 返回中）
  - [ ] 6.4 不可靠点位行添加 `row-class-name` 样式：quality == 2 时行背景色为 `#FEF0F0`（浅红色）

- [ ] Task 7: 前端 — 数据质量变更通知 (AC: #7)
  - [ ] 7.1 新建 `frontend/src/composables/useDataQuality.ts` composable（不要集成到 useAlarm.ts — 它们使用不同的 WebSocket 通道）
  - [ ] 7.2 在 composable 中使用 `useWebSocket({ url: '/ws/system' })` 连接 system 通道，监听 `data_quality_changed` 类型的消息
  - [ ] 7.3 收到 quality == 2 的消息时，使用 Element Plus 的 `ElNotification` 显示警告通知："N个点位数据质量变为不可靠"
  - [ ] 7.4 收到 quality == 0 的恢复消息时，显示成功通知："数据源通信恢复，N个点位数据质量已恢复正常"
  - [ ] 7.5 在 `frontend/src/layouts/MainLayout.vue` 中挂载 `useDataQuality()` composable，确保全局监听

- [ ] Task 8: 前端 — 数据质量 API 模块 (AC: #5, #6)
  - [ ] 8.1 新建 `frontend/src/api/modules/dataQuality.ts`，实现 `getDataQualityStatus()` 和 `getDataQualityPoints(params)` API 调用
  - [ ] 8.2 定义 TypeScript 接口：`DataQualityStatus`、`DataQualityPoint`

- [ ] Task 9: 后端测试 (AC: #9)
  - [ ] 9.1 新建 `backend/tests/test_data_quality.py`
  - [ ] 9.2 测试告警引擎 — quality == 2 时 evaluate() 返回空列表
  - [ ] 9.3 测试告警引擎 — quality == 1 时 evaluate() 正常返回但消息带前缀
  - [ ] 9.4 测试告警引擎 — quality == 0 时正常检测
  - [ ] 9.5 测试 update_point_quality / update_points_quality 缓存更新
  - [ ] 9.6 测试 GET /api/v1/data-quality/status 返回正确统计
  - [ ] 9.7 测试 GET /api/v1/data-quality/points 按 quality 筛选

- [ ] Task 10: 前端构建验证
  - [ ] 10.1 `npm run build` 构建成功

## Dev Notes (开发指南)

### 1. 文件位置

```
backend/app/engines/alarm_engine.py                # 修改 — 新增质量缓存（_point_quality）、evaluate 跳过逻辑、get/update 方法
backend/app/services/websocket.py                  # 修改 — 新增 broadcast_system() 方法
backend/app/services/communication_monitor.py      # 修改 — mark_unreliable_points 返回 point_ids、增加 status 更新、引擎缓存同步、WebSocket 广播
backend/app/services/simulator.py                  # 修改 — 采集前检查质量，跳过不可靠点位的告警检测，Redis quality 值修正
backend/app/api/v1/data_quality.py                 # 新建 — 数据质量 API
backend/app/schemas/data_quality.py                # 新建 — 数据质量 Schema
backend/app/api/v1/__init__.py                     # 修改 — 注册 data_quality 路由
backend/tests/test_data_quality.py                 # 新建 — 数据质量测试
frontend/src/components/common/DataQualityTag.vue  # 新建 — 数据质量标签组件
frontend/src/api/modules/dataQuality.ts            # 新建 — 数据质量 API 模块
frontend/src/composables/useDataQuality.ts         # 新建 — 数据质量 WebSocket 通知（独立 composable，使用 system 通道）
frontend/src/views/environment/overview.vue        # 修改 — 传感器列表增加质量列
frontend/src/views/device-manage/detail.vue        # 修改 — 点位实时数据增加质量列
frontend/src/layouts/MainLayout.vue                # 修改 — 挂载 useDataQuality composable
```

### 2. 现有基础设施（直接复用，不要重复实现）

**PointRealtime.quality 字段已存在**（point.py 第55行）：
```python
quality = Column(Integer, default=0, comment="数据质量: 0=好 1=不确定 2=坏")
```

**communication_monitor.py 已实现基础逻辑**（第9-52行）：
- `check_communication_status()` 检测数据源中断/恢复
- `mark_unreliable_points()` 批量更新 PointRealtime.quality
- 中断时 quality=2，恢复时 quality=0
- 本 Story 需要在此基础上增加：告警引擎缓存同步、WebSocket 广播、status 字段更新

**告警引擎 evaluate() 入口**（alarm_engine.py 第149行）：
```python
def evaluate(self, point_id: int, value: float, point_type: str = "AI") -> List[EvaluateResult]:
```
在此方法开头加入质量检查即可。

### 3. 告警引擎质量缓存设计

```python
class AlarmEngine:
    def __init__(self):
        # ... 现有字段 ...
        self._point_quality: Dict[int, int] = {}  # 新增：点位质量缓存

    async def load_thresholds(self) -> int:
        # ... 现有加载逻辑 ...
        # 新增：加载质量数据
        quality_result = await session.execute(
            select(PointRealtime.point_id, PointRealtime.quality)
        )
        self._point_quality = {row[0]: row[1] for row in quality_result.all()}

    def evaluate(self, point_id, value, point_type="AI"):
        if not self._loaded:
            return []
        # 新增：质量检查
        quality = self._point_quality.get(point_id, 0)
        if quality == 2:
            return []  # 不可靠，跳过检测
        # ... 现有检测逻辑 ...
        # 如果 quality == 1，在结果消息前加前缀
        if quality == 1:
            for r in results:
                r.alarm_message = f"[数据质量不确定] {r.alarm_message}"
        return results

    def get_point_quality(self, point_id: int) -> int:
        return self._point_quality.get(point_id, 0)

    def update_point_quality(self, point_id: int, quality: int):
        self._point_quality[point_id] = quality

    def update_points_quality(self, point_ids: List[int], quality: int):
        for pid in point_ids:
            self._point_quality[pid] = quality
```

### 4. 模拟器质量检查位置

在 `simulator.py` 的 `collect_and_save()` 方法中，第126-128行之前插入质量检查：

```python
# 检查告警（使用告警引擎替代内联检测）
status = "normal"
alarms_to_create = []

# 新增：检查数据质量
point_quality = alarm_engine.get_point_quality(point.id)

if point.point_type in ["AI", "DI"] and point_quality < 2:  # 修改：quality < 2 才检测
    triggered_list = alarm_engine.evaluate(point.id, new_value, point.point_type)
    # ... 现有逻辑 ...
```

### 5. WebSocket system 通道广播

`ws_manager` 当前没有 `broadcast_system()` 方法（只有 `broadcast_realtime` 和 `broadcast_alarm`），需要新增。后端 `/ws/system` WebSocket 端点已存在（main.py 第325-336行），前端可通过 `useWebSocket({ url: '/ws/system' })` 连接。通信监控定时任务已在 main.py 第185-195行注册（每30秒调用 `check_communication_status`）。消息格式：

```python
await ws_manager.broadcast_system({
    "type": "data_quality_changed",
    "datasource_id": ds.id,
    "datasource_name": ds.name,
    "quality": 2,  # 或 0
    "affected_point_ids": point_ids,
    "affected_count": len(point_ids),
    "message": "数据源 XXX 通信中断，N个点位标记为不可靠",
    "timestamp": datetime.now().isoformat()
})
```

### 6. 前端 DataQualityTag 组件

```vue
<template>
  <el-tag :type="tagType" size="small" effect="light">
    {{ tagText }}
  </el-tag>
</template>

<script setup lang="ts">
const props = defineProps<{ quality: number }>()
const tagType = computed(() => {
  if (props.quality === 2) return 'danger'
  if (props.quality === 1) return 'warning'
  return 'success'
})
const tagText = computed(() => {
  if (props.quality === 2) return '不可靠'
  if (props.quality === 1) return '不确定'
  return '正常'
})
</script>
```

### 7. 关键约束

- **不新增数据库字段**: `PointRealtime.quality` 已存在，直接复用
- **不新增数据库表**: 仅新增 API 路由和 Schema
- **告警引擎缓存同步**: 通信监控标记质量后必须同步更新引擎缓存，否则引擎仍会用旧的质量值
- **模拟器兼容**: 模拟器仍然更新实时值（保持数据流），只是跳过告警检测
- **WebSocket action 命名**: system 通道使用 `type: "data_quality_changed"`，不要与 alarm 通道混淆
- **ORM session expire**: communication_monitor 中 commit 后不要读取 ORM 属性，使用已知值
- **自动导入**: 前端 Vue API 无需手动 import（unplugin-auto-import）
- **权限控制**: 数据质量 API 需要 viewer 权限即可查看

### 8. 通信监控调度（已存在）

`check_communication_status()` 已在 `main.py` 的 `lifespan()` 中注册为定时任务（第185-195行），每30秒执行一次。本 Story 不需要修改调度逻辑，只需要增强 `communication_monitor.py` 中的 `mark_unreliable_points()` 和 `check_communication_status()` 函数，添加告警引擎缓存同步和 WebSocket 广播。

### 9. Story 5.2/5.3 经验教训

- `broadcast_alarm()` 从 data dict 提取 action 到消息顶层，构建 `{type: "alarm", action: "xxx", data: {...}}`
- `broadcast_system()` 需要新建（参考 broadcast_alarm 模式），消息格式 `{type: "system", data: {...}}`
- 告警引擎 `load_thresholds()` 在启动时和版本变更时调用，质量缓存需要在同一时机加载
- 通信监控定时任务已在 main.py lifespan 中注册（第185-195行），每30秒执行
- `mark_unreliable_points()` 当前不返回 point_ids，需要修改为返回 `List[int]` 以便调用方使用
- `/ws/system` 后端端点已存在（main.py 第325行），前端可通过 `useWebSocket({ url: '/ws/system' })` 连接

### References

- [Source: models/point.py] PointRealtime.quality（第55行）：0=好, 1=不确定, 2=坏
- [Source: services/communication_monitor.py] check_communication_status()（第9行）、mark_unreliable_points()（第36行）— 已在 main.py lifespan 中注册定时调度
- [Source: engines/alarm_engine.py] evaluate()（第149行）、load_thresholds()（第73行）、_point_device_type 映射模式 — PointRealtime 已在第16行导入
- [Source: services/simulator.py] collect_and_save()（第101行）、告警检测入口（第126-128行）、Redis 缓存 quality 硬编码为 0（第282行）
- [Source: services/websocket.py] broadcast_realtime()（第48行）、broadcast_alarm()（第56行）— 无 broadcast_system，需新增
- [Source: main.py] /ws/system 端点（第325-336行）、lifespan 定时任务模式（第174-195行，含告警引擎刷新和通信监控）
- [Source: api/v1/__init__.py] 路由注册模式
- [Source: architecture.md] 数据质量标记（第215行、第518行）、通信中断策略（第509行）
- [Source: prd.md] FR32（第761行）：通信中断时标记不可靠，避免误告警

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
