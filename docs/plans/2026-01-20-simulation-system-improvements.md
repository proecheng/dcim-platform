# 模拟数据系统改进实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 改进模拟数据系统，实现按需加载、日期动态调整、以及算力中心各楼层平面布局图和3D可视化

**Architecture:**
- 前端：仪表盘添加"加载演示数据"按钮，带进度显示
- 后端：提供模拟数据加载API，支持日期偏移计算
- 可视化：SVG平面布局图 + Three.js 3D楼宇模型

**Tech Stack:** Vue 3, TypeScript, Three.js, Python FastAPI, SQLAlchemy

---

## 大楼布局设计

### 楼层结构 (基于已定义的330个点位)

| 楼层 | 面积 | 用途 | 机柜数 | 主要设备 |
|------|------|------|--------|----------|
| B1 | 500㎡ | 地下制冷机房 | - | 冷水机组×2、冷却塔×2、冷冻/冷却水泵×4 |
| F1 | 1000㎡ | 1楼机房区A | 20台 | UPS×2、精密空调×4、配电柜、PDU×20 |
| F2 | 1000㎡ | 2楼机房区B | 15台 | UPS×2、精密空调×4、配电柜、PDU×15 |
| F3 | 1000㎡ | 3楼办公监控 | 8台 | UPS×1、精密空调×2、监控中心、会议室 |

### 平面布局设计 (参考图片67-73)

#### B1 制冷机房平面图 (40m × 12.5m)
```
┌─────────────────────────────────────────────────────────────┐
│  冷却塔区 (室外)                                              │
│  ┌─────────┐  ┌─────────┐                                   │
│  │  CT-1   │  │  CT-2   │                                   │
│  └─────────┘  └─────────┘                                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────┐  ┌─────────┐     ┌────────┐  ┌────────┐       │
│  │ 冷水机组1│  │ 冷水机组2│     │冷冻水泵1│  │冷冻水泵2│       │
│  │  CH-1   │  │  CH-2   │     │ CHWP-1 │  │ CHWP-2 │       │
│  └─────────┘  └─────────┘     └────────┘  └────────┘       │
│                                                             │
│  ┌────────┐  ┌────────┐       [配电柜]     [控制柜]         │
│  │冷却水泵1│  │冷却水泵2│                                    │
│  │ CWP-1  │  │ CWP-2  │                                    │
│  └────────┘  └────────┘                                    │
│                                          [入口]             │
└─────────────────────────────────────────────────────────────┘
```

#### F1 机房区A平面图 (40m × 25m)
```
┌─────────────────────────────────────────────────────────────┐
│ [精密空调1] [精密空调2]           [精密空调3] [精密空调4]      │
├─────────────────────────────────────────────────────────────┤
│     冷通道                    冷通道                         │
│  ┌──┐┌──┐┌──┐┌──┐┌──┐     ┌──┐┌──┐┌──┐┌──┐┌──┐           │
│  │01││02││03││04││05│     │11││12││13││14││15│           │
│  └──┘└──┘└──┘└──┘└──┘     └──┘└──┘└──┘└──┘└──┘           │
│     热通道                    热通道                         │
│  ┌──┐┌──┐┌──┐┌──┐┌──┐     ┌──┐┌──┐┌──┐┌──┐┌──┐           │
│  │06││07││08││09││10│     │16││17││18││19││20│           │
│  └──┘└──┘└──┘└──┘└──┘     └──┘└──┘└──┘└──┘└──┘           │
│     冷通道                    冷通道                         │
├─────────────────────────────────────────────────────────────┤
│ [UPS-1]  [UPS-2]  [配电柜]  [消防控制]       [入口] [楼梯]   │
└─────────────────────────────────────────────────────────────┘
```

#### F2 机房区B平面图 (40m × 25m)
```
┌─────────────────────────────────────────────────────────────┐
│ [精密空调1] [精密空调2]           [精密空调3] [精密空调4]      │
├─────────────────────────────────────────────────────────────┤
│     冷通道                                                   │
│  ┌──┐┌──┐┌──┐┌──┐┌──┐     ┌──┐┌──┐┌──┐                    │
│  │01││02││03││04││05│     │11││12││13│                    │
│  └──┘└──┘└──┘└──┘└──┘     └──┘└──┘└──┘                    │
│     热通道                                                   │
│  ┌──┐┌──┐┌──┐┌──┐┌──┐     ┌──┐┌──┐                        │
│  │06││07││08││09││10│     │14││15│     [备用区]           │
│  └──┘└──┘└──┘└──┘└──┘     └──┘└──┘                        │
│     冷通道                                                   │
├─────────────────────────────────────────────────────────────┤
│ [UPS-1]  [UPS-2]  [配电柜]  [消防控制]       [入口] [楼梯]   │
└─────────────────────────────────────────────────────────────┘
```

#### F3 办公监控区平面图 (40m × 25m)
```
┌─────────────────────────────────────────────────────────────┐
│  ┌────────────────────┐   ┌────────────────────┐           │
│  │      监控中心       │   │      会议室         │           │
│  │  (大屏显示墙+工位)   │   │                    │           │
│  └────────────────────┘   └────────────────────┘           │
├─────────────────────────────────────────────────────────────┤
│ [精密空调1]                               [精密空调2]        │
│                                                             │
│  ┌──┐┌──┐┌──┐┌──┐     ┌──┐┌──┐┌──┐┌──┐                    │
│  │01││02││03││04│     │05││06││07││08│   [小型机房区]      │
│  └──┘└──┘└──┘└──┘     └──┘└──┘└──┘└──┘                    │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│ [UPS-1]  [配电柜]  [茶水间]  [卫生间]       [入口] [楼梯]    │
└─────────────────────────────────────────────────────────────┘
```

---

## Phase 1: 后端API - 模拟数据加载服务

