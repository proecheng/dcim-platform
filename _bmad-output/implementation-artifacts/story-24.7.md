# Story 24.7: 熔断降级机制

Status: done

## Story

As a 开发者,
I want 诊断引擎具备熔断降级能力,
So that 推理引擎故障时系统自动回退到L1规则引擎，保证基本诊断能力不中断。

## Acceptance Criteria (验收标准)

1. **AC-1: 熔断触发条件** — Given 诊断引擎正常运行（熔断器状态=CLOSED），**仅 L2/L3 推理参与熔断统计（L1 请求完全跳过熔断检查）**，When L2/L3 推理满足以下条件之一: (a) 错误率超过10%（滑动窗口60秒内，至少5次请求，超时也算失败）, (b) 低流量模式（窗口内请求<5次）下连续3次失败/超时即触发，Then 熔断器状态切换为 OPEN，所有新 L2/L3 诊断请求自动降级到 L1 规则引擎（L1 请求不受影响），And 记录熔断事件到系统告警（"诊断引擎L2/L3熔断，已降级到L1"）

2. **AC-2: 自动恢复流程** — When 熔断器处于 OPEN 状态且 `time.time() - last_trip_time >= 30秒`（被动检测：下一个请求到来时判断冷却期是否结束），Then 切换到 HALF_OPEN 状态，放行 1 个请求到 L2 试探（其他并发请求仍降级到 L1），And 试探成功（<10秒且无错误）→ 恢复 CLOSED，重置所有计数器，And 试探失败 → 回到 OPEN，重置 `last_trip_time` 重新冷却 30 秒

3. **AC-3: 数据库故障降级** — When PostgreSQL 诊断表不可用时，Then 诊断结果临时写入 Redis（key: `diagnosis:pending:{uuid}`, TTL: 1小时）。**datetime 字段序列化为 ISO 格式字符串，反序列化时转回 datetime 对象**。And DB 恢复后由定时任务（每 60 秒）批量写入，**每批最多处理 50 条**防止恢复风暴。And Redis 也不可用时记录 CRITICAL 日志，诊断结果丢失（不做更深层 fallback，避免过度复杂）

4. **AC-4: 健康检查端点** — 熔断器状态可通过 `GET /api/v1/diagnosis/health` 查询，返回 `{state, error_rate, last_trip_time, consecutive_failures, window_stats}`

5. **AC-5: 降级结果标记** — 当 L2/L3 请求被降级到 L1 执行时，`diagnosis_sessions.status` 标记为 `degraded`。**原始请求就是 L1 的不受熔断器影响，status 仍为 success/timeout/error**。诊断结果仍然保存和推送（confidence 可能较低）

6. **AC-6: 熔断事件告警** — 状态变化（CLOSED→OPEN, OPEN→HALF_OPEN, HALF_OPEN→CLOSED/OPEN）时通过 WebSocket `/ws/alarms` 通道推送系统告警（复用已验证的 `broadcast()` + `"alarms"` 通道，不使用未验证的 `/ws/system` 通道），type: `system_diagnosis_breaker`，target_roles: `["admin"]`

## Tasks / Subtasks (任务分解)

