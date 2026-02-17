# Story 5.1: 告警阈值配置增强

Status: done

## Story

As a 系统管理员,
I want 为真实设备点位配置 4 级告警阈值,
So that 系统可以根据实际运行数据触发准确的告警。

## Acceptance Criteria (验收标准)

1. **AC-1: 4 级阈值一体化配置 API** — 新增 `PUT /api/v1/thresholds/point/{point_id}/four-level` 端点，接受 4 级阈值配置（high_high/high/low/low_low），每级包含阈值、告警消息、启用状态，以及共享的延迟触发和死区参数。后端对该点位的 4 条 AlarmThreshold 记录执行 upsert（存在则更新，不存在则创建）
2. **AC-2: 4 级阈值一体化前端表单** — 在阈值配置页面新增"4 级阈值配置"对话框，选择点位后显示 4 行表单（紧急-高高限、重要-高限、次要-低限、提示-低低限），每行包含阈值输入、告警消息、启用开关。表单校验：high_high > high > low > low_low（已启用的级别之间）
3. **AC-3: 按设备类型批量配置 API** — 新增 `POST /api/v1/thresholds/batch-by-device-type` 端点，接受 device_type + 4 级阈值模板，后端查询该设备类型下所有 AI 类型点位，为每个点位应用阈值模板。返回成功/失败数量
4. **AC-4: 按设备类型批量配置前端** — 在阈值配置页面新增"按设备类型批量配置"按钮，打开对话框：选择设备类型（下拉框）→ 显示该类型下 AI 点位数量 → 填写 4 级阈值模板 → 确认后批量应用
5. **AC-5: 配置变更实时生效** — 阈值 CRUD 操作后递增内存版本号，新增 `GET /api/v1/thresholds/version` 端点返回当前版本。数据模拟器的告警检测逻辑每周期从数据库读取最新阈值（当前已是此行为），确保配置变更无需重启即生效
6. **AC-6: 阈值列表增强** — 阈值列表 API 新增 `device_type` 筛选参数，前端筛选区新增设备类型下拉框。列表表格新增"设备类型"列
7. **AC-7: 后端测试** — 测试 4 级阈值一体化 API（创建、更新、部分启用）、按设备类型批量配置 API、版本号递增机制

## Tasks / Subtasks (任务分解)

