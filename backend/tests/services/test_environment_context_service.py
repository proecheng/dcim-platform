"""
环境上下文服务测试
Story 25.6: 动态告警阈值
"""

import pytest
import time
from datetime import datetime
from app.services.diagnosis.environment_context_service import EnvironmentContextService


class TestEnvironmentContextService:
    """环境上下文服务测试"""

    @pytest.fixture(autouse=True)
    async def setup(self):
        """每个测试前清除缓存"""
        await EnvironmentContextService.clear_cache()
        yield
        await EnvironmentContextService.clear_cache()

    def test_get_current_season_spring(self):
        """测试春季判断（3-5月）"""
        # Mock datetime
        import app.services.diagnosis.environment_context_service as module
        original_datetime = module.datetime

        class MockDatetime:
            @staticmethod
            def now():
                class MockNow:
                    month = 4
                return MockNow()

        module.datetime = MockDatetime
        try:
            season = EnvironmentContextService._get_current_season()
            assert season == "spring"
        finally:
            module.datetime = original_datetime

    def test_get_current_season_summer(self):
        """测试夏季判断（6-8月）"""
        import app.services.diagnosis.environment_context_service as module
        original_datetime = module.datetime

        class MockDatetime:
            @staticmethod
            def now():
                class MockNow:
                    month = 7
                return MockNow()

        module.datetime = MockDatetime
        try:
            season = EnvironmentContextService._get_current_season()
            assert season == "summer"
        finally:
            module.datetime = original_datetime

    def test_get_current_season_autumn(self):
        """测试秋季判断（9-11月）"""
        import app.services.diagnosis.environment_context_service as module
        original_datetime = module.datetime

        class MockDatetime:
            @staticmethod
            def now():
                class MockNow:
                    month = 10
                return MockNow()

        module.datetime = MockDatetime
        try:
            season = EnvironmentContextService._get_current_season()
            assert season == "autumn"
        finally:
            module.datetime = original_datetime

    def test_get_current_season_winter(self):
        """测试冬季判断（12-2月）"""
        import app.services.diagnosis.environment_context_service as module
        original_datetime = module.datetime

        class MockDatetime:
            @staticmethod
            def now():
                class MockNow:
                    month = 1
                return MockNow()

        module.datetime = MockDatetime
        try:
            season = EnvironmentContextService._get_current_season()
            assert season == "winter"
        finally:
            module.datetime = original_datetime

    @pytest.mark.asyncio
    async def test_get_context_returns_default_values(self):
        """测试 Redis 不可用时返回默认值"""
        context = await EnvironmentContextService.get_context()

        assert "outdoor_temp" in context
        assert "it_load_percent" in context
        assert "season" in context
        assert "timestamp" in context

        # 默认值检查
        assert context["outdoor_temp"] == 25.0
        assert context["it_load_percent"] == 50.0
        assert context["season"] in ["spring", "summer", "autumn", "winter"]
        assert isinstance(context["timestamp"], float)

    @pytest.mark.asyncio
    async def test_cache_validity(self):
        """测试缓存有效性"""
        # 第一次调用
        context1 = await EnvironmentContextService.get_context()
        timestamp1 = context1["timestamp"]

        # 立即第二次调用（应该使用缓存）
        context2 = await EnvironmentContextService.get_context()
        timestamp2 = context2["timestamp"]

        assert timestamp1 == timestamp2, "缓存应该生效"

        # 等待缓存过期（61秒）
        EnvironmentContextService._cache["timestamp"] = time.time() - 61

        # 第三次调用（缓存已过期）
        context3 = await EnvironmentContextService.get_context()
        timestamp3 = context3["timestamp"]

        assert timestamp3 > timestamp1, "缓存过期后应该重新加载"

    @pytest.mark.asyncio
    async def test_clear_cache(self):
        """测试清除缓存"""
        # 加载上下文
        await EnvironmentContextService.get_context()
        assert EnvironmentContextService._cache, "缓存应该存在"

        # 清除缓存
        await EnvironmentContextService.clear_cache()
        assert not EnvironmentContextService._cache, "缓存应该被清除"
