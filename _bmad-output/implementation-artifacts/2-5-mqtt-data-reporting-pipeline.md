# Story 2.5: MQTT 数据上报链路

Status: done

## Story

As a 开发者,
I want 后端通过 MQTT 客户端接收网关上报的数据,
so that 采集数据可以进入后端处理流水线。

## Acceptance Criteria (验收标准)

1. **AC-1: 网关 MQTT 客户端** — `GatewayMqttClient` 封装 aiomqtt，提供 `publish(topic, payload)` 方法，连接断开时自动将数据写入 OfflineCache
2. **AC-2: 数据上报格式** — 网关将 NormalizedReading 列表转换为 MQTT 数据消息格式：`{"gw_id": "...", "ts": epoch, "points": [{"id": "p001", "v": 25.6, "q": 0, "t": epoch}]}`
3. **AC-3: 后端数据订阅** — MqttService 订阅 `dcim/+/gw/+/data`，收到消息后调用 `handle_point_data` 处理
4. **AC-4: 后端数据入库** — `handle_point_data` 将点位数据批量写入 `point_data_latest` 表（point_id, value, quality, timestamp, gateway_id），更新最新值
5. **AC-5: 离线缓存集成** — GatewayMqttClient 连接断开时，publish 自动降级为 OfflineCache.enqueue；重连后自动 flush_batch
6. **AC-6: QoS 配置** — 数据上报使用 QoS 1

## Tasks / Subtasks (任务分解)

