# Story 4.4: 通信中断检测与展示

Status: done

## Story

As a 运维工程师,
I want 系统自动检测数据源通信中断并显示影响范围,
So that 我可以快速判断是设备故障还是网络故障。

## Acceptance Criteria (验收标准)

1. **AC-1: 通信中断检测服务** — 新增后端服务 `communication_monitor.py`，定期检查所有启用数据源的 `consecutive_failures` 字段，当 `consecutive_failures >= retry_max_failures`（默认 5）时标记数据源状态为 `interrupted`，并计算中断时长（当前时间 - last_communication）
2. **AC-2: 数据源通信状态 API** — 新增 `GET /api/v1/datasources/communication-status` 端点，返回所有数据源的通信状态列表，包含：数据源名称、协议类型、连接状态（connected/disconnected/interrupted）、最后通信时间、连续失败次数、中断时长、受影响点位数
3. **AC-3: 受影响点位标记** — 当数据源被标记为 `interrupted` 时，其关联的 DataSourcePoint 对应的 PointRealtime 记录的 `quality` 字段更新为 `2`（坏/不可靠）
4. **AC-4: 通信状态前端展示** — 在数据源管理页面 (`datasource/index.vue`) 新增通信状态列，显示连接状态标签（绿=connected、黄=disconnected、红=interrupted）、最后通信时间、连续失败次数
5. **AC-5: 通信中断影响范围面板** — 在数据源管理页面，当数据源状态为 `interrupted` 时，可展开查看影响范围：受影响点位数、受影响设备数、中断时长
6. **AC-6: 后端测试** — 测试通信中断检测逻辑和通信状态 API

## Tasks / Subtasks (任务分解)

