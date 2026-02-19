# Story 15-5: OTA 网关升级 — 设计方案

## 需求回顾

运维工程师可远程升级网关固件：
- 后端通过 MQTT QoS 2 发送升级指令到 `dcim/{site_id}/gw/{gw_id}/ota`
- 网关下载升级包到 B 分区，验证后切换启动
- 升级失败自动回滚到 A 分区
- 支持分批升级和灰度发布策略

## 现有基础设施

| 组件 | 位置 | 说明 |
|------|------|------|
| Gateway 模型 | `backend/app/models/gateway.py` | 已有 `version` 字段 |
| MQTT 客户端 | `backend/app/mqtt/client.py` | `publish(topic, payload, qos=2)` |
| 配置下发 | `backend/app/services/config_push.py` | 参考模式：构建 → MQTT 发送 → 记录状态 |
| 网关 API | `backend/app/api/v1/gateways.py` | CRUD + 配置下发 + 事件历史 |
| Topic 约定 | `dcim/{site_id}/gw/{gw_id}/{type}` | type: status/data/config |

## 设计方案

### 1. 数据模型

新增 `FirmwarePackage` 和 `OtaTask` 模型到 `backend/app/models/gateway.py`：

```python
class FirmwarePackage(Base):
    """固件包"""
    __tablename__ = "firmware_packages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    version = Column(String(50), unique=True, nullable=False, comment="版本号 (semver)")
    filename = Column(String(200), nullable=False, comment="文件名")
    file_size = Column(Integer, nullable=False, comment="文件大小(字节)")
    checksum_sha256 = Column(String(64), nullable=False, comment="SHA-256 校验和")
    download_url = Column(String(500), nullable=False, comment="下载地址")
    release_notes = Column(String(2000), comment="更新说明")
    min_version = Column(String(50), comment="最低兼容版本")
    is_active = Column(Boolean, default=True, comment="是否可用")
    created_at = Column(DateTime, default=datetime.now)


class OtaTask(Base):
    """OTA 升级任务"""
    __tablename__ = "ota_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(50), unique=True, nullable=False, comment="任务唯一标识(UUID)")
    firmware_id = Column(Integer, nullable=False, comment="目标固件包 ID")
    target_version = Column(String(50), nullable=False, comment="目标版本")
    strategy = Column(String(20), default="immediate", comment="策略: immediate/batch/canary")
    batch_size = Column(Integer, default=0, comment="分批大小(0=全部)")
    batch_interval = Column(Integer, default=300, comment="批次间隔(秒)")
    canary_percent = Column(Integer, default=10, comment="灰度百分比")
    status = Column(String(20), default="pending", comment="pending/running/paused/completed/failed/cancelled")
    total_gateways = Column(Integer, default=0, comment="总网关数")
    success_count = Column(Integer, default=0, comment="成功数")
    fail_count = Column(Integer, default=0, comment="失败数")
    created_by = Column(String(50), comment="创建人")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class OtaTaskGateway(Base):
    """OTA 任务-网关关联（每个网关的升级状态）"""
    __tablename__ = "ota_task_gateways"
    __table_args__ = (
        UniqueConstraint("task_id", "gateway_id", name="uq_ota_task_gateway"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(50), nullable=False, index=True, comment="任务 ID")
    gateway_id = Column(String(50), nullable=False, index=True, comment="网关标识")
    batch_index = Column(Integer, default=0, comment="所属批次")
    status = Column(String(20), default="pending", comment="pending/downloading/installing/verifying/success/failed/rollback")
    old_version = Column(String(50), comment="升级前版本")
    progress = Column(Integer, default=0, comment="进度百分比 0-100")
    error_message = Column(String(500), comment="错误信息")
    started_at = Column(DateTime, comment="开始时间")
    completed_at = Column(DateTime, comment="完成时间")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
```

### 2. MQTT 通信协议

#### 下行指令（后端 → 网关）

Topic: `dcim/{site_id}/gw/{gw_id}/ota`  
QoS: 2

```json
{
  "task_id": "uuid-xxx",
  "action": "upgrade",
  "firmware": {
    "version": "2.1.0",
    "download_url": "https://firmware.example.com/gw-2.1.0.bin",
    "checksum_sha256": "abc123...",
    "file_size": 10485760
  }
}
```

取消指令：
```json
{
  "task_id": "uuid-xxx",
  "action": "cancel"
}
```

#### 上行状态（网关 → 后端）

Topic: `dcim/{site_id}/gw/{gw_id}/ota/status`  
QoS: 1

```json
{
  "task_id": "uuid-xxx",
  "gw_id": "gw-001",
  "status": "downloading",
  "progress": 45,
  "error": null
}
```