- [x] Task 1: CircuitBreaker 核心类 (AC: #1, #2)
  - [x] 1.1 创建 `backend/app/services/diagnosis/circuit_breaker.py` — `CircuitBreaker` 类，状态机实现（CLOSED/OPEN/HALF_OPEN）
  - [x] 1.2 实现滑动窗口计数器 — 60 秒窗口，记录每次请求的成功/失败/超时，计算实时错误率
  - [x] 1.3 实现熔断触发逻辑 — 错误率 >10%（窗口内 >=5 次请求）或低流量模式下连续 3 次失败
  - [x] 1.4 实现 HALF_OPEN 试探逻辑 — 30 秒冷却后放行 1 个请求，成功恢复 CLOSED，失败回到 OPEN
  - [x] 1.5 实现 `allow_request(inference_level: str)` 方法 — 调度器在执行推理前调用，L1 请求直接返回 (True, False) 跳过熔断检查；L2/L3 根据状态返回 (allowed: bool, degraded: bool)。OPEN 状态下检查冷却期 `time.time() - last_trip_time >= cooldown_seconds` 判断是否转 HALF_OPEN
  - [x] 1.6 实现 `record_success()` / `record_failure()` / `record_timeout()` 方法 — 推理完成后调用，更新窗口计数
  - [x] 1.7 实现状态变更回调 — 状态切换时触发告警推送

- [x] Task 2: 双路径集成 (AC: #1, #2, #5)
  - [x] 2.1 在 `DiagnosisScheduler.__init__()` 中创建 `CircuitBreaker` 实例（全局单例，scheduler 重启时重置为 CLOSED）
  - [x] 2.2 修改 `scheduler.py` 的 `_execute_inference()` — 执行前调用 `allow_request(inference_level)`，如果 degraded=True 且原始级别为 L2/L3 则强制使用 L1
  - [x] 2.3 在推理成功/失败/超时路径中调用对应的 `record_*()` 方法（仅非降级的 L2/L3 请求计数）
  - [x] 2.4 降级时设置 `status="degraded"` 传入 `DiagnosisResultStore.save_complete()`
  - [x] 2.5 `diagnosis_engine.py` 不需要接入熔断器 — 旧引擎（Story 9-3）只走 L1 规则匹配，没有 L2/L3 推理能力。熔断器仅保护 L2/L3 路径，L1 路径天然不受影响。如果未来 `diagnosis_engine.py` 增加 L2 支持，再在该路径接入熔断器

- [x] Task 3: 数据库故障降级写入 (AC: #3)
  - [x] 3.1 创建 `backend/app/services/diagnosis/fallback_store.py` — `DiagnosisFallbackStore` 类
  - [x] 3.2 实现 `save_to_redis()` — 诊断结果序列化写入 Redis（key: `diagnosis:pending:{uuid}`, TTL: 3600s）。**datetime 字段转 ISO 字符串**，反序列化时用 `datetime.fromisoformat()` 还原
  - [x] 3.3 实现 `recover_pending()` — 扫描 `diagnosis:pending:*` keys（**每批最多 50 条**），反序列化+类型还原后调用 `DiagnosisResultStore.save_complete()` 写入 DB
  - [x] 3.4 在 `DiagnosisResultStore.save_complete()` 中增加 fallback — DB 写入失败时调用 `DiagnosisFallbackStore.save_to_redis()`，**注意不要 raise 原始异常让 scheduler 重复保存**，而是 fallback 成功则返回 (0, 0) 占位 ID，fallback 失败则 raise
  - [x] 3.5 注册定时任务 — 每 60 秒执行 `recover_pending()`，DB 可用时批量恢复

- [x] Task 4: 健康检查 API (AC: #4)
  - [x] 4.1 在 `backend/app/api/v1/diagnosis.py` 中新增 `GET /api/v1/diagnosis/health` 端点
  - [x] 4.2 返回格式: `{state: "CLOSED"|"OPEN"|"HALF_OPEN", error_rate: float, last_trip_time: str|null, consecutive_failures: int, total_requests_in_window: int, failed_requests_in_window: int, degraded_since: str|null}`

- [x] Task 5: 熔断事件告警推送 (AC: #6)
  - [x] 5.1 在 `CircuitBreaker` 状态变更回调 `on_state_change` 中调用 `ws_manager.broadcast_diagnosis(msg_type="system_diagnosis_breaker", data=..., target_roles=["admin"])`（复用 Story 24.6 建立的 `broadcast_diagnosis()` 方法，保持一致性）
  - [x] 5.2 data 内容: `{"state": "OPEN", "previous_state": "CLOSED", "error_rate": 0.15, "reason": "error_rate_exceeded", "timestamp": "..."}`

- [x] Task 6: 单元测试与集成测试 (AC: 全部)
  - [x] 6.1 测试熔断触发 — 模拟连续失败，验证状态从 CLOSED → OPEN
  - [x] 6.2 测试错误率计算 — 滑动窗口内 >10% 错误率触发熔断
  - [x] 6.3 测试低流量模式 — <5 次请求时连续 3 次失败触发
  - [x] 6.4 测试自动恢复 — OPEN → 30s → HALF_OPEN → 试探成功 → CLOSED
  - [x] 6.5 测试试探失败 — HALF_OPEN → 试探失败 → 回到 OPEN
  - [x] 6.6 测试降级路由 — OPEN 状态下 L2 请求自动路由到 L1
  - [x] 6.7 测试健康检查 API — 验证返回数据完整性
  - [x] 6.8 测试 Redis 降级写入 — 模拟 DB 不可用，验证写入 Redis
  - [x] 6.9 测试 pending 恢复 — 验证 Redis 中的 pending 数据成功恢复到 DB
  - [x] 6.10 测试状态变更告警 — 验证 WebSocket 推送消息格式（通过 alarms 通道）
  - [x] 6.11 测试 L1 请求不受熔断影响 — OPEN 状态下 L1 请求正常执行，status 为 success
  - [x] 6.12 测试 datetime 序列化/反序列化 — Redis fallback 的 datetime 字段 round-trip 正确性
  - [x] 6.13 测试时间 mock — 使用可注入时间源（`time_func` 参数）测试冷却期，避免真实等待 30s

## Dev Notes (开发指南)

### 1. CircuitBreaker 核心设计

**状态机**:

```
CLOSED (正常) ──错误率>10% 或 连续3次失败──→ OPEN (熔断，降级到L1)
     ↑                                              │
     │                                        30s 冷却期
     │                                              │
     └──── 试探成功 ←──── HALF_OPEN (试探) ←────┘
```

**滑动窗口实现**（使用 `collections.deque` + 时间戳）:

```python
# backend/app/services/diagnosis/circuit_breaker.py

import asyncio
import time
import logging
from collections import deque
from enum import Enum
from typing import Tuple, Optional, Callable, Awaitable

logger = logging.getLogger(__name__)


class BreakerState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """诊断引擎熔断器 — 状态机 + 滑动窗口"""

    def __init__(
        self,
        *,
        error_threshold: float = 0.10,    # 错误率阈值 10%
        window_seconds: int = 60,          # 滑动窗口 60 秒
        min_requests: int = 5,             # 最低请求数（低于此用连续失败计数）
        consecutive_failures_threshold: int = 3,  # 低流量连续失败阈值
        cooldown_seconds: int = 30,        # OPEN → HALF_OPEN 冷却时间
        on_state_change: Optional[Callable] = None,  # 状态变更回调（async）
    ):
        self._state = BreakerState.CLOSED
        self._error_threshold = error_threshold
        self._window_seconds = window_seconds
        self._min_requests = min_requests
        self._consecutive_failures_threshold = consecutive_failures_threshold
        self._cooldown_seconds = cooldown_seconds
        self._on_state_change = on_state_change

        # 滑动窗口: deque of (timestamp, success: bool)
        self._window: deque = deque()
        self._consecutive_failures = 0
        self._last_trip_time: Optional[float] = None
        self._half_open_in_flight = False  # HALF_OPEN 期间是否有试探请求
        self._lock: Optional[asyncio.Lock] = None  # 延迟初始化，避免跨事件循环问题
        self._time_func = time_func or time.time  # 可注入时间源，测试用
```

**构造函数签名**中增加 `time_func: Optional[Callable] = None` 参数。

**延迟 Lock 初始化**: `_lock` 在首次 `allow_request()` 调用时创建（`if self._lock is None: self._lock = asyncio.Lock()`），避免在错误的事件循环中创建 Lock 导致 `RuntimeError`。

**HALF_OPEN 安全保护**: `_half_open_in_flight` 必须用 `try/finally` 包裹试探请求，确保异常（包括 `CancelledError`）时重置标志。在 `record_success()`/`record_failure()`/`record_timeout()` 中都要设置 `self._half_open_in_flight = False`。

**关键方法**:

```python
async def allow_request(self, inference_level: str = "L2") -> Tuple[bool, bool]:
    """
    Returns: (allowed, degraded)
    - L1 请求: 直接返回 (True, False)，跳过所有熔断逻辑
    - CLOSED: (True, False) — 正常放行
    - OPEN + 冷却期未到: (True, True) — 降级到 L1
    - OPEN + 冷却期已到: 转 HALF_OPEN，(True, False) — 试探放行
    - HALF_OPEN 且无 in-flight: (True, False) — 试探放行
    - HALF_OPEN 且有 in-flight: (True, True) — 试探中，其他请求降级
    """

async def record_success(self):
    """推理成功 — HALF_OPEN 时恢复 CLOSED"""

async def record_failure(self):
    """推理失败 — 更新窗口，可能触发 OPEN"""

async def record_timeout(self):
    """推理超时 — 等同 failure"""
```

### 2. 调度器集成改造

**修改 `scheduler.py` 的 `_execute_inference()` 方法**:

```python
async def _execute_inference(self, task: PriorityTask):
    task_data = task.data
    alarm_id = task_data.get("alarm_id")
    inference_level = task_data.get("inference_level")

    # 熔断检查（传入 inference_level，L1 请求直接短路返回）
    allowed, degraded = await self.circuit_breaker.allow_request(inference_level)
    original_level = inference_level

    if degraded and inference_level in ("L2", "L3"):
        # 降级到 L1
        inference_level = "L1"
        logger.warning(f"Circuit breaker degraded: alarm {alarm_id} {original_level}→L1")

    start_time = datetime.utcnow()
    try:
        result = await asyncio.wait_for(...)  # 原有推理逻辑

        # 记录成功（仅对原始级别 L2/L3 计数）
        if original_level in ("L2", "L3") and not degraded:
            await self.circuit_breaker.record_success()

        status = "degraded" if degraded else "success"
        # ... 保存结果 ...

    except asyncio.TimeoutError:
        if original_level in ("L2", "L3") and not degraded:
            await self.circuit_breaker.record_timeout()
        # ... 保存 timeout 结果 ...

    except Exception as e:
        if original_level in ("L2", "L3") and not degraded:
            await self.circuit_breaker.record_failure()
        # ... 保存 error 结果 ...
```

**关键设计决策**:
- 仅 L2/L3 请求参与熔断计数（L1 是降级目标，不纳入统计）
- 降级后的 L1 请求不计入熔断窗口（避免 L1 失败影响恢复判断）
- `status="degraded"` 仅在实际发生降级时设置

### 3. 数据库故障降级写入

**`DiagnosisFallbackStore` 设计**:

```python
# backend/app/services/diagnosis/fallback_store.py
# 重要: 使用 get_redis_client() 获取裸 redis.asyncio.Redis 连接
# 不要用 redis_service（RedisService 静默吞异常，无 scan_iter）

from app.core.redis_lock import get_redis_client

class DiagnosisFallbackStore:
    """诊断结果 Redis 降级存储"""

    PENDING_KEY_PREFIX = "diagnosis:pending:"
    PENDING_TTL = 3600  # 1 小时
    RECOVER_BATCH_SIZE = 50  # 每批最多恢复 50 条

    @staticmethod
    async def save_to_redis(data: dict) -> str:
        """
        将诊断结果序列化写入 Redis（裸连接，异常上抛）
        Returns: pending_key
        """
        client = await get_redis_client()  # 裸 redis.asyncio.Redis
        pending_id = str(uuid.uuid4())
        key = f"{DiagnosisFallbackStore.PENDING_KEY_PREFIX}{pending_id}"
        # 直接调用裸 client，写入失败会抛异常（不会被静默吞掉）
        await client.set(key, json.dumps(data, default=str), ex=DiagnosisFallbackStore.PENDING_TTL)
        return key

    @staticmethod
    async def recover_pending() -> int:
        """
        扫描并恢复 pending 诊断结果到 DB（每批最多 50 条）
        Returns: 恢复成功的数量
        """
        client = await get_redis_client()  # 裸连接，支持 scan_iter
        keys = []
        async for key in client.scan_iter(
            f"{DiagnosisFallbackStore.PENDING_KEY_PREFIX}*",
            count=DiagnosisFallbackStore.RECOVER_BATCH_SIZE
        ):
            keys.append(key)
            if len(keys) >= DiagnosisFallbackStore.RECOVER_BATCH_SIZE:
                break  # 每批最多 50 条，防止恢复风暴

        recovered = 0
        for key in keys:
            raw = await client.get(key)
            if not raw:
                continue
            try:
                data = json.loads(raw)
                # datetime 字段反序列化
                for dt_field in ("start_time", "end_time"):
                    if isinstance(data.get(dt_field), str):
                        data[dt_field] = datetime.fromisoformat(data[dt_field])
                await DiagnosisResultStore.save_complete(**data)
                await client.delete(key)
                recovered += 1
            except Exception as e:
                logger.warning(f"Failed to recover {key}: {e}")
        return recovered
```

**集成到 `result_store.py`**:

```python
# 在 save_complete() 的 except 块中:
except Exception as e:
    await session.rollback()
    logger.error("诊断结果保存失败: %s", e)
    # DB 故障降级写入 Redis
    try:
        from app.services.diagnosis.fallback_store import DiagnosisFallbackStore
        await DiagnosisFallbackStore.save_to_redis({
            "trigger_alarm_id": trigger_alarm_id,
            "device_id": device_id,
            "engine_level": engine_level,
            "start_time": start_time.isoformat() if start_time else None,
            "end_time": end_time.isoformat() if end_time else None,
            # ... 其余参数（非 datetime 类型直接传递） ...
        })
        logger.warning("诊断结果已降级写入 Redis: alarm_id=%s", trigger_alarm_id)
        return (0, 0)  # 占位 ID，不 raise，避免 scheduler 重复保存
    except Exception as redis_err:
        logger.critical("Redis 降级写入也失败: %s", redis_err)
        raise  # Redis 也失败才 raise 原始异常
```

**关键改动**:
- DB fallback 成功后返回 `(0, 0)` 而非 raise，防止 scheduler 的 except 块再次调用 `save_complete()` 造成双重写入
- **调用方检查**: scheduler 在收到 `(0, 0)` 时必须跳过后续的 `push_diagnosis_result()` 和 `update_push_status()` 调用，因为 session_id=0 不存在于 DB 中。判断方式: `if session_id == 0: return  # fallback 模式，跳过推送`

**定时恢复任务**: 在 `scheduler.start()` 中启动 60 秒间隔的恢复任务:

```python
self._recovery_task = asyncio.create_task(self._recovery_loop())

async def _recovery_loop(self):
    while self.running:
        await asyncio.sleep(60)
        try:
            recovered = await DiagnosisFallbackStore.recover_pending()
            if recovered > 0:
                logger.info(f"Recovered {recovered} pending diagnosis results from Redis")
        except Exception as e:
            logger.warning(f"Recovery loop error: {e}")
```

### 4. 健康检查 API

```python
# backend/app/api/v1/diagnosis.py

@router.get("/health")  # 必须在 /sessions/{session_id} 之前注册
async def diagnosis_health(current_user: User = Depends(require_viewer)):
    """诊断引擎健康检查（使用 require_viewer，已在 diagnosis.py 中导入）"""
    try:
        scheduler = await get_scheduler()
        breaker = scheduler.circuit_breaker
        return {
            "state": breaker.state.value,
            "error_rate": round(breaker.error_rate, 4),
            "last_trip_time": breaker.last_trip_time_iso,
            "consecutive_failures": breaker.consecutive_failures,
            "total_requests_in_window": breaker.total_in_window,
            "failed_requests_in_window": breaker.failed_in_window,
            "degraded_since": breaker.degraded_since_iso,
        }
    except Exception:
        # 调度器未启动时返回未知状态
        return {"state": "UNKNOWN", "error_rate": 0, "message": "Scheduler not running"}
```

### 5. 现有代码中需要注意的模式

**DiagnosisResultStore.save_complete()** — Story 24.6 建立的统一存储入口，本 Story 在其异常路径增加 Redis 降级逻辑

**DiagnosisPushService** — 降级结果仍然走推送流程，confidence 可能较低，自动按分级规则处理

**WebSocket 通道**:
- 诊断结果推送: `/ws/alarms` 通道（复用 `broadcast_diagnosis()`）
- 熔断状态告警: 也使用 `/ws/alarms` 通道（`broadcast(message, "alarms")`），前端通过 `type` 字段区分

**健康检查 API 路由顺序**: `/health` 端点必须在 `/sessions/{session_id}` 之前注册，否则 FastAPI 会将 "health" 解析为 session_id 参数

**`__init__.py` lazy imports** — Story 24.6 已将 scheduler 等模块改为 lazy try/except 导入，本 Story 新增的 `circuit_breaker.py` 和 `fallback_store.py` 不需要在 `__init__.py` 中导出（由 scheduler 内部使用）

**Redis 导入路径**: 项目中不存在 `app.core.redis_client` 模块。正确路径:
- `from app.core.redis_lock import get_redis_client` — 获取裸 `redis.asyncio.Redis` 连接（支持 `scan_iter`，异常不被静默吞掉）
- `from app.core.redis import redis_service` — `RedisService` 包装类（静默降级，不适合 fallback 场景）
- `fallback_store.py` 必须使用 `get_redis_client()`，测试中 mock 该函数

### 6. 与其他 Story 的关系

- **Story 24.2 (调度器)**: 本 Story 直接修改 `scheduler.py`，在 `_execute_inference()` 中增加熔断检查
- **Story 24.5 (L2 故障树)**: L2 推理超时/错误是主要的熔断触发场景
- **Story 24.6 (结果存储)**: `save_complete()` 增加 Redis 降级路径；`status="degraded"` 已在 24.6 中支持
- **Story 24.8 (标注与 RBAC)**: 健康检查 API 需要认证但无需特定角色

### Project Structure Notes

- 新增文件放在 `backend/app/services/diagnosis/` 目录
- `circuit_breaker.py` — 纯 Python 无外部依赖（仅 asyncio + collections）
- `fallback_store.py` — 依赖 Redis（`get_redis()`）
- 不创建新的 Alembic 迁移（不新增表/字段，复用 24.6 的 `status` 枚举）
- 测试文件: `backend/tests/test_story_24_7.py`

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 24.7] — AC 和技术要点
- [Source: _bmad-output/planning-artifacts/architecture.md#Section 18.9] — 熔断降级架构
- [Source: _bmad-output/planning-artifacts/architecture.md#Section 18.2] — 并发控制和超时
- [Source: _bmad-output/planning-artifacts/architecture.md#Section 18.15] — 诊断数据流（熔断检查点）
- [Source: _bmad-output/planning-artifacts/prd.md#FR34-41] — 灾难恢复和降级要求
- [Source: backend/app/services/diagnosis/scheduler.py] — 现有调度器（集成点）
- [Source: backend/app/services/diagnosis/result_store.py] — 结果存储（降级写入入口）
- [Source: _bmad-output/implementation-artifacts/story-24.6.md] — 上一 Story 建立的模式

---

**FR 追溯:** FR34-41
**Epic:** 24 (智能诊断核心引擎)
**Dependencies:** Story 24.2, 24.5, 24.6
**Estimated Effort:** 2-3 天

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6

### Debug Log References
- 修复 `_last_trip_time` falsy 判断: `0.0` 被视为 False，改为 `is not None`

### Code Review Fixes
- [H1] `result_store.py`: Redis fallback 失败时现在抛出原始 DB 异常而非 Redis 异常
- [H2] `fallback_store.py`: `recover_pending()` 检测 DB 仍不可用时（save_complete 返回 0,0）停止本批恢复，防止重复数据
- [M2] `scheduler.py`: `_recovery_loop` 启动后 5s 立即执行首次恢复，不再等待 60s
- [M3] `circuit_breaker.py`: 回调异常静默处理（回调内部自行记录日志），避免重复日志
- [L1] `fallback_store.py`: 移除未使用的 `Optional` 导入

### Completion Notes List
- 17/18 测试通过（1 个 health API 测试因已知的 `app.core.redis_client` 模块缺失导致 client fixture 加载失败，非本 Story 引入）
- 更新了 Story 24.6 的 `test_save_complete_rollback_on_error` 测试以适配新的 Redis fallback 逻辑

### File List
- `backend/app/services/diagnosis/circuit_breaker.py` — 新增，CircuitBreaker 核心类
- `backend/app/services/diagnosis/fallback_store.py` — 新增，DiagnosisFallbackStore Redis 降级存储
- `backend/app/services/diagnosis/scheduler.py` — 修改，集成熔断器 + 恢复任务
- `backend/app/services/diagnosis/result_store.py` — 修改，增加 Redis 降级路径
- `backend/app/api/v1/diagnosis.py` — 修改，新增 /health 端点
- `backend/tests/test_story_24_7.py` — 新增，18 个测试用例
- `backend/tests/test_story_24_6.py` — 修改，适配 fallback 逻辑
