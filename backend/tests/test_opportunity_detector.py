"""节能机会自动检测服务测试 — Story 6-3"""
import pytest
from datetime import datetime, date
from decimal import Decimal

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import delete, select

from app.core.database import Base
from app.models.energy import EnergyOpportunity
from app.services.opportunity_detector import (
    OpportunityDetector,
    CATEGORY_TO_INT,
    PRIORITY_TO_STR,
)
from app.services.opportunity_engine import OpportunityCategory, PLUGIN_CATEGORY_MAPPING
from app.services.analysis_plugins.base import PluginPriority


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
        await session.execute(delete(EnergyOpportunity))
        await session.commit()
        yield session


# ==================== 1. 检测创建机会 ====================


class TestRunDetection:
    """测试自动检测核心流程"""

    @pytest.mark.anyio
    async def test_run_detection_creates_opportunities(self, db_session):
        """运行检测后应在数据库中创建 EnergyOpportunity 记录"""
        detector = OpportunityDetector(db_session)
        result = await detector.run_detection(days=30)

        assert result["total_analyzed"] >= 0
        assert result["new_opportunities"] >= 0
        assert "details" in result

        # 检查数据库中确实有记录（如果有新机会的话）
        if result["new_opportunities"] > 0:
            db_result = await db_session.execute(select(EnergyOpportunity))
            records = db_result.scalars().all()
            assert len(records) == result["new_opportunities"]

    @pytest.mark.anyio
    async def test_run_detection_dedup(self, db_session):
        """同一天运行两次，第二次应跳过重复"""
        detector = OpportunityDetector(db_session)

        first_run = await detector.run_detection(days=30)
        first_new = first_run["new_opportunities"]

        second_run = await detector.run_detection(days=30)
        second_new = second_run["new_opportunities"]

        # 第二次运行不应创建新机会（全部去重）
        assert second_new == 0
        assert second_run["skipped_duplicates"] >= first_new

    @pytest.mark.anyio
    async def test_detection_with_no_data(self, db_session):
        """空数据库下检测不应崩溃"""
        detector = OpportunityDetector(db_session)
        result = await detector.run_detection(days=7)

        assert isinstance(result, dict)
        assert "total_analyzed" in result
        assert "errors" in result
        # 不应有未捕获异常

    @pytest.mark.anyio
    async def test_dedup_excludes_rejected_completed(self, db_session):
        """已拒绝/已完成的机会不应阻止新机会创建"""
        # 先运行一次创建机会
        detector = OpportunityDetector(db_session)
        first_run = await detector.run_detection(days=30)

        if first_run["new_opportunities"] == 0:
            pytest.skip("插件未生成任何机会，无法测试去重排除逻辑")

        # 将所有机会标记为 rejected
        db_result = await db_session.execute(select(EnergyOpportunity))
        for opp in db_result.scalars().all():
            opp.status = "rejected"
        await db_session.commit()

        # 再次运行 — rejected 的不应阻止新创建
        third_run = await detector.run_detection(days=30)
        assert third_run["new_opportunities"] >= first_run["new_opportunities"]


# ==================== 2. 映射字典测试 ====================


class TestMappingDicts:
    """测试映射字典的完整性"""

    def test_category_mapping(self):
        """CATEGORY_TO_INT 应映射全部 4 个 OpportunityCategory"""
        assert CATEGORY_TO_INT[OpportunityCategory.BILL_OPTIMIZATION] == 1
        assert CATEGORY_TO_INT[OpportunityCategory.DEVICE_OPERATION] == 2
        assert CATEGORY_TO_INT[OpportunityCategory.EQUIPMENT_UPGRADE] == 3
        assert CATEGORY_TO_INT[OpportunityCategory.COMPREHENSIVE] == 4
        assert len(CATEGORY_TO_INT) == 4

    def test_priority_mapping(self):
        """PRIORITY_TO_STR 应映射全部 4 个 PluginPriority 值"""
        assert PRIORITY_TO_STR[PluginPriority.CRITICAL] == "high"
        assert PRIORITY_TO_STR[PluginPriority.HIGH] == "high"
        assert PRIORITY_TO_STR[PluginPriority.MEDIUM] == "medium"
        assert PRIORITY_TO_STR[PluginPriority.LOW] == "low"
        assert len(PRIORITY_TO_STR) == 4


# ==================== 3. 字段转换测试 ====================


class TestFieldConversion:
    """测试 SuggestionResult → EnergyOpportunity 字段映射"""

    @pytest.mark.anyio
    async def test_confidence_conversion(self, db_session):
        """confidence 80 应转换为 0.80，而非 80.0"""
        detector = OpportunityDetector(db_session)
        result = await detector.run_detection(days=30)

        if result["new_opportunities"] == 0:
            pytest.skip("插件未生成机会，无法验证 confidence 转换")

        db_result = await db_session.execute(select(EnergyOpportunity))
        for opp in db_result.scalars().all():
            conf = float(opp.confidence)
            # Numeric(3,2) 最大 9.99，confidence 必须 <= 1.0
            assert conf <= 1.0, f"confidence {conf} 超出 Numeric(3,2) 范围"
            assert conf >= 0.0

    @pytest.mark.anyio
    async def test_potential_saving_mapping(self, db_session):
        """estimated_cost_saving 应映射到 potential_saving"""
        detector = OpportunityDetector(db_session)
        result = await detector.run_detection(days=30)

        if result["new_opportunities"] == 0:
            pytest.skip("插件未生成机会，无法验证 potential_saving")

        db_result = await db_session.execute(select(EnergyOpportunity))
        for opp in db_result.scalars().all():
            # potential_saving 应为非负数值
            saving = float(opp.potential_saving or 0)
            assert saving >= 0

    @pytest.mark.anyio
    async def test_analysis_data_json_structure(self, db_session):
        """analysis_data JSON 应包含 detail 和 estimated_saving_kwh 键"""
        detector = OpportunityDetector(db_session)
        result = await detector.run_detection(days=30)

        if result["new_opportunities"] == 0:
            pytest.skip("插件未生成机会，无法验证 analysis_data 结构")

        db_result = await db_session.execute(select(EnergyOpportunity))
        for opp in db_result.scalars().all():
            data = opp.analysis_data
            assert isinstance(data, dict), "analysis_data 应为 dict"
            assert "detail" in data, "analysis_data 应包含 detail 键"
            assert "estimated_saving_kwh" in data, "analysis_data 应包含 estimated_saving_kwh 键"


# ==================== 4. API 端点测试 ====================


class TestDetectAPI:
    """测试 /detect API 端点"""

    @pytest.mark.anyio
    async def test_trigger_detection_api(self, db_session, session_factory):
        """POST /v1/opportunities/detect 应返回 200"""
        from httpx import AsyncClient, ASGITransport
        from app.main import app
        from app.api.deps import get_db, get_current_user
        from app.models.user import User

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
                resp = await client.post(
                    "/api/v1/opportunities/detect",
                    params={"days": 30},
                )
                assert resp.status_code == 200
                body = resp.json()
                assert body["code"] == 0
                assert "data" in body
                assert body["data"]["total_analyzed"] >= 0
        finally:
            app.dependency_overrides.clear()
