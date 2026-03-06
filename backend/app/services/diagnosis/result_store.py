"""
诊断结果存储服务 - Story 24.6
单事务保存 session + result + audit_log，支持审计数据脱敏与大小控制
"""

import json
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import update

from app.core.database import async_session
from app.models.diagnosis import DiagnosisSession, DiagnosisResult, DiagnosisAuditLog

logger = logging.getLogger(__name__)


class DiagnosisResultStore:
    """诊断结果存储 - 无状态工具类"""

    # 需要脱敏的敏感字段名
    SENSITIVE_KEYS = {"password", "token", "secret", "api_key", "authorization"}
    # 审计数据最大大小 64KB
    MAX_AUDIT_SIZE = 64 * 1024

    @staticmethod
    async def save_complete(
        *,
        trigger_alarm_id: Optional[int] = None,
        device_id: Optional[int] = None,
        engine_level: str,
        status: str = "success",
        max_confidence: Optional[float] = None,
        start_time: datetime,
        end_time: Optional[datetime] = None,
        inference_time_ms: int = 0,
        # result 字段
        alarm_id: Optional[int] = None,
        alarm_no: Optional[str] = None,
        rule_id: Optional[int] = None,
        rule_code: Optional[str] = None,
        device_type: Optional[str] = None,
        zone: Optional[str] = None,
        causes: Optional[list] = None,
        diagnosis_level: Optional[str] = None,
        matched: Optional[bool] = None,
        conclusion: Optional[str] = None,
        confidence: Optional[float] = None,
        suggested_actions: Optional[list] = None,
        evidence: Optional[dict] = None,
        root_cause: Optional[str] = None,
        reasoning_path: Optional[list] = None,
        fault_tree_version: Optional[str] = None,
        error_message: Optional[str] = None,
        # audit 字段
        input_data: Optional[dict] = None,
        output_data: Optional[dict] = None,
        push_status: str = "skipped",
    ) -> tuple[int, int]:
        """
        单事务保存诊断会话 + 结果 + 审计日志

        Returns:
            (session_id, result_id) 元组
        """
        async with async_session() as session:
            try:
                # 1. 创建诊断会话
                db_session = DiagnosisSession(
                    trigger_alarm_id=trigger_alarm_id,
                    device_id=device_id,
                    engine_level=engine_level,
                    status=status,
                    push_status=push_status,
                    max_confidence=max_confidence,
                    start_time=start_time,
                    end_time=end_time,
                    inference_time_ms=inference_time_ms,
                )
                session.add(db_session)
                await session.flush()  # 获取 session.id

                # 2. 创建诊断结果
                db_result = DiagnosisResult(
                    alarm_id=alarm_id,
                    alarm_no=alarm_no,
                    rule_id=rule_id,
                    rule_code=rule_code,
                    device_id=device_id,
                    device_type=device_type,
                    zone=zone,
                    causes=causes,
                    diagnosis_level=diagnosis_level or engine_level,
                    matched=matched,
                    conclusion=conclusion,
                    confidence=confidence,
                    suggested_actions=suggested_actions,
                    evidence=evidence,
                    inference_time_ms=inference_time_ms,
                    error_message=error_message,
                    session_id=db_session.id,
                    root_cause=root_cause,
                    reasoning_path=reasoning_path,
                    fault_tree_version=fault_tree_version,
                )
                session.add(db_result)
                await session.flush()

                # 3. 创建审计日志（脱敏处理）
                sanitized_input = DiagnosisResultStore._sanitize_audit_data(
                    input_data or {}
                )
                sanitized_output = DiagnosisResultStore._sanitize_audit_data(
                    output_data or {}
                )

                db_audit = DiagnosisAuditLog(
                    session_id=db_session.id,
                    input_data=sanitized_input,
                    output_data=sanitized_output,
                    engine_level=engine_level,
                    inference_time_ms=inference_time_ms,
                    fault_tree_version=fault_tree_version,
                )
                session.add(db_audit)

                await session.commit()

                logger.info(
                    "诊断结果保存成功: session_id=%d, result_id=%d, engine=%s",
                    db_session.id,
                    db_result.id,
                    engine_level,
                )
                return db_session.id, db_result.id

            except Exception as e:
                await session.rollback()
                logger.error("诊断结果保存失败: %s", e)
                # DB 故障降级写入 Redis (Story 24.7)
                try:
                    from app.services.diagnosis.fallback_store import DiagnosisFallbackStore
                    await DiagnosisFallbackStore.save_to_redis({
                        "trigger_alarm_id": trigger_alarm_id,
                        "device_id": device_id,
                        "engine_level": engine_level,
                        "status": status,
                        "max_confidence": max_confidence,
                        "start_time": start_time.isoformat() if start_time else None,
                        "end_time": end_time.isoformat() if end_time else None,
                        "inference_time_ms": inference_time_ms,
                        "alarm_id": alarm_id,
                        "alarm_no": alarm_no,
                        "rule_id": rule_id,
                        "rule_code": rule_code,
                        "device_type": device_type,
                        "zone": zone,
                        "causes": causes,
                        "diagnosis_level": diagnosis_level,
                        "matched": matched,
                        "conclusion": conclusion,
                        "confidence": confidence,
                        "suggested_actions": suggested_actions,
                        "evidence": evidence,
                        "root_cause": root_cause,
                        "reasoning_path": reasoning_path,
                        "fault_tree_version": fault_tree_version,
                        "error_message": error_message,
                        "input_data": input_data,
                        "output_data": output_data,
                        "push_status": push_status,
                    })
                    logger.warning("诊断结果已降级写入 Redis: alarm_id=%s", trigger_alarm_id)
                    return (0, 0)  # 占位 ID，不 raise，避免 scheduler 重复保存
                except Exception as redis_err:
                    logger.critical("Redis 降级写入也失败: %s (原始DB错误: %s)", redis_err, e)
                    raise e  # 抛出原始 DB 异常，而非 Redis 异常

    @staticmethod
    async def update_push_status(session_id: int, push_status: str) -> None:
        """更新诊断会话的推送状态"""
        async with async_session() as session:
            try:
                stmt = (
                    update(DiagnosisSession)
                    .where(DiagnosisSession.id == session_id)
                    .values(push_status=push_status)
                )
                await session.execute(stmt)
                await session.commit()
                logger.debug("推送状态已更新: session_id=%d, status=%s", session_id, push_status)
            except Exception as e:
                await session.rollback()
                logger.error("更新推送状态失败: session_id=%d, %s", session_id, e)
                raise

    @staticmethod
    def _sanitize_audit_data(data: dict) -> dict:
        """
        递归移除敏感字段，并控制数据大小

        Args:
            data: 原始数据字典

        Returns:
            脱敏后的数据字典
        """
        if not isinstance(data, dict):
            return data

        sanitized = {}
        for key, value in data.items():
            # 检查是否为敏感字段
            if key.lower() in DiagnosisResultStore.SENSITIVE_KEYS:
                sanitized[key] = "***REDACTED***"
            elif isinstance(value, dict):
                sanitized[key] = DiagnosisResultStore._sanitize_audit_data(value)
            elif isinstance(value, list):
                sanitized[key] = [
                    DiagnosisResultStore._sanitize_audit_data(item)
                    if isinstance(item, dict)
                    else item
                    for item in value
                ]
            else:
                sanitized[key] = value

        # 大小控制
        return DiagnosisResultStore._truncate_to_size(
            sanitized, DiagnosisResultStore.MAX_AUDIT_SIZE
        )

    @staticmethod
    def _truncate_to_size(data: dict, max_size: int) -> dict:
        """
        字段级裁剪，确保序列化后不超过 max_size

        逐个移除最大的字段值，直到总大小满足限制
        """
        serialized = json.dumps(data, ensure_ascii=False, default=str)
        if len(serialized.encode("utf-8")) <= max_size:
            return data

        # 按值序列化后的大小降序排列字段
        field_sizes = []
        for key, value in data.items():
            val_str = json.dumps(value, ensure_ascii=False, default=str)
            field_sizes.append((key, len(val_str.encode("utf-8"))))

        field_sizes.sort(key=lambda x: x[1], reverse=True)

        # 逐个截断最大字段
        result = dict(data)
        result["_truncated"] = True
        for key, _ in field_sizes:
            if key == "_truncated":
                continue
            result[key] = "[TRUNCATED]"
            serialized = json.dumps(result, ensure_ascii=False, default=str)
            if len(serialized.encode("utf-8")) <= max_size:
                break

        return result
