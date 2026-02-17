# Story 4.1: 六大子系统仪表盘适配

Status: done

## Story

As a 运维工程师,
I want 在仪表盘上查看真实设备的实时数据,
So that 我可以掌握机房各子系统的实时运行状态。

## Acceptance Criteria (验收标准)

1. **AC-1: 实时数据 API Redis 优先** — GET `/api/v1/realtime` 和 `/api/v1/realtime/summary` 优先从 Redis 缓存读取数据，Redis 不可用时降级为数据库查询
2. **AC-2: 模拟器写入 Redis** — DataSimulator 在生成数据后同步写入 Redis 缓存（key: `point:{id}:latest`，TTL 60s），使 WebSocket 推送和 API 都能从 Redis 获取最新值
3. **AC-3: 数据源桥接服务** — 新增 `DataSourceBridge` 服务，将 DataSource/DataSourcePoint 采集的真实数据同步到 Point/PointRealtime 表，使现有仪表盘无需修改即可展示真实数据
4. **AC-4: 环境监控总览** — 将环境监控 overview 页面从占位符升级为真实数据展示（温湿度、水浸、烟雾传感器状态），数据来自 PointRealtime 按 device_type 筛选
5. **AC-5: 安防消防总览** — 将安防消防 overview 页面从占位符升级为真实数据展示（门禁状态、烟雾检测、干接点信号），数据来自 PointRealtime 按 device_type 筛选
6. **AC-6: 无数据占位显示** — 当 SIMULATION_ENABLED=false 且无真实数据时，仪表盘数值显示"--"而非 0 或空白
7. **AC-7: 后端测试** — 测试 Redis 优先读取逻辑和降级逻辑

## Tasks / Subtasks (任务分解)

