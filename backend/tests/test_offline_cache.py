"""离线缓存测试 — Story 2.4"""

import os
import tempfile
import time
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from gateway.cache import OfflineCache


@pytest_asyncio.fixture
async def cache():
    """创建临时缓存实例"""
    db_path = tempfile.mktemp(suffix=".db")
    c = OfflineCache(db_path=db_path)
    await c.open()
    yield c
    await c.close()
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.mark.asyncio
async def test_open_close():
    """打开创建数据库文件，关闭后 _db 为 None"""
    db_path = tempfile.mktemp(suffix=".db")
    c = OfflineCache(db_path=db_path)
    await c.open()
    assert c._db is not None
    assert os.path.exists(db_path)
    await c.close()
    assert c._db is None
    os.unlink(db_path)


@pytest.mark.asyncio
async def test_enqueue(cache):
    """写入记录后 pending_count 增加"""
    await cache.enqueue("dcim/1/gw/gw-001/data", '{"points": []}')
    stats = await cache.get_stats()
    assert stats["pending_count"] == 1
    assert stats["total_count"] == 1


@pytest.mark.asyncio
async def test_flush_batch_success(cache):
    """全部上传成功"""
    for i in range(3):
        await cache.enqueue("topic", f"payload-{i}")
    publish_fn = AsyncMock()
    count = await cache.flush_batch(publish_fn)
    assert count == 3
    assert publish_fn.call_count == 3
    stats = await cache.get_stats()
    assert stats["pending_count"] == 0
    assert stats["uploaded_count"] == 3


@pytest.mark.asyncio
async def test_flush_batch_partial_failure(cache):
    """第 2 条失败时停止，仅上传 1 条"""
    for i in range(3):
        await cache.enqueue("topic", f"payload-{i}")
    publish_fn = AsyncMock(side_effect=[None, Exception("fail"), None])
    count = await cache.flush_batch(publish_fn)
    assert count == 1
    stats = await cache.get_stats()
    assert stats["pending_count"] == 2
    assert stats["uploaded_count"] == 1


@pytest.mark.asyncio
async def test_flush_batch_empty(cache):
    """空队列返回 0"""
    publish_fn = AsyncMock()
    count = await cache.flush_batch(publish_fn)
    assert count == 0
    assert publish_fn.call_count == 0


@pytest.mark.asyncio
async def test_cleanup_expired(cache):
    """清理过期已上传记录"""
    old_ts = time.time() - 73 * 3600  # 73 小时前
    await cache._db.execute(
        "INSERT INTO upload_queue (timestamp, topic, payload, uploaded) VALUES (?, ?, ?, 1)",
        (old_ts, "topic", "old-payload"),
    )
    await cache._db.commit()
    count = await cache.cleanup(retention_hours=72)
    assert count == 1
    stats = await cache.get_stats()
    assert stats["total_count"] == 0


@pytest.mark.asyncio
async def test_cleanup_keeps_recent(cache):
    """近期已上传记录不被清理"""
    await cache.enqueue("topic", "payload")
    await cache._db.execute("UPDATE upload_queue SET uploaded = 1")
    await cache._db.commit()
    count = await cache.cleanup(retention_hours=72)
    assert count == 0
    stats = await cache.get_stats()
    assert stats["uploaded_count"] == 1


@pytest.mark.asyncio
async def test_get_stats(cache):
    """混合数据统计正确"""
    await cache.enqueue("t1", "p1")
    await cache.enqueue("t2", "p2")
    await cache._db.execute("UPDATE upload_queue SET uploaded = 1 WHERE id = 1")
    await cache._db.commit()
    stats = await cache.get_stats()
    assert stats["pending_count"] == 1
    assert stats["uploaded_count"] == 1
    assert stats["total_count"] == 2


@pytest.mark.asyncio
@patch("gateway.cache.shutil.disk_usage")
async def test_check_storage_sufficient(mock_disk, cache):
    """磁盘空间充足时不清理"""
    mock_disk.return_value = (100_000_000, 50_000_000, 50_000_000)  # 50% free
    result = await cache.check_storage(min_free_pct=10.0)
    assert result["free_pct"] == 50.0
    assert result["cleaned_uploaded"] == 0
    assert result["data_loss"] is False


@pytest.mark.asyncio
@patch("gateway.cache.shutil.disk_usage")
async def test_check_storage_low_cleans_uploaded(mock_disk, cache):
    """磁盘空间不足时清理已上传记录"""
    for i in range(5):
        await cache.enqueue("topic", f"payload-{i}")
    await cache._db.execute("UPDATE upload_queue SET uploaded = 1")
    await cache._db.commit()

    # 第一次: 空间不足, 第二次(清理后): 空间充足
    mock_disk.side_effect = [
        (100_000_000, 95_000_000, 5_000_000),  # 5% free
        (100_000_000, 85_000_000, 15_000_000),  # 15% free after cleanup
    ]
    result = await cache.check_storage(min_free_pct=10.0)
    assert result["cleaned_uploaded"] == 5
    assert result["data_loss"] is False
