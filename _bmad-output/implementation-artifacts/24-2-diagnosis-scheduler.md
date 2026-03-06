# Story 24.2: 诊断调度器与并发控制

**Story ID:** 24.2
**Epic:** 24 - 智能诊断核心引擎
**Status:** ready-for-dev
**Created:** 2026-03-06
**Author:** BMAD System

---

## 用户故事

As a 开发者,
I want 一个支持优先级队列和并发控制的诊断调度器,
So that 多个告警同时触发时系统能有序处理，紧急告警优先，不会因过载崩溃。

---

## 验收标准

### 核心功能

- **Given** 诊断引擎服务已启动
- **When** 多个告警同时通过 Redis Pub/Sub 触发诊断
- **Then** 调度器使用自定义 `CancellablePriorityQueue(maxsize=50)`（基于 heapq + `_cancelled` 标记法 + asyncio.Event 通知）排队，按告警级别优先级排序
- **And** 使用 `asyncio.Semaphore(10)` 限制最多 10 个并发推理任务
- **And** 队列满时：低优先级新任务直接丢弃并记录日志；紧急/重要新任务将队列中最低优先级的未取消任务标记为取消，然后插入新任务
- **And** 每个推理任务设置 `asyncio.wait_for` 超时保护（L1: 2s, L2: 10s, L3: 60s）
- **And** 超时的任务触发熔断计数器（见 Story 24.7）
- **And** 调度器支持根据告警级别自动选择推理级别：紧急/重要→L2，次要/提示→L1
- **And** 运维工程师可通过 API `/api/v1/diagnosis/trigger` 手动触发诊断并指定推理级别（自动/L1/L2/L3），需 operator+ 角色，限流 10 次/分钟/用户、30 次/分钟/全局

### 告警订阅与路由

- **Given** 告警引擎检测到越限并通过 Redis Pub/Sub 发布 `alarm:new` 事件
- **When** 诊断调度器订阅该事件
- **Then** 调度器将告警封装为诊断任务提交到 `CancellablePriorityQueue`（按告警级别排优先级：紧急=0, 重要=1, 次要=2, 提示=3）
- **And** L1 引擎匹配成功时输出结论并保存到 `diagnosis_results` 表
- **And** 无规则匹配时：紧急/重要告警自动升级到 L2 分析（调度器重新入队为 L2 任务）；次要/提示告警记录"L1未匹配"结果，不自动升级（管理员可通过手动触发 API 升级）
- **And** L2 未匹配时：不自动升级到 L3，记录"L2未匹配"结果（L3 推理需手动触发，因为 L3 推理耗时较长且资源消耗大）

### 结果保存

- **Given** L1 引擎完成推理
- **When** 推理成功或失败
- **Then** 系统在 `diagnosis_results` 表创建记录（alarm_id, device_id, diagnosis_level, matched, conclusion, confidence, suggested_actions, evidence, inference_time_ms, created_at）
- **And** 推理失败时记录错误信息到 `error_message` 字段
- **And** 通过 WebSocket `/ws/diagnosis` 推送结果给前端（需 operator+ 角色）（注：WebSocket 推送在后续 Story 实现）

---

## 技术实现要点

### 1. CancellablePriorityQueue 实现

**文件**: `backend/app/services/diagnosis/priority_queue.py`

