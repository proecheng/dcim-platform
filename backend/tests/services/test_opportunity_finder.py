"""
Test cases for Opportunity Finder
机会发现算法测试
"""

import pytest
from datetime import date, timedelta
from decimal import Decimal
from app.services.load_shift.algorithms.opportunity_finder import OpportunityFinder


@pytest.mark.asyncio
async def test_opportunity_finder_initialization(db_session):
    """测试 OpportunityFinder 初始化"""
    finder = OpportunityFinder(db_session)
    
    assert finder.db == db_session
    assert finder.pricing["sharp"] == Decimal("1.2")
    assert finder.pricing["valley"] == Decimal("0.3")
    assert finder.min_price_diff == Decimal("0.3")
    assert finder.min_shift_power == 50.0
    assert finder.min_confidence == 0.6


@pytest.mark.asyncio
async def test_identify_shift_pairs(db_session):
    """测试转移对识别"""
    finder = OpportunityFinder(db_session)
    
    analysis = {
        "peak_avg_power": 500.0,
        "valley_avg_power": 300.0,
        "available_capacity": 200.0,
        "confidence": 0.8
    }
    
    pairs = finder._identify_shift_pairs(analysis)
    
    assert len(pairs) > 0
    assert all(pair["price_diff"] >= finder.min_price_diff for pair in pairs)
    assert all(pair["recommended_power"] > 0 for pair in pairs)


@pytest.mark.asyncio
async def test_calculate_predicted_saving(db_session):
    """测试预期收益计算"""
    finder = OpportunityFinder(db_session)
    
    shift_power = 100.0
    price_diff = Decimal("0.6")
    duration_hours = 4
    
    saving = finder._calculate_predicted_saving(shift_power, price_diff, duration_hours)
    
    expected = Decimal("100") * Decimal("4") * Decimal("0.6")
    assert saving == expected.quantize(Decimal("0.01"))


@pytest.mark.asyncio
async def test_calculate_confidence_score(db_session):
    """测试置信度计算"""
    finder = OpportunityFinder(db_session)
    
    # 测试完整数据
    confidence = finder._calculate_confidence_score(lookback_days=30, device_count=5)
    assert 0.6 <= confidence <= 1.0
    
    # 测试数据不足
    confidence_low = finder._calculate_confidence_score(lookback_days=7, device_count=1)
    assert confidence_low < confidence


@pytest.mark.asyncio
async def test_determine_priority(db_session):
    """测试优先级判定"""
    finder = OpportunityFinder(db_session)
    
    # 高优先级
    priority_high = finder._determine_priority(Decimal("600"), 0.85)
    assert priority_high == "high"
    
    # 中优先级
    priority_medium = finder._determine_priority(Decimal("300"), 0.7)
    assert priority_medium == "medium"
    
    # 低优先级
    priority_low = finder._determine_priority(Decimal("100"), 0.5)
    assert priority_low == "low"


@pytest.mark.asyncio
async def test_find_daily_opportunities_no_data(async_db):
    """测试无数据时的机会发现"""
    finder = OpportunityFinder(async_db)

    # 使用未来日期（无历史数据）
    future_date = date.today() + timedelta(days=365)
    opportunities = await finder.find_daily_opportunities(future_date, lookback_days=7)

    assert isinstance(opportunities, list)
    # 无数据时应返回空列表
    assert len(opportunities) == 0
