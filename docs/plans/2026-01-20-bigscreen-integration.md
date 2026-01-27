# 数字孪生大屏系统集成计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将数字孪生大屏完整集成到算力中心智能监控系统中，实现真实数据对接、导航入口、权限控制和布局配置。

**Architecture:**
- 前端: 使用已有的 API 模块替换 mock 数据，添加侧边栏/仪表盘入口
- 后端: 新增布局配置 API，复用现有 realtime/alarm/energy API
- 数据流: useBigscreenData → 现有 API → 后端服务 → 数据库

**Tech Stack:** Vue 3, Three.js, FastAPI, SQLAlchemy, Pinia

---

## Phase 1: API 数据对接

### Task 1.1: 更新 useBigscreenData 接入真实 API

**Files:**
- Modify: `frontend/src/composables/bigscreen/useBigscreenData.ts`

**Step 1: 添加 API 导入**

在文件顶部添加:
```typescript
import { getRealtimeSummary, getAllRealtimeData } from '@/api/modules/realtime'
import { getActiveAlarms } from '@/api/modules/alarm'
import { getEnergyDashboard } from '@/api/modules/energy'
```

**Step 2: 实现 fetchEnvironmentData**

替换 fetchEnvironmentData 函数:
```typescript
async function fetchEnvironmentData() {
  try {
    const summary = await getRealtimeSummary()

    // 从实时数据中提取温湿度
    const realtimeData = await getAllRealtimeData()
    const tempPoints = realtimeData.filter(p => p.point_code.includes('_TH_') && p.point_code.includes('_001'))
    const humidPoints = realtimeData.filter(p => p.point_code.includes('_TH_') && p.point_code.includes('_002'))

    const temps = tempPoints.map(p => p.value).filter(v => v > 0)
    const humids = humidPoints.map(p => p.value).filter(v => v > 0)

    const data = {
      temperature: {
        max: temps.length > 0 ? Math.max(...temps) : 30,
        avg: temps.length > 0 ? temps.reduce((a, b) => a + b, 0) / temps.length : 24,
        min: temps.length > 0 ? Math.min(...temps) : 20
      },
      humidity: {
        max: humids.length > 0 ? Math.max(...humids) : 60,
        avg: humids.length > 0 ? humids.reduce((a, b) => a + b, 0) / humids.length : 50,
        min: humids.length > 0 ? Math.min(...humids) : 40
      }
    }

    store.updateEnvironment(data)
  } catch (e) {
    console.error('Failed to fetch environment data:', e)
  }
}
```

**Step 3: 实现 fetchEnergyData**

替换 fetchEnergyData 函数:
```typescript
async function fetchEnergyData() {
  try {
    const dashboard = await getEnergyDashboard()

    const data = {
      totalPower: dashboard.realtime?.total_power || 0,
      itPower: dashboard.realtime?.it_power || 0,
      coolingPower: dashboard.realtime?.cooling_power || 0,
      pue: dashboard.efficiency?.pue || 1.5,
      todayEnergy: dashboard.cost?.today_energy || 0,
      todayCost: dashboard.cost?.today_cost || 0
    }

    store.updateEnergy(data)
  } catch (e) {
    console.error('Failed to fetch energy data:', e)
  }
}
```

**Step 4: 实现 fetchAlarmData**

替换 fetchAlarmData 函数:
```typescript
async function fetchAlarmData() {
  try {
    const activeAlarms = await getActiveAlarms()

    const alarms: BigscreenAlarm[] = activeAlarms.map(alarm => ({
      id: alarm.id,
      deviceId: alarm.point_code.split('_').slice(0, 2).join('-'),
      deviceName: alarm.point_name,
      level: alarm.alarm_level as 'critical' | 'major' | 'minor' | 'warning' | 'info',
      message: alarm.alarm_message,
      value: alarm.trigger_value,
      threshold: alarm.threshold_value,
      time: new Date(alarm.created_at).getTime(),
      createdAt: alarm.created_at
    }))

    store.setAlarms(alarms)
  } catch (e) {
    console.error('Failed to fetch alarm data:', e)
  }
}
```

