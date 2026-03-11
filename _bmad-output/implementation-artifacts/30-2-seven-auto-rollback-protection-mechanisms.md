# Story 30.2: 7 项自动回退保护机制

Status: done

## Story

As a 系统运维人员,
I want 系统在检测到异常条件时自动回退制冷操作,
So that 数据中心设备安全不受威胁。

## 依赖

- Story 30.1（约束检查引擎）— done
  - 提供 `check_all_constraints`、`_get_max_inlet_temperature`、`_load_constraint_config`
  - 提供 `ConstraintType`、`ConstraintViolation` 数据结构

## Acceptance Criteria

1. Given 预冷或负荷转移操作正在进行
   When 检测到以下任一条件
   Then 触发对应自动回退动作：
   - 条件1: 任一机柜 T_inlet > 26°C → 恢复正常制冷
   - 条件2: 温升速率超预测 150% → 恢复正常制冷
   - 条件3: 温度变化超 5°C/h → 限制功率调整速度
   - 条件4: 空调故障告警 → 停止功率转移
   - 条件5: 温度传感器离线 → 切回固定保守比例 0.2
   - 条件6: 市电中断切 UPS → T_max 收紧到 25°C
   - 条件7: 预冷时湿度接近露点 → 停止降温防结露

2. Given 回退触发条件消失
   When 安全状态持续满足恢复条件一段时间
   Then 自动恢复到正常模式：
   - 温度回退（条件1/2）：温度裕度 > 4°C 持续 15 分钟后恢复
   - 传感器回退（条件5）：传感器恢复正常且数据稳定 10 分钟后恢复
   - UPS 回退（条件6）：市电恢复且 UPS 稳定 5 分钟后恢复
   - 空调故障回退（条件4）：告警清除且运行稳定 10 分钟后恢复
   - 湿度回退（条件7）：送风温度与露点温差 > 5°C 持续 10 分钟后恢复

3. Given 回退事件发生
   When 回退管理器执行回退/恢复动作
   Then 每次事件记录完整上下文到 `rollback_events` 表
   - 包含：触发条件、当前温度/值、回退动作、zone_id、时间戳

4. Given 回退事件发生
   When 回退管理器执行回退/恢复动作
   Then 事件通过告警 WebSocket 通道推送通知
   - 使用 `ws_manager.broadcast_alarm()` 推送

5. Given 系统启动
   When 后台监控任务启动
   Then 通过 asyncio 后台任务持续监控所有活跃 CoolingZone
   - 检测周期 ≤ 10 秒
   - 遵循 main.py 中已有的 asyncio.create_task 模式

6. Given 回退保护正在生效
   When 查询回退状态
   Then 可获取每个 zone 的当前回退状态和活跃回退条件列表

## Tasks / Subtasks

