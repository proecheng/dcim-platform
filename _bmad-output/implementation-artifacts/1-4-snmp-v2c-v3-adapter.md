# Story 1.4: SNMP v2c/v3 适配器

Status: done

## Story

As a 集成工程师,
I want 通过 SNMP v2c/v3 协议采集网络设备数据,
so that 我可以接入 UPS、网络交换机等支持 SNMP 的设备。

## Acceptance Criteria (验收标准)

1. **AC-1: 适配器注册** — 创建统一的 `SnmpAdapter` 类，继承 `BaseProtocolAdapter`，通过 `@register_adapter("snmp_v2c")` 和 `@register_adapter("snmp_v3")` 两个装饰器注册到 `ADAPTER_REGISTRY`，采集调度器可自动发现和调用
2. **AC-2: SNMP v2c 连接** — 使用 `pysnmp` (pysnmp-lextudio) 的 `CommunityData` 建立 v2c 会话，支持配置目标地址、端口（默认 161）、团体名（community）
3. **AC-3: SNMP v3 连接** — 使用 `pysnmp` 的 `UsmUserData` 建立 v3 会话，支持用户名、认证协议（MD5/SHA）、认证密钥、加密协议（DES/AES）、加密密钥
4. **AC-4: GET 操作** — 通过 `get_cmd` 读取指定 OID 的值，首版逐点位读取（pysnmp 的 `get_cmd` 支持多 ObjectType 批量读取，可作为后续优化）
5. **AC-5: WALK 操作** — 通过 `bulk_walk_cmd` 遍历指定 OID 子树，取第一个叶子节点的值作为该点位的值
6. **AC-6: 数据归一化** — 原始 SNMP 值经过缩放（scale）、偏移（offset）、枚举映射（enum_mapping）转换为工程值
7. **AC-7: 认证失败处理** — 团体名错误或 v3 认证失败时返回明确错误提示"认证失败，请检查团体名/认证参数"
8. **AC-8: OID 不存在处理** — OID 不存在时跳过该点位并记录警告日志，不影响其他点位采集
9. **AC-9: 超时重试** — SNMP 请求超时（默认 5s）时立即重试 1 次，仍失败则标记点位质量为 `DataQuality.UNRELIABLE`
10. **AC-10: 连接测试** — `test_connection` 尝试读取 sysDescr（`.1.3.6.1.2.1.1.1.0`）验证连通性，整体超时 10 秒
11. **AC-11: 写入不支持** — SNMP 适配器的 `write_point` 始终返回 `False`（SNMP 设备通常为只读采集，不支持 SET 操作）

## Tasks / Subtasks (任务分解)