```python
import asyncio
import heapq
from typing import Any, Optional
from dataclasses import dataclass, field

@dataclass(order=True)
class PriorityTask:
    priority: int
    task_id: str = field(compare=False)
    data: Any = field(compare=False)
    _cancelled: bool = field(default=False, compare=False)

class CancellablePriorityQueue:
    """
    基于 heapq 的可取消优先级队列
    - 支持按优先级排序（数字越小优先级越高）
    - 支持任务取消（标记法，不立即移除）
    - 支持队列满时的替换策略
    """
    def __init__(self, maxsize: int = 50):
        self._queue: list[PriorityTask] = []
        self._maxsize = maxsize
        self._event = asyncio.Event()
        self._lock = asyncio.Lock()

    async def put(self, priority: int, task_id: str, data: Any) -> bool:
        """
        插入任务，返回是否成功
        队列满时：
        - 新任务优先级 >= 队列最低优先级：丢弃新任务，返回 False
        - 新任务优先级 < 队列最低优先级：取消队列中最低优先级任务，插入新任务
        """
        async with self._lock:
            # 移除已取消的任务
            self._queue = [t for t in self._queue if not t._cancelled]
            heapq.heapify(self._queue)

            if len(self._queue) >= self._maxsize:
                # 队列已满，检查是否需要替换
                # 此时 self._queue 中都是未取消的任务
                lowest_priority_task = max(self._queue, key=lambda t: t.priority)
                if priority >= lowest_priority_task.priority:
                    # 新任务优先级更低，丢弃
                    return False
                else:
                    # 取消最低优先级任务
                    lowest_priority_task._cancelled = True

            # 插入新任务
            task = PriorityTask(priority=priority, task_id=task_id, data=data)
            heapq.heappush(self._queue, task)
            self._event.set()
            return True

    async def get(self) -> Optional[PriorityTask]:
        """
        获取最高优先级任务（跳过已取消的任务）
        """
        while True:
            async with self._lock:
                # 移除已取消的任务
                while self._queue and self._queue[0]._cancelled:
                    heapq.heappop(self._queue)

                if self._queue:
                    task = heapq.heappop(self._queue)
                    if not task._cancelled:
                        return task
                else:
                    self._event.clear()

            # 等待新任务
            await self._event.wait()

    async def cancel(self, task_id: str) -> bool:
        """
        取消指定任务（标记法）
        """
        async with self._lock:
            for task in self._queue:
                if task.task_id == task_id and not task._cancelled:
                    task._cancelled = True
                    return True
            return False

    def qsize(self) -> int:
        """
        返回队列大小（不包括已取消的任务）
        """
        return sum(1 for t in self._queue if not t._cancelled)
```

### 2. DiagnosisScheduler 实现

**文件**: `backend/app/services/diagnosis/scheduler.py`