- [ ] Task 1: 网关 MQTT 客户端 (AC: #1, #5, #6)
  - [ ] 1.1 实现 `gateway/mqtt_client.py` — `GatewayMqttClient` 类
  - [ ] 1.2 `connect(host, port, username, password)` 方法：建立 MQTT 连接
  - [ ] 1.3 `publish(topic, payload, qos=1)` 方法：发布消息，断开时降级到 OfflineCache
  - [ ] 1.4 `disconnect()` 方法：断开连接
  - [ ] 1.5 `is_connected` 属性：返回连接状态

- [ ] Task 2: 数据格式转换 (AC: #2)
  - [ ] 2.1 在 `gateway/mqtt_client.py` 中实现 `format_point_data(gateway_id, readings)` 函数
  - [ ] 2.2 将 NormalizedReading 列表转换为 MQTT 消息 JSON

- [ ] Task 3: 后端数据处理模型 (AC: #4)
  - [ ] 3.1 在 `backend/app/models/gateway.py` 新增 `PointDataLatest` 模型（point_id, value, quality, timestamp, gateway_id, updated_at）
  - [ ] 3.2 使用 UPSERT 语义：point_id 存在则更新，不存在则插入

- [ ] Task 4: 后端数据处理服务 (AC: #4)
  - [ ] 4.1 创建 `backend/app/services/point_data.py`
  - [ ] 4.2 实现 `async def handle_point_data(payload: dict, db)` — 解析点位数据，批量 upsert 到 PointDataLatest

- [ ] Task 5: MqttService 订阅数据 topic (AC: #3)
  - [ ] 5.1 修改 `backend/app/mqtt/client.py` — 在 _connect_loop 中增加订阅 `dcim/+/gw/+/data`
  - [ ] 5.2 在 _handle_message 中增加 data topic 的处理分支

- [ ] Task 6: 单元测试 (AC: 全部)
  - [ ] 6.1 测试 format_point_data — 正确转换 NormalizedReading 为 MQTT JSON
  - [ ] 6.2 测试 GatewayMqttClient.publish — 连接时直接发布（mock aiomqtt）
  - [ ] 6.3 测试 GatewayMqttClient.publish — 断开时降级到 OfflineCache
  - [ ] 6.4 测试 handle_point_data — 新点位插入 PointDataLatest
  - [ ] 6.5 测试 handle_point_data — 已有点位更新值
  - [ ] 6.6 测试 handle_point_data — 无效 payload 不崩溃
  - [ ] 6.7 测试 MqttService — data topic 消息路由到 handle_point_data
  - [ ] 6.8 测试 format_point_data — 空 readings 返回空 points

## Dev Notes (开发指南)

### 1. 文件位置

```
gateway/mqtt_client.py                     # 修改 — 实现 GatewayMqttClient
backend/app/models/gateway.py              # 修改 — 新增 PointDataLatest 模型
backend/app/services/point_data.py         # 新建 — 点位数据处理服务
backend/app/mqtt/client.py                 # 修改 — 订阅 data topic
backend/tests/test_point_data.py           # 新建 — 单元测试
```

### 2. MQTT 数据消息格式

```json
{
  "gw_id": "gw-001",
  "ts": 1708000000,
  "points": [
    {"id": "p001", "v": 25.6, "q": 0, "t": 1708000000},
    {"id": "p002", "v": 1, "q": 0, "t": 1708000000}
  ]
}
```

- `id`: point_id
- `v`: value（float/int/bool/str）
- `q`: quality（0=normal, 1=unreliable, 2=abnormal）
- `t`: timestamp（Unix epoch）

### 3. GatewayMqttClient

```python
# gateway/mqtt_client.py

import json
import logging
import time
from datetime import datetime
from typing import Any, Optional

from .adapters.base import NormalizedReading, DataQuality
from .cache import OfflineCache

logger = logging.getLogger(__name__)

QUALITY_MAP = {
    DataQuality.NORMAL: 0,
    DataQuality.UNRELIABLE: 1,
    DataQuality.ABNORMAL: 2,
}


def format_point_data(gateway_id: str, readings: list[NormalizedReading]) -> dict:
    """将 NormalizedReading 列表转换为 MQTT 数据消息"""
    return {
        "gw_id": gateway_id,
        "ts": int(time.time()),
        "points": [
            {
                "id": r.point_id,
                "v": r.value,
                "q": QUALITY_MAP.get(r.quality, 0),
                "t": int(r.timestamp.timestamp()),
            }
            for r in readings
        ],
    }


class GatewayMqttClient:
    """网关 MQTT 客户端 — 数据上报 + 离线缓存降级"""

    def __init__(
        self,
        gateway_id: str,
        site_id: int = 1,
        cache: Optional[OfflineCache] = None,
    ) -> None:
        self._gateway_id = gateway_id
        self._site_id = site_id
        self._cache = cache
        self._client = None  # aiomqtt.Client (set externally or via connect)
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def data_topic(self) -> str:
        return f"dcim/{self._site_id}/gw/{self._gateway_id}/data"

    async def publish(self, topic: str, payload: str, qos: int = 1) -> None:
        """发布消息，断开时降级到离线缓存"""
        if self._connected and self._client:
            try:
                await self._client.publish(topic, payload, qos=qos)
                return
            except Exception:
                logger.warning("MQTT 发布失败，降级到离线缓存")
                self._connected = False

        # 降级到离线缓存
        if self._cache:
            await self._cache.enqueue(topic, payload)
        else:
            logger.error("MQTT 断开且无离线缓存，数据丢失: topic=%s", topic)

    async def publish_readings(self, readings: list[NormalizedReading]) -> None:
        """上报采集数据"""
        if not readings:
            return
        msg = format_point_data(self._gateway_id, readings)
        await self.publish(self.data_topic, json.dumps(msg))

    def set_connected(self, client: Any) -> None:
        """设置连接状态（由外部连接管理器调用）"""
        self._client = client
        self._connected = True

    def set_disconnected(self) -> None:
        """设置断开状态"""
        self._client = None
        self._connected = False
```

### 4. PointDataLatest 模型

```python
class PointDataLatest(Base):
    """点位最新数据"""
    __tablename__ = "point_data_latest"

    id = Column(Integer, primary_key=True, autoincrement=True)
    point_id = Column(String(100), unique=True, nullable=False, index=True, comment="点位ID")
    value = Column(String(200), comment="最新值（字符串存储）")
    quality = Column(Integer, default=0, comment="质量码: 0=正常, 1=不可靠, 2=异常")
    timestamp = Column(DateTime, comment="采集时间")
    gateway_id = Column(String(50), comment="来源网关")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")
```

### 5. 点位数据处理服务

```python
# backend/app/services/point_data.py

import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from ..models.gateway import PointDataLatest

logger = logging.getLogger(__name__)


async def handle_point_data(payload: dict, db: AsyncSession) -> int:
    """处理网关上报的点位数据，返回处理条数"""
    gw_id = payload.get("gw_id")
    points = payload.get("points")
    if not gw_id or not points:
        logger.warning("数据消息格式无效: 缺少 gw_id 或 points")
        return 0

    count = 0
    for pt in points:
        point_id = pt.get("id")
        if not point_id:
            continue

        value = str(pt.get("v", ""))
        quality = int(pt.get("q", 0))
        ts_epoch = pt.get("t")
        timestamp = datetime.fromtimestamp(ts_epoch) if ts_epoch else datetime.now()

        # UPSERT: 存在则更新，不存在则插入
        result = await db.execute(
            select(PointDataLatest).where(PointDataLatest.point_id == point_id)
        )
        existing = result.scalar_one_or_none()

        if existing:
            await db.execute(
                update(PointDataLatest).where(PointDataLatest.point_id == point_id).values(
                    value=value,
                    quality=quality,
                    timestamp=timestamp,
                    gateway_id=gw_id,
                    updated_at=datetime.now(),
                )
            )
        else:
            record = PointDataLatest(
                point_id=point_id,
                value=value,
                quality=quality,
                timestamp=timestamp,
                gateway_id=gw_id,
            )
            db.add(record)

        count += 1

    await db.commit()
    logger.debug("点位数据处理: gw=%s, %d 条", gw_id, count)
    return count
```

### 6. MqttService 修改

在 `_connect_loop` 中增加订阅：
```python
await client.subscribe("dcim/+/gw/+/data", qos=1)
```

在 `_handle_message` 中增加 data 分支：
```python
if len(parts) == 5 and parts[4] == "data":
    from ..services.point_data import handle_point_data
    async with async_session() as db:
        await handle_point_data(payload, db)
```

注意：由于 Story 2.3 已将 gateway_registration 的 import 移到顶部，这里 point_data 也应该在顶部导入。

### 7. 关键约束

- **QoS 1**: 数据上报使用 QoS 1（至少一次），控制命令使用 QoS 2（精确一次）
- **value 字符串存储**: PointDataLatest.value 用 String 存储，支持 float/int/bool/str 各种类型
- **UPSERT**: 按 point_id 唯一键，存在则更新，不存在则插入
- **离线降级**: GatewayMqttClient.publish 失败时自动写入 OfflineCache
- **顶层导入**: MqttService 中 handle_point_data 在模块顶部导入
- **测试使用 mock**: mock aiomqtt，不需要真实 MQTT Broker

### Project Structure Notes

- `gateway/mqtt_client.py` — 修改（从 stub 实现）
- `backend/app/models/gateway.py` — 新增 PointDataLatest 模型
- `backend/app/services/point_data.py` — 新建
- `backend/app/mqtt/client.py` — 修改（订阅 data topic + 处理分支）
- 测试文件放在 `backend/tests/test_point_data.py`

### References

- [Source: architecture.md#4.6] MQTT Topic: dcim/{site_id}/gw/{gw_id}/data, QoS 1
- [Source: architecture.md] MQTT 数据上报消息格式
- [Source: epics.md#Story 2.5] Acceptance Criteria
- [Source: base.py] NormalizedReading, DataQuality

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

