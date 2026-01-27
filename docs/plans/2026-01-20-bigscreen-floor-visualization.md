# 数字孪生大屏楼层可视化实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 移除侧边栏大屏入口，修复导航问题，实现楼层2D/3D可视化切换，并集成到演示数据系统

**Architecture:** 修改导航配置 → 修复交互问题 → 创建楼层图生成系统 → 实现大屏楼层切换 → 集成演示数据加载

**Tech Stack:** Vue 3, TypeScript, Three.js, Canvas 2D, Python/FastAPI, SQLAlchemy

---

## 问题现状分析

| 问题 | 现状 | 根因 |
|------|------|------|
| 侧边栏有大屏入口 | MainLayout.vue L105-108 有菜单项 | 设计需求变更 |
| 大屏左侧面板点击无效 | handleNavigate 使用 window.open 新标签页 | window.opener 为真时总是新标签页 |
| 无楼层切换功能 | FloorLayoutSelector 存在但未集成 | 仅有2D组件，未连接大屏 |
| 无2D/3D切换 | 仅有3D场景 | 未实现2D平面图展示 |

## 楼层结构

```
B1 - 地下制冷机房 (冷水机、冷却塔、水泵)
F1 - 1楼机房区A (20个机柜、UPS、空调)
F2 - 2楼机房区B (15个机柜、UPS、空调)
F3 - 3楼办公监控 (8个机柜、UPS、空调)
```

---

## Task 1: 移除侧边栏大屏菜单项

**Files:**
- Modify: `frontend/src/layouts/MainLayout.vue`

**Step 1: 删除大屏菜单项**

找到并删除以下代码块（约L105-108）：
```vue
<el-menu-item index="/bigscreen" @click="openBigscreen">
  <el-icon><FullScreen /></el-icon>
  <template #title>数字孪生大屏</template>
</el-menu-item>
```

**Step 2: 删除相关方法**

删除 openBigscreen 方法（如存在）

**Step 3: 验证**

Run: `npm run build`
Expected: 构建成功，无错误

---

## Task 2: 修复大屏面板导航问题

**Files:**
- Modify: `frontend/src/views/bigscreen/index.vue`

**Step 1: 修改 handleNavigate 函数**

当前代码（L386-394）：
```typescript
function handleNavigate(path: string) {
  if (window.opener) {
    window.open(path, '_blank')
  } else {
    router.push(path)
  }
}
```

修改为（始终在父窗口导航）：
```typescript
function handleNavigate(path: string) {
  if (window.opener) {
    // 在打开此窗口的父窗口中导航
    window.opener.location.href = path
    // 可选：关闭大屏窗口
    // window.close()
  } else {
    router.push(path)
  }
}
```

**Step 2: 验证**

Run: `npm run build`
Expected: 构建成功

---

## Task 3: 创建楼层图数据模型

**Files:**
- Create: `backend/app/models/floor_map.py`
- Modify: `backend/app/models/__init__.py`

**Step 1: 创建楼层图模型**

```python
"""楼层平面图模型"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Enum
from sqlalchemy.sql import func
from ..core.database import Base
import enum

class MapType(str, enum.Enum):
    """图类型"""
    MAP_2D = "2d"
    MAP_3D = "3d"

class FloorMap(Base):
    """楼层平面图"""
    __tablename__ = "floor_maps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    floor_code = Column(String(10), nullable=False, comment="楼层代码 B1/F1/F2/F3")
    floor_name = Column(String(50), nullable=False, comment="楼层名称")
    map_type = Column(String(10), nullable=False, comment="图类型 2d/3d")
    map_data = Column(Text, nullable=False, comment="图数据 JSON格式")
    thumbnail = Column(Text, comment="缩略图 Base64")
    is_default = Column(Boolean, default=False, comment="是否默认显示")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
```

**Step 2: 添加到 models/__init__.py**

```python
from .floor_map import FloorMap, MapType
```

**Step 3: 重启后端使表生效**

---

## Task 4: 创建楼层图生成服务

**Files:**
- Create: `backend/app/services/floor_map_generator.py`

**Step 1: 创建2D图生成器**