```python
import asyncio
import json
import logging
from typing import Optional
from datetime import datetime
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import async_session
from app.core.redis_client import get_redis
from app.services.diagnosis.priority_queue import CancellablePriorityQueue, PriorityTask
from app.services.diagnosis.l1_engine import L1RuleEngine
from app.models.diagnosis import DiagnosisResult

logger = logging.getLogger(__name__)

# 告警级别到优先级的映射（数字越小优先级越高）
ALARM_LEVEL_PRIORITY = {
    "critical": 0,  # 紧急
    "major": 1,     # 重要
    "minor": 2,     # 次要
    "warning": 3    # 提示
}

# 推理级别超时配置（秒）
INFERENCE_TIMEOUT = {
    "L1": 2,
    "L2": 10,
    "L3": 60
}

class DiagnosisScheduler:
    """
    诊断调度器
    - 订阅 Redis alarm:new 事件
    - 管理优先级队列
    - 控制并发推理任务
    - 保存诊断结果
    """
    def __init__(self, max_workers: int = 10, queue_size: int = 50):
        self.queue = CancellablePriorityQueue(maxsize=queue_size)
        self.semaphore = asyncio.Semaphore(max_workers)
        self.max_workers = max_workers
        self.l1_engine = L1RuleEngine()
        self.redis: Optional[Redis] = None
        self.running = False
        self._workers: list[asyncio.Task] = []

    async def start(self):
        """
        启动调度器
        """
        if self.running:
            logger.warning("Scheduler already running")
            return

        self.running = True
        self.redis = await get_redis()

        # 加载 L1 规则引擎
        try:
            await self.l1_engine.load_rules()
        except Exception as e:
            logger.error(f"Failed to load L1 rules: {e}", exc_info=True)
            self.running = False
            raise RuntimeError(f"Cannot start scheduler: L1 engine initialization failed") from e

        # 启动 worker 协程
        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker(f"worker-{i}"))
            self._workers.append(worker)

        # 启动 Redis 订阅
        subscriber = asyncio.create_task(self._subscribe_alarms())
        self._workers.append(subscriber)

        logger.info("DiagnosisScheduler started")

    async def stop(self):
        """
        停止调度器（优雅关闭）
        """
        logger.info("Stopping scheduler...")
        self.running = False

        # 先取消订阅协程，停止接收新告警
        if self._workers:
            subscriber = self._workers[-1]  # 最后一个是订阅协程
            subscriber.cancel()
            try:
                await subscriber
            except asyncio.CancelledError:
                pass

        # 等待队列清空（最多等待 30 秒）
        logger.info("Waiting for queue to drain...")
        for _ in range(30):
            if self.queue.qsize() == 0:
                break
            await asyncio.sleep(1)

        if self.queue.qsize() > 0:
            logger.warning(f"Queue not empty after 30s, {self.queue.qsize()} tasks will be lost")

        # 取消所有 worker
        for worker in self._workers[:-1]:  # 排除已取消的订阅协程
            worker.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        logger.info("DiagnosisScheduler stopped")

    async def _subscribe_alarms(self):
        """
        订阅 Redis alarm:new 事件（带重连机制）
        """
        retry_delay = 1  # 初始重试延迟（秒）
        max_retry_delay = 60  # 最大重试延迟（秒）

        while self.running:
            try:
                pubsub = self.redis.pubsub()
                await pubsub.subscribe("alarm:new")

                logger.info("Subscribed to alarm:new channel")
                retry_delay = 1  # 重置重试延迟

                async for message in pubsub.listen():
                    if not self.running:
                        break

                    if message["type"] == "message":
                        try:
                            alarm_data = json.loads(message["data"])
                            await self._handle_alarm(alarm_data)
                        except Exception as e:
                            logger.error(f"Error handling alarm: {e}", exc_info=True)
            except asyncio.CancelledError:
                logger.info("Alarm subscription cancelled")
                break
            except Exception as e:
                logger.error(f"Error in alarm subscription: {e}, retrying in {retry_delay}s", exc_info=True)
                # 关闭旧的 pubsub 连接
                try:
                    await pubsub.unsubscribe("alarm:new")
                    await pubsub.close()
                except:
                    pass
                await asyncio.sleep(retry_delay)
                # 指数退避，最大 60 秒
                retry_delay = min(retry_delay * 2, max_retry_delay)

    async def _handle_alarm(self, alarm_data: dict):
        """
        处理告警事件，提交到队列
        """
        alarm_id = alarm_data.get("id")
        alarm_level = alarm_data.get("level", "warning")
        device_id = alarm_data.get("device_id")

        # 映射告警级别到优先级
        priority = ALARM_LEVEL_PRIORITY.get(alarm_level, 3)

        # 自动选择推理级别
        if alarm_level in ["critical", "major"]:
            inference_level = "L2"  # 紧急/重要 → L2（Story 24.5 实现）
        else:
            inference_level = "L1"  # 次要/提示 → L1

        task_data = {
            "alarm_id": alarm_id,
            "device_id": device_id,
            "alarm_level": alarm_level,
            "inference_level": inference_level,
            "alarm_data": alarm_data
        }

        # 提交到队列
        success = await self.queue.put(priority, f"alarm-{alarm_id}", task_data)

        if not success:
            logger.warning(f"Alarm {alarm_id} dropped (queue full, low priority)")
            # TODO: WebSocket 通知运维人员

    async def _worker(self, worker_id: str):
        """
        Worker 协程，从队列取任务并执行推理
        """
        logger.info(f"Worker {worker_id} started")

        try:
            while self.running:
                # 获取任务
                task: PriorityTask = await self.queue.get()

                if task is None:
                    continue

                # 并发控制
                async with self.semaphore:
                    await self._execute_inference(task)
        except asyncio.CancelledError:
            logger.info(f"Worker {worker_id} cancelled")
        except Exception as e:
            logger.error(f"Worker {worker_id} error: {e}", exc_info=True)

    async def _execute_inference(self, task: PriorityTask):
        """
        执行推理任务
        """
        task_data = task.data
        alarm_id = task_data["alarm_id"]
        device_id = task_data["device_id"]
        inference_level = task_data["inference_level"]
        alarm_data = task_data["alarm_data"]

        start_time = datetime.utcnow()

        try:
            # 超时保护
            timeout = INFERENCE_TIMEOUT.get(inference_level, 2)

            if inference_level == "L1":
                result = await asyncio.wait_for(
                    self.l1_engine.match_rules(alarm_data),
                    timeout=timeout
                )
            elif inference_level == "L2":
                # TODO: Story 24.5 实现 L2 引擎
                logger.warning(f"L2 inference not implemented yet for alarm {alarm_id}")
                result = {"matched": False, "reason": "L2 not implemented"}
            else:
                result = {"matched": False, "reason": f"Unknown level {inference_level}"}

            # 计算推理时间
            inference_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            # 保存结果
            await self._save_result(alarm_id, device_id, inference_level, result, inference_time_ms)

            # 自动升级逻辑
            if not result.get("matched") and task_data["alarm_level"] in ["critical", "major"]:
                if inference_level == "L1":
                    # 检查是否已有 L2 诊断结果，避免重复诊断
                    async with async_session() as session:
                        existing_l2 = await session.execute(
                            select(DiagnosisResult).where(
                                DiagnosisResult.alarm_id == alarm_id,
                                DiagnosisResult.diagnosis_level == "L2"
                            )
                        )
                        if existing_l2.scalar_one_or_none() is None:
                            # L1 未匹配且无 L2 结果，升级到 L2
                            logger.info(f"Alarm {alarm_id} L1 no match, upgrading to L2")
                            task_data["inference_level"] = "L2"
                            priority = ALARM_LEVEL_PRIORITY.get(task_data["alarm_level"], 1)
                            await self.queue.put(priority, f"alarm-{alarm_id}-L2", task_data)
                        else:
                            logger.info(f"Alarm {alarm_id} L1 no match, but L2 result already exists, skipping upgrade")

        except asyncio.TimeoutError:
            logger.error(f"Inference timeout for alarm {alarm_id} (level={inference_level})")
            # TODO: 触发熔断计数器（Story 24.7）
            await self._save_result(
                alarm_id, device_id, inference_level,
                {"matched": False, "error": "Timeout"},
                INFERENCE_TIMEOUT.get(inference_level, 2) * 1000
            )
        except Exception as e:
            logger.error(f"Inference error for alarm {alarm_id}: {e}", exc_info=True)
            await self._save_result(
                alarm_id, device_id, inference_level,
                {"matched": False, "error": str(e)},
                0
            )

    async def _save_result(
        self,
        alarm_id: int,
        device_id: int,
        diagnosis_level: str,
        result: dict,
        inference_time_ms: int
    ):
        """
        保存诊断结果到数据库
        """
        async with async_session() as session:
            diagnosis_result = DiagnosisResult(
                alarm_id=alarm_id,
                device_id=device_id,
                diagnosis_level=diagnosis_level,
                matched=result.get("matched", False),
                conclusion=result.get("conclusion"),
                confidence=result.get("confidence"),
                suggested_actions=result.get("suggested_actions"),
                evidence=result.get("evidence"),
                inference_time_ms=inference_time_ms,
                error_message=result.get("error")
            )
            session.add(diagnosis_result)
            await session.commit()

            logger.info(f"Saved diagnosis result for alarm {alarm_id}")

            # TODO: WebSocket 推送结果（需 operator+ 角色）

    async def trigger_manual(
        self,
        device_id: int,
        level: str = "auto",
        alarm_data: Optional[dict] = None
    ) -> dict:
        """
        手动触发诊断
        """
        if level == "auto":
            level = "L1"

        if level not in ["L1", "L2", "L3"]:
            raise ValueError(f"Invalid level: {level}")

        # 验证设备存在
        from app.models.device import Device
        async with async_session() as session:
            device = await session.get(Device, device_id)
            if device is None:
                raise ValueError(f"Device {device_id} not found")

        # 构造任务数据
        task_data = {
            "alarm_id": None,  # 手动触发无告警ID
            "device_id": device_id,
            "alarm_level": "manual",
            "inference_level": level,
            "alarm_data": alarm_data or {}
        }

        # 手动触发优先级设为 1（重要）
        # 使用 UUID 避免 task_id 冲突
        import uuid
        task_id = f"manual-{device_id}-{uuid.uuid4().hex[:8]}"
        success = await self.queue.put(1, task_id, task_data)

        if not success:
            raise RuntimeError("Queue full, cannot trigger diagnosis")

        return {"status": "queued", "device_id": device_id, "level": level}

# 全局调度器实例
_scheduler: Optional[DiagnosisScheduler] = None

async def get_scheduler() -> DiagnosisScheduler:
    """
    获取全局调度器实例
    """
    global _scheduler
    if _scheduler is None:
        _scheduler = DiagnosisScheduler()
    return _scheduler
```