### Task 1.1: 创建模拟数据加载服务

**Files:**
- Create: `backend/app/services/demo_data_service.py`

**Step 1: 创建演示数据服务**

```python
"""
演示数据服务 - 支持按需加载和日期偏移
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Callable
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import async_session, init_db
from ..models import Point, PointRealtime, PointHistory, AlarmThreshold, PUEHistory
from ..data.building_points import get_all_points, get_threshold_for_point


class DemoDataService:
    """演示数据服务"""

    def __init__(self):
        self.is_loaded = False
        self.loading = False
        self.progress = 0
        self.progress_message = ""

    async def check_demo_data_status(self) -> dict:
        """检查演示数据状态"""
        async with async_session() as session:
            # 检查点位数量
            result = await session.execute(select(func.count(Point.id)))
            point_count = result.scalar() or 0

            # 检查是否有模拟数据标记
            # 演示数据点位编码以B1_/F1_/F2_/F3_开头
            result = await session.execute(
                select(func.count(Point.id)).where(
                    Point.point_code.like("B1_%") |
                    Point.point_code.like("F1_%") |
                    Point.point_code.like("F2_%") |
                    Point.point_code.like("F3_%")
                )
            )
            demo_point_count = result.scalar() or 0

            # 检查历史数据
            result = await session.execute(select(func.count(PointHistory.id)))
            history_count = result.scalar() or 0

            self.is_loaded = demo_point_count > 300

            return {
                "is_loaded": self.is_loaded,
                "point_count": point_count,
                "demo_point_count": demo_point_count,
                "history_count": history_count,
                "loading": self.loading,
                "progress": self.progress,
                "progress_message": self.progress_message
            }

    async def load_demo_data(
        self,
        days: int = 30,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> dict:
        """加载演示数据（带进度回调）"""
        if self.loading:
            return {"success": False, "message": "正在加载中，请稍候"}

        self.loading = True
        self.progress = 0
        self.progress_message = "初始化..."

        try:
            await init_db()

            # Phase 1: 检查并清理旧数据 (0-10%)
            self._update_progress(5, "检查现有数据...", progress_callback)
            status = await self.check_demo_data_status()

            if status["demo_point_count"] > 0:
                self._update_progress(8, "清理旧演示数据...", progress_callback)
                await self._clear_demo_data()

            # Phase 2: 创建点位 (10-40%)
            self._update_progress(10, "创建监控点位...", progress_callback)
            point_count = await self._create_points(progress_callback)

            # Phase 3: 生成历史数据 (40-90%)
            self._update_progress(40, "生成历史数据...", progress_callback)
            history_count = await self._generate_history(days, progress_callback)

            # Phase 4: 生成PUE历史 (90-100%)
            self._update_progress(90, "生成能耗数据...", progress_callback)
            await self._generate_pue_history(days, progress_callback)

            self._update_progress(100, "加载完成", progress_callback)
            self.is_loaded = True

            return {
                "success": True,
                "message": f"成功加载演示数据",
                "point_count": point_count,
                "history_count": history_count,
                "days": days
            }

        except Exception as e:
            self._update_progress(0, f"加载失败: {str(e)}", progress_callback)
            return {"success": False, "message": str(e)}
        finally:
            self.loading = False

    async def unload_demo_data(self) -> dict:
        """卸载演示数据"""
        if self.loading:
            return {"success": False, "message": "正在操作中，请稍候"}

        self.loading = True
        self.progress = 0
        self.progress_message = "正在卸载..."

        try:
            await self._clear_demo_data()
            self.is_loaded = False
            return {"success": True, "message": "演示数据已卸载"}
        except Exception as e:
            return {"success": False, "message": str(e)}
        finally:
            self.loading = False

    async def refresh_dates(self) -> dict:
        """刷新历史数据日期到最近30天"""
        async with async_session() as session:
            # 获取历史数据的时间范围
            result = await session.execute(
                select(func.min(PointHistory.recorded_at), func.max(PointHistory.recorded_at))
            )
            min_date, max_date = result.one()

            if not min_date or not max_date:
                return {"success": False, "message": "没有历史数据"}

            # 计算偏移量：将max_date调整到当前时间
            now = datetime.now()
            offset = now - max_date

            # 更新PointHistory日期
            await session.execute(
                update(PointHistory).values(
                    recorded_at=PointHistory.recorded_at + offset
                )
            )

            # 更新PUEHistory日期
            await session.execute(
                update(PUEHistory).values(
                    record_time=PUEHistory.record_time + offset
                )
            )

            await session.commit()

            return {
                "success": True,
                "message": f"日期已更新，偏移 {offset.days} 天",
                "offset_days": offset.days
            }

    async def _clear_demo_data(self):
        """清理演示数据"""
        async with async_session() as session:
            # 获取演示点位ID
            result = await session.execute(
                select(Point.id).where(
                    Point.point_code.like("B1_%") |
                    Point.point_code.like("F1_%") |
                    Point.point_code.like("F2_%") |
                    Point.point_code.like("F3_%")
                )
            )
            demo_point_ids = [r[0] for r in result.fetchall()]

            if demo_point_ids:
                # 删除相关历史数据
                await session.execute(
                    delete(PointHistory).where(PointHistory.point_id.in_(demo_point_ids))
                )
                # 删除告警阈值
                await session.execute(
                    delete(AlarmThreshold).where(AlarmThreshold.point_id.in_(demo_point_ids))
                )
                # 删除实时数据
                await session.execute(
                    delete(PointRealtime).where(PointRealtime.point_id.in_(demo_point_ids))
                )
                # 删除点位
                await session.execute(
                    delete(Point).where(Point.id.in_(demo_point_ids))
                )

            # 删除PUE历史
            await session.execute(delete(PUEHistory))

            await session.commit()

    async def _create_points(self, progress_callback) -> int:
        """创建点位"""
        async with async_session() as session:
            points = get_all_points()
            total_created = 0
            total_points = sum(len(plist) for plist in points.values())

            for point_type, point_list in points.items():
                for i, p in enumerate(point_list):
                    point = Point(
                        point_code=p["point_code"],
                        point_name=p["point_name"],
                        point_type=point_type,
                        device_type=p["device_type"],
                        area_code=p["point_code"].split("_")[0],
                        unit=p.get("unit", ""),
                        data_type=p.get("data_type", "float" if point_type == "AI" else "boolean"),
                        min_range=p.get("min_range"),
                        max_range=p.get("max_range"),
                        collect_interval=p.get("collect_interval", 10),
                        is_enabled=True,
                    )
                    session.add(point)
                    await session.flush()

                    # 创建实时数据
                    realtime = PointRealtime(
                        point_id=point.id,
                        value=0,
                        status="normal",
                    )
                    session.add(realtime)

                    # 创建告警阈值
                    thresholds = get_threshold_for_point(p["point_code"], p["point_name"])
                    for t in thresholds:
                        threshold = AlarmThreshold(
                            point_id=point.id,
                            threshold_type=t["type"],
                            threshold_value=t["value"],
                            alarm_level=t["level"],
                            alarm_message=t["message"],
                            is_enabled=True,
                        )
                        session.add(threshold)

                    total_created += 1

                    # 每50个点位更新一次进度
                    if total_created % 50 == 0:
                        progress = 10 + int((total_created / total_points) * 30)
                        self._update_progress(progress, f"创建点位 {total_created}/{total_points}", progress_callback)

            await session.commit()
            return total_created

    async def _generate_history(self, days: int, progress_callback) -> int:
        """生成历史数据"""
        from ..services.history_generator import HistoryGenerator

        generator = HistoryGenerator(days=days)
        total_hours = days * 24

        async with async_session() as session:
            result = await session.execute(select(Point).where(Point.is_enabled == True))
            points = result.scalars().all()

            total_records = 0
            batch_records = []
            batch_size = 1000

            for i, point in enumerate(points):
                records = generator.generate_point_history(point, total_hours)

                for r in records:
                    batch_records.append(PointHistory(**r))

                    if len(batch_records) >= batch_size:
                        session.add_all(batch_records)
                        await session.commit()
                        total_records += len(batch_records)
                        batch_records = []

                        # 更新进度 40-90%
                        progress = 40 + int((total_records / (len(points) * total_hours)) * 50)
                        self._update_progress(
                            min(progress, 89),
                            f"生成历史数据 {total_records} 条...",
                            progress_callback
                        )

            if batch_records:
                session.add_all(batch_records)
                await session.commit()
                total_records += len(batch_records)

            return total_records

    async def _generate_pue_history(self, days: int, progress_callback):
        """生成PUE历史数据"""
        from ..services.history_generator import HistoryGenerator

        generator = HistoryGenerator(days=days)
        await generator.generate_energy_history()

    def _update_progress(self, progress: int, message: str, callback: Optional[Callable] = None):
        """更新进度"""
        self.progress = progress
        self.progress_message = message
        if callback:
            callback(progress, message)


# 全局服务实例
demo_data_service = DemoDataService()
```

