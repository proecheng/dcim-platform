"""
A/B 测试服务单元测试 - Story 26.5
"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.diagnosis.ab_testing_service import ABTestingService
from app.models.ab_test_config import ABTestConfig, ABTestDeviceAssignment
from app.models.fault_tree import FaultTree, FaultTreeVersion
from app.models.diagnosis import DiagnosisResult, DiagnosisAnnotation


@pytest.mark.asyncio
async def test_create_ab_test(db_session: AsyncSession):
    """测试创建 A/B 测试配置"""
    # 创建故障树和版本
    fault_tree = FaultTree(name="测试故障树", status="active")
    db_session.add(fault_tree)
    await db_session.flush()

    version_a = FaultTreeVersion(
        tree_id=fault_tree.id,
        version_number=2,
        status="reviewed",
        snapshot="{}",
        created_by=1,
    )
    version_b = FaultTreeVersion(
        tree_id=fault_tree.id,
        version_number=1,
        status="active",
        snapshot="{}",
        created_by=1,
    )
    db_session.add_all([version_a, version_b])
    await db_session.commit()

    # 创建 A/B 测试
    service = ABTestingService(db_session)
    ab_test = await service.create_ab_test(
        name="测试 A/B 测试",
        fault_tree_id=fault_tree.id,
        version_a_id=version_a.id,
        version_b_id=version_b.id,
        strategy="percentage",
        strategy_params={"percentage": 10},
        created_by=1,
    )

    assert ab_test.id is not None
    assert ab_test.name == "测试 A/B 测试"
    assert ab_test.status == "active"
    assert ab_test.version == 1


@pytest.mark.asyncio
async def test_create_duplicate_ab_test(db_session: AsyncSession):
    """测试创建重复的 A/B 测试（同一故障树只能有一个活跃测试）"""
    # 创建故障树和版本
    fault_tree = FaultTree(name="测试故障树2", status="active")
    db_session.add(fault_tree)
    await db_session.flush()

    version_a = FaultTreeVersion(
        tree_id=fault_tree.id,
        version_number=2,
        status="reviewed",
        snapshot="{}",
        created_by=1,
    )
    version_b = FaultTreeVersion(
        tree_id=fault_tree.id,
        version_number=1,
        status="active",
        snapshot="{}",
        created_by=1,
    )
    db_session.add_all([version_a, version_b])
    await db_session.commit()

    # 创建第一个 A/B 测试
    service = ABTestingService(db_session)
    await service.create_ab_test(
        name="测试 A/B 测试1",
        fault_tree_id=fault_tree.id,
        version_a_id=version_a.id,
        version_b_id=version_b.id,
        strategy="percentage",
        strategy_params={"percentage": 10},
        created_by=1,
    )

    # 尝试创建第二个 A/B 测试（应该失败）
    with pytest.raises(ValueError, match="已有活跃的 A/B 测试"):
        await service.create_ab_test(
            name="测试 A/B 测试2",
            fault_tree_id=fault_tree.id,
            version_a_id=version_a.id,
            version_b_id=version_b.id,
            strategy="percentage",
            strategy_params={"percentage": 20},
            created_by=1,
        )


@pytest.mark.asyncio
async def test_select_version_by_hash(db_session: AsyncSession):
    """测试一致性哈希分流"""
    service = ABTestingService(db_session)

    # 测试 10% 分流
    version_id = service._select_version_by_hash("device-001", 10, 100, 200)
    # 同一设备ID应该始终返回相同版本
    assert version_id == service._select_version_by_hash("device-001", 10, 100, 200)

    # 测试 100% 分流（全部使用版本A）
    version_id = service._select_version_by_hash("device-002", 100, 100, 200)
    assert version_id == 100

    # 测试 0% 分流（全部使用版本B）
    version_id = service._select_version_by_hash("device-003", 0, 100, 200)
    assert version_id == 200


@pytest.mark.asyncio
async def test_select_version_by_device_type(db_session: AsyncSession):
    """测试按设备类型分流"""
    service = ABTestingService(db_session)

    # UPS 设备使用版本A
    version_id = service._select_version_by_device_type("UPS", ["UPS", "PDU"], 100, 200)
    assert version_id == 100

    # 空调设备使用版本B
    version_id = service._select_version_by_device_type("空调", ["UPS", "PDU"], 100, 200)
    assert version_id == 200


@pytest.mark.asyncio
async def test_select_version_by_site(db_session: AsyncSession):
    """测试按站点分流"""
    service = ABTestingService(db_session)

    # 站点1使用版本A
    version_id = service._select_version_by_site(1, [1, 3, 5], 100, 200)
    assert version_id == 100

    # 站点2使用版本B
    version_id = service._select_version_by_site(2, [1, 3, 5], 100, 200)
    assert version_id == 200


@pytest.mark.asyncio
async def test_update_ab_test(db_session: AsyncSession):
    """测试更新 A/B 测试配置（扩大灰度）"""
    # 创建故障树和版本
    fault_tree = FaultTree(name="测试故障树3", status="active")
    db_session.add(fault_tree)
    await db_session.flush()

    version_a = FaultTreeVersion(
        tree_id=fault_tree.id,
        version_number=2,
        status="reviewed",
        snapshot="{}",
        created_by=1,
    )
    version_b = FaultTreeVersion(
        tree_id=fault_tree.id,
        version_number=1,
        status="active",
        snapshot="{}",
        created_by=1,
    )
    db_session.add_all([version_a, version_b])
    await db_session.commit()

    # 创建 A/B 测试
    service = ABTestingService(db_session)
    ab_test = await service.create_ab_test(
        name="测试更新",
        fault_tree_id=fault_tree.id,
        version_a_id=version_a.id,
        version_b_id=version_b.id,
        strategy="percentage",
        strategy_params={"percentage": 10},
        created_by=1,
    )

    # 更新配置（扩大到 20%）
    updated = await service.update_ab_test(
        ab_test_id=ab_test.id,
        strategy_params={"percentage": 20},
        version=1,
    )

    assert updated.strategy_params["percentage"] == 20
    assert updated.version == 2  # 版本号应该递增


@pytest.mark.asyncio
async def test_update_ab_test_version_conflict(db_session: AsyncSession):
    """测试乐观锁版本冲突"""
    # 创建故障树和版本
    fault_tree = FaultTree(name="测试故障树4", status="active")
    db_session.add(fault_tree)
    await db_session.flush()

    version_a = FaultTreeVersion(
        tree_id=fault_tree.id,
        version_number=2,
        status="reviewed",
        snapshot="{}",
        created_by=1,
    )
    version_b = FaultTreeVersion(
        tree_id=fault_tree.id,
        version_number=1,
        status="active",
        snapshot="{}",
        created_by=1,
    )
    db_session.add_all([version_a, version_b])
    await db_session.commit()

    # 创建 A/B 测试
    service = ABTestingService(db_session)
    ab_test = await service.create_ab_test(
        name="测试版本冲突",
        fault_tree_id=fault_tree.id,
        version_a_id=version_a.id,
        version_b_id=version_b.id,
        strategy="percentage",
        strategy_params={"percentage": 10},
        created_by=1,
    )

    # 使用错误的版本号更新（应该失败）
    with pytest.raises(ValueError, match="版本冲突"):
        await service.update_ab_test(
            ab_test_id=ab_test.id,
            strategy_params={"percentage": 20},
            version=999,  # 错误的版本号
        )


@pytest.mark.asyncio
async def test_update_ab_test_gradual_expansion_limit(db_session: AsyncSession):
    """测试灰度扩大限制（不超过 2 倍）"""
    # 创建故障树和版本
    fault_tree = FaultTree(name="测试故障树5", status="active")
    db_session.add(fault_tree)
    await db_session.flush()

    version_a = FaultTreeVersion(
        tree_id=fault_tree.id,
        version_number=2,
        status="reviewed",
        snapshot="{}",
        created_by=1,
    )
    version_b = FaultTreeVersion(
        tree_id=fault_tree.id,
        version_number=1,
        status="active",
        snapshot="{}",
        created_by=1,
    )
    db_session.add_all([version_a, version_b])
    await db_session.commit()

    # 创建 A/B 测试
    service = ABTestingService(db_session)
    ab_test = await service.create_ab_test(
        name="测试灰度限制",
        fault_tree_id=fault_tree.id,
        version_a_id=version_a.id,
        version_b_id=version_b.id,
        strategy="percentage",
        strategy_params={"percentage": 10},
        created_by=1,
    )

    # 尝试扩大到 30%（超过 2 倍，应该失败）
    with pytest.raises(ValueError, match="灰度扩大不能超过 2 倍"):
        await service.update_ab_test(
            ab_test_id=ab_test.id,
            strategy_params={"percentage": 30},
            version=1,
        )


@pytest.mark.asyncio
async def test_chi_square_test(db_session: AsyncSession):
    """测试卡方检验"""
    service = ABTestingService(db_session)

    # 测试样本量不足
    version_a_stats = {
        "accurate_count": 5,
        "inaccurate_count": 0,
        "diagnosis_count": 5,
    }
    version_b_stats = {
        "accurate_count": 3,
        "inaccurate_count": 0,
        "diagnosis_count": 3,
    }
    result = service._perform_chi_square_test(version_a_stats, version_b_stats)
    assert result["method"] == "insufficient_sample"
    assert result["is_significant"] is False

    # 测试显著差异
    version_a_stats = {
        "accurate_count": 85,
        "inaccurate_count": 15,
        "diagnosis_count": 100,
    }
    version_b_stats = {
        "accurate_count": 70,
        "inaccurate_count": 30,
        "diagnosis_count": 100,
    }
    result = service._perform_chi_square_test(version_a_stats, version_b_stats)
    assert result["method"] in ["chi_square", "fisher_exact"]
    assert result["p_value"] is not None
