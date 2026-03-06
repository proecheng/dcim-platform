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
from app.core.redis_lock import get_redis_client
from app.services.diagnosis.priority_queue import CancellablePriorityQueue, PriorityTask
from app.services.diagnosis.l1_engine import L1RuleEngine
from app.services.diagnosis.result_store import DiagnosisResultStore
from app.services.diagnosis.push_service import DiagnosisPushService
from app.services.diagnosis.circuit_breaker import CircuitBreaker
from app.services.diagnosis.fallback_store import DiagnosisFallbackStore
from app.services.diagnosis.annotation_anomaly import AnnotationAnomalyDetector
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
        self._subscriber_task: Optional[asyncio.Task] = None
        self._recovery_task: Optional[asyncio.Task] = None
        self._anomaly_detection_task: Optional[asyncio.Task] = None

        # 熔断器 (Story 24.7)
        self.circuit_breaker = CircuitBreaker(
            on_state_change=self._on_breaker_state_change,
        )


    async def start(self):
        """
        启动调度器
        """
        if self.running:
            logger.warning("Scheduler already running")
            return

        # 清理旧状态（防止重启时状态不一致）
        if self._workers:
            logger.warning("Cleaning up old workers from previous failed start")
            for worker in self._workers:
                worker.cancel()
            await asyncio.gather(*self._workers, return_exceptions=True)
            self._workers.clear()
        if self._subscriber_task:
            self._subscriber_task.cancel()
            try:
                await self._subscriber_task
            except asyncio.CancelledError:
                pass
            self._subscriber_task = None

        self.running = True
        self.redis = await get_redis_client()

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

        # 启动 Redis 订阅（显式存储）
        self._subscriber_task = asyncio.create_task(self._subscribe_alarms())

        # 启动 Redis 降级恢复定时任务 (Story 24.7)
        self._recovery_task = asyncio.create_task(self._recovery_loop())

        # 启动标注偏差检测定时任务 (Story 24.8)
        self._anomaly_detection_task = asyncio.create_task(self._anomaly_detection_loop())

        logger.info("DiagnosisScheduler started")

    async def stop(self):
        """
        停止调度器（优雅关闭）
        """
        logger.info("Stopping scheduler...")
        self.running = False

        # 先取消订阅协程，停止接收新告警
        if self._subscriber_task:
            self._subscriber_task.cancel()
            try:
                await self._subscriber_task
            except asyncio.CancelledError:
                pass

        # 等待队列清空（最多等待 30 秒）
        logger.info("Waiting for queue to drain...")
        for _ in range(30):
            qsize = await self.queue.qsize()
            if qsize == 0:
                break
            await asyncio.sleep(1)

        qsize = await self.queue.qsize()
        if qsize > 0:
            logger.warning(f"Queue not empty after 30s, {qsize} tasks will be lost")

        # 取消恢复任务
        if self._recovery_task:
            self._recovery_task.cancel()
            try:
                await self._recovery_task
            except asyncio.CancelledError:
                pass
            self._recovery_task = None

        # 取消偏差检测任务
        if self._anomaly_detection_task:
            self._anomaly_detection_task.cancel()
            try:
                await self._anomaly_detection_task
            except asyncio.CancelledError:
                pass
            self._anomaly_detection_task = None

        # 取消所有 worker
        for worker in self._workers:
            worker.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        self._subscriber_task = None
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
        执行推理任务（使用 DiagnosisResultStore + DiagnosisPushService）
        含熔断检查 (Story 24.7)
        """
        task_data = task.data

        # 验证 task_data 格式
        if not isinstance(task_data, dict):
            logger.error(f"Invalid task_data type: {type(task_data)}")
            return

        alarm_id = task_data.get("alarm_id")
        device_id = task_data.get("device_id")
        inference_level = task_data.get("inference_level")
        alarm_data = task_data.get("alarm_data")

        # 验证必需字段
        if not inference_level:
            logger.error(f"Missing inference_level in task_data: {task_data}")
            return
        if not isinstance(alarm_data, dict):
            logger.error(f"Invalid alarm_data type: {type(alarm_data)}")
            return

        # 熔断检查 (Story 24.7)
        allowed, degraded = await self.circuit_breaker.allow_request(inference_level)
        original_level = inference_level

        if degraded and inference_level in ("L2", "L3"):
            inference_level = "L1"
            logger.warning(f"Circuit breaker degraded: alarm {alarm_id} {original_level}->L1")

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

            # 记录成功（仅对原始级别 L2/L3 且未降级计数）
            if original_level in ("L2", "L3") and not degraded:
                await self.circuit_breaker.record_success()

            # 计算推理时间
            end_time = datetime.utcnow()
            inference_time_ms = int((end_time - start_time).total_seconds() * 1000)

            # 使用 DiagnosisResultStore 保存结果
            confidence = result.get("confidence")
            if isinstance(confidence, (int, float)):
                if confidence > 1.0:
                    confidence = confidence / 100.0
            else:
                confidence = None

            status = "degraded" if degraded else "success"

            session_id, result_id = await DiagnosisResultStore.save_complete(
                trigger_alarm_id=alarm_id,
                device_id=device_id,
                engine_level=inference_level,
                status=status,
                max_confidence=confidence,
                start_time=start_time,
                end_time=end_time,
                inference_time_ms=inference_time_ms,
                alarm_id=alarm_id,
                diagnosis_level=inference_level,
                matched=result.get("matched", False),
                conclusion=result.get("conclusion"),
                confidence=confidence,
                suggested_actions=result.get("suggested_actions"),
                evidence=result.get("evidence"),
                root_cause=result.get("root_cause"),
                reasoning_path=result.get("reasoning_path"),
                fault_tree_version=result.get("fault_tree_version"),
                error_message=result.get("error"),
                input_data=alarm_data,
                output_data=result,
            )

            # fallback 模式跳过推送 (session_id=0 表示已降级写入 Redis)
            if session_id == 0:
                return

            # 分级推送
            if confidence is not None:
                push_status = await DiagnosisPushService.push_diagnosis_result(
                    session_id=session_id,
                    device_id=device_id,
                    engine_level=inference_level,
                    confidence=confidence,
                    conclusion=result.get("conclusion"),
                    root_cause=result.get("root_cause"),
                    suggested_actions=result.get("suggested_actions"),
                )
                await DiagnosisResultStore.update_push_status(session_id, push_status)

            # 自动升级逻辑（降级时不升级）
            if not degraded and not result.get("matched") and task_data.get("alarm_level") in ["critical", "major"]:
                if inference_level == "L1":
                    async with async_session() as db_session:
                        existing_l2 = await db_session.execute(
                            select(DiagnosisResult).where(
                                DiagnosisResult.alarm_id == alarm_id,
                                DiagnosisResult.diagnosis_level == "L2"
                            )
                        )
                        if existing_l2.scalar_one_or_none() is None:
                            logger.info(f"Alarm {alarm_id} L1 no match, upgrading to L2")
                            task_data["inference_level"] = "L2"
                            priority = ALARM_LEVEL_PRIORITY.get(task_data["alarm_level"], 1)
                            await self.queue.put(priority, f"alarm-{alarm_id}-L2", task_data)
                        else:
                            logger.info(f"Alarm {alarm_id} L1 no match, but L2 result already exists, skipping upgrade")

        except asyncio.TimeoutError:
            logger.error(f"Inference timeout for alarm {alarm_id} (level={inference_level})")
            # 记录超时（仅对原始级别 L2/L3 且未降级计数）
            if original_level in ("L2", "L3") and not degraded:
                await self.circuit_breaker.record_timeout()
            end_time = datetime.utcnow()
            timeout_ms = INFERENCE_TIMEOUT.get(inference_level, 2) * 1000
            try:
                await DiagnosisResultStore.save_complete(
                    trigger_alarm_id=alarm_id,
                    device_id=device_id,
                    engine_level=inference_level,
                    status="timeout",
                    start_time=start_time,
                    end_time=end_time,
                    inference_time_ms=timeout_ms,
                    alarm_id=alarm_id,
                    diagnosis_level=inference_level,
                    matched=False,
                    error_message="Timeout",
                    input_data=alarm_data,
                    output_data={"matched": False, "error": "Timeout"},
                )
            except Exception as save_err:
                logger.error(f"Failed to save timeout result: {save_err}")

        except Exception as e:
            logger.error(f"Inference error for alarm {alarm_id}: {e}", exc_info=True)
            # 记录失败（仅对原始级别 L2/L3 且未降级计数）
            if original_level in ("L2", "L3") and not degraded:
                await self.circuit_breaker.record_failure()
            end_time = datetime.utcnow()
            try:
                await DiagnosisResultStore.save_complete(
                    trigger_alarm_id=alarm_id,
                    device_id=device_id,
                    engine_level=inference_level,
                    status="error",
                    start_time=start_time,
                    end_time=end_time,
                    inference_time_ms=0,
                    alarm_id=alarm_id,
                    diagnosis_level=inference_level,
                    matched=False,
                    error_message=str(e),
                    input_data=alarm_data,
                    output_data={"matched": False, "error": str(e)},
                )
            except Exception as save_err:
                logger.error(f"Failed to save error result: {save_err}")


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

    async def _recovery_loop(self):
        """定时恢复 Redis 中的 pending 诊断结果 (Story 24.7)"""
        # 启动后立即尝试一次恢复（处理重启前遗留数据）
        await asyncio.sleep(5)  # 等待 Redis 连接就绪
        while self.running:
            try:
                recovered = await DiagnosisFallbackStore.recover_pending()
                if recovered > 0:
                    logger.info(f"Recovered {recovered} pending diagnosis results from Redis")
            except Exception as e:
                logger.warning(f"Recovery loop error: {e}")
            await asyncio.sleep(60)

    async def _on_breaker_state_change(self, data: dict):
        """熔断器状态变更回调 -- 推送 WebSocket 告警 (Story 24.7)"""
        try:
            from app.services.websocket import ws_manager
            await ws_manager.broadcast_diagnosis(
                msg_type="system_diagnosis_breaker",
                data=data,
                target_roles=["admin"],
            )
        except Exception as e:
            logger.error(f"Failed to broadcast breaker state change: {e}")

    async def _anomaly_detection_loop(self):
        """定时检测标注偏差 (Story 24.8)"""
        # 启动后等待 10 分钟再开始检测（避免启动时数据不足）
        await asyncio.sleep(600)

        while self.running:
            try:
                # 使用 Redis 分布式锁确保只有一个实例执行
                lock_key = "diagnosis:annotation_anomaly_detection:lock"
                lock_value = str(uuid.uuid4())
                lock_ttl = 300  # 5 分钟锁超时

                # 尝试获取锁
                acquired = await self.redis.set(lock_key, lock_value, nx=True, ex=lock_ttl)

                if acquired:
                    try:
                        async with async_session() as db_session:
                            anomalies = await AnnotationAnomalyDetector.detect_anomalies(db_session)

                            if anomalies:
                                logger.warning(f"Detected {len(anomalies)} annotation anomalies")

                                # 推送 WebSocket 告警给管理员
                                try:
                                    from app.services.websocket import ws_manager
                                    await ws_manager.broadcast_diagnosis(
                                        msg_type="annotation_anomaly_alert",
                                        data={
                                            "anomalies": anomalies,
                                            "detected_at": datetime.now().isoformat(),
                                        },
                                        target_roles=["admin"],
                                    )
                                except Exception as ws_err:
                                    logger.error(f"Failed to broadcast anomaly alert: {ws_err}")

                                # 写入系统内通知表（持久化）
                                try:
                                    from app.models.notification import SystemNotification
                                    notification = SystemNotification(
                                        title="标注偏差告警",
                                        content=f"检测到 {len(anomalies)} 个用户标注率异常",
                                        notification_type="annotation_anomaly",
                                        target_role="admin",
                                        data={"anomalies": anomalies},
                                    )
                                    db_session.add(notification)
                                    await db_session.commit()
                                except Exception as notif_err:
                                    logger.error(f"Failed to save anomaly notification: {notif_err}")
                    finally:
                        # 释放锁
                        script = """
                        if redis.call("get", KEYS[1]) == ARGV[1] then
                            return redis.call("del", KEYS[1])
                        else
                            return 0
                        end
                        """
                        await self.redis.eval(script, 1, lock_key, lock_value)
                else:
                    logger.debug("Anomaly detection lock already held by another instance")

            except Exception as e:
                logger.error(f"Anomaly detection loop error: {e}", exc_info=True)

            # 每小时检测一次
            await asyncio.sleep(3600)


# 全局调度器实例
_scheduler: Optional[DiagnosisScheduler] = None
_scheduler_lock = asyncio.Lock()

async def get_scheduler() -> DiagnosisScheduler:
    """
    获取全局调度器实例（线程安全）
    """
    global _scheduler
    async with _scheduler_lock:
        if _scheduler is None:
            _scheduler = DiagnosisScheduler()
        return _scheduler