```python
"""楼层平面图生成服务"""
import json
import math
from typing import Dict, List, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.database import async_session
from ..models import Point, Device

# 楼层配置
FLOOR_CONFIG = {
    "B1": {
        "name": "地下制冷机房",
        "width": 40,
        "height": 30,
        "color": "#1a3a5c",
        "devices": ["chiller", "cooling_tower", "pump"]
    },
    "F1": {
        "name": "1楼机房区A",
        "width": 50,
        "height": 40,
        "color": "#1e4d2b",
        "cabinets": 20,
        "rows": 4,
        "cols": 5
    },
    "F2": {
        "name": "2楼机房区B",
        "width": 50,
        "height": 35,
        "color": "#4a1e6b",
        "cabinets": 15,
        "rows": 3,
        "cols": 5
    },
    "F3": {
        "name": "3楼办公监控",
        "width": 45,
        "height": 30,
        "color": "#6b4a1e",
        "cabinets": 8,
        "rows": 2,
        "cols": 4
    }
}

class FloorMapGenerator:
    """楼层图生成器"""

    def generate_2d_map(self, floor_code: str, devices: List[Dict]) -> Dict[str, Any]:
        """生成2D平面图数据"""
        config = FLOOR_CONFIG.get(floor_code, {})

        map_data = {
            "floor": floor_code,
            "name": config.get("name", f"Floor {floor_code}"),
            "dimensions": {
                "width": config.get("width", 50),
                "height": config.get("height", 40)
            },
            "background": config.get("color", "#1a1a2e"),
            "elements": []
        }

        # 根据楼层类型生成不同布局
        if floor_code == "B1":
            map_data["elements"] = self._generate_cooling_layout(devices)
        else:
            map_data["elements"] = self._generate_datacenter_layout(floor_code, config, devices)

        return map_data

    def generate_3d_map(self, floor_code: str, devices: List[Dict]) -> Dict[str, Any]:
        """生成3D场景数据"""
        config = FLOOR_CONFIG.get(floor_code, {})

        map_data = {
            "floor": floor_code,
            "name": config.get("name", f"Floor {floor_code}"),
            "scene": {
                "width": config.get("width", 50),
                "depth": config.get("height", 40),
                "height": 4  # 层高
            },
            "camera": {
                "position": [25, 20, 35],
                "target": [25, 0, 20]
            },
            "objects": []
        }

        # 生成3D对象
        if floor_code == "B1":
            map_data["objects"] = self._generate_cooling_3d(devices)
        else:
            map_data["objects"] = self._generate_datacenter_3d(floor_code, config, devices)

        return map_data

    def _generate_cooling_layout(self, devices: List[Dict]) -> List[Dict]:
        """生成制冷机房2D布局"""
        elements = []

        # 冷水机组区域
        elements.append({
            "type": "zone",
            "id": "chiller_zone",
            "name": "冷水机组区",
            "x": 2, "y": 2, "width": 15, "height": 12,
            "color": "#0066cc"
        })

        # 冷却塔区域
        elements.append({
            "type": "zone",
            "id": "tower_zone",
            "name": "冷却塔区",
            "x": 20, "y": 2, "width": 15, "height": 12,
            "color": "#00aa66"
        })

        # 水泵区域
        elements.append({
            "type": "zone",
            "id": "pump_zone",
            "name": "水泵区",
            "x": 2, "y": 16, "width": 33, "height": 10,
            "color": "#6600cc"
        })

        # 添加设备
        chiller_x, tower_x, pump_x = 4, 22, 4
        for device in devices:
            device_type = device.get("device_type", "")
            if "chiller" in device_type.lower() or "冷水机" in device.get("name", ""):
                elements.append({
                    "type": "device",
                    "id": device.get("code", ""),
                    "name": device.get("name", ""),
                    "deviceType": "chiller",
                    "x": chiller_x, "y": 5,
                    "width": 4, "height": 6,
                    "status": device.get("status", "normal")
                })
                chiller_x += 5
            elif "tower" in device_type.lower() or "冷却塔" in device.get("name", ""):
                elements.append({
                    "type": "device",
                    "id": device.get("code", ""),
                    "name": device.get("name", ""),
                    "deviceType": "cooling_tower",
                    "x": tower_x, "y": 5,
                    "width": 4, "height": 6,
                    "status": device.get("status", "normal")
                })
                tower_x += 5
            elif "pump" in device_type.lower() or "水泵" in device.get("name", ""):
                elements.append({
                    "type": "device",
                    "id": device.get("code", ""),
                    "name": device.get("name", ""),
                    "deviceType": "pump",
                    "x": pump_x, "y": 18,
                    "width": 3, "height": 5,
                    "status": device.get("status", "normal")
                })
                pump_x += 4

        return elements

    def _generate_datacenter_layout(self, floor_code: str, config: Dict, devices: List[Dict]) -> List[Dict]:
        """生成数据中心机房2D布局"""
        elements = []
        rows = config.get("rows", 4)
        cols = config.get("cols", 5)
        cabinet_width = 2.5
        cabinet_height = 4
        aisle_width = 3

        # 机柜区域
        cabinet_idx = 0
        for row in range(rows):
            for col in range(cols):
                x = 5 + col * (cabinet_width + 1)
                y = 5 + row * (cabinet_height + aisle_width)

                # 查找对应机柜设备
                cabinet_device = None
                for d in devices:
                    if f"CAB-{floor_code}-{cabinet_idx+1:02d}" in d.get("code", ""):
                        cabinet_device = d
                        break

                elements.append({
                    "type": "cabinet",
                    "id": f"CAB-{floor_code}-{cabinet_idx+1:02d}",
                    "name": f"机柜{cabinet_idx+1}",
                    "x": x, "y": y,
                    "width": cabinet_width, "height": cabinet_height,
                    "status": cabinet_device.get("status", "normal") if cabinet_device else "normal",
                    "row": row + 1,
                    "col": col + 1
                })
                cabinet_idx += 1

                if cabinet_idx >= config.get("cabinets", 20):
                    break
            if cabinet_idx >= config.get("cabinets", 20):
                break

        # UPS区域
        elements.append({
            "type": "zone",
            "id": f"ups_zone_{floor_code}",
            "name": "UPS区",
            "x": config.get("width", 50) - 10, "y": 2,
            "width": 8, "height": 8,
            "color": "#cc6600"
        })

        # 空调区域
        elements.append({
            "type": "zone",
            "id": f"ac_zone_{floor_code}",
            "name": "精密空调区",
            "x": config.get("width", 50) - 10, "y": 12,
            "width": 8, "height": 10,
            "color": "#00cccc"
        })

        return elements

    def _generate_cooling_3d(self, devices: List[Dict]) -> List[Dict]:
        """生成制冷机房3D对象"""
        objects = []

        # 地板
        objects.append({
            "type": "floor",
            "position": [20, 0, 15],
            "size": [40, 0.1, 30],
            "color": "#1a3a5c"
        })

        # 冷水机组
        chiller_x = 5
        for i in range(3):
            objects.append({
                "type": "equipment",
                "id": f"chiller_{i+1}",
                "name": f"冷水机组{i+1}",
                "equipmentType": "chiller",
                "position": [chiller_x, 1.5, 8],
                "size": [4, 3, 6],
                "color": "#0066cc"
            })
            chiller_x += 6

        # 冷却塔
        tower_x = 25
        for i in range(2):
            objects.append({
                "type": "equipment",
                "id": f"tower_{i+1}",
                "name": f"冷却塔{i+1}",
                "equipmentType": "cooling_tower",
                "position": [tower_x, 2, 8],
                "size": [5, 4, 5],
                "color": "#00aa66"
            })
            tower_x += 7

        # 水泵
        pump_x = 5
        for i in range(4):
            objects.append({
                "type": "equipment",
                "id": f"pump_{i+1}",
                "name": f"冷冻水泵{i+1}",
                "equipmentType": "pump",
                "position": [pump_x, 0.75, 22],
                "size": [2, 1.5, 3],
                "color": "#6600cc"
            })
            pump_x += 5

        return objects

    def _generate_datacenter_3d(self, floor_code: str, config: Dict, devices: List[Dict]) -> List[Dict]:
        """生成数据中心3D对象"""
        objects = []
        width = config.get("width", 50)
        depth = config.get("height", 40)

        # 地板
        objects.append({
            "type": "floor",
            "position": [width/2, 0, depth/2],
            "size": [width, 0.1, depth],
            "color": config.get("color", "#1e4d2b")
        })

        # 机柜
        rows = config.get("rows", 4)
        cols = config.get("cols", 5)
        cabinet_idx = 0

        for row in range(rows):
            for col in range(cols):
                x = 5 + col * 4
                z = 5 + row * 8

                objects.append({
                    "type": "cabinet",
                    "id": f"CAB-{floor_code}-{cabinet_idx+1:02d}",
                    "name": f"机柜{cabinet_idx+1}",
                    "position": [x, 1.1, z],
                    "size": [0.6, 2.2, 1.0],
                    "color": "#333344",
                    "row": row + 1,
                    "col": col + 1
                })
                cabinet_idx += 1

                if cabinet_idx >= config.get("cabinets", 20):
                    break
            if cabinet_idx >= config.get("cabinets", 20):
                break

        # UPS设备
        objects.append({
            "type": "equipment",
            "id": f"UPS-{floor_code}-1",
            "name": "UPS主机",
            "equipmentType": "ups",
            "position": [width - 6, 1, 5],
            "size": [3, 2, 2],
            "color": "#cc6600"
        })

        # 精密空调
        ac_z = 15
        for i in range(2):
            objects.append({
                "type": "equipment",
                "id": f"AC-{floor_code}-{i+1}",
                "name": f"精密空调{i+1}",
                "equipmentType": "ac",
                "position": [width - 5, 1.5, ac_z],
                "size": [2, 3, 1.5],
                "color": "#00cccc"
            })
            ac_z += 5

        return objects
```

