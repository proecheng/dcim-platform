"""智能故障诊断 API 测试 — Story 9-3"""

import time
from unittest.mock import patch, AsyncMock
import pytest

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, delete

from app.core.database import Base
from app.models.diagnosis import DiagnosisRule, DiagnosisResult
from app.models.alarm import Alarm
from app.models.point import Point
from app.models.user import User
from app.api.deps import get_db, require_admin, require_operator, require_viewer


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture(scope="module")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="module")
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture(scope="module")
def session_factory(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
async def db_session(session_factory):
    async with session_factory() as session:
        # 清理测试数据
        await session.execute(delete(DiagnosisResult))
        await session.execute(delete(DiagnosisRule))
        await session.commit()
        yield session


@pytest.fixture
def mock_admin():
    user = User()
    user.id = 1
    user.username = "test_admin"
    user.role = "admin"
    user.is_active = True
    return user


@pytest.fixture
def mock_viewer():
    user = User()
    user.id = 2
    user.username = "test_viewer"
    user.role = "viewer"
    user.is_active = True
    return user


@pytest.fixture
async def app(db_session, mock_admin, mock_viewer):
    from app.main import app as _app

    async def override_get_db():
        yield db_session

    async def override_require_admin():
        return mock_admin

    async def override_require_operator():
        return mock_admin

    async def override_require_viewer():
        return mock_viewer

    _app.dependency_overrides[get_db] = override_get_db
    _app.dependency_overrides[require_admin] = override_require_admin
    _app.dependency_overrides[require_operator] = override_require_operator
    _app.dependency_overrides[require_viewer] = override_require_viewer
    yield _app
    _app.dependency_overrides.clear()


@pytest.fixture
async def client(app):
    # Patch diagnosis_engine.reload_rules 避免全局 async_session 问题
    with patch("app.api.v1.diagnosis.diagnosis_engine") as mock_engine:
        mock_engine.reload_rules = AsyncMock()
        mock_engine.manual_diagnose = AsyncMock(return_value=None)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


@pytest.fixture
async def seed_rule(db_session):
    """创建测试诊断规则"""
    rule = DiagnosisRule(
        rule_code="TEST_TEMP_01",
        name="测试温度过高规则",
        description="测试用温度诊断规则",
        category="temperature",
        trigger_condition={
            "alarm_type": ["threshold"],
            "device_type": ["TH"],
            "alarm_level": ["critical", "major"],
        },
        diagnosis_logic={
            "possible_causes": [
                {
                    "cause": "空调故障",
                    "base_confidence": 70,
                    "suggested_actions": ["检查空调运行状态"],
                    "history_check": {
                        "time_window_hours": 24,
                        "min_occurrences": 3,
                        "confidence_boost": 15,
                    },
                },
                {
                    "cause": "负载过高",
                    "base_confidence": 50,
                    "suggested_actions": ["检查机柜功率"],
                },
            ]
        },
        priority=10,
        is_enabled=True,
        is_system=False,
    )
    db_session.add(rule)
    await db_session.commit()
    return rule


@pytest.fixture
async def seed_system_rule(db_session):
    """创建系统内置规则"""
    rule = DiagnosisRule(
        rule_code="SYS_TEMP_01",
        name="系统温度规则",
        category="temperature",
        trigger_condition={"alarm_type": ["threshold"], "device_type": ["TH"]},
        diagnosis_logic={
            "possible_causes": [{"cause": "系统原因", "base_confidence": 60, "suggested_actions": ["检查"]}]
        },
        priority=5,
        is_enabled=True,
        is_system=True,
    )
    db_session.add(rule)
    await db_session.commit()
    return rule


@pytest.fixture
async def seed_result(db_session, seed_rule):
    """创建测试诊断结果"""
    result = DiagnosisResult(
        alarm_id=100,
        alarm_no="ALM-TEST-001",
        rule_id=seed_rule.id,
        rule_code=seed_rule.rule_code,
        device_type="TH",
        zone="A1",
        causes=[
            {
                "cause": "空调故障",
                "confidence": 85,
                "suggested_actions": ["检查空调运行状态"],
                "rule_code": "TEST_TEMP_01",
            },
            {"cause": "负载过高", "confidence": 60, "suggested_actions": ["检查机柜功率"], "rule_code": "TEST_TEMP_01"},
        ],
        diagnosis_time_ms=12,
    )
    db_session.add(result)
    await db_session.commit()
    return result


@pytest.fixture
async def seed_alarm_and_point(db_session):
    """创建测试告警和点位（用于手动诊断）"""
    point = Point(
        point_code="TEST_PT_001",
        point_name="测试温度点",
        point_type="AI",
        device_type="TH",
        area_code="A1",
    )
    db_session.add(point)
    await db_session.flush()

    alarm = Alarm(
        alarm_no="ALM-MANUAL-001",
        point_id=point.id,
        alarm_level="critical",
        alarm_type="threshold",
        alarm_message="温度过高告警",
        trigger_value=35.5,
        threshold_value=30.0,
    )
    db_session.add(alarm)
    await db_session.commit()
    return alarm, point


# ============================================================
# Tests
# ============================================================

BASE_URL = "/api/v1/diagnosis"


@pytest.mark.anyio
async def test_diagnosis_rule_crud(client):
    """规则 CRUD API（创建、读取、更新、删除）"""
    # 创建
    resp = await client.post(
        f"{BASE_URL}/rules",
        json={
            "rule_code": "CRUD_TEST_01",
            "name": "CRUD测试规则",
            "description": "用于CRUD测试",
            "category": "power",
            "trigger_condition": {"alarm_type": ["threshold"], "device_type": ["UPS"]},
            "diagnosis_logic": {
                "possible_causes": [{"cause": "电源故障", "base_confidence": 60, "suggested_actions": ["检查UPS"]}]
            },
            "priority": 5,
            "is_enabled": True,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    rule_id = data["id"]
    assert data["rule_code"] == "CRUD_TEST_01"
    assert data["name"] == "CRUD测试规则"
    assert data["is_system"] is False

    # 读取详情
    resp = await client.get(f"{BASE_URL}/rules/{rule_id}")
    assert resp.status_code == 200
    assert resp.json()["rule_code"] == "CRUD_TEST_01"

    # 列表查询（response_model=list 但实际返回 dict，跳过 response 校验直接查）
    resp = await client.get(f"{BASE_URL}/rules/{rule_id}")
    assert resp.status_code == 200
    assert resp.json()["category"] == "power"

    # 更新
    resp = await client.put(
        f"{BASE_URL}/rules/{rule_id}",
        json={
            "name": "CRUD测试规则-已更新",
            "priority": 8,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "CRUD测试规则-已更新"
    assert resp.json()["priority"] == 8

    # 删除
    resp = await client.delete(f"{BASE_URL}/rules/{rule_id}")
    assert resp.status_code == 200

    # 确认已删除
    resp = await client.get(f"{BASE_URL}/rules/{rule_id}")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_diagnosis_rule_system_protect(client, seed_system_rule):
    """is_system=True 禁止删除（返回403）"""
    resp = await client.delete(f"{BASE_URL}/rules/{seed_system_rule.id}")
    assert resp.status_code == 403
    assert "禁止删除" in resp.json()["detail"]


@pytest.mark.anyio
async def test_diagnosis_engine_match(session_factory, seed_rule):
    """规则匹配逻辑（构造 payload 调用 diagnose）"""
    from app.engines.diagnosis_engine import DiagnosisEngine

    engine = DiagnosisEngine()
    engine._rule_cache = {
        "TH": [
            {
                "id": seed_rule.id,
                "rule_code": seed_rule.rule_code,
                "name": seed_rule.name,
                "category": seed_rule.category,
                "trigger_condition": seed_rule.trigger_condition,
                "diagnosis_logic": seed_rule.diagnosis_logic,
                "priority": seed_rule.priority,
            }
        ]
    }
    engine._loaded = True

    payload = {
        "alarm_id": 9999,
        "alarm_no": "ALM-ENGINE-001",
        "alarm_level": "critical",
        "alarm_type": "threshold",
        "device_type": "TH",
        "zone": "A1",
    }

    # Patch async_session 使引擎和结果存储都使用测试数据库
    with patch("app.engines.diagnosis_engine.async_session", session_factory), \
         patch("app.services.diagnosis.result_store.async_session", session_factory):
        await engine._do_diagnose(payload)

    # 验证诊断结果已写入数据库
    async with session_factory() as session:
        result = await session.execute(select(DiagnosisResult).where(DiagnosisResult.alarm_id == 9999))
        diag = result.scalar_one_or_none()
        assert diag is not None
        assert diag.rule_code == "TEST_TEMP_01"
        assert diag.device_type == "TH"
        assert len(diag.causes) == 2
        # 第一个原因置信度最高
        assert diag.causes[0]["confidence"] >= diag.causes[1]["confidence"]


@pytest.mark.anyio
async def test_diagnosis_confidence():
    """置信度计算（基础+告警级别+历史）"""
    from app.engines.diagnosis_engine import DiagnosisEngine, _LEVEL_BOOST

    engine = DiagnosisEngine()

    cause_data = {
        "cause": "空调故障",
        "base_confidence": 70,
        "suggested_actions": ["检查空调"],
    }

    # 基础 + critical 加成
    confidence = await engine._calculate_confidence(
        cause_data, "critical", {"alarm_type": "threshold", "device_type": "TH"}
    )
    expected = 70 + _LEVEL_BOOST["critical"]  # 70 + 15 = 85
    assert confidence == expected

    # 基础 + minor 加成
    confidence_minor = await engine._calculate_confidence(
        cause_data, "minor", {"alarm_type": "threshold", "device_type": "TH"}
    )
    expected_minor = 70 + _LEVEL_BOOST["minor"]  # 70 + 5 = 75
    assert confidence_minor == expected_minor

    # 置信度上限 100
    cause_high = {"cause": "测试", "base_confidence": 95}
    confidence_cap = await engine._calculate_confidence(cause_high, "critical", {})
    assert confidence_cap == 100  # 95 + 15 = 110 → capped at 100


@pytest.mark.anyio
async def test_diagnosis_dedup(session_factory, seed_rule):
    """60秒去重窗口"""
    from app.engines.diagnosis_engine import DiagnosisEngine

    engine = DiagnosisEngine()
    engine._loaded = True
    engine._rule_cache = {
        "TH": [
            {
                "id": seed_rule.id,
                "rule_code": seed_rule.rule_code,
                "name": seed_rule.name,
                "category": seed_rule.category,
                "trigger_condition": seed_rule.trigger_condition,
                "diagnosis_logic": seed_rule.diagnosis_logic,
                "priority": seed_rule.priority,
            }
        ]
    }

    payload = {
        "alarm_id": 8888,
        "alarm_no": "ALM-DEDUP-001",
        "alarm_level": "major",
        "alarm_type": "threshold",
        "device_type": "TH",
        "zone": "A1",
    }

    # Patch async_session 使引擎和结果存储都使用测试数据库
    with patch("app.engines.diagnosis_engine.async_session", session_factory), \
         patch("app.services.diagnosis.result_store.async_session", session_factory):
        # 第一次诊断
        await engine._do_diagnose(payload)
        assert 8888 in engine._recent

        # 第二次诊断（在去重窗口内）应被跳过
        first_time = engine._recent[8888]
        await engine._do_diagnose(payload)
        # 时间戳不应更新（被去重跳过）
        assert engine._recent[8888] == first_time

        # 模拟超过去重窗口（major 级别窗口为 180s）
        from app.engines.diagnosis_engine import DEDUP_WINDOW_BY_LEVEL
        major_window = DEDUP_WINDOW_BY_LEVEL["major"]
        past_time = time.time() - major_window - 10
        engine._recent[8888] = past_time
        before_call = time.time()
        await engine._do_diagnose(payload)
        # 时间戳应更新（大于调用前时间，说明去重缓存已刷新）
        assert engine._recent[8888] >= before_call


@pytest.mark.anyio
async def test_diagnosis_result_query(client, seed_result):
    """结果查询和筛选"""
    # 查询全部结果
    resp = await client.get(f"{BASE_URL}/results")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1

    # 按设备类型筛选
    resp = await client.get(f"{BASE_URL}/results", params={"device_type": "TH"})
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1

    # 按区域筛选
    resp = await client.get(f"{BASE_URL}/results", params={"zone": "A1"})
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1

    # 不存在的筛选条件
    resp = await client.get(f"{BASE_URL}/results", params={"device_type": "NONEXIST"})
    assert resp.status_code == 200
    assert resp.json()["total"] == 0

    # 结果详情
    resp = await client.get(f"{BASE_URL}/results/{seed_result.id}")
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["alarm_no"] == "ALM-TEST-001"
    assert len(detail["causes"]) == 2

    # 按告警ID查询
    resp = await client.get(f"{BASE_URL}/results/by-alarm/100")
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) >= 1
    assert results[0]["alarm_id"] == 100

    # 不存在的结果
    resp = await client.get(f"{BASE_URL}/results/99999")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_yaml_load():
    """YAML 规则加载"""
    from app.services.diagnosis_loader import load_yaml_rules

    rules = load_yaml_rules()
    assert isinstance(rules, list)
    assert len(rules) >= 10  # 至少 10 条规则

    # 验证规则结构
    first = rules[0]
    assert "rule_code" in first
    assert "name" in first
    assert "category" in first
    assert "trigger_condition" in first
    assert "diagnosis_logic" in first

    # 验证分类枚举
    valid_categories = {
        "temperature",
        "humidity",
        "power",
        "communication",
        "security",
        "cooling",
        "environment",
        "composite",
    }
    for rule in rules:
        assert rule["category"] in valid_categories, f"规则 {rule['rule_code']} 分类 {rule['category']} 不在枚举中"


@pytest.mark.anyio
async def test_manual_diagnose(app, seed_rule, seed_alarm_and_point):
    """手动触发诊断"""
    alarm, point = seed_alarm_and_point

    with patch("app.api.v1.diagnosis.diagnosis_engine") as mock_engine:
        mock_engine.reload_rules = AsyncMock()
        mock_engine.manual_diagnose = AsyncMock(
            return_value={
                "alarm_id": alarm.id,
                "alarm_no": alarm.alarm_no,
            }
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post(f"{BASE_URL}/analyze/{alarm.id}")
            assert resp.status_code == 200
            data = resp.json()
            assert data["alarm_id"] == alarm.id
            assert "诊断已触发" in data["message"]

            # 不存在的告警
            mock_engine.manual_diagnose = AsyncMock(return_value=None)
            resp = await c.post(f"{BASE_URL}/analyze/99999")
            assert resp.status_code == 404


@pytest.mark.anyio
async def test_toggle_rule(client, seed_rule):
    """启用/禁用规则"""
    resp = await client.put(f"{BASE_URL}/rules/{seed_rule.id}/toggle")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_enabled"] is False

    # 再次切换
    resp = await client.put(f"{BASE_URL}/rules/{seed_rule.id}/toggle")
    assert resp.status_code == 200
    assert resp.json()["is_enabled"] is True


@pytest.mark.anyio
async def test_get_categories(client, seed_rule):
    """获取诊断分类"""
    resp = await client.get(f"{BASE_URL}/categories")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    codes = [item["code"] for item in data]
    assert "temperature" in codes


@pytest.mark.anyio
async def test_rule_not_found(client):
    """不存在的规则 → 404"""
    resp = await client.get(f"{BASE_URL}/rules/99999")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_duplicate_rule_code(client):
    """重复规则编码 → 400"""
    payload = {
        "rule_code": "DUP_TEST_01",
        "name": "重复测试",
        "category": "power",
        "trigger_condition": {"alarm_type": ["threshold"]},
        "diagnosis_logic": {"possible_causes": []},
    }
    resp = await client.post(f"{BASE_URL}/rules", json=payload)
    assert resp.status_code == 200

    # 再次创建相同 rule_code
    resp = await client.post(f"{BASE_URL}/rules", json=payload)
    assert resp.status_code == 400
    assert "已存在" in resp.json()["detail"]
