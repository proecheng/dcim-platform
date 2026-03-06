"""
诊断结果 Redis 降级存储 - Story 24.7
当 PostgreSQL 不可用时，将诊断结果临时写入 Redis
"""

import json
import logging
import uuid
from datetime import datetime

from app.core.redis_lock import get_redis_client

logger = logging.getLogger(__name__)


class DiagnosisFallbackStore:
    """诊断结果 Redis 降级存储"""

    PENDING_KEY_PREFIX = "diagnosis:pending:"
    PENDING_TTL = 3600  # 1 小时
    RECOVER_BATCH_SIZE = 50  # 每批最多恢复 50 条

    @staticmethod
    async def save_to_redis(data: dict) -> str:
        """
        将诊断结果序列化写入 Redis

        datetime 字段已由调用方转为 ISO 字符串。
        Returns: pending_key
        """
        client = await get_redis_client()
        pending_id = str(uuid.uuid4())
        key = f"{DiagnosisFallbackStore.PENDING_KEY_PREFIX}{pending_id}"
        serialized = json.dumps(data, default=str, ensure_ascii=False)
        await client.set(key, serialized, ex=DiagnosisFallbackStore.PENDING_TTL)
        logger.info("诊断结果已写入 Redis 降级存储: %s", key)
        return key

    @staticmethod
    async def recover_pending() -> int:
        """
        扫描并恢复 pending 诊断结果到 DB（每批最多 50 条）

        Returns: 恢复成功的数量
        """
        from app.services.diagnosis.result_store import DiagnosisResultStore

        client = await get_redis_client()
        keys = []
        async for key in client.scan_iter(
            f"{DiagnosisFallbackStore.PENDING_KEY_PREFIX}*",
            count=DiagnosisFallbackStore.RECOVER_BATCH_SIZE,
        ):
            keys.append(key)
            if len(keys) >= DiagnosisFallbackStore.RECOVER_BATCH_SIZE:
                break

        if not keys:
            return 0

        # datetime 需要还原的字段
        DT_FIELDS = ("start_time", "end_time")

        recovered = 0
        for key in keys:
            raw = await client.get(key)
            if not raw:
                continue
            try:
                data = json.loads(raw)
                # datetime 字段反序列化
                for dt_field in DT_FIELDS:
                    val = data.get(dt_field)
                    if isinstance(val, str) and val != "None":
                        data[dt_field] = datetime.fromisoformat(val)
                    elif val == "None" or val is None:
                        data[dt_field] = None

                session_id, _ = await DiagnosisResultStore.save_complete(**data)
                if session_id == 0:
                    # save_complete 返回 (0,0) 说明 DB 仍不可用，已再次写入 Redis
                    # 删除原始 key 避免下次恢复时重复处理
                    await client.delete(key)
                    logger.warning("恢复时 DB 仍不可用，跳过: %s", key)
                    break  # DB 不可用时停止本批恢复，等下次循环
                await client.delete(key)
                recovered += 1
            except Exception as e:
                logger.warning("恢复 pending 诊断结果失败 %s: %s", key, e)
                break  # 出错时停止本批恢复，避免循环重试

        return recovered
