# Story 4.2: 设备详情与历史曲线

Status: done

## Story

As a 运维工程师,
I want 查看单台设备的详细信息和历史数据,
So that 我可以深入分析设备运行状况。

## Acceptance Criteria (验收标准)

1. **AC-1: 设备详情 API 增强** — 新增 `GET /api/v1/devices/{device_id}/detail` 端点，返回设备基本信息 + 关联点位实时数据 + 当前活动告警，一次请求获取设备详情页所需全部数据
2. **AC-2: 设备详情前端页面** — 新增设备详情页 `/device-manage/detail/:id`，包含三个区域：设备信息卡片（编码、名称、类型、区域、状态、厂商、型号）、关联点位实时数据表格（点位名、当前值、单位、状态）、当前活动告警列表
3. **AC-3: 点位历史曲线** — 在设备详情页中，点击某个 AI 类型点位可展开历史曲线面板，使用 ECharts 折线图展示，支持 5 种时间范围快捷选择：1小时/6小时/24小时/7天/30天
4. **AC-4: 历史曲线调用现有 API** — 历史曲线使用现有 `GET /api/v1/history/{point_id}/trend` 端点（`duration` 参数），不新增后端历史查询端点
5. **AC-5: 设备列表页入口** — 在设备管理列表页 (`device-manage/index.vue`) 的操作列新增"详情"按钮，点击跳转到设备详情页
6. **AC-6: 路由注册** — 在 `frontend/src/router/index.ts` 中注册设备详情页路由 `/device-manage/detail/:id`
7. **AC-7: 后端测试** — 测试设备详情 API 返回正确的设备信息、关联点位实时数据、活动告警

## Tasks / Subtasks (任务分解)