---

## Task 5: 创建楼层图API

**Files:**
- Create: `backend/app/api/v1/floor_map.py`
- Modify: `backend/app/api/v1/__init__.py`

**Step 1: 创建API路由**

```python
"""楼层图 API"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from pydantic import BaseModel

from ..deps import get_db, get_current_user
from ...models import FloorMap
from ...models.user import User
from ...schemas.common import ResponseModel

router = APIRouter()

class FloorMapResponse(BaseModel):
    """楼层图响应"""
    id: int
    floor_code: str
    floor_name: str
    map_type: str
    map_data: dict
    thumbnail: Optional[str] = None
    is_default: bool

    class Config:
        from_attributes = True

class FloorListResponse(BaseModel):
    """楼层列表响应"""
    floors: List[dict]

@router.get("/floors", response_model=ResponseModel[FloorListResponse], summary="获取楼层列表")
async def get_floors(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取所有楼层及其可用的图类型"""
    result = await db.execute(
        select(FloorMap.floor_code, FloorMap.floor_name, FloorMap.map_type)
        .distinct()
        .order_by(FloorMap.floor_code)
    )
    rows = result.fetchall()

    # 按楼层分组
    floor_dict = {}
    for row in rows:
        code = row[0]
        if code not in floor_dict:
            floor_dict[code] = {
                "floor_code": code,
                "floor_name": row[1],
                "map_types": []
            }
        floor_dict[code]["map_types"].append(row[2])

    return ResponseModel(data=FloorListResponse(floors=list(floor_dict.values())))

@router.get("/{floor_code}/{map_type}", response_model=ResponseModel[FloorMapResponse], summary="获取楼层图")
async def get_floor_map(
    floor_code: str,
    map_type: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取指定楼层的2D或3D图数据"""
    result = await db.execute(
        select(FloorMap).where(
            FloorMap.floor_code == floor_code,
            FloorMap.map_type == map_type
        )
    )
    floor_map = result.scalar_one_or_none()

    if not floor_map:
        raise HTTPException(status_code=404, detail=f"Floor map not found: {floor_code}/{map_type}")

    import json
    response = FloorMapResponse(
        id=floor_map.id,
        floor_code=floor_map.floor_code,
        floor_name=floor_map.floor_name,
        map_type=floor_map.map_type,
        map_data=json.loads(floor_map.map_data),
        thumbnail=floor_map.thumbnail,
        is_default=floor_map.is_default
    )

    return ResponseModel(data=response)
```

