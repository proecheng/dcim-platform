"""SQLite 本地缓存 + 断点续传。实现 Story: 2.4"""
import logging
import shutil
import time
from pathlib import Path
from typing import Any, Callable, Coroutine, Optional

logger = logging.getLogger(__name__)

# aiosqlite 可选依赖
try:
    import aiosqlite
    _HAS_AIOSQLITE = True
except ImportError:
    _HAS_AIOSQLITE = False
    logger.warning("aiosqlite 未安装，离线缓存不可用")


class OfflineCache:
    """网关离线缓存 — SQLite upload_queue 断点续传"""

    def __init__(self, db_path: str = "upload_cache.db") -> None:
        self._db_path = db_path
        self._db: Optional[Any] = None  # aiosqlite.Connection

    async def open(self) -> None:
        """打开数据库连接并建表"""
        if not _HAS_AIOSQLITE:
            raise RuntimeError("aiosqlite 未安装")
        self._db = await aiosqlite.connect(self._db_path)
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS upload_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                topic TEXT NOT NULL,
                payload TEXT NOT NULL,
                uploaded INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now', 'localtime'))
            )
        """)
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS ix_upload_queue_uploaded
            ON upload_queue(uploaded, id)
        """)
        await self._db.commit()
        logger.info("离线缓存已打开: %s", self._db_path)

    async def close(self) -> None:
        """关闭数据库连接"""
        if self._db:
            await self._db.close()
            self._db = None
        logger.info("离线缓存已关闭")

    async def enqueue(self, topic: str, payload: str) -> None:
        """写入一条待上传记录"""
        if not self._db:
            raise RuntimeError("缓存未打开")
        await self._db.execute(
            "INSERT INTO upload_queue (timestamp, topic, payload) VALUES (?, ?, ?)",
            (time.time(), topic, payload),
        )
        await self._db.commit()

    async def flush_batch(
        self,
        publish_fn: Callable[[str, str], Coroutine],
        batch_size: int = 100,
    ) -> int:
        """批量上传缓存数据，返回成功上传条数

        按 id 顺序逐条上传，单条失败时停止当前批次（保证顺序性）。
        """
        if not self._db:
            raise RuntimeError("缓存未打开")

        cursor = await self._db.execute(
            "SELECT id, topic, payload FROM upload_queue WHERE uploaded = 0 ORDER BY id LIMIT ?",
            (batch_size,),
        )
        rows = await cursor.fetchall()

        if not rows:
            return 0

        uploaded_count = 0
        for row_id, topic, payload in rows:
            try:
                await publish_fn(topic, payload)
                await self._db.execute(
                    "UPDATE upload_queue SET uploaded = 1 WHERE id = ?", (row_id,)
                )
                uploaded_count += 1
            except Exception:
                logger.warning("缓存上传失败，停止当前批次 (已上传 %d 条)", uploaded_count)
                break

        await self._db.commit()
        if uploaded_count:
            logger.info("缓存批量上传: %d/%d 条", uploaded_count, len(rows))
        return uploaded_count

    async def cleanup(self, retention_hours: int = 72) -> int:
        """清理过期已上传记录，返回删除条数"""
        if not self._db:
            raise RuntimeError("缓存未打开")
        cutoff = time.time() - retention_hours * 3600
        cursor = await self._db.execute(
            "DELETE FROM upload_queue WHERE uploaded = 1 AND timestamp < ?",
            (cutoff,),
        )
        await self._db.commit()
        count = cursor.rowcount
        if count:
            logger.info("清理过期缓存: %d 条", count)
        return count

    async def check_storage(self, min_free_pct: float = 10.0) -> dict:
        """检查存储空间，不足时清理

        Returns:
            {"free_pct": float, "cleaned_uploaded": int, "cleaned_pending": int, "data_loss": bool}
        """
        db_dir = str(Path(self._db_path).resolve().parent)
        total, used, free = shutil.disk_usage(db_dir)
        free_pct = (free / total) * 100 if total > 0 else 100.0

        result = {
            "free_pct": round(free_pct, 1),
            "cleaned_uploaded": 0,
            "cleaned_pending": 0,
            "data_loss": False,
        }

        if free_pct >= min_free_pct or not self._db:
            return result

        # 先删最旧已上传记录
        cursor = await self._db.execute(
            "DELETE FROM upload_queue WHERE id IN "
            "(SELECT id FROM upload_queue WHERE uploaded = 1 ORDER BY id LIMIT 1000)"
        )
        await self._db.commit()
        result["cleaned_uploaded"] = cursor.rowcount
        logger.warning("存储空间不足 (%.1f%%)，清理已上传记录: %d 条", free_pct, cursor.rowcount)

        # 重新检查
        total, used, free = shutil.disk_usage(db_dir)
        free_pct = (free / total) * 100 if total > 0 else 100.0
        result["free_pct"] = round(free_pct, 1)

        if free_pct >= min_free_pct:
            return result

        # 仍不足，删最旧未上传记录
        cursor = await self._db.execute(
            "DELETE FROM upload_queue WHERE id IN "
            "(SELECT id FROM upload_queue WHERE uploaded = 0 ORDER BY id LIMIT 1000)"
        )
        await self._db.commit()
        result["cleaned_pending"] = cursor.rowcount
        result["data_loss"] = cursor.rowcount > 0
        if result["data_loss"]:
            logger.error("存储空间严重不足，丢弃未上传数据: %d 条", cursor.rowcount)

        return result

    async def get_stats(self) -> dict:
        """获取缓存统计"""
        if not self._db:
            raise RuntimeError("缓存未打开")
        cursor = await self._db.execute(
            "SELECT uploaded, COUNT(*) FROM upload_queue GROUP BY uploaded"
        )
        rows = await cursor.fetchall()
        stats = {"pending_count": 0, "uploaded_count": 0, "total_count": 0}
        for uploaded, count in rows:
            if uploaded == 0:
                stats["pending_count"] = count
            else:
                stats["uploaded_count"] = count
            stats["total_count"] += count
        return stats
