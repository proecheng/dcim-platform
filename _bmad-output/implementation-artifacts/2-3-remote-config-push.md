# Story 2.3: 远程配置下发

Status: done

## Story

As a 运维工程师,
I want 通过平台远程向网关下发采集配置,
so that 我不需要到现场修改网关配置。

## Acceptance Criteria (验收标准)

1. **AC-1: 配置下发 API** — 新增 `POST /api/v1/gateways/{id}/push-config` 端点，将指定网关关联的数据源配置打包为 JSON，通过 MQTT 发布到 `dcim/{site_id}/gw/{gw_id}/config`
2. **AC-2: 配置下发记录** — 每次下发创建 `ConfigPushRecord`（gateway_id、config_snapshot、status=pending、created_at），下发成功后更新 status=delivered
3. **AC-3: 配置下发历史** — 新增 `GET /api/v1/gateways/{id}/config-history` 分页查询配置下发记录
4. **AC-4: 配置构建服务** — 从数据库读取网关关联的 DataSource + DataSourcePoint，构建符合网关 DataSourceConfig 格式的配置 JSON
5. **AC-5: MQTT 发布能力** — MqttService 新增 `publish(topic, payload, qos=2)` 方法，支持向指定 topic 发布消息
6. **AC-6: 网关侧配置接收** — 网关 `ConfigReceiver` 订阅 `dcim/{site_id}/gw/{gw_id}/config`，收到配置后解析并通过回调通知上层热加载
7. **AC-7: 优雅降级** — MQTT 不可用时，push-config API 返回明确错误（503），不静默失败

## Tasks / Subtasks (任务分解)