**Step 2: 验证服务导入**

Run:
```bash
cd /d/mytest1 && python -c "from backend.app.services.demo_data_service import demo_data_service; print('OK')"
```

Expected: 输出 "OK"

---

### Task 1.2: 创建演示数据API端点

**Files:**
- Create: `backend/app/api/v1/demo.py`
- Modify: `backend/app/api/v1/__init__.py`

**Step 1: 创建API路由**

创建 `backend/app/api/v1/demo.py`:

```python
"""
演示数据API
"""
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from typing import Optional

from ...services.demo_data_service import demo_data_service

router = APIRouter(prefix="/demo", tags=["演示数据"])


class LoadDemoDataRequest(BaseModel):
    days: int = 30


class DemoDataResponse(BaseModel):
    success: bool
    message: str
    data: Optional[dict] = None


@router.get("/status")
async def get_demo_status():
    """获取演示数据状态"""
    status = await demo_data_service.check_demo_data_status()
    return {"code": 0, "data": status}


@router.post("/load")
async def load_demo_data(request: LoadDemoDataRequest, background_tasks: BackgroundTasks):
    """加载演示数据（后台任务）"""
    if demo_data_service.loading:
        return {
            "code": 1,
            "message": "正在加载中，请稍候",
            "data": {
                "progress": demo_data_service.progress,
                "progress_message": demo_data_service.progress_message
            }
        }

    # 启动后台任务
    background_tasks.add_task(demo_data_service.load_demo_data, request.days)

    return {
        "code": 0,
        "message": "开始加载演示数据",
        "data": {"days": request.days}
    }


@router.get("/progress")
async def get_load_progress():
    """获取加载进度"""
    return {
        "code": 0,
        "data": {
            "loading": demo_data_service.loading,
            "progress": demo_data_service.progress,
            "progress_message": demo_data_service.progress_message,
            "is_loaded": demo_data_service.is_loaded
        }
    }


@router.post("/unload")
async def unload_demo_data():
    """卸载演示数据"""
    result = await demo_data_service.unload_demo_data()
    return {"code": 0 if result["success"] else 1, **result}


@router.post("/refresh-dates")
async def refresh_dates():
    """刷新历史数据日期到最近30天"""
    result = await demo_data_service.refresh_dates()
    return {"code": 0 if result["success"] else 1, **result}
```

**Step 2: 注册路由**

在 `backend/app/api/v1/__init__.py` 中添加:

```python
from .demo import router as demo_router
# 在 api_router.include_router 调用列表中添加
api_router.include_router(demo_router)
```

