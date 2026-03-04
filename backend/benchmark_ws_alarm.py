"""
WebSocket broadcast + alarm_engine.evaluate() benchmark

Tests:
  1. alarm_engine.evaluate() - 2830 calls (pure in-memory threshold check)
  2. JSON serialization - 2830 point payloads for WebSocket broadcast
  3. Simulated WebSocket broadcast - send_json to N mock clients
"""
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import asyncio
import json
import math
import random
import statistics
import time
from dataclasses import dataclass
from typing import Dict, List
from collections import defaultdict
from datetime import datetime


# ── Minimal alarm engine replica (no DB dependency) ──────────

@dataclass
class ThresholdCache:
    id: int
    point_id: int
    threshold_type: str
    threshold_value: float
    alarm_level: str
    alarm_message: str
    delay_seconds: int
    dead_band: float
    priority: int


@dataclass
class EvaluateResult:
    threshold_id: int
    threshold_type: str
    threshold_value: float
    alarm_level: str
    alarm_message: str


class AlarmEngineBench:
    """Minimal alarm engine for benchmarking evaluate() throughput"""

    def __init__(self):
        self._thresholds: Dict[int, List[ThresholdCache]] = defaultdict(list)
        self._prev_values: Dict[int, float] = {}
        self._last_alarm_time: Dict[tuple, float] = {}
        self.STORM_WINDOW = 60

    def load_mock_thresholds(self, n_points: int):
        """Pre-load thresholds for n points (2 thresholds per point: high + low)"""
        for i in range(1, n_points + 1):
            self._thresholds[i] = [
                ThresholdCache(
                    id=i * 2 - 1, point_id=i, threshold_type="high",
                    threshold_value=45.0, alarm_level="major",
                    alarm_message=f"Point {i} high alarm",
                    delay_seconds=0, dead_band=0.5, priority=1,
                ),
                ThresholdCache(
                    id=i * 2, point_id=i, threshold_type="low",
                    threshold_value=5.0, alarm_level="minor",
                    alarm_message=f"Point {i} low alarm",
                    delay_seconds=0, dead_band=0.5, priority=0,
                ),
            ]

    def evaluate(self, point_id: int, value: float) -> List[EvaluateResult]:
        """Replicate core evaluate logic: threshold comparison + storm suppression"""
        results = []
        thresholds = self._thresholds.get(point_id)
        if not thresholds:
            return results

        now = time.time()
        for tc in thresholds:
            triggered = False
            if tc.threshold_type == "high" and value > tc.threshold_value:
                triggered = True
            elif tc.threshold_type == "low" and value < tc.threshold_value:
                triggered = True

            if triggered:
                # Storm suppression check
                key = (point_id, tc.id)
                last = self._last_alarm_time.get(key, 0)
                if now - last >= self.STORM_WINDOW:
                    self._last_alarm_time[key] = now
                    results.append(EvaluateResult(
                        threshold_id=tc.id,
                        threshold_type=tc.threshold_type,
                        threshold_value=tc.threshold_value,
                        alarm_level=tc.alarm_level,
                        alarm_message=tc.alarm_message,
                    ))

        self._prev_values[point_id] = value
        return results


# ── Mock WebSocket for broadcast benchmark ──────────

class MockWebSocket:
    """Simulates WebSocket.send_json() - measures serialization + write overhead"""

    def __init__(self):
        self._buffer = []

    async def send_json(self, data: dict):
        # Simulate real send_json: serialize to JSON string
        self._buffer.append(json.dumps(data))


# ── Config ──────────

TOTAL_POINTS = 2830
ROUNDS = 5
WS_CLIENT_COUNTS = [1, 5, 10, 20]


# ── Benchmarks ──────────

def bench_alarm_evaluate(engine: AlarmEngineBench, n: int) -> tuple:
    """Benchmark: evaluate() for n points, return (elapsed, alarm_count)"""
    alarm_count = 0
    t0 = time.perf_counter()
    for i in range(1, n + 1):
        # ~5% of values will trigger high alarm (>45), ~5% low (<5)
        value = 20.0 + 5.0 * math.sin(i * 0.1) + random.uniform(-2, 2)
        # Occasionally inject extreme values
        if random.random() < 0.05:
            value = 50.0 + random.uniform(0, 10)  # trigger high
        elif random.random() < 0.05:
            value = 2.0 - random.uniform(0, 3)  # trigger low
        results = engine.evaluate(i, value)
        alarm_count += len(results)
    elapsed = time.perf_counter() - t0
    return elapsed, alarm_count


async def bench_ws_serialization(n: int) -> float:
    """Benchmark: JSON serialize 2830 point payloads (what broadcast_realtime does)"""
    now = datetime.now().isoformat()
    points = []
    for i in range(n):
        points.append({
            "point_id": i + 1,
            "value": round(20.0 + random.uniform(-5, 5), 2),
            "quality": 0,
            "status": "normal",
            "updated_at": now,
        })

    # Simulate what broadcast_realtime does: wrap in message + serialize
    t0 = time.perf_counter()
    message = {"type": "realtime", "data": {"points": points, "count": len(points)}}
    json.dumps(message)
    elapsed = time.perf_counter() - t0
    return elapsed


async def bench_ws_broadcast(n_points: int, n_clients: int) -> float:
    """Benchmark: broadcast aggregated payload to N mock WebSocket clients"""
    now = datetime.now().isoformat()
    points = [
        {
            "point_id": i + 1,
            "value": round(20.0 + random.uniform(-5, 5), 2),
            "quality": 0,
            "status": "normal",
            "updated_at": now,
        }
        for i in range(n_points)
    ]
    message = {"type": "realtime", "data": {"points": points, "count": len(points)}}

    clients = [MockWebSocket() for _ in range(n_clients)]

    t0 = time.perf_counter()
    for client in clients:
        await client.send_json(message)
    elapsed = time.perf_counter() - t0
    return elapsed