**Step 2: 注册路由**

在 `backend/app/api/v1/__init__.py` 添加：
```python
from .floor_map import router as floor_map_router
api_router.include_router(floor_map_router, prefix="/floor-map", tags=["楼层图"])
```

---

## Task 6: 集成楼层图到演示数据服务

**Files:**
- Modify: `backend/app/services/demo_data_service.py`

**Step 1: 导入楼层图生成器和模型**

在文件顶部添加：
```python
from .floor_map_generator import FloorMapGenerator, FLOOR_CONFIG
from ..models import FloorMap
```

**Step 2: 在 _clear_demo_data 中添加清理楼层图**

在删除其他数据后添加：
```python
await session.execute(delete(FloorMap))
```

**Step 3: 添加生成楼层图方法**

```python
async def _generate_floor_maps(self, progress_callback):
    """生成楼层平面图数据"""
    generator = FloorMapGenerator()

    async with async_session() as session:
        # 获取设备数据用于生成图
        for floor_code in ["B1", "F1", "F2", "F3"]:
            config = FLOOR_CONFIG.get(floor_code, {})

            # 模拟设备数据（实际应从数据库查询）
            devices = []

            # 生成2D图
            map_2d = generator.generate_2d_map(floor_code, devices)
            floor_map_2d = FloorMap(
                floor_code=floor_code,
                floor_name=config.get("name", f"Floor {floor_code}"),
                map_type="2d",
                map_data=json.dumps(map_2d, ensure_ascii=False),
                is_default=(floor_code == "F1")
            )
            session.add(floor_map_2d)

            # 生成3D图
            map_3d = generator.generate_3d_map(floor_code, devices)
            floor_map_3d = FloorMap(
                floor_code=floor_code,
                floor_name=config.get("name", f"Floor {floor_code}"),
                map_type="3d",
                map_data=json.dumps(map_3d, ensure_ascii=False),
                is_default=False
            )
            session.add(floor_map_3d)

        await session.commit()
        self._update_progress(92, "生成 8 张楼层图 (4层 x 2类型)", progress_callback)
```