**Step 5: 实现 fetchDeviceData**

替换 fetchDeviceData 函数:
```typescript
async function fetchDeviceData() {
  try {
    const realtimeData = await getAllRealtimeData()

    if (store.layout) {
      for (const module of store.layout.modules) {
        for (const cabinet of module.cabinets) {
          // 根据机柜ID查找关联的点位数据
          const relatedPoints = realtimeData.filter(p =>
            p.point_code.startsWith(cabinet.id.replace('-', '_'))
          )

          const tempPoint = relatedPoints.find(p => p.point_code.includes('_TH_') && p.point_code.endsWith('_001'))
          const humidPoint = relatedPoints.find(p => p.point_code.includes('_TH_') && p.point_code.endsWith('_002'))
          const powerPoint = relatedPoints.find(p => p.point_code.includes('_PDU_'))

          const hasAlarm = relatedPoints.some(p => p.status === 'alarm')
          const isOffline = relatedPoints.every(p => p.status === 'offline')

          const deviceData: DeviceRealtimeData = {
            id: cabinet.id,
            status: isOffline ? 'offline' : (hasAlarm ? 'alarm' : 'normal'),
            temperature: tempPoint?.value || 24,
            humidity: humidPoint?.value || 50,
            power: powerPoint?.value || 5,
            load: Math.min(100, Math.max(0, ((powerPoint?.value || 5) / 10) * 100))
          }
          store.updateDeviceData(cabinet.id, deviceData)
        }
      }
    }
  } catch (e) {
    console.error('Failed to fetch device data:', e)
  }
}
```

**Step 6: 验证构建**

Run:
```bash
cd D:\mytest1\frontend && npm run build
```

Expected: 构建成功，无 TypeScript 错误

---

### Task 1.2: 添加大屏布局 API

**Files:**
- Modify: `frontend/src/api/modules/index.ts`
- Create: `frontend/src/api/modules/bigscreen.ts`

**Step 1: 创建 bigscreen API 模块**

```typescript
// frontend/src/api/modules/bigscreen.ts
import request from '@/utils/request'
import type { DataCenterLayout } from '@/types/bigscreen'

/**
 * 获取机房布局配置
 */
export function getDataCenterLayout(): Promise<DataCenterLayout> {
  return request.get('/v1/bigscreen/layout')
}

/**
 * 保存机房布局配置 (管理员)
 */
export function saveDataCenterLayout(layout: DataCenterLayout): Promise<void> {
  return request.post('/v1/bigscreen/layout', layout)
}

/**
 * 获取默认布局模板
 */
export function getDefaultLayout(): Promise<DataCenterLayout> {
  // 返回默认布局配置
  return Promise.resolve({
    name: '默认机房布局',
    dimensions: { width: 40, length: 30, height: 4 },
    modules: [
      {
        id: 'module-A',
        name: 'A区机柜',
        position: { x: -10, z: 0 },
        rotation: 0,
        cabinets: [
          { id: 'A-01', name: 'A区1号柜', position: { x: 0, y: 0, z: 0 }, size: { width: 0.6, height: 2, depth: 1 }, status: 'normal' },
          { id: 'A-02', name: 'A区2号柜', position: { x: 1.2, y: 0, z: 0 }, size: { width: 0.6, height: 2, depth: 1 }, status: 'normal' },
          { id: 'A-03', name: 'A区3号柜', position: { x: 2.4, y: 0, z: 0 }, size: { width: 0.6, height: 2, depth: 1 }, status: 'normal' },
          { id: 'A-04', name: 'A区4号柜', position: { x: 3.6, y: 0, z: 0 }, size: { width: 0.6, height: 2, depth: 1 }, status: 'normal' }
        ],
        coolingUnits: [
          { id: 'AC-A-01', position: { x: -2, z: 0 } }
        ]
      },
      {
        id: 'module-B',
        name: 'B区机柜',
        position: { x: 10, z: 0 },
        rotation: 0,
        cabinets: [
          { id: 'B-01', name: 'B区1号柜', position: { x: 0, y: 0, z: 0 }, size: { width: 0.6, height: 2, depth: 1 }, status: 'normal' },
          { id: 'B-02', name: 'B区2号柜', position: { x: 1.2, y: 0, z: 0 }, size: { width: 0.6, height: 2, depth: 1 }, status: 'normal' },
          { id: 'B-03', name: 'B区3号柜', position: { x: 2.4, y: 0, z: 0 }, size: { width: 0.6, height: 2, depth: 1 }, status: 'normal' },
          { id: 'B-04', name: 'B区4号柜', position: { x: 3.6, y: 0, z: 0 }, size: { width: 0.6, height: 2, depth: 1 }, status: 'normal' }
        ],
        coolingUnits: [
          { id: 'AC-B-01', position: { x: 6, z: 0 } }
        ]
      }
    ],
    infrastructure: {
      upsRoom: { position: { x: 0, z: -12 }, size: { width: 6, length: 4 } },
      powerRoom: { position: { x: 0, z: 12 }, size: { width: 6, length: 4 } }
    }
  })
}
```

