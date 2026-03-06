import asyncio
import json
import logging
import uuid
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
from app.models.device import Device

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
            pubsub = None
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
                if pubsub:
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

