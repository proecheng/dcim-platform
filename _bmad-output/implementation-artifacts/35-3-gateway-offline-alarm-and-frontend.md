# Story 35.3: 网关离线告警与前端展示

Status: ready-for-dev

## Story

As a 运维工程师,
I want 协议转换网关离线时收到明确告警，前端能区分显示网关故障和设备故障,
So that 我能快速响应并了解故障影响范围。

## Acceptance Criteria

1. **Given** 网关 DataSource 状态变为 gateway_offline **When** gateway_monitor 触发状态变更 **Then** 生成"协议转换网关离线"告警（level=major），告警描述包含影响的 MS/TP 设备数量和设备名称列表
2. **Given** 设备 DataSource 状态变为 device_offline **When** communication_monitor 检测到 **Then** 生成"MS/TP 设备离线（网关正常）"告警（level=minor）
3. **Given** 网关或设备恢复在线 **When** 状态从 gateway_offline/device_offline 恢复为 connected/disconnected **Then** 自动恢复（resolved）对应的 active 告警
4. **Given** 管理员查看数据源列表 **When** 存在 MS/TP 相关数据源 **Then** 状态列区分显示：gateway_offline（红色 Tag "网关离线"）、device_offline（橙色 Tag "设备离线"）
5. **Given** 管理员查看数据源列表 **When** 使用 parent_datasource_id 参数过滤 **Then** 仅返回指定网关下的子设备数据源
6. **Given** 管理员查看数据源列表 **When** 存在状态筛选下拉框 **Then** 新增"网关离线"和"设备离线"筛选选项

## Tasks / Subtasks

