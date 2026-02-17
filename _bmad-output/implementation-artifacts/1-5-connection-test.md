# Story 1.5: 连接测试功能

Status: done

## Story

As a 集成工程师,
I want 对数据源执行连接测试,
so that 我可以在正式采集前验证通信参数是否正确。

## Acceptance Criteria (验收标准)

1. **AC-1: REST API 端点** — 新增 `POST /api/v1/datasources/test-connection` 端点，接收协议类型和连接参数，返回测试结果
2. **AC-2: 适配器桥接** — API 端点根据 `protocol_type` 从 `ADAPTER_REGISTRY` 获取对应适配器，实例化后调用 `test_connection()` 方法
3. **AC-3: 成功响应** — 连接成功时返回 `{success: true, message: "连接测试成功", latency_ms: 12.5, sample_data: {...}}`
4. **AC-4: 失败响应** — 连接失败时返回 `{success: false, message: "具体错误原因"}`，HTTP 状态码仍为 200（测试结果而非服务器错误）
5. **AC-5: 超时控制** — 整体超时 10 秒，超时返回 `{success: false, message: "连接测试超时 (10s)"}`
6. **AC-6: 协议校验** — 不支持的协议类型（不在 `ADAPTER_REGISTRY` 中）返回 HTTP 400 错误
7. **AC-7: 权限控制** — 需要 operator 及以上权限才能执行连接测试
8. **AC-8: 已有数据源测试** — 新增 `POST /api/v1/datasources/{datasource_id}/test-connection` 端点，从数据库读取已有数据源配置执行测试
9. **AC-9: 网关模块独立** — 连接测试逻辑在 gateway 层完成，API 层仅做桥接调用，不引入 gateway 对 backend 的依赖

## Tasks / Subtasks (任务分解)

