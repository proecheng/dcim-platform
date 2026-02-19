# Story 15-4: OPC-UA 适配器设计方案

## Story 验收标准 (来自 epics.md)

- Given 集成工程师配置 OPC-UA 数据源（端点 URL、节点 ID 映射、证书认证）
- When 采集调度器触发
- Then OpcUaAdapter 通过 asyncua 异步读取指定节点数据
- And 支持证书认证
- And 支持节点浏览和订阅模式

## 概述

基于 asyncua (opcua-asyncio) 库实现 OpcUaAdapter，遵循 BaseProtocolAdapter ABC，注册为 "opc_ua" 协议类型。

## 核心设计决策

1. **asyncua 是原生 asyncio** — 无需 asyncio.to_thread() 包装
2. **Client 实例管理** — 每个 OpcUaAdapter 持有独立的 asyncua.Client 实例（不同于 BACnet 的全局单例，因为 OPC-UA 没有端口绑定限制，每个连接是独立的 TCP session）
3. **认证方式**:
   - 匿名（默认）
   - 用户名/密码 (client.set_user() / client.set_password())
   - 证书认证 (client.set_security() with X.509 证书路径)
4. **点位地址格式**: OPC-UA NodeId 字符串，如 "ns=2;i=1001", "ns=2;s=Temperature", "ns=2;g=xxx-guid"
5. **read_points()**: 使用 asyncua 的 client.read_values() 批量读取节点值（原生支持批量读取多个节点）
6. **write_point()**: 使用 node.write_value() 写入
7. **test_connection()**: 读取 Server_ServerStatus_CurrentTime 节点验证连通性
8. **扩展方法**: browse_nodes() 递归浏览节点树，subscribe_data_change() 订阅模式

## connection_config 示例

```json
{
    "endpoint_url": "opc.tcp://192.168.1.100:4840",
    "security_policy": "none",
    "security_mode": "none",
    "auth_type": "anonymous",
    "auth_config": {
        "username": "admin",
        "password": "secret",
        "certificate_path": "/path/to/cert.der",
        "private_key_path": "/path/to/key.pem",
        "server_certificate_path": "/path/to/server.der"
    },
    "timeout": 10,
    "session_timeout": 3600000
}
```

## 点位地址格式

OPC-UA NodeId 字符串:
- `ns=2;i=1001` — 命名空间2，数字标识符1001
- `ns=2;s=Temperature` — 命名空间2，字符串标识符
- `i=2258` — 命名空间0（默认），Server_ServerStatus_CurrentTime

## BaseProtocolAdapter ABC 接口

所有方法必须实现:

```python
class BaseProtocolAdapter(ABC):
    async def connect(self, config: DataSourceConfig) -> bool
    async def disconnect(self) -> None
    async def read_points(self, points: list[PointConfig]) -> dict[str, PointValue]
    async def write_point(self, point_id: str, value: Any) -> bool
    async def test_connection(self) -> ConnectionResult
    def get_status(self) -> AdapterStatus
```

## DataSourceConfig 数据类

```python
@dataclass
class DataSourceConfig:
    datasource_id: str
    protocol_type: str
    connection_params: dict
    collection_interval: int = 5
    write_enabled: bool = False
    points: list[PointConfig] = field(default_factory=list)
    retry_base_delay: float = 1.0
    retry_max_delay: float = 60.0
    retry_max_failures: int = 5
```

## 已有适配器的关键模式 (必须遵循)

- connect() 先验证配置，缺少必要参数时设 CONFIG_ERROR 并 return False
- connect() 如果已连接，先调 disconnect() 防止资源泄漏
- read_points() 网络未连接时返回所有点位 ABNORMAL
- read_points() 连续失败达到 retry_max_failures 时设 COMMUNICATION_INTERRUPTED
- write_point() 检查 write_enabled、config 存在、point_cfg 存在、value 非 None
- test_connection() 返回 ConnectionResult(success, message, latency_ms, sample_data)
- 所有网络操作使用 asyncio.wait_for(timeout) 包装
- 第三方库 import 放在方法内部，ImportError 时设 CONFIG_ERROR

## asyncua 库 API 参考

来自 opcua-asyncio 文档:

```python
from asyncua import Client, Node, ua

# 连接
async with Client(url='opc.tcp://localhost:4840') as client:
    node = client.get_node('ns=2;i=1001')
    value = await node.read_value()

# 用户名密码认证
client = Client(url="opc.tcp://192.168.2.64:4840")
client.set_user("test")
client.set_password("test")
await client.connect()

# 证书认证
from asyncua.crypto.security_policies import SecurityPolicyBasic256Sha256
await client.set_security(
    SecurityPolicyBasic256Sha256,
    certificate=str(cert_path),
    private_key=str(private_key_path),
    server_certificate="server_certificate.der",
)

# 批量读取
nodes = [client.get_node('ns=2;i=1001'), client.get_node('ns=2;i=1002')]
values = await client.read_values(nodes)

# 写入
node = client.get_node('ns=2;i=1001')
await node.write_value(42.0)

# 浏览
children = await node.get_children()
display_name = await node.read_display_name()

# 订阅
class SubHandler:
    def datachange_notification(self, node, val, data):
        print(f"Data change: {node} = {val}")

handler = SubHandler()
subscription = await client.create_subscription(500, handler)
handle = await subscription.subscribe_data_change(node)
```

## 实现步骤

### Step 1: 创建 gateway/adapters/opc_ua.py

实现 OpcUaAdapter 类:

1. NodeId 解析函数 `parse_node_id(address: str)` — 验证 NodeId 格式
2. `__init__()` — 初始化状态字段
3. `connect(config)` — 验证配置 → 创建 Client → 设置认证 → 连接 → 验证
4. `disconnect()` — 关闭 Client
5. `read_points(points)` — 批量读取节点值，失败时逐个读取 fallback
6. `write_point(point_id, value)` — 写入节点值
7. `test_connection()` — 读取 ServerStatus 验证连通性
8. `get_status()` — 返回 AdapterStatus
9. `browse_nodes(node_id)` — 浏览节点树（扩展方法）
10. `subscribe_data_change(points, handler, interval)` — 订阅数据变化（扩展方法）
11. `unsubscribe()` — 取消订阅（扩展方法）

### Step 2: 更新 gateway/adapters/__init__.py

添加 `from . import opc_ua` 导入触发注册。

### Step 3: 创建 backend/tests/test_opc_ua_adapter.py

约 40 个测试用例，覆盖:
- NodeId 解析（正常/异常格式）
- 注册表注册验证
- connect() 各种场景（成功、缺少配置、ImportError、连接失败、重复连接）
- disconnect() 正常/异常
- read_points() 批量读取成功、部分失败、全部失败、连续失败触发 COMMUNICATION_INTERRUPTED
- write_point() 成功、禁用、未连接、value=None
- test_connection() 成功、超时、异常
- get_status() 各状态
- browse_nodes() 正常/异常
- subscribe/unsubscribe 生命周期
- 认证方式（匿名、用户名密码、证书）

## 文件清单

- `gateway/adapters/opc_ua.py` — OpcUaAdapter 实现（~400行）
- `gateway/adapters/__init__.py` — 添加 from . import opc_ua 导入
- `backend/tests/test_opc_ua_adapter.py` — 测试文件（~40 tests）
