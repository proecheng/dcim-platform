# Story 33.3: 前端 VPP 集成状态监控

Status: done

## Story

As a 系统管理员,
I want 在前端查看 VPP 集成状态和指令执行历史,
So that 我能监控数据中心参与虚拟电厂的运行情况。

## 依赖

- Story 33.1（VPP 可调容量上报）— done
- Story 33.2（VPP 调控指令接收与执行）— done

## Acceptance Criteria

1. Given VPP 接口已上线
   When 进入 VPP 监控页面
   Then 显示 VPP 连接状态（在线/离线/异常）
   And 状态通过调用 `GET /api/v1/precool/vpp/capacity` 判断：成功=在线，异常=异常，超时=离线

2. Given VPP 监控页面已加载
   When 查看可调容量区域
   Then 显示当前可调容量仪表盘（向下可调 + 向上可调，双仪表盘）
   And 仪表盘使用现有 GaugeChart 组件，单位 kW
   And 同时显示热功率和电功率数值

3. Given VPP 监控页面已加载
   When 查看指令执行列表
   Then 显示最近指令执行列表（时间、类型、状态、目标功率、实际调控量）
   And 支持分页查询（默认 20 条/页）
   And 通过新增 `GET /api/v1/precool/vpp/dispatches` 端点获取数据

4. Given VPP 监控页面已加载
   When 查看统计区域
   Then 显示日/月累计参与需求响应统计
   And 统计项：参与次数、总调控量(kWh)、总节省电费(元)
   And 通过新增 `GET /api/v1/precool/vpp/statistics` 端点获取数据

5. Given 所有新增后端端点
   When 运行测试
   Then 单元测试全部通过

6. Given 所有前端代码
   When TypeScript 编译
   Then 无类型错误

## Tasks / Subtasks

