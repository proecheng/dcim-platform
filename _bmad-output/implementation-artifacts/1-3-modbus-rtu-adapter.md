# Story 1.3: Modbus RTU 适配器

Status: done

## Story

As a 集成工程师,
I want 通过 Modbus RTU 协议采集串口设备数据,
so that 我可以接入通过 RS-485 连接的精密空调、环境传感器、电池巡检仪。

## Acceptance Criteria (验收标准)

1. **AC-1: 适配器注册** — `ModbusRtuAdapter` 继承 `BaseProtocolAdapter`，通过 `@register_adapter("modbus_rtu")` 装饰器注册到 `ADAPTER_REGISTRY`，采集调度器可自动发现和调用
2. **AC-2: 串口连接** — 使用 `AsyncModbusSerialClient` 建立串口连接，支持配置串口号、波特率、数据位、校验位、停止位、从站地址
3. **AC-3: 四种寄存器类型** — 与 Story 1.2 一致，支持 HR/IR/CO/DI 四种寄存器类型读取
4. **AC-4: 读取超时重试** — 读取超时立即重试 1 次，仍失败则标记点位质量为 `DataQuality.UNRELIABLE`
5. **AC-5: 串口被占用** — 串口被占用时记录错误并标记数据源为 `AdapterState.CONFIG_ERROR`，提示用户检查串口分配
6. **AC-6: CRC 校验失败** — 波特率不匹配导致 CRC 校验失败时，连续 3 次失败后标记数据源为"通信中断"并建议检查串口参数
7. **AC-7: 写入支持** — 与 Story 1.2 一致，`write_point` 支持写入 HR 和 CO（仅当 `write_enabled=True`），禁止写入 IR/DI
8. **AC-8: 连接测试** — `test_connection` 尝试连接并读取少量数据，整体超时 10 秒

## Tasks / Subtasks (任务分解)