**Step 2: 更新 API 导出**

在 `frontend/src/api/modules/index.ts` 添加:
```typescript
export * from './bigscreen'
```

**Step 3: 验证构建**

Run:
```bash
cd D:\mytest1\frontend && npm run build
```

Expected: 构建成功

---

## Phase 2: 导航入口集成

### Task 2.1: 添加侧边栏大屏入口

**Files:**
- Modify: `frontend/src/layouts/MainLayout.vue`

**Step 1: 添加图标导入**

在 icons 导入行添加 `FullScreen`:
```typescript
import {
  Monitor, Cpu, Bell, TrendCharts, Setting, Document,
  Expand, Fold, UserFilled, ArrowDown,
  Lightning, Odometer, DataLine, Finished, Share, DataAnalysis,
  FullScreen  // 添加
} from '@element-plus/icons-vue'
```

**Step 2: 添加大屏菜单项**

在 `</el-menu>` 标签前添加:
```vue
<el-menu-item index="/bigscreen" @click="openBigscreen">
  <el-icon><FullScreen /></el-icon>
  <template #title>数字孪生大屏</template>
</el-menu-item>
```

**Step 3: 添加 openBigscreen 方法**

在 script 中添加:
```typescript
function openBigscreen() {
  window.open('/bigscreen', '_blank')
}
```

**Step 4: 验证构建**

Run:
```bash
cd D:\mytest1\frontend && npm run build
```

Expected: 构建成功

---

### Task 2.2: 添加仪表盘快捷入口

**Files:**
- Modify: `frontend/src/views/dashboard/index.vue`

**Step 1: 在统计卡片区域添加大屏入口按钮**

在第一个 `<el-row>` 后添加快捷入口:
```vue
<!-- 快捷操作栏 -->
<el-row class="quick-actions">
  <el-col :span="24">
    <el-card shadow="hover">
      <div class="actions-content">
        <span class="actions-title">快捷操作</span>
        <el-button type="primary" :icon="FullScreen" @click="openBigscreen">
          打开数字孪生大屏
        </el-button>
        <el-button :icon="Refresh" @click="refreshData">
          刷新数据
        </el-button>
      </div>
    </el-card>
  </el-col>
</el-row>
```

**Step 2: 添加图标导入**

添加 `FullScreen, Refresh` 到 icons 导入

**Step 3: 添加方法**

```typescript
function openBigscreen() {
  window.open('/bigscreen', '_blank')
}
```

**Step 4: 添加样式**

```scss
.quick-actions {
  margin-bottom: 20px;

  .actions-content {
    display: flex;
    align-items: center;
    gap: 16px;

    .actions-title {
      font-weight: 600;
      color: #333;
      margin-right: 8px;
    }
  }
}
```

**Step 5: 验证构建**

Run:
```bash
cd D:\mytest1\frontend && npm run build
```

Expected: 构建成功

---

## Phase 3: 大屏页面优化

### Task 3.1: 加载布局配置

**Files:**
- Modify: `frontend/src/views/bigscreen/index.vue`

**Step 1: 导入布局 API**

```typescript
import { getDefaultLayout } from '@/api/modules/bigscreen'
```

