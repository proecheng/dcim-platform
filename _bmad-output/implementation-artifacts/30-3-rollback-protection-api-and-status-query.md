# Story 30.3: 回退保护 API 与状态查询

Status: done

## Story

As a 运维人员,
I want 查询当前回退保护状态和历史触发记录,
So that 我能了解系统安全防护的运行情况。

## 依赖

- Story 30.2（7 项自动回退保护机制）— done
  - 提供 `RollbackManager.get_zone_rollback_status(zone_id)` 实时状态查询
  - 提供 `RollbackManager.get_all_statuses()` 全量状态查询
  - 提供 `RollbackEvent` 数据模型（rollback_events 表）
  - 提供 `RollbackTriggerType` 枚举（7 种触发类型）
  - 提供 `rollback_manager` 全局实例

## Acceptance Criteria

1. Given 回退保护机制已运行
   When 调用 `GET /api/v1/precool/zones/{zone_id}/rollback-status`
   Then 返回当前保护状态（正常/回退中）
   - 包含 `has_active_rollback`（bool）、`active_triggers` 列表
   - 每个 trigger 包含：trigger_type、since、event_id、recovering 状态

2. Given 回退事件存在历史记录
   When 调用 `GET /api/v1/precool/zones/{zone_id}/rollback-history`
   Then 返回历史回退事件列表（分页）
   - 响应包含 trigger_type、trigger_value、threshold、action、status、created_at、resolved_at
   - 支持 skip/limit 分页参数
   - 支持 status 筛选（active/resolved，不传则返回全部）
   - 按 created_at 降序排列

3. Given 需要全局概览
   When 调用 `GET /api/v1/precool/rollback-overview`
   Then 返回所有 zone 的回退状态汇总
   - 包含总 zone 数（从 CoolingZone 表查询）、活跃回退数、各 trigger_type 统计

4. Given API 被调用
   When 权限检查通过
   Then 所有端点需要 viewer 及以上权限（admin/operator/viewer）

5. Given API 端点已创建
   When 编写测试
   Then 每个端点至少 2 个测试用例（正常/边界）

## Tasks / Subtasks

