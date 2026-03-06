"""
诊断结果 Redis 降级存储 - Story 24.7
当 PostgreSQL 不可用时，将诊断结果临时写入 Redis
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Optional, Dict, Any

from app.core.redis_lock import get_redis_client

logger = logging.getLogger(__name__)


def _convert_datetime_to_iso(data: Any) -> Any:
    """递归转换 datetime 对象为 ISO 字符串"""
    if isinstance(data, datetime):
        return data.isoformat()
    elif isinstance(data, dict):
        return {k: _convert_datetime_to_iso(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_convert_datetime_to_iso(item) for item in data]
    else:
        return data


def _convert_iso_to_datetime(data: Any, dt_fields: tuple) -> Any:
    """递归转换 ISO 字符串为 datetime 对象（仅处理指定字段）"""
    if isinstance(data, dict):
        result = {}
        for k, v in data.items():
            if k in dt_fields and isinstance(v, str) and v != "None":
                try:
                    result[k] = datetime.fromisoformat(v)
                except (ValueError, AttributeError):
                    result[k] = None
            elif v == "None" or v is None:
                result[k] = None
            else:
                result[k] = v
        return result
    return data


class DiagnosisFallbackStore:
    """诊断结果 Redis 降级存储"""

    PENDING_KEY_PREFIX = "diagnosis:pending:"
    PENDING_TTL = 3600  # 1 小时
    RECOVER_BATCH_SIZE = 50  # 每批最多恢复 50 条
    TTL_EXPIRING_THRESHOLD = 600  # TTL < 600 秒时写入本地文件
    RECOVERY_LOCK_KEY = "diagnosis:fallback_recovery_lock"
    RECOVERY_LOCK_TTL = 30  # 锁过期时间 30 秒

    @staticmethod
    async def save_to_redis(data: dict, reason: str = "") -> str:
        """
        将诊断结果序列化写入 Redis

        自动检测并转换 datetime 字段为 ISO 字符串（递归处理嵌套字典）。
        添加数据版本号 _version: "1.0"。
        添加降级原因 _fallback_reason。
        Returns: pending_key
        """
        client = await get_redis_client()
        pending_id = str(uuid.uuid4())
        key = f"{DiagnosisFallbackStore.PENDING_KEY_PREFIX}{pending_id}"

        # 添加元数据
        data_with_meta = {
            "_version": "1.0",
            "_fallback_reason": reason,
            **data
        }

        # 自动转换 datetime 字段
        converted_data = _convert_datetime_to_iso(data_with_meta)

        serialized = json.dumps(converted_data, ensure_ascii=False)
        await client.set(key, serialized, ex=DiagnosisFallbackStore.PENDING_TTL)
        logger.info("诊断结果已写入 Redis 降级存储: %s (reason: %s)", key, reason)
        return key

    @staticmethod
    async def recover_pending() -> Dict[str, int]:
        """
        扫描并恢复 pending 诊断结果到 DB（每批最多 50 条）

        Returns: {"success": 成功数量, "failed": 失败数量, "skipped": 跳过数量}
        """
        from app.services.diagnosis.result_store import DiagnosisResultStore

        client = await get_redis_client()

        # 尝试获取分布式锁
        lock_token = str(uuid.uuid4())
        lock_acquired = await client.set(
            DiagnosisFallbackStore.RECOVERY_LOCK_KEY,
            lock_token,
            nx=True,
            ex=DiagnosisFallbackStore.RECOVERY_LOCK_TTL
        )

        if not lock_acquired:
            logger.debug("未获取到恢复任务锁，跳过本次恢复")
            return {"success": 0, "failed": 0, "skipped": 0}

        try:
            keys = []
            async for key in client.scan_iter(
                f"{DiagnosisFallbackStore.PENDING_KEY_PREFIX}*",
                count=DiagnosisFallbackStore.RECOVER_BATCH_SIZE,
            ):
                keys.append(key)
                if len(keys) >= DiagnosisFallbackStore.RECOVER_BATCH_SIZE:
                    break

            if not keys:
                return {"success": 0, "failed": 0, "skipped": 0}

            # datetime 需要还原的字段
            DT_FIELDS = ("start_time", "end_time")

            success_count = 0
            failed_count = 0
            skipped_count = 0

            for key in keys:
                raw = await client.get(key)
                if not raw:
                    continue

                try:
                    data = json.loads(raw)

                    # 检查数据版本号
                    version = data.get("_version")
                    if version != "1.0":
                        logger.warning("数据版本不匹配: %s (key: %s)", version, key)
                        skipped_count += 1
                        continue

                    # 移除元数据字段
                    data.pop("_version", None)
                    data.pop("_fallback_reason", None)

                    # datetime 字段反序列化
                    data = _convert_iso_to_datetime(data, DT_FIELDS)

                    # 尝试写回数据库
                    result = await DiagnosisResultStore.save_complete(**data)

                    if result == (None, None):
                        # DB 仍不可用，保留 key
                        logger.warning("恢复时 DB 仍不可用，保留数据: %s", key)

                        # 检查 TTL 是否即将过期
                        ttl = await client.ttl(key)
                        if ttl > 0 and ttl < DiagnosisFallbackStore.TTL_EXPIRING_THRESHOLD:
                            # 写入本地文件
                            await DiagnosisFallbackStore._save_to_local_file(
                                data, "redis_expired", key
                            )
                            await client.delete(key)
                            logger.warning("Redis key 即将过期，已写入本地文件: %s", key)

                        failed_count += 1
                        continue  # 跳过当前数据，继续处理下一条

                    # 恢复成功，删除 Redis 键
                    await client.delete(key)
                    success_count += 1

                except Exception as e:
                    logger.warning("恢复 pending 诊断结果失败 %s: %s", key, e)
                    failed_count += 1
                    continue  # 跳过当前数据，继续处理下一条

            return {
                "success": success_count,
                "failed": failed_count,
                "skipped": skipped_count
            }

        finally:
            # 释放锁时验证 token
            stored_token = await client.get(DiagnosisFallbackStore.RECOVERY_LOCK_KEY)
            if stored_token:
                # Redis 可能返回 str 或 bytes，统一处理
                stored_token_str = stored_token.decode() if isinstance(stored_token, bytes) else stored_token
                if stored_token_str == lock_token:
                    await client.delete(DiagnosisFallbackStore.RECOVERY_LOCK_KEY)

    @staticmethod
    async def _save_to_local_file(data: dict, reason: str, key: str = "") -> None:
        """
        将降级数据写入本地文件

        Args:
            data: 诊断数据
            reason: 降级原因（redis_unavailable 或 redis_expired）
            key: Redis key（用于日志）
        """
        import os
        from pathlib import Path

        # 确定文件路径
        if reason == "redis_unavailable":
            file_path = "logs/diagnosis_fallback_redis_unavailable.log"
        else:
            file_path = "logs/diagnosis_fallback_redis_expired.log"

        # 确保目录存在
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)

        # 添加元数据
        data_with_meta = {
            "_version": "1.0",
            "_fallback_reason": reason,
            "_redis_key": key,
            "_timestamp": datetime.now().isoformat(),
            **data
        }

        # 转换 datetime
        converted_data = _convert_datetime_to_iso(data_with_meta)

        # 追加写入文件（JSON Lines 格式）
        try:
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(converted_data, ensure_ascii=False) + "\n")
            logger.warning("降级数据已写入本地文件: %s (reason: %s)", file_path, reason)
        except Exception as e:
            logger.error("写入本地文件失败: %s", e)