- [x] Task 1: 创建回退事件数据模型 (AC: #3)
  - [x] 1.1 定义 `RollbackEvent` 表（zone_id, trigger_type, trigger_value, threshold, action, status, context_json, created_at, resolved_at）
  - [x] 1.2 定义 `RollbackTriggerType` 枚举（7 种触发类型）
  - [x] 1.3 创建 Alembic migration 文件（命名模式: `YYYYMMDD_HHMM_story_30_2_rollback_events.py`）

- [x] Task 2: 创建回退保护管理器 `rollback_manager.py` (AC: #1, #2, #6)
  - [x] 2.1 定义 `RollbackManager` 类（管理 zone 回退状态、检测循环）
  - [x] 2.2 实现 7 项触发检测方法（复用 constraints.py 的温度/速率查询）
  - [x] 2.3 实现回退动作执行（更新 zone 状态标记，记录事件）
  - [x] 2.4 实现 5 项自动恢复条件检测
  - [x] 2.5 实现 `get_zone_rollback_status(zone_id)` 查询当前状态

- [x] Task 3: 集成 asyncio 后台监控任务 (AC: #5)
  - [x] 3.1 在 `main.py` lifespan 中添加回退监控循环（10 秒间隔）
  - [x] 3.2 查询所有活跃 CoolingZone，对每个 zone 执行检测

- [x] Task 4: 集成告警 WebSocket 推送 (AC: #4)
  - [x] 4.1 回退触发时通过 `ws_manager.broadcast_alarm()` 推送事件
  - [x] 4.2 恢复时同样推送通知

- [x] Task 5: 编写单元测试 (AC: #1-#6)
  - [x] 5.1 7 项触发条件检测测试（每个条件正常/触发两个用例）
  - [x] 5.2 自动恢复条件测试
  - [x] 5.3 回退事件记录测试
  - [x] 5.4 状态查询测试

## Dev Notes

### 架构约束

- **新建文件**: `backend/app/services/precool/rollback_manager.py` — 回退保护管理器
- **新建文件**: `backend/app/models/rollback.py` — RollbackEvent 数据模型
- **新建文件**: `backend/alembic/versions/YYYYMMDD_HHMM_story_30_2_rollback_events.py` — 数据库迁移
- **修改文件**: `backend/app/main.py` — 添加 asyncio 后台监控任务 + rollback 配置初始化
- **新建文件**: `backend/tests/services/precool/test_rollback_manager.py` — 单元测试

### RollbackEvent 数据模型

```python
# backend/app/models/rollback.py

class RollbackTriggerType(str, Enum):
    TEMP_OVER_LIMIT = "temp_over_limit"           # 条件1: T_inlet > 26°C
    RATE_OVER_PREDICTED = "rate_over_predicted"    # 条件2: 温升超预测 150%
    RATE_OVER_LIMIT = "rate_over_limit"            # 条件3: |dT/dt| > 5°C/h
    AC_FAULT = "ac_fault"                          # 条件4: 空调故障
    SENSOR_OFFLINE = "sensor_offline"              # 条件5: 传感器离线
    UPS_ACTIVE = "ups_active"                      # 条件6: 市电中断切 UPS
    HUMIDITY_DEW_POINT = "humidity_dew_point"       # 条件7: 湿度接近露点

class RollbackEvent(Base):
    __tablename__ = "rollback_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    zone_id = Column(Integer, ForeignKey("cooling_zones.id"), nullable=False)
    trigger_type = Column(String(30), nullable=False)   # RollbackTriggerType 值
    trigger_value = Column(Float)                       # 触发时的实际值
    threshold = Column(Float)                           # 阈值
    action = Column(String(100), nullable=False)        # 执行的回退动作描述
    status = Column(String(20), default="active")       # active / resolved
    context_json = Column(Text)                         # JSON: 附加上下文（温度、功率等）
    created_at = Column(DateTime, default=func.now())
    resolved_at = Column(DateTime, nullable=True)
```

### RollbackManager 核心设计

```python
class RollbackManager:
    """回退保护管理器 — 持续监控 CoolingZone 安全状态"""

    def __init__(self):
        # 内存中维护每个 zone 的回退状态
        # {zone_id: {trigger_type: {"active": bool, "since": datetime, "event_id": int, "recovery_start": datetime|None}}}
        self._zone_states: Dict[int, Dict[str, dict]] = {}

    async def check_zone(self, zone_id: int, session: AsyncSession):
        """对单个 zone 执行全部 7 项检测 + 已触发项的恢复检测"""
        ...

    async def _check_temp_over_limit(self, zone_id, session) -> Optional[dict]:
        """条件1: 复用 _get_max_inlet_temperature，阈值 26°C（T_max - 1°C 预警线）"""
        ...

    async def _check_rate_over_predicted(self, zone_id, session) -> Optional[dict]:
        """条件2: 比较实际温升 vs SystemConfig 基准温升"""
        ...

    async def _check_rate_over_limit(self, zone_id, session) -> Optional[dict]:
        """条件3: 复用 check_rate_of_change"""
        ...

    async def _check_ac_fault(self, zone_id, session) -> Optional[dict]:
        """条件4: CoolingZoneUnit → CoolingUnit → Device → Point(device_type='AC') → PointRealtime(status='fault'/'alarm')"""
        ...

    async def _check_sensor_offline(self, zone_id, session) -> Optional[dict]:
        """条件5: CoolingZoneCabinet → CabinetTemperatureSensor(inlet) → Point → PointRealtime(status='offline')
        注意：与 constraints._get_max_inlet_temperature 返回 None 的语义不同。
        constraints 中 None = 无数据不违规；这里 None 可能是传感器离线需要检查 PointRealtime.status"""
        ...

    async def _check_ups_active(self, zone_id, session) -> Optional[dict]:
        """条件6: 查询 UPS 点位状态（若无 UPS 点位数据则跳过）"""
        ...

    async def _check_humidity_dew_point(self, zone_id, session) -> Optional[dict]:
        """条件7: 查询 TH 点位湿度值，计算露点（若无 TH 数据则跳过）"""
        ...

    async def _try_recovery(self, zone_id, trigger_type, session):
        """检查是否满足恢复条件，使用 recovery_start 时间窗口"""
        ...

    def get_zone_rollback_status(self, zone_id: int) -> dict:
        """返回 zone 当前回退状态"""
        ...

# 模块级全局实例
rollback_manager = RollbackManager()
```

### 7 项触发条件的数据源

| 条件 | 检测方法 | 数据源 |
|------|---------|--------|
| 1. T_inlet > 26°C | 复用 `constraints._get_max_inlet_temperature` | CoolingZoneCabinet → CabinetTemperatureSensor(inlet) → PointHistory |
| 2. 温升超预测 150% | `_calculate_temperature_rise_rate` vs `SystemConfig.rollback_predicted_rate` | PointHistory 温度 + SystemConfig 基准值 |
| 3. \|dT/dt\| > 5°C/h | 复用 `constraints.check_rate_of_change` | 同 constraints.py |
| 4. 空调故障 | CoolingZoneUnit → CoolingUnit(device_id) → Device → Point(device_type='AC') → PointRealtime(status) | 检查 status 为 'alarm' 或 'fault' |
| 5. 传感器离线 | CoolingZoneCabinet → CabinetTemperatureSensor(inlet) → Point → PointRealtime(status) | 检查 status 为 'offline' |
| 6. UPS 供电 | Point(device_type='UPS', point_type='DI') → PointRealtime.value | 0=市电, 1=电池模式（若无 UPS 点位则跳过） |
| 7. 湿度接近露点 | Point(device_type='TH') → PointRealtime.value | Magnus 公式计算露点（若无 TH 点位则跳过） |

### 条件 2 特殊处理

条件 2（温升超预测 150%）需要"预测温升"基准值。当前系统无预冷计划调度（Epic 31 的内容），且 CoolingLinkageConfig **没有** `predicted_rate` 字段。因此：
- **当前实现**: 使用 `_calculate_temperature_rise_rate` 获取实际温升速率，与 SystemConfig 配置的基准温升速率（默认 2.0°C/h，配置键 `rollback_predicted_rate`）比较
- **在 `main.py` 初始化中添加**: `rollback_predicted_rate: "2.0"` 到 SystemConfig
- **判断逻辑**: 若实际温升 > 基准值 × 1.5，则触发回退
- **未来扩展**: Epic 31 实现预冷调度后，基准值改为实际预测值

### 条件 6/7 的数据可用性

- **条件 6 (UPS 状态)**: 项目中 UPS 设备通过 `Point(device_type='UPS')` 建模。UPS 在线/电池模式可通过 DI 类型点位的值判断（0=市电, 1=电池模式）。若无 UPS 点位数据，该条件跳过不检测。
- **条件 7 (湿度/露点)**: 温湿度传感器 `Point(device_type='TH')` 有湿度值。露点由 Magnus 公式计算：`Td = (243.04 × (ln(RH/100) + 17.625×T/(243.04+T))) / (17.625 - (ln(RH/100) + 17.625×T/(243.04+T)))`。若无 TH 点位数据，该条件跳过。

### 自动恢复的时间窗口管理

恢复条件通过 `_zone_states` 内存字典中的 `recovery_start` 时间戳实现：
1. 首次检测到触发条件消失时，记录 `recovery_start = datetime.now()`
2. 后续检测中，若条件仍然消失且 `now - recovery_start >= 恢复等待时间`，执行恢复
3. 若恢复期间条件再次出现，清除 `recovery_start`（重新计时）

### asyncio 后台任务集成

参照 `main.py` 中已有的后台任务模式：

```python
# main.py lifespan 中添加
async def _rollback_monitor_loop():
    """回退保护监控循环 — 每 10 秒检查所有活跃 zone"""
    from app.services.precool.rollback_manager import rollback_manager
    from app.core.database import async_session
    from app.models.topology_config import CoolingZone

    await asyncio.sleep(15)  # 等待其他服务初始化
    logger.info("🛡️ 回退保护监控已启动")

    while True:
        try:
            async with async_session() as session:
                # CoolingZone 无 is_active 字段，查询所有 zone
                zones = (await session.execute(
                    select(CoolingZone.id)
                )).scalars().all()

                for zone_id in zones:
                    try:
                        await rollback_manager.check_zone(zone_id, session)
                    except Exception as e:
                        logger.error(f"Zone {zone_id} 回退检测异常: {e}")

                await session.commit()
        except Exception as e:
            logger.error(f"回退监控循环异常: {e}")

        await asyncio.sleep(10)

rollback_task = asyncio.create_task(_rollback_monitor_loop())
```

### WebSocket 告警推送格式

```python
await ws_manager.broadcast_alarm({
    "action": "rollback",         # 或 "rollback_recovery"
    "id": event.id,
    "zone_id": zone_id,
    "trigger_type": trigger_type,
    "trigger_value": trigger_value,
    "threshold": threshold,
    "rollback_action": action_description,
    "timestamp": datetime.now().isoformat(),
})
```

### 测试模式

纯 mock 模式（同 test_constraints.py）：
- Mock `AsyncSession` 和 ORM 查询
- Mock `_get_max_inlet_temperature`、`_calculate_temperature_rise_rate` 等
- Mock `ws_manager.broadcast_alarm`
- 使用 `datetime` mock 控制时间推进（测试恢复等待时间）

### CoolingZone 查询方式

CoolingZone 表（`topology_config.py`）**没有** `is_active` 字段。查询所有 zone 使用 `select(CoolingZone.id)`（查所有记录）。
若需过滤"已启用预冷"的 zone，可通过 `CoolingLinkageConfig.precool_enabled == True` 关联查询。

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Epic30-Story30.2] — AC 定义
- [Source: _bmad-output/planning-artifacts/architecture.md#Section21] — 7 项自动回退保护
- [Source: docs/空调可转移功率算法调研与改进方案.md] — 回退触发条件与操作人员速查
- [Source: backend/app/services/precool/constraints.py] — 约束检查引擎（复用）
- [Source: backend/app/services/websocket.py:157] — ws_manager 全局实例
- [Source: backend/app/main.py:411-534] — asyncio 后台任务模式参考
- [Source: backend/app/models/point.py:57-72] — PointRealtime 状态字段
- [Source: backend/app/models/power.py] — UPSDevice 数据模型

### Previous Story Intelligence

**从 Story 30.1 学到的关键经验：**
1. **Lazy import 模式**: 避免循环导入，在函数体内 import
2. **Mock 路径**: mock 原始模块路径（如 `app.services.datacenter_shift_strategy._calculate_temperature_rise_rate`），而非 constraints 模块
3. **错误隔离**: 每个检查独立 try/except，确保一个失败不影响其他
4. **Dev Agent Record**: 实施完成后必须更新 tasks [x]、File List、Change Log

## NFR 追溯

- **NFR-TCL-4**: 回退检测 ≤ 10 秒轮询周期
- **NFR-TCL-6**: 回退响应时间 ≤ 30 秒

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Completion Notes List

- 7 项触发检测全部实现，每项独立 try/except 隔离
- 5 项自动恢复条件实现（温度/速率 15min，传感器/空调/湿度 10min，UPS 5min）
- 条件 2（温升超预测）使用 SystemConfig `rollback_predicted_rate` 默认 2.0°C/h，未来 Epic 31 替换为实际预测值
- 条件 6/7（UPS/湿度）无点位数据时自动跳过不检测
- WebSocket 推送在 try/except 内，推送失败不影响核心回退逻辑
- 修复 Story 30.1 遗留 bug: `constraints.py` 中 `CoolingZoneCabinet.cooling_zone_id` → `zone_id`
- 26 项单元测试全部通过

### Change Log

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/models/rollback.py` | 新建 | RollbackEvent + RollbackTriggerType 数据模型 |
| `backend/alembic/versions/20260311_0100_story_30_2_rollback_events.py` | 新建 | rollback_events 表迁移 |
| `backend/app/services/precool/rollback_manager.py` | 新建 | RollbackManager: 7 项检测 + 触发/恢复 + 状态查询 |
| `backend/app/main.py` | 修改 | 添加回退配置初始化 + asyncio 监控循环(10s) |
| `backend/app/services/precool/constraints.py` | 修改 | 修复 CoolingZoneCabinet.zone_id FK 字段名 |
| `backend/tests/services/precool/test_rollback_manager.py` | 新建 | 26 项单元测试 |

### File List

- `backend/app/models/rollback.py` — RollbackEvent 模型 + RollbackTriggerType 枚举
- `backend/alembic/versions/20260311_0100_story_30_2_rollback_events.py` — Alembic 迁移
- `backend/app/services/precool/rollback_manager.py` — 回退保护管理器（468 行）
- `backend/app/main.py` — asyncio 后台任务 + SystemConfig 初始化
- `backend/app/services/precool/constraints.py` — zone_id FK 修复
- `backend/tests/services/precool/test_rollback_manager.py` — 26 项单元测试
