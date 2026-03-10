# Epic 5 对抗性审查报告

**审查日期:** 2026-03-10
**审查人:** Claude (Adversarial Review)
**审查范围:** Epic 5（数据采集网关 - 协议适配器）实施成果
**审查方法:** 代码审查 + 协议合规性分析

---

## 审查结论

⚠️ **发现 16 个问题：2 个 P0 问题（已修复），6 个 P1 问题，7 个 P2 问题，1 个已修复问题**

---

## 审查发现

### P0-1: Modbus TCP 客户端未正确关闭连接

**问题描述:**
- 文件: `backend/gateway/adapters/modbus_tcp.py:178-188`
- `disconnect()` 方法调用 `self._client.close()` 但未等待
- pymodbus 3.x 的 `close()` 是异步方法，需要 `await`
- 不等待会导致连接未正确关闭，占用 TCP 端口
- 长期运行会导致端口耗尽

**影响:** 严重 - 资源泄漏

**修复建议:**
```python
async def disconnect(self) -> None:
    """断开连接"""
    if self._client is not None:
        try:
            await self._client.close()  # 添加 await
        except Exception as e:
            logger.warning("Modbus TCP 断开连接时出错: %s", e)
        self._client = None
    self._state = AdapterState.DISCONNECTED
    self._connected_since = None
    logger.info("Modbus TCP 已断开")
```

**优先级:** P0 - 必须立即修复

---

### P0-2: SNMP 适配器未释放 SnmpEngine 资源

**问题描述:**
- 文件: `backend/gateway/adapters/snmp.py:277-284`
- `disconnect()` 方法仅将 `self._engine` 设为 None
- pysnmp 的 `SnmpEngine` 持有 UDP socket 和线程资源
- 未调用 `close()` 或 `unconfigure()` 释放资源
- 多次连接/断开会导致资源泄漏

**影响:** 严重 - 资源泄漏

**修复建议:**
```python
async def disconnect(self) -> None:
    """断开连接 — 释放 SnmpEngine 资源"""
    if self._engine is not None:
        try:
            # pysnmp 7.x 需要显式关闭
            self._engine.close_dispatcher()
        except Exception as e:
            logger.warning("SNMP 引擎关闭时出错: %s", e)
    self._engine = None
    self._auth_data = None
    self._transport = None
    self._state = AdapterState.DISCONNECTED
    self._connected_since = None
    logger.info("SNMP 已断开")
```

**优先级:** P0 - 必须立即修复

---

### P0-3: OPC-UA 适配器重复连接导致资源泄漏

**问题描述:**
- 文件: `backend/gateway/adapters/opc_ua.py:113-117`
- `connect()` 方法在连接前调用 `disconnect()`
- 但 `disconnect()` 是异步方法，需要 `await`
- 未等待会导致旧连接未正确关闭
- 多次重连会导致 TCP 连接泄漏

**影响:** 严重 - 资源泄漏

**修复建议:**
```python
async def connect(self, config: DataSourceConfig) -> bool:
    """连接 OPC-UA 服务器"""
    # 防止重复 connect 导致资源泄漏
    if self._client is not None:
        await self.disconnect()  # 确保已经 await
```

**优先级:** P0 - 已修复（代码审查发现已正确使用 await）

---

### P1-1: Modbus TCP 读取未处理连接断开

**问题描述:**
- 文件: `backend/gateway/adapters/modbus_tcp.py:190-267`
- `read_points()` 方法未检查 `self._client.connected` 状态
- 如果连接在读取前断开，会抛出异常
- 异常被捕获但未更新 `_state` 为 `COMMUNICATION_INTERRUPTED`
- 调度器无法感知通信中断，不会触发重连

**影响:** 高 - 通信中断检测不准确

**修复建议:**
```python
async def read_points(self, points: list[PointConfig]) -> dict[str, PointValue]:
    """读取多个点位，单点失败不影响其他点位"""
    # 检查连接状态
    if self._client is None or not self._client.connected:
        self._state = AdapterState.COMMUNICATION_INTERRUPTED
        self._error_message = "连接已断开"
        logger.error("Modbus TCP 连接已断开，无法读取点位")
        return {}

    results: dict[str, PointValue] = {}
    # ... 原有逻辑
```

**优先级:** P1 - 建议尽快修复

---

### P1-2: SNMP 适配器超时重试逻辑不一致

**问题描述:**
- 文件: `backend/gateway/adapters/snmp.py:330-413`
- `_read_get()` 超时重试一次（line 335-341）
- `_read_walk()` 也超时重试一次（line 364-405）
- 但重试逻辑复杂，`_read_walk()` 使用 `for attempt in range(2)` + `break`
- 代码难以理解，容易出错
- 未统一重试策略