- [ ] Task 1: 后端 — 实时数据 API Redis 优先读取 (AC: #1)
  - [ ] 1.1 修改 `backend/app/api/v1/realtime.py` 的 `get_all_realtime` 和 `get_realtime_summary`，优先从 Redis 读取
  - [ ] 1.2 Redis 不可用时降级为现有数据库查询逻辑

- [ ] Task 2: 后端 — 模拟器写入 Redis (AC: #2)
  - [ ] 2.1 修改 `backend/app/services/simulator.py` 的 `collect_and_save` 方法，在保存数据库后同步写入 Redis
  - [ ] 2.2 Redis key 格式: `point:{point_id}:latest`，value 为 JSON，TTL 60s

- [ ] Task 3: 后端 — 数据源桥接服务 (AC: #3)
  - [ ] 3.1 创建 `backend/app/services/datasource_bridge.py`
  - [ ] 3.2 实现 `sync_point_data(datasource_point_id, value, quality)` — 将 DataSourcePoint 数据写入对应的 PointRealtime 记录
  - [ ] 3.3 实现 `link_datasource_to_point(datasource_point_id, point_id)` — 建立 DataSourcePoint 到 Point 的映射关系

- [ ] Task 4: 前端 — 环境监控总览页面 (AC: #4)
  - [ ] 4.1 重写 `frontend/src/views/environment/overview.vue`，展示温湿度、水浸、烟雾传感器数据
  - [ ] 4.2 调用 `/api/v1/realtime/by-type/AI` 和 `/api/v1/realtime/by-type/DI` 按 device_type 筛选环境相关点位

- [ ] Task 5: 前端 — 安防消防总览页面 (AC: #5)
  - [ ] 5.1 重写 `frontend/src/views/security/overview.vue`，展示门禁、烟雾、干接点信号状态
  - [ ] 5.2 调用 realtime API 按 device_type 筛选安防相关点位

- [ ] Task 6: 前端 — 无数据占位显示 (AC: #6)
  - [ ] 6.1 修改 `frontend/src/views/dashboard/index.vue`，当数值为 null/undefined 时显示"--"
  - [ ] 6.2 修改环境和安防总览页面，无数据时显示"--"

- [ ] Task 7: 后端测试 (AC: #7)
  - [ ] 7.1 测试 Redis 优先读取 — mock Redis 有数据时返回缓存数据
  - [ ] 7.2 测试 Redis 降级 — mock Redis 不可用时回退到数据库查询
  - [ ] 7.3 测试数据源桥接 — sync_point_data 正确写入 PointRealtime
  - [ ] 7.4 测试模拟器 Redis 写入 — 模拟器生成数据后 Redis 有对应 key

- [ ] Task 8: 前端构建验证
  - [ ] 8.1 `npm run build` 构建成功

## Dev Notes (开发指南)

### 1. 文件位置

```
backend/app/api/v1/realtime.py           # 修改 — Redis 优先读取
backend/app/services/simulator.py        # 修改 — 写入 Redis
backend/app/services/datasource_bridge.py # 新建 — 数据源桥接
backend/tests/test_realtime_redis.py     # 新建 — 测试
frontend/src/views/environment/overview.vue  # 重写 — 环境监控
frontend/src/views/security/overview.vue     # 重写 — 安防消防
frontend/src/views/dashboard/index.vue       # 修改 — 无数据占位
```

### 2. 实时数据 API Redis 优先读取

在 `backend/app/api/v1/realtime.py` 的 `get_all_realtime` 中：

```python
from ...core.redis import redis_service

@router.get("", summary="获取所有点位实时数据")
async def get_all_realtime(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    # 1. 先尝试从 Redis 批量读取
    if redis_service and redis_service.is_available:
        try:
            # 获取所有启用点位的 ID
            point_query = select(Point).where(Point.is_enabled == True)
            point_result = await db.execute(point_query)
            points = point_result.scalars().all()

            point_ids = [p.id for p in points]
            point_map = {p.id: p for p in points}

            # 批量从 Redis 获取
            keys = [f"point:{pid}:latest" for pid in point_ids]
            cached_values = await redis_service.mget(keys)

            data = []
            missing_ids = []
            for i, pid in enumerate(point_ids):
                cached = cached_values[i] if i < len(cached_values) else None
                if cached:
                    import json
                    rt = json.loads(cached)
                    point = point_map[pid]
                    data.append(RealtimeData(
                        point_id=pid,
                        point_code=point.point_code,
                        point_name=point.point_name,
                        point_type=point.point_type,
                        device_type=point.device_type,
                        area_code=point.area_code,
                        value=rt.get("value"),
                        value_text=rt.get("value_text"),
                        unit=point.unit,
                        quality=rt.get("quality", 0),
                        status=rt.get("status", "normal"),
                        alarm_level=rt.get("alarm_level"),
                        updated_at=rt.get("updated_at")
                    ))
                else:
                    missing_ids.append(pid)

            # 对 Redis 中没有的点位，从数据库补充
            if missing_ids:
                db_result = await db.execute(
                    select(Point, PointRealtime).join(
                        PointRealtime, Point.id == PointRealtime.point_id
                    ).where(Point.id.in_(missing_ids))
                )
                for point, realtime in db_result.all():
                    data.append(RealtimeData(
                        point_id=point.id,
                        point_code=point.point_code,
                        point_name=point.point_name,
                        point_type=point.point_type,
                        device_type=point.device_type,
                        area_code=point.area_code,
                        value=realtime.value,
                        value_text=realtime.value_text,
                        unit=point.unit,
                        quality=realtime.quality,
                        status=realtime.status,
                        alarm_level=realtime.alarm_level,
                        updated_at=realtime.updated_at
                    ))

            return data
        except Exception:
            pass  # Redis 异常，降级到数据库

    # 2. 降级：从数据库读取（现有逻辑）
    query = select(Point, PointRealtime).join(
        PointRealtime, Point.id == PointRealtime.point_id
    ).where(Point.is_enabled == True)
    result = await db.execute(query)
    rows = result.all()
    # ... 现有逻辑不变
```

### 3. 模拟器写入 Redis

在 `backend/app/services/simulator.py` 的 `collect_and_save` 方法末尾添加 Redis 写入：

```python
import json
from ..core.redis import redis_service

async def collect_and_save(self, session, point):
    # ... 现有生成和保存逻辑 ...

    # 写入 Redis 缓存
    if redis_service and redis_service.is_available:
        try:
            cache_data = json.dumps({
                "value": new_value if point.point_type == "AI" else int(new_value),
                "value_text": value_text,
                "quality": quality,
                "status": status,
                "alarm_level": alarm_level,
                "updated_at": datetime.now().isoformat()
            })
            await redis_service.set(
                f"point:{point.id}:latest",
                cache_data,
                ttl=60
            )
        except Exception:
            pass  # Redis 写入失败不影响主流程

    return point_data
```

### 4. 数据源桥接服务

```python
# backend/app/services/datasource_bridge.py
"""数据源桥接服务 — 将 DataSourcePoint 数据同步到 Point/PointRealtime"""
import json
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from ..models.point import Point, PointRealtime
from ..models.gateway import DataSourcePoint
from ..core.redis import redis_service


async def sync_point_data(
    session: AsyncSession,
    point_id: int,
    value: float,
    quality: int = 0,
    status: str = "normal",
    alarm_level: Optional[str] = None,
):
    """将采集数据同步到 PointRealtime 表和 Redis"""
    now = datetime.now()

    # 更新 PointRealtime
    await session.execute(
        update(PointRealtime).where(PointRealtime.point_id == point_id).values(
            value=value,
            raw_value=value,
            quality=quality,
            status=status,
            alarm_level=alarm_level,
            updated_at=now,
        )
    )
    await session.commit()

    # 写入 Redis
    if redis_service and redis_service.is_available:
        try:
            cache_data = json.dumps({
                "value": value,
                "value_text": str(value),
                "quality": quality,
                "status": status,
                "alarm_level": alarm_level,
                "updated_at": now.isoformat(),
            })
            await redis_service.set(f"point:{point_id}:latest", cache_data, ttl=60)
        except Exception:
            pass
```

### 5. 环境监控总览页面

重写 `frontend/src/views/environment/overview.vue`：

```vue
<template>
  <div class="environment-overview">
    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #E6A23C;">
              <el-icon :size="22"><Sunny /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ avgTemp ?? '--' }}</div>
              <div class="stat-label">平均温度 (°C)</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #409EFF;">
              <el-icon :size="22"><Cloudy /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ avgHumidity ?? '--' }}</div>
              <div class="stat-label">平均湿度 (%)</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #67C23A;">
              <el-icon :size="22"><CircleCheck /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ normalCount }}</div>
              <div class="stat-label">正常传感器</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #F56C6C;">
              <el-icon :size="22"><Warning /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ alarmCount }}</div>
              <div class="stat-label">告警传感器</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 温湿度传感器列表 -->
    <el-card shadow="hover" style="margin-top: 16px;">
      <template #header>
        <div class="card-header">
          <span>环境传感器实时数据</span>
          <el-button type="primary" link @click="fetchData">刷新</el-button>
        </div>
      </template>
      <el-table :data="envPoints" stripe border>
        <el-table-column prop="point_name" label="传感器名称" min-width="180" />
        <el-table-column prop="device_type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag size="small">{{ getDeviceTypeLabel(row.device_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="当前值" width="120">
          <template #default="{ row }">
            <span>{{ row.value != null ? row.value : '--' }} {{ row.unit || '' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'normal' ? 'success' : row.status === 'alarm' ? 'danger' : 'info'" size="small">
              {{ row.status === 'normal' ? '正常' : row.status === 'alarm' ? '告警' : '离线' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="area_code" label="区域" width="80" />
        <el-table-column prop="updated_at" label="更新时间" min-width="170" />
      </el-table>
      <el-empty v-if="envPoints.length === 0" description="暂无环境传感器数据" />
    </el-card>
  </div>
</template>
```

脚本部分调用 `getAllRealtimeData()` 然后按 `device_type` 筛选 `TH`（温湿度）、`WATER`（水浸）、`SMOKE`（烟雾）类型的点位。

### 6. 安防消防总览页面

类似环境监控，重写 `frontend/src/views/security/overview.vue`，筛选 `device_type` 为 `DOOR`（门禁）、`SMOKE`（烟雾）、`IR`（红外）的点位。

### 7. 无数据占位显示

在 dashboard 的 `summary` 映射中，当后端返回 null 时前端显示 "--"：

```typescript
// 在 template 中使用 ?? '--' 运算符
{{ overview.temperature ?? '--' }}
```

### 8. 关键约束

- **Redis 降级**: Redis 不可用时必须无感降级到数据库查询，不能报错
- **模拟器兼容**: 模拟器写入 Redis 是增量改动，不影响现有数据库写入逻辑
- **桥接服务**: 仅提供基础框架，实际调用点在后续 Story（MQTT 数据处理链路）中集成
- **环境/安防页面**: 使用现有 realtime API，不新增后端端点
- **测试模式**: 使用 in-memory SQLite + mock Redis

### References

- [Source: api/v1/realtime.py] 现有实时数据 API
- [Source: services/simulator.py] 数据模拟器
- [Source: core/redis.py] Redis 服务
- [Source: services/cache_service.py] 缓存服务
- [Source: views/environment/overview.vue] 环境监控占位页
- [Source: views/security/overview.vue] 安防消防占位页

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