**Step 2: 在 onSceneReady 中加载布局**

在 `onSceneReady` 函数开头添加:
```typescript
// 加载布局配置
const layout = await getDefaultLayout()
store.setLayout(layout)
```

**Step 3: 移除硬编码的模拟数据初始化**

移除 `onSceneReady` 中的:
- `store.updateEnvironment({...})`
- `store.updateEnergy({...})`
- `store.setAlarms([...])`

这些数据现在由 `useBigscreenData` 自动获取。

**Step 4: 验证构建**

Run:
```bash
cd D:\mytest1\frontend && npm run build
```

Expected: 构建成功

---

### Task 3.2: 添加返回主系统按钮

**Files:**
- Modify: `frontend/src/views/bigscreen/index.vue`

**Step 1: 在顶部栏添加返回按钮**

在 `.top-bar` 的 `.time` 前添加:
```vue
<div class="back-btn" @click="goBack">
  <el-icon><Back /></el-icon>
</div>
```

**Step 2: 添加图标导入**

```typescript
import { Back } from '@element-plus/icons-vue'
```

**Step 3: 添加方法**

```typescript
function goBack() {
  if (window.opener) {
    window.close()
  } else {
    window.location.href = '/dashboard'
  }
}
```

**Step 4: 添加样式**

```scss
.back-btn {
  cursor: pointer;
  padding: 8px;
  border-radius: 4px;
  margin-right: 12px;

  &:hover {
    background: rgba(255, 255, 255, 0.1);
  }
}
```

**Step 5: 验证构建**

Run:
```bash
cd D:\mytest1\frontend && npm run build
```

Expected: 构建成功

---

## Phase 4: 后端 API 支持 (可选)

### Task 4.1: 创建布局配置 API

**Files:**
- Create: `backend/app/api/v1/bigscreen.py`
- Modify: `backend/app/api/v1/__init__.py`
- Modify: `backend/app/main.py`

**Step 1: 创建 bigscreen API**

```python
# backend/app/api/v1/bigscreen.py
from fastapi import APIRouter, Depends
from typing import Dict, Any, List
from pydantic import BaseModel

router = APIRouter(prefix="/bigscreen", tags=["大屏"])

class CabinetConfig(BaseModel):
    id: str
    name: str
    position: Dict[str, float]
    size: Dict[str, float]
    status: str = "normal"

class ModuleConfig(BaseModel):
    id: str
    name: str
    position: Dict[str, float]
    rotation: float = 0
    cabinets: List[CabinetConfig]
    coolingUnits: List[Dict[str, Any]] = []

class DataCenterLayout(BaseModel):
    name: str
    dimensions: Dict[str, float]
    modules: List[ModuleConfig]
    infrastructure: Dict[str, Any] = {}

# 默认布局配置 (可后续存入数据库)
DEFAULT_LAYOUT = DataCenterLayout(
    name="默认机房布局",
    dimensions={"width": 40, "length": 30, "height": 4},
    modules=[
        ModuleConfig(
            id="module-A",
            name="A区机柜",
            position={"x": -10, "z": 0},
            rotation=0,
            cabinets=[
                CabinetConfig(id="A-01", name="A区1号柜", position={"x": 0, "y": 0, "z": 0}, size={"width": 0.6, "height": 2, "depth": 1}),
                CabinetConfig(id="A-02", name="A区2号柜", position={"x": 1.2, "y": 0, "z": 0}, size={"width": 0.6, "height": 2, "depth": 1}),
                CabinetConfig(id="A-03", name="A区3号柜", position={"x": 2.4, "y": 0, "z": 0}, size={"width": 0.6, "height": 2, "depth": 1}),
                CabinetConfig(id="A-04", name="A区4号柜", position={"x": 3.6, "y": 0, "z": 0}, size={"width": 0.6, "height": 2, "depth": 1}),
            ],
            coolingUnits=[{"id": "AC-A-01", "position": {"x": -2, "z": 0}}]
        ),
        ModuleConfig(
            id="module-B",
            name="B区机柜",
            position={"x": 10, "z": 0},
            rotation=0,
            cabinets=[
                CabinetConfig(id="B-01", name="B区1号柜", position={"x": 0, "y": 0, "z": 0}, size={"width": 0.6, "height": 2, "depth": 1}),
                CabinetConfig(id="B-02", name="B区2号柜", position={"x": 1.2, "y": 0, "z": 0}, size={"width": 0.6, "height": 2, "depth": 1}),
                CabinetConfig(id="B-03", name="B区3号柜", position={"x": 2.4, "y": 0, "z": 0}, size={"width": 0.6, "height": 2, "depth": 1}),
                CabinetConfig(id="B-04", name="B区4号柜", position={"x": 3.6, "y": 0, "z": 0}, size={"width": 0.6, "height": 2, "depth": 1}),
            ],
            coolingUnits=[{"id": "AC-B-01", "position": {"x": 6, "z": 0}}]
        )
    ],
    infrastructure={
        "upsRoom": {"position": {"x": 0, "z": -12}, "size": {"width": 6, "length": 4}},
        "powerRoom": {"position": {"x": 0, "z": 12}, "size": {"width": 6, "length": 4}}
    }
)

@router.get("/layout", response_model=DataCenterLayout)
async def get_layout():
    """获取机房布局配置"""
    return DEFAULT_LAYOUT

@router.post("/layout")
async def save_layout(layout: DataCenterLayout):
    """保存机房布局配置 (管理员)"""
    # TODO: 存入数据库
    global DEFAULT_LAYOUT
    DEFAULT_LAYOUT = layout
    return {"message": "布局配置已保存"}
```