**Step 4: 在 load_demo_data 中调用**

在 Phase 5 和 Phase 6 之间添加新阶段：
```python
# Phase 5.5: 生成楼层图 (88-92%)
self._update_progress(88, "生成楼层平面图...", progress_callback)
await self._generate_floor_maps(progress_callback)
```

---

## Task 7: 创建前端楼层图API模块

**Files:**
- Create: `frontend/src/api/modules/floorMap.ts`

**Step 1: 创建API模块**

```typescript
import request from '@/utils/request'

export interface FloorInfo {
  floor_code: string
  floor_name: string
  map_types: string[]
}

export interface FloorMapData {
  id: number
  floor_code: string
  floor_name: string
  map_type: string
  map_data: any
  thumbnail?: string
  is_default: boolean
}

// 获取楼层列表
export function getFloors() {
  return request.get<{ floors: FloorInfo[] }>('/v1/floor-map/floors')
}

// 获取楼层图数据
export function getFloorMap(floorCode: string, mapType: '2d' | '3d') {
  return request.get<FloorMapData>(`/v1/floor-map/${floorCode}/${mapType}`)
}
```

---

## Task 8: 创建大屏楼层选择器组件

**Files:**
- Create: `frontend/src/components/bigscreen/FloorSelector.vue`

**Step 1: 创建组件**

