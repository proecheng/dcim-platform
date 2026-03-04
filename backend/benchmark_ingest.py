"""
ingest_pipeline 性能基准测试

模拟 2830 个点位每 5 秒通过统一入库管道的写入压力。
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import asyncio
import json
import time
import random
import math
import statistics
from datetime import datetime

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, Integer, String, Float, DateTime, text, event
from sqlalchemy.dialects.sqlite import insert as sqlite_insert


# ── 最小化模型定义（不依赖 app 模块）──────────────────────

class Base(DeclarativeBase):
    pass


class PointDataLatest(Base):
    __tablename__ = "point_data_latest"
    id = Column(Integer, primary_key=True, autoincrement=True)
    point_id = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(String(200))
    quality = Column(Integer, default=0)
    timestamp = Column(DateTime)
    gateway_id = Column(String(50))
    updated_at = Column(DateTime, default=datetime.now)


class PointRealtime(Base):
    __tablename__ = "point_realtime"
    point_id = Column(Integer, primary_key=True)
    raw_value = Column(Float)
    value = Column(Float)
    value_text = Column(String(50))
    quality = Column(Integer, default=0)
    status = Column(String(20), default="normal")
    alarm_level = Column(String(20))
    change_count = Column(Integer, default=0)
    last_change_at = Column(DateTime)
    updated_at = Column(DateTime, default=datetime.now)


# ── 配置 ──────────────────────────────────────────────

TOTAL_POINTS = 2830
BATCH_SIZES = [100, 200, 300, 500]
ROUNDS = 5  # 每个批次大小跑 5 轮取平均


# ── 数据生成 ──────────────────────────────────────────

def generate_point_data(n: int, offset: int = 0) -> list[dict]:
    """生成 n 个模拟点位数据"""
    now = datetime.now()
    int(now.timestamp())
    return [
        {
            "point_id": f"DEMO_POINT_{offset + i:04d}",
            "value": str(round(20.0 + 5.0 * math.sin(i * 0.1) + random.uniform(-0.5, 0.5), 2)),
            "quality": 0,
            "timestamp": now,
            "gateway_id": "virtual-gw-demo",
        }
        for i in range(n)
    ]


def generate_realtime_data(n: int) -> list[dict]:
    """生成 n 个 PointRealtime 更新数据"""
    now = datetime.now()
    return [
        {
            "point_id": i + 1,
            "raw_value": round(20.0 + 5.0 * math.sin(i * 0.1) + random.uniform(-0.5, 0.5), 2),
            "value": round(20.0 + 5.0 * math.sin(i * 0.1) + random.uniform(-0.5, 0.5), 2),
            "quality": 0,
            "status": "normal",
            "updated_at": now,
        }
        for i in range(n)
    ]


# ── SQLite WAL 优化 ──────────────────────────────────

def set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA cache_size=-64000")  # 64MB
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


# ── Benchmark 函数 ────────────────────────────────────

async def setup_db(engine):
    """创建表 + 预填充 PointRealtime 行"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    # 预填充 PointRealtime（模拟已有点位）
    async with async_sessionmaker(engine, class_=AsyncSession)() as session:
        now = datetime.now()
        for batch_start in range(0, TOTAL_POINTS, 500):
            batch_end = min(batch_start + 500, TOTAL_POINTS)
            rows = [
                {
                    "point_id": i + 1,
                    "raw_value": 20.0,
                    "value": 20.0,
                    "quality": 0,
                    "status": "normal",
                    "updated_at": now,
                }
                for i in range(batch_start, batch_end)
            ]
            await session.execute(PointRealtime.__table__.insert(), rows)
        await session.commit()
    print(f"  预填充 {TOTAL_POINTS} 行 PointRealtime 完成")


async def bench_bulk_upsert_pdl(session: AsyncSession, data: list[dict]) -> float:
    """测试 PointDataLatest bulk upsert（SQLite INSERT OR REPLACE）"""
    t0 = time.perf_counter()
    stmt = sqlite_insert(PointDataLatest).values(data)
    stmt = stmt.on_conflict_do_update(
        index_elements=["point_id"],
        set_={
            "value": stmt.excluded.value,
            "quality": stmt.excluded.quality,
            "timestamp": stmt.excluded.timestamp,
            "gateway_id": stmt.excluded.gateway_id,
            "updated_at": stmt.excluded.timestamp,
        },
    )
    await session.execute(stmt)
    await session.commit()
    return time.perf_counter() - t0