async def bench_ws_broadcast_throttled(n_points: int, n_clients: int, chunk_size: int = 500) -> float:
    """Benchmark: broadcast in chunks (throttled strategy) to N clients"""
    datetime.now().isoformat()
    points = [
        {
            "point_id": i + 1,
            "value": round(20.0 + random.uniform(-5, 5), 2),
            "quality": 0,
            "status": "normal",
        }
        for i in range(n_points)
    ]

    clients = [MockWebSocket() for _ in range(n_clients)]

    t0 = time.perf_counter()
    for start in range(0, n_points, chunk_size):
        chunk = points[start:start + chunk_size]
        message = {"type": "realtime", "data": {"points": chunk, "count": len(chunk)}}
        for client in clients:
            await client.send_json(message)
    elapsed = time.perf_counter() - t0
    return elapsed


# ── Main ──────────

async def main():
    print("=" * 70)
    print("WebSocket + Alarm Engine Benchmark")
    print(f"Points: {TOTAL_POINTS}, Rounds: {ROUNDS}")
    print("=" * 70)

    # ── Test 1: alarm_engine.evaluate() ──
    print("\n-- Test 1: alarm_engine.evaluate() x 2830 points --")
    engine = AlarmEngineBench()
    engine.load_mock_thresholds(TOTAL_POINTS)

    times = []
    total_alarms = 0
    for _ in range(ROUNDS):
        # Reset storm suppression for fair comparison
        engine._last_alarm_time.clear()
        elapsed, alarms = bench_alarm_evaluate(engine, TOTAL_POINTS)
        times.append(elapsed)
        total_alarms += alarms

    avg = statistics.mean(times)
    std = statistics.stdev(times) if len(times) > 1 else 0
    avg_alarms = total_alarms / ROUNDS
    print(f"  avg={avg*1000:.1f}ms +/- {std*1000:.1f}ms | ~{avg_alarms:.0f} alarms/round | {'OK' if avg < 0.5 else 'SLOW'}")

    # ── Test 2: JSON serialization of full payload ──
    print("\n-- Test 2: JSON serialize 2830-point payload --")
    times = []
    for _ in range(ROUNDS):
        t = await bench_ws_serialization(TOTAL_POINTS)
        times.append(t)
    avg = statistics.mean(times)
    std = statistics.stdev(times) if len(times) > 1 else 0
    print(f"  avg={avg*1000:.1f}ms +/- {std*1000:.1f}ms | {'OK' if avg < 0.1 else 'SLOW'}")

    # ── Test 3: WebSocket broadcast (full payload, N clients) ──
    print("\n-- Test 3: WebSocket broadcast (full payload) --")
    for n_clients in WS_CLIENT_COUNTS:
        times = []
        for _ in range(ROUNDS):
            t = await bench_ws_broadcast(TOTAL_POINTS, n_clients)
            times.append(t)
        avg = statistics.mean(times)
        std = statistics.stdev(times) if len(times) > 1 else 0
        print(f"  {n_clients:>2d} clients | avg={avg*1000:.1f}ms +/- {std*1000:.1f}ms | {'OK' if avg < 0.5 else 'SLOW'}")

    # ── Test 4: WebSocket broadcast (throttled, chunked) ──
    print("\n-- Test 4: WebSocket broadcast (chunked 500pts/frame, 10 clients) --")
    times = []
    for _ in range(ROUNDS):
        t = await bench_ws_broadcast_throttled(TOTAL_POINTS, 10, chunk_size=500)
        times.append(t)
    avg = statistics.mean(times)
    std = statistics.stdev(times) if len(times) > 1 else 0
    chunks = math.ceil(TOTAL_POINTS / 500)
    print(f"  {chunks} chunks x 10 clients | avg={avg*1000:.1f}ms +/- {std*1000:.1f}ms | {'OK' if avg < 0.5 else 'SLOW'}")

    # ── Test 5: Combined pipeline timing estimate ──
    print("\n-- Test 5: Full pipeline time budget (2830 pts / 5 sec) --")
    # Re-run each component once for combined estimate
    engine._last_alarm_time.clear()
    t_alarm, _ = bench_alarm_evaluate(engine, TOTAL_POINTS)
    t_serial = await bench_ws_serialization(TOTAL_POINTS)
    t_broadcast = await bench_ws_broadcast(TOTAL_POINTS, 10)

    print("  DB write (from prev benchmark):  ~400ms")
    print(f"  Alarm evaluate:                  {t_alarm*1000:.1f}ms")
    print(f"  JSON serialize:                  {t_serial*1000:.1f}ms")
    print(f"  WS broadcast (10 clients):       {t_broadcast*1000:.1f}ms")
    print("  Redis pipeline (estimated):      ~50ms")
    total_est = 400 + t_alarm * 1000 + t_serial * 1000 + t_broadcast * 1000 + 50
    print("  ----------------------------------------")
    print(f"  Estimated total:                 ~{total_est:.0f}ms")
    print(f"  5-sec budget remaining:          ~{5000 - total_est:.0f}ms")
    if total_est < 2000:
        print("  PASS: Full pipeline well within 5-second budget")
    elif total_est < 4000:
        print("  WARN: Tight but feasible")
    else:
        print("  FAIL: Exceeds budget, need optimization")

    print("\n" + "=" * 70)
    print("Benchmark complete")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
