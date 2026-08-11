"""自动运行报表 API 测试 (Story 12-1)"""

import pytest

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import delete

from app.core.database import Base
from app.models.report import ReportRecord, ReportSchedule, DeviceHealthScore
from app.models.device import Device
from app.models.alarm import Alarm
from app.models.user import User
from app.api.deps import (
    SiteAccessContext,
    enforce_inventory_authorization,
    get_db,
    get_site_access_context,
    require_admin,
    require_operator,
    require_viewer,
)


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
        await session.execute(delete(DeviceHealthScore))
        await session.execute(delete(ReportSchedule))
        await session.execute(delete(ReportRecord))
        await session.execute(delete(Alarm))
        await session.execute(delete(Device))
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
async def app(db_session, mock_admin):
    from app.main import app as _app

    async def override_get_db():
        yield db_session

    async def override_require_admin():
        return mock_admin

    async def override_require_operator():
        return mock_admin

    async def override_require_viewer():
        return mock_admin

    async def override_inventory_authorization():
        return None

    async def override_site_access_context():
        return SiteAccessContext(user_id=mock_admin.id, role="admin", jti="report-test-jti", site_ids=None)

    _app.dependency_overrides[get_db] = override_get_db
    _app.dependency_overrides[require_admin] = override_require_admin
    _app.dependency_overrides[require_operator] = override_require_operator
    _app.dependency_overrides[require_viewer] = override_require_viewer
    _app.dependency_overrides[enforce_inventory_authorization] = override_inventory_authorization
    _app.dependency_overrides[get_site_access_context] = override_site_access_context
    yield _app
    _app.dependency_overrides.clear()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ============================================================
# Constants
# ============================================================

AUTO_URL = "/api/v1/reports/auto-generate"
SCHEDULES_URL = "/api/v1/reports/schedules"
RECORDS_URL = "/api/v1/reports/records"


# ============================================================
# Tests
# ============================================================


@pytest.mark.anyio
async def test_auto_generate_daily(client):
    """自动生成日报"""
    resp = await client.post(AUTO_URL, json={"report_type": "daily"})
    assert resp.status_code == 200
    data = resp.json()
    assert "record_id" in data
    assert "report_name" in data
    assert "data" in data
    report_data = data["data"]
    assert "alarm_trends" in report_data
    assert "energy_comparison" in report_data
    assert "workorder_stats" in report_data
    assert "device_availability" in report_data
    assert "comparison" in report_data


@pytest.mark.anyio
async def test_auto_generate_weekly(client):
    """自动生成周报"""
    resp = await client.post(AUTO_URL, json={"report_type": "weekly"})
    assert resp.status_code == 200
    report_data = resp.json()["data"]
    assert "alarm_trends" in report_data
    assert "energy_comparison" in report_data
    assert "workorder_stats" in report_data
    assert "device_availability" in report_data
    assert "comparison" in report_data


@pytest.mark.anyio
async def test_auto_generate_monthly(client):
    """自动生成月报"""
    resp = await client.post(AUTO_URL, json={"report_type": "monthly"})
    assert resp.status_code == 200
    report_data = resp.json()["data"]
    assert "alarm_trends" in report_data
    assert "energy_comparison" in report_data
    assert "workorder_stats" in report_data
    assert "device_availability" in report_data
    assert "comparison" in report_data


@pytest.mark.anyio
async def test_auto_generate_saves_record(client):
    """自动生成后记录保存到列表"""
    resp = await client.post(AUTO_URL, json={"report_type": "daily"})
    assert resp.status_code == 200

    resp = await client.get(RECORDS_URL)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert any(r["report_type"] == "daily" and r["status"] == "completed" for r in items)


@pytest.mark.anyio
async def test_auto_generate_comparison(client):
    """自动生成报表包含同比环比数据"""
    resp = await client.post(AUTO_URL, json={"report_type": "daily"})
    assert resp.status_code == 200
    comparison = resp.json()["data"]["comparison"]
    assert "alarm_current" in comparison
    assert "alarm_mom_change_percent" in comparison
    assert "alarm_yoy_change_percent" in comparison


@pytest.mark.anyio
async def test_schedule_crud_create(client):
    """创建报表调度"""
    resp = await client.post(SCHEDULES_URL, json={"name": "每日报表", "report_type": "daily"})
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert data["name"] == "每日报表"
    assert data["report_type"] == "daily"
    assert data["is_enabled"] is True