- [ ] Task 1: ConfigPushRecord 模型 (AC: #2)
  - [ ] 1.1 在 `backend/app/models/gateway.py` 新增 `ConfigPushRecord` 模型（id, gateway_id, config_snapshot, status, error_message, created_at, updated_at）
  - [ ] 1.2 status 枚举: "pending", "delivered", "failed"

- [ ] Task 2: Schema 新增 (AC: #1, #3)
  - [ ] 2.1 新增 `ConfigPushResponse` schema（id, gateway_id, status, created_at）
  - [ ] 2.2 新增 `ConfigPushRecordResponse` schema（完整记录）

- [ ] Task 3: 配置构建服务 (AC: #4)
  - [ ] 3.1 创建 `backend/app/services/config_push.py`
  - [ ] 3.2 实现 `async def build_gateway_config(gateway_id: int, db) -> dict` — 查询 Gateway + DataSource + DataSourcePoint，构建配置 JSON
  - [ ] 3.3 配置格式匹配网关 DataSourceConfig 结构：datasources 列表，每个含 datasource_id, protocol_type, connection_params, collection_interval, points 列表

- [ ] Task 4: MQTT 发布能力 (AC: #5)
  - [ ] 4.1 MqttService 新增 `_client` 属性保存当前连接的 aiomqtt.Client 引用
  - [ ] 4.2 新增 `async def publish(topic, payload, qos=2)` 方法
  - [ ] 4.3 未连接时 publish 抛出 `RuntimeError("MQTT 未连接")`

- [ ] Task 5: 配置下发 API (AC: #1, #2, #3, #7)
  - [ ] 5.1 新增 `POST /api/v1/gateways/{gateway_id}/push-config` — 构建配置、创建记录、通过 MQTT 发布、更新记录状态
  - [ ] 5.2 新增 `GET /api/v1/gateways/{gateway_id}/config-history` — 分页查询下发记录
  - [ ] 5.3 MQTT 不可用时返回 503

- [ ] Task 6: 网关侧 ConfigReceiver (AC: #6)
  - [ ] 6.1 实现 `gateway/config_receiver.py` — `ConfigReceiver` 类
  - [ ] 6.2 `start(mqtt_subscribe_fn)` 方法：订阅 config topic
  - [ ] 6.3 `_on_config(payload)` 方法：解析配置 JSON，转换为 DataSourceConfig 列表
  - [ ] 6.4 `on_config_received` 回调：通知上层热加载

- [ ] Task 7: 单元测试 (AC: 全部)
  - [ ] 7.1 测试 build_gateway_config — 正确构建配置 JSON（含 datasource + points）
  - [ ] 7.2 测试 build_gateway_config — 网关无数据源时返回空列表
  - [ ] 7.3 测试 POST push-config API — 成功下发（mock MQTT publish）
  - [ ] 7.4 测试 POST push-config API — MQTT 不可用返回 503
  - [ ] 7.5 测试 GET config-history API — 分页返回记录
  - [ ] 7.6 测试 ConfigPushRecord 创建和状态更新
  - [ ] 7.7 测试 ConfigReceiver — 解析配置 JSON 为 DataSourceConfig 列表
  - [ ] 7.8 测试 ConfigReceiver — 无效 JSON 不崩溃
  - [ ] 7.9 测试 MqttService.publish — 调用 client.publish（mock）
  - [ ] 7.10 测试 MqttService.publish — 未连接时抛出 RuntimeError

## Dev Notes (开发指南)

### 1. 文件位置

```
backend/app/models/gateway.py              # 修改 — 新增 ConfigPushRecord 模型
backend/app/schemas/gateway.py             # 修改 — 新增 ConfigPush schema
backend/app/services/config_push.py        # 新建 — 配置构建+下发服务
backend/app/mqtt/client.py                 # 修改 — 新增 publish 方法
backend/app/api/v1/gateways.py             # 修改 — 新增 push-config 和 config-history 端点
gateway/config_receiver.py                 # 修改 — 实现 ConfigReceiver
backend/tests/test_config_push.py          # 新建 — 单元测试
```

### 2. ConfigPushRecord 模型

```python
class ConfigPushRecord(Base):
    """配置下发记录"""
    __tablename__ = "config_push_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    gateway_id = Column(String(50), nullable=False, index=True, comment="网关标识")
    config_snapshot = Column(JSON, nullable=False, comment="下发的配置快照")
    status = Column(String(20), default="pending", comment="状态: pending/delivered/failed")
    error_message = Column(String(500), comment="错误信息")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")
```

### 3. 配置构建服务

```python
# backend/app/services/config_push.py

import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..models.gateway import Gateway, DataSource, DataSourcePoint, ConfigPushRecord

logger = logging.getLogger(__name__)


async def build_gateway_config(gateway_id: int, db: AsyncSession) -> dict:
    """构建网关采集配置 JSON

    返回格式:
    {
        "gateway_id": "gw-001",
        "datasources": [
            {
                "datasource_id": "ds-1",
                "protocol_type": "modbus_tcp",
                "connection_params": {...},
                "collection_interval": 5,
                "write_enabled": false,
                "points": [
                    {"point_id": "p1", "address": "40001", "data_type": "float32", ...}
                ]
            }
        ]
    }
    """
    # 查询网关
    gw_result = await db.execute(select(Gateway).where(Gateway.id == gateway_id))
    gateway = gw_result.scalar_one_or_none()
    if not gateway:
        raise ValueError(f"网关不存在: {gateway_id}")

    # 查询关联数据源
    ds_result = await db.execute(
        select(DataSource).where(
            DataSource.gateway_id == gateway_id,
            DataSource.is_enabled == True,
        )
    )
    datasources = ds_result.scalars().all()

    ds_configs = []
    for ds in datasources:
        # 查询数据源点位
        pt_result = await db.execute(
            select(DataSourcePoint).where(DataSourcePoint.datasource_id == ds.id)
        )
        points = pt_result.scalars().all()

        ds_config = {
            "datasource_id": str(ds.id),
            "protocol_type": ds.protocol_type,
            "connection_params": ds.connection_config,
            "collection_interval": ds.collection_interval,
            "write_enabled": ds.write_enabled,
            "points": [
                {
                    "point_id": str(pt.point_id or pt.id),
                    "address": pt.address,
                    "data_type": pt.data_type,
                    "scale": pt.scale,
                    "offset": pt.offset,
                    "enum_mapping": pt.enum_mapping,
                    "is_dry_contact": pt.is_dry_contact,
                }
                for pt in points
            ],
        }
        ds_configs.append(ds_config)

    return {
        "gateway_id": gateway.gateway_id,
        "datasources": ds_configs,
    }


async def push_config_to_gateway(
    gateway_id: int,
    mqtt_publish_fn,
    db: AsyncSession,
) -> ConfigPushRecord:
    """构建配置并通过 MQTT 下发到网关"""
    config = await build_gateway_config(gateway_id, db)

    # 创建下发记录
    record = ConfigPushRecord(
        gateway_id=config["gateway_id"],
        config_snapshot=config,
        status="pending",
    )
    db.add(record)
    await db.flush()

    # 查询网关获取 site_id
    gw_result = await db.execute(select(Gateway).where(Gateway.id == gateway_id))
    gateway = gw_result.scalar_one()
    topic = f"dcim/{gateway.site_id}/gw/{gateway.gateway_id}/config"

    try:
        import json
        await mqtt_publish_fn(topic, json.dumps(config), qos=2)
        record.status = "delivered"
        logger.info("配置下发成功: %s → %s", gateway.gateway_id, topic)
    except Exception as e:
        record.status = "failed"
        record.error_message = str(e)[:500]
        logger.error("配置下发失败: %s — %s", gateway.gateway_id, e)

    await db.commit()
    return record
```

### 4. MqttService publish 方法

```python
# 在 MqttService 类中新增:

def __init__(self) -> None:
    self._task: Optional[asyncio.Task] = None
    self._heartbeat_task: Optional[asyncio.Task] = None
    self._running = False
    self._client = None  # 新增：保存当前 aiomqtt.Client 引用

# 在 _connect_loop 中，连接成功后保存 client 引用:
#   self._client = client
# 在连接断开/异常时清除:
#   self._client = None

async def publish(self, topic: str, payload: str, qos: int = 2) -> None:
    """发布 MQTT 消息"""
    if self._client is None:
        raise RuntimeError("MQTT 未连接")
    await self._client.publish(topic, payload, qos=qos)
    logger.debug("MQTT 消息已发布: topic=%s, qos=%d", topic, qos)
```

### 5. ConfigReceiver（网关侧）

```python
# gateway/config_receiver.py

import json
import logging
from typing import Any, Callable, Optional

from .adapters.base import DataSourceConfig, PointConfig

logger = logging.getLogger(__name__)


class ConfigReceiver:
    """远程配置接收器 — 订阅 MQTT config topic，解析并回调"""

    def __init__(
        self,
        gateway_id: str,
        site_id: int = 1,
        on_config_received: Optional[Callable[[list[DataSourceConfig]], Any]] = None,
    ) -> None:
        self._gateway_id = gateway_id
        self._site_id = site_id
        self._on_config_received = on_config_received

    @property
    def topic(self) -> str:
        return f"dcim/{self._site_id}/gw/{self._gateway_id}/config"

    def handle_message(self, payload_str: str) -> list[DataSourceConfig]:
        """解析配置消息，返回 DataSourceConfig 列表"""
        try:
            data = json.loads(payload_str)
        except json.JSONDecodeError:
            logger.error("配置消息 JSON 解析失败")
            return []

        if not isinstance(data, dict) or "datasources" not in data:
            logger.warning("配置消息格式无效: 缺少 datasources 字段")
            return []

        configs = []
        for ds_raw in data["datasources"]:
            try:
                points = [
                    PointConfig(
                        point_id=p["point_id"],
                        address=p["address"],
                        data_type=p.get("data_type", "float32"),
                        scale=float(p.get("scale", 1.0)),
                        offset=float(p.get("offset", 0.0)),
                        enum_mapping=p.get("enum_mapping"),
                        is_dry_contact=bool(p.get("is_dry_contact", False)),
                    )
                    for p in ds_raw.get("points", [])
                ]
                config = DataSourceConfig(
                    datasource_id=ds_raw["datasource_id"],
                    protocol_type=ds_raw["protocol_type"],
                    connection_params=ds_raw.get("connection_params", {}),
                    collection_interval=int(ds_raw.get("collection_interval", 5)),
                    write_enabled=bool(ds_raw.get("write_enabled", False)),
                    points=points,
                )
                configs.append(config)
            except (KeyError, TypeError, ValueError) as e:
                logger.warning("解析数据源配置失败，跳过: %s", e)
                continue

        logger.info("收到远程配置: %d 个数据源", len(configs))

        if self._on_config_received and configs:
            self._on_config_received(configs)

        return configs
```

### 6. API 端点

```python
# POST /api/v1/gateways/{gateway_id}/push-config
# 路由位置：在 /{gateway_id}/events 之后，/{gateway_id} PUT 之前

@router.post("/{gateway_id}/push-config", response_model=ConfigPushResponse, summary="下发配置到网关")
async def push_config(gateway_id: int, db, user=require_operator):
    # 获取全局 MqttService 实例（从 app.state 或模块级变量）
    # 由于 MqttService 是后台任务，这里通过 mqtt_service 全局实例获取 publish 方法
    # 如果 MQTT 未连接，返回 503
    ...

# GET /api/v1/gateways/{gateway_id}/config-history
@router.get("/{gateway_id}/config-history", response_model=PageResponse[ConfigPushRecordResponse], summary="配置下发历史")
async def config_history(gateway_id: int, page, page_size, db, user=require_viewer):
    ...
```

### 7. MQTT 全局实例

由于 push-config API 需要调用 MqttService.publish，需要一个全局可访问的 MqttService 实例。

方案：在 `backend/app/mqtt/__init__.py` 中创建模块级实例：
```python
"""MQTT 通信层"""
from .client import MqttService

# 全局 MQTT 服务实例
mqtt_service = MqttService()
```

API 中通过 `from ...mqtt import mqtt_service` 获取实例。

### 8. 关键约束

- **路由顺序**: `push-config` 和 `config-history` 在 `/{gateway_id}` GET 之后、PUT 之前
- **QoS 2**: 配置下发使用 QoS 2 确保精确一次送达
- **MQTT 不可用**: publish 抛出 RuntimeError，API 捕获后返回 503
- **配置快照**: ConfigPushRecord 保存完整配置 JSON，便于审计和回溯
- **flush vs commit**: push_config_to_gateway 内部统一 commit
- **测试使用 mock**: mock MqttService.publish，不需要真实 MQTT Broker
- **lazy logging**: 使用 `%s` 格式

### 9. 测试策略

- build_gateway_config 测试：使用内存 SQLite，创建 Gateway + DataSource + DataSourcePoint 测试数据
- push-config API 测试：mock mqtt_service.publish，验证记录创建和状态更新
- config-history API 测试：创建 ConfigPushRecord 记录，验证分页查询
- ConfigReceiver 测试：纯函数测试，验证 JSON 解析和 DataSourceConfig 转换
- MqttService.publish 测试：mock _client，验证调用和未连接异常

### Project Structure Notes

- `backend/app/models/gateway.py` — 新增 ConfigPushRecord 模型
- `backend/app/schemas/gateway.py` — 新增 ConfigPush schema
- `backend/app/services/config_push.py` — 新建，配置构建+下发
- `backend/app/mqtt/client.py` — 修改，新增 publish + _client
- `backend/app/mqtt/__init__.py` — 修改，导出全局 mqtt_service 实例
- `backend/app/api/v1/gateways.py` — 修改，新增端点
- `gateway/config_receiver.py` — 修改（从 stub 实现）
- 测试文件放在 `backend/tests/test_config_push.py`

### References

- [Source: architecture.md#4.6] MQTT Topic: dcim/{site_id}/gw/{gw_id}/config, QoS 2
- [Source: epics.md#Story 2.3] Acceptance Criteria
- [Source: config_loader.py] DataSourceConfig 格式参考
- [Source: base.py] DataSourceConfig, PointConfig 数据类

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

