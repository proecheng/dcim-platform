"""
电价方案管理系统单元测试
"""

import pytest
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock

from app.models.energy import ElectricityPricing, PricingScheme, SchemePricingRelation
from app.services.pricing_service import PricingService
from tests.conftest import auth_headers


@pytest.fixture
async def sample_pricings(async_db):
    """创建测试电价时段"""
    pricings = [
        ElectricityPricing(
            pricing_name="尖峰时段",
            period_type="sharp",
            price=1.2,
            start_time="10:00",
            end_time="12:00",
            is_enabled=True,
            effective_date=date.today()
        ),
        ElectricityPricing(
            pricing_name="高峰时段",
            period_type="peak",
            price=1.0,
            start_time="08:00",
            end_time="10:00",
            is_enabled=True,
            effective_date=date.today()
        ),
        ElectricityPricing(
            pricing_name="平段时段",
            period_type="normal",
            price=0.7,
            start_time="12:00",
            end_time="18:00",
            is_enabled=True,
            effective_date=date.today()
        ),
        ElectricityPricing(
            pricing_name="低谷时段",
            period_type="valley",
            price=0.4,
            start_time="18:00",
            end_time="08:00",  # 跨日时段
            is_enabled=True,
            effective_date=date.today()
        ),
    ]
    
    for pricing in pricings:
        async_db.add(pricing)
    
    await async_db.flush()
    return pricings


@pytest.fixture
async def complete_pricings(async_db):
    """创建完整覆盖24小时的电价时段"""
    pricings = [
        ElectricityPricing(
            pricing_name="时段1",
            period_type="peak",
            price=1.0,
            start_time="00:00",
            end_time="08:00",
            is_enabled=True,
            effective_date=date.today()
        ),
        ElectricityPricing(
            pricing_name="时段2",
            period_type="normal",
            price=0.7,
            start_time="08:00",
            end_time="18:00",
            is_enabled=True,
            effective_date=date.today()
        ),
        ElectricityPricing(
            pricing_name="时段3",
            period_type="valley",
            price=0.4,
            start_time="18:00",
            end_time="24:00",
            is_enabled=True,
            effective_date=date.today()
        ),
    ]
    
    for pricing in pricings:
        async_db.add(pricing)
    
    await async_db.flush()
    return pricings


@pytest.fixture
async def sample_scheme(async_db, complete_pricings):
    """创建测试方案"""
    scheme = PricingScheme(
        scheme_name="测试方案",
        description="用于测试的电价方案",
        is_active=False,
        effective_date=date.today(),
        expire_date=date.today() + timedelta(days=30)
    )
    async_db.add(scheme)
    await async_db.flush()
    
    # 关联时段
    for pricing in complete_pricings:
        relation = SchemePricingRelation(
            scheme_id=scheme.id,
            pricing_id=pricing.id
        )
        async_db.add(relation)
    
    await async_db.flush()
    return scheme