- [x] Task 1: 新增连接测试请求/响应 Schema (AC: #1, #3, #4)
  - [x] 1.1 在 `backend/app/schemas/gateway.py` 中新增 `ConnectionTestRequest` — 包含 `protocol_type: str` 和 `connection_config: dict`（与 DataSource 模型字段名一致）
  - [x] 1.2 新增 `ConnectionTestResponse` — 包含 `success: bool`, `message: str`, `latency_ms: Optional[float]`, `sample_data: Optional[dict]`

- [x] Task 2: 实现连接测试服务函数 (AC: #2, #5, #6, #9)
  - [x] 2.1 在 `backend/app/services/` 中创建 `connection_test.py`
  - [x] 2.2 实现 `async def test_datasource_connection(protocol_type: str, connection_config: dict) -> dict`
  - [x] 2.3 从 `ADAPTER_REGISTRY` 获取适配器类，实例化，构建 `DataSourceConfig`，调用 `connect()` + `test_connection()`
  - [x] 2.4 整体超时 10 秒（`asyncio.wait_for`）
  - [x] 2.5 确保 `disconnect()` 在 finally 块中调用（资源清理）
  - [x] 2.6 不支持的协议类型抛出 `ValueError`

- [x] Task 3: 新增 API 端点 (AC: #1, #7, #8)
  - [x] 3.1 在 `backend/app/api/v1/datasources.py` 中新增 `POST /test-connection` — 接收 `ConnectionTestRequest`，调用服务函数
  - [x] 3.2 新增 `POST /{datasource_id}/test-connection` — 从数据库读取数据源配置，调用服务函数
  - [x] 3.3 两个端点都需要 `require_operator` 权限
  - [x] 3.4 协议类型不在 `ADAPTER_REGISTRY` 中时返回 HTTP 400（不使用 `KNOWN_PROTOCOL_TYPES`，连接测试只对已实现的适配器有意义）

- [x] Task 4: 单元测试 (AC: 全部)
  - [x] 4.1 测试 `test_datasource_connection` 服务函数 — mock ADAPTER_REGISTRY
  - [x] 4.2 测试成功响应（success=True, latency_ms, sample_data）
  - [x] 4.3 测试失败响应（success=False, message）
  - [x] 4.4 测试超时 10 秒
  - [x] 4.5 测试不支持的协议类型 → ValueError
  - [x] 4.6 测试 disconnect 在 finally 中调用（资源清理）
  - [x] 4.7 测试 API 端点 `POST /test-connection`（mock 服务函数）
  - [x] 4.8 测试 API 端点 `POST /{id}/test-connection`（mock 服务函数 + mock DB）
  - [x] 4.9 测试权限控制（无权限 → 401）

## Dev Notes (开发指南)

### 1. 文件位置

```
backend/app/schemas/gateway.py          # 修改 — 新增 ConnectionTestRequest/Response
backend/app/services/connection_test.py  # 新建 — 连接测试服务函数
backend/app/api/v1/datasources.py       # 修改 — 新增两个 API 端点
backend/tests/test_connection_test.py   # 新建 — 单元测试
```

### 2. Schema 定义

```python
# backend/app/schemas/gateway.py 新增

class ConnectionTestRequest(BaseModel):
    protocol_type: str
    connection_config: dict  # 与 DataSource 模型字段名一致

class ConnectionTestResponse(BaseModel):
    success: bool
    message: str
    latency_ms: Optional[float] = None
    sample_data: Optional[dict] = None
```

### 3. 服务函数核心逻辑

```python
# backend/app/services/connection_test.py

import asyncio
import logging
from dataclasses import asdict
from gateway.adapters.registry import ADAPTER_REGISTRY
from gateway.adapters.base import DataSourceConfig, ConnectionResult

logger = logging.getLogger(__name__)

async def test_datasource_connection(
    protocol_type: str,
    connection_config: dict,
) -> dict:
    """执行数据源连接测试"""
    if protocol_type not in ADAPTER_REGISTRY:
        raise ValueError(f"不支持的协议类型: {protocol_type}")

    adapter_cls = ADAPTER_REGISTRY[protocol_type]
    adapter = adapter_cls()

    logger.info("开始连接测试: protocol_type=%s", protocol_type)

    try:
        # 构建最小配置（DataSourceConfig 使用 connection_params 字段名）
        config = DataSourceConfig(
            datasource_id="test-connection",
            protocol_type=protocol_type,
            connection_params=connection_config,
        )

        # 连接 + 测试，整体超时 10 秒
        async def _do_test() -> ConnectionResult:
            connected = await adapter.connect(config)
            if not connected:
                status = adapter.get_status()
                return ConnectionResult(
                    success=False,
                    message=status.error_message or "连接失败",
                )
            return await adapter.test_connection()

        result = await asyncio.wait_for(_do_test(), timeout=10.0)

        logger.info(
            "连接测试完成: protocol_type=%s, success=%s, latency_ms=%s",
            protocol_type, result.success, result.latency_ms,
        )
        return asdict(result)

    except asyncio.TimeoutError:
        logger.warning("连接测试超时: protocol_type=%s", protocol_type)
        return asdict(ConnectionResult(
            success=False,
            message="连接测试超时 (10s)",
        ))
    except Exception as e:
        logger.error("连接测试异常: protocol_type=%s, error=%s", protocol_type, e)
        return asdict(ConnectionResult(
            success=False,
            message=str(e),
        ))
    finally:
        try:
            await adapter.disconnect()
        except Exception:
            pass
```

### 4. API 端点

```python
# backend/app/api/v1/datasources.py 新增

from gateway.adapters.registry import ADAPTER_REGISTRY as _ADAPTER_REGISTRY

@router.post("/test-connection", summary="测试数据源连接")
async def test_connection(
    req: ConnectionTestRequest,
    _: User = Depends(require_operator),
):
    # 用 ADAPTER_REGISTRY 校验，只允许已实现的协议（非 KNOWN_PROTOCOL_TYPES）
    if req.protocol_type not in _ADAPTER_REGISTRY:
        raise HTTPException(status_code=400, detail=f"不支持的协议类型: {req.protocol_type}")

    from ...services.connection_test import test_datasource_connection
    result = await test_datasource_connection(req.protocol_type, req.connection_config)
    return result


@router.post("/{datasource_id}/test-connection", summary="测试已有数据源连接")
async def test_existing_connection(
    datasource_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_operator),
):
    result = await db.execute(select(DataSource).where(DataSource.id == datasource_id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="数据源不存在")

    # 已有数据源也需要校验适配器是否已实现
    if obj.protocol_type not in _ADAPTER_REGISTRY:
        raise HTTPException(status_code=400, detail=f"不支持的协议类型: {obj.protocol_type}")

    from ...services.connection_test import test_datasource_connection
    result = await test_datasource_connection(obj.protocol_type, obj.connection_config)
    return result
```

**重要**: `POST /test-connection` 必须放在 `POST /{datasource_id}/test-connection` 之前定义，否则 FastAPI 会把 "test-connection" 当作 `datasource_id` 路径参数匹配。

### 5. 路由顺序注意

FastAPI 按定义顺序匹配路由。当前 `datasources.py` 中已有 `POST ""` (创建数据源)。新增的两个端点应放在文件中 `GET /{datasource_id}` 之前，确保 `/test-connection` 不被误匹配为 `/{datasource_id}`。

推荐顺序:
1. `GET ""` — 列表
2. `POST ""` — 创建
3. `POST "/test-connection"` — 测试连接（新增）
4. `GET "/{datasource_id}"` — 详情
5. `PUT "/{datasource_id}"` — 更新
6. `POST "/{datasource_id}/test-connection"` — 测试已有数据源（新增）
7. `DELETE "/{datasource_id}"` — 删除

### 6. 关键约束

- **gateway 模块独立**: 服务函数通过 `from gateway.adapters.registry import ADAPTER_REGISTRY` 导入，gateway 不依赖 backend
- **资源清理**: `adapter.disconnect()` 必须在 finally 中调用，防止连接泄漏
- **HTTP 200 返回测试结果**: 连接失败不是服务器错误，HTTP 状态码始终 200，通过 `success` 字段区分
- **lazy logging**: 使用 `%s` 格式
- **测试使用 mock**: mock `ADAPTER_REGISTRY` 和适配器实例，不需要真实设备

### 7. 测试策略

```python
# 测试服务函数
@patch("backend.app.services.connection_test.ADAPTER_REGISTRY")
async def test_connection_success(self, mock_registry):
    mock_adapter = AsyncMock()
    mock_adapter.connect.return_value = True
    mock_adapter.test_connection.return_value = ConnectionResult(
        success=True, message="连接测试成功", latency_ms=12.5, sample_data={"key": "val"}
    )
    mock_adapter.disconnect.return_value = None
    mock_registry.__contains__ = lambda k: True        # 注意: 无 self 参数
    mock_registry.__getitem__ = lambda k: lambda: mock_adapter  # 注意: 无 self 参数
    ...

# 测试 API 端点 — 使用 httpx AsyncClient + app
from httpx import AsyncClient, ASGITransport
async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
    resp = await client.post("/api/v1/datasources/test-connection", json={...}, headers=auth_headers)
```

**注意**: API 测试需要 mock 认证依赖（`require_operator`），可以通过 `app.dependency_overrides` 实现。

### Project Structure Notes (项目结构对齐)

- `backend/app/services/connection_test.py` — 新建，遵循现有 services 目录模式
- `backend/app/api/v1/datasources.py` — 修改，新增两个端点
- `backend/app/schemas/gateway.py` — 修改，新增两个 Schema
- 测试文件放在 `backend/tests/test_connection_test.py`

### References (参考来源)

- [Source: architecture.md#4.3] 数据源管理 API — CRUD、连接测试
- [Source: architecture.md#6.1] BaseProtocolAdapter.test_connection() — 已在所有适配器中实现
- [Source: epics.md#Story 1.5] Acceptance Criteria — 测试连接、10 秒超时、成功/失败响应
- [Source: datasources.py] 现有 CRUD 端点 — 路由顺序参考
- [Source: gateway.py models] DataSource.connection_config — 已有数据源的连接配置字段

### Previous Story Intelligence (Story 1.4 经验)

- **ADAPTER_REGISTRY 导入**: `from gateway.adapters.registry import ADAPTER_REGISTRY`
- **DataSourceConfig 构建**: `DataSourceConfig(datasource_id=..., protocol_type=..., connection_params=...)`
- **ConnectionResult 数据类**: `success: bool, message: str, sample_data: Optional[dict], latency_ms: Optional[float]`
- **test_connection 已实现**: modbus_tcp（读 HR:0）、modbus_rtu（读 HR:0）、snmp（读 sysDescr）— 都有 10 秒超时
- **适配器生命周期**: `adapter = AdapterCls()` → `await adapter.connect(config)` → `await adapter.test_connection()` → `await adapter.disconnect()`

## Dev Agent Record

### Agent Model Used

claude-opus-4-6 (sisyphus-junior)

### Debug Log References

### Completion Notes List

- 22/22 测试通过（12 服务层 + 10 API 层）
- 164/167 全量回归通过，3 个失败为 SNMP 注册测试的预存问题（ADAPTER_REGISTRY fixture 隔离）
- 服务函数使用 `dataclasses.asdict()` 统一转换 ConnectionResult → dict
- API 端点使用 `_ADAPTER_REGISTRY` 校验协议类型（非 KNOWN_PROTOCOL_TYPES）
- 路由顺序正确：`/test-connection` 在 `/{datasource_id}` 之前

### File List

- `backend/app/schemas/gateway.py` — 修改：新增 ConnectionTestRequest, ConnectionTestResponse
- `backend/app/services/connection_test.py` — 新建：连接测试服务函数（66 行）
- `backend/app/api/v1/datasources.py` — 修改：新增 2 个端点 + ADAPTER_REGISTRY 导入
- `backend/tests/test_connection_test.py` — 新建：22 个测试（440 行）

### Story Review (Adversarial) — 2026-02-15

**发现问题:** 2 CRITICAL, 3 ENHANCE, 1 OPTIMIZE（O1 不修复）

| ID | 级别 | 问题 | 修复 |
|----|------|------|------|
| C1 | CRITICAL | `ConnectionTestRequest.connection_params` 与 DataSource 模型 `connection_config` 字段名不一致 | 统一为 `connection_config`，服务函数内部映射到 `DataSourceConfig.connection_params` |
| C2 | CRITICAL | API 端点用 `KNOWN_PROTOCOL_TYPES` 校验，包含未实现协议（mqtt 等），会通过 API 层但在服务层报错 | 改用 `ADAPTER_REGISTRY` 校验，只允许已实现的适配器 |
| E1 | ENHANCE | `hasattr(result, 'success')` 类型判断不严谨，`_do_test()` 混合返回 dict 和 ConnectionResult | 统一返回 `ConnectionResult`，用 `dataclasses.asdict()` 转换 |
| E2 | ENHANCE | 测试策略中 mock `__contains__`/`__getitem__` 的 lambda 多了 `self` 参数 | 移除多余的 `self` 参数 |
| E3 | ENHANCE | 服务函数缺少日志记录，连接测试是运维关键操作 | 添加 `logger.info/warning/error` 记录测试开始、完成、超时、异常 |
| O1 | OPTIMIZE | `POST /test-connection` 路径不够 RESTful | 保持现状，项目其他 API 也非严格 RESTful |

### Code Review (Adversarial) — 2026-02-15

**发现问题:** 0 HIGH (H1 撤回), 2 MEDIUM, 1 LOW（L1 不修复）

| ID | 级别 | 问题 | 修复 |
|----|------|------|------|
| H1 | ~~HIGH~~ 撤回 | lambda `self` 参数看似多余 | 实际 MagicMock 描述符协议需要 `self`，撤回修复 |
| M1 | MEDIUM | `test_existing_connection` 中 `result` 变量名被 DB 查询和服务返回值复用 | 服务返回值改名为 `test_result` |
| M2 | MEDIUM | 服务函数使用 lazy import，与项目其他模块不一致 | 移到文件顶部 import 区域，更新测试 mock 路径 |
| L1 | LOW | `_do_test` coroutine never awaited 警告 | 不修复，mock `asyncio.wait_for` 的固有副作用 |
