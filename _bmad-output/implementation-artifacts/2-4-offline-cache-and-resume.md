# Story 2.4: 离线缓存与断点续传

Status: done

## Story

As a 运维工程师,
I want 网关在服务器断开时自动缓存数据,
so that 网络恢复后数据不丢失。

## Acceptance Criteria (验收标准)

1. **AC-1: 本地缓存写入** — `OfflineCache` 类使用 aiosqlite 管理本地 SQLite `upload_queue` 表，提供 `enqueue(payload)` 方法将采集数据写入缓存
2. **AC-2: 批量上传** — `flush_batch(publish_fn, batch_size=100)` 方法按时间戳顺序取出未上传记录，逐批通过 publish_fn 上传，成功后标记 uploaded=True
3. **AC-3: 自动清理** — `cleanup(retention_hours=72)` 方法删除已上传且超过 72 小时的记录
4. **AC-4: 存储空间管理** — `check_storage()` 方法检查磁盘剩余空间，<10% 时先删最旧已上传记录，仍不足则覆盖最旧未上传记录并记录告警
5. **AC-5: 统计信息** — `get_stats()` 返回缓存统计：pending_count（待上传）、uploaded_count（已上传）、total_count
6. **AC-6: 生命周期管理** — `open()` 创建/打开 SQLite 数据库并建表，`close()` 关闭连接

## Tasks / Subtasks (任务分解)

- [ ] Task 1: OfflineCache 核心类 (AC: #1, #6)
  - [ ] 1.1 实现 `gateway/cache.py` — `OfflineCache` 类
  - [ ] 1.2 `open(db_path)` 方法：创建 aiosqlite 连接，建 upload_queue 表（id, timestamp, topic, payload, uploaded, created_at）
  - [ ] 1.3 `close()` 方法：关闭连接
  - [ ] 1.4 `enqueue(topic, payload)` 方法：插入一条待上传记录

- [ ] Task 2: 批量上传 (AC: #2)
  - [ ] 2.1 `flush_batch(publish_fn, batch_size=100)` 方法：查询 uploaded=0 最早 batch_size 条，逐条调用 publish_fn(topic, payload)，成功后标记 uploaded=1
  - [ ] 2.2 返回成功上传的条数
  - [ ] 2.3 单条上传失败时停止当前批次（保证顺序性）

- [ ] Task 3: 自动清理 (AC: #3)
  - [ ] 3.1 `cleanup(retention_hours=72)` 方法：删除 uploaded=1 且 created_at < now - retention_hours 的记录
  - [ ] 3.2 返回删除的条数

- [ ] Task 4: 存储空间管理 (AC: #4)
  - [ ] 4.1 `check_storage(min_free_pct=10.0)` 方法：使用 shutil.disk_usage 检查磁盘剩余百分比
  - [ ] 4.2 剩余 < min_free_pct 时，先删最旧已上传记录（最多 1000 条）
  - [ ] 4.3 删除后仍不足，删最旧未上传记录（最多 1000 条），返回 data_loss=True

- [ ] Task 5: 统计信息 (AC: #5)
  - [ ] 5.1 `get_stats()` 方法：返回 dict（pending_count, uploaded_count, total_count）

- [ ] Task 6: 单元测试 (AC: 全部)
  - [ ] 6.1 测试 open/close — 创建数据库和表
  - [ ] 6.2 测试 enqueue — 插入记录，验证字段
  - [ ] 6.3 测试 flush_batch — 成功上传标记 uploaded=1
  - [ ] 6.4 测试 flush_batch — 上传失败时停止批次
  - [ ] 6.5 测试 flush_batch — 空队列返回 0
  - [ ] 6.6 测试 cleanup — 删除过期已上传记录
  - [ ] 6.7 测试 cleanup — 不删除未过期或未上传记录
  - [ ] 6.8 测试 get_stats — 返回正确计数
  - [ ] 6.9 测试 check_storage — 空间充足时不删除
  - [ ] 6.10 测试 check_storage — 空间不足时删除已上传记录

## Dev Notes (开发指南)

### 1. 文件位置

```
gateway/cache.py                           # 修改 — 实现 OfflineCache
backend/tests/test_offline_cache.py        # 新建 — 单元测试
```

### 2. upload_queue 表结构

```sql
CREATE TABLE IF NOT EXISTS upload_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    topic TEXT NOT NULL,
    payload TEXT NOT NULL,
    uploaded INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS ix_upload_queue_uploaded ON upload_queue(uploaded, id);
```

### 3. OfflineCache 核心实现

```python
# gateway/cache.py

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
        """批量上传缓存数据，返回成功上传条数"""
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
        """清理过期已上传记录"""
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
        db_dir = str(Path(self._db_path).parent or ".")
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
```

### 4. 关键约束

- **aiosqlite 可选**: try/except ImportError，未安装时 open() 抛出 RuntimeError
- **顺序性**: flush_batch 按 id 顺序上传，单条失败时停止整个批次
- **原子性**: 每条上传成功后立即标记 uploaded=1，最后统一 commit
- **存储管理**: 先删已上传，再删未上传，data_loss 标记数据丢失
- **时间戳**: upload_queue.timestamp 用 time.time()（Unix epoch float），created_at 用 SQLite datetime 函数
- **测试**: 使用临时文件路径（tempfile），测试后清理
- **不依赖 psutil**: 使用 shutil.disk_usage 检查磁盘空间（标准库）

### 5. 测试策略

- 使用 tempfile.mktemp() 创建临时 SQLite 文件
- 测试后删除临时文件
- flush_batch 测试：mock publish_fn（AsyncMock）
- check_storage 测试：mock shutil.disk_usage 返回不同空间值
- 所有测试使用 async/await

### Project Structure Notes

- `gateway/cache.py` — 修改（从 stub 实现）
- 测试文件放在 `backend/tests/test_offline_cache.py`（利用 pytest.ini 的 pythonpath=..）

### References

- [Source: architecture.md#10.4] 断点续传机制 — upload_queue 表结构
- [Source: epics.md#Story 2.4] Acceptance Criteria
- [Source: architecture.md#2.3] 网关内部架构 — cache.py

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