**Step 2: 注册路由**

在 `backend/app/main.py` 中添加:
```python
from app.api.v1 import bigscreen
app.include_router(bigscreen.router, prefix="/api/v1")
```

**Step 3: 验证后端**

Run:
```bash
cd D:\mytest1 && python -m uvicorn backend.app.main:app --reload --port 8000
```

测试:
```bash
curl http://localhost:8000/api/v1/bigscreen/layout
```

Expected: 返回布局 JSON

---

## Phase 5: 最终验证

### Task 5.1: 完整功能测试

**Step 1: 启动后端服务**

Run:
```bash
cd D:\mytest1 && python -m uvicorn backend.app.main:app --reload --port 8000
```

**Step 2: 启动前端服务**

Run:
```bash
cd D:\mytest1\frontend && npm run dev
```

**Step 3: 验证功能清单**

| 功能 | 验证方式 | 预期结果 |
|------|----------|----------|
| 侧边栏入口 | 点击"数字孪生大屏"菜单 | 新窗口打开大屏 |
| 仪表盘入口 | 点击"打开数字孪生大屏"按钮 | 新窗口打开大屏 |
| 大屏加载 | 访问 /bigscreen | 3D场景正常渲染 |
| 环境数据 | 查看左侧面板 | 显示真实温湿度数据 |
| 能耗数据 | 查看右侧面板 | 显示真实PUE/功率数据 |
| 告警数据 | 查看告警气泡 | 显示真实告警信息 |
| 返回按钮 | 点击左上角返回 | 关闭窗口或返回仪表盘 |
| 模式切换 | 切换指挥/运维/展示模式 | 界面相应变化 |
| 自动巡航 | 展示模式下点击巡航 | 相机自动移动 |

**Step 4: 构建生产版本**

Run:
```bash
cd D:\mytest1\frontend && npm run build
```

Expected: 构建成功，无错误

---

## 验证清单

- [x] Task 1.1: useBigscreenData 接入真实 API
- [x] Task 1.2: 创建 bigscreen API 模块
- [x] Task 2.1: 侧边栏添加大屏入口
- [x] Task 2.2: 仪表盘添加快捷入口
- [x] Task 3.1: 大屏加载布局配置
- [x] Task 3.2: 添加返回主系统按钮
- [x] Task 4.1: 后端布局 API (可选 - 已跳过，使用前端默认布局)
- [x] Task 5.1: 完整功能测试

---

*本计划将数字孪生大屏完整集成到算力中心智能监控系统中，实现真实数据展示和便捷导航。*