**Step 3: 验证API注册**

Run:
```bash
cd /d/mytest1 && python -c "from backend.app.api.v1 import api_router; print([r.path for r in api_router.routes if 'demo' in str(r.path)])"
```

Expected: 输出包含 `/demo/` 的路由列表

---

## Phase 2: 前端 - 演示数据加载组件

### Task 2.1: 创建演示数据API模块

**Files:**
- Create: `frontend/src/api/modules/demo.ts`
- Modify: `frontend/src/api/modules/index.ts`

**Step 1: 创建API模块**

创建 `frontend/src/api/modules/demo.ts`:

```typescript
/**
 * 演示数据 API
 */
import request from '../request'

// 获取演示数据状态
export function getDemoStatus() {
  return request.get('/demo/status')
}

// 加载演示数据
export function loadDemoData(days: number = 30) {
  return request.post('/demo/load', { days })
}

// 获取加载进度
export function getDemoProgress() {
  return request.get('/demo/progress')
}

// 卸载演示数据
export function unloadDemoData() {
  return request.post('/demo/unload')
}

// 刷新历史数据日期
export function refreshDemoDataDates() {
  return request.post('/demo/refresh-dates')
}
```

**Step 2: 导出API模块**

在 `frontend/src/api/modules/index.ts` 中添加:

```typescript
export * from './demo'
```

---

### Task 2.2: 创建演示数据加载对话框组件

**Files:**
- Create: `frontend/src/components/DemoDataLoader.vue`

**Step 1: 创建组件**

```vue
<template>
  <el-dialog
    v-model="visible"
    title="演示数据管理"
    width="500px"
    :close-on-click-modal="false"
  >
    <div class="demo-loader">
      <!-- 状态显示 -->
      <div class="status-section">
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="数据状态">
            <el-tag :type="status.is_loaded ? 'success' : 'info'">
              {{ status.is_loaded ? '已加载' : '未加载' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="演示点位数">
            {{ status.demo_point_count || 0 }}
          </el-descriptions-item>
          <el-descriptions-item label="历史记录数">
            {{ formatNumber(status.history_count || 0) }}
          </el-descriptions-item>
        </el-descriptions>
      </div>

      <!-- 加载进度 -->
      <div class="progress-section" v-if="status.loading">
        <el-progress
          :percentage="status.progress"
          :stroke-width="20"
          :text-inside="true"
        />
        <div class="progress-message">{{ status.progress_message }}</div>
      </div>

      <!-- 操作按钮 -->
      <div class="action-section">
        <template v-if="!status.is_loaded">
          <el-button
            type="primary"
            :loading="status.loading"
            :icon="Download"
            @click="handleLoad"
          >
            {{ status.loading ? '加载中...' : '加载演示数据' }}
          </el-button>
          <div class="action-hint">
            加载约330个监控点位和30天历史数据
          </div>
        </template>
        <template v-else>
          <el-button
            type="success"
            :icon="Refresh"
            @click="handleRefreshDates"
            :loading="refreshing"
          >
            刷新日期到最近
          </el-button>
          <el-button
            type="danger"
            :icon="Delete"
            @click="handleUnload"
            :loading="unloading"
          >
            卸载演示数据
          </el-button>
        </template>
      </div>

      <!-- 说明 -->
      <div class="info-section">
        <el-alert type="info" :closable="false">
          <template #title>
            <strong>演示数据说明</strong>
          </template>
          <ul class="info-list">
            <li>演示数据模拟3层算力中心大楼的动环监控系统</li>
            <li>包含B1制冷机房、F1-F2机房区、F3办公监控区</li>
            <li>加载后可体验完整的监控、告警、能耗等功能</li>
            <li>"刷新日期"可将历史数据更新为最近30天</li>
          </ul>
        </el-alert>
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, watch, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Download, Delete, Refresh } from '@element-plus/icons-vue'
import { getDemoStatus, loadDemoData, getDemoProgress, unloadDemoData, refreshDemoDataDates } from '@/api/modules/demo'

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits(['update:modelValue', 'loaded', 'unloaded'])

const visible = ref(false)
const refreshing = ref(false)
const unloading = ref(false)
let progressTimer: number | null = null

const status = reactive({
  is_loaded: false,
  demo_point_count: 0,
  history_count: 0,
  loading: false,
  progress: 0,
  progress_message: ''
})

watch(() => props.modelValue, (val) => {
  visible.value = val
  if (val) {
    fetchStatus()
  }
})

watch(visible, (val) => {
  emit('update:modelValue', val)
  if (!val && progressTimer) {
    clearInterval(progressTimer)
    progressTimer = null
  }
})

onMounted(() => {
  if (props.modelValue) {
    fetchStatus()
  }
})

async function fetchStatus() {
  try {
    const res = await getDemoStatus()
    if (res.data) {
      Object.assign(status, res.data)
    }

    // 如果正在加载，启动进度轮询
    if (status.loading && !progressTimer) {
      startProgressPolling()
    }
  } catch (e) {
    console.error('获取演示数据状态失败', e)
  }
}

function startProgressPolling() {
  progressTimer = window.setInterval(async () => {
    try {
      const res = await getDemoProgress()
      if (res.data) {
        Object.assign(status, res.data)

        if (!res.data.loading) {
          clearInterval(progressTimer!)
          progressTimer = null

          if (res.data.is_loaded) {
            ElMessage.success('演示数据加载完成')
            emit('loaded')
          }
        }
      }
    } catch (e) {
      console.error('获取进度失败', e)
    }
  }, 1000)
}

async function handleLoad() {
  try {
    const res = await loadDemoData(30)
    if (res.code === 0) {
      status.loading = true
      status.progress = 0
      status.progress_message = '开始加载...'
      startProgressPolling()
    } else {
      ElMessage.warning(res.message)
    }
  } catch (e) {
    ElMessage.error('启动加载失败')
  }
}

async function handleUnload() {
  try {
    await ElMessageBox.confirm(
      '确定要卸载演示数据吗？所有演示点位和历史数据将被删除。',
      '确认卸载',
      { type: 'warning' }
    )

    unloading.value = true
    const res = await unloadDemoData()

    if (res.code === 0) {
      ElMessage.success('演示数据已卸载')
      status.is_loaded = false
      status.demo_point_count = 0
      status.history_count = 0
      emit('unloaded')
    } else {
      ElMessage.error(res.message)
    }
  } catch (e) {
    // 用户取消
  } finally {
    unloading.value = false
  }
}

async function handleRefreshDates() {
  refreshing.value = true
  try {
    const res = await refreshDemoDataDates()
    if (res.code === 0) {
      ElMessage.success(`历史数据日期已更新到最近${res.data?.offset_days || 30}天`)
    } else {
      ElMessage.error(res.message)
    }
  } catch (e) {
    ElMessage.error('刷新日期失败')
  } finally {
    refreshing.value = false
  }
}

function formatNumber(num: number): string {
  return num.toLocaleString()
}
</script>

<style scoped lang="scss">
.demo-loader {
  .status-section {
    margin-bottom: 20px;
  }

  .progress-section {
    margin-bottom: 20px;

    .progress-message {
      margin-top: 8px;
      text-align: center;
      color: var(--el-text-color-secondary);
      font-size: 13px;
    }
  }

  .action-section {
    text-align: center;
    margin-bottom: 20px;

    .action-hint {
      margin-top: 8px;
      color: var(--el-text-color-secondary);
      font-size: 12px;
    }
  }

  .info-section {
    .info-list {
      margin: 8px 0 0;
      padding-left: 20px;
      font-size: 12px;
      line-height: 1.8;
    }
  }
}
</style>
```