class TestPricingServiceValidation:
    """方案校验测试"""
    
    async def test_validate_complete_scheme(self, async_db, sample_scheme):
        """测试完整方案校验"""
        service = PricingService(async_db)
        result = await service.validate_scheme(sample_scheme.id)
        
        assert result['valid'] is True
        assert result['coverage'] == 24.0
        assert len(result['conflicts']) == 0
        assert len(result['gaps']) == 0
    
    async def test_validate_incomplete_scheme(self, async_db):
        """测试不完整方案校验"""
        # 创建只覆盖20小时的时段
        pricings = [
            ElectricityPricing(
                pricing_name="时段1",
                period_type="peak",
                price=1.0,
                start_time="08:00",
                end_time="18:00",
                is_enabled=True,
                effective_date=date.today()
            ),
            ElectricityPricing(
                pricing_name="时段2",
                period_type="valley",
                price=0.4,
                start_time="18:00",
                end_time="04:00",  # 跨日，10小时
                is_enabled=True,
                effective_date=date.today()
            ),
        ]
        
        for pricing in pricings:
            async_db.add(pricing)
        await async_db.flush()
        
        # 创建方案
        scheme = PricingScheme(
            scheme_name="不完整方案",
            is_active=False,
            effective_date=date.today()
        )
        async_db.add(scheme)
        await async_db.flush()
        
        for pricing in pricings:
            relation = SchemePricingRelation(
                scheme_id=scheme.id,
                pricing_id=pricing.id
            )
            async_db.add(relation)
        await async_db.flush()
        
        service = PricingService(async_db)
        result = await service.validate_scheme(scheme.id)
        
        assert result['valid'] is False
        assert result['coverage'] == 20.0
        assert len(result['gaps']) > 0
    
    async def test_validate_conflict_scheme(self, async_db):
        """测试有冲突的方案校验"""
        # 创建有重叠的时段
        pricings = [
            ElectricityPricing(
                pricing_name="时段1",
                period_type="peak",
                price=1.0,
                start_time="08:00",
                end_time="12:00",
                is_enabled=True,
                effective_date=date.today()
            ),
            ElectricityPricing(
                pricing_name="时段2",
                period_type="normal",
                price=0.7,
                start_time="10:00",  # 与时段1重叠
                end_time="14:00",
                is_enabled=True,
                effective_date=date.today()
            ),
        ]
        
        for pricing in pricings:
            async_db.add(pricing)
        await async_db.flush()
        
        scheme = PricingScheme(
            scheme_name="冲突方案",
            is_active=False,
            effective_date=date.today()
        )
        async_db.add(scheme)
        await async_db.flush()
        
        for pricing in pricings:
            relation = SchemePricingRelation(
                scheme_id=scheme.id,
                pricing_id=pricing.id
            )
            async_db.add(relation)
        await async_db.flush()
        
        service = PricingService(async_db)
        result = await service.validate_scheme(scheme.id)
        
        assert result['valid'] is False
        assert len(result['conflicts']) > 0
    
    async def test_validate_cross_day_period(self, async_db):
        """测试跨日时段校验"""
        # 创建跨日时段
        pricings = [
            ElectricityPricing(
                pricing_name="白天时段",
                period_type="peak",
                price=1.0,
                start_time="08:00",
                end_time="22:00",
                is_enabled=True,
                effective_date=date.today()
            ),
            ElectricityPricing(
                pricing_name="夜间时段",
                period_type="valley",
                price=0.4,
                start_time="22:00",
                end_time="08:00",  # 跨日
                is_enabled=True,
                effective_date=date.today()
            ),
        ]
        
        for pricing in pricings:
            async_db.add(pricing)
        await async_db.flush()
        
        scheme = PricingScheme(
            scheme_name="跨日方案",
            is_active=False,
            effective_date=date.today()
        )
        async_db.add(scheme)
        await async_db.flush()
        
        for pricing in pricings:
            relation = SchemePricingRelation(
                scheme_id=scheme.id,
                pricing_id=pricing.id
            )
            async_db.add(relation)
        await async_db.flush()
        
        service = PricingService(async_db)
        result = await service.validate_scheme(scheme.id)
        
        assert result['valid'] is True
        assert result['coverage'] == 24.0


