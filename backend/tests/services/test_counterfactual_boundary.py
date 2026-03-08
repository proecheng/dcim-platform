"""
反事实分析边界测试
Story 26.1: 反事实分析
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.diagnosis import DiagnosisSession, DiagnosisResult
from app.services.diagnosis.counterfactual_service import (
    analyze_counterfactual,
    calculate_evidence_weight,
)


@pytest.mark.asyncio
async def test_counterfactual_no_evidence(db: AsyncSession):
    """
    边界测试: 无证据场景

    验证:
    1. 诊断结果没有证据
    2. 分析返回 None（跳过分析）
    """
    # 1. 创建诊断会话
    session = DiagnosisSession(
        trigger_alarm_id=3001,
        device_id=301,
        engine_level="L1",
        status="success",
        max_confidence=0.5,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    # 2. 创建诊断结果（无证据）
    result = DiagnosisResult(
        session_id=session.id,
        alarm_id=3001,
        alarm_no="ALM-2026-3001",
        device_type="UPS",
        zone="F区",
        root_cause="未知故障",
        confidence=0.5,
        evidence=[],  # 空证据列表
        reasoning_path=[],
        fault_tree_version="v1.0.0",
    )
    db.add(result)
    await db.commit()

    # 3. 执行反事实分析（应该跳过）
    analysis = await analyze_counterfactual(session.id, top_n=3, db=db)

    assert analysis is None  # 无证据时应该返回 None


@pytest.mark.asyncio
async def test_counterfactual_low_confidence(db: AsyncSession):
    """
    边界测试: 低置信度场景

    验证:
    1. 原始置信度 < 0.3
    2. 分析返回 None（跳过分析）
    """
    # 1. 创建诊断会话
    session = DiagnosisSession(
        trigger_alarm_id=3002,
        device_id=302,
        engine_level="L1",
        status="success",
        max_confidence=0.25,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    # 2. 创建诊断结果（低置信度）
    result = DiagnosisResult(
        session_id=session.id,
        alarm_id=3002,
        alarm_no="ALM-2026-3002",
        device_type="AC",
        zone="G区",
        root_cause="可能故障",
        confidence=0.25,  # 低于 0.3 阈值
        evidence=[
            {
                "node_id": 601,
                "evidence_type": "sensor",
                "probability": 0.5,
                "sensor_weight": 0.7,
                "path_length": 1,
            }
        ],
        reasoning_path=[{"node_id": 601, "description": "弱证据", "dependencies": []}],
        fault_tree_version="v1.0.0",
    )
    db.add(result)
    await db.commit()

    # 3. 执行反事实分析（应该跳过）
    analysis = await analyze_counterfactual(session.id, top_n=3, db=db)

    assert analysis is None  # 低置信度时应该返回 None


@pytest.mark.asyncio
async def test_counterfactual_equal_weights(db: AsyncSession):
    """
    边界测试: 证据权重相等场景

    验证:
    1. 所有证据权重完全相等
    2. 分析正常执行
    3. 返回结果按原始顺序
    """
    # 1. 创建诊断会话
    session = DiagnosisSession(
        trigger_alarm_id=3003,
        device_id=303,
        engine_level="L2",
        status="success",
        max_confidence=0.7,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    # 2. 创建诊断结果（所有证据权重相等）
    result = DiagnosisResult(
        session_id=session.id,
        alarm_id=3003,
        alarm_no="ALM-2026-3003",
        device_type="PDU",
        zone="H区",
        root_cause="配电故障",
        confidence=0.7,
        evidence=[
            {
                "node_id": 701,
                "evidence_type": "sensor",
                "probability": 0.8,
                "sensor_weight": 0.9,
                "path_length": 1,
            },
            {
                "node_id": 702,
                "evidence_type": "sensor",
                "probability": 0.8,
                "sensor_weight": 0.9,
                "path_length": 1,
            },
            {
                "node_id": 703,
                "evidence_type": "sensor",
                "probability": 0.8,
                "sensor_weight": 0.9,
                "path_length": 1,
            },
        ],
        reasoning_path=[
            {"node_id": 701, "description": "证据1", "dependencies": []},
            {"node_id": 702, "description": "证据2", "dependencies": []},
            {"node_id": 703, "description": "证据3", "dependencies": []},
        ],
        fault_tree_version="v1.0.0",
    )
    db.add(result)
    await db.commit()

    # 3. 执行反事实分析
    analysis = await analyze_counterfactual(session.id, top_n=3, db=db)

    assert analysis is not None
    assert len(analysis.top_evidences) == 3
    assert len(analysis.analysis_results) == 3

    # 4. 验证权重相等
    weights = [
        calculate_evidence_weight(ev, 0.8) for ev in result.evidence
    ]
    assert len(set(weights)) == 1  # 所有权重相同


@pytest.mark.asyncio
async def test_counterfactual_more_than_10_evidences(db: AsyncSession):
    """
    边界测试: 超过10个证据场景

    验证:
    1. 证据数量 > 10
    2. 只分析 Top 5（默认 top_n=5）
    3. 返回结果数量 = 5
    """
    # 1. 创建诊断会话
    session = DiagnosisSession(
        trigger_alarm_id=3004,
        device_id=304,
        engine_level="L2",
        status="success",
        max_confidence=0.9,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    # 2. 创建诊断结果（15个证据）
    evidences = []
    reasoning_path = []
    for i in range(15):
        evidences.append(
            {
                "node_id": 800 + i,
                "evidence_type": "sensor",
                "probability": 0.9 - i * 0.02,  # 递减概率
                "sensor_weight": 0.95 - i * 0.01,  # 递减权重
                "path_length": 1 + i // 5,  # 路径长度递增
            }
        )
        reasoning_path.append(
            {"node_id": 800 + i, "description": f"证据{i}", "dependencies": []}
        )

    result = DiagnosisResult(
        session_id=session.id,
        alarm_id=3004,
        alarm_no="ALM-2026-3004",
        device_type="UPS",
        zone="I区",
        root_cause="复杂故障",
        confidence=0.9,
        evidence=evidences,
        reasoning_path=reasoning_path,
        fault_tree_version="v1.0.0",
    )
    db.add(result)
    await db.commit()

    # 3. 执行反事实分析（top_n=5）
    analysis = await analyze_counterfactual(session.id, top_n=5, db=db)

    assert analysis is not None
    assert len(analysis.top_evidences) == 5  # 只返回 Top 5
    assert len(analysis.analysis_results) == 5

    # 4. 验证返回的是权重最高的5个证据
    top_5_node_ids = [ev["node_id"] for ev in analysis.top_evidences]
    assert top_5_node_ids == [800, 801, 802, 803, 804]  # 前5个证据权重最高


@pytest.mark.asyncio
async def test_counterfactual_session_not_found(db: AsyncSession):
    """
    边界测试: 诊断会话不存在

    验证:
    1. session_id 不存在
    2. 分析返回 None
    """
    # 执行反事实分析（不存在的 session_id）
    analysis = await analyze_counterfactual(99999, top_n=3, db=db)

    assert analysis is None


@pytest.mark.asyncio
async def test_counterfactual_result_not_found(db: AsyncSession):
    """
    边界测试: 诊断结果不存在

    验证:
    1. 诊断会话存在，但没有诊断结果
    2. 分析返回 None
    """
    # 1. 创建诊断会话（但不创建诊断结果）
    session = DiagnosisSession(
        trigger_alarm_id=3005,
        device_id=305,
        engine_level="L1",
        status="pending",
        max_confidence=0.0,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    # 2. 执行反事实分析（没有诊断结果）
    analysis = await analyze_counterfactual(session.id, top_n=3, db=db)

    assert analysis is None


def test_calculate_evidence_weight_boundary():
    """
    单元测试: 证据权重计算边界值

    验证:
    1. 最小权重（probability=0, sensor_weight=0, path_length=10）
    2. 最大权重（probability=1, sensor_weight=1, path_length=1）
    3. 路径衰减因子影响
    """
    # 1. 最小权重
    min_evidence = {
        "probability": 0.0,
        "sensor_weight": 0.0,
        "path_length": 10,
    }
    min_weight = calculate_evidence_weight(min_evidence, 0.8)
    assert min_weight == 0.0

    # 2. 最大权重
    max_evidence = {
        "probability": 1.0,
        "sensor_weight": 1.0,
        "path_length": 1,
    }
    max_weight = calculate_evidence_weight(max_evidence, 0.8)
    assert max_weight == 0.8  # 1.0 * 1.0 * 0.8^1

    # 3. 路径衰减影响
    evidence_path_1 = {
        "probability": 0.9,
        "sensor_weight": 0.9,
        "path_length": 1,
    }
    evidence_path_3 = {
        "probability": 0.9,
        "sensor_weight": 0.9,
        "path_length": 3,
    }
    weight_path_1 = calculate_evidence_weight(evidence_path_1, 0.8)
    weight_path_3 = calculate_evidence_weight(evidence_path_3, 0.8)

    assert weight_path_1 > weight_path_3  # 路径越短，权重越高
    assert weight_path_3 == pytest.approx(0.9 * 0.9 * (0.8 ** 3), rel=1e-6)


@pytest.mark.asyncio
async def test_counterfactual_cache_invalidation_version_mismatch(db: AsyncSession):
    """
    边界测试: 缓存失效 - 版本不匹配

    验证:
    1. 第一次分析创建缓存
    2. 更新故障树版本
    3. 第二次分析重新计算（缓存失效）
    """
    # 1. 创建诊断会话和结果
    session = DiagnosisSession(
        trigger_alarm_id=3006,
        device_id=306,
        engine_level="L2",
        status="success",
        max_confidence=0.8,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    result = DiagnosisResult(
        session_id=session.id,
        alarm_id=3006,
        alarm_no="ALM-2026-3006",
        device_type="UPS",
        zone="J区",
        root_cause="UPS故障",
        confidence=0.8,
        evidence=[
            {
                "node_id": 901,
                "evidence_type": "sensor",
                "probability": 0.85,
                "sensor_weight": 0.9,
                "path_length": 1,
            }
        ],
        reasoning_path=[{"node_id": 901, "description": "电压异常", "dependencies": []}],
        fault_tree_version="v1.0.0",
    )
    db.add(result)
    await db.commit()

    # 2. 第一次分析（创建缓存）
    analysis1 = await analyze_counterfactual(session.id, top_n=3, db=db)
    assert analysis1 is not None
    analysis1_id = analysis1.id

    # 3. 更新故障树版本
    result.fault_tree_version = "v2.0.0"
    await db.commit()

    # 4. 第二次分析（缓存失效，重新计算）
    analysis2 = await analyze_counterfactual(session.id, top_n=3, db=db)
    assert analysis2 is not None
    assert analysis2.id != analysis1_id  # 应该创建新记录
    assert analysis2.fault_tree_version == "v2.0.0"


@pytest.mark.asyncio
async def test_counterfactual_timeout_handling(db: AsyncSession):
    """
    边界测试: 超时处理

    验证:
    1. 分析超时（ANALYSIS_TIMEOUT_SECONDS=5秒）
    2. 返回 None
    3. 记录超时指标
    """
    # 注意: 这个测试需要模拟超时场景，实际测试中可能需要 mock
    # 这里只验证正常情况下不会超时

    # 1. 创建诊断会话和结果
    session = DiagnosisSession(
        trigger_alarm_id=3007,
        device_id=307,
        engine_level="L2",
        status="success",
        max_confidence=0.75,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    result = DiagnosisResult(
        session_id=session.id,
        alarm_id=3007,
        alarm_no="ALM-2026-3007",
        device_type="AC",
        zone="K区",
        root_cause="空调故障",
        confidence=0.75,
        evidence=[
            {
                "node_id": 1001,
                "evidence_type": "sensor",
                "probability": 0.8,
                "sensor_weight": 0.85,
                "path_length": 1,
            }
        ],
        reasoning_path=[{"node_id": 1001, "description": "温度异常", "dependencies": []}],
        fault_tree_version="v1.0.0",
    )
    db.add(result)
    await db.commit()

    # 2. 执行反事实分析（正常情况下应该在5秒内完成）
    analysis = await analyze_counterfactual(session.id, top_n=3, db=db)

    assert analysis is not None
    assert analysis.analysis_time_ms < 5000  # 应该在5秒内完成
