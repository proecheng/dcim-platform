# Story 34.2: 通知渠道适配器框架 + 消息模板

Status: ready-for-dev

## Story

As a 系统,
I want 一个可插拔的通知渠道适配器框架和消息模板引擎,
So that 可以灵活添加通知渠道，且每种渠道发送格式正确的通知内容。

## Acceptance Criteria

1. **Given** 系统启动 **When** 加载通知模块 **Then** 注册所有已启用的渠道适配器（email + im），禁用的适配器被跳过且不报错
2. **Given** 调用适配器发送通知成功 **Then** 创建 NotificationRecord（status=sent, sent_at 有值）
3. **Given** 调用适配器发送失败 **Then** 创建 NotificationRecord（status=failed, error_message 有值），放入异步重试队列
4. **Given** 重试队列中的通知 **When** 重试成功 **Then** 更新 NotificationRecord.status=sent；**When** 重试次数达到 max_retries **Then** 更新 status=failed 不再重试
5. **Given** 发送短信/邮件/IM/语音通知 **When** 渲染消息内容 **Then** 使用对应渠道的消息模板，包含站点名、告警级别、设备名、点位名、当前值、时间
6. **Given** 应用关闭（shutdown） **When** 重试队列中仍有待处理消息 **Then** 批量更新为 failed（error_message="进程关闭"），不丢失记录

> **本 Story 范围：** 适配器基类 + EmailNotificationAdapter + ImAdapter（钉钉 Webhook）+ NotificationRecord 模型 + 重试队列 + 消息模板。SmsAdapter 和 VoiceCallAdapter 在 V4.3.1 交付，本 Story 仅定义桩实现。

## Tasks / Subtasks

