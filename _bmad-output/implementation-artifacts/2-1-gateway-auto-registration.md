# Story 2.1: 网关自动注册

Status: done

## Story

As a 运维工程师,
I want 采集网关上线时自动注册到平台,
so that 我不需要手动录入网关信息。

## Acceptance Criteria (验收标准)

1. **AC-1: 网关状态上报** — 网关侧 `StatusReporter` 每 30 秒通过 MQTT 发布心跳消息到 `dcim/{site_id}/gw/{gw_id}/status`，包含 gateway_id、IP、版本、CPU/内存/磁盘使用率
2. **AC-2: 后端 MQTT 客户端** — 后端新增 `MqttService`，使用 aiomqtt 连接 EMQX Broker，订阅 `dcim/+/gw/+/status` 通配符 topic
3. **AC-3: 自动注册** — 收到未知 gateway_id 的心跳消息时，自动创建 Gateway 记录（gateway_id、name、ip_address、version、capabilities）
4. **AC-4: 心跳更新** — 收到已知 gateway_id 的心跳消息时，更新 status=online、name、ip_address、version、capabilities、cpu_usage、memory_usage、disk_usage、last_heartbeat
5. **AC-5: 离线检测** — 后端定时任务（每 30 秒）检查所有 online 网关的 last_heartbeat，超过 90 秒未心跳的标记为 offline
6. **AC-6: MQTT 配置** — Settings 新增 mqtt_host、mqtt_port、mqtt_username、mqtt_password 配置项
7. **AC-7: 优雅降级** — MQTT Broker 不可用时，后端正常启动，MQTT 功能降级，日志记录连接失败

## Tasks / Subtasks (任务分解)

