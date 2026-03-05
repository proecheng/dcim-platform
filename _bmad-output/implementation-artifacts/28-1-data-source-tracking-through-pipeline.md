# Story 28.1: 数据来源标记贯穿统一管道（方案 G）

Status: done

## Story

As a 运维工程师,
I want 所有监控数据和告警都标记了数据来源,
So that 我能区分哪些是 demo 模拟数据、哪些是真实网关采集数据，在真实环境中过滤掉 demo 数据。

## Acceptance Criteria (验收标准)

1. **AC-1: 数据库 source 列** — Point 表新增 `source: VARCHAR(20)` 列（默认 "manual"）；PointDataLatest 表新增 `source: VARCHAR(20)` 列（默认 "unknown"）；PointHistory 表新增 `source: VARCHAR(20)` 列（默认 "unknown"）；PointRealtime 表新增 `source: VARCHAR(20)` 列（默认 "unknown"）。
2. **AC-2: Alarm 表 data_source 列** — Alarm 表新增 `data_source: VARCHAR(20)` 列（默认 "unknown"），告警创建时记录触发数据的 `IngestPoint.source` 值。
3. **AC-3: 管道 Phase 1 传递 source** — `_batch_upsert_realtime()`、`_batch_upsert_latest()`、`_batch_insert_history()` 写入 DB 时传递 `IngestPoint.source`。
4. **AC-4: 管道 Phase 2 传递 source** — 告警评估流程中（`ingest_pipeline.py` 第435-444行 Alarm 构造），新建 Alarm 记录时将触发数据的 `source` 写入 `Alarm.data_source`。
5. **AC-5: 管道 Phase 3 传递 source** — `_broadcast_realtime()` WS 消息体增加 `source` 字段；`_update_redis_cache()` Redis JSON 增加 `source` 字段。
6. **AC-6: history_generator 标记** — `history_generator.py` 写入 PointHistory 时标记 `source="demo_backfill"`，并在文件头部注释说明绕过 `process_payload` 的原因。
7. **AC-7: API 过滤支持** — 告警列表 API `/api/v1/alarms` 支持 `?data_source=demo` 查询参数；历史数据 API 支持 `?source=mqtt` 查询参数。前端告警列表页（`views/alarm/index.vue`）新增"来源"列和"来源"筛选下拉框。
8. **AC-8: Alembic 迁移与数据修正** — 迁移脚本正确添加新列，使用 `batch_alter_table` 兼容 SQLite。迁移后执行 data migration：将已有 demo 创建的 Point 记录 source 更新为 "demo"（通过 demo seed 的标识逻辑判断）。
9. **AC-9: Pydantic Schema 更新** — `AlarmInfo` 响应模型包含 `data_source` 字段，`HistoryResponse` 包含 `source` 字段，确保 API 返回值包含来源信息。

## Tasks / Subtasks (任务分解)