- [x] Task 1: 创建回退相关 Pydantic Schema (AC: #1, #2, #3)
  - [x] 1.1 在 `schemas/precool.py` 追加 `RollbackStatusResponse`、`RollbackTriggerInfo`
  - [x] 1.2 追加 `RollbackEventOut`（历史事件输出 schema）
  - [x] 1.3 追加 `RollbackOverviewResponse`（全局概览 schema）

- [x] Task 2: 在 `api/v1/precool.py` 追加 3 个回退 API 端点 (AC: #1, #2, #3, #4)
  - [x] 2.1 `GET /zones/{zone_id}/rollback-status` — 先查 CoolingZone 表验证 zone_id 存在（不存在返回 404），再调用 `rollback_manager.get_zone_rollback_status(zone_id)`
  - [x] 2.2 `GET /zones/{zone_id}/rollback-history` — 先校验 zone_id 存在（404），再查询 RollbackEvent 表（分页 + 可选 status 筛选）
  - [x] 2.3 `GET /rollback-overview` — 先查 CoolingZone 全量 ID，逐个调用 `rollback_manager.get_zone_rollback_status(zone_id)`（**不要使用 `get_all_statuses()`**，它只包含内存中已注册的 zone），统计 24h 事件数

- [x] Task 3: 编写单元测试 (AC: #5)
  - [x] 3.1 rollback-status 端点测试（正常状态 + 活跃回退）
  - [x] 3.2 rollback-history 端点测试（空历史 + 有记录 + 分页 + status 筛选）
  - [x] 3.3 rollback-overview 端点测试（无回退 + 有活跃回退）

## Dev Notes

### 架构约束

- **修改文件**: `backend/app/schemas/precool.py` — 追加 3 个 schema 类
- **修改文件**: `backend/app/api/v1/precool.py` — 追加 3 个端点
- **新建文件**: `backend/tests/api/test_precool_rollback.py` — API 测试

### API 端点设计

#### 1. GET /api/v1/precool/zones/{zone_id}/rollback-status

```python
@router.get("/zones/{zone_id}/rollback-status", summary="查询 zone 回退保护状态")
async def get_rollback_status(
    zone_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(["admin", "operator", "viewer"])),
):
    """
    返回指定 zone 的实时回退保护状态。
    数据来源: rollback_manager.get_zone_rollback_status(zone_id)（内存状态）
    """
```

响应格式：
```json
{
    "code": 200,
    "message": "success",
    "data": {
        "zone_id": 1,
        "has_active_rollback": true,
        "active_triggers": [
            {
                "trigger_type": "temp_over_limit",
                "since": "2026-03-11T10:30:00",
                "event_id": 42,
                "recovering": false
            }
        ]
    }
}
```

#### 2. GET /api/v1/precool/zones/{zone_id}/rollback-history

```python
@router.get("/zones/{zone_id}/rollback-history", summary="查询回退历史事件")
async def get_rollback_history(
    zone_id: int,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    status: Optional[Literal["active", "resolved"]] = Query(default=None, description="筛选: active/resolved，不传返回全部"),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(["admin", "operator", "viewer"])),
):
    """
    查询指定 zone 的历史回退事件，支持分页和 status 筛选。
    数据来源: RollbackEvent 表（ORM 查询）
    """
```

响应格式：
```json
{
    "code": 200,
    "message": "success",
    "data": {
        "items": [
            {
                "id": 42,
                "zone_id": 1,
                "trigger_type": "temp_over_limit",
                "trigger_value": 27.5,
                "threshold": 26.0,
                "action": "恢复正常制冷",
                "status": "resolved",
                "created_at": "2026-03-11T10:30:00",
                "resolved_at": "2026-03-11T10:45:00"
            }
        ],
        "total": 15
    }
}
```

#### 3. GET /api/v1/precool/rollback-overview

```python
@router.get("/rollback-overview", summary="全局回退状态概览")
async def get_rollback_overview(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(["admin", "operator", "viewer"])),
):
    """
    返回所有 zone 的回退状态汇总。
    数据来源:
    - total_zones: 从 CoolingZone 表 SELECT COUNT(*) 获取（非 rollback_manager 内存）
    - zone_statuses: rollback_manager.get_zone_rollback_status(zone_id) 对每个 CoolingZone
    - recent_events_24h: RollbackEvent 表统计
    """
```

响应格式：
```json
{
    "code": 200,
    "message": "success",
    "data": {
        "total_zones": 5,
        "zones_with_active_rollback": 1,
        "total_active_triggers": 2,
        "trigger_type_counts": {
            "temp_over_limit": 1,
            "sensor_offline": 1
        },
        "recent_events_24h": 8,
        "zone_statuses": [...]
    }
}
```

### Pydantic Schema 设计

```python
# 追加到 schemas/precool.py

class RollbackTriggerInfo(BaseModel):
    """回退触发条件信息"""
    trigger_type: str
    since: Optional[datetime] = None
    event_id: Optional[int] = None
    recovering: bool = False

class RollbackStatusResponse(BaseModel):
    """回退状态响应"""
    zone_id: int
    has_active_rollback: bool
    active_triggers: List[RollbackTriggerInfo]

class RollbackEventOut(BaseModel):
    """回退事件历史输出"""
    model_config = {"from_attributes": True}

    id: int
    zone_id: int
    trigger_type: str
    trigger_value: Optional[float] = None
    threshold: Optional[float] = None
    action: str
    status: str
    context_json: Optional[str] = None
    created_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None

class RollbackOverviewResponse(BaseModel):
    """回退全局概览"""
    total_zones: int
    zones_with_active_rollback: int
    total_active_triggers: int
    trigger_type_counts: Dict[str, int]
    recent_events_24h: int
    zone_statuses: List[RollbackStatusResponse]
```

### 测试模式

使用项目现有的 API 测试模式（参考 `tests/api/` 目录）：
- 使用 `httpx.AsyncClient` + `app` fixture
- Mock `rollback_manager`: `patch("app.api.v1.precool.rollback_manager")` （顶层 import 后 mock 消费端）
- Mock 数据库查询: `AsyncMock` session
- 验证响应 code、data 结构、分页逻辑

### 权限说明

所有 3 个端点使用 `require_role(["admin", "operator", "viewer"])`，回退状态是只读查询，所有角色均可查看。
注意：现有 precool.py 端点（predict/parameters/validation/dashboard）使用 `["admin", "operator"]` 不含 viewer。
回退状态查询有意对 viewer 开放，因为这是安全监控信息，所有角色都需要可见性。

### Import 指导

在 `precool.py` 中使用**顶层 import**（3 个端点共用，无循环依赖风险）：
```python
from ...services.precool.rollback_manager import rollback_manager
from ...models.rollback import RollbackEvent
```

overview 端点中的 `CoolingZone` 使用**函数体内 lazy import**（与 dashboard 端点保持一致）：
```python
from ...models.topology_config import CoolingZone
```

注意：`rollback_manager` 返回的 `since` 是 ISO 字符串，Pydantic v2 datetime 字段会自动解析，无需转换。

### 响应格式

遵循项目现有的 `{"code": 200, "message": "...", "data": ...}` 统一响应格式（与 precool.py 现有端点一致）。

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Epic30-Story30.3] — AC 定义
- [Source: _bmad-output/planning-artifacts/architecture.md#Section21.5] — API 扩展端点定义
- [Source: backend/app/api/v1/precool.py] — 现有预冷 API 端点（追加模式）
- [Source: backend/app/schemas/precool.py] — 现有 Schema 定义（追加模式）
- [Source: backend/app/services/precool/rollback_manager.py:438-463] — get_zone_rollback_status / get_all_statuses
- [Source: backend/app/models/rollback.py] — RollbackEvent + RollbackTriggerType

### Previous Story Intelligence

**从 Story 30.2 学到的关键经验：**
1. **WebSocket mock 路径**: `patch("app.services.websocket.ws_manager")` 而非 module-level
2. **CoolingZoneCabinet FK**: 字段是 `zone_id` 不是 `cooling_zone_id`
3. **Lazy import**: 函数体内 import 避免循环依赖
4. **Dev Agent Record**: 实施完必须更新 tasks [x]、File List、Change Log
5. **统一响应格式**: `{"code": 200, "message": "success", "data": ...}`

## NFR 追溯

- **NFR-TCL-6**: 回退响应时间 ≤ 30 秒（API 查询响应远低于此限制）

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Completion Notes List

- 13/13 API 测试全部通过
- 17/17 回归测试（test_precool.py）全部通过
- 3 个 API 端点实现完成：rollback-status、rollback-history、rollback-overview
- 4 个 Pydantic Schema 追加完成
- 代码审查修复：移除未使用 import（MagicMock, AsyncMock）

### Change Log

- `backend/app/schemas/precool.py`: 追加 RollbackTriggerInfo、RollbackStatusResponse、RollbackEventOut、RollbackOverviewResponse 4 个 Schema
- `backend/app/api/v1/precool.py`: 追加 rollback-status、rollback-history、rollback-overview 3 个端点 + 顶层 import rollback_manager/RollbackEvent
- `backend/tests/api/test_precool_rollback.py`: 新建 13 个测试用例（3 个 TestClass）

### File List

- `backend/app/schemas/precool.py` (modified)
- `backend/app/api/v1/precool.py` (modified)
- `backend/tests/api/test_precool_rollback.py` (new)