### 3. 数据库模型扩展

**文件**: `backend/app/models/diagnosis.py`（扩展）

```python
# 在现有 DiagnosisRule 模型基础上，新增 DiagnosisResult 模型

class DiagnosisResult(Base):
    """
    诊断结果表
    """
    __tablename__ = "diagnosis_results"

    id = Column(Integer, primary_key=True, index=True)
    alarm_id = Column(Integer, ForeignKey("alarms.id", ondelete="SET NULL"), nullable=True, index=True)  # 手动触发时为 NULL
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False, index=True)
    diagnosis_level = Column(String(10), nullable=False)  # L1/L2/L3
    matched = Column(Boolean, nullable=False, default=False)
    conclusion = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    suggested_actions = Column(JSON, nullable=True)
    evidence = Column(JSON, nullable=True)
    inference_time_ms = Column(Integer, nullable=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    # 关系
    alarm = relationship("Alarm", back_populates="diagnosis_results")
    device = relationship("Device", back_populates="diagnosis_results")
```

**同时需要修改以下模型文件添加反向关系**：

**文件**: `backend/app/models/alarm.py`

```python
# 在 Alarm 模型中添加
diagnosis_results = relationship("DiagnosisResult", back_populates="alarm", cascade="all, delete-orphan")
```

**文件**: `backend/app/models/device.py`