- [ ] Task 1: Alarm 模型扩展 — 新增 source 字段 (AC: #1, #2, #3)
  - [ ] 1.1 Alarm 表新增 `source` 列（String(100), nullable=True, indexed），用于存储 `"datasource:{ds_id}"`
  - [ ] 1.2 Alarm 表 `point_id` 改为 nullable=True（数据源级告警无点位关联）
  - [ ] 1.3 Alembic 迁移脚本：仅添加 source 列（SQLite 不支持 ALTER COLUMN nullable，ORM 模型层面已改 nullable=True）
  - [ ] 1.4 告警 API 中的 JOIN/GROUP BY 查询加 `Alarm.point_id.isnot(None)` 条件，防止 NULL point_id 影响统计
- [ ] Task 2: 告警触发与恢复方法 (AC: #1, #2, #3)
  - [ ] 2.1 新建 `backend/app/services/datasource_alarm.py` 共享模块
  - [ ] 2.2 实现 `create_datasource_alarm(db, ds, alarm_type, level, message)` — 幂等创建
  - [ ] 2.3 实现 `resolve_datasource_alarm(db, ds_id)` — Python 计算 duration_seconds
  - [ ] 2.4 实现 `resolve_datasource_alarms_batch(db, ds_ids)` — 批量关闭告警（避免 N+1）
  - [ ] 2.5 在 `_probe_gateway()` 中嵌入告警触发/恢复（含子设备名称查询和 WebSocket 推送）
  - [ ] 2.6 在 communication_monitor.py 中嵌入 device_offline 告警创建/恢复
- [ ] Task 3: API 扩展 (AC: #5)
  - [ ] 3.1 `GET /api/v1/datasources` 新增可选查询参数 `parent_datasource_id: Optional[int]`
- [ ] Task 4: 前端数据源列表页扩展 (AC: #4, #6)
  - [ ] 4.1 `commStatusType()` 和 `commStatusText()` 新增 gateway_offline / device_offline 映射
  - [ ] 4.2 `getStatusType()` 和 `getStatusLabel()` 同步新增映射（保持一致性）
  - [ ] 4.3 状态筛选下拉框新增"网关离线"和"设备离线"选项
- [ ] Task 5: 测试 (AC: #1-#6)
  - [ ] 5.1 网关离线告警创建测试 — gateway_offline 触发 major 告警，描述包含子设备信息
  - [ ] 5.2 设备离线告警创建测试 — device_offline 触发 minor 告警
  - [ ] 5.3 网关恢复自动关闭告警测试 — gateway 恢复 → source 匹配的 active 告警 resolved
  - [ ] 5.4 设备恢复自动关闭告警测试 — device 恢复 → 对应告警 resolved
  - [ ] 5.5 API parent_datasource_id 过滤测试
  - [ ] 5.6 重复告警幂等测试 — 已有 active 告警时不重复创建
  - [ ] 5.7 网关恢复级联告警关闭测试 — 网关恢复时子设备的 gateway_offline 告警也批量关闭
  - [ ] 5.8 communication_monitor 回归测试 — 现有 interrupted 逻辑不受影响

## Dev Notes

### 关键设计决策（R1 审查修正）

**1. Alarm.source 字段（新增列）：**
现有 Alarm 表没有 `source` 字段，仅有 `data_source`（存储 demo/mqtt/bridge/unknown）。数据源级告警需要一个独立的匹配键来关联告警与 DataSource。新增 `source` 列（String(100), nullable=True），索引加速查找。

```python
# Alarm 模型新增
source = Column(String(100), nullable=True, index=True, comment="告警来源标识(如 datasource:123)")
```

**2. point_id 改为 nullable + 告警 API 防护（R1#1, R1#9）：**
ORM 模型改 `nullable=True`。SQLite 不支持 ALTER COLUMN 修改 nullable 约束，但 SQLite 实际上**不强制检查 NOT NULL 约束的修改**（通过 ORM INSERT NULL 即可）。迁移脚本仅添加 `source` 列，不重建 alarms 表。

告警 API 中的 JOIN/GROUP BY 查询需加保护：
```python
# 在 alarm API 的 JOIN 查询中，排除 point_id=NULL 的记录
query = query.where(Alarm.point_id.isnot(None))
# 或使用 LEFT JOIN（outerjoin）
```

AlarmInfo schema 中 `point_id` 改为 `Optional[int] = None`。

**3. 告警类型与级别：**

| alarm_type | alarm_level | 触发条件 | 描述模板 |
|---|---|---|---|
| `mstp_gateway_offline` | major | 网关 consecutive_failures >= 阈值 | "协议转换网关 {name} 离线，影响 {count} 台 MS/TP 设备：{device_list}" |
| `mstp_device_offline` | minor | 设备 consecutive_failures >= 阈值，网关在线 | "MS/TP 设备 {name} 离线（网关正常）" |

**4. alarm_no 生成统一（R1#2）：**
使用与 ingest_pipeline 相同的格式：`ALM{timestamp}{uuid.hex[:6]}`，避免两种格式并存：
```python
import uuid
alarm_no = f"ALM{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6]}"
```

**5. 共享模块 datasource_alarm.py（R1#5）：**

提取告警方法到独立共享模块 `backend/app/services/datasource_alarm.py`，避免 gateway_monitor 和 communication_monitor 之间的跨模块调用：

```python
"""DataSource 级告警管理（网关/设备离线）— Story 35.3"""
import uuid
import logging
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from ..models.alarm import Alarm
from ..models.gateway import DataSource

logger = logging.getLogger(__name__)


async def create_datasource_alarm(
    db: AsyncSession,
    ds: DataSource,
    alarm_type: str,
    alarm_level: str,
    alarm_message: str,
) -> Optional[Alarm]:
    """为 DataSource 创建告警，幂等（已有 active 告警则跳过）"""
    source_key = f"datasource:{ds.id}"
    # 幂等检查
    existing = await db.execute(
        select(Alarm).where(
            Alarm.source == source_key,
            Alarm.status == "active",
        ).limit(1)
    )
    if existing.scalar_one_or_none() is not None:
        return None  # 已有 active 告警

    alarm_no = f"ALM{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6]}"
    alarm = Alarm(
        alarm_no=alarm_no,
        point_id=None,
        alarm_level=alarm_level,
        alarm_type=alarm_type,
        alarm_message=alarm_message,
        source=source_key,
        status="active",
        data_source="bridge",
    )
    db.add(alarm)
    await db.flush()
    logger.info("数据源告警创建: %s [%s] %s", alarm_no, alarm_type, ds.name)
    return alarm
```

**6. resolve_datasource_alarm — Python 计算 duration_seconds（R1#3）：**

```python
async def resolve_datasource_alarm(
    db: AsyncSession, ds_id: int, now: Optional[datetime] = None
) -> int:
    """恢复指定 DataSource 的所有 active 告警，返回关闭数量"""
    if now is None:
        now = datetime.now()
    source_key = f"datasource:{ds_id}"

    result = await db.execute(
        select(Alarm).where(Alarm.source == source_key, Alarm.status == "active")
    )
    alarms = result.scalars().all()
    for alarm in alarms:
        alarm.status = "resolved"
        alarm.resolve_type = "auto"
        alarm.resolved_at = now
        if alarm.created_at:
            alarm.duration_seconds = int((now - alarm.created_at).total_seconds())
    return len(alarms)
```

**7. resolve_datasource_alarms_batch — 批量关闭（R1#4）：**

网关恢复时，一次性关闭所有子设备的告警（避免 N+1）：
```python
async def resolve_datasource_alarms_batch(
    db: AsyncSession, ds_ids: list[int], now: Optional[datetime] = None
) -> int:
    """批量恢复多个 DataSource 的 active 告警"""
    if not ds_ids:
        return 0
    if now is None:
        now = datetime.now()
    source_keys = [f"datasource:{did}" for did in ds_ids]

    result = await db.execute(
        select(Alarm).where(
            Alarm.source.in_(source_keys), Alarm.status == "active"
        )
    )
    alarms = result.scalars().all()
    for alarm in alarms:
        alarm.status = "resolved"
        alarm.resolve_type = "auto"
        alarm.resolved_at = now
        if alarm.created_at:
            alarm.duration_seconds = int((now - alarm.created_at).total_seconds())
    return len(alarms)
```

**8. _probe_gateway 中的告警触发位置（R1#7）：**

在 `_probe_gateway()` 中，网关达阈值后的逻辑：
```python
if row.consecutive_failures >= row.retry_max_failures:
    # 1. 标记网关 gateway_offline（已有）
    # 2. 批量级联子设备（已有）
    # 3. 查询子设备名称列表（新增）
    child_result = await db.execute(
        select(DataSource.id, DataSource.name)
        .where(DataSource.parent_datasource_id == gw_ds.id)
    )
    children = child_result.fetchall()
    device_names = ", ".join([c.name for c in children[:10]])  # 最多列出10个
    if len(children) > 10:
        device_names += f" 等{len(children)}台"
    # 4. 创建告警
    await create_datasource_alarm(
        db, gw_ds, "mstp_gateway_offline", "major",
        f"协议转换网关 {gw_ds.name} 离线，影响 {len(children)} 台 MS/TP 设备：{device_names}"
    )
```

网关恢复时：
```python
if pre_probe_status == "gateway_offline":
    # 1. 子设备状态恢复为 disconnected（已有）
    # 2. 关闭网关自身告警
    await resolve_datasource_alarm(db, gw_ds.id)
    # 3. 批量关闭子设备告警
    child_result = await db.execute(
        select(DataSource.id).where(DataSource.parent_datasource_id == gw_ds.id)
    )
    child_ids = [r[0] for r in child_result.fetchall()]
    await resolve_datasource_alarms_batch(db, child_ids)
```

**9. WebSocket 告警推送（R1#10）：**

在 `create_datasource_alarm` 返回告警对象后，在 `_probe_gateway` / `communication_monitor` 的调用点执行 WebSocket 推送：
```python
from ..core.websocket import ws_manager

alarm = await create_datasource_alarm(db, gw_ds, ...)
if alarm:
    try:
        await ws_manager.broadcast_alarm({
            "action": "new",
            "id": alarm.id,
            "alarm_no": alarm.alarm_no,
            "alarm_level": alarm.alarm_level,
            "alarm_type": alarm.alarm_type,
            "alarm_message": alarm.alarm_message,
            "status": "active",
        })
    except Exception:
        pass  # WebSocket 失败不影响告警存储
```

注意：WebSocket 推送在 `db.commit()` 之前调用。参照 ingest_pipeline 的 commit-first-then-broadcast 模式，应在 commit 之后推送。但由于 `_probe_gateway` 在循环结束后统一 commit（check_mstp_gateway_health 末尾），推送应在 commit 后批量执行。

**优化方案**：在 `_probe_gateway` 中收集待推送消息列表，`check_mstp_gateway_health` 的 commit 之后统一推送。

**10. WebSocket 推送 commit-first-then-broadcast 模式（R1#10 + R2#5）：**

在 `check_mstp_gateway_health` 和 `check_communication_status` 中，收集待推送消息列表，commit 之后统一推送：
```python
# check_mstp_gateway_health 中
pending_broadcasts = []
for gw_ds in gateway_datasources:
    try:
        broadcasts = await _probe_gateway(gw_ds, db)  # 返回待推送列表
        pending_broadcasts.extend(broadcasts)
    except Exception as e:
        logger.error(...)

await db.commit()

# commit 成功后推送
for msg in pending_broadcasts:
    try:
        await ws_manager.broadcast_alarm(msg)
    except Exception:
        pass
```

`_probe_gateway` 返回 `list[dict]`（待推送消息），不直接推送。这保证了数据库提交失败时不会发出虚假推送。

**11. 孤儿设备告警清理（R2#1）：**

当网关 DataSource 被删除（ondelete=SET NULL），子设备变成孤儿（parent_datasource_id=NULL）。在 `resolve_datasource_alarm` 中，查找 source 对应的 DataSource 是否仍存在。但更简单的方案是：**不额外处理**。

原因：
- 网关被删除是低频管理操作
- 孤儿设备会被 communication_monitor 作为普通设备处理（parent=NULL → 无父网关逻辑）
- 其 active 告警的 source="datasource:{id}" 会在设备恢复通信时自动关闭
- 如果设备也被删除，告警保持 active 不影响系统运行（前端筛选默认不展示已删除设备的告警）

**12. 前端状态映射同步（R1#8）：**

`getStatusType` 和 `getStatusLabel` 在多个页面中使用。需同步新增映射：
```typescript
// getStatusType 新增
gateway_offline: 'danger',
device_offline: 'warning',

// getStatusLabel 新增
gateway_offline: '网关离线',
device_offline: '设备离线',
```

**11. 竞态安全性（R1#6）：**

幂等检查采用 SELECT + INSERT 模式。由于 `check_mstp_gateway_health` 和 `check_communication_status` 都是单协程串行执行（asyncio.create_task 但各自 while True 循环内串行），且使用独立 Session，实际竞态概率极低。不引入 SELECT FOR UPDATE（SQLite 不支持），也不使用唯一约束（source+status 组合不适合唯一约束，因为 resolved 后可能再次 active）。在极端情况下产生重复告警可通过前端去重展示处理。

### 需修改的文件清单

| 文件 | 修改内容 |
|------|---------|
| `backend/app/models/alarm.py` | Alarm 新增 `source` 列，`point_id` 改为 nullable |
| `backend/app/schemas/alarm.py` | AlarmInfo 中 point_id 改为 Optional[int] |
| `backend/alembic/versions/20260321_story_35_3_alarm_source.py` | 迁移脚本（仅添加 source 列 + 索引）|
| `backend/app/services/datasource_alarm.py` | 新建：create/resolve/resolve_batch |
| `backend/app/services/gateway_monitor.py` | 嵌入告警触发/恢复 + 子设备名称查询 |
| `backend/app/services/communication_monitor.py` | device_offline 告警创建/恢复 |
| `backend/app/api/v1/alarm.py` | JOIN/GROUP BY 查询加 point_id.isnot(None) 防护 |
| `backend/app/api/v1/datasources.py` | 新增 `parent_datasource_id` 查询参数 |
| `frontend/src/views/datasource/index.vue` | 状态显示扩展 + 筛选选项 |
| `backend/tests/services/test_gateway_offline_alarm.py` | 新建测试文件（8 个测试） |

### 不需要修改的文件

- `backend/app/schemas/gateway.py` — DataSourceResponse 已有 parent_datasource_id（Story 35.1）
- `backend/app/main.py` — 无需新增定时任务
- `backend/app/models/gateway.py` — DataSource 模型无需修改

### 测试策略

```python
# Mock BacnetIpAdapter（复用 Story 35.2 模式）
@patch("app.services.gateway_monitor.BacnetIpAdapter")
async def test_gateway_offline_alarm_created(MockAdapter, async_db):
    # 1. 创建网关+子设备 DataSource
    # 2. Mock adapter.connect 返回 False
    # 3. 循环调用 _probe_gateway 直到 consecutive_failures >= 阈值
    # 4. 验证 Alarm 表有 source="datasource:{gw_id}", alarm_type="mstp_gateway_offline", status="active"
    # 5. 验证 alarm_message 包含子设备数量
```

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Epic 35 Story 35.3]
- [Source: _bmad-output/planning-artifacts/architecture.md#Section 24.3]
- [Source: _bmad-output/planning-artifacts/prd.md#FR-BN03, FR-BN04]
- [Source: backend/app/models/alarm.py — Alarm 表结构]
- [Source: backend/app/services/gateway_monitor.py — _probe_gateway() 模式]
- [Source: backend/app/services/communication_monitor.py — check_communication_status() 模式]
- [Source: frontend/src/views/datasource/index.vue — commStatusType/commStatusText 模式]
- [Source: backend/app/api/v1/datasources.py:82-120 — list_datasources 查询参数]

### R1 审查修正记录

| 编号 | 问题 | 修正 |
|------|------|------|
| R1-1 | point_id nullable 后 JOIN/GROUP BY 风险 | 告警 API 查询加 point_id.isnot(None) 防护 |
| R1-2 | alarm_no 格式不一致 | 统一使用 ingest_pipeline 格式 ALM{timestamp}{uuid6} |
| R1-3 | julianday() 数据库方言依赖 | 改用 Python 计算 duration_seconds |
| R1-4 | 子设备告警关闭 N+1 性能 | 新增 resolve_datasource_alarms_batch 批量方法 |
| R1-5 | 跨模块调用 | 提取到独立共享模块 datasource_alarm.py |
| R1-6 | 幂等检查竞态 | 串行协程+独立Session，竞态概率极低，可接受 |
| R1-7 | 子设备名称查询时序 | 明确在 _probe_gateway 的 UPDATE 之后、commit 之前查询 |
| R1-8 | 前端 getStatusType 未同步 | 同步新增 gateway_offline/device_offline 映射 |
| R1-9 | SQLite ALTER COLUMN 限制 | 迁移仅添加 source 列，nullable 由 ORM 处理 |
| R1-10 | 缺少 WebSocket 推送 | commit 后批量推送告警消息 |

### R2 边缘用例审查修正记录

| 编号 | 问题 | 结论 |
|------|------|------|
| R2-1 | 孤儿设备告警 | 不额外处理，依赖 communication_monitor 自然恢复 |
| R2-2 | 单 cycle 翻转 | 可接受，retry_max_failures=5 已提供缓冲 |
| R2-3 | 超长消息 | 已限制最多列出 10 个设备名 |
| R2-4 | SQLite 迁移 | 标准 add_column，无需 batch mode |
| R2-5 | WebSocket 时序 | commit-first-then-broadcast，_probe_gateway 返回待推送列表 |
| R2-6 | 双告警恢复 | 设计合理，不会并存两条告警 |
| R2-7 | point_id=NULL 前端异常 | AlarmInfo 改 Optional + 告警 API JOIN 防护 |
| R2-8 | 网络波动误判 | retry_max_failures=5 已足够，不修改 |

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6

### Debug Log References

### Completion Notes List

### File List