@pytest.mark.anyio
async def test_schedule_crud_list(client):
    """获取报表调度列表"""
    resp = await client.post(SCHEDULES_URL, json={"name": "列表测试", "report_type": "weekly"})
    assert resp.status_code == 200
    schedule_id = resp.json()["id"]

    resp = await client.get(SCHEDULES_URL)
    assert resp.status_code == 200
    items = resp.json()
    assert any(s["id"] == schedule_id for s in items)


@pytest.mark.anyio
async def test_schedule_crud_update(client):
    """更新报表调度"""
    resp = await client.post(SCHEDULES_URL, json={"name": "待更新", "report_type": "daily"})
    assert resp.status_code == 200
    schedule_id = resp.json()["id"]

    resp = await client.put(f"{SCHEDULES_URL}/{schedule_id}", json={"name": "更新名称", "is_enabled": False})
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "更新名称"
    assert data["is_enabled"] is False


@pytest.mark.anyio
async def test_schedule_crud_delete(client):
    """删除报表调度"""
    resp = await client.post(SCHEDULES_URL, json={"name": "待删除", "report_type": "monthly"})
    assert resp.status_code == 200
    schedule_id = resp.json()["id"]

    resp = await client.delete(f"{SCHEDULES_URL}/{schedule_id}")
    assert resp.status_code == 200

    resp = await client.get(SCHEDULES_URL)
    assert resp.status_code == 200
    assert len(resp.json()) == 0


@pytest.mark.anyio
async def test_schedule_create_invalid_type(client):
    """创建调度时使用无效报表类型"""
    resp = await client.post(SCHEDULES_URL, json={"name": "test", "report_type": "invalid"})
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_auto_generate_invalid_type(client):
    """自动生成时使用无效报表类型"""
    resp = await client.post(AUTO_URL, json={"report_type": "invalid"})
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_auto_generate_record_has_data(client):
    """自动生成的记录包含 report_data"""
    resp = await client.post(AUTO_URL, json={"report_type": "daily"})
    assert resp.status_code == 200

    resp = await client.get(RECORDS_URL)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) > 0
    assert items[0]["report_data"] is not None


# ============================================================
# Story 12-2: 智能摘要面板
# ============================================================

SUMMARY_URL = "/api/v1/reports/summary-panel"


@pytest.mark.anyio
async def test_summary_panel_returns_structure(client):
    """摘要面板返回正确结构"""
    resp = await client.get(SUMMARY_URL)
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert "total_items" in body
    assert "generated_at" in body
    assert isinstance(body["items"], list)


@pytest.mark.anyio
async def test_summary_panel_items_have_fields(client):
    """摘要面板项包含必要字段"""
    resp = await client.get(SUMMARY_URL)
    assert resp.status_code == 200
    # 空数据库可能没有待处理项，但结构正确
    for item in resp.json()["items"]:
        assert "type" in item
        assert "title" in item
        assert "priority" in item
        assert "count" in item
        assert "action" in item
        assert "link" in item


@pytest.mark.anyio
async def test_summary_panel_items_sorted_by_priority(client):
    """摘要面板项按优先级排序"""
    resp = await client.get(SUMMARY_URL)
    assert resp.status_code == 200
    items = resp.json()["items"]
    priorities = [item["priority"] for item in items]
    assert priorities == sorted(priorities)


@pytest.mark.anyio
async def test_summary_panel_total_matches(client):
    """total_items 与 items 长度一致"""
    resp = await client.get(SUMMARY_URL)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_items"] == len(body["items"])


# ============================================================
# Story 12-3: PDF 报表导出
# ============================================================

PDF_URL = "/api/v1/reports/auto-report-pdf"


@pytest.mark.anyio
async def test_export_pdf_success(client):
    """导出自动报表 PDF"""
    # 先生成一条报表记录
    gen_resp = await client.post(AUTO_URL, json={"report_type": "daily"})
    assert gen_resp.status_code == 200
    record_id = gen_resp.json()["record_id"]

    # 导出 PDF
    pdf_resp = await client.get(f"{PDF_URL}/{record_id}")
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"] == "application/pdf"
    assert len(pdf_resp.content) > 0