---

### Task 2.3: 在仪表盘添加演示数据入口

**Files:**
- Modify: `frontend/src/views/dashboard/index.vue`

**Step 1: 导入组件和API**

在 script 部分添加导入:

```typescript
import DemoDataLoader from '@/components/DemoDataLoader.vue'
import { Database } from '@element-plus/icons-vue'

// 在 data/ref 中添加
const showDemoLoader = ref(false)
```

**Step 2: 在快捷操作栏添加按钮**

在模板的快捷操作栏中添加:

```vue
<el-button :icon="Database" @click="showDemoLoader = true">
  演示数据
</el-button>
```

**Step 3: 添加对话框组件**

在模板末尾添加:

```vue
<!-- 演示数据加载对话框 -->
<DemoDataLoader v-model="showDemoLoader" @loaded="refreshData" @unloaded="refreshData" />
```

---

## Phase 3: 楼层平面布局SVG组件

### Task 3.1: 创建SVG布局组件基础

**Files:**
- Create: `frontend/src/components/floor-layouts/FloorLayoutBase.vue`
- Create: `frontend/src/components/floor-layouts/index.ts`

**Step 1: 创建基础布局组件**

创建 `frontend/src/components/floor-layouts/FloorLayoutBase.vue`:

```vue
<template>
  <div class="floor-layout" :style="{ width: width + 'px', height: height + 'px' }">
    <svg
      :viewBox="`0 0 ${viewBoxWidth} ${viewBoxHeight}`"
      preserveAspectRatio="xMidYMid meet"
      xmlns="http://www.w3.org/2000/svg"
    >
      <!-- 背景 -->
      <rect
        x="0" y="0"
        :width="viewBoxWidth" :height="viewBoxHeight"
        fill="#1a2a4a"
        stroke="#2a4a6a"
        stroke-width="2"
      />

      <!-- 网格线 -->
      <g class="grid-lines" v-if="showGrid">
        <line
          v-for="i in Math.floor(viewBoxWidth / gridSize)"
          :key="'v' + i"
          :x1="i * gridSize" y1="0"
          :x2="i * gridSize" :y2="viewBoxHeight"
          stroke="#2a3a5a"
          stroke-width="0.5"
        />
        <line
          v-for="i in Math.floor(viewBoxHeight / gridSize)"
          :key="'h' + i"
          x1="0" :y1="i * gridSize"
          :x2="viewBoxWidth" :y2="i * gridSize"
          stroke="#2a3a5a"
          stroke-width="0.5"
        />
      </g>

      <!-- 楼层内容插槽 -->
      <slot></slot>

      <!-- 设备标注 -->
      <g class="device-labels">
        <slot name="labels"></slot>
      </g>
    </svg>

    <!-- 图例 -->
    <div class="layout-legend" v-if="showLegend">
      <slot name="legend">
        <div class="legend-item">
          <span class="legend-color" style="background: #409EFF;"></span>
          <span>机柜</span>
        </div>
        <div class="legend-item">
          <span class="legend-color" style="background: #67C23A;"></span>
          <span>空调</span>
        </div>
        <div class="legend-item">
          <span class="legend-color" style="background: #E6A23C;"></span>
          <span>UPS</span>
        </div>
      </slot>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps({
  width: { type: Number, default: 800 },
  height: { type: Number, default: 500 },
  viewBoxWidth: { type: Number, default: 400 },
  viewBoxHeight: { type: Number, default: 250 },
  showGrid: { type: Boolean, default: true },
  showLegend: { type: Boolean, default: true },
  gridSize: { type: Number, default: 20 }
})
</script>

<style scoped lang="scss">
.floor-layout {
  position: relative;
  background: #0a1a2a;
  border-radius: 8px;
  overflow: hidden;

  svg {
    width: 100%;
    height: 100%;
  }

  .layout-legend {
    position: absolute;
    bottom: 10px;
    right: 10px;
    background: rgba(0, 0, 0, 0.6);
    padding: 8px 12px;
    border-radius: 4px;
    display: flex;
    gap: 12px;

    .legend-item {
      display: flex;
      align-items: center;
      gap: 4px;
      font-size: 12px;
      color: #fff;

      .legend-color {
        width: 12px;
        height: 12px;
        border-radius: 2px;
      }
    }
  }
}
</style>
```

