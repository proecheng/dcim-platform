"""
诊断结果分级推送服务 - Story 24.6
根据置信度分级推送诊断结果到前端
"""

import json
import logging
from typing import Optional
from datetime import datetime

from app.services.websocket import ws_manager
from app.core.redis_lock import get_redis_client

logger = logging.getLogger(__name__)


class DiagnosisPushService:
    """诊断结果分级推送服务"""

    RETRY_QUEUE_KEY = "diagnosis:push_retry_queue"
    MAX_RETRY_COUNT = 3
    RETRY_TTL = 86400  # 24 小时

    @staticmethod
    async def push_diagnosis_result(
        *,
        session_id: int,
        device_id: Optional[int] = None,
        device_type: Optional[str] = None,
        engine_level: str,
        confidence: float,
        conclusion: Optional[str] = None,
        root_cause: Optional[str] = None,
        suggested_actions: Optional[list] = None,
    ) -> str:
        """
        根据置信度分级推送诊断结果

        推送规则:
        - confidence > 0.80 → diagnosis_alert（高置信度告警）
        - confidence >= 0.60 → diagnosis_suggestion（建议）
        - confidence < 0.60 → log_only，不推送，返回 "skipped"

        Args:
            session_id: 诊断会话ID
            device_id: 设备ID
            device_type: 设备类型
            engine_level: 推理级别
            confidence: 置信度 (0.0-1.0)
            conclusion: 诊断结论
            root_cause: 根因描述
            suggested_actions: 建议操作列表

        Returns:
            推送状态: "pushed" / "failed" / "skipped"
        """
        push_level = DiagnosisPushService.get_push_level(confidence)

        # 低置信度不推送
        if push_level == "log_only":
            logger.debug(
                "诊断结果置信度较低(%.2f)，跳过推送: session_id=%d",
                confidence,
                session_id,
            )
            return "skipped"

        try:
            # 确定推送类型
            if push_level == "alert":
                push_type = "diagnosis_alert"
            else:
                push_type = "diagnosis_suggestion"

            # 构建推送数据
            push_data = {
                "session_id": session_id,
                "device_id": device_id,
                "device_type": device_type,
                "engine_level": engine_level,
                "confidence": int(confidence * 100),  # 转百分比
                "conclusion": conclusion,
                "root_cause": root_cause,
                "suggested_actions": suggested_actions or [],
            }

            await ws_manager.broadcast_diagnosis(
                msg_type=push_type,
                data=push_data,
                target_roles=["operator", "admin"],
            )

            logger.info(
                "诊断结果已推送: session_id=%d, type=%s, confidence=%d%%",
                session_id,
                push_type,
                int(confidence * 100),
            )
            return "pushed"

        except Exception as e:
            logger.error(
                "诊断结果推送失败: session_id=%d, error=%s",
                session_id,
                e,
            )
            # 推送失败时写入重试队列（AC4 第二轮审查问题 5）
            try:
                await DiagnosisPushService._enqueue_retry(
                    session_id=session_id,
                    device_id=device_id,
                    device_type=device_type,
                    engine_level=engine_level,
                    confidence=confidence,
                    conclusion=conclusion,
                    root_cause=root_cause,
                    suggested_actions=suggested_actions,
                )
            except Exception as retry_err:
                logger.error("写入重试队列失败: %s", retry_err)

            return "failed"

    @staticmethod
    async def _enqueue_retry(
        *,
        session_id: int,
        device_id: Optional[int],
        device_type: Optional[str],
        engine_level: str,
        confidence: float,
        conclusion: Optional[str],
        root_cause: Optional[str],
        suggested_actions: Optional[list],
    ) -> None:
        """将推送失败的数据写入 Redis 重试队列"""
        client = await get_redis_client()

        retry_data = {
            "session_id": session_id,
            "device_id": device_id,
            "device_type": device_type,
            "engine_level": engine_level,
            "confidence": confidence,
            "conclusion": conclusion,
            "root_cause": root_cause,
            "suggested_actions": suggested_actions,
            "retry_count": 0,
            "created_at": datetime.now().isoformat(),
        }

        await client.rpush(DiagnosisPushService.RETRY_QUEUE_KEY, json.dumps(retry_data, ensure_ascii=False))
        logger.info("推送失败数据已写入重试队列: session_id=%d", session_id)

    @staticmethod
    async def process_retry_queue() -> dict:
        """
        处理重试队列（后台任务每 60 秒调用一次）

        Returns:
            {"success": 成功数, "failed": 失败数, "expired": 过期数}
        """
        client = await get_redis_client()
        success_count = 0
        failed_count = 0
        expired_count = 0

        # 批量处理，每次最多 50 条
        batch_size = 50
        for _ in range(batch_size):
            # 从队列左侧弹出一条数据
            raw = await client.lpop(DiagnosisPushService.RETRY_QUEUE_KEY)
            if not raw:
                break

            try:
                data = json.loads(raw)
                retry_count = data.get("retry_count", 0)
                created_at = datetime.fromisoformat(data["created_at"])

                # 检查是否过期（超过 24 小时）
                age_seconds = (datetime.now() - created_at).total_seconds()
                if age_seconds > DiagnosisPushService.RETRY_TTL:
                    logger.warning("重试数据已过期: session_id=%d, age=%.0fs", data["session_id"], age_seconds)
                    expired_count += 1
                    continue

                # 检查重试次数
                if retry_count >= DiagnosisPushService.MAX_RETRY_COUNT:
                    logger.warning("重试次数已达上限: session_id=%d, retry_count=%d", data["session_id"], retry_count)
                    failed_count += 1
                    continue

                # 尝试重新推送
                status = await DiagnosisPushService.push_diagnosis_result(
                    session_id=data["session_id"],
                    device_id=data.get("device_id"),
                    device_type=data.get("device_type"),
                    engine_level=data["engine_level"],
                    confidence=data["confidence"],
                    conclusion=data.get("conclusion"),
                    root_cause=data.get("root_cause"),
                    suggested_actions=data.get("suggested_actions"),
                )

                if status == "pushed":
                    success_count += 1
                    logger.info("重试推送成功: session_id=%d", data["session_id"])
                else:
                    # 推送仍然失败，增加重试计数并重新入队
                    data["retry_count"] = retry_count + 1
                    await client.rpush(DiagnosisPushService.RETRY_QUEUE_KEY, json.dumps(data, ensure_ascii=False))
                    failed_count += 1

            except Exception as e:
                logger.error("处理重试队列数据失败: %s", e)
                failed_count += 1
                continue

        if success_count + failed_count + expired_count > 0:
            logger.info(
                "重试队列处理完成: success=%d, failed=%d, expired=%d", success_count, failed_count, expired_count
            )

        return {"success": success_count, "failed": failed_count, "expired": expired_count}

    @staticmethod
    def get_push_level(confidence: float) -> str:
        """
        根据置信度获取推送级别

        Args:
            confidence: 置信度 (0.0-1.0)

        Returns:
            推送级别: "alert" / "suggestion" / "log_only"
        """
        if confidence > 0.80:
            return "alert"
        elif confidence >= 0.60:
            return "suggestion"
        else:
            return "log_only"