- [ ] Task 1: 数据库模型增加 source 列 (AC: #1, #2)
  - [ ] 1.1 修改 `backend/app/models/point.py`，Point 模型（第11-51行）增加：
    ```python
    source = Column(String(20), default="manual", server_default="manual")
    ```
  - [ ] 1.2 修改 `backend/app/models/point.py`，PointRealtime 模型（第54-69行）增加：
    ```python
    source = Column(String(20), default="unknown", server_default="unknown")
    ```
  - [ ] 1.3 修改 `backend/app/models/history.py`，PointHistory 模型（第11-28行）增加：
    ```python
    source = Column(String(20), default="unknown", server_default="unknown")
    ```
  - [ ] 1.4 修改 `backend/app/models/gateway.py`，PointDataLatest 模型（第103-115行）增加：
    ```python
    source = Column(String(20), default="unknown", server_default="unknown")
    ```
  - [ ] 1.5 修改 `backend/app/models/alarm.py`，Alarm 模型（第31-68行）增加：
    ```python
    data_source = Column(String(20), default="unknown", server_default="unknown")
    ```
  - [ ] 1.6 **注意**：所有新列使用 `server_default` 且**不加** `nullable=False`，确保 SQLite `ALTER TABLE ADD COLUMN` 兼容

- [ ] Task 2: Alembic 迁移脚本 (AC: #8)
  - [ ] 2.1 执行 `cd backend && alembic revision --autogenerate -m "add source tracking columns"`
  - [ ] 2.2 **手动修改**生成的迁移脚本，使用 `batch_alter_table` 模式确保 SQLite 兼容：
    ```python
    def upgrade() -> None:
        # SQLite 兼容：使用 batch mode
        with op.batch_alter_table('points') as batch_op:
            batch_op.add_column(sa.Column('source', sa.String(20), server_default='manual'))
        with op.batch_alter_table('point_realtime') as batch_op:
            batch_op.add_column(sa.Column('source', sa.String(20), server_default='unknown'))
        with op.batch_alter_table('point_history') as batch_op:
            batch_op.add_column(sa.Column('source', sa.String(20), server_default='unknown'))
        with op.batch_alter_table('point_data_latest') as batch_op:
            batch_op.add_column(sa.Column('source', sa.String(20), server_default='unknown'))
        with op.batch_alter_table('alarms') as batch_op:
            batch_op.add_column(sa.Column('data_source', sa.String(20), server_default='unknown'))

        # Data migration: 现有 demo 点位的 source 修正
        # 安全条件：仅在全量 demo 数据库中执行（无真实网关点位时）
        # 通过检查是否存在 source!='manual' 的记录判断是否有真实数据
        op.execute("""
            UPDATE points SET source = 'demo'
            WHERE source = 'manual'
            AND NOT EXISTS (
                SELECT 1 FROM point_data_latest WHERE gateway_id IS NOT NULL
            )
        """)
    ```
  - [ ] 2.3 **data migration 安全性**：上述 SQL 仅在数据库没有真实网关数据时执行全量更新。如果已有真实网关接入的环境重放迁移，EXISTS 子查询会阻止错误更新。开发者在非纯 demo 环境中需手动确认迁移结果。
  - [ ] 2.4 如果需要与 Story 28.4 的 `is_demo` 列合并迁移，在同一个迁移文件中处理
  - [ ] 2.4 执行 `alembic upgrade head` 验证迁移成功
  - [ ] 2.5 验证迁移后：Point 行 source="demo"，其余表新列使用默认值
  - [ ] 2.6 验证 `alembic downgrade -1` 回滚正确

- [ ] Task 3: IngestPipeline Phase 1 — 写 DB 传递 source (AC: #3)
  - [ ] 3.1 修改 `backend/app/services/ingest_pipeline.py` 的 `_batch_upsert_realtime()`（实际位置：第207-290行）：
    - 在 INSERT 语句中增加 `source` 列
    - 在 UPDATE SET 中使用 SQLite 语法 `source = excluded.source`（项目使用 SQLite，不用 MySQL 的 `VALUES(source)`）
    - 从 `IngestPoint.source` 获取值
  - [ ] 3.2 修改 `_batch_upsert_latest()`（实际位置：第292-346行）：
    - 同上，INSERT/UPDATE 中传递 source
  - [ ] 3.3 修改 `_batch_insert_history()`（实际位置：第348行起）：
    - INSERT 语句中增加 `source` 列
    - 从 `IngestPoint.source` 获取值

- [ ] Task 4: IngestPipeline Phase 2 — 告警 source (AC: #4)
  - [ ] 4.1 定位 Alarm 构造代码：`backend/app/services/ingest_pipeline.py` 第435-444行：
    ```python
    alarm = Alarm(
        alarm_no=alarm_no,
        point_id=pt.point_id,
        threshold_id=triggered.threshold_id,
        alarm_level=triggered.alarm_level,
        alarm_type="communication" if is_comm_suspect else "threshold",
        alarm_message=alarm_msg,
        trigger_value=pt.value,
        threshold_value=triggered.threshold_value,
    )
    ```
  - [ ] 4.2 在 Alarm 构造中添加 `data_source=pt.source`（pt 是当前处理的 IngestPoint）
  - [ ] 4.3 确认 `pt` 变量在告警创建上下文中可访问（检查函数签名和参数传递链）

- [ ] Task 5: IngestPipeline Phase 3 — WS 和 Redis (AC: #5)
  - [ ] 5.1 修改 `_broadcast_realtime()`（实际位置：第586-601行）：
    - 在 WebSocket 消息 payload 中增加 `"source": point.source` 字段
  - [ ] 5.2 修改 `_update_redis_cache()`（实际位置：第603-636行）：
    - 在缓存的 JSON 对象中增加 `"source": point.source` 字段

- [ ] Task 6: history_generator 标记 (AC: #6)
  - [ ] 6.1 修改 `backend/app/services/history_generator.py`
  - [ ] 6.2 在 `generate_point_history()`（约第71-125行）创建 PointHistory 记录时添加 `source="demo_backfill"`：
    ```python
    PointHistory(point_id=point.id, value=value, recorded_at=record_time, source="demo_backfill")
    ```
  - [ ] 6.3 在文件头部添加注释：
    ```python
    # 历史数据生成器直接写入 PointHistory，绕过 process_payload()
    # 原因：历史回填不应触发告警评估和 WebSocket 推送
    # source 标记为 "demo_backfill" 以区分于实时管道数据
    ```
  - [ ] 6.4 检查能耗模型写入（EnergyHourly/EnergyDaily/EnergyMonthly/PUEHistory/Demand15MinData 等）：这些表当前**不添加 source 列**（能耗数据只有 demo 生成路径，没有真实数据路径，添加 source 列在 demo 数据隔离 Story 28.4 的 is_demo 标记中处理更合适）

- [ ] Task 7: Demo 种子数据标记 (关联)
  - [ ] 7.1 修改 `backend/app/demo/service.py` 中创建 Point 的逻辑，设置 `source="demo"`
  - [ ] 7.2 检查 `backend/app/demo/seeds/` 中的种子文件，确保 Point 创建时传递 `source="demo"`
  - [ ] 7.3 DemoEngine 发送 IngestPoint 时确认 `source="demo"`（当前 engine.py:148 已有）

- [ ] Task 8: Pydantic Schema 更新 (AC: #9)
  - [ ] 8.1 修改 `backend/app/schemas/alarm.py`，在 `AlarmInfo`（或 `AlarmResponse`）中增加：
    ```python
    data_source: Optional[str] = None
    ```
  - [ ] 8.2 修改 `backend/app/schemas/history.py`（或 `backend/app/schemas/point.py` 中的历史响应模型），增加：
    ```python
    source: Optional[str] = None
    ```
  - [ ] 8.3 确认 Pydantic 模型的 `model_config` 或 `orm_mode = True` 能自动从 ORM 对象读取新字段

- [ ] Task 9: API 过滤参数 (AC: #7)
  - [ ] 9.1 修改 `backend/app/api/v1/alarm.py` 的告警列表端点（实际位置：第42-54行参数定义）：
    - 新增可选查询参数 `data_source: Optional[str] = Query(None, description="数据来源过滤: demo/mqtt/bridge")`
    - 在查询中添加 `if data_source: query = query.filter(Alarm.data_source == data_source)`
  - [ ] 9.2 修改历史数据 API 端点。先查找具体文件：在 `backend/app/api/v1/` 下搜索 `PointHistory` 或 `point_history` 引用。可能的文件为 `history.py`、`point.py` 或 `energy.py`。定位后：
    - 新增可选查询参数 `source: Optional[str] = Query(None)`
    - 在查询中添加 `if source: query = query.filter(PointHistory.source == source)`

- [ ] Task 10: 前端告警列表页增加来源显示 (AC: #7)
  - [ ] 10.1 修改 `frontend/src/api/modules/alarm.ts`，在请求参数类型中增加 `data_source?: string`
  - [ ] 10.2 修改 `frontend/src/views/alarm/index.vue`：
    - 在筛选区增加"来源"下拉框（el-select，选项：全部/demo/mqtt/bridge/unknown）
    - 在表格中增加"来源"列（el-table-column），显示 `data_source` 字段
    - 查询 API 时传递 `data_source` 参数
  - [ ] 10.3 来源列使用 el-tag 样式区分：demo=warning, mqtt=success, bridge=info, unknown=default

- [ ] Task 11: 后端测试
  - [ ] 11.1 测试 IngestPipeline：构造 `IngestPoint(source="mqtt")` 调用 `process_payload()`，验证 PointHistory/PointRealtime/PointDataLatest 的 source 字段正确写入
  - [ ] 11.2 测试 IngestPipeline：构造 `IngestPoint(source="demo")` 触发告警，验证 Alarm.data_source 为 "demo"
  - [ ] 11.3 测试告警 API：调用 `GET /api/v1/alarms?data_source=demo`，验证仅返回 demo 来源的告警
  - [ ] 11.4 测试历史 API：调用历史查询端点带 `?source=mqtt`，验证过滤正确
  - [ ] 11.5 测试迁移：验证 `alembic upgrade head` 和 `alembic downgrade -1` 往返正确
  - [ ] 11.6 测试 data migration：验证迁移后已有 Point 的 source 为 "demo" 而非 "manual"

- [ ] Task 12: 构建验证
  - [ ] 12.1 `cd backend && pytest tests/` 确认所有现有测试通过
  - [ ] 12.2 `cd frontend && npm run build` 确认前端构建成功
  - [ ] 12.3 启动后端服务，确认 demo 模拟器正常运行
  - [ ] 12.4 通过 Swagger UI 验证告警列表 API 的 `data_source` 参数可用
  - [ ] 12.5 在前端告警列表页验证"来源"列和筛选器正常工作

## Dev Notes (开发指南)

### 现有代码结构

**IngestPoint 类** (`ingest_pipeline.py`, 第35-46行)：
```python
@dataclass
class IngestPoint:
    point_id: int
    value: float
    source: str = "unknown"  # demo/mqtt/bridge/unknown
    # ... 其他字段
```
`source` 字段已存在但在后续流程中被完全忽略。

**数据写入三阶段**（`ingest_pipeline.py`）：
- Phase 1（第207-348+行）：写 DB — `_batch_upsert_realtime()`(207-290), `_batch_upsert_latest()`(292-346), `_batch_insert_history()`(348+) — 全部未传 source
- Phase 2（第435-444行）：告警创建 — `Alarm()` 构造时未记录来源
- Phase 3（第586-636行）：WS 推送 `_broadcast_realtime()`(586-601) + Redis 缓存 `_update_redis_cache()`(603-636) — 全部未传 source

**ORM 模型现状**：
- `Point` (point.py:11-51) — 无 source 列
- `PointRealtime` (point.py:54-69) — 无 source 列
- `PointHistory` (history.py:11-28) — 无 source 列
- `PointDataLatest` (gateway.py:103-115) — 有 `gateway_id` 但无统一 source
- `Alarm` (alarm.py:31-68) — 无 data_source 列

**history_generator.py**（约175行）：
- `generate_point_history()`：直接写 PointHistory，绕过 `process_payload()`
- 当前创建记录：`PointHistory(point_id=point.id, value=value, recorded_at=record_time)` — 无 source

### source 枚举值定义

| source 值 | 含义 | 使用场景 |
|-----------|------|---------|
| `demo` | Demo 模拟器实时数据 | DemoEngine 每60秒一轮 |
| `demo_backfill` | Demo 历史数据回填 | history_generator 批量生成 |
| `mqtt` | MQTT 网关真实数据 | MQTTClient 事件驱动 |
| `bridge` | 数据源桥接 | DataSourceBridge 轮询 |
| `manual` | 用户手动录入 | API 创建点位时的默认值 |
| `unknown` | 来源不明 | 迁移前已有数据的默认值 |

### SQLite 兼容性注意

SQLite 的 `ALTER TABLE ADD COLUMN` 限制：
- 不支持 `NOT NULL` 约束（除非有 `DEFAULT` 值）
- **必须使用 `batch_alter_table` 模式**确保所有操作兼容
- ORM 模型中**不加** `nullable=False`，仅用 `server_default` 提供默认值
- Alembic autogenerate 可能生成不兼容语法，**必须手动检查并修改**

### Data Migration 注意

现有数据库中的 Point 全部由 demo seed 创建。迁移后 `server_default='manual'` 会将这些点位标记为 "manual"，与事实不符。因此迁移脚本中必须包含 `UPDATE points SET source = 'demo' WHERE source = 'manual'` 的数据修正步骤。

### 能耗表 source 列决策

EnergyHourly/EnergyDaily/EnergyMonthly/PUEHistory/Demand15MinData 等能耗汇总表当前**不在本 Story 范围**添加 source 列。原因：
1. 能耗数据目前只有 demo 生成路径，没有真实数据写入路径
2. 能耗数据的隔离将在 Story 28.4 中通过 `is_demo` 标记统一处理
3. 未来真实能耗数据接入时，可在对应 Story 中补充 source 列

### 与 Story 28.4 的迁移协调

Story 28.4 需要在 17 个表上添加 `is_demo` 列。如果两个 Story 同时开发：
- **推荐**：合并为一个迁移脚本，避免迁移冲突
- 或确保各自迁移脚本的 revision 链正确连接（28.1 先，28.4 后）

### 执行顺序与并行开发说明

本 Story 与 Story 27.1 可并行开发：
- **28.1 修改**：后端 Models/Pipeline/API + 前端 `views/alarm/index.vue`（Task 10 新增来源列）+ 前端 `api/modules/alarm.ts`（新增 data_source 参数）
- **27.1 修改**：前端 Store/Composable/Views（不修改 `views/alarm/index.vue` 代码，仅检查确认）

**唯一交叉点**：`views/alarm/index.vue` — 27.1 的 Task 6 仅检查不修改该文件，28.1 的 Task 10 在该文件新增列和筛选器。**无合并冲突风险**。

**类型预留**：Story 27.1 Task 7 已在 Alarm/AlarmInfo 接口中预留 `data_source?: string` 可选字段，28.1 后端就绪后前端自动消费，无需额外修改。

### 参考文档

- `docs/demo-system-audit.md` — D-1 数据来源标记创建即丢弃、D-5 历史生成器绕过管道
- `architecture.md` Section 20 — Demo 系统与数据隔离规范