---

### Task 3.2: 创建B1制冷机房布局

**Files:**
- Create: `frontend/src/components/floor-layouts/FloorB1Layout.vue`

**Step 1: 创建B1布局组件**

```vue
<template>
  <FloorLayoutBase
    :width="width"
    :height="height"
    :viewBoxWidth="400"
    :viewBoxHeight="125"
  >
    <!-- 区域分隔 -->
    <line x1="0" y1="30" x2="400" y2="30" stroke="#3a5a7a" stroke-width="1" stroke-dasharray="4"/>

    <!-- 冷却塔区域 (室外) -->
    <text x="200" y="15" fill="#6a8aaa" text-anchor="middle" font-size="10">冷却塔区(室外)</text>
    <rect x="60" y="5" width="40" height="20" fill="#4a7a9a" stroke="#5a9aba" rx="2"/>
    <text x="80" y="18" fill="#fff" text-anchor="middle" font-size="8">CT-1</text>
    <rect x="120" y="5" width="40" height="20" fill="#4a7a9a" stroke="#5a9aba" rx="2"/>
    <text x="140" y="18" fill="#fff" text-anchor="middle" font-size="8">CT-2</text>

    <!-- 冷水机组 -->
    <rect x="30" y="45" width="60" height="35" fill="#2a5a8a" stroke="#4a8aba" rx="3"/>
    <text x="60" y="58" fill="#fff" text-anchor="middle" font-size="8">冷水机组1</text>
    <text x="60" y="70" fill="#aaa" text-anchor="middle" font-size="7">CH-1</text>

    <rect x="110" y="45" width="60" height="35" fill="#2a5a8a" stroke="#4a8aba" rx="3"/>
    <text x="140" y="58" fill="#fff" text-anchor="middle" font-size="8">冷水机组2</text>
    <text x="140" y="70" fill="#aaa" text-anchor="middle" font-size="7">CH-2</text>

    <!-- 冷冻水泵 -->
    <rect x="200" y="45" width="40" height="25" fill="#3a6a5a" stroke="#5a9a7a" rx="2"/>
    <text x="220" y="60" fill="#fff" text-anchor="middle" font-size="7">CHWP-1</text>
    <rect x="250" y="45" width="40" height="25" fill="#3a6a5a" stroke="#5a9a7a" rx="2"/>
    <text x="270" y="60" fill="#fff" text-anchor="middle" font-size="7">CHWP-2</text>

    <!-- 冷却水泵 -->
    <rect x="30" y="90" width="40" height="25" fill="#5a6a3a" stroke="#8a9a5a" rx="2"/>
    <text x="50" y="105" fill="#fff" text-anchor="middle" font-size="7">CWP-1</text>
    <rect x="80" y="90" width="40" height="25" fill="#5a6a3a" stroke="#8a9a5a" rx="2"/>
    <text x="100" y="105" fill="#fff" text-anchor="middle" font-size="7">CWP-2</text>

    <!-- 配电柜和控制柜 -->
    <rect x="200" y="85" width="35" height="30" fill="#8a5a3a" stroke="#ba7a5a" rx="2"/>
    <text x="217" y="103" fill="#fff" text-anchor="middle" font-size="7">配电柜</text>
    <rect x="245" y="85" width="35" height="30" fill="#5a5a8a" stroke="#7a7aba" rx="2"/>
    <text x="262" y="103" fill="#fff" text-anchor="middle" font-size="7">控制柜</text>

    <!-- 管道示意 -->
    <path d="M90,80 L90,90 L200,90 L200,57" stroke="#00aaff" fill="none" stroke-width="2" stroke-dasharray="3"/>
    <path d="M170,80 L170,90 L120,90" stroke="#ff6600" fill="none" stroke-width="2" stroke-dasharray="3"/>

    <!-- 入口 -->
    <rect x="350" y="100" width="40" height="20" fill="none" stroke="#67C23A" rx="2" stroke-dasharray="3"/>
    <text x="370" y="113" fill="#67C23A" text-anchor="middle" font-size="8">入口</text>

    <!-- 楼层标识 -->
    <text x="390" y="15" fill="#fff" text-anchor="end" font-size="12" font-weight="bold">B1</text>
    <text x="390" y="25" fill="#6a8aaa" text-anchor="end" font-size="8">地下制冷机房</text>

    <template #legend>
      <div class="legend-item">
        <span class="legend-color" style="background: #2a5a8a;"></span>
        <span>冷水机组</span>
      </div>
      <div class="legend-item">
        <span class="legend-color" style="background: #3a6a5a;"></span>
        <span>冷冻水泵</span>
      </div>
      <div class="legend-item">
        <span class="legend-color" style="background: #5a6a3a;"></span>
        <span>冷却水泵</span>
      </div>
      <div class="legend-item">
        <span class="legend-color" style="background: #4a7a9a;"></span>
        <span>冷却塔</span>
      </div>
    </template>
  </FloorLayoutBase>
</template>

<script setup lang="ts">
import FloorLayoutBase from './FloorLayoutBase.vue'

defineProps({
  width: { type: Number, default: 800 },
  height: { type: Number, default: 250 }
})
</script>
```

---

### Task 3.3: 创建F1机房布局

**Files:**
- Create: `frontend/src/components/floor-layouts/FloorF1Layout.vue`

**Step 1: 创建F1布局组件**