async def bench_bulk_update_pr(session: AsyncSession, data: list[dict]) -> float:
    """测试 PointRealtime bulk update（逐批 UPDATE ... WHERE point_id IN (...)）"""
    t0 = time.perf_counter()
    # SQLite 不支持 bulk UPDATE with VALUES，用 executemany 模拟
    for row in data:
        await session.execute(
            text(
                "UPDATE point_realtime SET raw_value=:raw_value, value=:value, "
                "quality=:quality, status=:status, updated_at=:updated_at "
                "WHERE point_id=:point_id"
            ),
            row,
        )
    await session.commit()
    return time.perf_counter() - t0


async def bench_bulk_update_pr_batch(session: AsyncSession, data: list[dict]) -> float:
    """测试 PointRealtime 批量 UPDATE（使用 CASE WHEN 单条 SQL）"""
    t0 = time.perf_counter()
    if not data:
        return 0.0

    point_ids = [str(d["point_id"]) for d in data]
    id_list = ",".join(point_ids)

    # 构建 CASE WHEN 语句
    value_cases = " ".join(f"WHEN {d['point_id']} THEN {d['value']}" for d in data)
    raw_cases = " ".join(f"WHEN {d['point_id']} THEN {d['raw_value']}" for d in data)

    sql = f"""
        UPDATE point_realtime SET
            value = CASE point_id {value_cases} END,
            raw_value = CASE point_id {raw_cases} END,
            quality = 0,
            status = 'normal',
            updated_at = datetime('now')
        WHERE point_id IN ({id_list})
    """
    await session.execute(text(sql))
    await session.commit()
    return time.perf_counter() - t0


async def bench_redis_pipeline(n: int) -> float:
    """测试 Redis pipeline 批量写入"""
    try:
        import redis.asyncio as aioredis
        pool = aioredis.from_url("redis://localhost:6379/0", decode_responses=True)
        await pool.ping()
    except Exception as e:
        print(f"  Redis 不可用，跳过: {e}")
        return -1.0

    t0 = time.perf_counter()
    pipe = pool.pipeline()
    now = datetime.now().isoformat()
    for i in range(n):
        key = f"point:{i+1}:latest"
        val = json.dumps({"value": round(20.0 + random.uniform(-5, 5), 2), "ts": now})
        pipe.set(key, val, ex=60)
    await pipe.execute()
    elapsed = time.perf_counter() - t0

    # 清理
    pipe2 = pool.pipeline()
    for i in range(n):
        pipe2.delete(f"point:{i+1}:latest")
    await pipe2.execute()
    await pool.close()

    return elapsed


# ── 主测试流程 ────────────────────────────────────────

