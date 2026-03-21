# Story 35.2: 双层故障隔离

Status: done

## Story

As a 运维工程师,
I want 平台能区分"协议转换网关离线"和"MS/TP 终端设备离线"两种故障场景,
So that 我能快速定位故障层级，不把单设备故障误判为网关故障。

## Acceptance Criteria

1. **Given** 网关 DataSource 连通性探测连续失败达到阈值 **When** check_mstp_gateway_health 检测到 **Then** 该网关 DataSource 标记为 status="gateway_offline"，所有子 DataSource 批量标记为 status="gateway_offline"
2. **Given** 网关在线但某 MS/TP 设备的 DataSource consecutive_failures 达到阈值 **When** communication_monitor 检测到 **Then** 仅该设备 DataSource 标记为 status="device_offline"，网关和其他设备不受影响
3. **Given** 网关 DataSource 探测恢复成功 **When** check_mstp_gateway_health 检测到 **Then** 网关 DataSource 恢复为 status="connected"，子 DataSource 从 gateway_offline 恢复为 disconnected（等待各自采集确认）
4. **Given** 故障发生 **When** 到状态更新完成 **Then** 延迟 ≤ 30s（一个检查周期内）

## Tasks / Subtasks

- [ ] Task 1: check_mstp_gateway_health 核心方法 (AC: #1, #3)
  - [ ] 1.1 在 gateway_monitor.py 新增 check_mstp_gateway_health(db) 异步方法
  - [ ] 1.2 通过 parent_datasource_id 反查获取所有网关 DataSource ID
  - [ ] 1.3 对每个网关：try/finally 包裹 connect→test_connection→disconnect
  - [ ] 1.4 探测成功：SQL 级别 UPDATE consecutive_failures=0, status='connected'
  - [ ] 1.5 探测失败：SQL 级别 UPDATE consecutive_failures=consecutive_failures+1
  - [ ] 1.6 达到阈值时批量级联子 DataSource 为 gateway_offline
  - [ ] 1.7 网关恢复：子 DataSource 从 gateway_offline 恢复为 disconnected
- [ ] Task 2: communication_monitor 扩展 (AC: #2)
  - [ ] 2.1 循环前预加载所有 parent_datasource_id→status 映射（避免 N+1）
  - [ ] 2.2 子设备故障且父网关在线→标记 device_offline（而非 interrupted）
  - [ ] 2.3 子设备父网关已 gateway_offline→跳过（由 gateway_health 管理）
  - [ ] 2.4 恢复路径：device_offline→connected 当 consecutive_failures=0
  - [ ] 2.5 gateway_offline 恢复跳过（由 gateway_health 管理）
- [ ] Task 3: 定时任务注册 (AC: #4)
  - [ ] 3.1 在 main.py lifespan 中注册 _mstp_gateway_health_loop（30s 周期）
  - [ ] 3.2 shutdown 时显式 cancel mstp_health_task
- [ ] Task 4: 测试 (AC: #1-#4)
  - [ ] 4.1 网关故障级联测试（网关+子设备均变 gateway_offline）
  - [ ] 4.2 设备单独离线测试（网关在线，仅设备 device_offline）
  - [ ] 4.3 网关恢复测试（网关→connected，子设备→disconnected）
  - [ ] 4.4 无网关配置时 check_mstp_gateway_health 立即返回
  - [ ] 4.5 communication_monitor 兼容新状态回归测试
  - [ ] 4.6 子设备先 device_offline 后网关故障→变 gateway_offline，网关恢复后→disconnected

## Dev Notes

### 关键设计决策（R1+R2 审查修正）

**1. consecutive_failures 由 check_mstp_gateway_health 自行管理（R1#1）：**
网关 DataSource 的 `is_enabled=False`，CollectionScheduler 不会为其创建采集任务，因此 `consecutive_failures` 永远不会被采集管线递增。`check_mstp_gateway_health` 必须自行通过 SQL UPDATE 递增/重置。

**2. 探测逻辑（R1#2/#3 + R2#5 connect超时 + R2#2 条件恢复 + R2#4 flush）：**
```python
import asyncio

GATEWAY_PROBE_TIMEOUT = 10  # 秒，防止 connect() 永久挂起（R2#8）

async def _probe_gateway(gw_ds: DataSource, db: AsyncSession):
    """探测单个网关可达性，更新 consecutive_failures 和 status"""
    adapter = BacnetIpAdapter()
    config = DataSourceConfig(
        datasource_id=str(gw_ds.id),
        protocol_type="bacnet_ip",
        connection_params=gw_ds.connection_config,
        points=[],
        collection_interval=30,
    )
    reachable = False
    try:
        # R2#8: 超时保护，防止 connect() 挂起
        connected = await asyncio.wait_for(
            adapter.connect(config), timeout=GATEWAY_PROBE_TIMEOUT
        )
        if connected:
            result = await asyncio.wait_for(
                adapter.test_connection(), timeout=GATEWAY_PROBE_TIMEOUT
            )
            reachable = result.success
    except asyncio.TimeoutError:
        logger.warning("网关 %s 探测超时 (%ds)", gw_ds.id, GATEWAY_PROBE_TIMEOUT)
        reachable = False
    except Exception as e:
        logger.warning("网关 %s 探测异常: %s", gw_ds.id, e)
        reachable = False
    finally:
        try:
            await adapter.disconnect()
        except Exception:
            pass

    now = datetime.now()
    if reachable:
        # 探测成功：重置失败计数
        await db.execute(
            update(DataSource).where(DataSource.id == gw_ds.id)
            .values(consecutive_failures=0, status="connected", updated_at=now)
        )
        # R2#2: 仅当网关之前是 gateway_offline 时才恢复子设备（避免无谓 UPDATE）
        if gw_ds.status == "gateway_offline":
            await db.execute(
                update(DataSource)
                .where(
                    DataSource.parent_datasource_id == gw_ds.id,
                    DataSource.status == "gateway_offline",
                )
                .values(status="disconnected", updated_at=now)
            )
    else:
        # 探测失败：SQL 级别递增（R1#9）
        await db.execute(
            update(DataSource).where(DataSource.id == gw_ds.id)
            .values(
                consecutive_failures=DataSource.consecutive_failures + 1,
                updated_at=now,
            )
        )
        # R2#4: flush 确保 SELECT 读到最新值
        await db.flush()
        result = await db.execute(
            select(DataSource.consecutive_failures, DataSource.retry_max_failures)
            .where(DataSource.id == gw_ds.id)
        )
        row = result.one()
        if row.consecutive_failures >= row.retry_max_failures:
            await db.execute(
                update(DataSource).where(DataSource.id == gw_ds.id)
                .values(status="gateway_offline", updated_at=now)
            )
            # 批量级联子设备
            await db.execute(
                update(DataSource)
                .where(
                    DataSource.parent_datasource_id == gw_ds.id,
                    DataSource.status != "gateway_offline",
                )
                .values(status="gateway_offline", updated_at=now)
            )
```

**3. 网关恢复时子设备恢复为 disconnected 而非 connected（R1#10）：**
子设备可能在网关故障前已经是 device_offline 状态。网关恢复后标记为 disconnected，等待各自下次采集确认真实状态。

**4. communication_monitor 预加载父状态（R1#5 + R2#7 安全访问）：**
```python
parent_ids = {ds.parent_datasource_id for ds in datasources if ds.parent_datasource_id is not None}
parent_status_map = {}
if parent_ids:
    parent_result = await session.execute(
        select(DataSource.id, DataSource.status).where(DataSource.id.in_(parent_ids))
    )
    parent_status_map = {r.id: r.status for r in parent_result.fetchall()}

# R2#7: 使用 .get() 避免 KeyError（父 DataSource 可能已被删除）
# parent_status = parent_status_map.get(ds.parent_datasource_id)
# if parent_status is None → 父已删除，按普通设备处理
```

**5. 竞态处理策略（R1#4）：**
两个循环无需加锁，gateway_offline 覆盖 device_offline 是期望行为。`parent_status_map` 在循环开始时快照，30s 周期内的少量滞后可接受。

### 网关 DataSource 识别方式（含 R2#5 空值过滤）

```python
from sqlalchemy import distinct
gw_ids_result = await db.execute(
    select(distinct(DataSource.parent_datasource_id))
    .where(DataSource.parent_datasource_id.isnot(None))
)
gateway_ids = [r[0] for r in gw_ids_result.fetchall()]
if not gateway_ids:
    return  # 无 MS/TP 网关配置，跳过

# 加载网关 DataSource 对象（R2#5: 已删除的网关自然被过滤）
gw_result = await db.execute(
    select(DataSource).where(DataSource.id.in_(gateway_ids))
)
gateway_datasources = gw_result.scalars().all()
if not gateway_datasources:
    return  # 所有引��的网关均已删除
```

### 定时任务注册

参照 `main.py:451` 的 `_communication_monitor_loop` 模式：
```python
# 启动 MS/TP 网关健康检查（每 30 秒）— Story 35.2
async def _mstp_gateway_health_loop():
    while True:
        await asyncio.sleep(30)
        try:
            async with async_session() as session:
                await check_mstp_gateway_health(session)
        except Exception as e:
            logger.warning("MS/TP 网关健康检查失败: %s", e)

mstp_health_task = asyncio.create_task(_mstp_gateway_health_loop())
```

放在 `comm_monitor_task` 之后（约 line 462），在 yield 前。**shutdown 时必须显式 cancel**：
```python
mstp_health_task.cancel()
```

### 需修改的文件清单

| 文件 | 修改内容 |
|------|---------|
| `backend/app/services/gateway_monitor.py` | 新增 `check_mstp_gateway_health()` 和 `_probe_gateway()` |
| `backend/app/services/communication_monitor.py` | 预加载父状态 + device_offline/gateway_offline 兼容 |
| `backend/app/main.py` | 注册+shutdown cancel `_mstp_gateway_health_loop` |
| `backend/tests/services/test_mstp_gateway_health.py` | 新建测试文件 |

### 不需要修改的文件

- `gateway/scheduler.py` — 不直接处理 MS/TP 网关状态
- `gateway/adapters/bacnet_ip.py` — 仅调用 test_connection()
- `backend/app/models/gateway.py` — status 是 String 无枚举约束
- `backend/app/api/v1/datasources.py` — Story 35.3 处理前端展示

### 测试策略

测试中 mock BacnetIpAdapter，不做真实 BACnet 网络探测：
```python
# 在测试中 mock adapter
from unittest.mock import AsyncMock, patch

@patch("app.services.gateway_monitor.BacnetIpAdapter")
async def test_gateway_offline_cascade(MockAdapter, async_db):
    mock_adapter = MockAdapter.return_value
    mock_adapter.connect = AsyncMock(return_value=False)  # 连接失败
    mock_adapter.disconnect = AsyncMock()
    # ... 验证级联逻辑
```

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Epic 35 Story 35.2]
- [Source: _bmad-output/planning-artifacts/architecture.md#Section 24.3]
- [Source: backend/app/services/gateway_monitor.py — record_status_change 模式]
- [Source: backend/app/services/communication_monitor.py — check_communication_status 模式]
- [Source: backend/app/main.py:451-461 — 定时任务注册模式]

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6

### Debug Log References
- SQLAlchemy synchronize_session="evaluate" 导致 ORM identity map 被 Core UPDATE 同步 → 使用 pre_probe_status 缓存旧状态

### Completion Notes List
- R1 审查修正 11 项，R2 边缘用例修正 8 项
- 代码审查后修正：import 移到模块顶部、注释修正、定时任务初始延迟错开(45s)
- 10 个测试全部通过（6 新 + 4 回归）

### File List
- `backend/app/services/gateway_monitor.py` — 新增 _probe_gateway() + check_mstp_gateway_health()
- `backend/app/services/communication_monitor.py` — 预加载 parent_status_map + device_offline/gateway_offline 逻辑
- `backend/app/main.py` — 注册 _mstp_gateway_health_loop + shutdown cancel
- `backend/tests/services/test_mstp_gateway_health.py` — 6 个测试用例