```vue
<template>
  <FloorLayoutBase
    :width="width"
    :height="height"
    :viewBoxWidth="400"
    :viewBoxHeight="250"
  >
    <!-- 精密空调区 -->
    <rect x="30" y="10" width="30" height="20" fill="#67C23A" stroke="#8aE35A" rx="2"/>
    <text x="45" y="23" fill="#fff" text-anchor="middle" font-size="6">AC-1</text>
    <rect x="70" y="10" width="30" height="20" fill="#67C23A" stroke="#8aE35A" rx="2"/>
    <text x="85" y="23" fill="#fff" text-anchor="middle" font-size="6">AC-2</text>
    <rect x="280" y="10" width="30" height="20" fill="#67C23A" stroke="#8aE35A" rx="2"/>
    <text x="295" y="23" fill="#fff" text-anchor="middle" font-size="6">AC-3</text>
    <rect x="320" y="10" width="30" height="20" fill="#67C23A" stroke="#8aE35A" rx="2"/>
    <text x="335" y="23" fill="#fff" text-anchor="middle" font-size="6">AC-4</text>

    <!-- 冷通道标识 -->
    <text x="100" y="45" fill="#00aaff" font-size="8">冷通道</text>
    <text x="250" y="45" fill="#00aaff" font-size="8">冷通道</text>

    <!-- 机柜列 1 (01-05) -->
    <g v-for="i in 5" :key="'r1-' + i">
      <rect
        :x="20 + (i-1) * 35" y="55"
        width="30" height="35"
        fill="#409EFF" stroke="#5abaff"
        rx="2"
        :class="{ 'cabinet-alarm': getDeviceStatus('F1', i) === 'alarm' }"
      />
      <text :x="35 + (i-1) * 35" y="75" fill="#fff" text-anchor="middle" font-size="8">
        {{ String(i).padStart(2, '0') }}
      </text>
    </g>

    <!-- 机柜列 2 (11-15) -->
    <g v-for="i in 5" :key="'r2-' + i">
      <rect
        :x="210 + (i-1) * 35" y="55"
        width="30" height="35"
        fill="#409EFF" stroke="#5abaff"
        rx="2"
      />
      <text :x="225 + (i-1) * 35" y="75" fill="#fff" text-anchor="middle" font-size="8">
        {{ String(10 + i).padStart(2, '0') }}
      </text>
    </g>

    <!-- 热通道标识 -->
    <text x="100" y="105" fill="#ff6600" font-size="8">热通道</text>
    <text x="250" y="105" fill="#ff6600" font-size="8">热通道</text>

    <!-- 机柜列 3 (06-10) -->
    <g v-for="i in 5" :key="'r3-' + i">
      <rect
        :x="20 + (i-1) * 35" y="115"
        width="30" height="35"
        fill="#409EFF" stroke="#5abaff"
        rx="2"
      />
      <text :x="35 + (i-1) * 35" y="135" fill="#fff" text-anchor="middle" font-size="8">
        {{ String(5 + i).padStart(2, '0') }}
      </text>
    </g>

    <!-- 机柜列 4 (16-20) -->
    <g v-for="i in 5" :key="'r4-' + i">
      <rect
        :x="210 + (i-1) * 35" y="115"
        width="30" height="35"
        fill="#409EFF" stroke="#5abaff"
        rx="2"
      />
      <text :x="225 + (i-1) * 35" y="135" fill="#fff" text-anchor="middle" font-size="8">
        {{ String(15 + i).padStart(2, '0') }}
      </text>
    </g>

    <!-- 冷通道标识 -->
    <text x="100" y="165" fill="#00aaff" font-size="8">冷通道</text>
    <text x="250" y="165" fill="#00aaff" font-size="8">冷通道</text>

    <!-- 底部设备区 -->
    <line x1="0" y1="180" x2="400" y2="180" stroke="#3a5a7a" stroke-width="1"/>

    <!-- UPS -->
    <rect x="20" y="190" width="50" height="40" fill="#E6A23C" stroke="#ffba5c" rx="3"/>
    <text x="45" y="213" fill="#fff" text-anchor="middle" font-size="8">UPS-1</text>
    <rect x="80" y="190" width="50" height="40" fill="#E6A23C" stroke="#ffba5c" rx="3"/>
    <text x="105" y="213" fill="#fff" text-anchor="middle" font-size="8">UPS-2</text>

    <!-- 配电柜 -->
    <rect x="150" y="190" width="45" height="40" fill="#8a5a3a" stroke="#ba7a5a" rx="2"/>
    <text x="172" y="213" fill="#fff" text-anchor="middle" font-size="7">配电柜</text>

    <!-- 消防控制 -->
    <rect x="210" y="190" width="45" height="40" fill="#f56c6c" stroke="#ff8c8c" rx="2"/>
    <text x="232" y="213" fill="#fff" text-anchor="middle" font-size="7">消防</text>

    <!-- 入口和楼梯 -->
    <rect x="320" y="200" width="35" height="25" fill="none" stroke="#67C23A" rx="2" stroke-dasharray="3"/>
    <text x="337" y="216" fill="#67C23A" text-anchor="middle" font-size="7">入口</text>
    <rect x="360" y="200" width="30" height="25" fill="none" stroke="#909399" rx="2"/>
    <text x="375" y="216" fill="#909399" text-anchor="middle" font-size="7">楼梯</text>

    <!-- 楼层标识 -->
    <text x="390" y="15" fill="#fff" text-anchor="end" font-size="12" font-weight="bold">F1</text>
    <text x="390" y="25" fill="#6a8aaa" text-anchor="end" font-size="8">1楼机房区A</text>
  </FloorLayoutBase>
</template>

<script setup lang="ts">
import FloorLayoutBase from './FloorLayoutBase.vue'

defineProps({
  width: { type: Number, default: 800 },
  height: { type: Number, default: 500 }
})

function getDeviceStatus(floor: string, index: number): string {
  // 这里可以接入实际的设备状态数据
  return 'normal'
}
</script>

<style scoped>
.cabinet-alarm {
  fill: #f56c6c !important;
  animation: alarm-blink 1s infinite;
}

@keyframes alarm-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}
</style>
```