```python
# 在 Device 模型中添加
diagnosis_results = relationship("DiagnosisResult", back_populates="device", cascade="all, delete-orphan")
```

**Alembic 迁移脚本**:

```python
# backend/alembic/versions/xxxx_create_diagnosis_results.py

def upgrade():
    op.create_table(
        'diagnosis_results',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('alarm_id', sa.Integer(), nullable=True),
        sa.Column('device_id', sa.Integer(), nullable=False),
        sa.Column('diagnosis_level', sa.String(length=10), nullable=False),
        sa.Column('matched', sa.Boolean(), nullable=False),
        sa.Column('conclusion', sa.Text(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('suggested_actions', sa.JSON(), nullable=True),
        sa.Column('evidence', sa.JSON(), nullable=True),
        sa.Column('inference_time_ms', sa.Integer(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['alarm_id'], ['alarms.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_diagnosis_results_alarm_id', 'diagnosis_results', ['alarm_id'])
    op.create_index('ix_diagnosis_results_device_id', 'diagnosis_results', ['device_id'])
    op.create_index('ix_diagnosis_results_created_at', 'diagnosis_results', ['created_at'])

def downgrade():
    op.drop_index('ix_diagnosis_results_created_at', table_name='diagnosis_results')
    op.drop_index('ix_diagnosis_results_device_id', table_name='diagnosis_results')
    op.drop_index('ix_diagnosis_results_alarm_id', table_name='diagnosis_results')
    op.drop_table('diagnosis_results')
```

### 4. API 端点

**文件**: `backend/app/api/v1/diagnosis.py`

