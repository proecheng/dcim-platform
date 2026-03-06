"""
诊断结果分级推送服务 - Story 24.6
根据置信度分级推送诊断结果到前端
"""

import logging
from typing import Optional

from app.services.websocket import ws_manager

logger = logging.getLogger(__name__)


class DiagnosisPushService:
    """诊断结果分级推送服务"""

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
            return "failed"

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