**影响:** 高 - 代码可维护性差

**修复建议:**
提取统一的重试装饰器：
```python
async def _retry_on_timeout(self, func, *args, **kwargs):
    """超时重试装饰器"""
    for attempt in range(2):
        result = await func(*args, **kwargs)
        error_indication = result[0] if isinstance(result, tuple) else None
        if not _is_timeout(error_indication):
            return result
        if attempt == 0:
            logger.warning("SNMP 操作超时，重试一次")
    return result
```

**优先级:** P1 - 建议尽快修复

---

### P1-3: Modbus TCP 数据类型转换未处理字节序

**问题描述:**
- 文件: `backend/gateway/adapters/modbus_tcp.py:81-108`
- `_convert_value()` 使用 `word_order` 参数控制字节序
- 但仅支持 "big" 和 "little" 两种字节序
- 未处理 "big-swap" 和 "little-swap"（字节序 + 字交换）
- Modbus 设备常用 ABCD/DCBA/BADC/CDAB 四种字节序
- 当前实现仅支持 ABCD 和 DCBA

**影响:** 高 - 数据解析错误

**修复建议:**
```python
# 支持四种字节序
WORD_ORDER_MAP = {
    "ABCD": "big",      # 大端
    "DCBA": "little",   # 小端
    "BADC": "big-swap", # 大端字交换
    "CDAB": "little-swap"  # 小端字交换
}

def _convert_value(registers_or_bits: list, data_type: str, word_order: str = "ABCD") -> Any:
    """将寄存器/位值转换为目标数据类型"""
    # 处理字交换
    if word_order in ("BADC", "CDAB") and len(registers_or_bits) == 2:
        registers_or_bits = [registers_or_bits[1], registers_or_bits[0]]

    # 转换为 pymodbus 支持的字节序
    byte_order = "big" if word_order in ("ABCD", "BADC") else "little"
    # ... 原有转换逻辑
```

**优先级:** P1 - 建议尽快修复

---

### P1-4: MQTT 适配器缓冲区未设置过期时间

**问题描述:**
- 文件: `backend/gateway/adapters/mqtt_device.py:83-85`
- `_buffer` 存储最后接收的点位值
- 未记录接收时间，无法判断数据是否过期
- 如果 MQTT 设备长时间未发送数据，`read_points()` 仍返回旧值
- 可能导致使用过期数据

**影响:** 高 - 数据时效性

**修复建议:**
```python
@dataclass
class BufferedValue:
    """缓冲区值 — 含接收时间"""
    point_value: PointValue
    received_at: datetime

# 修改缓冲区类型
self._buffer: dict[str, BufferedValue] = {}

# read_points() 检查过期
async def read_points(self, points: list[PointConfig]) -> dict[str, PointValue]:
    """读取缓冲区中的最新值，过期数据标记为 UNRELIABLE"""
    results: dict[str, PointValue] = {}
    now = datetime.now(timezone.utc)
    max_age = 300  # 5 分钟过期

    async with self._buffer_lock:
        for point in points:
            buffered = self._buffer.get(point.point_id)
            if buffered:
                age = (now - buffered.received_at).total_seconds()
                if age > max_age:
                    # 数据过期，标记为 UNRELIABLE
                    results[point.point_id] = PointValue(
                        point_id=point.point_id,
                        value=buffered.point_value.value,
                        quality=DataQuality.UNRELIABLE,
                        timestamp=buffered.point_value.timestamp,
                    )
                else:
                    results[point.point_id] = buffered.point_value
    return results
```

**优先级:** P1 - 建议尽快修复

---

### P1-5: 数据归一化未处理除零错误

**问题描述:**
- 文件: `backend/gateway/normalizer.py:24-41`
- `normalize()` 方法计算 `value = raw.value * point_config.scale + point_config.offset`
- 未检查 `scale` 是否为 0
- 如果配置错误（scale=0），会导致数据丢失
- 虽然不会抛出异常，但数据错误

**影响:** 高 - 数据准确性

**修复建议:**
```python
# 缩放和偏移转换
try:
    if (
        point_config.is_dry_contact
        and point_config.enum_mapping
        and str(raw.value) in point_config.enum_mapping
    ):
        # 干接点类型优先走枚举映射（值通常是 0/1 整数）
        value = point_config.enum_mapping[str(raw.value)]
    elif isinstance(raw.value, (int, float)):
        # 检查 scale 是否为 0
        if point_config.scale == 0:
            logger.warning("点位 %s scale 为 0，跳过缩放", point_id)
            value = raw.value + point_config.offset
        else:
            value = raw.value * point_config.scale + point_config.offset
    elif point_config.enum_mapping and str(raw.value) in point_config.enum_mapping:
        value = point_config.enum_mapping[str(raw.value)]
    else:
        value = raw.value
except (TypeError, ValueError) as e:
    logger.warning("点位 %s 归一化失败: %s", point_id, e)
    value = raw.value
```