```python
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi_limiter.depends import RateLimiter
from pydantic import BaseModel
from typing import Optional

from app.api.deps import require_operator, get_current_user, global_rate_limiter
from app.services.diagnosis.scheduler import get_scheduler
from app.models.user import User

router = APIRouter()

class TriggerDiagnosisRequest(BaseModel):
    device_id: int
    level: str = "auto"  # auto/L1/L2/L3

class TriggerDiagnosisResponse(BaseModel):
    status: str
    device_id: int
    level: str

@router.post(
    "/trigger",
    response_model=TriggerDiagnosisResponse,
    dependencies=[
        Depends(require_operator),
        Depends(RateLimiter(times=10, seconds=60)),  # 10次/分钟/用户
        Depends(global_rate_limiter(times=30, seconds=60))  # 30次/分钟/全局
    ]
)
async def trigger_diagnosis(
    request: TriggerDiagnosisRequest,
    current_user: User = Depends(get_current_user)
):
    """
    手动触发诊断

    需要 operator+ 角色
    限流: 10次/分钟/用户, 30次/分钟/全局
    """
    scheduler = await get_scheduler()

    try:
        result = await scheduler.trigger_manual(
            device_id=request.device_id,
            level=request.level
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))

# TODO: 其他端点（sessions 列表/详情, health, chaos/*）
```

**全局限流实现**（需添加到 `backend/app/api/deps.py`）:

```python
from fastapi import HTTPException, status
from redis.asyncio import Redis
from app.core.redis_client import get_redis
import time

def global_rate_limiter(times: int, seconds: int):
    """
    全局限流装饰器
    使用 Redis 计数器实现
    """
    async def dependency():
        redis = await get_redis()
        key = f"global_rate_limit:{int(time.time() // seconds)}"

        # 原子递增
        count = await redis.incr(key)

        # 设置过期时间（首次创建时）
        if count == 1:
            await redis.expire(key, seconds)

        if count > times:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Global rate limit exceeded: {times} requests per {seconds} seconds"
            )

    return dependency
```

### 5. FastAPI Lifespan 集成

**文件**: `backend/app/main.py`（修改）

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.services.diagnosis.scheduler import get_scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时
    scheduler = await get_scheduler()
    await scheduler.start()

    yield

    # 关闭时
    await scheduler.stop()

