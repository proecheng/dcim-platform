# Story 1.2: Modbus TCP 适配器

Status: done

## Story

As a 集成工程师,
I want 通过 Modbus TCP 协议采集设备数据,
so that 我可以接入通过网络连接的空调、UPS、PDU 等设备。

## Acceptance Criteria (验收标准)

1. **AC-1: 适配器注册** — `ModbusTcpAdapter` 继承 `BaseProtocolAdapter`，通过 `@register_adapter("modbus_tcp")` 装饰器注册到 `ADAPTER_REGISTRY`，采集调度器可自动发现和调用
2. **AC-2: 四种寄存器类型** — 支持 Holding Register (`read_holding_registers`)、Input Register (`read_input_registers`)、Coil (`read_coils`)、Discrete Input (`read_discrete_inputs`) 四种寄存器类型读取
3. **AC-3: 连接与重试** — 连接失败时按指数退避重试（1s→2s→4s→8s→最大60s），连续 5 次失败标记数据源为"通信中断"并触发告警（复用 Story 1.1 的 RetryPolicy + CollectionScheduler 机制）
4. **AC-4: 地址越界处理** — 寄存器地址越界时记录错误日志并标记对应点位为 `DataQuality.ABNORMAL`
5. **AC-5: 从站无响应处理** — 从站无响应时按指数退避重试，连续 5 次失败标记数据源为"通信中断"并触发告警
6. **AC-6: 数据类型转换** — 数据类型不匹配（如期望 float 收到 int）时尝试自动转换，无法转换则标记点位质量为 `DataQuality.ABNORMAL`
7. **AC-7: 写入支持** — `write_point` 支持写入寄存器/线圈（仅当 `DataSourceConfig.write_enabled=True` 时允许）。单寄存器用 `write_register`，多寄存器（int32/float32）用 `write_registers` + `convert_to_registers`，线圈用 `write_coil`
8. **AC-8: 连接测试** — `test_connection` 尝试连接并读取少量数据，返回 `ConnectionResult`（含延迟和样本数据），整体超时 10 秒

## Tasks / Subtasks (任务分解)

- [x] Task 1: 添加 pymodbus 依赖 (AC: 全部)
  - [x] 1.1 在 `gateway/requirements.txt` 中添加 `pymodbus>=3.6,<4.0`（如文件不存在则创建）
  - [x] 1.2 安装依赖验证 import 正常

