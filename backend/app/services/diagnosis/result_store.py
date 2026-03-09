"""
诊断结果存储服务 - Story 24.6
单事务保存 session + result + audit_log，支持审计数据脱敏与大小控制
"""

import json
import logging
import re
from datetime import datetime
from typing import Optional

from sqlalchemy import update

from app.core.database import async_session
from app.models.diagnosis import DiagnosisSession, DiagnosisResult, DiagnosisAuditLog

logger = logging.getLogger(__name__)


class DiagnosisResultStore:
    """诊断结果存储 - 无状态工具类"""

    # 需要脱敏的敏感字段名（使用更精确的模式）
    SENSITIVE_KEYS = {"password", "token", "secret", "api_key", "authorization"}
    # 敏感字段后缀模式（避免误匹配 primary_key, keyboard 等）
    SENSITIVE_SUFFIXES = {"_password", "_token", "_secret", "_key", "_api_key"}
    # 字符串值中的敏感模式
    SENSITIVE_VALUE_PATTERN = re.compile(
        r'(password|token|key|secret|authorization)\s*[:=]\s*\S+(\s+\S+)?|bearer\s+\S+',
        re.IGNORECASE
    )
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
        fault_tree_version_id: Optional[int] = None,  # Story 26.5: A/B 测试版本ID
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
                    fault_tree_version_id=fault_tree_version_id,  # Story 26.5
                )
                session.add(db_result)
                await session.flush()

                # 数据一致性检查（AC2 第二轮审查问题 1）
                if device_id is not None and db_session.device_id is not None:
                    if device_id != db_session.device_id:
                        logger.error(
                            "数据一致性错误: result.device_id=%s != session.device_id=%s",
                            device_id, db_session.device_id
                        )
                        raise ValueError(
                            f"device_id 不一致: result={device_id}, session={db_session.device_id}"
                        )

                if inference_time_ms != db_session.inference_time_ms:
                    logger.warning(
                        "inference_time_ms 不一致: result=%d, session=%d (可能是计算误差)",
                        inference_time_ms, db_session.inference_time_ms
                    )

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

                    # 构建降级数据（保持 datetime 对象，由 save_to_redis 自动转换）
                    fallback_data = {
                        "trigger_alarm_id": trigger_alarm_id,
                        "device_id": device_id,
                        "engine_level": engine_level,
                        "status": status,
                        "max_confidence": max_confidence,
                        "start_time": start_time,  # datetime 对象
                        "end_time": end_time,      # datetime 对象
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
                    }

                    # 记录降级原因
                    fallback_reason = f"{type(e).__name__}: {str(e)}"

                    await DiagnosisFallbackStore.save_to_redis(fallback_data, reason=fallback_reason)
                    logger.warning("诊断结果已降级写入 Redis: alarm_id=%s", trigger_alarm_id)
                    return (None, None)  # 修正：返回 (None, None) 表示降级保存成功

                except Exception as redis_err:
                    logger.critical("Redis 降级写入也失败: %s (原始DB错误: %s)", redis_err, e)
                    # Redis 也失败，尝试写入本地文件
                    try:
                        await DiagnosisFallbackStore._save_to_local_file(
                            fallback_data, "redis_unavailable"
                        )
                        return (None, None)  # 仍返回 (None, None)，表示已降级处理
                    except Exception as file_err:
                        logger.critical("本地文件降级也失败: %s", file_err)
                        raise e  # 抛出原始 DB 异常

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
            # 检查是否为敏感字段（AC2 第二轮审查问题 2）
            key_lower = key.lower()
            is_sensitive = (
                key_lower in DiagnosisResultStore.SENSITIVE_KEYS or
                any(key_lower.endswith(suffix) for suffix in DiagnosisResultStore.SENSITIVE_SUFFIXES)
            )

            if is_sensitive:
                sanitized[key] = "***REDACTED***"
            elif isinstance(value, str):
                # 检查字符串值中的敏感模式（AC2 第二轮审查问题 3）
                sanitized[key] = DiagnosisResultStore._sanitize_string_value(value)
            elif isinstance(value, dict):
                sanitized[key] = DiagnosisResultStore._sanitize_audit_data(value)
            elif isinstance(value, list):
                sanitized[key] = [
                    DiagnosisResultStore._sanitize_audit_data(item)
                    if isinstance(item, dict)
                    else DiagnosisResultStore._sanitize_string_value(item)
                    if isinstance(item, str)
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
    def _sanitize_string_value(value: str) -> str:
        """
        检查并脱敏字符串值中的敏感模式

        例如: "Authorization: Bearer abc123" -> "Authorization: ***REDACTED***"
              "password=secret123" -> "password=***REDACTED***"
        """
        def replace_sensitive(match):
            full = match.group(0)
            # Bearer 模式
            if full.lower().startswith("bearer"):
                return "Bearer ***REDACTED***"
            # 其他 key=value / key: value 模式
            group1 = match.group(1)
            if group1:
                return f"{group1}=***REDACTED***"
            return "***REDACTED***"

        return DiagnosisResultStore.SENSITIVE_VALUE_PATTERN.sub(replace_sensitive, value)

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