状态流转：`pending → downloading → installing → verifying → success`  
失败路径：`任意阶段 → failed → rollback`

### 3. 服务层

新增 `backend/app/services/ota_service.py`：

```python
class OtaService:
    """OTA 升级服务"""

    async def create_task(self, firmware_id, gateway_ids, strategy, ..., db) -> OtaTask:
        """创建升级任务 — 验证固件、分配批次、写入数据库"""

    async def start_task(self, task_id, mqtt_publish_fn, db) -> None:
        """启动任务 — 按策略发送 MQTT 指令"""

    async def handle_ota_status(self, payload, db) -> None:
        """处理网关上报的 OTA 状态 — 更新 OtaTaskGateway"""

    async def cancel_task(self, task_id, mqtt_publish_fn, db) -> None:
        """取消任务 — 向未完成网关发送 cancel 指令"""

    async def pause_task(self, task_id, db) -> None:
        """暂停任务 — 停止发送后续批次"""

    async def resume_task(self, task_id, mqtt_publish_fn, db) -> None:
        """恢复任务 — 继续发送下一批次"""

    async def _dispatch_batch(self, task, batch_index, mqtt_publish_fn, db) -> None:
        """发送一个批次的升级指令"""

    async def _check_batch_completion(self, task_id, db) -> bool:
        """检查当前批次是否全部完成，决定是否发送下一批"""
```

#### 分批/灰度策略

- **immediate**: 一次性向所有目标网关发送指令
- **batch**: 按 `batch_size` 分组，每组完成后等待 `batch_interval` 秒再发下一组
- **canary**: 先选 `canary_percent%` 的网关升级，全部成功后再升级剩余

批次分配逻辑在 `create_task` 中完成，写入 `OtaTaskGateway.batch_index`。

#### 超时与回滚

- 单个网关升级超时：600 秒（可配置）
- 超时后标记 `failed`，网关侧 A/B 分区自动回滚
- 批次失败率超过阈值（默认 30%）时自动暂停任务

### 4. MQTT 集成

在 `backend/app/mqtt/client.py` 的 `_connect_loop` 中新增订阅：

```python
await client.subscribe("dcim/+/gw/+/ota/status", qos=1)
```

在 `_handle_message` 中新增 OTA 状态处理分支：

```python
elif msg_type == "ota" and len(parts) == 6 and parts[5] == "status":
    from ..services.ota_service import ota_service
    async with async_session() as db:
        await ota_service.handle_ota_status(payload, db)
```

### 5. API 路由

新增 `backend/app/api/v1/ota.py`：

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/firmware` | 上传/注册固件包 |
| GET | `/firmware` | 固件包列表 |
| DELETE | `/firmware/{id}` | 删除固件包 |
| POST | `/tasks` | 创建升级任务 |
| GET | `/tasks` | 任务列表（分页） |
| GET | `/tasks/{task_id}` | 任务详情（含各网关状态） |
| POST | `/tasks/{task_id}/start` | 启动任务 |
| POST | `/tasks/{task_id}/cancel` | 取消任务 |
| POST | `/tasks/{task_id}/pause` | 暂停任务 |
| POST | `/tasks/{task_id}/resume` | 恢复任务 |

路由前缀: `/api/v1/ota`

### 6. Schema

新增 `backend/app/schemas/ota.py`：

- `FirmwareCreate`, `FirmwareResponse`
- `OtaTaskCreate(firmware_id, gateway_ids: list[int], strategy, batch_size, batch_interval, canary_percent)`
- `OtaTaskResponse`, `OtaTaskDetailResponse`（含 `gateways: list[OtaGatewayStatus]`）
- `OtaGatewayStatus(gateway_id, status, progress, old_version, error_message, started_at, completed_at)`

### 7. 文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/models/gateway.py` | 修改 | 新增 FirmwarePackage, OtaTask, OtaTaskGateway |
| `backend/app/schemas/ota.py` | 新建 | OTA 相关 Schema |
| `backend/app/services/ota_service.py` | 新建 | OTA 升级核心服务 |
| `backend/app/api/v1/ota.py` | 新建 | OTA API 路由 |
| `backend/app/api/v1/__init__.py` | 修改 | 注册 OTA 路由 |
| `backend/app/mqtt/client.py` | 修改 | 订阅 ota/status topic + 处理 |
| `backend/tests/test_ota.py` | 新建 | OTA 服务测试 |

### 8. 不做的事

- 不实现真实的固件文件上传/存储（仅注册 URL + checksum）
- 不实现网关侧的 A/B 分区逻辑（网关侧职责，后端只发指令和跟踪状态）
- 不实现 WebSocket 实时推送 OTA 进度（可后续扩展）
- 不修改前端（本 Story 仅后端 + 测试）