```vue
<template>
  <div class="floor-selector">
    <div class="selector-title">楼层选择</div>

    <div class="floor-buttons">
      <button
        v-for="floor in floors"
        :key="floor.floor_code"
        :class="['floor-btn', { active: currentFloor === floor.floor_code }]"
        @click="selectFloor(floor.floor_code)"
      >
        {{ floor.floor_code }}
        <span class="floor-name">{{ floor.floor_name }}</span>
      </button>
    </div>

    <div class="view-toggle">
      <button
        :class="['view-btn', { active: viewMode === '2d' }]"
        @click="setViewMode('2d')"
      >
        2D 平面图
      </button>
      <button
        :class="['view-btn', { active: viewMode === '3d' }]"
        @click="setViewMode('3d')"
      >
        3D 场景
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { getFloors, getFloorMap, type FloorInfo } from '@/api/modules/floorMap'

const props = defineProps<{
  modelValue?: string
  mode?: '2d' | '3d'
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', floor: string): void
  (e: 'update:mode', mode: '2d' | '3d'): void
  (e: 'floorChange', data: { floor: string, mode: '2d' | '3d', mapData: any }): void
}>()

const floors = ref<FloorInfo[]>([])
const currentFloor = ref(props.modelValue || 'F1')
const viewMode = ref<'2d' | '3d'>(props.mode || '3d')
const loading = ref(false)

onMounted(async () => {
  try {
    const res = await getFloors()
    floors.value = res.data?.floors || res.floors || []

    // 加载默认楼层
    await loadFloorMap()
  } catch (err) {
    console.error('Failed to load floors:', err)
  }
})

async function selectFloor(floorCode: string) {
  currentFloor.value = floorCode
  emit('update:modelValue', floorCode)
  await loadFloorMap()
}

async function setViewMode(mode: '2d' | '3d') {
  viewMode.value = mode
  emit('update:mode', mode)
  await loadFloorMap()
}

async function loadFloorMap() {
  if (loading.value) return
  loading.value = true

  try {
    const res = await getFloorMap(currentFloor.value, viewMode.value)
    const mapData = res.data?.map_data || res.map_data

    emit('floorChange', {
      floor: currentFloor.value,
      mode: viewMode.value,
      mapData
    })
  } catch (err) {
    console.error('Failed to load floor map:', err)
  } finally {
    loading.value = false
  }
}

watch(() => props.modelValue, (val) => {
  if (val && val !== currentFloor.value) {
    currentFloor.value = val
    loadFloorMap()
  }
})
</script>

<style scoped lang="scss">
.floor-selector {
  position: absolute;
  top: 80px;
  left: 20px;
  z-index: 100;
  background: rgba(0, 20, 40, 0.85);
  border: 1px solid rgba(0, 200, 255, 0.3);
  border-radius: 8px;
  padding: 12px;
  min-width: 120px;
}

.selector-title {
  color: #00ccff;
  font-size: 12px;
  margin-bottom: 10px;
  text-align: center;
  border-bottom: 1px solid rgba(0, 200, 255, 0.2);
  padding-bottom: 8px;
}

.floor-buttons {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 12px;
}

.floor-btn {
  background: rgba(0, 100, 150, 0.3);
  border: 1px solid rgba(0, 200, 255, 0.2);
  border-radius: 4px;
  color: #88ccff;
  padding: 8px 12px;
  cursor: pointer;
  transition: all 0.2s;
  text-align: left;

  .floor-name {
    display: block;
    font-size: 10px;
    color: #668899;
    margin-top: 2px;
  }

  &:hover {
    background: rgba(0, 150, 200, 0.4);
    border-color: rgba(0, 200, 255, 0.5);
  }

  &.active {
    background: rgba(0, 200, 255, 0.3);
    border-color: #00ccff;
    color: #ffffff;

    .floor-name {
      color: #aaddff;
    }
  }
}

.view-toggle {
  display: flex;
  gap: 4px;
  border-top: 1px solid rgba(0, 200, 255, 0.2);
  padding-top: 10px;
}

.view-btn {
  flex: 1;
  background: rgba(0, 100, 150, 0.3);
  border: 1px solid rgba(0, 200, 255, 0.2);
  border-radius: 4px;
  color: #88ccff;
  padding: 6px 8px;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.2s;

  &:hover {
    background: rgba(0, 150, 200, 0.4);
  }

  &.active {
    background: rgba(0, 200, 255, 0.3);
    border-color: #00ccff;
    color: #ffffff;
  }
}
</style>
```

---

## Task 9: 创建2D平面图渲染组件

**Files:**
- Create: `frontend/src/components/bigscreen/Floor2DView.vue`

**Step 1: 创建2D渲染组件**

