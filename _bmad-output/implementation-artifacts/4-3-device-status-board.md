# Story 4.3: 设备状态看板

Status: done

## Story

As a 运维工程师,
I want 查看按区域和类型分组的设备状态看板,
So that 我可以快速了解哪些设备在线、离线或告警。

## Acceptance Criteria (验收标准)

1. **AC-1: 设备状态看板 API** — 新增 `GET /api/v1/devices/status-board` 端点，返回按区域和设备类型分组的设备状态统计（每组包含 online/offline/alarm/maintenance 计数和设备列表），支持 `area_code` 和 `device_type` 查询参数筛选
2. **AC-2: 设备在线状态 Redis 缓存** — 模拟器在更新设备关联点位数据时，同步写入 Redis 缓存 `device:{device_id}:online`（TTL 60s）；设备状态看板 API 优先从 Redis 判断设备在线状态，Redis 不可用时降级为数据库 Device.status 字段
3. **AC-3: 设备状态看板前端页面** — 新增设备状态看板页面 `/device-status`，按区域分组展示设备卡片，每张卡片显示设备名称、类型标签、在线/离线/告警状态指示灯，支持按区域和设备类型下拉筛选
4. **AC-4: 状态统计汇总** — 页面顶部显示全局统计卡片：总设备数、在线数、离线数、告警数
5. **AC-5: 路由注册** — 在 `frontend/src/router/index.ts` 中注册设备状态看板路由
6. **AC-6: 后端测试** — 测试设备状态看板 API 的分组统计和筛选功能

## Tasks / Subtasks (任务分解)