- [x] Task 1: 创建 ModbusRtuAdapter 核心 (AC: #1, #2)
  - [x] 1.1 在 `gateway/requirements.txt` 中添加 `pyserial>=3.5` 并安装
  - [x] 1.2 创建 `gateway/adapters/modbus_rtu.py`
  - [x] 1.3 实现 `connect(config)` — 使用 `AsyncModbusSerialClient` 建立串口连接，从 `config.connection_params` 读取 `port`(串口号)、`baudrate`(默认9600)、`bytesize`(默认8)、`parity`(默认"N")、`stopbits`(默认1)、`device_id`(从站地址，默认1)、`timeout`(默认3s)、`word_order`(默认"big")
  - [x] 1.4 实现串口被占用检测（`SerialException` / `PermissionError`）→ 标记 `AdapterState.CONFIG_ERROR`
  - [x] 1.5 实现 `disconnect()` — 调用 `client.close()`，更新状态
  - [x] 1.6 实现 `get_status()` — 返回 `AdapterStatus`

- [x] Task 2: 实现读取功能 (AC: #3, #4, #6)
  - [x] 2.1 复用 Story 1.2 的 `_parse_address` 和 `_convert_value` 工具函数（从 modbus_tcp 导入）
  - [x] 2.2 实现 `read_points(points)` — 逐点位读取，单点失败不影响其他点位
  - [x] 2.3 实现读取超时重试：超时立即重试 1 次，仍失败标记 `DataQuality.UNRELIABLE`
  - [x] 2.4 实现 CRC 校验失败检测：连续 3 次 CRC 失败后标记通信中断，日志建议检查串口参数

- [x] Task 3: 实现写入功能 (AC: #7)
  - [x] 3.1 实现 `write_point(point_id, value)` — 仅允许 HR 和 CO，禁止 IR/DI
  - [x] 3.2 写入前检查 `write_enabled`

- [x] Task 4: 实现连接测试 (AC: #8)
  - [x] 4.1 实现 `test_connection()` — 整体超时 10 秒，返回 `ConnectionResult`

- [x] Task 5: 注册适配器
  - [x] 5.1 在 `gateway/adapters/__init__.py` 中添加 `from . import modbus_rtu`

- [x] Task 6: 单元测试 (AC: 全部)
  - [x] 6.1 测试适配器注册（`ADAPTER_REGISTRY["modbus_rtu"]` 存在）
  - [x] 6.2 测试 connect/disconnect 生命周期（mock AsyncModbusSerialClient）
  - [x] 6.3 测试串口被占用 → CONFIG_ERROR
  - [x] 6.4 测试四种寄存器类型读取
  - [x] 6.5 测试读取超时重试 1 次 → UNRELIABLE
  - [x] 6.6 测试 CRC 校验失败连续 3 次 → 通信中断
  - [x] 6.7 测试写入功能（HR/CO 允许，IR/DI 拒绝）
  - [x] 6.8 测试连接测试功能（含 10 秒超时）
  - [x] 6.9 测试 word_order 配置传递

## Dev Notes (开发指南)

### 1. 文件位置

```
gateway/adapters/modbus_rtu.py    # 新建 — ModbusRtuAdapter 实现
gateway/adapters/__init__.py      # 修改 — 添加 import
backend/tests/test_modbus_rtu.py  # 新建 — 单元测试
```

### 2. pymodbus 3.x 异步串口 API

**关键**: 使用 `AsyncModbusSerialClient`，framer 为 `FramerType.RTU`。

```python
from pymodbus.client import AsyncModbusSerialClient
from pymodbus.framer import FramerType
from pymodbus.pdu import ExceptionResponse

client = AsyncModbusSerialClient(
    port="/dev/ttyUSB0",       # Windows: "COM3"
    framer=FramerType.RTU,
    baudrate=9600,
    bytesize=8,
    parity="N",                # "N"=None, "E"=Even, "O"=Odd
    stopbits=1,
    timeout=3,
    handle_local_echo=False,
    reconnect_delay=0,         # 禁用内置重连
)
await client.connect()

# 读写 API 与 TCP 完全一致
result = await client.read_holding_registers(0, count=1, slave=device_id)
```

### 3. connection_params 规范

```python
{
    "port": "COM3",              # 必填 — 串口号（Windows: COM3, Linux: /dev/ttyUSB0）
    "baudrate": 9600,            # 可选 — 波特率，默认 9600
    "bytesize": 8,               # 可选 — 数据位，默认 8
    "parity": "N",               # 可选 — 校验位 "N"/"E"/"O"，默认 "N"
    "stopbits": 1,               # 可选 — 停止位，默认 1
    "device_id": 1,              # 可选 — 从站地址，默认 1
    "timeout": 3,                # 可选 — 通信超时秒数，默认 3
    "word_order": "big",         # 可选 — 字序，默认 "big"
}
```

### 4. 与 Story 1.2 的代码复用

**复用 `_parse_address` 和 `_convert_value`**: 这两个函数是纯工具函数，与协议无关。从 `modbus_tcp` 模块导入：

```python
from .modbus_tcp import _parse_address, _convert_value, _READ_METHODS, _DEFAULT_COUNT, _ILLEGAL_ADDRESS
```

**不复用的部分**: connect/disconnect（串口 vs TCP 参数完全不同）、错误处理（串口特有的 SerialException、CRC 错误）。

### 5. RTU 特有错误处理

| 错误类型 | 检测方式 | 处理 |
|---------|---------|------|
| 串口被占用 | `SerialException` 或 `PermissionError` 在 connect 时 | `AdapterState.CONFIG_ERROR`，日志提示检查串口分配 |
| CRC 校验失败 | `ModbusIOException` 含 "CRC" 或 response 为 `ModbusIOException` | 计数器 +1，连续 3 次后标记通信中断 |
| 读取超时 | `asyncio.TimeoutError` 或 `ModbusException` | 立即重试 1 次，仍失败标记 `UNRELIABLE` |

**CRC 失败检测**: pymodbus 3.x 在 CRC 校验失败时会抛出 `ModbusIOException`，message 中通常包含 "CRC" 或 "incomplete message"。也可能返回 `isError()=True` 的响应。需要用 `self._crc_failure_count` 跟踪连续失败次数。

### 6. 读取超时重试逻辑

```python
async def _read_with_retry(self, read_method, addr, count):
    """读取并在超时时重试 1 次"""
    for attempt in range(2):  # 最多 2 次（原始 + 1 次重试）
        try:
            response = await read_method(addr, count=count, slave=self._device_id)
            if not response.isError():
                self._crc_failure_count = 0  # 成功读取重置 CRC 计数器
                return response, DataQuality.NORMAL
            if isinstance(response, ExceptionResponse):
                return response, DataQuality.ABNORMAL
            # 其他错误（可能是 CRC）
            self._crc_failure_count += 1
            if self._crc_failure_count >= 3:
                logger.error("连续 %d 次 CRC/通信失败，建议检查串口参数（波特率、校验位）", self._crc_failure_count)
            if attempt == 0:
                continue  # 重试
            return response, DataQuality.UNRELIABLE
        except (asyncio.TimeoutError, ModbusException):
            # 仅对超时和 Modbus 通信异常重试
            if attempt == 0:
                logger.debug("点位读取超时，重试第 %d 次", attempt + 1)
                continue
            raise
        except Exception:
            # 其他异常（串口断开等）不重试，直接抛出
            raise
    # 不应到达这里
```

**CRC 计数器说明**: `_crc_failure_count` 是实例级别的持久计数器，跨多次 `read_points` 调用累积。成功读取时重置为 0。连续 3 次失败后由调度器的 `RetryPolicy.is_interrupted` 判断是否标记通信中断。

### 7. 关键约束

- **pymodbus 版本**: 已安装 `>=3.6,<4.0`（Story 1.2 已添加依赖）
- **pyserial 依赖**: pymodbus 串口支持需要 pyserial。需在 `gateway/requirements.txt` 添加 `pyserial>=3.5` 并安装（`pip install pyserial`）。如果未安装，`AsyncModbusSerialClient` import 会失败
- **不引入其他新依赖**: 只用 pymodbus + pyserial + 标准库
- **网关模块独立**: `gateway/` 不依赖 `backend/app/`
- **测试使用 mock**: mock `AsyncModbusSerialClient`，不需要真实串口
- **Windows 兼容**: 串口号使用 "COM3" 格式

### 8. 测试策略

与 Story 1.2 类似，使用 `unittest.mock.AsyncMock` mock 串口客户端：

```python
@patch("gateway.adapters.modbus_rtu.AsyncModbusSerialClient")
async def test_connect_success(self, MockClient):
    mock_instance = AsyncMock()
    type(mock_instance).connected = PropertyMock(return_value=True)
    MockClient.return_value = mock_instance
    ...
```

**串口被占用模拟**: `MockClient.side_effect = SerialException("Port is already open")`

**CRC 失败模拟**: mock read 方法返回 `isError()=True` 的响应，或抛出 `ModbusIOException`

### Project Structure Notes (项目结构对齐)

- `gateway/adapters/modbus_rtu.py` — 新建文件，与 Architecture 定义一致
- `gateway/adapters/__init__.py` — 追加 `from . import modbus_rtu`
- 测试文件放在 `backend/tests/test_modbus_rtu.py` — 原因：`backend/pytest.ini` 配置了 `pythonpath = ..`（项目根目录）

### References (参考来源)

- [Source: architecture.md#6.3] Modbus TCP/RTU 分开 — 独立适配器
- [Source: architecture.md#1.2] IoT 采集层 — pymodbus 3.x
- [Source: epics.md#Story 1.3] Acceptance Criteria — 串口配置、CRC 校验、超时重试
- [Source: 1-2-modbus-tcp-adapter.md] Story 1.2 实现 — _parse_address/_convert_value 可复用
- [Source: pymodbus docs] AsyncModbusSerialClient API — FramerType.RTU, baudrate, parity, bytesize, stopbits

### Previous Story Intelligence (Story 1.2 经验)

- **装饰器注册模式**: `@register_adapter("modbus_rtu")` 在 import 时自动注册
- **测试隔离**: 使用 `autouse=True` fixture 保存/恢复 ADAPTER_REGISTRY
- **slave 参数**: pymodbus 3.x 实际参数名是 `slave`，不是 `device_id`
- **FramerType 导入路径**: `from pymodbus.framer import FramerType`（3.12 版本）
- **禁用内置重连**: `reconnect_delay=0`
- **IR 只读**: write_point 禁止写入 IR（Modbus 协议规范）
- **自动类型转换**: 失败后自动转 float 标记 `DataQuality.UNRELIABLE`
- **lazy logging**: 使用 `%s` 格式而非 f-string
- **异常链**: `raise ValueError(...) from e`
- **word_order**: 必须从 connection_params 读取并传给 convert_from_registers

## Dev Agent Record

### Agent Model Used

claude-opus-4-6

### Debug Log References

- pyserial 3.5 安装成功
- 复用 modbus_tcp 的 _parse_address/_convert_value/_READ_METHODS/_DEFAULT_COUNT/_ILLEGAL_ADDRESS
- SerialException 从 `serial` 包导入（pyserial 提供）
- _read_with_retry 实现超时重试 + CRC 计数

### Completion Notes List

- 全部 6 个 Task 已完成
- 28 个单元测试全部通过，覆盖 9 个测试领域
- 复用 Story 1.2 工具函数，避免代码重复
- RTU 特有：串口被占用 → CONFIG_ERROR、CRC 连续 3 次 → 通信中断警告、超时重试 1 次 → UNRELIABLE
- 无回归

### File List

**新建文件:**
- `gateway/adapters/modbus_rtu.py` — ModbusRtuAdapter 完整实现
- `backend/tests/test_modbus_rtu.py` — 28 个单元测试

**修改文件:**
- `gateway/requirements.txt` — 添加 `pyserial>=3.5`
- `gateway/adapters/__init__.py` — 添加 `from . import modbus_rtu`

## Senior Developer Review (AI)

**审查日期:** 2026-02-15
**审查结果:** ✅ Approve (with fixes applied)

### 发现问题: 2 High, 1 Medium, 1 Low

| ID | 级别 | 文件 | 问题 | 状态 |
|----|------|------|------|------|
| H1 | HIGH | modbus_rtu.py:146-201 | _read_with_retry 返回 ExceptionResponse 对象但 read_points 又重复检查 | ✅ 已修复 — _read_with_retry 现在返回 None+ABNORMAL，read_points 简化 |
| H2 | HIGH | modbus_rtu.py:146 | ExceptionResponse 缺少差异化日志（地址越界 vs 其他异常） | ✅ 已修复 — 在 _read_with_retry 中添加 ILLEGAL_ADDRESS 判断 |
| M1 | MEDIUM | modbus_rtu.py:150 | CRC 计数在重试前递增，重试成功后重置 — 时序不一致 | ✅ 已修复 — 改为重试失败后才递增 |
| L1 | LOW | modbus_rtu.py:125 | 返回类型注释不精确 | 未修复（不影响功能） |

### 测试结果

- 修复前: 28/28 passed
- 修复后: 28/28 passed（无新增测试，修复为内部逻辑优化）
- RTU + TCP 联合: 77/77 passed