- [ ] Task 1: NotificationRecord 数据模型 (AC: #2, #3)
  - [ ] 1.1 创建 `backend/app/models/notification_record.py` — ORM 模型
  - [ ] 1.2 更新 `backend/app/models/__init__.py` — 注册模型
  - [ ] 1.3 创建 Alembic 迁移脚本
- [ ] Task 2: 消息模板 + AlarmNotificationContext DTO (AC: #5)
  - [ ] 2.1 创建 `backend/app/schemas/notification.py` — DTO + 模板渲染函数
- [ ] Task 3: 适配器框架 + 实现 (AC: #1, #2, #3)
  - [ ] 3.1 创建 `backend/app/services/notification/adapters.py` — 基类 + EmailAdapter + ImAdapter + Sms/Voice 桩
  - [ ] 3.2 创建 `backend/app/services/notification/__init__.py` — 包初始化
- [ ] Task 4: 重试队列 + 分发器骨架 (AC: #3, #4, #6)
  - [ ] 4.1 创建 `backend/app/services/notification/dispatcher.py` — 重试队列 + worker + shutdown 处理
- [ ] Task 5: API 端点 — 渠道配置 + 测试发送 (AC: #1)
  - [ ] 5.1 创建 `backend/app/api/v1/notification.py` — 渠道配置查询 + 测试发送端点
  - [ ] 5.2 更新 `backend/app/api/v1/__init__.py` — 注册路由
- [ ] Task 6: 自动化测试 (AC: #1~#6)
  - [ ] 6.1 创建 `backend/tests/api/test_notification.py`

## Dev Notes

### 数据模型

**NotificationRecord 表** — 新建文件 `backend/app/models/notification_record.py`

```python
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index, Text
from app.core.database import Base

class NotificationRecord(Base):
    __tablename__ = "notification_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alarm_id = Column(Integer, ForeignKey("alarms.id", ondelete="SET NULL"), nullable=True, comment="关联告警")
    policy_id = Column(Integer, nullable=True, comment="触发策略ID")
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, comment="通知对象")
    channel_type = Column(String(20), nullable=False, comment="渠道类型: sms|im|voice|email")
    platform = Column(String(20), nullable=True, comment="平台: dingtalk|wecom|null")
    contact_value = Column(String(200), nullable=False, comment="实际发送的联系方式")
    content_summary = Column(String(500), nullable=True, comment="发送内容摘要")
    status = Column(String(20), nullable=False, default="pending", comment="状态: pending|sent|failed|retrying")
    retry_count = Column(Integer, nullable=False, default=0, comment="已重试次数")
    max_retries = Column(Integer, nullable=False, default=3, comment="最大重试次数")
    sent_at = Column(DateTime, nullable=True, comment="发送成功时间")
    error_message = Column(Text, nullable=True, comment="错误信息")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")

    __table_args__ = (
        Index("ix_nr_alarm_id", "alarm_id"),
        Index("ix_nr_status", "status"),
        Index("ix_nr_created_at", "created_at"),
    )
```

索引：
- `ix_nr_alarm_id` on `alarm_id`（按告警查通知记录）
- `ix_nr_status` on `status`（重试 worker 查询 retrying 状态）
- `ix_nr_created_at` on `created_at`（通知记录列表按时间排序）

> **policy_id 无 FK 约束说明：** NotificationPolicy 表在 Story 34.3 才创建，本 Story 中 policy_id 为普通 Integer 字段（nullable=True），不添加 ForeignKey。Story 34.3 迁移中可选择添加 FK 约束。

[Source: architecture.md#Section 22.2]

### AlarmNotificationContext DTO

```python
# backend/app/schemas/notification.py
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class AlarmNotificationContext:
    """通知上下文 DTO — 避免跨层传递 ORM 对象"""
    alarm_id: int
    alarm_level: str          # critical | major | minor | info
    alarm_message: str
    device_name: Optional[str]
    point_name: Optional[str]
    current_value: Optional[float]
    threshold_value: Optional[float]
    site_id: Optional[int]
    site_name: Optional[str]
    created_at: datetime
```

### 消息模板

```python
# 短信模板（≤70中文字符）
SMS_TEMPLATE = "[DCIM] {site_name} {alarm_level_cn}告警: {device_name}/{point_name} 当前值{current_value}"

# 邮件模板（HTML）
EMAIL_SUBJECT_TEMPLATE = "[DCIM告警] {site_name} - {alarm_level_cn}: {device_name}"
EMAIL_BODY_TEMPLATE = """
<html><body>
<h3 style="color:#e74c3c">⚠️ {alarm_level_cn}告警</h3>
<table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse">
<tr><td><b>站点</b></td><td>{site_name}</td></tr>
<tr><td><b>设备</b></td><td>{device_name}</td></tr>
<tr><td><b>点位</b></td><td>{point_name}</td></tr>
<tr><td><b>当前值</b></td><td>{current_value}</td></tr>
<tr><td><b>阈值</b></td><td>{threshold_value}</td></tr>
<tr><td><b>时间</b></td><td>{created_at}</td></tr>
<tr><td><b>详情</b></td><td>{alarm_message}</td></tr>
</table>
</body></html>
"""

# IM 模板（Markdown 卡片）
IM_MARKDOWN_TEMPLATE = """### ⚠️ {alarm_level_cn}告警
- **站点：** {site_name}
- **设备：** {device_name}
- **点位：** {point_name}
- **当前值：** {current_value}
- **阈值：** {threshold_value}
- **时间：** {created_at}
- **详情：** {alarm_message}"""

# 语音 TTS 模板
VOICE_TTS_TEMPLATE = "{site_name}发生{alarm_level_cn}告警，设备{device_name}，点位{point_name}，当前值{current_value}，请及时处理。"

ALARM_LEVEL_CN = {"critical": "紧急", "major": "重要", "minor": "次要", "info": "信息"}
```

渲染函数 `render_notification(template, context)` 统一处理 None 值替换为"未知"。

### 适配器架构

```python
# backend/app/services/notification/adapters.py
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class NotificationResult:
    success: bool
    error_message: Optional[str] = None

class NotificationAdapter(ABC):
    """通知渠道适配器基类"""

    @abstractmethod
    async def send(self, contact_value: str, subject: str, content: str,
                   context: AlarmNotificationContext) -> NotificationResult: ...

    @abstractmethod
    async def health_check(self) -> bool: ...

    @abstractmethod
    def is_enabled(self) -> bool: ...

class EmailNotificationAdapter(NotificationAdapter):
    """邮件适配器 — 包装现有 EmailService 单例"""

    def __init__(self, email_svc):
        self._email_svc = email_svc

    def is_enabled(self) -> bool:
        return self._email_svc.is_available

    async def send(self, contact_value, subject, content, context):
        # EmailService.send_html_email 接收 List[str]，需包装单个地址为列表
        try:
            success = await asyncio.wait_for(
                self._email_svc.send_html_email([contact_value], subject, content),
                timeout=45
            )
            if success:
                return NotificationResult(success=True)
            return NotificationResult(success=False, error_message="邮件发送返回 False")
        except asyncio.TimeoutError:
            return NotificationResult(success=False, error_message="邮件发送超时(45s)")
        except Exception as e:
            return NotificationResult(success=False, error_message=str(e))

    async def health_check(self) -> bool:
        return self._email_svc.is_available

class ImAdapter(NotificationAdapter):
    """钉钉 Webhook 适配器 — httpx.AsyncClient 原生异步"""

    def __init__(self):
        self._webhook_url: Optional[str] = None
        self._secret: Optional[str] = None

    async def load_config(self):
        """从 SystemConfig 加载钉钉配置 — 在 init_adapters() 中调用"""
        from app.core.database import async_session
        from app.models.config import SystemConfig
        async with async_session() as session:
            for key in ("notification.im.dingtalk.webhook_url", "notification.im.dingtalk.secret"):
                result = await session.execute(
                    select(SystemConfig).where(SystemConfig.key == key)
                )
                cfg = result.scalar_one_or_none()
                if cfg and cfg.value:
                    if "webhook_url" in key:
                        self._webhook_url = cfg.value
                    else:
                        self._secret = cfg.value

    def is_enabled(self) -> bool:
        return bool(self._webhook_url)

    async def send(self, contact_value, subject, content, context):
        import httpx, hmac, hashlib, base64, time, urllib.parse
        url = self._webhook_url
        # 仅在配置了 secret 时加签（钉钉支持无签名的 IP 白名单模式）
        if self._secret:
            timestamp = str(round(time.time() * 1000))
            string_to_sign = f"{timestamp}\n{self._secret}"
            hmac_code = hmac.new(
                self._secret.encode("utf-8"),
                string_to_sign.encode("utf-8"),
                digestmod=hashlib.sha256
            ).digest()
            sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}timestamp={timestamp}&sign={sign}"

        payload = {
            "msgtype": "markdown",
            "markdown": {"title": subject, "text": content},
            "at": {"atMobiles": [contact_value] if contact_value else []}
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload)
            data = resp.json()
            if data.get("errcode") == 0:
                return NotificationResult(success=True)
            return NotificationResult(success=False, error_message=f"钉钉API错误: {data}")

    async def health_check(self) -> bool:
        return self.is_enabled()

class SmsAdapter(NotificationAdapter):
    """短信适配器 — V4.3.1 交付，当前为桩实现"""
    async def send(self, contact_value, subject, content, context):
        return NotificationResult(success=False, error_message="SMS adapter not implemented")
    async def health_check(self): return False
    def is_enabled(self): return False

class VoiceCallAdapter(NotificationAdapter):
    """语音电话适配器 — V4.3.1 交付，当前为桩实现"""
    async def send(self, contact_value, subject, content, context):
        return NotificationResult(success=False, error_message="Voice adapter not implemented")
    async def health_check(self): return False
    def is_enabled(self): return False
```

**适配器注册表：**
```python
ADAPTER_REGISTRY: dict[str, NotificationAdapter] = {}

async def init_adapters():
    """在 main.py lifespan 启动时调用（异步，因为 ImAdapter 需要从 DB 加载配置）"""
    from app.services.email_service import email_service
    ADAPTER_REGISTRY["email"] = EmailNotificationAdapter(email_service)
    im_adapter = ImAdapter()
    await im_adapter.load_config()
    ADAPTER_REGISTRY["im"] = im_adapter
    ADAPTER_REGISTRY["sms"] = SmsAdapter()
    ADAPTER_REGISTRY["voice"] = VoiceCallAdapter()
```

### 重试队列

```python
# backend/app/services/notification/dispatcher.py
class NotificationDispatcher:
    def __init__(self):
        self._retry_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._shutdown_event = asyncio.Event()
        self._worker_task: Optional[asyncio.Task] = None

    async def start(self):
        """启动重试 worker — 在 lifespan startup 调用"""
        self._worker_task = asyncio.create_task(self._retry_worker())

    async def shutdown(self):
        """优雅关闭 — 在 lifespan shutdown 调用"""
        self._shutdown_event.set()
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await asyncio.wait_for(self._worker_task, timeout=30)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
        # drain 队列中剩余消息 → 批量更新为 failed
        await self._drain_queue()

    async def _retry_worker(self):
        """后台重试协程 — 指数退避 30s/60s/120s"""
        while not self._shutdown_event.is_set():
            try:
                record_id = await asyncio.wait_for(
                    self._retry_queue.get(), timeout=5.0
                )
            except asyncio.TimeoutError:
                continue
            # 从 DB 加载 record 获取 retry_count
            async with async_session() as session:
                record = await session.get(NotificationRecord, record_id)
                if not record or record.retry_count >= record.max_retries:
                    continue
                delay = min(30 * (2 ** record.retry_count), 300)
            await asyncio.sleep(delay)
            await self._retry_send(record_id)

    async def _drain_queue(self):
        """优雅关闭时清空队列 — 批量更新为 failed"""
        record_ids = []
        while not self._retry_queue.empty():
            try:
                record_ids.append(self._retry_queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        if record_ids:
            async with async_session() as session:
                await session.execute(
                    update(NotificationRecord)
                    .where(NotificationRecord.id.in_(record_ids))
                    .values(status="failed", error_message="进程关闭，重试中断")
                )
                await session.commit()

    async def send_notification(self, context, channel_type, contact_value, user_id, policy_id=None):
        """发送单条通知 — 创建 NotificationRecord + 调用适配器
        注意：使用独立 async_session()（非依赖注入），因为 dispatcher 不在 request 上下文中
        """
        from app.schemas.notification import render_notification, get_template_for_channel, get_subject_for_channel

        # 渲染消息内容
        subject = render_notification(get_subject_for_channel(channel_type), context)
        content = render_notification(get_template_for_channel(channel_type), context)

        async with async_session() as session:
            # 1. 创建 NotificationRecord(status=pending)
            record = NotificationRecord(
                alarm_id=context.alarm_id, user_id=user_id, policy_id=policy_id,
                channel_type=channel_type, contact_value=contact_value,
                content_summary=subject[:500], status="pending",
                max_retries=3,
            )
            session.add(record)
            await session.commit()
            await session.refresh(record)
            record_id = record.id

        # 2. 调用 adapter.send()
        adapter = ADAPTER_REGISTRY.get(channel_type)
        if not adapter or not adapter.is_enabled():
            async with async_session() as session:
                record = await session.get(NotificationRecord, record_id)
                record.status = "failed"
                record.error_message = f"渠道 {channel_type} 未启用"
                await session.commit()
            return

        result = await adapter.send(contact_value, subject, content, context)

        async with async_session() as session:
            record = await session.get(NotificationRecord, record_id)
            if result.success:
                # 3. 成功 → status=sent, sent_at=now
                record.status = "sent"
                record.sent_at = datetime.now()
            else:
                # 4. 失败 → status=failed, 加入重试队列
                record.status = "failed"
                record.error_message = result.error_message
                await session.commit()
                if record.retry_count < record.max_retries:
                    self._retry_queue.put_nowait(record_id)
                return
            await session.commit()

    async def _retry_send(self, record_id: int):
        """重试发送单条通知"""
        async with async_session() as session:
            record = await session.get(NotificationRecord, record_id)
            if not record or record.status == "sent":
                return
            record.retry_count += 1
            record.status = "retrying"
            await session.commit()

        adapter = ADAPTER_REGISTRY.get(record.channel_type)
        if not adapter or not adapter.is_enabled():
            async with async_session() as session:
                record = await session.get(NotificationRecord, record_id)
                record.status = "failed"
                record.error_message = f"渠道 {record.channel_type} 未启用"
                await session.commit()
            return

        # 重建 context 用于模板渲染（从 record 中恢复最小信息）
        from app.schemas.notification import render_notification, get_template_for_channel, get_subject_for_channel
        # 重试时使用 content_summary 作为 subject，重新渲染 content 需要原始 context
        # 简化方案：重试时直接使用 record.content_summary 作为 subject，content 使用通用重试消息
        result = await adapter.send(
            record.contact_value,
            record.content_summary or "DCIM告警通知",
            record.content_summary or "DCIM告警通知（重试）",
            None  # context 不可用于重试，适配器需处理 context=None
        )

        async with async_session() as session:
            record = await session.get(NotificationRecord, record_id)
            if result.success:
                record.status = "sent"
                record.sent_at = datetime.now()
            else:
                record.status = "failed"
                record.error_message = result.error_message
                if record.retry_count < record.max_retries:
                    try:
                        self._retry_queue.put_nowait(record_id)
                    except asyncio.QueueFull:
                        logger.error("重试队列已满，丢弃: record_id=%d", record_id)
            await session.commit()
```

### main.py lifespan 集成点

```python
# main.py lifespan() 启动阶段（在现有 scheduler.start() 之后）
from app.services.notification import init_adapters, notification_dispatcher

# 初始化适配器注册表（异步，ImAdapter 需从 DB 加载配置）
await init_adapters()

# 启动重试 worker
await notification_dispatcher.start()

# --- lifespan yield ---

# main.py lifespan() 关闭阶段（在现有 scheduler.shutdown() 之前）
await notification_dispatcher.shutdown()
```

### 渠道配置 API

```
GET  /api/v1/notification/channels          — 查询所有渠道状态（enabled/disabled + health_check）
POST /api/v1/notification/channels/test      — 测试发送（指定渠道 + 联系方式）
```

权限：`require_admin`

**测试发送请求/响应 Schema：**

```python
class ChannelTestRequest(BaseModel):
    channel_type: str = Field(..., pattern="^(sms|im|voice|email)$")
    contact_value: str = Field(..., min_length=1, max_length=200)

class ChannelTestResponse(BaseModel):
    success: bool
    error_message: Optional[str] = None

class ChannelStatusInfo(BaseModel):
    channel_type: str
    enabled: bool
    healthy: bool
```

### 渠道配置项（SystemConfig key）

| Key | 说明 | 默认值 |
|-----|------|--------|
| `notification.im.dingtalk.webhook_url` | 钉钉机器人 Webhook URL | 空（禁用） |
| `notification.im.dingtalk.secret` | 钉钉签名密钥 | 空 |
| `notification.email.enabled` | 是否启用邮件通知 | true（依赖 EmailService 配置） |
| `notification.retry.max_retries` | 最大重试次数 | 3 |
| `notification.retry.base_delay` | 重试基础延迟（秒） | 30 |

### 迁移脚本

- Revision: `20260319_0100`
- Down revision: `20260318_0100`（Story 34.1）
- 创建 `notification_records` 表 + 3 个索引

### 文件清单

| 操作 | 文件 |
|------|------|
| 新建 | `backend/app/models/notification_record.py` |
| 新建 | `backend/app/schemas/notification.py` |
| 新建 | `backend/app/services/notification/__init__.py` |
| 新建 | `backend/app/services/notification/adapters.py` |
| 新建 | `backend/app/services/notification/dispatcher.py` |
| 新建 | `backend/app/api/v1/notification.py` |
| 新建 | `backend/alembic/versions/20260319_0100_story_34_2_notification_records.py` |
| 新建 | `backend/tests/api/test_notification.py` |
| 修改 | `backend/app/models/__init__.py` — 注册 NotificationRecord |
| 修改 | `backend/app/api/v1/__init__.py` — 注册 notification 路由 |
| 修改 | `backend/app/main.py` — lifespan 中调用 init_adapters() + dispatcher.start()/shutdown() |

### 测试场景

> **测试 mock 策略：** 所有适配器测试使用 `unittest.mock.AsyncMock` / `monkeypatch` mock 外部依赖（EmailService.send_html_email、httpx.AsyncClient.post），不真正发送邮件或调用钉钉 API。dispatcher 测试使用 mock adapter 注入 ADAPTER_REGISTRY。

1. EmailAdapter 发送成功 → NotificationRecord.status=sent（mock EmailService 返回 True）
2. EmailAdapter 发送失败 → NotificationRecord.status=failed + error_message（mock 返回 False）
3. ImAdapter（钉钉）发送成功 → status=sent（mock httpx 返回 errcode=0）
4. ImAdapter 发送失败（webhook 无效）→ status=failed（mock httpx 返回 errcode!=0）
5. SmsAdapter 桩返回 not implemented
6. VoiceCallAdapter 桩返回 not implemented
7. 渠道配置查询 → 返回所有渠道 enabled/disabled 状态
8. 测试发送 → 指定渠道 + 联系方式，返回发送结果（mock adapter）
9. 消息模板渲染 — SMS 模板 ≤70 字符
10. 消息模板渲染 — IM Markdown 模板包含所有字段
11. 消息模板渲染 — context 字段为 None 时替换为"未知"
12. 重试队列 — 失败通知进入队列
13. 非 admin 用户访问渠道配置 → 403
14. 适配器注册表 — 禁用的适配器不参与发送