- [ ] Task 1: 后端 — 4 级阈值一体化 API (AC: #1)
  - [ ] 1.1 在 `backend/app/schemas/threshold.py` 新增 `FourLevelThresholdItem` 和 `FourLevelThresholdCreate` Schema
  - [ ] 1.2 在 `backend/app/api/v1/threshold.py` 新增 `PUT /point/{point_id}/four-level` 端点
  - [ ] 1.3 实现 upsert 逻辑：按 point_id + threshold_type 查询，存在则更新，不存在则创建
  - [ ] 1.4 自动映射 threshold_type → alarm_level（high_high→critical, high→major, low→minor, low_low→info）
  - [ ] 1.5 自动设置 priority（high_high=4, high=3, low=2, low_low=1）

- [ ] Task 2: 后端 — 按设备类型批量配置 API (AC: #3)
  - [ ] 2.1 在 `backend/app/schemas/threshold.py` 新增 `BatchByDeviceTypeCreate` Schema
  - [ ] 2.2 在 `backend/app/api/v1/threshold.py` 新增 `POST /batch-by-device-type` 端点
  - [ ] 2.3 查询 Point 表中 device_type 匹配且 point_type == 'AI' 的所有点位
  - [ ] 2.4 对每个点位复用 4 级阈值 upsert 逻辑
  - [ ] 2.5 返回 `{ success_count, skip_count, error_count, errors, affected_point_ids }`

- [ ] Task 3: 后端 — 阈值版本号与列表增强 (AC: #5, #6)
  - [ ] 3.1 在 `backend/app/api/v1/threshold.py` 模块级别添加 `_threshold_version` 计数器
  - [ ] 3.2 在所有阈值写操作（create/update/delete/batch/four-level）后递增版本号
  - [ ] 3.3 新增 `GET /version` 端点返回 `{ version, updated_at }`
  - [ ] 3.4 阈值列表 GET 端点新增 `device_type` 可选查询参数，通过 JOIN Point 表筛选
  - [ ] 3.5 ThresholdInfo 响应新增 `device_type` 字段

- [ ] Task 4: 前端 — 4 级阈值配置对话框 (AC: #2)
  - [ ] 4.1 在 `frontend/src/api/modules/threshold.ts` 新增 `setFourLevelThresholds(pointId, data)` 函数和对应 TypeScript 接口
  - [ ] 4.2 在 `frontend/src/views/settings/index.vue` 新增"4 级阈值配置"按钮（在"新增阈值"按钮旁）
  - [ ] 4.3 新增 4 级阈值配置对话框组件，包含：点位选择器（filterable el-select）、4 行阈值表单（el-form 内嵌 el-table 或 4 组 el-form-item）
  - [ ] 4.4 每行显示：级别标签（紧急/重要/次要/提示）、阈值类型标签（高高限/高限/低限/低低限）、阈值输入（el-input-number）、告警消息（el-input）、启用开关（el-switch）
  - [ ] 4.5 共享参数区：延迟触发（el-input-number, 秒）、死区（el-input-number）
  - [ ] 4.6 表单校验：已启用级别的阈值必须满足 high_high > high（如果都启用）、low > low_low（如果都启用）
  - [ ] 4.7 选择点位后自动加载该点位现有阈值配置（调用 `getPointThresholds`），回填表单
  - [ ] 4.8 提交后调用 `setFourLevelThresholds`，成功后刷新阈值列表

- [ ] Task 5: 前端 — 按设备类型批量配置 (AC: #4)
  - [ ] 5.1 在 `frontend/src/api/modules/threshold.ts` 新增 `batchSetByDeviceType(data)` 函数和接口
  - [ ] 5.2 在 `frontend/src/api/modules/point.ts` 新增 `getPointCountByDeviceType(deviceType)` 函数（或复用现有 API 带 device_type 筛选）
  - [ ] 5.3 在 `frontend/src/views/settings/index.vue` 新增"按设备类型批量配置"按钮
  - [ ] 5.4 新增批量配置对话框：设备类型下拉框（el-select，选项为 TH/UPS/PDU/AC 等）、选择后显示"该类型下共 N 个 AI 点位"提示
  - [ ] 5.5 复用 4 级阈值表单（与 Task 4 相同的 4 行表单结构）
  - [ ] 5.6 提交前二次确认（el-message-box confirm："确定为 N 个点位批量设置阈值？"）
  - [ ] 5.7 提交后显示结果（成功 N 个，失败 N 个）

- [ ] Task 6: 前端 — 阈值列表增强 (AC: #6)
  - [ ] 6.1 在筛选区新增"设备类型"下拉框（el-select，选项同 Task 5）
  - [ ] 6.2 `loadThresholds` 函数传递 `device_type` 参数
  - [ ] 6.3 表格新增"设备类型"列（在"点位名称"列之后）

- [ ] Task 7: 后端测试 (AC: #7)
  - [ ] 7.1 测试 4 级阈值 API — 首次创建 4 条记录
  - [ ] 7.2 测试 4 级阈值 API — 再次调用更新已有记录（upsert）
  - [ ] 7.3 测试 4 级阈值 API — 部分级别启用、部分禁用
  - [ ] 7.4 测试 4 级阈值 API — 点位不存在返回 404
  - [ ] 7.5 测试按设备类型批量 API — 正常批量创建
  - [ ] 7.6 测试按设备类型批量 API — 无匹配点位返回空结果
  - [ ] 7.7 测试版本号 — CRUD 操作后版本递增

- [ ] Task 8: 前端构建验证
  - [ ] 8.1 `npm run build` 构建成功

## Dev Notes (开发指南)

### 1. 文件位置

```
backend/app/api/v1/threshold.py              # 修改 — 新增 3 个端点
backend/app/schemas/threshold.py             # 修改 — 新增 3 个 Schema
backend/tests/test_threshold_enhancement.py  # 新建 — 测试
frontend/src/api/modules/threshold.ts        # 修改 — 新增 2 个 API 函数
frontend/src/views/settings/index.vue        # 修改 — 新增按钮、对话框、筛选
```

### 2. 4 级阈值一体化 API

在 `backend/app/api/v1/threshold.py` 中新增端点：

```python
from ...schemas.threshold import FourLevelThresholdCreate, FourLevelThresholdItem

@router.put("/point/{point_id}/four-level", summary="4级阈值一体化配置")
async def set_four_level_thresholds(
    point_id: int,
    data: FourLevelThresholdCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    为指定点位一次性配置 4 级告警阈值（高高限/高限/低限/低低限）。
    已存在的阈值更新，不存在的创建。
    """
    # 1. 检查点位存在
    point_result = await db.execute(select(Point).where(Point.id == point_id))
    point = point_result.scalar_one_or_none()
    if not point:
        raise HTTPException(status_code=404, detail="点位不存在")

    # 2. 定义映射
    level_mapping = {
        "high_high": {"alarm_level": "critical", "priority": 4},
        "high": {"alarm_level": "major", "priority": 3},
        "low": {"alarm_level": "minor", "priority": 2},
        "low_low": {"alarm_level": "info", "priority": 1},
    }

    results = []
    for threshold_type, item in [
        ("high_high", data.high_high),
        ("high", data.high),
        ("low", data.low),
        ("low_low", data.low_low),
    ]:
        if item is None:
            continue

        mapping = level_mapping[threshold_type]

        # upsert
        existing = await db.execute(
            select(AlarmThreshold).where(
                AlarmThreshold.point_id == point_id,
                AlarmThreshold.threshold_type == threshold_type
            )
        )
        threshold = existing.scalar_one_or_none()

        if threshold:
            threshold.threshold_value = item.value
            threshold.alarm_message = item.message or f"{point.point_name} {threshold_type} 告警"
            threshold.is_enabled = item.enabled if item.enabled is not None else True
            threshold.alarm_level = mapping["alarm_level"]
            threshold.priority = mapping["priority"]
            threshold.delay_seconds = data.delay_seconds
            threshold.dead_band = data.dead_band
            threshold.updated_at = datetime.now()
        else:
            threshold = AlarmThreshold(
                point_id=point_id,
                threshold_type=threshold_type,
                threshold_value=item.value,
                alarm_level=mapping["alarm_level"],
                alarm_message=item.message or f"{point.point_name} {threshold_type} 告警",
                delay_seconds=data.delay_seconds,
                dead_band=data.dead_band,
                is_enabled=item.enabled if item.enabled is not None else True,
                priority=mapping["priority"],
            )
            db.add(threshold)

        results.append(threshold_type)

    await db.commit()
    _increment_version()

    # 返回该点位所有阈值
    all_thresholds = await db.execute(
        select(AlarmThreshold).where(AlarmThreshold.point_id == point_id)
            .order_by(AlarmThreshold.priority.desc())
    )
    return [ThresholdInfo.model_validate(t) for t in all_thresholds.scalars().all()]
```

### 3. Schema 定义

在 `backend/app/schemas/threshold.py` 新增：

```python
class FourLevelThresholdItem(BaseModel):
    """单级阈值配置"""
    value: Optional[float] = None
    message: Optional[str] = None
    enabled: Optional[bool] = True

class FourLevelThresholdCreate(BaseModel):
    """4级阈值一体化配置"""
    high_high: Optional[FourLevelThresholdItem] = None  # 紧急 - 高高限
    high: Optional[FourLevelThresholdItem] = None       # 重要 - 高限
    low: Optional[FourLevelThresholdItem] = None        # 次要 - 低限
    low_low: Optional[FourLevelThresholdItem] = None    # 提示 - 低低限
    delay_seconds: int = 0
    dead_band: float = 0

class BatchByDeviceTypeCreate(BaseModel):
    """按设备类型批量配置阈值"""
    device_type: str  # TH/UPS/PDU/AC/DOOR/SMOKE/WATER/IR/FAN/LIGHT
    thresholds: FourLevelThresholdCreate
```

### 4. 按设备类型批量配置 API

```python
@router.post("/batch-by-device-type", summary="按设备类型批量配置阈值")
async def batch_set_by_device_type(
    data: BatchByDeviceTypeCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator)
):
    """
    为指定设备类型下所有 AI 点位批量配置 4 级阈值。
    """
    # 查询该设备类型下所有 AI 点位
    points_result = await db.execute(
        select(Point).where(
            Point.device_type == data.device_type,
            Point.point_type == "AI"
        )
    )
    points = points_result.scalars().all()

    if not points:
        return {
            "success_count": 0,
            "skip_count": 0,
            "error_count": 0,
            "errors": [],
            "message": f"设备类型 {data.device_type} 下没有 AI 类型点位"
        }

    success_count = 0
    error_list = []

    for point in points:
        try:
            # 复用 4 级阈值 upsert 逻辑（提取为内部函数）
            await _upsert_four_level(db, point, data.thresholds)
            success_count += 1
        except Exception as e:
            error_list.append(f"点位 {point.point_code}: {str(e)}")

    await db.commit()
    _increment_version()

    return {
        "success_count": success_count,
        "error_count": len(error_list),
        "errors": error_list,
        "total_points": len(points)
    }
```

### 5. 版本号机制

在 `backend/app/api/v1/threshold.py` 模块顶部：

```python
from datetime import datetime
import threading

_threshold_version = 0
_threshold_version_time = datetime.now()
_version_lock = threading.Lock()

def _increment_version():
    global _threshold_version, _threshold_version_time
    with _version_lock:
        _threshold_version += 1
        _threshold_version_time = datetime.now()

@router.get("/version", summary="获取阈值配置版本号")
async def get_threshold_version():
    """返回阈值配置版本号，用于告警引擎缓存失效判断"""
    return {
        "version": _threshold_version,
        "updated_at": _threshold_version_time.isoformat()
    }
```

在现有的 `create_threshold`、`update_threshold`、`delete_threshold`、`batch_create_thresholds`、`copy_thresholds` 函数的 `await db.commit()` 之后添加 `_increment_version()` 调用。

### 6. 前端 4 级阈值对话框

在 `frontend/src/views/settings/index.vue` 中新增对话框：

```vue
<!-- 4级阈值配置对话框 -->
<el-dialog v-model="fourLevelDialogVisible" title="4级阈值配置" width="700px">
  <el-form :model="fourLevelForm" label-width="100px">
    <el-form-item label="选择点位" required>
      <el-select v-model="fourLevelForm.point_id" filterable placeholder="请选择点位"
        style="width: 100%;" @change="loadExistingThresholds">
        <el-option v-for="p in aiPointList" :key="p.id"
          :label="`${p.point_code} - ${p.point_name}`" :value="p.id" />
      </el-select>
    </el-form-item>

    <el-divider content-position="left">阈值配置</el-divider>

    <el-table :data="fourLevelRows" border style="margin-bottom: 16px;">
      <el-table-column prop="levelLabel" label="告警级别" width="90">
        <template #default="{ row }">
          <el-tag :type="alarmLevelType[row.alarmLevel]" size="small">{{ row.levelLabel }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="typeLabel" label="阈值类型" width="90" />
      <el-table-column label="阈值" width="150">
        <template #default="{ row }">
          <el-input-number v-model="row.value" :precision="2" size="small" style="width: 120px;" />
        </template>
      </el-table-column>
      <el-table-column label="告警消息" min-width="180">
        <template #default="{ row }">
          <el-input v-model="row.message" size="small" placeholder="自动生成" />
        </template>
      </el-table-column>
      <el-table-column label="启用" width="70">
        <template #default="{ row }">
          <el-switch v-model="row.enabled" size="small" />
        </template>
      </el-table-column>
    </el-table>

    <el-row :gutter="20">
      <el-col :span="12">
        <el-form-item label="延迟触发">
          <el-input-number v-model="fourLevelForm.delay_seconds" :min="0" :max="300" />
          <span style="margin-left: 8px; color: var(--text-secondary);">秒</span>
        </el-form-item>
      </el-col>
      <el-col :span="12">
        <el-form-item label="死区(回差)">
          <el-input-number v-model="fourLevelForm.dead_band" :min="0" :precision="2" />
        </el-form-item>
      </el-col>
    </el-row>
  </el-form>
  <template #footer>
    <el-button @click="fourLevelDialogVisible = false">取消</el-button>
    <el-button type="primary" @click="submitFourLevel">确定</el-button>
  </template>
</el-dialog>
```

其中 `fourLevelRows` 为响应式数组：

```typescript
const fourLevelRows = ref([
  { key: 'high_high', levelLabel: '紧急', typeLabel: '高高限', alarmLevel: 'critical', value: null, message: '', enabled: true },
  { key: 'high', levelLabel: '重要', typeLabel: '高限', alarmLevel: 'major', value: null, message: '', enabled: true },
  { key: 'low', levelLabel: '次要', typeLabel: '低限', alarmLevel: 'minor', value: null, message: '', enabled: true },
  { key: 'low_low', levelLabel: '提示', typeLabel: '低低限', alarmLevel: 'info', value: null, message: '', enabled: true },
])
```

### 7. 前端 API 扩展

在 `frontend/src/api/modules/threshold.ts` 新增：

```typescript
export interface FourLevelThresholdItem {
  value: number | null
  message?: string
  enabled?: boolean
}

export interface FourLevelThresholdParams {
  high_high?: FourLevelThresholdItem
  high?: FourLevelThresholdItem
  low?: FourLevelThresholdItem
  low_low?: FourLevelThresholdItem
  delay_seconds?: number
  dead_band?: number
}

export interface BatchByDeviceTypeParams {
  device_type: string
  thresholds: FourLevelThresholdParams
}

/**
 * 4级阈值一体化配置
 */
export function setFourLevelThresholds(
  pointId: number,
  data: FourLevelThresholdParams
): Promise<ThresholdInfo[]> {
  return request.put(`/v1/thresholds/point/${pointId}/four-level`, data)
}

/**
 * 按设备类型批量配置阈值
 */
export function batchSetByDeviceType(data: BatchByDeviceTypeParams): Promise<{
  success_count: number
  error_count: number
  errors: string[]
  total_points: number
}> {
  return request.post('/v1/thresholds/batch-by-device-type', data)
}

/**
 * 获取阈值配置版本号
 */
export function getThresholdVersion(): Promise<{
  version: number
  updated_at: string
}> {
  return request.get('/v1/thresholds/version')
}
```

### 8. 设备类型常量

前端设备类型选项（复用现有 Point 模型的 device_type 枚举）：

```typescript
const deviceTypeOptions = [
  { label: '温湿度传感器', value: 'TH' },
  { label: 'UPS', value: 'UPS' },
  { label: 'PDU', value: 'PDU' },
  { label: '精密空调', value: 'AC' },
  { label: '门禁', value: 'DOOR' },
  { label: '烟感', value: 'SMOKE' },
  { label: '漏水', value: 'WATER' },
  { label: '红外', value: 'IR' },
  { label: '风机', value: 'FAN' },
  { label: '照明', value: 'LIGHT' },
]
```

### 9. 阈值列表增强

在 `backend/app/api/v1/threshold.py` 的 `get_thresholds` 端点新增 `device_type` 参数：

```python
@router.get("", response_model=PageResponse[ThresholdInfo], summary="获取阈值配置列表")
async def get_thresholds(
    # ... 现有参数 ...
    device_type: Optional[str] = Query(None, description="设备类型"),
    # ...
):
    query = select(AlarmThreshold)

    if device_type:
        query = query.join(Point, AlarmThreshold.point_id == Point.id).where(
            Point.device_type == device_type
        )
    # ... 其余逻辑不变 ...
```

### 10. 关键约束

- **不新增数据库表**: 复用现有 AlarmThreshold 表，通过 point_id + threshold_type 唯一标识一条阈值记录
- **不破坏现有 API**: 所有新端点为新增路径，现有 CRUD 端点保持不变
- **阈值校验**: 后端不强制校验 high_high > high > low > low_low（允许灵活配置），前端做友好提示
- **AI 点位过滤**: 批量配置仅针对 AI（模拟量输入）类型点位，DI（开关量）点位使用状态变化触发，不适用阈值
- **版本号**: 使用模块级变量 + threading.Lock，进程重启后重置为 0。告警引擎通过比较版本号决定是否重新加载阈值缓存
- **自动导入**: 前端项目使用 unplugin-auto-import，Vue API（ref, reactive, computed, onMounted）无需手动 import
- **测试模式**: 使用 in-memory SQLite，mock 数据包含 Point（AI 类型）+ AlarmThreshold

### References

- [Source: api/v1/threshold.py] 现有阈值 CRUD API（GET/POST/PUT/DELETE + batch + copy）
- [Source: api/v1/alarm.py] 告警管理 API（告警列表、确认、解决、规则、屏蔽）
- [Source: models/alarm.py] AlarmThreshold 模型（point_id, threshold_type, threshold_value, alarm_level）
- [Source: models/point.py] Point 模型（device_type, point_type, area_code）
- [Source: schemas/threshold.py] 阈值 Schema（ThresholdCreate, ThresholdUpdate, ThresholdInfo, ThresholdBatchCreate）
- [Source: views/settings/index.vue] 阈值配置前端页面（Tab 布局、el-table、对话框 CRUD）
- [Source: api/modules/threshold.ts] 前端阈值 API（getThresholdList, createThreshold, batchCreateThresholds）
- [Source: api/modules/alarm.ts] 前端告警 API（AlarmInfo, AlarmRuleInfo 类型定义）

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

