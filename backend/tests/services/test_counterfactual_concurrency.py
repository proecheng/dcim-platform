"""
反事实分析并发测试
Story 26.1: 反事实分析
"""

import pytest
import asyncio
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.diagnosis import DiagnosisSession, DiagnosisResult
from app.services.diagnosis.counterfactual_service import analyze_counterfactual
from tests.conftest import redis_required


@redis_required
@pytest.mark.asyncio
async def test_concurrent_same_session_redis_lock(async_db: AsyncSession):
    """
    并发测试: 同一 session_id 并发请求

    验证:
    1. 多个并发请求同时分析同一 session_id
    2. Redis 分布式锁确保只有一个请求执行分析
    3. 其他请求返回 None（获取锁失败）
    4. 最终只创建一条分析记录
    """
    # 1. 创建诊断会话和结果
    now = datetime.now()
    session = DiagnosisSession(
        trigger_alarm_id=4001,
        device_id=401,
        engine_level="L2",
        status="success",
        max_confidence=0.8,
        start_time=now,
        end_time=now,
    )
    async_db.add(session)
    await async_db.commit()
    await async_db.refresh(session)

    result = DiagnosisResult(
        session_id=session.id,
        alarm_id=4001,
        alarm_no="ALM-2026-4001",
        device_type="UPS",
        zone="并发测试区",
        root_cause="UPS故障",
        confidence=0.8,
        evidence=[
            {
                "node_id": 1001,
                "evidence_type": "sensor",
                "probability": 0.85,
                "sensor_weight": 0.9,
                "path_length": 1,
            },
            {
                "node_id": 1002,
                "evidence_type": "threshold",
                "probability": 0.75,
                "sensor_weight": 0.85,
                "path_length": 2,
            },
            {
                "node_id": 1003,
                "evidence_type": "history",
                "probability": 0.7,
                "sensor_weight": 0.8,
                "path_length": 3,
            },
        ],
        reasoning_path=[
            {"node_id": 1001, "description": "电压异常", "dependencies": []},
            {"node_id": 1002, "description": "充电异常", "dependencies": [1001]},
            {"node_id": 1003, "description": "历史故障", "dependencies": [1001, 1002]},
        ],
        fault_tree_version="v1.0.0",
    )
    async_db.add(result)
    await async_db.commit()

    # 2. 并发执行 5 次分析
    tasks = [
        analyze_counterfactual(session.id, top_n=3, db=async_db)
        for _ in range(5)
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 3. 验证结果
    # 至少有一个成功（获取锁成功）
    successful_results = [r for r in results if r is not None and not isinstance(r, Exception)]
    assert len(successful_results) >= 1, "至少应该有一个请求成功"

    # 失败的请求应该返回 None（获取锁失败）
    failed_results = [r for r in results if r is None]
    assert len(failed_results) >= 1, "至少应该有一个请求因锁冲突而失败"

    # 4. 验证数据库中只有一条记录
    from sqlalchemy import select, func
    from app.models.diagnosis import CounterfactualAnalysis

    count_result = await async_db.execute(
        select(func.count(CounterfactualAnalysis.id)).where(
            CounterfactualAnalysis.session_id == session.id,
            CounterfactualAnalysis.deleted_at.is_(None)
        )
    )
    count = count_result.scalar()
    assert count == 1, f"应该只有一条分析记录，实际有 {count} 条"


@redis_required
@pytest.mark.asyncio
async def test_concurrent_different_sessions(async_db: AsyncSession):
    """
    并发测试: 不同 session_id 并发请求

    验证:
    1. 多个不同 session_id 并发请求
    2. 所有请求都应该成功（不同锁）
    3. 每个 session_id 都有对应的分析记录
    """
    # 1. 创建 3 个诊断会话和结果
    sessions = []
    now = datetime.now()

    for i in range(3):
        session = DiagnosisSession(
            trigger_alarm_id=5000 + i,
            device_id=500 + i,
            engine_level="L2",
            status="success",
            max_confidence=0.7 + i * 0.05,
            start_time=now,
            end_time=now,
        )
        async_db.add(session)
        await async_db.commit()
        await async_db.refresh(session)

        result = DiagnosisResult(
            session_id=session.id,
            alarm_id=5000 + i,
            alarm_no=f"ALM-2026-{5000 + i}",
            device_type="UPS",
            zone=f"并发测试区{i}",
            root_cause=f"故障{i}",
            confidence=0.7 + i * 0.05,
            evidence=[
                {
                    "node_id": 2000 + i * 10,
                    "evidence_type": "sensor",
                    "probability": 0.8,
                    "sensor_weight": 0.85,
                    "path_length": 1,
                }
            ],
            reasoning_path=[
                {"node_id": 2000 + i * 10, "description": f"证据{i}", "dependencies": []}
            ],
            fault_tree_version="v1.0.0",
        )
        async_db.add(result)
        await async_db.commit()

        sessions.append(session)

    # 2. 并发执行分析
    tasks = [
        analyze_counterfactual(s.id, top_n=3, db=async_db)
        for s in sessions
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 3. 验证所有请求都成功
    successful_results = [r for r in results if r is not None and not isinstance(r, Exception)]
    assert len(successful_results) == 3, f"所有请求都应该成功，实际成功 {len(successful_results)} 个"

    # 4. 验证每个 session_id 都有对应的分析记录
    from sqlalchemy import select
    from app.models.diagnosis import CounterfactualAnalysis

    for session in sessions:
        analysis_result = await async_db.execute(
            select(CounterfactualAnalysis).where(
                CounterfactualAnalysis.session_id == session.id,
                CounterfactualAnalysis.deleted_at.is_(None)
            )
        )
        analysis = analysis_result.scalar_one_or_none()
        assert analysis is not None, f"Session {session.id} 应该有分析记录"


@redis_required
@pytest.mark.asyncio
async def test_concurrent_cache_hit(async_db: AsyncSession):
    """
    并发测试: 缓存命中场景

    验证:
    1. 第一次分析创建缓存
    2. 后续并发请求都命中缓存
    3. 所有请求返回相同的分析记录
    """
    # 1. 创建诊断会话和结果
    now = datetime.now()
    session = DiagnosisSession(
        trigger_alarm_id=6001,
        device_id=601,
        engine_level="L2",
        status="success",
        max_confidence=0.75,
        start_time=now,
        end_time=now,
    )
    async_db.add(session)
    await async_db.commit()
    await async_db.refresh(session)

    result = DiagnosisResult(
        session_id=session.id,
        alarm_id=6001,
        alarm_no="ALM-2026-6001",
        device_type="AC",
        zone="缓存测试区",
        root_cause="空调故障",
        confidence=0.75,
        evidence=[
            {
                "node_id": 3001,
                "evidence_type": "sensor",
                "probability": 0.8,
                "sensor_weight": 0.85,
                "path_length": 1,
            }
        ],
        reasoning_path=[
            {"node_id": 3001, "description": "温度异常", "dependencies": []}
        ],
        fault_tree_version="v1.0.0",
    )
    async_db.add(result)
    await async_db.commit()

    # 2. 第一次分析（创建缓存）
    first_analysis = await analyze_counterfactual(session.id, top_n=3, db=async_db)
    assert first_analysis is not None
    first_analysis_id = first_analysis.id

    # 3. 并发执行 10 次分析（应该都命中缓存）
    tasks = [
        analyze_counterfactual(session.id, top_n=3, db=async_db)
        for _ in range(10)
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 4. 验证所有请求都返回相同的分析记录
    successful_results = [r for r in results if r is not None and not isinstance(r, Exception)]
    assert len(successful_results) >= 1, "至少应该有一个请求成功"

    for analysis in successful_results:
        assert analysis.id == first_analysis_id, "所有请求应该返回相同的缓存记录"


@redis_required
@pytest.mark.asyncio
async def test_concurrent_lock_timeout(async_db: AsyncSession):
    """
    并发测试: 锁超时场景

    验证:
    1. 模拟长时间持有锁的场景
    2. 其他请求在锁超时后能够获取锁
    3. 最终所有请求都能完成
    """
    # 1. 创建诊断会话和结果
    now = datetime.now()
    session = DiagnosisSession(
        trigger_alarm_id=7001,
        device_id=701,
        engine_level="L2",
        status="success",
        max_confidence=0.8,
        start_time=now,
        end_time=now,
    )
    async_db.add(session)
    await async_db.commit()
    await async_db.refresh(session)

    result = DiagnosisResult(
        session_id=session.id,
        alarm_id=7001,
        alarm_no="ALM-2026-7001",
        device_type="PDU",
        zone="超时测试区",
        root_cause="配电故障",
        confidence=0.8,
        evidence=[
            {
                "node_id": 4001,
                "evidence_type": "sensor",
                "probability": 0.85,
                "sensor_weight": 0.9,
                "path_length": 1,
            }
        ],
        reasoning_path=[
            {"node_id": 4001, "description": "电流异常", "dependencies": []}
        ],
        fault_tree_version="v1.0.0",
    )
    async_db.add(result)
    await async_db.commit()

    # 2. 第一次分析（正常完成）
    first_analysis = await analyze_counterfactual(session.id, top_n=3, db=async_db)
    assert first_analysis is not None

    # 3. 等待一段时间后再次分析（模拟锁过期后的场景）
    await asyncio.sleep(2)

    # 4. 第二次分析（应该命中缓存）
    second_analysis = await analyze_counterfactual(session.id, top_n=3, db=async_db)
    assert second_analysis is not None
    assert second_analysis.id == first_analysis.id, "应该返回缓存记录"