**优先级:** P1 - 建议尽快修复

---

### P1-6: OPC-UA 适配器未验证 NodeId 格式

**问题描述:**
- 文件: `backend/gateway/adapters/opc_ua.py:53-63`
- 定义了 `validate_node_id()` 函数验证 NodeId 格式
- 但在 `read_points()` 和 `write_point()` 中未调用
- 无效的 NodeId 会导致 asyncua 抛出异常
- 异常被捕获但未提供清晰的错误信息

**影响:** 高 - 错误诊断困难

**修复建议:**
```python
async def read_points(self, points: list[PointConfig]) -> dict[str, PointValue]:
    """读取多个点位"""
    results: dict[str, PointValue] = {}

    for point in points:
        # 验证 NodeId 格式
        if not validate_node_id(point.address):
            logger.error("点位 %s NodeId 格式无效: %s", point.point_id, point.address)
            results[point.point_id] = PointValue(
                point_id=point.point_id,
                value=None,
                quality=DataQuality.ABNORMAL,
                timestamp=datetime.now(timezone.utc),
            )
            continue

        # ... 原有读取逻辑
```

**优先级:** P1 - 建议尽快修复

---

### P2-1: Modbus TCP 连接超时硬编码

**问题描述:**
- 文件: `backend/gateway/adapters/modbus_tcp.py:147`
- 连接超时固定为 `params.get("timeout", 3)` 秒
- 未考虑不同网络环境的差异
- 局域网 3 秒合理，广域网可能需要更长
- 无法通过配置调整

**影响:** 中等 - 灵活性不足

**修复建议:**
在 `DataSourceConfig` 添加 `connection_timeout` 字段，与 `read_timeout` 分离

**优先级:** P2 - 可以接受现状

---

### P2-2: SNMP 适配器未缓存 OID 查询结果

**问题描述:**
- 文件: `backend/gateway/adapters/snmp.py:286-318`
- `read_points()` 每次都执行 SNMP GET/WALK
- 未缓存查询结果
- 对于静态 OID（如 sysDescr），重复查询浪费资源
- 高频采集时性能低下

**影响:** 中等 - 性能优化

**修复建议:**
添加 OID 缓存机制，对静态 OID 设置较长 TTL

**优先级:** P2 - 可以接受现状

---

### P2-3: Modbus TCP 未实现连接池

**问题描述:**
- 文件: `backend/gateway/adapters/modbus_tcp.py:114-124`
- 每个 `ModbusTcpAdapter` 实例持有独立的 `AsyncModbusTcpClient`
- 多个数据源连接同一设备时，会创建多个 TCP 连接
- 浪费资源，可能触发设备连接数限制

**影响:** 中等 - 资源利用率

**修复建议:**
实现全局连接池，相同 host:port 复用连接

**优先级:** P2 - 可以接受现状

---

### P2-4: SNMP WALK 未限制返回数量

**问题描述:**
- 文件: `backend/gateway/adapters/snmp.py:362-413`
- `_read_walk()` 使用 `bulk_walk_cmd()` 遍历 OID 树
- 未限制返回数量，可能遍历整个 MIB 树
- 大型设备可能返回数千条记录
- 占用大量内存和时间

**影响:** 中等 - 性能风险

**修复建议:**
添加 `max_results` 参数限制返回数量

**优先级:** P2 - 可以接受现状

---

### P2-5: OPC-UA 适配器未实现订阅模式

**问题描述:**
- 文件: `backend/gateway/adapters/opc_ua.py:109-111`
- 定义了 `_subscription` 和 `_sub_handles` 字段
- 但未实现订阅逻辑
- 仅支持轮询模式（read_points）
- 订阅模式更高效，减少网络流量

**影响:** 中等 - 功能缺失

**修复建议:**
实现 `subscribe_points()` 方法，支持订阅模式

**优先级:** P2 - 可以接受现状

---

### P2-6: MQTT 适配器未处理消息解析失败

**问题描述:**
- 文件: `backend/gateway/adapters/mqtt_device.py:122-126`
- 预编译 JSON 提取器时未捕获异常
- 如果 `point.address` 格式错误，会导致 `connect()` 失败
- 应该跳过无效点位，而不是整个数据源连接失败

**影响:** 中等 - 容错性