- [ ] Task 1: 添加依赖并创建适配器文件 (AC: #1)
  - [ ] 1.1 在 `gateway/requirements.txt` 中添加 `pysnmp-lextudio>=6.1,<7.0`
  - [ ] 1.2 创建 `gateway/adapters/snmp.py`
  - [ ] 1.3 使用两个 `@register_adapter` 装饰器注册 `"snmp_v2c"` 和 `"snmp_v3"`

- [ ] Task 2: 实现连接功能 (AC: #2, #3, #7)
  - [ ] 2.1 实现 `connect(config)` — 根据 `config.protocol_type` 区分 v2c/v3
  - [ ] 2.2 v2c: 从 `connection_params` 读取 `host`、`port`(默认161)、`community`(默认"public")
  - [ ] 2.3 v3: 从 `connection_params` 读取 `host`、`port`(默认161)、`username`、`auth_protocol`("MD5"/"SHA")、`auth_key`、`priv_protocol`("DES"/"AES")、`priv_key`
  - [ ] 2.4 v3 安全级别校验: 如果提供了 `priv_protocol` 但未提供 `auth_protocol`，报错"加密需要先启用认证"
  - [ ] 2.5 连接时尝试读取 sysDescr 验证连通性，认证失败返回明确错误提示
  - [ ] 2.6 实现 `disconnect()` — 将 `self._engine` 设为 `None`（SnmpEngine 无显式 close），更新状态

- [ ] Task 3: 实现读取功能 (AC: #4, #5, #6, #8, #9)
  - [ ] 3.1 实现 `read_points(points)` — 根据点位 address 前缀区分 GET/WALK 操作
  - [ ] 3.2 GET 操作: address 格式为 `"get:.1.3.6.1.2.1.1.1.0"` 或纯 OID `".1.3.6.1.2.1.1.1.0"`
  - [ ] 3.3 WALK 操作: address 格式为 `"walk:.1.3.6.1.2.1.1"` — 遍历子树，取**第一个叶子节点的值**作为该点位的值（不做聚合）
  - [ ] 3.4 实现超时重试: 超时立即重试 1 次，仍失败标记 `DataQuality.UNRELIABLE`
  - [ ] 3.5 OID 不存在时跳过该点位，记录 warning 日志，标记 `DataQuality.ABNORMAL`
  - [ ] 3.6 实现数据归一化: 应用 scale、offset、enum_mapping

- [ ] Task 4: 实现写入和连接测试 (AC: #10, #11)
  - [ ] 4.1 实现 `write_point` — 始终返回 `False`，日志提示 SNMP 不支持写入
  - [ ] 4.2 实现 `test_connection()` — 读取 sysDescr，整体超时 10 秒，返回 `ConnectionResult`

- [ ] Task 5: 注册适配器
  - [ ] 5.1 在 `gateway/adapters/__init__.py` 中添加 `from . import snmp`

- [ ] Task 6: 单元测试 (AC: 全部)
  - [ ] 6.1 测试适配器注册（`ADAPTER_REGISTRY["snmp_v2c"]` 和 `ADAPTER_REGISTRY["snmp_v3"]` 存在且指向同一类）
  - [ ] 6.2 测试 v2c connect/disconnect 生命周期（mock pysnmp）
  - [ ] 6.3 测试 v3 connect/disconnect 生命周期（mock pysnmp）
  - [ ] 6.4 测试 v3 安全级别校验（priv 无 auth → 报错）
  - [ ] 6.5 测试 GET 操作读取单个 OID
  - [ ] 6.6 测试 WALK 操作遍历子树
  - [ ] 6.7 测试认证失败 → 明确错误提示（v2c 超时提示含团体名，v3 精确提示）
  - [ ] 6.8 测试 OID 不存在 → 跳过 + warning 日志
  - [ ] 6.9 测试超时重试 1 次 → UNRELIABLE
  - [ ] 6.10 测试数据归一化（scale、offset、enum_mapping）
  - [ ] 6.11 测试 write_point 始终返回 False
  - [ ] 6.12 测试 test_connection（含 10 秒超时）
  - [ ] 6.13 测试 get_status 返回正确状态

## Dev Notes (开发指南)

### 1. 关键库选择：pysnmp-lextudio（非 aiosnmp）

**重要**: 架构文档中提到 `aiosnmp`，但 aiosnmp 仅支持 SNMP v2c，**不支持 v3**。本 Story 需要 v3 支持（用户名、MD5/SHA 认证、DES/AES 加密），因此使用 `pysnmp-lextudio`（PySNMP 6.x，由 LeXtudio 维护的 fork）。

```
pip install pysnmp-lextudio>=6.1,<7.0
```

pysnmp-lextudio 6.x 提供完整的 asyncio 支持，API 路径为 `pysnmp.hlapi.v3arch.asyncio`。

### 2. 文件位置

```
gateway/adapters/snmp.py           # 新建 — SnmpAdapter 实现（v2c + v3 统一类）
gateway/adapters/__init__.py       # 修改 — 添加 from . import snmp
gateway/requirements.txt           # 修改 — 添加 pysnmp-lextudio>=6.1,<7.0
backend/tests/test_snmp.py         # 新建 — 单元测试
```

### 3. pysnmp asyncio API 用法

**v2c GET 操作:**

```python
from pysnmp.hlapi.v3arch.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    get_cmd,
)

engine = SnmpEngine()
error_indication, error_status, error_index, var_binds = await get_cmd(
    engine,
    CommunityData("public"),
    await UdpTransportTarget.create(("192.168.1.1", 161), timeout=5, retries=0),
    ContextData(),
    ObjectType(ObjectIdentity(".1.3.6.1.2.1.1.1.0")),
)
# error_indication: 非 None 表示传输层错误（超时、认证失败等）
# error_status: 非 0 表示 SNMP 协议错误（noSuchName 等）
# var_binds: [(oid, value), ...]
```

**v3 GET 操作:**

```python
from pysnmp.hlapi.v3arch.asyncio import UsmUserData
from pysnmp.hlapi.v3arch import auth

error_indication, error_status, error_index, var_binds = await get_cmd(
    engine,
    UsmUserData(
        "myuser",
        authKey="authpass123",
        privKey="privpass123",
        authProtocol=auth.usmHMACMD5AuthProtocol,    # MD5
        privProtocol=auth.usmDESPrivProtocol,          # DES
    ),
    await UdpTransportTarget.create(("192.168.1.1", 161), timeout=5, retries=0),
    ContextData(),
    ObjectType(ObjectIdentity(".1.3.6.1.2.1.1.1.0")),
)
```

**WALK 操作 (bulk_walk_cmd):**

```python
from pysnmp.hlapi.v3arch.asyncio import bulk_walk_cmd

objects = bulk_walk_cmd(
    engine,
    auth_data,
    transport_target,
    ContextData(),
    0,   # non_repeaters
    25,  # max_repetitions
    ObjectType(ObjectIdentity(".1.3.6.1.2.1.1")),
)
async for error_indication, error_status, error_index, var_binds in objects:
    if error_indication or error_status:
        break
    for var_bind in var_binds:
        oid, value = var_bind
        # 处理每个 OID-value 对
```

### 4. 认证协议映射

```python
from pysnmp.hlapi.v3arch import auth

AUTH_PROTOCOLS = {
    "MD5": auth.usmHMACMD5AuthProtocol,
    "SHA": auth.usmHMACSHAAuthProtocol,
}

PRIV_PROTOCOLS = {
    "DES": auth.usmDESPrivProtocol,
    "AES": auth.usmAesCfb128Protocol,    # AES-128
}
```

### 5. connection_params 规范

**v2c:**
```python
{
    "host": "192.168.1.1",       # 必填 — 目标 IP 地址
    "port": 161,                 # 可选 — SNMP 端口，默认 161
    "community": "public",       # 可选 — 团体名，默认 "public"
    "timeout": 5,                # 可选 — 超时秒数，默认 5
}
```

**v3:**
```python
{
    "host": "192.168.1.1",       # 必填 — 目标 IP 地址
    "port": 161,                 # 可选 — SNMP 端口，默认 161
    "username": "snmpuser",      # 必填 — v3 用户名
    "auth_protocol": "SHA",      # 可选 — 认证协议 "MD5"/"SHA"，默认 None（noAuth）
    "auth_key": "authpass123",   # 条件必填 — 认证密钥（auth_protocol 非 None 时必填）
    "priv_protocol": "AES",      # 可选 — 加密协议 "DES"/"AES"，默认 None（noPriv）
    "priv_key": "privpass123",   # 条件必填 — 加密密钥（priv_protocol 非 None 时必填）
    "timeout": 5,                # 可选 — 超时秒数，默认 5
}
```

**v3 安全级别组合规则（SNMP v3 规范）:**
- `noAuthNoPriv`: 仅 `username`，不设 auth/priv — `UsmUserData("user")`
- `authNoPriv`: `username` + `auth_protocol` + `auth_key`，不设 priv — `UsmUserData("user", authKey=..., authProtocol=...)`
- `authPriv`: `username` + `auth_protocol` + `auth_key` + `priv_protocol` + `priv_key` — 完整参数
- **禁止**: 提供 `priv_protocol` 但未提供 `auth_protocol` → connect 时应报错"加密需要先启用认证（SNMP v3 规范要求 authPriv 不能跳过 auth）"

### 6. 点位 address 格式

```
# GET 操作（默认）— 读取单个 OID
"get:.1.3.6.1.2.1.1.1.0"     # 显式 GET 前缀
".1.3.6.1.2.1.1.1.0"         # 无前缀默认为 GET

# WALK 操作 — 遍历 OID 子树
"walk:.1.3.6.1.2.1.1"        # 显式 WALK 前缀
```

解析函数 `_parse_oid(address)` 返回 `(operation, oid)` 元组，operation 为 `"get"` 或 `"walk"`。

### 7. 错误处理

| 错误类型 | 检测方式 | 处理 |
|---------|---------|------|
| 认证失败 (v2c) | `error_indication` 包含 "requestTimedOut"（v2c 团体名错误时设备直接丢弃请求不响应，表现为超时） | connect 时 sysDescr 读取超时，提示"连接超时，请检查目标地址和团体名" |
| 认证失败 (v3) | `error_indication` 包含 "unknownUserName"/"wrongDigest"/"decryptionError" | 标记 `AdapterState.CONFIG_ERROR`，提示"认证失败，请检查团体名/认证参数" |
| OID 不存在 | `error_status` 为 noSuchName/noSuchObject/noSuchInstance，或 var_bind value 为 `NoSuchObject`/`NoSuchInstance` | 跳过该点位，warning 日志，标记 `DataQuality.ABNORMAL` |
| 超时 | `error_indication` 包含 "requestTimedOut" | 重试 1 次，仍失败标记 `DataQuality.UNRELIABLE` |
| 网络不可达 | `error_indication` 非 None（其他类型） | 标记 `DataQuality.ABNORMAL`，记录错误日志 |

**v2c 认证失败 vs 网络超时**: SNMP v2c 协议中，设备收到错误团体名时**直接丢弃请求不响应**，因此 v2c 认证失败与网络超时**无法区分**，都表现为 `error_indication` 超时。connect 阶段如果 sysDescr 读取超时，错误提示应同时提及目标地址和团体名。v3 认证失败则有明确的 `error_indication`（如 `unknownUserName`），可以精确提示。

### 8. 数据归一化

SNMP 返回的原始值类型多样（Integer, OctetString, Counter32, Gauge32, TimeTicks 等）。归一化流程：

```python
def _normalize_value(raw_value, point: PointConfig) -> tuple[Any, DataQuality]:
    """将 SNMP 原始值转换为工程值"""
    # 1. 提取原始 Python 值
    if hasattr(raw_value, 'prettyPrint'):
        str_val = raw_value.prettyPrint()
    else:
        str_val = str(raw_value)

    # 2. 尝试转为数值
    try:
        numeric_val = float(str_val)
    except (ValueError, TypeError):
        # 非数值类型（字符串），直接返回
        if point.enum_mapping and str_val in point.enum_mapping:
            return point.enum_mapping[str_val], DataQuality.NORMAL
        return str_val, DataQuality.NORMAL

    # 3. 应用 scale + offset
    result = numeric_val * point.scale + point.offset

    # 4. 枚举映射（数值 key）
    if point.enum_mapping:
        str_key = str(int(numeric_val))
        if str_key in point.enum_mapping:
            return point.enum_mapping[str_key], DataQuality.NORMAL

    return result, DataQuality.NORMAL
```

### 9. 适配器注册模式（双注册）

两种写法均可，因为 `register_adapter` 装饰器返回原始 `cls`（`return cls`），叠加不会丢失类引用：

```python
from .registry import register_adapter

# 写法 A: 叠加装饰器（推荐，简洁）
@register_adapter("snmp_v3")
@register_adapter("snmp_v2c")
class SnmpAdapter(BaseProtocolAdapter):
    ...
# 执行顺序: 先注册 snmp_v2c → 返回 SnmpAdapter → 再注册 snmp_v3 → 返回 SnmpAdapter

# 写法 B: 手动调用（等价）
# register_adapter("snmp_v2c")(SnmpAdapter)
# register_adapter("snmp_v3")(SnmpAdapter)
```

### 10. 关键约束

- **pysnmp-lextudio 版本**: `>=6.1,<7.0`（6.x 系列，asyncio 支持稳定）
- **不引入 aiosnmp**: 虽然架构文档提到 aiosnmp，但它不支持 v3，不使用
- **UdpTransportTarget.create 是 async**: pysnmp 6.x 中 `UdpTransportTarget.create()` 是协程，必须 `await`
- **SnmpEngine 生命周期**: 每个适配器实例持有一个 `SnmpEngine`，connect 时创建，disconnect 时将 `self._engine` 设为 `None`（pysnmp 的 SnmpEngine 没有显式 close 方法，依赖 GC 回收）
- **retries=0**: pysnmp 内置重试设为 0，由适配器自己控制重试逻辑
- **网关模块独立**: `gateway/` 不依赖 `backend/app/`
- **测试使用 mock**: mock pysnmp 的 `get_cmd`、`bulk_walk_cmd`、`UdpTransportTarget.create`
- **lazy logging**: 使用 `%s` 格式而非 f-string
- **异常链**: `raise ValueError(...) from e`

### 11. 测试策略

```python
from unittest.mock import patch, AsyncMock, MagicMock

# Mock pysnmp 的 get_cmd
@patch("gateway.adapters.snmp.get_cmd", new_callable=AsyncMock)
@patch("gateway.adapters.snmp.UdpTransportTarget")
async def test_get_operation(self, MockTransport, mock_get_cmd):
    # 模拟成功响应
    mock_get_cmd.return_value = (
        None,           # error_indication
        0,              # error_status
        0,              # error_index
        [               # var_binds
            (ObjectIdentity(".1.3.6.1.2.1.1.1.0"), OctetString("Linux server")),
        ],
    )
    ...
```

**认证失败模拟**: `mock_get_cmd.return_value = ("unknownUserName", 0, 0, [])`

**OID 不存在模拟**: 使用 `NoSuchObject` 或 `NoSuchInstance` 作为 var_bind value

**超时模拟**: `mock_get_cmd.return_value = ("requestTimedOut", 0, 0, [])`

**WALK 模拟**: mock `bulk_walk_cmd` 返回 async iterator

### Project Structure Notes (项目结构对齐)

- `gateway/adapters/snmp.py` — 新建文件，与 Architecture 2.5 定义一致（架构写 `snmp_v2c.py`，但因 v2c/v3 共用一个类，命名为 `snmp.py` 更合理）
- `gateway/adapters/__init__.py` — 追加 `from . import snmp`
- 测试文件放在 `backend/tests/test_snmp.py` — 原因：`backend/pytest.ini` 配置了 `pythonpath = ..`（项目根目录）

### References (参考来源)

- [Source: architecture.md#6.2] 适配器注册表 — snmp_v2c, snmp_v3 两个注册名
- [Source: architecture.md#1.2] IoT 采集层 — aiosnmp（已替换为 pysnmp-lextudio，因 v3 需求）
- [Source: architecture.md#6.7] 数据归一化层 — 缩放、偏移、枚举映射
- [Source: epics.md#Story 1.4] Acceptance Criteria — GET/WALK、v2c/v3、认证失败、OID 不存在、超时重试
- [Source: pysnmp docs] pysnmp.hlapi.v3arch.asyncio API — get_cmd, bulk_walk_cmd, CommunityData, UsmUserData
- [Source: datasources.py] KNOWN_PROTOCOL_TYPES 已包含 "snmp_v2c" 和 "snmp_v3"

### Previous Story Intelligence (Story 1.3 经验)

- **装饰器注册模式**: `@register_adapter("protocol_name")` 在 import 时自动注册
- **测试隔离**: 使用 `autouse=True` fixture 保存/恢复 ADAPTER_REGISTRY
- **lazy logging**: 使用 `%s` 格式而非 f-string
- **异常链**: `raise ValueError(...) from e`
- **write_point 权限检查**: 先检查 `write_enabled`，再检查操作是否允许
- **test_connection 超时**: 整体 10 秒超时，使用 `asyncio.wait_for`
- **DataQuality 三级**: NORMAL（正常）、UNRELIABLE（不可靠，超时重试失败）、ABNORMAL（异常，协议错误）
- **get_status**: 返回 `AdapterStatus` 包含 state、connected_since、last_read_time、consecutive_failures、error_message

## Dev Agent Record

### Agent Model Used

claude-opus-4-6

### Debug Log References

- pysnmp-lextudio 6.3.0 已弃用，升级为 pysnmp 7.1.22
- pysnmp 7.x API 变更: getCmd → get_cmd, bulkWalkCmd → bulk_walk_cmd
- pysnmp 7.x 新增 UdpTransportTarget.create() 异步构造
- pysnmp.hlapi.asyncio 路径在 7.x 中仍可用（snake_case）

### Completion Notes List

- 全部 6 个 Task 已完成
- 30 个单元测试全部通过，覆盖 13 个测试领域
- 双注册模式: @register_adapter("snmp_v3") + @register_adapter("snmp_v2c") 叠加装饰器
- v2c CommunityData + v3 UsmUserData 统一在一个 SnmpAdapter 类
- v3 安全级别校验: priv 无 auth → 报错
- GET/WALK 操作均支持超时重试 1 次 → UNRELIABLE
- 无回归（107/107 全部通过）

### File List

**新建文件:**
- `gateway/adapters/snmp.py` — SnmpAdapter 完整实现（~490 lines）
- `backend/tests/test_snmp.py` — 30 个单元测试

**修改文件:**
- `gateway/requirements.txt` — 添加 `pysnmp>=7.0,<8.0`（替换 pysnmp-lextudio）
- `gateway/adapters/__init__.py` — 添加 `from . import snmp`

## Senior Developer Review (AI)

**审查日期:** 2026-02-15
**审查结果:** ✅ Approve (with fixes applied)

### 发现问题: 3 High, 2 Medium, 1 Low

| ID | 级别 | 文件 | 问题 | 状态 |
|----|------|------|------|------|
| H1 | HIGH | snmp.py:1-24 | pysnmp-lextudio 6.x 已弃用，升级 pysnmp 7.x，API 改为 snake_case (get_cmd/bulk_walk_cmd) | ✅ 已修复 |
| H2 | HIGH | snmp.py:156 | UdpTransportTarget 改用 await UdpTransportTarget.create() 异步构造 | ✅ 已修复 |
| H3 | HIGH | snmp.py:362-426 | _read_walk while/break/continue 重试逻辑过于复杂 → 简化为 for attempt in range(2) | ✅ 已修复 |
| M1 | MEDIUM | snmp.py:211 | error_index 可能为 None 导致 int(None) 异常 → 添加 try/except 防护 | ✅ 已修复 |
| M2 | MEDIUM | snmp.py:97 | 枚举映射 int(numeric_val) 对浮点值截断 → 仅对整数值做映射 | ✅ 已修复 |
| L1 | LOW | test_snmp.py | 缺少 v3 noAuthNoPriv/authNoPriv 安全级别测试 | 未修复（不影响功能） |

### 测试结果

- 修复前: 30/30 passed（pysnmp-lextudio 6.x）
- 修复后: 30/30 passed（pysnmp 7.x）
- SNMP + RTU + TCP 联合: 107/107 passed