```vue
<template>
  <div class="floor-2d-view" ref="containerRef">
    <canvas ref="canvasRef" @click="handleClick" @mousemove="handleHover"></canvas>

    <div v-if="hoveredElement" class="tooltip" :style="tooltipStyle">
      <div class="tooltip-title">{{ hoveredElement.name }}</div>
      <div class="tooltip-info">{{ hoveredElement.type }}</div>
      <div v-if="hoveredElement.status" :class="['status', hoveredElement.status]">
        {{ statusText(hoveredElement.status) }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, computed, onUnmounted } from 'vue'

interface MapElement {
  type: string
  id: string
  name: string
  x: number
  y: number
  width: number
  height: number
  color?: string
  status?: string
  deviceType?: string
}

interface MapData {
  floor: string
  name: string
  dimensions: { width: number; height: number }
  background: string
  elements: MapElement[]
}

const props = defineProps<{
  mapData: MapData | null
}>()

const emit = defineEmits<{
  (e: 'elementClick', element: MapElement): void
}>()

const containerRef = ref<HTMLDivElement>()
const canvasRef = ref<HTMLCanvasElement>()
const hoveredElement = ref<MapElement | null>(null)
const mousePos = ref({ x: 0, y: 0 })

const scale = ref(1)
const offsetX = ref(0)
const offsetY = ref(0)

const tooltipStyle = computed(() => ({
  left: `${mousePos.value.x + 15}px`,
  top: `${mousePos.value.y + 15}px`
}))

function statusText(status: string) {
  const map: Record<string, string> = {
    normal: '正常',
    warning: '告警',
    error: '故障',
    offline: '离线'
  }
  return map[status] || status
}

function draw() {
  const canvas = canvasRef.value
  const container = containerRef.value
  if (!canvas || !container || !props.mapData) return

  const ctx = canvas.getContext('2d')
  if (!ctx) return

  // 设置canvas尺寸
  const rect = container.getBoundingClientRect()
  canvas.width = rect.width
  canvas.height = rect.height

  const { dimensions, background, elements } = props.mapData

  // 计算缩放和偏移使地图居中
  const scaleX = (rect.width - 40) / dimensions.width
  const scaleY = (rect.height - 40) / dimensions.height
  scale.value = Math.min(scaleX, scaleY)
  offsetX.value = (rect.width - dimensions.width * scale.value) / 2
  offsetY.value = (rect.height - dimensions.height * scale.value) / 2

  // 清空画布
  ctx.fillStyle = background
  ctx.fillRect(0, 0, canvas.width, canvas.height)

  // 绘制网格
  ctx.strokeStyle = 'rgba(0, 200, 255, 0.1)'
  ctx.lineWidth = 1
  for (let x = 0; x <= dimensions.width; x += 5) {
    ctx.beginPath()
    ctx.moveTo(offsetX.value + x * scale.value, offsetY.value)
    ctx.lineTo(offsetX.value + x * scale.value, offsetY.value + dimensions.height * scale.value)
    ctx.stroke()
  }
  for (let y = 0; y <= dimensions.height; y += 5) {
    ctx.beginPath()
    ctx.moveTo(offsetX.value, offsetY.value + y * scale.value)
    ctx.lineTo(offsetX.value + dimensions.width * scale.value, offsetY.value + y * scale.value)
    ctx.stroke()
  }

  // 绘制元素
  for (const el of elements) {
    const x = offsetX.value + el.x * scale.value
    const y = offsetY.value + el.y * scale.value
    const w = el.width * scale.value
    const h = el.height * scale.value

    // 背景
    ctx.fillStyle = el.color || getTypeColor(el.type, el.status)
    ctx.fillRect(x, y, w, h)

    // 边框
    ctx.strokeStyle = el === hoveredElement.value ? '#00ffff' : 'rgba(0, 200, 255, 0.5)'
    ctx.lineWidth = el === hoveredElement.value ? 2 : 1
    ctx.strokeRect(x, y, w, h)

    // 标签
    if (w > 30 && h > 20) {
      ctx.fillStyle = '#ffffff'
      ctx.font = `${Math.max(10, Math.min(12, w / 5))}px sans-serif`
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText(el.name.substring(0, 6), x + w/2, y + h/2)
    }
  }

  // 绘制标题
  ctx.fillStyle = '#00ccff'
  ctx.font = '16px sans-serif'
  ctx.textAlign = 'left'
  ctx.fillText(props.mapData.name, 20, 30)
}

function getTypeColor(type: string, status?: string): string {
  if (status === 'error') return 'rgba(255, 50, 50, 0.6)'
  if (status === 'warning') return 'rgba(255, 200, 0, 0.6)'
  if (status === 'offline') return 'rgba(100, 100, 100, 0.6)'

  const colors: Record<string, string> = {
    zone: 'rgba(0, 100, 150, 0.4)',
    cabinet: 'rgba(50, 80, 120, 0.6)',
    device: 'rgba(0, 150, 100, 0.6)',
    equipment: 'rgba(100, 100, 200, 0.6)'
  }
  return colors[type] || 'rgba(50, 100, 150, 0.5)'
}

function getElementAt(clientX: number, clientY: number): MapElement | null {
  if (!props.mapData || !canvasRef.value) return null

  const rect = canvasRef.value.getBoundingClientRect()
  const x = (clientX - rect.left - offsetX.value) / scale.value
  const y = (clientY - rect.top - offsetY.value) / scale.value

  // 从后向前检查（后绘制的在上层）
  for (let i = props.mapData.elements.length - 1; i >= 0; i--) {
    const el = props.mapData.elements[i]
    if (x >= el.x && x <= el.x + el.width && y >= el.y && y <= el.y + el.height) {
      return el
    }
  }
  return null
}

function handleHover(e: MouseEvent) {
  mousePos.value = { x: e.clientX, y: e.clientY }
  const el = getElementAt(e.clientX, e.clientY)
  if (el !== hoveredElement.value) {
    hoveredElement.value = el
    draw()
  }
}

function handleClick(e: MouseEvent) {
  const el = getElementAt(e.clientX, e.clientY)
  if (el) {
    emit('elementClick', el)
  }
}

let resizeObserver: ResizeObserver | null = null

onMounted(() => {
  draw()

  if (containerRef.value) {
    resizeObserver = new ResizeObserver(() => draw())
    resizeObserver.observe(containerRef.value)
  }
})

onUnmounted(() => {
  resizeObserver?.disconnect()
})

watch(() => props.mapData, () => draw(), { deep: true })
</script>

<style scoped lang="scss">
.floor-2d-view {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;

  canvas {
    width: 100%;
    height: 100%;
    cursor: pointer;
  }
}

.tooltip {
  position: fixed;
  background: rgba(0, 20, 40, 0.95);
  border: 1px solid rgba(0, 200, 255, 0.5);
  border-radius: 6px;
  padding: 10px 14px;
  pointer-events: none;
  z-index: 1000;

  .tooltip-title {
    color: #ffffff;
    font-size: 14px;
    font-weight: 500;
    margin-bottom: 4px;
  }

  .tooltip-info {
    color: #88ccff;
    font-size: 12px;
  }

  .status {
    margin-top: 6px;
    padding: 2px 8px;
    border-radius: 3px;
    font-size: 11px;

    &.normal { background: rgba(0, 200, 100, 0.3); color: #00ff88; }
    &.warning { background: rgba(255, 200, 0, 0.3); color: #ffcc00; }
    &.error { background: rgba(255, 50, 50, 0.3); color: #ff5555; }
    &.offline { background: rgba(100, 100, 100, 0.3); color: #888888; }
  }
}
</style>
```