class TestPricingSchemeAPI:
    """方案管理 API 测试"""
    
    async def test_get_schemes_empty(self, client, admin_user):
        """测试空方案列表"""
        _, token = admin_user
        resp = await client.get("/api/v1/energy/pricing-schemes", headers=auth_headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body
    
    async def test_create_scheme(self, client, admin_user, complete_pricings):
        """测试创建方案"""
        _, token = admin_user
        
        pricing_ids = [p.id for p in complete_pricings]
        
        resp = await client.post(
            "/api/v1/energy/pricing-schemes",
            headers=auth_headers(token),
            json={
                "scheme_name": "新建方案",
                "description": "测试创建方案",
                "effective_date": date.today().isoformat(),
                "pricing_ids": pricing_ids
            }
        )
        
        assert resp.status_code == 200
        body = resp.json()
        assert "id" in body["data"]
    
    async def test_validate_scheme_api(self, client, admin_user, sample_scheme):
        """测试方案校验 API"""
        _, token = admin_user
        
        resp = await client.post(
            f"/api/v1/energy/pricing-schemes/{sample_scheme.id}/validate",
            headers=auth_headers(token)
        )
        
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["valid"] is True
        assert body["data"]["coverage"] == 24.0
    
    async def test_activate_scheme(self, client, admin_user, sample_scheme):
        """测试激活方案"""
        _, token = admin_user
        
        resp = await client.post(
            f"/api/v1/energy/pricing-schemes/{sample_scheme.id}/activate",
            headers=auth_headers(token)
        )
        
        assert resp.status_code == 200
    
    async def test_activate_invalid_scheme(self, client, admin_user, async_db):
        """测试激活无效方案"""
        _, token = admin_user
        
        # 创建不完整方案
        pricing = ElectricityPricing(
            pricing_name="不完整时段",
            period_type="peak",
            price=1.0,
            start_time="08:00",
            end_time="12:00",
            is_enabled=True,
            effective_date=date.today()
        )
        async_db.add(pricing)
        await async_db.flush()
        
        scheme = PricingScheme(
            scheme_name="无效方案",
            is_active=False,
            effective_date=date.today()
        )
        async_db.add(scheme)
        await async_db.flush()
        
        relation = SchemePricingRelation(
            scheme_id=scheme.id,
            pricing_id=pricing.id
        )
        async_db.add(relation)
        await async_db.flush()
        
        resp = await client.post(
            f"/api/v1/energy/pricing-schemes/{scheme.id}/activate",
            headers=auth_headers(token)
        )
        
        assert resp.status_code == 400
    
    async def test_deactivate_scheme(self, client, admin_user, sample_scheme, async_db):
        """测试停用方案"""
        _, token = admin_user
        
        # 先激活方案
        sample_scheme.is_active = True
        await async_db.commit()
        
        resp = await client.post(
            f"/api/v1/energy/pricing-schemes/{sample_scheme.id}/deactivate",
            headers=auth_headers(token)
        )
        
        assert resp.status_code == 200
    
    async def test_delete_active_scheme(self, client, admin_user, sample_scheme, async_db):
        """测试删除激活方案（应失败）"""
        _, token = admin_user
        
        # 激活方案
        sample_scheme.is_active = True
        await async_db.commit()
        
        resp = await client.delete(
            f"/api/v1/energy/pricing-schemes/{sample_scheme.id}",
            headers=auth_headers(token)
        )
        
        assert resp.status_code == 400
    
    async def test_delete_inactive_scheme(self, client, admin_user, sample_scheme):
        """测试删除未激活方案"""
        _, token = admin_user
        
        resp = await client.delete(
            f"/api/v1/energy/pricing-schemes/{sample_scheme.id}",
            headers=auth_headers(token)
        )
        
        assert resp.status_code == 200


class TestSchemeAutoInvalidation:
    """方案自动失效测试"""
    
    async def test_edit_pricing_invalidates_scheme(self, client, admin_user, sample_scheme, complete_pricings, async_db):
        """测试编辑时段导致方案失效"""
        _, token = admin_user
        
        # 激活方案
        sample_scheme.is_active = True
        await async_db.commit()
        
        # 编辑方案中的一个时段，使其不完整
        pricing = complete_pricings[0]
        
        resp = await client.put(
            f"/api/v1/energy/pricing/{pricing.id}",
            headers=auth_headers(token),
            json={
                "start_time": "00:00",
                "end_time": "04:00"  # 缩短时段
            }
        )
        
        # 方案应该被自动停用
        await async_db.refresh(sample_scheme)
        assert sample_scheme.is_active is False


class TestConcurrentActivation:
    """并发激活测试"""
    
    async def test_concurrent_activation_with_lock(self, async_db, complete_pricings):
        """测试带锁的并发激活"""
        # 创建两个方案
        scheme1 = PricingScheme(
            scheme_name="方案1",
            is_active=False,
            effective_date=date.today()
        )
        scheme2 = PricingScheme(
            scheme_name="方案2",
            is_active=False,
            effective_date=date.today()
        )
        
        async_db.add(scheme1)
        async_db.add(scheme2)
        await async_db.flush()
        
        # 关联时段
        for pricing in complete_pricings:
            async_db.add(SchemePricingRelation(scheme_id=scheme1.id, pricing_id=pricing.id))
            async_db.add(SchemePricingRelation(scheme_id=scheme2.id, pricing_id=pricing.id))
        await async_db.flush()
        
        service = PricingService(async_db)
        
        # 模拟并发激活（实际测试需要真实的 Redis）
        # 这里只测试单个激活逻辑
        await service.activate_scheme(scheme1.id, user_id=1, redis_client=None)
        
        await async_db.refresh(scheme1)
        await async_db.refresh(scheme2)
        
        assert scheme1.is_active is True
        assert scheme2.is_active is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