@pytest.mark.anyio
async def test_export_pdf_not_found(client):
    """导出不存在的记录返回 404"""
    resp = await client.get(f"{PDF_URL}/99999")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_export_pdf_content_disposition(client):
    """PDF 响应包含 Content-Disposition"""
    gen_resp = await client.post(AUTO_URL, json={"report_type": "weekly"})
    assert gen_resp.status_code == 200
    record_id = gen_resp.json()["record_id"]

    pdf_resp = await client.get(f"{PDF_URL}/{record_id}")
    assert pdf_resp.status_code == 200
    assert "content-disposition" in pdf_resp.headers
    assert ".pdf" in pdf_resp.headers["content-disposition"]


# ============================================================
# Story 12-4: 设备健康度评估
# ============================================================

HEALTH_CALC_URL = "/api/v1/reports/device-health/calculate"
HEALTH_LIST_URL = "/api/v1/reports/device-health"


@pytest.mark.anyio
async def test_calculate_device_health_empty_db(client):
    """空数据库计算设备健康度 — 返回 0 设备"""
    resp = await client.post(HEALTH_CALC_URL)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_devices" in data
    assert "calculated_at" in data
    assert "summary" in data
    assert data["total_devices"] == 0
    assert data["summary"]["健康"] == 0


@pytest.mark.anyio
async def test_device_health_list_empty(client):
    """计算前获取健康度列表 — 空列表"""
    resp = await client.get(HEALTH_LIST_URL)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 0


@pytest.mark.anyio
async def test_device_health_list_after_calculate(client, db_session):
    """计算后获取健康度列表"""
    # 插入测试设备
    device = Device(
        device_name="测试设备A", device_type="UPS", device_code="TEST-A-001", area_code="A01", status="online"
    )
    db_session.add(device)
    await db_session.commit()
    await db_session.refresh(device)

    # 计算健康度
    calc_resp = await client.post(HEALTH_CALC_URL)
    assert calc_resp.status_code == 200
    assert calc_resp.json()["total_devices"] >= 1

    # 获取列表
    list_resp = await client.get(HEALTH_LIST_URL)
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert len(items) >= 1
    item = next((i for i in items if i["device_id"] == device.id), None)
    assert item is not None
    assert item["device_name"] == "测试设备A"
    assert item["score"] == 100.0
    assert item["health_level"] == "健康"


@pytest.mark.anyio
async def test_device_health_single_not_found(client):
    """获取不存在设备的健康度 — 404"""
    resp = await client.get(f"{HEALTH_LIST_URL}/99999")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_device_health_filter_level(client, db_session):
    """按健康等级筛选"""
    device = Device(
        device_name="筛选设备", device_type="空调", device_code="FILTER-001", area_code="A01", status="online"
    )
    db_session.add(device)
    await db_session.commit()

    await client.post(HEALTH_CALC_URL)

    # 筛选"健康"等级（无告警设备得分100，属于"健康"）
    resp = await client.get(HEALTH_LIST_URL, params={"health_level": "健康"})
    assert resp.status_code == 200
    items = resp.json()
    for item in items:
        assert item["health_level"] == "健康"

    # 筛选"危险"等级 — 无告警设备不会出现
    resp = await client.get(HEALTH_LIST_URL, params={"health_level": "危险"})
    assert resp.status_code == 200
    items = resp.json()
    for item in items:
        assert item["health_level"] == "危险"


@pytest.mark.anyio
async def test_device_health_sort_order(client, db_session):
    """按分数排序"""
    d1 = Device(device_name="排序设备1", device_type="UPS", device_code="SORT-001", area_code="A01", status="online")
    d2 = Device(device_name="排序设备2", device_type="空调", device_code="SORT-002", area_code="A01", status="online")
    db_session.add_all([d1, d2])
    await db_session.commit()

    await client.post(HEALTH_CALC_URL)

    # 升序
    resp = await client.get(HEALTH_LIST_URL, params={"sort_by": "score", "sort_order": "asc"})
    assert resp.status_code == 200
    items = resp.json()
    scores = [i["score"] for i in items]
    assert scores == sorted(scores)

    # 降序
    resp = await client.get(HEALTH_LIST_URL, params={"sort_by": "score", "sort_order": "desc"})
    assert resp.status_code == 200
    items = resp.json()
    scores = [i["score"] for i in items]
    assert scores == sorted(scores, reverse=True)