- [ ] Task 1: 后端 — 通信中断检测服务 (AC: #1, #3)
  - [ ] 1.1 创建 `backend/app/services/communication_monitor.py`
  - [ ] 1.2 实现 `check_communication_status(session)` 函数：查询所有启用数据源，检查 `consecutive_failures >= retry_max_failures`，将符合条件的数据源 status 更新为 `interrupted`
  - [ ] 1.3 实现 `mark_unreliable_points(session, datasource_id)` 函数：查询 DataSourcePoint 关联的 point_id，将对应 PointRealtime.quality 更新为 2
  - [ ] 1.4 当数据源从 interrupted 恢复（consecutive_failures 重置为 0）时，将 quality 恢复为 0

- [ ] Task 2: 后端 — 数据源通信状态 API (AC: #2)
  - [ ] 2.1 在 `backend/app/api/v1/datasources.py` 新增 `GET /communication-status` 端点（放在其他路由之前避免路径冲突）
  - [ ] 2.2 查询所有启用数据源，对每个数据源统计关联的 DataSourcePoint 数量和关联的不同 device 数量（通过 DataSourcePoint.point_id → Point.device_id）
  - [ ] 2.3 计算中断时长：如果 status == 'interrupted' 且 last_communication 不为空，则 duration = now - last_communication
  - [ ] 2.4 返回列表：`[{ id, name, protocol_type, status, last_communication, consecutive_failures, retry_max_failures, interruption_duration_seconds, affected_points, affected_devices }]`

- [ ] Task 3: 前端 — 数据源管理页面增强 (AC: #4, #5)
  - [ ] 3.1 修改 `frontend/src/views/datasource/index.vue`，在表格中新增列：通信状态（标签）、最后通信时间、连续失败次数
  - [ ] 3.2 通信状态标签颜色：connected=success、disconnected=warning、interrupted=danger
  - [ ] 3.3 当状态为 interrupted 时，行可展开显示影响范围面板：受影响点位数、受影响设备数、中断时长（格式化为 x小时x分钟）
  - [ ] 3.4 新增 API 调用 `getCommunicationStatus()` 并合并到表格数据中

- [ ] Task 4: 前端 — API 扩展 (AC: #2)
  - [ ] 4.1 在 `frontend/src/api/datasource.ts` 新增 `CommunicationStatusItem` 接口和 `getCommunicationStatus()` 函数

- [ ] Task 5: 后端测试 (AC: #6)
  - [ ] 5.1 测试 check_communication_status — 连续失败达到阈值时标记 interrupted
  - [ ] 5.2 测试 mark_unreliable_points — 受影响点位 quality 更新为 2
  - [ ] 5.3 测试通信状态 API — 返回正确的状态和影响范围统计
  - [ ] 5.4 测试通信状态 API — 中断时长计算正确

- [ ] Task 6: 前端构建验证
  - [ ] 6.1 `npm run build` 构建成功

## Dev Notes (开发指南)

### 1. 文件位置

```
backend/app/services/communication_monitor.py    # 新建 — 通信中断检测服务
backend/app/api/v1/datasources.py                # 修改 — 新增 communication-status 端点
backend/tests/test_communication_monitor.py      # 新建 — 测试
frontend/src/views/datasource/index.vue          # 修改 — 新增通信状态列和影响范围面板
frontend/src/api/datasource.ts                   # 修改 — 新增 API 函数
```

### 2. 通信中断检测服务

```python
# backend/app/services/communication_monitor.py
"""通信中断检测服务"""
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from ..models.gateway import DataSource, DataSourcePoint
from ..models.point import Point, PointRealtime


async def check_communication_status(session: AsyncSession):
    """检查所有数据源通信状态，标记中断的数据源"""
    result = await session.execute(
        select(DataSource).where(DataSource.is_enabled == True)
    )
    datasources = result.scalars().all()

    for ds in datasources:
        if ds.consecutive_failures >= ds.retry_max_failures:
            if ds.status != "interrupted":
                await session.execute(
                    update(DataSource).where(DataSource.id == ds.id).values(
                        status="interrupted"
                    )
                )
                # 标记受影响点位为不可靠
                await mark_unreliable_points(session, ds.id, quality=2)
        elif ds.status == "interrupted" and ds.consecutive_failures == 0:
            # 恢复
            await session.execute(
                update(DataSource).where(DataSource.id == ds.id).values(
                    status="connected"
                )
            )
            await mark_unreliable_points(session, ds.id, quality=0)

    await session.commit()


async def mark_unreliable_points(session: AsyncSession, datasource_id: int, quality: int):
    """标记数据源关联点位的数据质量"""
    # 查找数据源关联的 point_id
    result = await session.execute(
        select(DataSourcePoint.point_id).where(
            DataSourcePoint.datasource_id == datasource_id,
            DataSourcePoint.point_id.isnot(None)
        )
    )
    point_ids = [row[0] for row in result.all()]

    if point_ids:
        await session.execute(
            update(PointRealtime).where(
                PointRealtime.point_id.in_(point_ids)
            ).values(quality=quality)
        )
```

### 3. 通信状态 API

在 `datasources.py` 中新增端点，必须放在 `/{datasource_id}` 路由之前：

```python
from datetime import datetime
from ...models.gateway import DataSourcePoint
from ...models.point import Point

@router.get("/communication-status", summary="获取数据源通信状态")
async def get_communication_status(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_viewer)
):
    result = await db.execute(
        select(DataSource).where(DataSource.is_enabled == True).order_by(DataSource.name)
    )
    datasources = result.scalars().all()

    status_list = []
    for ds in datasources:
        # 统计受影响点位数
        points_result = await db.execute(
            select(func.count(DataSourcePoint.id)).where(
                DataSourcePoint.datasource_id == ds.id
            )
        )
        affected_points = points_result.scalar() or 0

        # 统计受影响设备数（通过 DataSourcePoint.point_id → Point.device_id 去重）
        devices_result = await db.execute(
            select(func.count(func.distinct(Point.device_id))).select_from(
                DataSourcePoint
            ).join(
                Point, DataSourcePoint.point_id == Point.id
            ).where(
                DataSourcePoint.datasource_id == ds.id,
                DataSourcePoint.point_id.isnot(None),
                Point.device_id.isnot(None)
            )
        )
        affected_devices = devices_result.scalar() or 0

        # 计算中断时长
        interruption_seconds = None
        if ds.status == "interrupted" and ds.last_communication:
            interruption_seconds = int((datetime.now() - ds.last_communication).total_seconds())

        status_list.append({
            "id": ds.id,
            "name": ds.name,
            "protocol_type": ds.protocol_type,
            "status": ds.status,
            "last_communication": ds.last_communication.isoformat() if ds.last_communication else None,
            "consecutive_failures": ds.consecutive_failures,
            "retry_max_failures": ds.retry_max_failures,
            "interruption_duration_seconds": interruption_seconds,
            "affected_points": affected_points,
            "affected_devices": affected_devices,
        })

    return status_list
```

### 4. 前端数据源页面增强

在 `datasource/index.vue` 的表格中新增列：

```vue
<el-table-column prop="comm_status" label="通信状态" width="110">
  <template #default="{ row }">
    <el-tag :type="commStatusType(row.status)" size="small">
      {{ commStatusText(row.status) }}
    </el-tag>
  </template>
</el-table-column>
<el-table-column prop="last_communication" label="最后通信" width="170" />
<el-table-column prop="consecutive_failures" label="连续失败" width="90" />
```

状态映射：
```typescript
function commStatusType(status: string) {
  return { connected: 'success', disconnected: 'warning', interrupted: 'danger' }[status] || 'info'
}
function commStatusText(status: string) {
  return { connected: '已连接', disconnected: '已断开', interrupted: '通信中断' }[status] || status
}
```

### 5. 关键约束

- **DataSource 模型已有字段**: `consecutive_failures`、`retry_max_failures`（默认 5）、`status`、`last_communication` — 不需要新增字段
- **通信状态 API 路由**: 必须放在 `/{datasource_id}` 之前，避免 FastAPI 将 "communication-status" 解析为 datasource_id
- **quality 值**: 0=好、1=不确定、2=坏（不可靠）
- **自动导入**: Vue API 和 Vue Router API 无需手动 import
- **测试模式**: 使用 in-memory SQLite

### References

- [Source: models/gateway.py] DataSource 模型（consecutive_failures, retry_max_failures, status, last_communication）
- [Source: models/gateway.py] DataSourcePoint 模型（datasource_id, point_id）
- [Source: models/point.py] PointRealtime 模型（quality 字段）
- [Source: api/v1/datasources.py] 现有数据源 API
- [Source: views/datasource/index.vue] 数据源管理页面
- [Source: api/datasource.ts] 前端数据源 API

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