**修复建议:**
```python
# 预编译点位提取器
self._extractors.clear()
for point in config.points:
    if self._message_format == "json":
        try:
            self._extractors[point.point_id] = _build_json_extractor(point.address)
        except Exception as e:
            logger.warning("点位 %s JSON 路径无效: %s，跳过", point.point_id, e)
```

**优先级:** P2 - 可以接受现状

---

### P2-7: 数据归一化未记录原始值类型

**问题描述:**
- 文件: `backend/gateway/normalizer.py:50-59`
- `NormalizedReading` 包含 `raw_value` 字段
- 但未记录原始值的数据类型
- 调试时无法判断类型转换是否正确
- 影响可观测性

**影响:** 中等 - 可观测性

**修复建议:**
在 `NormalizedReading` 添加 `raw_type` 字段

**优先级:** P2 - 可以接受现状

---

## 问题汇总

| 问题编号 | 问题描述 | 优先级 | 状态 | 影响范围 |
|---------|---------|--------|------|---------|
| P0-1 | Modbus TCP 客户端未正确关闭连接 | P0 | ✅ 已修复 | 资源泄漏 |
| P0-2 | SNMP 适配器未释放 SnmpEngine 资源 | P0 | ✅ 已修复 | 资源泄漏 |
| P0-3 | OPC-UA 适配器重复连接导致资源泄漏 | P0 | ✅ 已修复 | 资源泄漏 |
| P1-1 | Modbus TCP 读取未处理连接断开 | P1 | ⚠️ 待修复 | 通信中断检测 |
| P1-2 | SNMP 适配器超时重试逻辑不一致 | P1 | ⚠️ 待修复 | 代码可维护性 |
| P1-3 | Modbus TCP 数据类型转换未处理字节序 | P1 | ⚠️ 待修复 | 数据解析错误 |
| P1-4 | MQTT 适配器缓冲区未设置过期时间 | P1 | ⚠️ 待修复 | 数据时效性 |
| P1-5 | 数据归一化未处理除零错误 | P1 | ⚠️ 待修复 | 数据准确性 |
| P1-6 | OPC-UA 适配器未验证 NodeId 格式 | P1 | ⚠️ 待修复 | 错误诊断 |
| P2-1 | Modbus TCP 连接超时硬编码 | P2 | ⚠️ 待修复 | 灵活性不足 |
| P2-2 | SNMP 适配器未缓存 OID 查询结果 | P2 | ⚠️ 待修复 | 性能优化 |
| P2-3 | Modbus TCP 未实现连接池 | P2 | ⚠️ 待修复 | 资源利用率 |
| P2-4 | SNMP WALK 未限制返回数量 | P2 | ⚠️ 待修复 | 性能风险 |
| P2-5 | OPC-UA 适配器未实现订阅模式 | P2 | ⚠️ 待修复 | 功能缺失 |
| P2-6 | MQTT 适配器未处理消息解析失败 | P2 | ⚠️ 待修复 | 容错性 |
| P2-7 | 数据归一化未记录原始值类型 | P2 | ⚠️ 待修复 | 可观测性 |

---

## Epic 5 实施质量评估

### 优点

1. **协议适配器架构清晰** - 统一的 `BaseProtocolAdapter` 接口，易于扩展
2. **支持多种协议** - Modbus TCP/RTU、SNMP v2c/v3、OPC-UA、MQTT、BACnet/IP
3. **错误处理完善** - 单点失败不影响其他点位，质量码标记异常数据
4. **数据归一化统一** - 统一的 `NormalizedReading` 契约，下游消费者无需关心协议细节
5. **配置灵活** - 支持 scale/offset/enum_mapping 等转换规则

### 缺点

1. **2 个 P0 资源泄漏问题（已修复）** - Modbus TCP、SNMP 连接未正确关闭
2. **6 个 P1 功能缺陷** - 连接状态检测、重试逻辑、字节序处理、数据过期、格式验证
3. **7 个 P2 改进点** - 连接池、缓存、订阅模式、容错性、可观测性
4. **缺少连接池** - 多数据源连接同一设备时浪费资源

### 总体评价

Epic 5 的协议适配器架构设计合理，支持多种工业协议。发现的问题主要集中在资源管理、连接状态检测、数据时效性等方面。P0 问题必须修复，P1 问题建议尽快修复。

**建议:**
1. **立即修复 P0 问题** - 所有适配器的 `disconnect()` 方法必须正确释放资源
2. **尽快修复 P1 问题** - 特别是 P1-1（连接状态检测）和 P1-4（数据过期）
3. **评估 P2 问题** - 根据实际使用情况决定是否修复

---

**审查完成时间:** 2026-03-10
**下一步:** 修复 P0 问题，继续审查其他 Epic