- [ ] Task 1: 后端 — 模拟器写入设备在线状态到 Redis (AC: #2)
  - [ ] 1.1 修改 `backend/app/services/simulator.py`，在 `collect_and_save` 方法中，当成功更新点位数据后，同步写入 `device:{device_id}:online` 到 Redis（TTL 60s，value 为时间戳）
  - [ ] 1.2 需要从 Point 获取 device_id（Point.device_id 字段）

- [ ] Task 2: 后端 — 设备状态看板 API (AC: #1, #2)
  - [ ] 2.1 在 `backend/app/api/v1/device.py` 新增 `GET /status-board` 端点（放在 `/status-summary` 之后、`/{device_id}` 之前）
  - [ ] 2.2 查询所有启用设备，按 area_code 和 device_type 分组
  - [ ] 2.3 对每台设备，优先从 Redis `device:{device_id}:online` 判断在线状态（key 存在 = 在线），Redis 不可用时使用 Device.status 字段
  - [ ] 2.4 支持 `area_code` 和 `device_type` 可选查询参数筛选
  - [ ] 2.5 返回格式：`{ summary: { total, online, offline, alarm, maintenance }, groups: [{ area_code, device_type, devices: [...], stats: { online, offline, alarm } }] }`

- [ ] Task 3: 前端 — 设备状态看板页面 (AC: #3, #4)
  - [ ] 3.1 创建 `frontend/src/views/device-status/index.vue`
  - [ ] 3.2 顶部统计卡片行：总设备数、在线数（绿色）、离线数（红色）、告警数（橙色）
  - [ ] 3.3 筛选栏：区域下拉（A1/A2/B1/F1/F2/F3 + 全部）、设备类型下拉（UPS/AC/PDU/TH/DOOR/SMOKE/WATER + 全部）
  - [ ] 3.4 按区域分组展示设备卡片网格，每张卡片包含：设备名称、类型 el-tag、状态指示圆点（绿=在线、红=离线、橙=告警、灰=维护）
  - [ ] 3.5 点击设备卡片跳转到设备详情页 `/device-manage/detail/{id}`（复用 Story 4.2 的详情页）
  - [ ] 3.6 自动刷新（30s 间隔），onUnmounted 清除定时器

- [ ] Task 4: 前端 — API 扩展 + 路由注册 (AC: #5)
  - [ ] 4.1 在 `frontend/src/api/modules/device.ts` 新增 `getDeviceStatusBoard(params?)` 函数和接口
  - [ ] 4.2 在 `frontend/src/router/index.ts` 注册路由 `device-status`

- [ ] Task 5: 后端测试 (AC: #6)
  - [ ] 5.1 测试状态看板 API — 返回正确的分组统计
  - [ ] 5.2 测试状态看板 API — area_code 筛选
  - [ ] 5.3 测试状态看板 API — device_type 筛选
  - [ ] 5.4 测试状态看板 API — Redis 在线状态判断（mock Redis）

- [ ] Task 6: 前端构建验证
  - [ ] 6.1 `npm run build` 构建成功

## Dev Notes (开发指南)

### 1. 文件位置

```
backend/app/api/v1/device.py                  # 修改 — 新增 status-board 端点
backend/app/services/simulator.py             # 修改 — 写入设备在线状态到 Redis
backend/tests/test_device_status_board.py     # 新建 — 测试
frontend/src/views/device-status/index.vue    # 新建 — 设备状态看板页面
frontend/src/api/modules/device.ts            # 修改 — 新增 API 函数
frontend/src/router/index.ts                  # 修改 — 新增路由
```

### 2. 模拟器写入设备在线状态

在 `backend/app/services/simulator.py` 的 `collect_and_save` 方法中，在写入点位 Redis 缓存之后，额外写入设备在线状态：

```python
# 写入设备在线状态到 Redis
if redis_service and redis_service.is_available and point.device_id:
    try:
        await redis_service.set(
            f"device:{point.device_id}:online",
            datetime.now().isoformat(),
            ttl=60
        )
    except Exception:
        pass
```

### 3. 设备状态看板 API

```python
@router.get("/status-board", summary="获取设备状态看板")
async def get_status_board(
    area_code: Optional[str] = Query(None, description="区域代码"),
    device_type: Optional[str] = Query(None, description="设备类型"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    query = select(Device).where(Device.is_enabled == True)
    if area_code:
        query = query.where(Device.area_code == area_code)
    if device_type:
        query = query.where(Device.device_type == device_type)

    result = await db.execute(query.order_by(Device.area_code, Device.device_type))
    devices = result.scalars().all()

    # 批量检查 Redis 在线状态
    online_map = {}
    if redis_service and redis_service.is_available:
        try:
            keys = [f"device:{d.id}:online" for d in devices]
            values = await redis_service.mget(keys)
            for i, d in enumerate(devices):
                online_map[d.id] = values[i] is not None if i < len(values) else False
        except Exception:
            pass  # Redis 不可用，使用数据库状态

    # 分组
    groups = {}
    summary = {"total": 0, "online": 0, "offline": 0, "alarm": 0, "maintenance": 0}
    for d in devices:
        # 确定在线状态
        if d.id in online_map:
            effective_status = "online" if online_map[d.id] else d.status
        else:
            effective_status = d.status

        summary["total"] += 1
        summary[effective_status] = summary.get(effective_status, 0) + 1

        key = f"{d.area_code}_{d.device_type}"
        if key not in groups:
            groups[key] = {
                "area_code": d.area_code,
                "device_type": d.device_type,
                "devices": [],
                "stats": {"online": 0, "offline": 0, "alarm": 0, "maintenance": 0}
            }
        groups[key]["devices"].append({
            "id": d.id,
            "device_code": d.device_code,
            "device_name": d.device_name,
            "status": effective_status,
        })
        groups[key]["stats"][effective_status] = groups[key]["stats"].get(effective_status, 0) + 1

    return {
        "summary": summary,
        "groups": list(groups.values())
    }
```

### 4. 前端设备状态看板页面

使用 el-card 网格布局，按区域分组：

```vue
<template>
  <div class="device-status-page">
    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :span="6" v-for="stat in statCards" :key="stat.label">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value" :style="{ color: stat.color }">{{ stat.value }}</div>
          <div class="stat-label">{{ stat.label }}</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 筛选栏 -->
    <el-card shadow="hover" style="margin-bottom: 16px;">
      <el-form :inline="true">
        <el-form-item label="区域">
          <el-select v-model="filters.area_code" placeholder="全部区域" clearable @change="loadData">
            <el-option v-for="a in areaOptions" :key="a" :label="a" :value="a" />
          </el-select>
        </el-form-item>
        <el-form-item label="设备类型">
          <el-select v-model="filters.device_type" placeholder="全部类型" clearable @change="loadData">
            <el-option v-for="t in typeOptions" :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 按区域分组的设备卡片 -->
    <div v-for="group in groups" :key="`${group.area_code}_${group.device_type}`" class="device-group">
      <h4>{{ group.area_code }} 区 — {{ group.device_type }}</h4>
      <el-row :gutter="12">
        <el-col :xs="12" :sm="8" :md="6" :lg="4" v-for="device in group.devices" :key="device.id">
          <el-card shadow="hover" class="device-card" @click="goDetail(device.id)">
            <div class="device-status-dot" :class="device.status"></div>
            <div class="device-name">{{ device.device_name }}</div>
            <el-tag size="small">{{ group.device_type }}</el-tag>
          </el-card>
        </el-col>
      </el-row>
    </div>
  </div>
</template>
```

### 5. 路由注册

```typescript
{
  path: 'device-status',
  name: 'DeviceStatus',
  component: () => import('@/views/device-status/index.vue'),
  meta: { title: '设备状态看板', icon: 'Odometer' }
}
```

### 6. 关键约束

- **Redis 降级**: Redis 不可用时使用数据库 Device.status 字段，不报错
- **设备在线判断**: Redis key `device:{id}:online` 存在 = 在线（TTL 60s 自动过期 = 离线）
- **自动导入**: Vue API 和 Vue Router API 无需手动 import
- **测试模式**: 使用 in-memory SQLite + mock Redis
- **复用详情页**: 点击设备卡片跳转到 Story 4.2 的 `/device-manage/detail/{id}`

### References

- [Source: api/v1/device.py] 现有设备 API（GET /status-summary, GET /tree）
- [Source: services/simulator.py] 数据模拟器（已有 Redis 写入逻辑）
- [Source: core/redis.py] Redis 服务（mget 批量读取）
- [Source: views/device-manage/index.vue] 设备管理列表页（UI 参考）
- [Source: api/modules/device.ts] 前端设备 API

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