async def main():
    print("=" * 70)
    print("ingest_pipeline 性能基准测试")
    print(f"总点位数: {TOTAL_POINTS}, 批次大小: {BATCH_SIZES}, 轮次: {ROUNDS}")
    print("=" * 70)

    # 创建引擎（内存 SQLite，WAL 模式不适用于内存，但测试 IO 用文件）
    engine = create_async_engine(
        "sqlite+aiosqlite:///./benchmark_test.db",
        echo=False,
    )
    event.listen(engine.sync_engine, "connect", set_sqlite_pragma)

    SessionFactory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    await setup_db(engine)

    # ── Test 1: PointDataLatest bulk upsert ──
    print("\n── Test 1: PointDataLatest bulk upsert (INSERT OR REPLACE) ──")
    for batch_size in BATCH_SIZES:
        times = []
        for _ in range(ROUNDS):
            all_data = generate_point_data(TOTAL_POINTS)
            total_time = 0.0
            for start in range(0, TOTAL_POINTS, batch_size):
                batch = all_data[start : start + batch_size]
                async with SessionFactory() as session:
                    t = await bench_bulk_upsert_pdl(session, batch)
                    total_time += t
            times.append(total_time)
        avg = statistics.mean(times)
        std = statistics.stdev(times) if len(times) > 1 else 0
        batches = math.ceil(TOTAL_POINTS / batch_size)
        print(f"  batch={batch_size:>4d} | {batches:>3d} batches | avg={avg:.3f}s ± {std:.3f}s | {'✓ OK' if avg < 5.0 else '✗ TOO SLOW'}")

    # ── Test 2a: PointRealtime 逐行 UPDATE ──
    print("\n── Test 2a: PointRealtime 逐行 UPDATE (executemany) ──")
    for batch_size in BATCH_SIZES[:2]:  # 只测小批次，大批次太慢
        times = []
        for _ in range(ROUNDS):
            all_data = generate_realtime_data(TOTAL_POINTS)
            total_time = 0.0
            for start in range(0, TOTAL_POINTS, batch_size):
                batch = all_data[start : start + batch_size]
                async with SessionFactory() as session:
                    t = await bench_bulk_update_pr(session, batch)
                    total_time += t
            times.append(total_time)
        avg = statistics.mean(times)
        std = statistics.stdev(times) if len(times) > 1 else 0
        print(f"  batch={batch_size:>4d} | avg={avg:.3f}s ± {std:.3f}s | {'✓ OK' if avg < 5.0 else '✗ TOO SLOW'}")

    # ── Test 2b: PointRealtime CASE WHEN 批量 UPDATE ──
    print("\n── Test 2b: PointRealtime CASE WHEN 批量 UPDATE ──")
    for batch_size in BATCH_SIZES:
        times = []
        for _ in range(ROUNDS):
            all_data = generate_realtime_data(TOTAL_POINTS)
            total_time = 0.0
            for start in range(0, TOTAL_POINTS, batch_size):
                batch = all_data[start : start + batch_size]
                async with SessionFactory() as session:
                    t = await bench_bulk_update_pr_batch(session, batch)
                    total_time += t
            times.append(total_time)
        avg = statistics.mean(times)
        std = statistics.stdev(times) if len(times) > 1 else 0
        batches = math.ceil(TOTAL_POINTS / batch_size)
        print(f"  batch={batch_size:>4d} | {batches:>3d} batches | avg={avg:.3f}s ± {std:.3f}s | {'✓ OK' if avg < 5.0 else '✗ TOO SLOW'}")

    # ── Test 3: Redis pipeline ──
    print("\n── Test 3: Redis pipeline 批量写入 ──")
    times = []
    for _ in range(ROUNDS):
        t = await bench_redis_pipeline(TOTAL_POINTS)
        if t < 0:
            break
        times.append(t)
    if times:
        avg = statistics.mean(times)
        std = statistics.stdev(times) if len(times) > 1 else 0
        print(f"  {TOTAL_POINTS} keys | avg={avg:.3f}s ± {std:.3f}s | {'✓ OK' if avg < 1.0 else '✗ TOO SLOW'}")

    # ── Test 4: 综合管道（PDL upsert + PR CASE WHEN update，单事务）──
    print("\n── Test 4: 综合管道 (PDL + PR 单事务) ──")
    best_batch = 300  # 用 300 作为推荐批次
    times = []
    for _ in range(ROUNDS):
        pdl_data = generate_point_data(TOTAL_POINTS)
        pr_data = generate_realtime_data(TOTAL_POINTS)
        total_time = 0.0
        for start in range(0, TOTAL_POINTS, best_batch):
            end = min(start + best_batch, TOTAL_POINTS)
            pdl_batch = pdl_data[start:end]
            pr_batch = pr_data[start:end]

            t0 = time.perf_counter()
            async with SessionFactory() as session:
                # PDL upsert
                stmt = sqlite_insert(PointDataLatest).values(pdl_batch)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["point_id"],
                    set_={
                        "value": stmt.excluded.value,
                        "quality": stmt.excluded.quality,
                        "timestamp": stmt.excluded.timestamp,
                        "gateway_id": stmt.excluded.gateway_id,
                        "updated_at": stmt.excluded.timestamp,
                    },
                )
                await session.execute(stmt)

                # PR CASE WHEN update
                if pr_batch:
                    point_ids = [str(d["point_id"]) for d in pr_batch]
                    id_list = ",".join(point_ids)
                    value_cases = " ".join(f"WHEN {d['point_id']} THEN {d['value']}" for d in pr_batch)
                    raw_cases = " ".join(f"WHEN {d['point_id']} THEN {d['raw_value']}" for d in pr_batch)
                    sql = f"""
                        UPDATE point_realtime SET
                            value = CASE point_id {value_cases} END,
                            raw_value = CASE point_id {raw_cases} END,
                            quality = 0, status = 'normal', updated_at = datetime('now')
                        WHERE point_id IN ({id_list})
                    """
                    await session.execute(text(sql))

                await session.commit()
            total_time += time.perf_counter() - t0
        times.append(total_time)

    avg = statistics.mean(times)
    std = statistics.stdev(times) if len(times) > 1 else 0
    batches = math.ceil(TOTAL_POINTS / best_batch)
    print(f"  batch={best_batch} | {batches} batches | avg={avg:.3f}s ± {std:.3f}s")
    print(f"  5秒预算余量: {5.0 - avg:.3f}s (告警判定+Redis+WebSocket)")
    if avg < 3.0:
        print("  ✓ DB 写入在 3 秒内完成，留 2 秒给告警+Redis+WS，方案可行")
    elif avg < 5.0:
        print("  ⚠ DB 写入接近 5 秒，需要优化批次大小或减少 PDU 数量")
    else:
        print("  ✗ DB 写入超过 5 秒，需要减少点位数量或换 PostgreSQL")

    # 清理
    import os
    await engine.dispose()
    try:
        os.remove("benchmark_test.db")
        os.remove("benchmark_test.db-wal")
        os.remove("benchmark_test.db-shm")
    except FileNotFoundError:
        pass

    print("\n" + "=" * 70)
    print("基准测试完成")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
