"""
运维管理 API 核心测试
"""

import pytest
from datetime import datetime

from app.models.operation import (
    WorkOrder,
    WorkOrderStatus,
    WorkOrderType,
    WorkOrderPriority,
    InspectionPlan,
    InspectionTask,
    InspectionStatus,
    KnowledgeBase,
)
from tests.conftest import auth_headers


@pytest.fixture
async def sample_work_order(async_db):
    """创建测试工单"""
    order = WorkOrder(
        order_no="WO-20260101-001",
        title="测试故障工单",
        description="UPS 告警测试",
        order_type=WorkOrderType.fault,
        priority=WorkOrderPriority.high,
        status=WorkOrderStatus.pending,
        location="A区机房",
        reporter="张三",
    )
    async_db.add(order)
    await async_db.flush()
    return order


@pytest.fixture
async def sample_inspection_plan(async_db):
    """创建测试巡检计划"""
    plan = InspectionPlan(
        name="日常巡检计划",
        description="每日机房巡检",
        frequency="daily",
        location="A区机房",
        check_items='["温度","湿度","UPS状态"]',
        assignee="李四",
        is_active=True,
    )
    async_db.add(plan)
    await async_db.flush()
    return plan


@pytest.fixture
async def sample_inspection_task(async_db, sample_inspection_plan):
    """创建测试巡检任务"""
    task = InspectionTask(
        plan_id=sample_inspection_plan.id,
        task_no="IT-20260101-001",
        status=InspectionStatus.pending,
        assignee="李四",
        scheduled_date=datetime.now(),
    )
    async_db.add(task)
    await async_db.flush()
    return task


@pytest.fixture
async def sample_knowledge(async_db):
    """创建测试知识库条目"""
    kb = KnowledgeBase(
        title="UPS 故障排查指南",
        category="UPS",
        content="1. 检查输入电源 2. 检查电池状态",
        tags="UPS,故障,排查",
        is_published=True,
        author="admin",
    )
    async_db.add(kb)
    await async_db.flush()
    return kb


