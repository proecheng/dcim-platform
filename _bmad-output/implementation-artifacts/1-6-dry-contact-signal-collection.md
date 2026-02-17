# Story 1.6: 干接点信号采集

Status: done

## Story

As a 集成工程师,
I want 通过 Modbus I/O 采集模块读取干接点信号,
so that 消防主机和门禁系统的开关量信号可以接入 DCIM。

## Acceptance Criteria (验收标准)

1. **AC-1: 干接点状态变化检测** — gateway 层新增 `DryContactMonitor`，跟踪干接点点位的上一次值，检测 0→1 或 1→0 的状态变化
2. **AC-2: 状态变化事件回调** — 状态变化时通过回调函数通知上层，回调参数包含：`datasource_id`, `point_id`, `old_value`, `new_value`（归一化后）, `raw_old_value`, `raw_new_value`（原始值）, `is_fire_signal: bool`
3. **AC-3: FIRE_SIGNAL 标记** — 干接点点位可通过 `PointConfig` 的扩展字段 `fire_signal` 标记为消防信号，状态变化事件中 `is_fire_signal=True`
4. **AC-4: 调度器集成** — `CollectionScheduler` 在归一化后调用 `DryContactMonitor.check()`，检测干接点状态变化并触发回调
5. **AC-5: 非干接点不受影响** — `DryContactMonitor` 只处理 `is_dry_contact=True` 的点位，其他点位完全跳过
6. **AC-6: 首次采集不触发** — 首次采集时记录初始状态，不触发状态变化事件（避免启动时误报）
7. **AC-7: 数据质量过滤** — 数据质量为 `abnormal` 的读数不更新状态，不触发变化事件

## Tasks / Subtasks (任务分解)