- [ ] Task 1: 后端 — VPP 指令查询端点 (AC: #3, #5)
  - [ ] 1.1 在 `backend/app/api/v1/precool.py` 追加 `GET /vpp/dispatches` 端点
  - [ ] 1.2 在 `backend/app/schemas/precool.py` 追加 `VppDispatchListItem` schema

- [ ] Task 2: 后端 — VPP 统计端点 (AC: #4, #5)
  - [ ] 2.1 在 `backend/app/services/precool/vpp_dispatch.py` 追加 `get_statistics()` 方法
  - [ ] 2.2 在 `backend/app/api/v1/precool.py` 追加 `GET /vpp/statistics` 端点
  - [ ] 2.3 在 `backend/app/schemas/precool.py` 追加 `VppStatisticsResponse` schema

- [ ] Task 3: 后端测试 (AC: #5)
  - [ ] 3.1 在 `backend/tests/api/test_vpp_dispatch.py` 追加 dispatches 列表和 statistics 端点测试

- [ ] Task 4: 前端 API 模块 (AC: #1, #2, #3, #4)
  - [ ] 4.1 在 `frontend/src/api/modules/precool.ts` 追加 VPP 监控相关 API 调用

- [ ] Task 5: 前端 VPP 监控页面 (AC: #1, #2, #3, #4, #6)
  - [ ] 5.1 新建 `frontend/src/views/energy/shift/VppMonitorView.vue`
  - [ ] 5.2 路由注册：在 `frontend/src/router/index.ts` 的 `/energy/shift` 子路由追加 `vpp-monitor`

## Dev Notes

### 后端新增端点

#### GET /vpp/dispatches — 指令执行列表

在 `precool.py` 追加。**与现有 VPP 端点一样需要部署阶段 4 门控。** 但此端点面向内部管理员，使用 JWT 认证（不是 API Key）。

```python
@router.get("/vpp/dispatches", summary="查询 VPP 调控指令列表")
async def list_vpp_dispatches(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str = Query(None),
    _=Depends(require_role(["admin", "operator"])),
):
    """查询 VPP 调控指令历史（JWT 认证，admin/operator 可访问）"""
    try:
        from ...services.precool.vpp_dispatch import vpp_dispatch_service
        result = await vpp_dispatch_service.list_dispatches(page, page_size, status)
        return {"code": 200, "message": "success", "data": result}
    except Exception as e:
        logger.error(f"查询 VPP 调控指令列表失败: {e}", exc_info=True)
        return {"code": 500, "message": f"查询失败: {e}", "data": None}
```

**⚠️ 注意：** 此端点使用 `Depends(require_role(...))` JWT 认证，不是 VPP API Key 认证。面向内部管理界面。

**⚠️ 部署阶段门控：** 此端点不需要阶段 4 门控（管理员应该在任何阶段都能查看历史记录）。

#### GET /vpp/statistics — 需求响应统计

```python
@router.get("/vpp/statistics", summary="查询 VPP 需求响应统计")
async def get_vpp_statistics(
    _=Depends(require_role(["admin", "operator"])),
):
    """查询 VPP 需求响应统计（日/月汇总）"""
    try:
        from ...services.precool.vpp_dispatch import vpp_dispatch_service
        result = await vpp_dispatch_service.get_statistics()
        return {"code": 200, "message": "success", "data": result}
    except Exception as e:
        logger.error(f"查询 VPP 统计失败: {e}", exc_info=True)
        return {"code": 500, "message": f"查询失败: {e}", "data": None}
```

### VppDispatchService 新增方法

在 `backend/app/services/precool/vpp_dispatch.py` 追加：

```python
async def list_dispatches(self, page: int = 1, page_size: int = 20, status: str = None) -> dict:
    """查询 VPP 调控指令列表（分页）"""
    async with async_session() as session:
        query = select(VppDispatch).order_by(VppDispatch.created_at.desc())
        if status:
            query = query.where(VppDispatch.status == status)

        # 总数
        count_query = select(func.count()).select_from(VppDispatch)
        if status:
            count_query = count_query.where(VppDispatch.status == status)
        total_result = await session.execute(count_query)
        total = total_result.scalar() or 0

        # 分页
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await session.execute(query)
        dispatches = result.scalars().all()

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [self._build_response(d) for d in dispatches],
        }

async def get_statistics(self) -> dict:
    """查询 VPP 需求响应统计（日/月）"""
    async with async_session() as session:
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # 日统计
        daily_result = await session.execute(
            select(
                func.count().label("count"),
                func.sum(VppDispatch.accepted_power_kw).label("total_power"),
            ).where(
                VppDispatch.status == "accepted",
                VppDispatch.created_at >= today_start,
            )
        )
        daily = daily_result.first()

        # 月统计
        monthly_result = await session.execute(
            select(
                func.count().label("count"),
                func.sum(VppDispatch.accepted_power_kw).label("total_power"),
            ).where(
                VppDispatch.status == "accepted",
                VppDispatch.created_at >= month_start,
            )
        )
        monthly = monthly_result.first()

        # 估算节省电费（调控功率 × 持续时间 × 峰谷价差）
        # 峰谷价差约 0.5 元/kWh（简化估算）
        PRICE_DIFF = 0.5

        daily_count = daily.count if daily else 0
        daily_power = float(daily.total_power or 0)
        monthly_count = monthly.count if monthly else 0
        monthly_power = float(monthly.total_power or 0)

        return {
            "daily": {
                "count": daily_count,
                "total_power_kw": round(daily_power, 1),
                "estimated_savings_yuan": round(daily_power * PRICE_DIFF, 2),
            },
            "monthly": {
                "count": monthly_count,
                "total_power_kw": round(monthly_power, 1),
                "estimated_savings_yuan": round(monthly_power * PRICE_DIFF, 2),
            },
        }
```

**⚠️ 导入约束：** `vpp_dispatch.py` 已有 `from datetime import datetime` 和 `from sqlalchemy import select`。**但没有 `func`，需要追加：** `from sqlalchemy.sql import func`（用于 `func.count()` 和 `func.sum()`）。

**⚠️ _build_response 需要增加 created_at：** 现有 `_build_response` 方法不包含 `created_at` 字段。需要修改该方法，添加 `"created_at": dispatch.created_at.isoformat() if dispatch.created_at else None`（DateTime → ISO 字符串，确保 JSON 可序列化）。前端指令列表需要显示时间。

### Schema 追加

在 `backend/app/schemas/precool.py` 追加：

```python
class VppDispatchListItem(BaseModel):
    dispatch_id: str
    command_type: str
    target_power_kw: float
    duration_minutes: int
    status: str
    reject_reason: Optional[str] = None
    max_adjustable_kw: Optional[float] = None
    accepted_power_kw: Optional[float] = None
    aborted_schedule_id: Optional[int] = None

class VppStatisticsResponse(BaseModel):
    daily: dict  # {count, total_power_kw, estimated_savings_yuan}
    monthly: dict  # {count, total_power_kw, estimated_savings_yuan}
```

### 前端 API 模块追加

在 `frontend/src/api/modules/precool.ts` 文件末尾追加：

```typescript
// ==================== VPP 监控 (Story 33.3) ====================

/** 查询 VPP 可调容量 */
export function getVppCapacity() {
  return request.get<{ code: number; message: string; data: any }>('/v1/precool/vpp/capacity')
}

/** 查询 VPP 调控指令列表 */
export function getVppDispatches(params?: { page?: number; page_size?: number; status?: string }) {
  return request.get<{ code: number; message: string; data: any }>('/v1/precool/vpp/dispatches', { params })
}

/** 查询 VPP 需求响应统计 */
export function getVppStatistics() {
  return request.get<{ code: number; message: string; data: any }>('/v1/precool/vpp/statistics')
}
```

**⚠️ 请求模式：** 与 precool.ts 现有函数一致，使用 `request.get<{ code: number; message: string; data: any }>`。`request` 已在文件顶部导入（`import request from '@/api/request'`）。

### 前端 VppMonitorView.vue 页面

新建 `frontend/src/views/energy/shift/VppMonitorView.vue`，参照 CoolingLinkageMonitor.vue 布局模式：

**页面结构：**
1. **页头** — 返回按钮 + "VPP 集成状态监控" 标题
2. **连接状态卡片** — 显示在线/离线/异常状态 + 最后更新时间
3. **统计卡片行** (4 列 el-col) — 日参与次数、日调控量、月参与次数、月调控量
4. **可调容量仪表盘** (2 列) — 向下可调 GaugeChart + 向上可调 GaugeChart
5. **指令执行列表** — el-table 分页表格

**⚠️ 组件复用：**
- 仪表盘使用 `@/components/charts/GaugeChart.vue`（已有，props: value/title/unit/min/max/colors/height）
- 不需要新建 `VppCapacityGauge.vue` 组件（Epic 建议的独立组件不必要，直接用 GaugeChart 即可）
- 统计卡片使用 `el-statistic` 或自定义卡片（参照 ShiftDashboard.vue 模式）

**⚠️ 自动刷新：** 使用 `setInterval` 每 30 秒刷新容量和状态数据。`onUnmounted` 中清除定时器。

**⚠️ 不使用 Pinia Store：** 此页面数据仅在页面内使用，无需全局状态，直接在组件内管理。

```vue
<template>
  <div class="vpp-monitor">
    <!-- 页头（与 CoolingLinkageMonitor.vue 一致） -->
    <el-page-header @back="$router.back()" title="返回">
      <template #content>
        <span>VPP 集成状态监控</span>
      </template>
    </el-page-header>

    <!-- 连接状态 -->
    <el-card shadow="hover" class="status-card">
      <div class="connection-status">
        <el-tag :type="connectionTagType" size="large">{{ connectionStatusText }}</el-tag>
        <span class="last-update">最后更新: {{ lastUpdateTime }}</span>
      </div>
    </el-card>

    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :span="6" v-for="stat in statCards" :key="stat.label">
        <el-card shadow="hover">
          <div class="stat-card">
            <div class="stat-value">{{ stat.value }}</div>
            <div class="stat-label">{{ stat.label }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 可调容量仪表盘 -->
    <el-row :gutter="16">
      <el-col :span="12">
        <el-card header="向下可调容量（削峰）" shadow="hover">
          <GaugeChart :value="downCapacity" title="向下可调" unit="kW" :min="0" :max="maxGauge" height="280px" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card header="向上可调容量（填谷）" shadow="hover">
          <GaugeChart :value="upCapacity" title="向上可调" unit="kW" :min="0" :max="maxGauge" height="280px" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 指令执行列表 -->
    <el-card header="指令执行记录" shadow="hover" style="margin-top: 16px">
      <el-table :data="dispatches" v-loading="tableLoading" stripe>
        <el-table-column prop="created_at" label="时间" width="180" />
        <el-table-column prop="command_type" label="类型" width="120">
          <template #default="{ row }">
            <el-tag :type="row.command_type === 'down_adjust' ? 'warning' : 'success'" size="small">
              {{ row.command_type === 'down_adjust' ? '削峰' : '填谷' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="target_power_kw" label="目标功率(kW)" width="130" />
        <el-table-column prop="accepted_power_kw" label="实际调控(kW)" width="130" />
        <el-table-column prop="duration_minutes" label="持续时间(分)" width="130" />
        <el-table-column prop="reject_reason" label="备注" show-overflow-tooltip />
      </el-table>
      <el-pagination
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="totalDispatches"
        layout="total, prev, pager, next"
        @current-change="fetchDispatches"
        style="margin-top: 16px; justify-content: flex-end"
      />
    </el-card>
  </div>
</template>
```

**⚠️ 自动导入：** Vue API（ref, computed, onMounted, onUnmounted）和 Element Plus 组件（ElCard, ElRow, ElCol, ElTable, ElTag, ElPagination 等）由 unplugin-auto-import 自动导入，无需手动 import。

**⚠️ 手动导入需要：**
- `import GaugeChart from '@/components/charts/GaugeChart.vue'`
- `import { getVppCapacity, getVppDispatches, getVppStatistics } from '@/api/modules/precool'`
- 不需要导入 ArrowLeft 图标（el-page-header 组件自带返回按钮）

### 路由注册

在 `frontend/src/router/index.ts` 的 `/energy/shift` 子路由数组中追加：

```typescript
{
  path: 'vpp-monitor',
  name: 'VppMonitor',
  component: () => import('@/views/energy/shift/VppMonitorView.vue'),
  meta: { title: 'VPP 集成监控', icon: 'Connection' },
},
```

**⚠️ 位置：** 追加在 `deployment` 路由之后（约 line 148）。与 precool-schedule、deployment 等同级。

**⚠️ 不要放在 `/vpp/analysis` 下：** VPP 分析和 VPP 监控是不同功能。分析是 VPP 方案评估，监控是实时运行状态。监控页面属于预冷系统的运行监控范畴，放在 `/energy/shift/vpp-monitor`。

### 后端测试追加

在 `backend/tests/api/test_vpp_dispatch.py` 追加新测试类：

```python
@pytest.mark.asyncio
class TestVppDispatchListAPI:
    """GET /vpp/dispatches 端点测试"""

    async def test_list_dispatches_success(self, client, admin_token):
        """管理员可查询指令列表"""
        with patch(
            "app.services.precool.vpp_dispatch.vpp_dispatch_service.list_dispatches",
            new_callable=AsyncMock,
            return_value={"total": 0, "page": 1, "page_size": 20, "items": []},
        ):
            resp = await client.get(
                "/api/v1/precool/vpp/dispatches",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        body = resp.json()
        assert body["code"] == 200


@pytest.mark.asyncio
class TestVppStatisticsAPI:
    """GET /vpp/statistics 端点测试"""

    async def test_statistics_success(self, client, admin_token):
        """管理员可查询统计数据"""
        with patch(
            "app.services.precool.vpp_dispatch.vpp_dispatch_service.get_statistics",
            new_callable=AsyncMock,
            return_value={
                "daily": {"count": 3, "total_power_kw": 90.0, "estimated_savings_yuan": 45.0},
                "monthly": {"count": 25, "total_power_kw": 750.0, "estimated_savings_yuan": 375.0},
            },
        ):
            resp = await client.get(
                "/api/v1/precool/vpp/statistics",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        body = resp.json()
        assert body["code"] == 200
        assert body["data"]["daily"]["count"] == 3
```

**⚠️ 认证模式：** 新增的 GET 端点使用 JWT 认证（与 POST /vpp/dispatch 的 API Key 认证不同）。conftest.py 有 `admin_token` fixture 和 `auth_headers(token)` 辅助函数。但现有 test_vpp_dispatch.py 文件只用了 VPP API Key 认证。新增测试类需要引入 `admin_token` fixture，使用方式：`headers={"Authorization": f"Bearer {admin_token}"}`。

**⚠️ 替代方案：** 如果 `admin_token` fixture 导致复杂依赖问题，可以直接 patch `require_role` 依赖返回固定用户，避免数据库交互。

### 关键约束

- **dict 返回模式：** 后端端点与 precool.py 现有模式一致，返回 `{"code": N, "message": "...", "data": T}`
- **JWT 认证：** 新增的 GET 端点面向内部管理员，使用 `Depends(require_role(["admin", "operator"]))`
- **不需要阶段 4 门控：** dispatches 和 statistics 端点是历史查询，任何阶段都应可用
- **GaugeChart 复用：** 使用已有仪表盘组件，不新建独立组件
- **页面位置：** `/energy/shift/vpp-monitor`，与预冷系统其他页面同级
- **自动刷新：** 容量和状态每 30 秒刷新，列表手动刷新
- **VppDispatch 模型已有 created_at 字段：** 无需新增字段
- **`func.count()` 和 `func.sum()` 导入：** vpp_dispatch.py 已有 `from sqlalchemy.sql import func`

### Project Structure Notes

- **新建文件:** `frontend/src/views/energy/shift/VppMonitorView.vue` — VPP 监控页面
- **修改文件:** `frontend/src/api/modules/precool.ts` — 追加 3 个 VPP API 调用
- **修改文件:** `frontend/src/router/index.ts` — 追加 vpp-monitor 路由
- **修改文件:** `backend/app/api/v1/precool.py` — 追加 2 个 GET 端点
- **修改文件:** `backend/app/services/precool/vpp_dispatch.py` — 追加 list_dispatches/get_statistics 方法
- **修改文件:** `backend/app/schemas/precool.py` — 追加 VppDispatchListItem/VppStatisticsResponse
- **修改文件:** `backend/tests/api/test_vpp_dispatch.py` — 追加端点测试

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Story 33.3]
- [Source: _bmad-output/planning-artifacts/architecture.md — Section 21.5 API 设计]
- [Source: backend/app/api/v1/precool.py — 现有端点模式]
- [Source: backend/app/services/precool/vpp_dispatch.py — VppDispatchService]
- [Source: backend/app/services/precool/vpp_capacity.py — VppCapacityService]
- [Source: frontend/src/api/modules/precool.ts — 前端 API 模块]
- [Source: frontend/src/components/charts/GaugeChart.vue — 仪表盘组件]
- [Source: frontend/src/views/energy/shift/CoolingLinkageMonitor.vue — 监控页面布局参考]
- [Source: frontend/src/views/energy/shift/ShiftDashboard.vue — 统计卡片参考]
- [Source: frontend/src/router/index.ts — 路由配置]