- [ ] Task 1: 后端 — 设备详情聚合 API (AC: #1)
  - [ ] 1.1 在 `backend/app/api/v1/device.py` 新增 `GET /{device_id}/detail` 端点（现有 `/{device_id}/points` 已在 `/{device_id}` 之后注册且正常工作，`/detail` 同理不会冲突）
  - [ ] 1.2 查询设备基本信息（Device 表）
  - [ ] 1.3 查询关联点位及其实时数据（JOIN Point + PointRealtime，WHERE Point.device_id == device_id）
  - [ ] 1.4 查询当前活动告警（JOIN Alarm + Point，WHERE Point.device_id == device_id AND Alarm.status IN ('active', 'acknowledged')）

- [ ] Task 2: 前端 — 设备详情页 (AC: #2, #3)
  - [ ] 2.1 创建 `frontend/src/views/device-manage/detail.vue`
  - [ ] 2.2 设备信息卡片区域：el-descriptions 展示设备基本信息（编码、名称、类型、区域、状态、厂商、型号、安装日期）
  - [ ] 2.3 关联点位实时数据表格：el-table 展示点位列表（点位编码、名称、类型、当前值+单位、状态标签），无数据时显示"--"
  - [ ] 2.4 当前告警列表：el-table 展示活动告警（告警编号、级别标签、消息、触发值、时间）
  - [ ] 2.5 历史曲线面板：AI 类型点位行可展开，展开后显示 ECharts 折线图 + 时间范围按钮组（1h/6h/24h/7d/30d）
  - [ ] 2.6 历史曲线调用 `getPointTrend(pointId, { duration: minutes, limit: 500 })`，参考 `history/index.vue` 的 ECharts 配置模式
  - [ ] 2.7 ECharts 实例必须在 onUnmounted 时 dispose，窗口 resize 时调用 chart.resize()（参考 history/index.vue）
  - [ ] 2.8 页面加载后自动刷新实时数据（30s 间隔 setInterval），onUnmounted 时清除定时器

- [ ] Task 3: 前端 — 设备 API 扩展 (AC: #1)
  - [ ] 3.1 在 `frontend/src/api/modules/device.ts` 新增 `getDeviceDetail(id)` 函数和对应的 TypeScript 接口

- [ ] Task 4: 前端 — 路由注册 + 列表页入口 (AC: #5, #6)
  - [ ] 4.1 在 `frontend/src/router/index.ts` 的 `device-manage` 路由后新增子路由 `device-manage/detail/:id`
  - [ ] 4.2 在 `frontend/src/views/device-manage/index.vue` 操作列新增"详情"按钮，使用 `router.push` 跳转

- [ ] Task 5: 后端测试 (AC: #7)
  - [ ] 5.1 测试设备详情 API — 返回设备信息 + 关联点位 + 实时数据
  - [ ] 5.2 测试设备详情 API — 设备不存在返回 404
  - [ ] 5.3 测试设备详情 API — 设备无关联点位时返回空列表
  - [ ] 5.4 测试设备详情 API — 返回的告警仅包含 active/acknowledged 状态

- [ ] Task 6: 前端构建验证
  - [ ] 6.1 `npm run build` 构建成功

## Dev Notes (开发指南)

### 1. 文件位置

```
backend/app/api/v1/device.py              # 修改 — 新增 detail 端点
backend/tests/test_device_detail.py        # 新建 — 测试
frontend/src/views/device-manage/detail.vue # 新建 — 设备详情页
frontend/src/views/device-manage/index.vue  # 修改 — 新增"详情"按钮
frontend/src/api/modules/device.ts          # 修改 — 新增 getDeviceDetail
frontend/src/router/index.ts               # 修改 — 新增路由
```

### 2. 设备详情聚合 API

在 `backend/app/api/v1/device.py` 中，新增端点必须放在 `/{device_id}` 之前（FastAPI 路由匹配顺序）：

```python
from ...models.alarm import Alarm

@router.get("/{device_id}/detail", summary="获取设备详情（聚合）")
async def get_device_detail(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    """
    获取设备详情：基本信息 + 关联点位实时数据 + 当前活动告警
    """
    # 1. 设备基本信息
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")

    # 2. 关联点位 + 实时数据
    from ...models.point import PointRealtime
    points_result = await db.execute(
        select(Point, PointRealtime).outerjoin(
            PointRealtime, Point.id == PointRealtime.point_id
        ).where(Point.device_id == device_id).order_by(Point.point_code)
    )
    points_data = []
    point_ids = []
    for point, realtime in points_result.all():
        point_ids.append(point.id)
        points_data.append({
            "id": point.id,
            "point_code": point.point_code,
            "point_name": point.point_name,
            "point_type": point.point_type,
            "device_type": point.device_type,
            "unit": point.unit,
            "value": realtime.value if realtime else None,
            "value_text": realtime.value_text if realtime else None,
            "status": realtime.status if realtime else "offline",
            "alarm_level": realtime.alarm_level if realtime else None,
            "quality": realtime.quality if realtime else None,
            "updated_at": realtime.updated_at.isoformat() if realtime and realtime.updated_at else None,
        })

    # 3. 当前活动告警（通过点位 ID 关联）
    alarms_data = []
    if point_ids:
        alarms_result = await db.execute(
            select(Alarm).where(
                Alarm.point_id.in_(point_ids),
                Alarm.status.in_(["active", "acknowledged"])
            ).order_by(Alarm.created_at.desc())
        )
        for alarm in alarms_result.scalars().all():
            alarms_data.append({
                "id": alarm.id,
                "alarm_no": alarm.alarm_no,
                "point_id": alarm.point_id,
                "alarm_level": alarm.alarm_level,
                "alarm_message": alarm.alarm_message,
                "trigger_value": alarm.trigger_value,
                "threshold_value": alarm.threshold_value,
                "status": alarm.status,
                "created_at": alarm.created_at.isoformat() if alarm.created_at else None,
            })

    return {
        "device": DeviceInfo.model_validate(device),
        "points": points_data,
        "alarms": alarms_data,
    }
```

注意：此端点路径 `/{device_id}/detail` 不会与 `/{device_id}` 冲突，因为 FastAPI 按注册顺序匹配，且 `detail` 不是整数。但为安全起见，建议将此端点注册在 `/{device_id}` 之前。

### 3. 前端设备详情页

参考 `power/overview.vue` 和 `history/index.vue` 的 UI 模式：

```vue
<template>
  <div class="device-detail-page">
    <!-- 返回按钮 -->
    <el-page-header @back="router.back()" :content="device?.device_name || '设备详情'" />

    <!-- 设备信息卡片 -->
    <el-card shadow="hover" style="margin-top: 16px;">
      <template #header>设备信息</template>
      <el-descriptions :column="3" border v-if="device">
        <el-descriptions-item label="设备编码">{{ device.device_code }}</el-descriptions-item>
        <el-descriptions-item label="设备名称">{{ device.device_name }}</el-descriptions-item>
        <el-descriptions-item label="设备类型">
          <el-tag size="small">{{ device.device_type }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="区域">{{ device.area_code }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="statusType" size="small">{{ statusText }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="厂商">{{ device.manufacturer || '--' }}</el-descriptions-item>
        <el-descriptions-item label="型号">{{ device.model || '--' }}</el-descriptions-item>
        <el-descriptions-item label="安装日期">{{ device.install_date || '--' }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- 关联点位实时数据 -->
    <el-card shadow="hover" style="margin-top: 16px;">
      <template #header>关联点位实时数据</template>
      <el-table :data="points" stripe border>
        <!-- 可展开行：AI 类型点位展开显示历史曲线 -->
        <el-table-column type="expand" v-if="hasAIPoints">
          <template #default="{ row }">
            <PointHistoryChart v-if="row.point_type === 'AI'" :point-id="row.id" :unit="row.unit" />
          </template>
        </el-table-column>
        <el-table-column prop="point_code" label="点位编码" width="140" />
        <el-table-column prop="point_name" label="点位名称" min-width="160" />
        <el-table-column prop="point_type" label="类型" width="80" />
        <el-table-column label="当前值" width="120">
          <template #default="{ row }">
            {{ row.value != null ? Number(row.value).toFixed(2) : '--' }} {{ row.unit || '' }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="pointStatusType(row.status)" size="small">
              {{ pointStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="updated_at" label="更新时间" width="170" />
      </el-table>
    </el-card>

    <!-- 当前告警 -->
    <el-card shadow="hover" style="margin-top: 16px;">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span>当前告警</span>
          <el-tag v-if="alarms.length > 0" type="danger" size="small">{{ alarms.length }} 条</el-tag>
        </div>
      </template>
      <el-table :data="alarms" stripe border v-if="alarms.length > 0">
        <el-table-column prop="alarm_no" label="告警编号" width="140" />
        <el-table-column prop="alarm_level" label="级别" width="90">
          <template #default="{ row }">
            <el-tag :type="alarmLevelType(row.alarm_level)" size="small">
              {{ alarmLevelText(row.alarm_level) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="alarm_message" label="告警消息" min-width="200" />
        <el-table-column prop="trigger_value" label="触发值" width="100" />
        <el-table-column prop="created_at" label="触发时间" width="170" />
      </el-table>
      <el-empty v-else description="暂无活动告警" :image-size="60" />
    </el-card>
  </div>
</template>
```

### 4. 历史曲线子组件

在设备详情页内定义或单独创建 `PointHistoryChart` 组件，使用 ECharts 展示：

```vue
<!-- 可内联在 detail.vue 中，或单独文件 -->
<template>
  <div class="point-history-chart">
    <el-radio-group v-model="selectedDuration" size="small" @change="loadTrend">
      <el-radio-button :value="60">1小时</el-radio-button>
      <el-radio-button :value="360">6小时</el-radio-button>
      <el-radio-button :value="1440">24小时</el-radio-button>
      <el-radio-button :value="10080">7天</el-radio-button>
      <el-radio-button :value="43200">30天</el-radio-button>
    </el-radio-group>
    <div ref="chartRef" style="height: 250px; margin-top: 8px;"></div>
  </div>
</template>
```

调用 `getPointTrend(pointId, { duration: selectedDuration, limit: 500 })`，参考 `history/index.vue` 的 ECharts 配置：

```typescript
import * as echarts from 'echarts'
import { getPointTrend } from '@/api/modules/history'

// ECharts 配置参考 history/index.vue 的 updateChart 函数
const option: echarts.EChartsOption = {
  tooltip: { trigger: 'axis' },
  grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
  xAxis: {
    type: 'category',
    data: trendData.map(d => d.time),
    axisLabel: { rotate: 30, formatter: (v: string) => v.substring(5, 16) }
  },
  yAxis: { type: 'value', name: unit },
  series: [{
    type: 'line',
    data: trendData.map(d => d.value),
    smooth: true,
    areaStyle: { opacity: 0.3 },
    itemStyle: { color: '#409eff' }
  }]
}
```

### 5. 路由注册

在 `frontend/src/router/index.ts` 的 `device-manage` 路由之后添加：

```typescript
{
  path: 'device-manage/detail/:id',
  name: 'DeviceDetail',
  component: () => import('@/views/device-manage/detail.vue'),
  meta: { title: '设备详情', icon: 'View', hidden: true }
}
```

`hidden: true` 使其不在侧边栏菜单中显示。

### 6. 设备列表页入口

在 `device-manage/index.vue` 的操作列中新增"详情"按钮：

```vue
<el-table-column label="操作" width="200" fixed="right">
  <template #default="{ row }">
    <el-button type="primary" link @click="handleDetail(row)">详情</el-button>
    <el-button type="primary" link @click="handleEdit(row)">编辑</el-button>
    <el-button type="danger" link @click="handleDelete(row)">删除</el-button>
  </template>
</el-table-column>
```

```typescript
import { useRouter } from 'vue-router'
const router = useRouter()

function handleDetail(row: DeviceInfo) {
  router.push(`/device-manage/detail/${row.id}`)
}
```

### 7. 关键约束

- **不新增历史查询端点**: 历史曲线复用现有 `GET /api/v1/history/{point_id}/trend` 的 `duration` 参数
- **告警通过点位关联**: Alarm 表没有 device_id 字段，需通过设备关联的 point_ids 查询告警
- **路由顺序**: `/{device_id}/detail` 不会与 `/{device_id}` 冲突（同理 `/{device_id}/points` 已正常工作），无需特殊排序
- **自动刷新**: 设备详情页每 30s 自动刷新实时数据（调用 detail API），onUnmounted 清除定时器
- **自动导入**: 项目使用 unplugin-auto-import，Vue API（ref, computed, onMounted, onUnmounted, watch）和 Vue Router API（useRouter, useRoute）无需手动 import
- **无数据显示**: 点位无实时数据时显示"--"，与 Story 4.1 保持一致
- **ECharts 模式**: 参考 `history/index.vue` 的图表初始化、resize 监听、dispose 清理模式
- **测试模式**: 使用 in-memory SQLite，mock 数据包含 Device + Point + PointRealtime + Alarm

### References

- [Source: api/v1/device.py] 现有设备 API（GET /{device_id}, GET /{device_id}/points）
- [Source: api/v1/history.py] 历史趋势 API（GET /{point_id}/trend, duration 参数）
- [Source: api/v1/alarm.py] 告警 API（GET /active, point_id 筛选）
- [Source: models/device.py] Device 模型
- [Source: models/point.py] Point, PointRealtime 模型
- [Source: models/alarm.py] Alarm 模型（point_id 外键，无 device_id）
- [Source: views/history/index.vue] ECharts 图表配置参考
- [Source: views/device-manage/index.vue] 设备管理列表页
- [Source: api/modules/device.ts] 前端设备 API
- [Source: api/modules/history.ts] 前端历史 API（getPointTrend）

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