---

## Task 10: 集成楼层选择器到大屏

**Files:**
- Modify: `frontend/src/views/bigscreen/index.vue`

**Step 1: 导入新组件**

在 script setup 顶部添加：
```typescript
import FloorSelector from '@/components/bigscreen/FloorSelector.vue'
import Floor2DView from '@/components/bigscreen/Floor2DView.vue'
```

**Step 2: 添加状态变量**

```typescript
const currentFloor = ref('F1')
const viewMode = ref<'2d' | '3d'>('3d')
const floorMapData = ref<any>(null)
```

**Step 3: 添加处理函数**

```typescript
function handleFloorChange(data: { floor: string, mode: '2d' | '3d', mapData: any }) {
  currentFloor.value = data.floor
  viewMode.value = data.mode
  floorMapData.value = data.mapData

  // 如果是3D模式，更新Three.js场景
  if (data.mode === '3d' && data.mapData) {
    // 更新3D场景（可在ThreeScene中处理）
    console.log('Update 3D scene for floor:', data.floor)
  }
}

function handle2DElementClick(element: any) {
  console.log('2D element clicked:', element)
  // 可以打开设备详情面板
}
```

**Step 4: 在模板中添加组件**

在 `<div class="bigscreen-container">` 内添加：
```vue
<!-- 楼层选择器 -->
<FloorSelector
  v-model="currentFloor"
  :mode="viewMode"
  @update:mode="viewMode = $event"
  @floorChange="handleFloorChange"
/>

<!-- 2D视图（当选择2D模式时显示） -->
<Floor2DView
  v-if="viewMode === '2d'"
  :mapData="floorMapData"
  @elementClick="handle2DElementClick"
/>

<!-- 3D场景（当选择3D模式时显示） -->
<ThreeScene v-show="viewMode === '3d'" ... />
```

---

## Task 11: 更新文档

**Files:**
- Update: `findings.md`
- Update: `progress.md`

**Step 1: 更新 findings.md**

添加本次修改的详细记录

**Step 2: 更新 progress.md**

添加会话进度记录

**Step 3: 验证并提交**

Run: `npm run build`
Expected: 构建成功

---

## 验证清单

- [ ] 侧边栏无大屏菜单项
- [ ] 仪表盘大屏按钮功能正常
- [ ] 大屏面板点击可导航到主界面
- [ ] 楼层选择器显示B1/F1/F2/F3
- [ ] 2D/3D切换功能正常
- [ ] 2D平面图正确渲染设备布局
- [ ] 3D场景按楼层切换
- [ ] 加载演示数据时生成楼层图
- [ ] 文档已更新

---

## 回滚方案

如果出现问题：
1. 恢复 MainLayout.vue 菜单项
2. 恢复 bigscreen/index.vue handleNavigate 函数
3. 删除新增的楼层图相关文件
4. 清理 floor_maps 表数据