- [x] Task 1: 扩展 PointConfig 支持 fire_signal 标记 (AC: #3)
  - [x] 1.1 在 `gateway/adapters/base.py` 的 `PointConfig` 中新增 `fire_signal: bool = False` 字段
  - [x] 1.2 在 `gateway/config_loader.py` 中解析 `fire_signal` 配置项

- [x] Task 2: 实现 DryContactMonitor (AC: #1, #2, #3, #5, #6, #7)
  - [x] 2.1 在 `gateway/` 中创建 `dry_contact.py`
  - [x] 2.2 实现 `DryContactMonitor` 类，维护 `_last_values: dict[str, Any]` 状态表
  - [x] 2.3 实现 `check(readings: list[NormalizedReading], config: DataSourceConfig) -> list[DryContactEvent]`
  - [x] 2.4 定义 `DryContactEvent` 数据类：`datasource_id`, `point_id`, `old_value`, `new_value`（归一化后）, `raw_old_value`, `raw_new_value`（原始值）, `is_fire_signal`, `timestamp`
  - [x] 2.5 使用 `raw_value` 做状态比较（0/1 整数比较更可靠，避免枚举映射后字符串比较问题）
  - [x] 2.6 首次采集时记录初始 raw_value，返回空列表
  - [x] 2.7 数据质量为 `abnormal` 时跳过该点位
  - [x] 2.8 实现 `reset(datasource_id: str)` 清除指定数据源的状态
  - [x] 2.9 实现 `clear_all()` 清除所有状态

- [x] Task 3: 集成到 CollectionScheduler (AC: #4)
  - [x] 3.1 在 `CollectionScheduler.__init__` 中新增 `on_dry_contact` 回调参数
  - [x] 3.2 在 `__init__` 中创建 `self._dry_contact_monitor = DryContactMonitor()`
  - [x] 3.3 在 `_collection_loop` 中归一化后调用 `DryContactMonitor.check()`
  - [x] 3.4 有状态变化事件时调用 `on_dry_contact` 回调
  - [x] 3.5 在 `remove_datasource` 中调用 `self._dry_contact_monitor.reset(datasource_id)`
  - [x] 3.6 在 `stop()` 中调用 `self._dry_contact_monitor.clear_all()`

- [x] Task 4: 单元测试 (AC: 全部)
  - [x] 4.1 测试 DryContactMonitor — 首次采集不触发
  - [x] 4.2 测试状态变化 0→1 触发事件
  - [x] 4.3 测试状态变化 1→0 触发事件
  - [x] 4.4 测试状态不变不触发
  - [x] 4.5 测试非干接点点位被跳过
  - [x] 4.6 测试 fire_signal 标记传递
  - [x] 4.7 测试 abnormal 质量数据不触发
  - [x] 4.8 测试 reset 清除状态
  - [x] 4.9 测试 clear_all 清除所有状态
  - [x] 4.10 测试事件包含 raw_old_value 和 raw_new_value
  - [x] 4.11 测试 CollectionScheduler 集成 — on_dry_contact 回调被调用
  - [x] 4.12 测试 CollectionScheduler.remove_datasource 调用 reset
  - [x] 4.13 测试 CollectionScheduler.stop 调用 clear_all
  - [x] 4.14 测试 config_loader 解析 fire_signal 字段

## Dev Notes (开发指南)

### 1. 文件位置

```
gateway/adapters/base.py            # 修改 — PointConfig 新增 fire_signal
gateway/config_loader.py            # 修改 — 解析 fire_signal
gateway/dry_contact.py              # 新建 — DryContactMonitor + DryContactEvent
gateway/scheduler.py                # 修改 — 集成 DryContactMonitor
backend/tests/test_dry_contact.py   # 新建 — 单元测试
```

### 2. DryContactEvent 数据类

```python
# gateway/dry_contact.py

from dataclasses import dataclass
from datetime import datetime
from typing import Any

@dataclass
class DryContactEvent:
    """干接点状态变化事件"""
    datasource_id: str
    point_id: str
    old_value: Any          # 归一化后的值（枚举映射后，如 "正常"/"火警"）
    new_value: Any          # 归一化后的值
    raw_old_value: Any      # 原始值（0/1 整数）
    raw_new_value: Any      # 原始值
    is_fire_signal: bool
    timestamp: datetime
```

### 3. DryContactMonitor 核心逻辑

```python
# gateway/dry_contact.py

import logging
from .adapters.base import DataSourceConfig, NormalizedReading, DataQuality, PointConfig

logger = logging.getLogger(__name__)


class DryContactMonitor:
    """干接点状态变化监测器

    使用 raw_value（原始值 0/1）做状态比较，避免枚举映射后字符串比较不可靠。
    事件中同时提供归一化后的值和原始值。
    """

    def __init__(self) -> None:
        # key: "{datasource_id}:{point_id}", value: (last_raw_value, last_value)
        self._last_values: dict[str, tuple[Any, Any]] = {}

    def check(
        self,
        readings: list[NormalizedReading],
        config: DataSourceConfig,
    ) -> list[DryContactEvent]:
        """检测干接点状态变化，返回变化事件列表"""
        point_map = {p.point_id: p for p in config.points}
        events: list[DryContactEvent] = []

        for reading in readings:
            point_config = point_map.get(reading.point_id)
            if not point_config or not point_config.is_dry_contact:
                continue

            # 数据质量异常时跳过
            if reading.quality == DataQuality.ABNORMAL:
                logger.debug(
                    "干接点 %s 数据质量异常，跳过状态检测",
                    reading.point_id,
                )
                continue

            key = f"{reading.datasource_id}:{reading.point_id}"
            last = self._last_values.get(key)

            # 首次采集：记录初始值，不触发事件
            if last is None:
                self._last_values[key] = (reading.raw_value, reading.value)
                logger.info(
                    "干接点 %s 初始状态: raw=%s, value=%s",
                    reading.point_id, reading.raw_value, reading.value,
                )
                continue

            old_raw, old_value = last

            # 用 raw_value 做状态变化检测（0/1 整数比较更可靠）
            if reading.raw_value != old_raw:
                self._last_values[key] = (reading.raw_value, reading.value)
                is_fire = getattr(point_config, 'fire_signal', False)
                event = DryContactEvent(
                    datasource_id=reading.datasource_id,
                    point_id=reading.point_id,
                    old_value=old_value,
                    new_value=reading.value,
                    raw_old_value=old_raw,
                    raw_new_value=reading.raw_value,
                    is_fire_signal=is_fire,
                    timestamp=reading.timestamp,
                )
                events.append(event)
                logger.warning(
                    "干接点状态变化: %s raw=%s→%s value=%s→%s (fire_signal=%s)",
                    reading.point_id, old_raw, reading.raw_value,
                    old_value, reading.value, is_fire,
                )

        return events

    def reset(self, datasource_id: str) -> None:
        """清除指定数据源的所有干接点状态"""
        prefix = f"{datasource_id}:"
        keys_to_remove = [k for k in self._last_values if k.startswith(prefix)]
        for k in keys_to_remove:
            del self._last_values[k]
        if keys_to_remove:
            logger.info("已清除数据源 %s 的 %d 个干接点状态", datasource_id, len(keys_to_remove))

    def clear_all(self) -> None:
        """清除所有干接点状态（调度器停止时调用）"""
        count = len(self._last_values)
        self._last_values.clear()
        if count:
            logger.info("已清除全部 %d 个干接点状态", count)
```

### 4. PointConfig 扩展

```python
# gateway/adapters/base.py — PointConfig 新增字段
@dataclass
class PointConfig:
    """点位采集配置"""
    point_id: str
    address: str
    data_type: str
    scale: float = 1.0
    offset: float = 0.0
    enum_mapping: Optional[dict] = None
    is_dry_contact: bool = False
    fire_signal: bool = False  # 新增：是否消防信号
```

### 5. CollectionScheduler 集成

```python
# gateway/scheduler.py 修改

from .dry_contact import DryContactMonitor, DryContactEvent

# 新增回调类型
OnDryContactCallback = Callable[[list["DryContactEvent"]], Any]

class CollectionScheduler:
    def __init__(
        self,
        on_data: OnDataCallback | None = None,
        on_alarm: OnAlarmCallback | None = None,
        on_dry_contact: OnDryContactCallback | None = None,  # 新增
    ) -> None:
        ...
        self._on_dry_contact = on_dry_contact
        self._dry_contact_monitor = DryContactMonitor()

    # 在 _collection_loop 中，归一化后添加:
    # 干接点状态变化检测
    dc_events = self._dry_contact_monitor.check(readings, config)
    if dc_events and self._on_dry_contact:
        try:
            result = self._on_dry_contact(dc_events)
            if asyncio.iscoroutine(result):
                await result
        except Exception:
            logger.exception("数据源 '%s' 的干接点回调执行失败", ds_id)

    # 在 remove_datasource 中添加:
    self._dry_contact_monitor.reset(datasource_id)

    # 在 stop() 中，清除 tasks/adapters 后添加:
    self._dry_contact_monitor.clear_all()
```

### 6. config_loader 修改

```python
# gateway/config_loader.py — 解析 fire_signal
PointConfig(
    ...
    is_dry_contact=bool(p.get("is_dry_contact", False)),
    fire_signal=bool(p.get("fire_signal", False)),  # 新增
)
```

### 7. 关键约束

- **gateway 模块独立**: DryContactMonitor 在 gateway 层，不依赖 backend
- **不修改 Modbus 适配器**: 干接点信号通过现有 Modbus TCP/RTU 适配器读取 DI 寄存器，DryContactMonitor 只在归一化后做状态变化检测
- **首次不触发**: 避免系统重启时所有干接点都触发一次"变化"事件
- **abnormal 质量过滤**: 通信异常时不应误判为状态变化
- **lazy logging**: 使用 `%s` 格式
- **测试使用 mock**: 不需要真实 Modbus 设备

### 8. 测试策略

```python
# 测试 DryContactMonitor
def test_first_read_no_event():
    """首次采集记录初始值，不触发事件"""
    monitor = DryContactMonitor()
    events = monitor.check(readings, config)
    assert events == []

def test_state_change_triggers_event():
    """状态变化 0→1 触发事件，包含 raw_value 和归一化 value"""
    monitor = DryContactMonitor()
    monitor.check(readings_0, config)  # 首次
    events = monitor.check(readings_1, config)  # 变化
    assert len(events) == 1
    assert events[0].raw_old_value == 0
    assert events[0].raw_new_value == 1
    assert events[0].old_value == "正常"   # 枚举映射后
    assert events[0].new_value == "火警"   # 枚举映射后

# 测试 CollectionScheduler 集成 — mock adapter + on_dry_contact 回调
# 测试 remove_datasource 调用 reset
# 测试 stop 调用 clear_all
```

### Project Structure Notes (项目结构对齐)

- `gateway/dry_contact.py` — 新建，与 `normalizer.py`、`retry.py` 同级
- `gateway/adapters/base.py` — 修改，PointConfig 新增 `fire_signal` 字段
- `gateway/config_loader.py` — 修改，解析 `fire_signal`
- `gateway/scheduler.py` — 修改，集成 DryContactMonitor
- 测试文件放在 `backend/tests/test_dry_contact.py`

### References (参考来源)

- [Source: architecture.md#6.6] 干接点信号处理 — 复用 ModbusRtuAdapter 读取 DI 寄存器
- [Source: architecture.md#7.4] 消防信号最高优先级 — FIRE_SIGNAL 标记
- [Source: epics.md#Story 1.6] Acceptance Criteria — 干接点状态变化触发
- [Source: normalizer.py] 干接点枚举映射已实现
- [Source: scheduler.py] 采集循环 + 回调机制

### Previous Story Intelligence (Story 1.5 经验)

- **CollectionScheduler 回调模式**: `on_data(readings)`, `on_alarm(ds_id, error_msg)` — 支持同步和异步回调
- **DataNormalizer 干接点处理**: 已实现 `is_dry_contact` 优先走枚举映射
- **PointConfig 数据类**: dataclass，新增字段需要有默认值（放在末尾）
- **测试模式**: pytest + asyncio_mode=auto, mock adapter, pythonpath=..

## Dev Agent Record

### Agent Model Used

claude-opus-4-6 (sisyphus-junior)

### Debug Log References

### Completion Notes List

- 25/25 测试通过（20 DryContactMonitor + 4 Scheduler 集成 + 1 ConfigLoader）
- 189/192 全量回归通过，3 个失败为 SNMP 注册测试的预存问题
- 使用 raw_value 做状态比较（C1 修复），事件同时提供归一化值和原始值
- remove_datasource 调用 reset（E1 修复），stop 调用 clear_all（E2 修复）

### File List

- `gateway/adapters/base.py` — 修改：PointConfig 新增 `fire_signal: bool = False`
- `gateway/config_loader.py` — 修改：解析 `fire_signal` 字段
- `gateway/dry_contact.py` — 新建：DryContactMonitor + DryContactEvent（110 行）
- `gateway/scheduler.py` — 修改：集成 DryContactMonitor + on_dry_contact 回调 + reset/clear_all
- `backend/tests/test_dry_contact.py` — 新建：25 个测试

### Story Review (Adversarial) — 2026-02-15

**发现问题:** 1 CRITICAL, 2 ENHANCE, 1 OPTIMIZE（O1 不修复）

| ID | 级别 | 问题 | 修复 |
|----|------|------|------|
| C1 | CRITICAL | `DryContactMonitor` 用归一化后的 `value` 做状态比较，枚举映射后可能是字符串，比较不可靠 | 改用 `raw_value`（原始 0/1）做比较，事件中同时提供 `value`/`raw_value` |
| E1 | ENHANCE | `remove_datasource`/`reload_datasource` 未清除 DryContactMonitor 状态，重新添加时可能触发虚假事件 | 在 `remove_datasource` 中调用 `reset(datasource_id)` |
| E2 | ENHANCE | `stop()` 未清除 DryContactMonitor 状态，调度器重启后旧状态残留 | 新增 `clear_all()` 方法，在 `stop()` 中调用 |
| O1 | OPTIMIZE | `check()` 每次重建 `point_map` | 不修复，当前规模无性能问题 |

### Code Review (Adversarial) — 2026-02-15

**发现问题:** 0 HIGH, 0 MEDIUM, 1 LOW（不修复）

| ID | 级别 | 问题 | 修复 |
|----|------|------|------|
| L1 | LOW | `logger.warning` 用于所有干接点变化，普通门禁开关用 `info` 更合适 | 不修复，干接点变化本身值得关注 |
