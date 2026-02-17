# Story 2.2: 网关状态监控

Status: done

## Story

As a 运维工程师,
I want 查看所有网关的运行状态,
so that 我可以及时发现网关故障。

## Acceptance Criteria (验收标准)

1. **AC-1: 网关状态汇总** — 新增 `GET /api/v1/gateways/summary` 返回网关总数、在线数、离线数
2. **AC-2: 网关详情增强** — `GET /api/v1/gateways/{id}` 返回关联的数据源数量和点位数量
3. **AC-3: 网关状态变更记录** — 网关上线/离线时记录状态变更事件到 `gateway_events` 表（event_type、gateway_id、old_status、new_status、timestamp、detail）
4. **AC-4: 状态变更事件查询** — 新增 `GET /api/v1/gateways/{id}/events` 分页查询网关状态变更历史
5. **AC-5: 资源使用率告警阈值** — 网关 CPU/内存/磁盘使用率超过阈值（默认 90%）时，在心跳处理中记录告警事件（同网关 5 分钟内不重复告警）
6. **AC-6: 网关状态筛选增强** — 现有 `GET /api/v1/gateways` 支持按 keyword（名称/IP 模糊搜索）筛选

## Tasks / Subtasks (任务分解)

- [ ] Task 1: GatewayEvent 模型 (AC: #3)
  - [ ] 1.1 在 `backend/app/models/gateway.py` 新增 `GatewayEvent` 模型（id, gateway_id, event_type, old_status, new_status, detail, created_at）
  - [ ] 1.2 event_type 枚举: "status_change", "resource_warning"

- [ ] Task 2: Schema 增强 (AC: #1, #2, #4)
  - [ ] 2.1 新增 `GatewayStatusSummary` schema（total, online, offline）
  - [ ] 2.2 新增 `GatewayDetailResponse` schema（继承 GatewayResponse + datasource_count, point_count）
  - [ ] 2.3 新增 `GatewayEventResponse` schema

- [ ] Task 3: 网关状态服务 (AC: #3, #5)
  - [ ] 3.1 创建 `backend/app/services/gateway_monitor.py`
  - [ ] 3.2 实现 `async def record_status_change(gateway_id, old_status, new_status, db)` — 记录状态变更事件
  - [ ] 3.3 实现 `async def check_resource_warnings(payload, db)` — 检查 CPU/内存/磁盘是否超阈值，超过则记录 resource_warning 事件
  - [ ] 3.4 在 `handle_gateway_status` 中集成：状态变更时调用 record_status_change，每次心跳调用 check_resource_warnings

- [ ] Task 4: API 端点 (AC: #1, #2, #4, #6)
  - [ ] 4.1 新增 `GET /api/v1/gateways/summary` — 返回 GatewayStatusSummary
  - [ ] 4.2 修改 `GET /api/v1/gateways/{gateway_id}` — 返回 GatewayDetailResponse（含 datasource_count, point_count）
  - [ ] 4.3 新增 `GET /api/v1/gateways/{gateway_id}/events` — 分页查询事件
  - [ ] 4.4 修改 `GET /api/v1/gateways` — 新增 keyword 查询参数（模糊匹配 name 或 ip_address）

- [ ] Task 5: 单元测试 (AC: 全部)
  - [ ] 5.1 测试 GET /gateways/summary — 返回正确的 total/online/offline 计数
  - [ ] 5.2 测试 GET /gateways/{id} — 返回 datasource_count 和 point_count
  - [ ] 5.3 测试 record_status_change — 正确创建 GatewayEvent 记录
  - [ ] 5.4 测试 check_resource_warnings — CPU 超阈值记录告警事件
  - [ ] 5.5 测试 check_resource_warnings — 未超阈值不记录
  - [ ] 5.6 测试 handle_gateway_status 集成 — 新网关注册时记录 status_change 事件
  - [ ] 5.7 测试 handle_gateway_status 集成 — 离线网关重新上线记录 status_change 事件
  - [ ] 5.8 测试 GET /gateways/{id}/events — 分页返回事件列表
  - [ ] 5.9 测试 GET /gateways — keyword 模糊搜索
  - [ ] 5.10 测试 check_gateway_heartbeats 集成 — 超时标记 offline 时记录 status_change 事件
  - [ ] 5.11 测试 check_resource_warnings — 冷却期内不重复记录告警
  - [ ] 5.12 测试 check_resource_warnings — 冷却期过后重新记录告警

## Dev Notes (开发指南)

### 1. 文件位置

```
backend/app/models/gateway.py              # 修改 — 新增 GatewayEvent 模型
backend/app/schemas/gateway.py             # 修改 — 新增 Summary/Detail/Event schema
backend/app/services/gateway_monitor.py    # 新建 — 状态监控服务
backend/app/services/gateway_registration.py  # 修改 — 集成状态变更记录
backend/app/api/v1/gateways.py             # 修改 — 新增/增强端点
backend/tests/test_gateway_monitor.py      # 新建 — 单元测试
```

### 2. GatewayEvent 模型

```python
# backend/app/models/gateway.py — 新增

class GatewayEvent(Base):
    """网关事件记录"""
    __tablename__ = "gateway_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    gateway_id = Column(String(50), nullable=False, index=True, comment="网关标识")
    event_type = Column(String(30), nullable=False, comment="事件类型: status_change/resource_warning")
    old_status = Column(String(20), comment="旧状态")
    new_status = Column(String(20), comment="新状态")
    detail = Column(JSON, comment="事件详情")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
```

### 3. 新增 Schema

```python
# backend/app/schemas/gateway.py — 新增

class GatewayStatusSummary(BaseModel):
    """网关状态汇总"""
    total: int
    online: int
    offline: int


class GatewayDetailResponse(GatewayResponse):
    """网关详情（含关联统计）"""
    datasource_count: int = 0
    point_count: int = 0


class GatewayEventResponse(BaseModel):
    """网关事件"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    gateway_id: str
    event_type: str
    old_status: Optional[str] = None
    new_status: Optional[str] = None
    detail: Optional[dict] = None
    created_at: Optional[datetime] = None
```

### 4. 网关监控服务

```python
# backend/app/services/gateway_monitor.py

import logging
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..models.gateway import GatewayEvent

logger = logging.getLogger(__name__)

RESOURCE_WARNING_THRESHOLD = 90.0  # CPU/内存/磁盘告警阈值 %
RESOURCE_WARNING_COOLDOWN = 300  # 资源告警去重冷却期（秒）


async def record_status_change(
    gateway_id: str,
    old_status: str,
    new_status: str,
    db: AsyncSession,
    detail: dict | None = None,
) -> None:
    """记录网关状态变更事件"""
    event = GatewayEvent(
        gateway_id=gateway_id,
        event_type="status_change",
        old_status=old_status,
        new_status=new_status,
        detail=detail,
    )
    db.add(event)
    await db.flush()
    logger.info("网关状态变更: %s %s → %s", gateway_id, old_status, new_status)


async def check_resource_warnings(
    gateway_id: str,
    payload: dict,
    db: AsyncSession,
) -> None:
    """检查资源使用率是否超阈值（5 分钟内同网关不重复告警）"""
    warnings = {}
    for key, label in [("cpu", "CPU"), ("mem", "内存"), ("disk", "磁盘")]:
        value = payload.get(key)
        if value is not None and value > RESOURCE_WARNING_THRESHOLD:
            warnings[key] = value

    if not warnings:
        return

    # 去重：检查冷却期内是否已有 resource_warning
    cooldown_cutoff = datetime.now() - timedelta(seconds=RESOURCE_WARNING_COOLDOWN)
    result = await db.execute(
        select(GatewayEvent).where(
            GatewayEvent.gateway_id == gateway_id,
            GatewayEvent.event_type == "resource_warning",
            GatewayEvent.created_at > cooldown_cutoff,
        ).limit(1)
    )
    if result.scalar_one_or_none() is not None:
        return  # 冷却期内已有告警，跳过

    event = GatewayEvent(
        gateway_id=gateway_id,
        event_type="resource_warning",
        detail={"warnings": warnings, "threshold": RESOURCE_WARNING_THRESHOLD},
    )
    db.add(event)
    await db.flush()
    logger.warning("网关资源告警: %s %s", gateway_id, warnings)
```

### 5. handle_gateway_status 集成修改

在 `gateway_registration.py` 的 `handle_gateway_status` 中：
- 新网关注册后：调用 `record_status_change(gw_id, "none", "online", db)`
- 已有网关且状态从非 online 变为 online：调用 `record_status_change(gw_id, existing.status, "online", db)`
- 每次心跳：调用 `check_resource_warnings(gw_id, payload, db)`
- 注意：先 flush 事件，最后统一 commit

在 `check_gateway_heartbeats` 中：
- 标记 offline 后：为每个 stale gateway 调用 `record_status_change(gw_id, "online", "offline", db)`

### 6. API 端点

```python
# GET /api/v1/gateways/summary — 必须在 /{gateway_id} 之前注册！
@router.get("/summary", response_model=GatewayStatusSummary, summary="网关状态汇总")
async def gateway_summary(db, user):
    total = count(Gateway)
    online = count(Gateway where status="online")
    offline = total - online
    return GatewayStatusSummary(total=total, online=online, offline=offline)

# GET /api/v1/gateways/{gateway_id} — 增强返回 datasource_count, point_count
# 查询 DataSource where gateway_id=gw.id 的 count
# 查询 DataSourcePoint where datasource_id in (上述 datasource ids) 的 count

# GET /api/v1/gateways/{gateway_id}/events — 分页查询
@router.get("/{gateway_id}/events", summary="网关事件历史")
async def gateway_events(gateway_id: int, page, page_size, event_type: Optional[str], db, user):
    # 先查 Gateway 获取 gateway_id 字符串
    # 查询 GatewayEvent where gateway_id=gw.gateway_id, 按 created_at desc
```

### 7. 关键约束

- **路由顺序**: `/summary` 必须在 `/{gateway_id}` 之前注册，否则 "summary" 会被当作 gateway_id
- **flush vs commit**: record_status_change 和 check_resource_warnings 使用 flush（不 commit），由调用方统一 commit
- **资源告警去重**: 同网关 5 分钟（RESOURCE_WARNING_COOLDOWN=300s）内不重复记录 resource_warning 事件
- **gateway_id 参数**: API 路由中 gateway_id 是数据库 id（int），GatewayEvent 中 gateway_id 是网关标识（str）
- **测试使用内存 SQLite**: 与 Story 2.1 测试模式一致
- **lazy logging**: 使用 `%s` 格式

### 8. 测试策略

- API 测试：使用 httpx AsyncClient + ASGI transport，mock get_db
- 服务层测试：使用内存 SQLite，直接调用函数
- 集成测试：验证 handle_gateway_status 调用 record_status_change 和 check_resource_warnings

### Project Structure Notes

- `backend/app/models/gateway.py` — 新增 GatewayEvent 模型
- `backend/app/schemas/gateway.py` — 新增 3 个 schema
- `backend/app/services/gateway_monitor.py` — 新建，状态监控服务
- `backend/app/services/gateway_registration.py` — 修改，集成事件记录
- `backend/app/api/v1/gateways.py` — 修改，新增/增强端点
- 测试文件放在 `backend/tests/test_gateway_monitor.py`

### References

- [Source: epics.md#Story 2.2] Acceptance Criteria
- [Source: prd.md#FR16] 运维工程师可以查看网关运行状态
- [Source: architecture.md#4.2] WebSocket 通道（后续 Story 可集成实时推送）
- [Source: gateway.py model] Gateway, DataSource, DataSourcePoint 模型
- [Source: gateways.py API] 现有 CRUD 端点

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

