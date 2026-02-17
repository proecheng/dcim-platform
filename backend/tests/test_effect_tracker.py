"""效果追踪服务测试 — Story 6-4"""
import pytest
from datetime import datetime, date, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import delete, select

from app.core.database import Base
from app.models.energy import (
    EnergyOpportunity, ExecutionPlan, ExecutionTask, ExecutionResult, EnergyDaily
)
from app.services.effect_tracker import EffectTracker


# ==================== Fixtures ====================


@pytest.fixture(scope="module")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="module")
async def api_engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture(scope="module")
def session_factory(api_engine):
    return async_sessionmaker(api_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
async def db_session(session_factory):
    async with session_factory() as session:
        # 清理相关表（按外键顺序）
        await session.execute(delete(ExecutionResult))
        await session.execute(delete(ExecutionTask))
        await session.execute(delete(ExecutionPlan))
        await session.execute(delete(EnergyOpportunity))
        await session.execute(delete(EnergyDaily))
        await session.commit()
        yield session


# ==================== 辅助函数 ====================


def _create_opportunity(db, **kwargs):
    """创建测试机会"""
    defaults = dict(
        category=1,
        title="测试机会",
        description="测试描述",
        priority="high",
        status="executing",
        potential_saving=10000,
        confidence=0.85,
        source_plugin="peak_valley_optimizer",
        analysis_data={},
    )
    defaults.update(kwargs)
    opp = EnergyOpportunity(**defaults)
    db.add(opp)
    return opp


def _create_plan(db, opportunity_id, **kwargs):
    """创建测试执行计划"""
    defaults = dict(
        opportunity_id=opportunity_id,
        plan_name="测试计划",
        expected_saving=10000,
        status="completed",
        completed_at=datetime.now() - timedelta(days=10),
        created_by=1,
    )
    defaults.update(kwargs)
    plan = ExecutionPlan(**defaults)
    db.add(plan)
    return plan


# ==================== 1. 查找需要追踪的计划 ====================


class TestFindPlansNeedingTracking:

    @pytest.mark.anyio
    async def test_find_plans_needing_tracking(self, db_session):
        """已完成计划(completed_at 10天前, 无 ExecutionResult) 应被找到"""
        opp = _create_opportunity(db_session)
        await db_session.flush()

        plan = _create_plan(
            db_session, opp.id,
            completed_at=datetime.now() - timedelta(days=10)
        )
        await db_session.flush()
        await db_session.commit()

        tracker = EffectTracker(db_session)
        plans = await tracker._find_plans_needing_tracking()
        assert len(plans) >= 1
        assert any(p.id == plan.id for p in plans)

    @pytest.mark.anyio
    async def test_skip_plans_with_existing_results(self, db_session):
        """已有 ExecutionResult 的计划不应被找到"""
        opp = _create_opportunity(db_session)
        await db_session.flush()

        plan = _create_plan(
            db_session, opp.id,
            completed_at=datetime.now() - timedelta(days=10)
        )
        await db_session.flush()

        # 添加 ExecutionResult
        result = ExecutionResult(
            plan_id=plan.id,
            tracking_period=7,
            tracking_start=date.today() - timedelta(days=7),
            tracking_end=date.today(),
            actual_saving=5000,
            achievement_rate=50.0,
            status="tracking",
        )
        db_session.add(result)
        await db_session.commit()

        tracker = EffectTracker(db_session)
        plans = await tracker._find_plans_needing_tracking()
        assert not any(p.id == plan.id for p in plans)


# ==================== 2. 能耗对比计算 ====================


class TestEnergyComparisonEffect:

    @pytest.mark.anyio
    async def test_calculate_energy_comparison_effect(self, db_session):
        """创建 EnergyDaily 记录，验证能耗对比计算"""
        opp = _create_opportunity(db_session, source_plugin="generic_plugin", analysis_data={})
        await db_session.flush()

        completed_at = datetime.now() - timedelta(days=10)
        plan = _create_plan(db_session, opp.id, completed_at=completed_at)
        await db_session.flush()

        tracking_start = completed_at.date()

        # 执行前数据 (7天, 每天100kWh, 60元)
        for i in range(7):
            d = tracking_start - timedelta(days=7) + timedelta(days=i)
            db_session.add(EnergyDaily(
                device_id=1, stat_date=d, total_energy=100, energy_cost=60
            ))

        # 执行后数据 (7天, 每天80kWh, 48元)
        for i in range(7):
            d = tracking_start + timedelta(days=i)
            db_session.add(EnergyDaily(
                device_id=1, stat_date=d, total_energy=80, energy_cost=48
            ))

        await db_session.commit()

        tracker = EffectTracker(db_session)
        effect = await tracker._calculate_energy_comparison_effect(
            device_ids=[], tracking_start=tracking_start,
            tracking_end=tracking_start + timedelta(days=7), tracking_days=7
        )

        # 前7天总能耗700, 后7天总能耗560, 节省140
        assert effect['energy_saved'] == pytest.approx(140.0)
        # 前7天总费用420, 后7天总费用336, 节省84
        assert effect['cost_saved'] == pytest.approx(84.0)
        assert effect['calculation_method'] == 'energy_comparison'
        # 年化: (84/7)*250 = 3000
        assert effect['actual_annual'] == pytest.approx(3000.0)


# ==================== 3. 负荷转移效果计算 ====================


class TestLoadShiftEffect:

    @pytest.mark.anyio
    async def test_calculate_load_shift_effect(self, db_session):
        """提供 analysis_data 验证负荷转移计算"""
        analysis_data = {
            'device_rules': [
                {
                    'device_name': '空压机1',
                    'device_id': 10,
                    'rules': [
                        {
                            'source_period': 'peak',
                            'target_period': 'valley',
                            'power': 100,
                            'hours': 4,
                        }
                    ]
                }
            ]
        }

        tracker = EffectTracker(db_session)
        tracking_start = date.today() - timedelta(days=7)
        tracking_end = date.today()

        effect = await tracker._calculate_load_shift_effect(
            analysis_data, tracking_days=7,
            tracking_start=tracking_start, tracking_end=tracking_end
        )

        assert effect['calculation_method'] == 'load_shift'
        # power=100, hours=4, energy=400kWh/day
        # default prices: peak=0.95, valley=0.35, diff=0.60
        # daily_saving = 400 * 0.60 = 240
        # annual = 240 * 250 = 60000
        assert effect['actual_annual'] == pytest.approx(60000.0)
        assert effect['device_filtered'] is True


# ==================== 4. 标记完成追踪 ====================


class TestMarkCompletedTracking:

    @pytest.mark.anyio
    async def test_mark_completed_tracking(self, db_session):
        """tracking_end 在过去的 tracking 记录应被标记为 completed"""
        opp = _create_opportunity(db_session)
        await db_session.flush()
        plan = _create_plan(db_session, opp.id)
        await db_session.flush()

        result = ExecutionResult(
            plan_id=plan.id,
            tracking_period=7,
            tracking_start=date.today() - timedelta(days=14),
            tracking_end=date.today() - timedelta(days=7),
            actual_saving=5000,
            achievement_rate=50.0,
            status="tracking",
        )
        db_session.add(result)
        await db_session.commit()

        tracker = EffectTracker(db_session)
        count = await tracker._mark_completed_tracking()
        assert count >= 1

        # 验证状态已更新
        await db_session.refresh(result)
        assert result.status == "completed"


# ==================== 5. 设备ID提取 ====================


class TestExtractDeviceIds:

    @pytest.mark.anyio
    async def test_extract_device_ids(self, db_session):
        """从各种参数格式中提取设备ID"""
        opp = _create_opportunity(db_session)
        await db_session.flush()
        plan = _create_plan(db_session, opp.id)
        await db_session.flush()

        # 任务1: selected_devices 为 int 列表
        t1 = ExecutionTask(
            plan_id=plan.id, task_type='load_shift', task_name='t1',
            parameters={'selected_devices': [1, 2, 3]}, status='pending'
        )
        # 任务2: selected_devices 为 dict 列表
        t2 = ExecutionTask(
            plan_id=plan.id, task_type='load_shift', task_name='t2',
            parameters={'selected_devices': [{'device_id': 4}]}, status='pending'
        )
        # 任务3: target_object 为 "device:5"
        t3 = ExecutionTask(
            plan_id=plan.id, task_type='load_shift', task_name='t3',
            target_object='device:5', parameters={}, status='pending'
        )
        # 任务4: parameters.device_id
        t4 = ExecutionTask(
            plan_id=plan.id, task_type='load_shift', task_name='t4',
            parameters={'device_id': 6}, status='pending'
        )
        db_session.add_all([t1, t2, t3, t4])
        await db_session.commit()

        # 使用 SimpleNamespace 模拟 plan 对象避免 lazy load 问题
        from types import SimpleNamespace
        mock_plan = SimpleNamespace(tasks=[t1, t2, t3, t4])

        tracker = EffectTracker(db_session)
        ids = tracker._extract_device_ids(mock_plan)
        assert set(ids) == {1, 2, 3, 4, 5, 6}


# ==================== 6. 达成率 clamp ====================


class TestAchievementRateClamp:

    @pytest.mark.anyio
    async def test_achievement_rate_clamp(self, db_session):
        """actual_annual 远超 expected_saving 时，achievement_rate 应 clamp 到 999.99"""
        opp = _create_opportunity(db_session)
        await db_session.flush()
        plan = _create_plan(db_session, opp.id, expected_saving=100)
        await db_session.flush()
        await db_session.commit()

        tracker = EffectTracker(db_session)
        effect = {
            'actual_annual': 200000,
            'tracking_days': 7,
            'tracking_start': date.today() - timedelta(days=7),
            'tracking_end': date.today(),
            'energy_before': [],
            'energy_after': [],
        }
        await tracker._save_tracking_result(plan, effect)
        await db_session.commit()

        # 查询保存的结果
        res = await db_session.execute(
            select(ExecutionResult).where(ExecutionResult.plan_id == plan.id)
        )
        record = res.scalar_one()
        assert float(record.achievement_rate) == pytest.approx(999.99)


# ==================== 7. 无已完成计划 ====================


class TestRunTrackingEmpty:

    @pytest.mark.anyio
    async def test_run_tracking_no_completed_plans(self, db_session):
        """无已完成计划时应返回 {new_tracking: 0, marked_completed: 0}"""
        tracker = EffectTracker(db_session)
        result = await tracker.run_tracking()
        assert result['new_tracking'] == 0
        assert result['marked_completed'] == 0


# ==================== 8. execute_opportunity analysis_data fallback ====================


class TestExecuteOpportunityFallback:

    @pytest.mark.anyio
    async def test_execute_opportunity_with_analysis_data(self, db_session, session_factory):
        """无 measures 但有 analysis_data 的机会应从 analysis_data 生成任务"""
        from httpx import AsyncClient, ASGITransport
        from app.main import app
        from app.api.deps import get_db, get_current_user
        from app.models.user import User

        # 创建机会（无 measures，有 analysis_data）
        opp = EnergyOpportunity(
            category=1,
            title="峰谷优化测试",
            description="测试",
            priority="high",
            status="discovered",
            potential_saving=10000,
            confidence=0.85,
            source_plugin="peak_valley_optimizer",
            analysis_data={
                'device_rules': [
                    {
                        'device_name': '空压机1',
                        'device_id': 10,
                        'rules': [
                            {
                                'source_period': 'peak',
                                'target_period': 'valley',
                                'power': 100,
                                'hours': 4,
                            }
                        ]
                    }
                ]
            },
        )
        db_session.add(opp)
        await db_session.commit()
        await db_session.refresh(opp)
        opp_id = opp.id

        # 覆盖依赖
        async def override_get_db():
            async with session_factory() as session:
                yield session

        mock_admin = User(
            id=1, username="admin", password_hash="x",
            real_name="管理员", role="admin", is_active=True
        )

        async def override_get_current_user():
            return mock_admin

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(f"/api/v1/opportunities/{opp_id}/execute")
                assert resp.status_code == 200
                body = resp.json()
                assert body["task_count"] >= 1
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_execute_opportunity_with_measures_regression(self, db_session, session_factory):
        """有 measures 的机会应从 measures 生成任务（回归测试）"""
        from httpx import AsyncClient, ASGITransport
        from app.main import app
        from app.api.deps import get_db, get_current_user
        from app.models.user import User
        from app.models.energy import OpportunityMeasure

        # 创建机会 + measures
        opp = EnergyOpportunity(
            category=2,
            title="设备调节测试",
            description="测试",
            priority="medium",
            status="ready",
            potential_saving=5000,
            confidence=0.80,
            source_plugin="device_optimizer",
            analysis_data={},
        )
        db_session.add(opp)
        await db_session.flush()

        measure = OpportunityMeasure(
            opportunity_id=opp.id,
            measure_type="temp_adjust",
            measure_name="调节空调温度",
            regulation_object="精密空调#1",
            execution_mode="manual",
            sort_order=0,
        )
        db_session.add(measure)
        await db_session.commit()
        await db_session.refresh(opp)
        opp_id = opp.id

        # 覆盖依赖
        async def override_get_db():
            async with session_factory() as session:
                yield session

        mock_admin = User(
            id=1, username="admin", password_hash="x",
            real_name="管理员", role="admin", is_active=True
        )

        async def override_get_current_user():
            return mock_admin

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(f"/api/v1/opportunities/{opp_id}/execute")
                assert resp.status_code == 200
                body = resp.json()
                # 应从 measures 生成1个任务
                assert body["task_count"] == 1
        finally:
            app.dependency_overrides.clear()