app = FastAPI(lifespan=lifespan)
```

---

## 测试策略

### 单元测试

**文件**: `backend/tests/services/diagnosis/test_priority_queue.py`

测试用例：
1. 基本插入和获取
2. 优先级排序（数字越小优先级越高）
3. 队列满时的丢弃策略（低优先级任务被丢弃）
4. 队列满时的替换策略（高优先级任务替换低优先级任务）
5. 任务取消（标记法）
6. 并发插入和获取
7. 队列为空时调用 qsize() 返回 0
8. 取消不存在的 task_id 返回 False
9. 并发 put 和 cancel 同一任务
10. heapify 后堆不变性验证（使用 heapq.heappop 验证顺序）

**文件**: `backend/tests/services/diagnosis/test_scheduler.py`

测试用例：
1. 告警订阅和任务提交
2. 优先级队列排序
3. 并发控制（Semaphore）
4. 超时保护
5. L1 推理成功
6. L1 推理失败（无匹配）
7. L1 未匹配自动升级到 L2（紧急/重要告警）
8. 结果保存到数据库
9. 手动触发诊断

### 集成测试

**文件**: `backend/tests/api/test_diagnosis.py`

测试用例：
1. POST /api/v1/diagnosis/trigger - 成功触发
2. POST /api/v1/diagnosis/trigger - 无权限（非 operator）
3. POST /api/v1/diagnosis/trigger - 限流（超过 10次/分钟）
4. POST /api/v1/diagnosis/trigger - 无效级别
5. POST /api/v1/diagnosis/trigger - 队列满

### 性能测试

**文件**: `backend/test_scheduler_performance.py`

测试场景：
1. 100 个并发告警，验证队列不溢出（应在 10 秒内完成）
2. 1000 个告警连续提交，验证吞吐量（应 >= 50 任务/秒）
3. 混合优先级告警，验证高优先级优先处理（紧急告警平均等待时间 < 1 秒）
4. 长时间运行（1小时），验证内存泄漏（内存增长 < 100 MB）

---

## 依赖关系

### 前置依赖
- Story 24.1: L1 规则引擎（已完成）
- Epic 5: 告警管理（提供 Redis alarm:new 事件）
- Epic 14: PostgreSQL 迁移（提供数据库）

### 后续依赖
- Story 24.5: L2 故障树推理引擎（调度器需调用 L2 引擎）
- Story 24.7: 熔断降级机制（调度器需触发熔断计数器）

---

## 验收检查清单

- [ ] CancellablePriorityQueue 实现并通过单元测试
- [ ] DiagnosisScheduler 实现并通过单元测试
- [ ] 创建 diagnosis_results 表的 Alembic 迁移
- [ ] 在 Alarm 和 Device 模型中添加反向关系
- [ ] 实现 POST /api/v1/diagnosis/trigger API
- [ ] 实现 RBAC 权限控制（operator+）
- [ ] 实现用户级限流（10次/分钟/用户）
- [ ] 在 deps.py 中实现 global_rate_limiter 函数
- [ ] 实现全局限流（30次/分钟/全局）
- [ ] 初始化 fastapi_limiter（在 FastAPI lifespan 中）
- [ ] 订阅 Redis alarm:new 事件
- [ ] 实现 Redis 订阅重连机制（指数退避 + 关闭旧连接）
- [ ] L1 引擎加载失败时拒绝启动调度器
- [ ] L1 推理成功时保存结果
- [ ] L1 未匹配时自动升级到 L2（紧急/重要告警，且无 L2 结果）
- [ ] L2 未匹配时不自动升级到 L3
- [ ] 手动触发时验证设备存在
- [ ] 超时保护（L1: 2s）
- [ ] 并发控制（最多 10 个任务）
- [ ] 队列满时的丢弃/替换策略
- [ ] 优雅关闭（先停止订阅，再等待队列清空）
- [ ] 集成测试通过
- [ ] 性能测试通过（100 并发告警）

---

## FR 追溯

- FR34-4: 诊断调度器与并发控制
- Architecture 18.2: 并发控制

---

## 实施注意事项

1. **Redis 连接管理**: 使用 `app.core.redis_client.get_redis()` 获取 Redis 客户端，避免重复连接
2. **异步数据库**: 使用 `app.core.database.async_session()` 获取异步会话
3. **日志记录**: 所有关键操作（任务提交、推理成功/失败、队列满）都需记录日志
4. **错误处理**: 推理失败时不中断调度器，记录错误并继续处理下一个任务
5. **优雅关闭**: FastAPI lifespan 关闭时需等待队列清空（最多 30 秒）后再取消 worker
6. **WebSocket 推送**: 本 Story 暂不实现 WebSocket 推送，留待后续 Story 补充
7. **L2 引擎占位**: 调度器需预留 L2 引擎调用接口，但 L2 引擎在 Story 24.5 实现
8. **熔断计数器占位**: 超时时需触发熔断计数器，但熔断机制在 Story 24.7 实现
9. **fastapi_limiter 初始化**: 需要在 FastAPI 启动时初始化 fastapi_limiter（需要 Redis 连接），参考 `backend/app/main.py` 中的 lifespan 函数
10. **全局限流实现**: 需要在 `backend/app/api/deps.py` 中实现 `global_rate_limiter` 函数，使用 Redis 计数器实现全局限流
11. **Alembic 迁移命名**: 使用 `alembic revision -m "create diagnosis results"` 命令生成迁移脚本，会自动添加时间戳前缀
12. **模型反向关系**: 必须在 Alarm 和 Device 模型中添加 `diagnosis_results` 反向关系，否则 SQLAlchemy 会报错

---

## 估算工作量

- 开发: 2-3 天
- 测试: 1 天
- 总计: 3-4 天