- [ ] Task 1: Settings 新增 MQTT 配置 (AC: #6)
  - [ ] 1.1 在 `backend/app/core/config.py` 的 `Settings` 中新增 `mqtt_host`, `mqtt_port`, `mqtt_username`, `mqtt_password`, `mqtt_enabled` 配置项

- [ ] Task 2: 网关侧 StatusReporter (AC: #1)
  - [ ] 2.1 实现 `gateway/status_reporter.py` — `StatusReporter` 类
  - [ ] 2.2 `collect_metrics()` 方法：使用 `psutil` 获取 CPU/内存/磁盘使用率（psutil 不可用时返回 None）
  - [ ] 2.3 `build_status_message()` 方法：构建心跳 JSON 消息
  - [ ] 2.4 `start(mqtt_publish_fn)` 方法：启动 30 秒定时上报循环
  - [ ] 2.5 `stop()` 方法：停止上报

- [ ] Task 3: 后端网关注册服务 (AC: #3, #4)
  - [ ] 3.1 创建 `backend/app/services/gateway_registration.py`
  - [ ] 3.2 实现 `async def handle_gateway_status(payload: dict, db: AsyncSession)` — 解析心跳消息
  - [ ] 3.3 gateway_id 不存在时自动创建 Gateway 记录（status=online）
  - [ ] 3.4 gateway_id 已存在时更新心跳字段（status、name、ip、version、capabilities、cpu、mem、disk、last_heartbeat）

- [ ] Task 4: 后端 MQTT 服务 (AC: #2, #7)
  - [ ] 4.1 创建 `backend/app/mqtt/__init__.py` 和 `backend/app/mqtt/client.py`
  - [ ] 4.2 实现 `MqttService` 类 — 封装 aiomqtt 连接、订阅、消息分发
  - [ ] 4.3 订阅 `dcim/+/gw/+/status`，收到消息后调用 `handle_gateway_status`
  - [ ] 4.4 连接失败时记录日志，不阻塞后端启动（优雅降级）
  - [ ] 4.5 断线自动重连（指数退避）

- [ ] Task 5: 离线检测定时任务 (AC: #5)
  - [ ] 5.1 在 `backend/app/services/gateway_registration.py` 中实现 `async def check_gateway_heartbeats(db: AsyncSession)`
  - [ ] 5.2 查询 status=online 且 (last_heartbeat < now - 90s 或 last_heartbeat IS NULL) 的网关，标记为 offline
  - [ ] 5.3 在 MqttService 中启动定时任务（每 30 秒执行一次）

- [ ] Task 6: 单元测试 (AC: 全部)
  - [ ] 6.1 测试 StatusReporter — collect_metrics 返回正确结构
  - [ ] 6.2 测试 StatusReporter — build_status_message 包含必要字段
  - [ ] 6.3 测试 handle_gateway_status — 新网关自动注册
  - [ ] 6.4 测试 handle_gateway_status — 已有网关更新心跳
  - [ ] 6.5 测试 handle_gateway_status — 无效消息格式不崩溃
  - [ ] 6.6 测试 check_gateway_heartbeats — 超时网关标记 offline
  - [ ] 6.7 测试 check_gateway_heartbeats — 未超时网关保持 online
  - [ ] 6.8 测试 MqttService — topic 解析提取 site_id 和 gw_id
  - [ ] 6.9 测试 MqttService — 连接失败优雅降级
  - [ ] 6.10 测试 Settings — MQTT 配置默认值
  - [ ] 6.11 测试 handle_gateway_status — capabilities 为 list 时正确存储
  - [ ] 6.12 测试 check_gateway_heartbeats — last_heartbeat=NULL 的 online 网关也标记 offline
  - [ ] 6.13 测试 StatusReporter — stop() 在未 start 时调用不报错

## Dev Notes (开发指南)

### 1. 文件位置

```
backend/app/core/config.py              # 修改 — 新增 MQTT 配置
backend/app/mqtt/__init__.py            # 新建 — 包初始化
backend/app/mqtt/client.py              # 新建 — MqttService
backend/app/services/gateway_registration.py  # 新建 — 注册+心跳+离线检测
gateway/status_reporter.py              # 修改 — 实现 StatusReporter
backend/tests/test_gateway_registration.py    # 新建 — 单元测试
```

### 2. MQTT 配置

```python
# backend/app/core/config.py — Settings 新增
mqtt_enabled: bool = True
mqtt_host: str = "localhost"
mqtt_port: int = 1883
mqtt_username: str = ""
mqtt_password: str = ""
mqtt_client_id: str = "dcim-backend"
```

### 3. 心跳消息格式

```json
{
  "gw_id": "gw-001",
  "name": "机房A网关",
  "ip": "192.168.1.100",
  "version": "1.0.0",
  "capabilities": ["modbus_tcp", "modbus_rtu", "snmp_v2c"],
  "cpu": 45.2,
  "mem": 62.1,
  "disk": 38.5,
  "ts": 1708000000
}
```

### 4. StatusReporter 核心逻辑

```python
# gateway/status_reporter.py

import asyncio
import json
import logging
import os
import time
from typing import Any, Callable, Coroutine, Optional

logger = logging.getLogger(__name__)

# psutil 可选依赖
try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False
    logger.warning("psutil 未安装，系统指标将返回 None")


class StatusReporter:
    """网关状态上报器 — 每 30 秒发布心跳到 MQTT"""

    def __init__(
        self,
        gateway_id: str,
        site_id: int = 1,
        name: str = "",
        version: str = "1.0.0",
        capabilities: Optional[list[str]] = None,
        interval: int = 30,
    ) -> None:
        self._gateway_id = gateway_id
        self._site_id = site_id
        self._name = name or f"gateway-{gateway_id}"
        self._version = version
        self._capabilities = capabilities or []
        self._interval = interval
        self._task: Optional[asyncio.Task] = None
        self._running = False

    @property
    def topic(self) -> str:
        return f"dcim/{self._site_id}/gw/{self._gateway_id}/status"

    def collect_metrics(self) -> dict[str, Optional[float]]:
        """采集系统指标"""
        if not _HAS_PSUTIL:
            return {"cpu": None, "mem": None, "disk": None}
        disk_path = "/" if os.name != "nt" else "C:\\"
        return {
            "cpu": psutil.cpu_percent(interval=0),
            "mem": psutil.virtual_memory().percent,
            "disk": psutil.disk_usage(disk_path).percent,
        }

    def build_status_message(self) -> dict[str, Any]:
        """构建心跳消息"""
        metrics = self.collect_metrics()
        return {
            "gw_id": self._gateway_id,
            "name": self._name,
            "ip": self._get_ip(),
            "version": self._version,
            "capabilities": self._capabilities,
            "cpu": metrics["cpu"],
            "mem": metrics["mem"],
            "disk": metrics["disk"],
            "ts": int(time.time()),
        }

    def _get_ip(self) -> str:
        """获取本机 IP（尽力而为）"""
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    async def start(self, publish_fn: Callable[[str, str], Coroutine]) -> None:
        """启动定时上报"""
        self._running = True
        self._task = asyncio.create_task(self._report_loop(publish_fn))
        logger.info("状态上报已启动: topic=%s, interval=%ds", self.topic, self._interval)

    async def stop(self) -> None:
        """停止上报"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("状态上报已停止")

    async def _report_loop(self, publish_fn: Callable[[str, str], Coroutine]) -> None:
        """上报循环"""
        while self._running:
            try:
                msg = self.build_status_message()
                await publish_fn(self.topic, json.dumps(msg))
                logger.debug("心跳已发送: %s", self._gateway_id)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("心跳发送失败")
            await asyncio.sleep(self._interval)
```

### 5. 网关注册服务

```python
# backend/app/services/gateway_registration.py

import logging
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, or_

from ..models.gateway import Gateway

logger = logging.getLogger(__name__)

HEARTBEAT_TIMEOUT_SECONDS = 90


async def handle_gateway_status(payload: dict, db: AsyncSession) -> None:
    """处理网关心跳消息 — 自动注册或更新"""
    gw_id = payload.get("gw_id")
    if not gw_id:
        logger.warning("心跳消息缺少 gw_id: %s", payload)
        return

    result = await db.execute(select(Gateway).where(Gateway.gateway_id == gw_id))
    existing = result.scalar_one_or_none()

    now = datetime.now()

    if existing is None:
        # 自动注册
        gateway = Gateway(
            gateway_id=gw_id,
            name=payload.get("name", f"gateway-{gw_id}"),
            ip_address=payload.get("ip"),
            version=payload.get("version"),
            capabilities=payload.get("capabilities"),
            status="online",
            cpu_usage=payload.get("cpu"),
            memory_usage=payload.get("mem"),
            disk_usage=payload.get("disk"),
            last_heartbeat=now,
        )
        db.add(gateway)
        await db.commit()
        logger.info("网关自动注册: %s (%s)", gw_id, payload.get("ip"))
    else:
        # 更新心跳
        await db.execute(
            update(Gateway).where(Gateway.gateway_id == gw_id).values(
                status="online",
                name=payload.get("name", existing.name),
                ip_address=payload.get("ip", existing.ip_address),
                version=payload.get("version", existing.version),
                capabilities=payload.get("capabilities", existing.capabilities),
                cpu_usage=payload.get("cpu"),
                memory_usage=payload.get("mem"),
                disk_usage=payload.get("disk"),
                last_heartbeat=now,
                updated_at=now,
            )
        )
        await db.commit()
        logger.debug("网关心跳更新: %s", gw_id)


async def check_gateway_heartbeats(db: AsyncSession) -> int:
    """检查网关心跳超时，返回标记为 offline 的数量"""
    cutoff = datetime.now() - timedelta(seconds=HEARTBEAT_TIMEOUT_SECONDS)
    result = await db.execute(
        select(Gateway).where(
            Gateway.status == "online",
            or_(
                Gateway.last_heartbeat < cutoff,
                Gateway.last_heartbeat.is_(None),
            ),
        )
    )
    stale_gateways = result.scalars().all()

    if not stale_gateways:
        return 0

    stale_ids = [gw.gateway_id for gw in stale_gateways]
    await db.execute(
        update(Gateway).where(
            Gateway.gateway_id.in_(stale_ids)
        ).values(status="offline", updated_at=datetime.now())
    )
    await db.commit()

    for gw_id in stale_ids:
        logger.warning("网关心跳超时，标记为离线: %s", gw_id)

    return len(stale_ids)
```

### 6. MqttService（后端 MQTT 客户端）

```python
# backend/app/mqtt/client.py

import asyncio
import json
import logging
from typing import Optional

from ..core.config import get_settings
from ..core.database import async_session
from ..services.gateway_registration import handle_gateway_status, check_gateway_heartbeats

logger = logging.getLogger(__name__)


class MqttService:
    """后端 MQTT 客户端 — 订阅网关状态、数据上报"""

    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        """启动 MQTT 客户端（优雅降级：连接失败不阻塞）"""
        settings = get_settings()
        if not settings.mqtt_enabled:
            logger.info("MQTT 已禁用")
            return

        self._running = True
        self._task = asyncio.create_task(self._connect_loop())
        self._heartbeat_task = asyncio.create_task(self._heartbeat_check_loop())
        logger.info("MQTT 服务已启动")

    async def stop(self) -> None:
        """停止 MQTT 客户端"""
        self._running = False
        for task in [self._task, self._heartbeat_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        logger.info("MQTT 服务已停止")

    async def _connect_loop(self) -> None:
        """MQTT 连接循环（断线重连 + 指数退避）"""
        settings = get_settings()
        retry_delay = 1.0

        while self._running:
            try:
                import aiomqtt
                async with aiomqtt.Client(
                    hostname=settings.mqtt_host,
                    port=settings.mqtt_port,
                    username=settings.mqtt_username or None,
                    password=settings.mqtt_password or None,
                    identifier=settings.mqtt_client_id,
                ) as client:
                    logger.info("MQTT 已连接: %s:%d", settings.mqtt_host, settings.mqtt_port)
                    retry_delay = 1.0  # 重置退避

                    # 订阅网关状态 topic
                    await client.subscribe("dcim/+/gw/+/status")
                    logger.info("已订阅: dcim/+/gw/+/status")

                    async for message in client.messages:
                        await self._handle_message(message)

            except asyncio.CancelledError:
                raise
            except ImportError:
                logger.error("aiomqtt 未安装，MQTT 功能不可用")
                return
            except Exception as e:
                logger.warning("MQTT 连接失败: %s (%.1fs 后重试)", e, retry_delay)
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60.0)

    async def _handle_message(self, message) -> None:
        """处理收到的 MQTT 消息"""
        try:
            topic = str(message.topic)
            payload = json.loads(message.payload.decode())

            # 解析 topic: dcim/{site_id}/gw/{gw_id}/status
            parts = topic.split("/")
            if len(parts) == 5 and parts[4] == "status":
                async with async_session() as db:
                    await handle_gateway_status(payload, db)
        except json.JSONDecodeError:
            logger.warning("MQTT 消息 JSON 解析失败: topic=%s", message.topic)
        except Exception:
            logger.exception("MQTT 消息处理异常: topic=%s", message.topic)

    async def _heartbeat_check_loop(self) -> None:
        """定时检查网关心跳超时"""
        while self._running:
            try:
                await asyncio.sleep(30)
                async with async_session() as db:
                    count = await check_gateway_heartbeats(db)
                    if count:
                        logger.info("心跳检查: %d 个网关标记为离线", count)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("心跳检查异常")

    @staticmethod
    def parse_topic(topic: str) -> Optional[dict]:
        """解析 MQTT topic，提取 site_id 和 gw_id"""
        parts = topic.split("/")
        if len(parts) >= 5 and parts[0] == "dcim":
            return {
                "site_id": parts[1],
                "gw_id": parts[3],
                "type": parts[4],
            }
        return None
```

### 7. 关键约束

- **aiomqtt 条件导入**: `import aiomqtt` 在 `_connect_loop` 内部导入，未安装时记录错误并退出，不影响后端启动
- **优雅降级**: MQTT Broker 不可用时，后端正常运行，MQTT 功能不可用
- **断线重连**: 指数退避（1s → 2s → 4s → ... → 60s max）
- **心跳超时**: 90 秒（3 个心跳周期），避免网络抖动误判；last_heartbeat=NULL 也视为超时
- **psutil 可选**: 网关侧 psutil 未安装时指标返回 None
- **跨平台**: disk_usage 路径根据 os.name 区分 Windows/Linux
- **capabilities 类型**: 心跳消息中 capabilities 为 list[str]，Gateway 模型 JSON 列支持 list 存储，GatewayBase schema 定义为 Optional[dict] 但注册服务不经过 schema 验证
- **lazy logging**: 使用 `%s` 格式
- **顶层导入**: MqttService 中 gateway_registration 函数在模块顶部导入（非 lazy import）
- **测试使用 mock**: mock aiomqtt、psutil，不需要真实 MQTT Broker

### 8. 测试策略

- StatusReporter 测试：mock psutil，验证 collect_metrics 和 build_status_message
- handle_gateway_status 测试：使用内存 SQLite，验证自动注册和心跳更新
- check_gateway_heartbeats 测试：使用内存 SQLite，验证超时检测
- MqttService.parse_topic 测试：纯函数，直接测试
- MqttService 连接失败测试：mock aiomqtt，验证优雅降级

### Project Structure Notes

- `backend/app/mqtt/` — 新建目录，后端 MQTT 层
- `backend/app/services/gateway_registration.py` — 新建，网关注册服务
- `gateway/status_reporter.py` — 修改（从 stub 实现）
- 测试文件放在 `backend/tests/test_gateway_registration.py`

### References

- [Source: architecture.md#2.5] 网关内部架构 — status_reporter.py
- [Source: architecture.md#2.6] MQTT 客户端集成 — MVP 内嵌 aiomqtt
- [Source: architecture.md#4.6] MQTT Topic 设计 — dcim/{site_id}/gw/{gw_id}/status
- [Source: epics.md#Story 2.1] Acceptance Criteria
- [Source: gateway.py model] Gateway 模型 — 已有字段

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