---

### Task 3.4: 创建F2和F3布局 (类似F1结构)

**Files:**
- Create: `frontend/src/components/floor-layouts/FloorF2Layout.vue`
- Create: `frontend/src/components/floor-layouts/FloorF3Layout.vue`

**Step 1: F2布局 (15机柜版本)**

创建 `FloorF2Layout.vue` - 结构与F1类似，但机柜数量为15台

**Step 2: F3布局 (8机柜 + 办公区)**

创建 `FloorF3Layout.vue` - 包含监控中心和会议室区域

---

### Task 3.5: 创建楼层布局索引和选择器

**Files:**
- Create: `frontend/src/components/floor-layouts/index.ts`
- Create: `frontend/src/components/floor-layouts/FloorLayoutSelector.vue`

**Step 1: 创建索引文件**

```typescript
export { default as FloorLayoutBase } from './FloorLayoutBase.vue'
export { default as FloorB1Layout } from './FloorB1Layout.vue'
export { default as FloorF1Layout } from './FloorF1Layout.vue'
export { default as FloorF2Layout } from './FloorF2Layout.vue'
export { default as FloorF3Layout } from './FloorF3Layout.vue'
export { default as FloorLayoutSelector } from './FloorLayoutSelector.vue'
```

**Step 2: 创建楼层选择器**

```vue
<template>
  <div class="floor-selector">
    <div class="floor-tabs">
      <el-radio-group v-model="currentFloor" size="small">
        <el-radio-button label="B1">B1 制冷机房</el-radio-button>
        <el-radio-button label="F1">F1 机房区A</el-radio-button>
        <el-radio-button label="F2">F2 机房区B</el-radio-button>
        <el-radio-button label="F3">F3 办公监控</el-radio-button>
      </el-radio-group>
    </div>

    <div class="floor-content">
      <FloorB1Layout v-if="currentFloor === 'B1'" v-bind="$attrs" />
      <FloorF1Layout v-else-if="currentFloor === 'F1'" v-bind="$attrs" />
      <FloorF2Layout v-else-if="currentFloor === 'F2'" v-bind="$attrs" />
      <FloorF3Layout v-else-if="currentFloor === 'F3'" v-bind="$attrs" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import FloorB1Layout from './FloorB1Layout.vue'
import FloorF1Layout from './FloorF1Layout.vue'
import FloorF2Layout from './FloorF2Layout.vue'
import FloorF3Layout from './FloorF3Layout.vue'

const currentFloor = ref('F1')
</script>

<style scoped lang="scss">
.floor-selector {
  .floor-tabs {
    margin-bottom: 16px;
    text-align: center;
  }
}
</style>
```

---

## Phase 4: 3D楼宇模型集成

### Task 4.1: 扩展Three.js场景支持多楼层

**Files:**
- Modify: `frontend/src/composables/bigscreen/useThreeScene.ts`

**Step 1: 添加楼层切换函数**

在 useThreeScene 中添加楼层切换功能，支持在3D视图中切换查看不同楼层。

---

### Task 4.2: 创建3D楼宇建模组件

**Files:**
- Create: `frontend/src/composables/bigscreen/useBuildingModel.ts`

**Step 1: 创建楼宇模型生成器**

使用Three.js几何体构建简化的3D楼宇模型，包含：
- 4层楼结构（B1, F1, F2, F3）
- 机柜模型
- 空调/UPS设备模型
- 可点击交互

---

## Phase 5: 构建验证

### Task 5.1: 后端测试

**Step 1: 测试演示数据API**

Run:
```bash
cd /d/mytest1 && python -c "
import asyncio
from backend.app.services.demo_data_service import demo_data_service
asyncio.run(demo_data_service.check_demo_data_status())
print('OK')
"
```

**Step 2: 验证日期刷新功能**

Run:
```bash
cd /d/mytest1 && python -c "
from backend.app.services.demo_data_service import DemoDataService
print('DemoDataService loaded OK')
"
```

### Task 5.2: 前端构建测试

Run:
```bash
cd /d/mytest1/frontend && npm run build
```

Expected: 构建成功

---

## 验证清单

- [ ] Task 1.1: 创建演示数据服务
- [ ] Task 1.2: 创建演示数据API端点
- [ ] Task 2.1: 创建前端API模块
- [ ] Task 2.2: 创建演示数据加载对话框
- [ ] Task 2.3: 在仪表盘添加入口
- [ ] Task 3.1: 创建SVG布局基础组件
- [ ] Task 3.2: 创建B1制冷机房布局
- [ ] Task 3.3: 创建F1机房布局
- [ ] Task 3.4: 创建F2/F3布局
- [ ] Task 3.5: 创建楼层选择器
- [ ] Task 4.1: 扩展Three.js多楼层支持
- [ ] Task 4.2: 创建3D楼宇模型
- [ ] Task 5.1: 后端测试
- [ ] Task 5.2: 前端构建测试

---

## 核心改进点总结

1. **按需加载**: 用户可在仪表盘点击"演示数据"按钮，选择加载或卸载
2. **进度显示**: 加载过程显示进度条和状态信息
3. **日期刷新**: 历史数据可一键刷新到最近30天
4. **平面布局**: 4个楼层的SVG平面布局图，可视化展示设备分布
5. **3D可视化**: Three.js 3D楼宇模型，支持楼层切换和设备交互

---

*本计划将模拟数据系统改进为独立的可选模块，并提供完整的楼层可视化方案。*