- [x] Task 2: 实现 ModbusTcpAdapter 核心 (AC: #1, #2, #3, #5)
  - [x] 2.1 创建 `gateway/adapters/modbus_tcp.py`
  - [x] 2.2 实现 `connect(config)` — 使用 `AsyncModbusTcpClient` 建立连接，从 `config.connection_params` 读取 `host`、`port`(默认502)、`device_id`(从站地址，默认1)、`timeout`(默认3s)
  - [x] 2.3 实现 `disconnect()` — 调用 `client.close()`
  - [x] 2.4 实现 `read_points(points)` — 按寄存器类型分组批量读取，返回 `dict[str, PointValue]`
  - [x] 2.5 实现 `get_status()` — 返回 `AdapterStatus`

- [x] Task 3: 实现四种寄存器类型读取 (AC: #2, #4, #6)
  - [x] 3.1 解析 `PointConfig.address` 格式：`{register_type}:{address}` 或 `{register_type}:{address}:{count}`，例如 `HR:100`、`IR:200:2`、`CO:0`、`DI:0`
  - [x] 3.2 实现 Holding Register 读取 (`client.read_holding_registers`)
  - [x] 3.3 实现 Input Register 读取 (`client.read_input_registers`)
  - [x] 3.4 实现 Coil 读取 (`client.read_coils`)
  - [x] 3.5 实现 Discrete Input 读取 (`client.read_discrete_inputs`)
  - [x] 3.6 实现寄存器值→Python 类型转换（根据 `PointConfig.data_type`）
  - [x] 3.7 地址越界（`ExcCodes.ILLEGAL_ADDRESS`）时标记 `DataQuality.ABNORMAL`
  - [x] 3.8 数据类型不匹配时尝试自动转换，失败标记 `DataQuality.ABNORMAL`

- [x] Task 4: 实现写入功能 (AC: #7)
  - [x] 4.1 实现 `write_point(point_id, value)` — 解析地址，根据数据类型选择写入方式：单寄存器 `write_register`，多寄存器（int32/float32）`write_registers` + `convert_to_registers`，线圈 `write_coil`
  - [x] 4.2 写入前检查 `self._config.write_enabled`，未启用时返回 False 并记录警告

- [x] Task 5: 实现连接测试 (AC: #8)
  - [x] 5.1 实现 `test_connection()` — 连接后读取少量寄存器验证通信，整体超时 10 秒（`asyncio.wait_for`），返回 `ConnectionResult`（含延迟 ms 和样本数据）

- [x] Task 6: 单元测试 (AC: 全部)
  - [x] 6.1 测试适配器注册（`ADAPTER_REGISTRY["modbus_tcp"]` 存在）
  - [x] 6.2 测试 connect/disconnect 生命周期（mock AsyncModbusTcpClient），含重复 connect 清理旧连接
  - [x] 6.3 测试四种寄存器类型读取（mock 返回值）
  - [x] 6.4 测试地址越界处理（mock ExceptionResponse）
  - [x] 6.5 测试数据类型转换（int16/uint16/int32/uint32/float32/bool/string）
  - [x] 6.6 测试 word_order 配置（big/little 字序对 float32 结果的影响）
  - [x] 6.7 测试写入功能（write_enabled=True/False，含多寄存器写入）
  - [x] 6.8 测试连接测试功能（含 10 秒超时）
  - [x] 6.9 测试地址格式解析（合法/非法格式）

## Dev Notes (开发指南)

### 1. 文件位置

```
gateway/adapters/modbus_tcp.py   # 新建 — ModbusTcpAdapter 实现
gateway/requirements.txt         # 新建或追加 — pymodbus 依赖
backend/tests/test_modbus_tcp.py # 新建 — 单元测试
```

### 2. pymodbus 3.x 异步 API 用法

**关键**: 使用 `AsyncModbusTcpClient`，不要用同步 `ModbusTcpClient`。

```python
from pymodbus.client import AsyncModbusTcpClient
from pymodbus import FramerType, ModbusException
from pymodbus.pdu import ExceptionResponse
from pymodbus.constants import ExcCodes

# 创建客户端（禁用内置重连，由 CollectionScheduler 管理）
client = AsyncModbusTcpClient(
    host,
    port=port,
    framer=FramerType.SOCKET,
    timeout=timeout,
    reconnect_delay=0,  # 禁用 pymodbus 内置重连
)
await client.connect()
assert client.connected

# 读取 Holding Register
result = await client.read_holding_registers(address, count=count, device_id=device_id)
if result.isError():
    if isinstance(result, ExceptionResponse):
        if result.exception_code == ExcCodes.ILLEGAL_ADDRESS:
            # 地址越界
            ...
else:
    values = result.registers  # list[int]

# 读取 Coil
result = await client.read_coils(address, count=count, device_id=device_id)
values = result.bits  # list[bool]

# 写入单寄存器
await client.write_register(address, value, device_id=device_id)
# 写入多寄存器（int32/float32）
regs = client.convert_to_registers(float_value, client.DATATYPE.FLOAT32)
await client.write_registers(address, regs, device_id=device_id)
# 写入线圈
await client.write_coil(address, bool_value, device_id=device_id)

# 多寄存器数据类型转换（注意 word_order 参数）
word_order = connection_params.get("word_order", "big")
result = await client.read_holding_registers(address, count=2, device_id=device_id)
int32_value = client.convert_from_registers(result.registers, client.DATATYPE.INT32, word_order=word_order)
float32_value = client.convert_from_registers(result.registers, client.DATATYPE.FLOAT32, word_order=word_order)

# 关闭
client.close()
```

### 3. 地址格式规范

`PointConfig.address` 格式: `{register_type}:{start_address}` 或 `{register_type}:{start_address}:{register_count}`

| 前缀 | 寄存器类型 | pymodbus 方法 | 默认 count |
|------|-----------|--------------|-----------|
| `HR` | Holding Register | `read_holding_registers` | 由 data_type 决定 |
| `IR` | Input Register | `read_input_registers` | 由 data_type 决定 |
| `CO` | Coil | `read_coils` | 1 |
| `DI` | Discrete Input | `read_discrete_inputs` | 1 |

示例:
- `HR:100` — 读取 Holding Register 地址 100
- `IR:200:2` — 读取 Input Register 地址 200，连续 2 个寄存器
- `CO:0` — 读取 Coil 地址 0
- `DI:16` — 读取 Discrete Input 地址 16

### 4. 数据类型与寄存器数量映射

| data_type | 寄存器数 | 转换方式 |
|-----------|---------|---------|
| `int16` | 1 | `registers[0]`（有符号处理：>32767 则减 65536） |
| `uint16` | 1 | `registers[0]` |
| `int32` | 2 | `client.convert_from_registers(regs, DATATYPE.INT32, word_order=word_order)` |
| `uint32` | 2 | `client.convert_from_registers(regs, DATATYPE.UINT32, word_order=word_order)` |
| `float32` | 2 | `client.convert_from_registers(regs, DATATYPE.FLOAT32, word_order=word_order)` |
| `bool` | 1 (Coil/DI) | `bits[0]` |
| `string` | N (由 count 指定) | `client.convert_from_registers(regs, DATATYPE.STRING, string_encoding='utf-8')` |

`word_order` 从 `connection_params.get("word_order", "big")` 读取，传给所有 `convert_from_registers` 调用。

如果 `PointConfig.address` 未指定 count，根据 `data_type` 自动推断。

### 5. connection_params 规范

`DataSourceConfig.connection_params` 字典结构:

```python
{
    "host": "192.168.1.100",     # 必填 — 设备 IP
    "port": 502,                  # 可选 — 默认 502
    "device_id": 1,               # 可选 — 从站地址，默认 1
    "timeout": 3,                 # 可选 — 通信超时秒数，默认 3
    "word_order": "big",          # 可选 — 字序 "big"(默认) 或 "little"，影响 int32/float32 多寄存器解析
}
```

**⚠️ 字节序(word_order)说明**: 不同厂商 Modbus 设备的多寄存器值（int32/float32）字序不同。默认 `big`（高字在前），部分国产设备（如某些 PDU/UPS）使用 `little`（低字在前）。字序错误会导致 float32 读数完全无意义。`convert_from_registers` 的 `word_order` 参数必须从 `connection_params` 读取并传入。

### 6. 适配器实现骨架

```python
# gateway/adapters/modbus_tcp.py
import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional

from pymodbus.client import AsyncModbusTcpClient
from pymodbus import FramerType, ModbusException
from pymodbus.pdu import ExceptionResponse
from pymodbus.constants import ExcCodes

from .base import (
    BaseProtocolAdapter, DataSourceConfig, PointConfig, PointValue,
    ConnectionResult, AdapterStatus, AdapterState, DataQuality,
)
from .registry import register_adapter

logger = logging.getLogger(__name__)

# 寄存器类型前缀 → 读取方法名
REGISTER_TYPE_MAP = {
    "HR": "read_holding_registers",
    "IR": "read_input_registers",
    "CO": "read_coils",
    "DI": "read_discrete_inputs",
}

# data_type → 需要的寄存器数量
DATA_TYPE_REGISTER_COUNT = {
    "int16": 1, "uint16": 1,
    "int32": 2, "uint32": 2,
    "float32": 2,
    "bool": 1,
    "string": None,  # 由 address 中的 count 指定，如 HR:100:6
}


@register_adapter("modbus_tcp")
class ModbusTcpAdapter(BaseProtocolAdapter):
    """Modbus TCP 协议适配器"""

    def __init__(self):
        self._client: Optional[AsyncModbusTcpClient] = None
        self._config: Optional[DataSourceConfig] = None
        self._state = AdapterState.DISCONNECTED
        self._connected_since: Optional[datetime] = None
        self._last_read_time: Optional[datetime] = None
        self._consecutive_failures = 0
        self._error_message: Optional[str] = None

    async def connect(self, config: DataSourceConfig) -> bool:
        """建立 Modbus TCP 连接"""
        # 清理已有连接（防止重连场景泄漏）
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None

        self._config = config
        params = config.connection_params
        host = params["host"]
        port = params.get("port", 502)
        timeout = params.get("timeout", 3)

        # 禁用 pymodbus 内置重连（reconnect_delay=0），由 CollectionScheduler + RetryPolicy 统一管理
        self._client = AsyncModbusTcpClient(
            host, port=port,
            framer=FramerType.SOCKET,
            timeout=timeout,
            reconnect_delay=0,
        )
        await self._client.connect()
        if self._client.connected:
            self._state = AdapterState.CONNECTED
            self._connected_since = datetime.now(timezone.utc)
            self._error_message = None
            return True
        self._state = AdapterState.DISCONNECTED
        return False

    async def disconnect(self) -> None:
        """断开连接并清理状态"""
        if self._client is not None:
            self._client.close()
            self._client = None
        self._state = AdapterState.DISCONNECTED
        self._connected_since = None
    async def read_points(self, points: list[PointConfig]) -> dict[str, PointValue]: ...
    async def write_point(self, point_id: str, value: Any) -> bool: ...
    async def test_connection(self) -> ConnectionResult: ...
    def get_status(self) -> AdapterStatus: ...
```

### 7. 错误处理要点

- **连接失败**: `connect()` 返回 `False`，由 `CollectionScheduler._collection_loop` 的连接重试逻辑处理（Story 1.1 已实现）
- **读取异常**: `read_points()` 中捕获 `ModbusException`，抛出让调度器的采集循环处理重试
- **地址越界**: `ExceptionResponse` + `ExcCodes.ILLEGAL_ADDRESS` → 该点位标记 `DataQuality.ABNORMAL`，不影响其他点位
- **从站无响应**: `ModbusException` 或超时 → 由调度器重试机制处理
- **数据类型不匹配**: 转换失败时 try/except → 标记 `DataQuality.ABNORMAL`

**重要**: 单个点位读取失败不应中断整个 `read_points` 调用。对每个点位独立 try/except，失败的点位标记质量异常，成功的点位正常返回。

**批量优化**: MVP 阶段逐点位读取（每个点位一次 Modbus 请求），实现简单可靠。后续优化可将同类型连续地址合并为一次请求（如 HR:100 + HR:101 + HR:102 合并为 `read_holding_registers(100, count=3)`），但本 Story 不要求。

### 8. 与 Story 1.1 框架的集成

- **不需要修改** `scheduler.py`、`normalizer.py`、`retry.py` — 它们已经是通用的
- **只需要** 在 `gateway/adapters/__init__.py` 中 import `modbus_tcp` 模块，确保装饰器执行注册
- 调度器通过 `get_adapter("modbus_tcp")` 获取适配器类，自动实例化和调用

```python
# gateway/adapters/__init__.py — 添加 import
from .base import *  # noqa
from .registry import *  # noqa
from . import modbus_tcp  # 触发 @register_adapter 装饰器
```

### 9. 关键约束

- **pymodbus 版本**: `>=3.6,<4.0`（3.x 异步 API 稳定，4.0 可能有 breaking changes）
- **不引入其他新依赖**: 只用 pymodbus + 标准库
- **网关模块独立**: `gateway/` 不依赖 `backend/app/`
- **测试使用 mock**: 不需要真实 Modbus 设备，mock `AsyncModbusTcpClient` 的方法
- **Python 3.11+**: 与后端统一

### 10. 测试策略

使用 `unittest.mock.AsyncMock` mock pymodbus 客户端:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from gateway.adapters.modbus_tcp import ModbusTcpAdapter
from gateway.adapters.base import DataSourceConfig, PointConfig, DataQuality

@pytest.fixture
def adapter():
    return ModbusTcpAdapter()

@pytest.fixture
def modbus_config():
    return DataSourceConfig(
        datasource_id="ds-modbus-test",
        protocol_type="modbus_tcp",
        connection_params={"host": "192.168.1.100", "port": 502, "device_id": 1},
        points=[
            PointConfig(point_id="temp", address="HR:100", data_type="float32"),
            PointConfig(point_id="status", address="CO:0", data_type="bool"),
        ],
    )

@pytest.mark.asyncio
async def test_connect_success(adapter, modbus_config):
    with patch("gateway.adapters.modbus_tcp.AsyncModbusTcpClient") as MockClient:
        mock_instance = AsyncMock()
        mock_instance.connected = True
        MockClient.return_value = mock_instance
        result = await adapter.connect(modbus_config)
        assert result is True
```

### Project Structure Notes (项目结构对齐)

- `gateway/adapters/modbus_tcp.py` — 新建文件，与 Architecture 2.5 定义的 `modbus_tcp.py` 位置一致
- `gateway/adapters/__init__.py` — 需追加 `from . import modbus_tcp` 触发注册
- `gateway/requirements.txt` — 新建，管理网关模块的 Python 依赖
- 测试文件放在 `backend/tests/test_modbus_tcp.py`（与 Story 1.1 的 `test_gateway.py` 同级）— 原因：`backend/pytest.ini` 配置了 `pythonpath = ..`（项目根目录），使 `gateway` 包可被 import。不要在 gateway/ 下单独建测试目录

### References (参考来源)

- [Source: architecture.md#6.1] 适配器接口规范 — BaseProtocolAdapter 6 个抽象方法
- [Source: architecture.md#6.2] 适配器注册表 — ADAPTER_REGISTRY["modbus_tcp"]
- [Source: architecture.md#6.3] Modbus TCP/RTU 分开 — 独立适配器
- [Source: architecture.md#6.5] 错误重试策略 — 指数退避 + 连续 5 次失败中断
- [Source: architecture.md#1.2] IoT 采集层 — pymodbus 3.x
- [Source: epics.md#Story 1.2] Acceptance Criteria — 四种寄存器、重试、地址越界、类型转换
- [Source: 1-1-protocol-adapter-plugin-framework.md] Story 1.1 实现 — BaseProtocolAdapter/ADAPTER_REGISTRY/CollectionScheduler/DataNormalizer/RetryPolicy 已就绪
- [Source: pymodbus docs] AsyncModbusTcpClient API — FramerType.SOCKET, device_id, convert_from_registers

### Previous Story Intelligence (Story 1.1 经验)

- **装饰器注册模式**: `@register_adapter("modbus_tcp")` 装饰器会在 import 时自动注册，需确保 `__init__.py` 中 import 该模块
- **测试隔离**: Story 1.1 Review 发现 `TestAdapterRegistry` 需要 `teardown_method` 清理全局注册表 — 本 Story 测试也需注意注册表清理
- **async 接口**: `ConfigLoader` 已改为 async，所有适配器方法也是 async — 保持一致
- **干接点枚举映射**: `DataNormalizer` 已修复干接点优先走枚举映射 — 本适配器读取 DI 寄存器时返回 bool 值即可，归一化由 normalizer 处理
- **protocol_type 白名单**: `datasources.py` API 已添加 `KNOWN_PROTOCOL_TYPES` 校验，`"modbus_tcp"` 已在白名单中

## Dev Agent Record

### Agent Model Used

claude-opus-4-6

### Debug Log References

- pymodbus 3.12.0 安装成功，`from pymodbus.framer import FramerType` 替代 `from pymodbus import FramerType`（3.12 版本路径变更）
- 使用 `slave` 参数替代 `device_id`（pymodbus 3.x 实际参数名）
- `_ILLEGAL_ADDRESS = 0x02` 硬编码替代 `ExcCodes.ILLEGAL_ADDRESS`（避免 import 路径差异）

### Completion Notes List

- 全部 6 个 Task（含子任务）已完成
- 49 个单元测试全部通过（含审查后新增 3 个），覆盖 11 个测试领域
- 支持 7 种数据类型：int16/uint16/int32/uint32/float32/bool/string
- 支持 word_order 配置（big/little 字序）
- 禁用 pymodbus 内置重连（reconnect_delay=0），由 CollectionScheduler 统一管理
- connect() 清理已有连接防止泄漏
- 单点位读取失败不影响其他点位（per-point error isolation）
- test_connection 10 秒超时，自动连接
- 无回归：全量测试中所有失败均为预存问题

### File List

**新建文件:**
- `gateway/adapters/modbus_tcp.py` — ModbusTcpAdapter 完整实现
- `gateway/requirements.txt` — pymodbus>=3.6,<4.0
- `backend/tests/test_modbus_tcp.py` — 49 个单元测试

**修改文件:**
- `gateway/adapters/__init__.py` — 添加 `from . import modbus_tcp` 触发装饰器注册

## Senior Developer Review (AI)

**审查日期:** 2026-02-15
**审查结果:** ✅ Approve (with fixes applied)

### 发现问题: 3 High, 3 Medium, 2 Low

| ID | 级别 | 文件 | 问题 | 状态 |
|----|------|------|------|------|
| H1 | HIGH | modbus_tcp.py:209 | ExceptionResponse 条件冗余，if/else 结果相同 | ✅ 已修复 |
| H2 | HIGH | modbus_tcp.py:297 | 允许写入 IR (Input Register)，违反 Modbus 协议 | ✅ 已修复 |
| H3 | HIGH | modbus_tcp.py:258 | 自动类型转换后标记 NORMAL 应为 UNRELIABLE | ✅ 已修复 |
| M1 | MEDIUM | modbus_tcp.py 全文 | f-string 日志应改为 lazy logging | ✅ 已修复 |
| M2 | MEDIUM | modbus_tcp.py:64-71 | raise ValueError 丢失异常链 | ✅ 已修复 |
| M3 | MEDIUM | test_modbus_tcp.py | 缺少 write_point word_order 传递验证测试 | ✅ 已修复 |
| L1 | LOW | __init__.py | modbus_tcp 未加入 __all__ | 未修复（不影响功能） |
| L2 | LOW | test_modbus_tcp.py:531 | 超时测试耗时过长 | 未修复（可接受） |

### Action Items

- [x] H1: ExceptionResponse 分支差异化日志
- [x] H2: write_point 禁止写入 IR，仅允许 HR 和 CO
- [x] H3: 自动类型转换后标记 DataQuality.UNRELIABLE
- [x] M1: 全文 f-string 日志改为 lazy logging (%s 格式)
- [x] M2: _parse_address 中 raise ValueError 保留异常链 (from e)
- [x] M3: 新增 3 个测试：IR 写入拒绝、write word_order 传递、自动转换 UNRELIABLE

### 测试结果

- 修复前: 46/46 passed
- 修复后: 49/49 passed（新增 3 个测试）
- 全量回归: 无新增失败