class TestWorkOrderCRUD:
    """工单 CRUD 测试"""

    async def test_get_work_orders_empty(self, client, admin_user):
        """测试空工单列表"""
        _, token = admin_user
        resp = await client.get(
            "/api/v1/operation/workorders",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_create_work_order(self, client, admin_user):
        """测试创建工单"""
        _, token = admin_user
        resp = await client.post(
            "/api/v1/operation/workorders",
            headers=auth_headers(token),
            json={
                "title": "新建测试工单",
                "description": "空调异常",
                "order_type": "故障报修",
                "priority": "高",
                "location": "B区机房",
                "reporter": "王五",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["title"] == "新建测试工单"
        assert body["order_no"].startswith("WO-")

    async def test_get_work_order_detail(self, client, admin_user, sample_work_order):
        """测试获取工单详情"""
        _, token = admin_user
        resp = await client.get(
            f"/api/v1/operation/workorders/{sample_work_order.id}",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["order_no"] == "WO-20260101-001"
        assert body["title"] == "测试故障工单"

    async def test_get_work_order_not_found(self, client, admin_user):
        """测试工单不存在"""
        _, token = admin_user
        resp = await client.get(
            "/api/v1/operation/workorders/99999",
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_get_work_orders_filter_status(self, client, admin_user, sample_work_order):
        """测试按状态筛选工单"""
        _, token = admin_user
        resp = await client.get(
            "/api/v1/operation/workorders?status=待处理",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) >= 1

    async def test_update_work_order(self, client, admin_user, sample_work_order):
        """测试更新工单"""
        _, token = admin_user
        resp = await client.put(
            f"/api/v1/operation/workorders/{sample_work_order.id}",
            headers=auth_headers(token),
            json={"title": "更新后的工单标题", "remarks": "测试备注"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["title"] == "更新后的工单标题"

    async def test_assign_work_order(self, client, admin_user, sample_work_order):
        """测试派单"""
        _, token = admin_user
        resp = await client.post(
            f"/api/v1/operation/workorders/{sample_work_order.id}/assign",
            headers=auth_headers(token),
            json={"assignee": "技术员A"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["assignee"] == "技术员A"
        assert body["status"] == "已派单"


class TestWorkOrderStatusTransition:
    """工单状态转换测试"""

    async def test_invalid_status_transition(self, client, admin_user, async_db):
        """测试非法状态转换"""
        _, token = admin_user
        # 创建已关闭的工单
        order = WorkOrder(
            order_no="WO-CLOSED-001",
            title="已关闭工单",
            status=WorkOrderStatus.closed,
        )
        async_db.add(order)
        await async_db.flush()

        # 尝试派单（closed -> assigned 不允许）
        resp = await client.post(
            f"/api/v1/operation/workorders/{order.id}/assign",
            headers=auth_headers(token),
            json={"assignee": "技术员B"},
        )
        assert resp.status_code == 400


class TestInspectionPlan:
    """巡检计划测试"""

    async def test_get_inspection_plans(self, client, admin_user):
        """测试获取巡检计划列表"""
        _, token = admin_user
        resp = await client.get(
            "/api/v1/operation/plans",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_create_inspection_plan(self, client, admin_user):
        """测试创建巡检计划"""
        _, token = admin_user
        resp = await client.post(
            "/api/v1/operation/plans",
            headers=auth_headers(token),
            json={
                "name": "新建巡检计划",
                "description": "每周巡检",
                "frequency": "weekly",
                "location": "B区机房",
                "assignee": "赵六",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "新建巡检计划"

    async def test_get_inspection_plan_detail(self, client, admin_user, sample_inspection_plan):
        """测试获取巡检计划详情"""
        _, token = admin_user
        resp = await client.get(
            f"/api/v1/operation/plans/{sample_inspection_plan.id}",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "日常巡检计划"


class TestInspectionTask:
    """巡检任务测试"""

    async def test_get_inspection_tasks(self, client, admin_user):
        """测试获取巡检任务列表"""
        _, token = admin_user
        resp = await client.get(
            "/api/v1/operation/tasks",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_create_inspection_task(self, client, admin_user, sample_inspection_plan):
        """测试创建巡检任务"""
        _, token = admin_user
        resp = await client.post(
            "/api/v1/operation/tasks",
            headers=auth_headers(token),
            json={
                "plan_id": sample_inspection_plan.id,
                "assignee": "李四",
                "scheduled_date": datetime.now().isoformat(),
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["task_no"].startswith("IT-")

    async def test_start_inspection_task(self, client, admin_user, sample_inspection_task):
        """测试开始巡检任务"""
        _, token = admin_user
        resp = await client.post(
            f"/api/v1/operation/tasks/{sample_inspection_task.id}/start",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "巡检中"


class TestKnowledgeBase:
    """知识库测试"""

    async def test_get_knowledge_list(self, client, admin_user):
        """测试获取知识库列表"""
        _, token = admin_user
        resp = await client.get(
            "/api/v1/operation/knowledge",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert "data" in body
        assert "items" in body["data"]

    async def test_create_knowledge(self, client, admin_user):
        """测试创建知识库条目"""
        _, token = admin_user
        resp = await client.post(
            "/api/v1/operation/knowledge",
            headers=auth_headers(token),
            json={
                "title": "新建知识条目",
                "category": "空调",
                "content": "空调维护指南",
                "tags": "空调,维护",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["title"] == "新建知识条目"

    async def test_get_knowledge_detail(self, client, admin_user, sample_knowledge):
        """测试获取知识库详情"""
        _, token = admin_user
        resp = await client.get(
            f"/api/v1/operation/knowledge/{sample_knowledge.id}",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["title"] == "UPS 故障排查指南"

    async def test_get_knowledge_not_found(self, client, admin_user):
        """测试知识库条目不存在"""
        _, token = admin_user
        resp = await client.get(
            "/api/v1/operation/knowledge/99999",
            headers=auth_headers(token),
        )
        assert resp.status_code == 404


class TestOperationStatistics:
    """运维统计测试"""

    async def test_get_operation_statistics(self, client, admin_user, sample_work_order):
        """测试获取运维统计"""
        _, token = admin_user
        resp = await client.get(
            "/api/v1/operation/statistics",
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "total_orders" in body
        assert "pending_orders" in body
