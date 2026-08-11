"""
运维管理模块覆盖率测试
operation.py — 工单/巡检/知识库/告警规则/审批/统计
"""

import pytest
from app.models.alarm import Alarm
from tests.conftest import auth_headers

BASE = "/api/v1/operation"


# ============== 辅助函数 ==============


async def _create_workorder(client, token, **overrides):
    """创建一个工单并返回响应 JSON"""
    payload = {
        "title": "UPS 输出异常",
        "description": "UPS-01 输出电压偏低",
        "priority": "高",
        "order_type": "故障报修",
    }
    payload.update(overrides)
    resp = await client.post(f"{BASE}/workorders", json=payload, headers=auth_headers(token))
    assert resp.status_code == 200
    return resp.json()


async def _create_plan(client, token, **overrides):
    """创建一个巡检计划并返回响应 JSON"""
    payload = {
        "name": "机房日巡",
        "description": "每日检查温湿度、UPS、空调运行状态",
        "frequency": "daily",
        "location": "A1 机房",
        "assignee": "张工",
        "is_active": True,
    }
    payload.update(overrides)
    resp = await client.post(f"{BASE}/plans", json=payload, headers=auth_headers(token))
    assert resp.status_code == 200
    return resp.json()


async def _create_task(client, token, **overrides):
    """创建一个巡检任务并返回响应 JSON"""
    payload = {"assignee": "李工"}
    payload.update(overrides)
    resp = await client.post(f"{BASE}/tasks", json=payload, headers=auth_headers(token))
    assert resp.status_code == 200
    return resp.json()


async def _create_knowledge(client, token, **overrides):
    """创建一个知识库文章并返回响应 JSON"""
    payload = {
        "title": "UPS 维护手册",
        "content": "定期检查电池组内阻…",
        "category": "设备维护",
        "tags": "UPS,电池,维护",
        "author": "admin",
    }
    payload.update(overrides)
    resp = await client.post(f"{BASE}/knowledge", json=payload, headers=auth_headers(token))
    assert resp.status_code == 200
    return resp.json()


async def _create_alarm_rule(client, token, **overrides):
    """创建一个告警工单规则并返回响应 JSON"""
    payload = {
        "name": "紧急告警自动建单",
        "alarm_level": "critical",
        "order_type": "故障报修",
        "priority": "高",
        "is_enabled": True,
    }
    payload.update(overrides)
    resp = await client.post(f"{BASE}/alarm-rules", json=payload, headers=auth_headers(token))
    assert resp.status_code == 200
    return resp.json()


async def _create_alarm(async_db, alarm_no, alarm_level, alarm_message):
    """创建告警检查所需的真实告警记录"""
    alarm = Alarm(
        alarm_no=alarm_no,
        alarm_level=alarm_level,
        alarm_message=alarm_message,
    )
    async_db.add(alarm)
    await async_db.flush()
    return alarm


# ==================== 工单管理 ====================


@pytest.mark.asyncio
class TestWorkOrders:
    """工单 CRUD + 状态流转"""

    async def test_list_empty(self, client, admin_user):
        _, token = admin_user
        resp = await client.get(f"{BASE}/workorders", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_create_and_get(self, client, admin_user):
        _, token = admin_user
        created = await _create_workorder(client, token)
        assert created["title"] == "UPS 输出异常"
        assert created["status"] == "待处理"
        assert created["order_no"].startswith("WO-")

        # 获取详情
        wo_id = created["id"]
        resp = await client.get(f"{BASE}/workorders/{wo_id}", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["id"] == wo_id

    async def test_update(self, client, admin_user):
        _, token = admin_user
        created = await _create_workorder(client, token)
        wo_id = created["id"]
        resp = await client.put(
            f"{BASE}/workorders/{wo_id}",
            json={"title": "UPS 输出异常（已确认）", "priority": "紧急"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "UPS 输出异常（已确认）"

    async def test_delete(self, client, admin_user):
        _, token = admin_user
        created = await _create_workorder(client, token)
        wo_id = created["id"]
        resp = await client.delete(f"{BASE}/workorders/{wo_id}", headers=auth_headers(token))
        assert resp.status_code == 200

        # 确认已删除
        resp = await client.get(f"{BASE}/workorders/{wo_id}", headers=auth_headers(token))
        assert resp.status_code == 404

    async def test_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.get(f"{BASE}/workorders/99999", headers=auth_headers(token))
        assert resp.status_code == 404

    async def test_update_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.put(
            f"{BASE}/workorders/99999",
            json={"title": "不存在"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_delete_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.delete(f"{BASE}/workorders/99999", headers=auth_headers(token))
        assert resp.status_code == 404

    async def test_no_auth(self, client):
        resp = await client.get(f"{BASE}/workorders")
        assert resp.status_code in (401, 403)

    async def test_list_with_filters(self, client, admin_user):
        _, token = admin_user
        await _create_workorder(client, token, priority="高")
        await _create_workorder(client, token, priority="低", title="低优先级工单")
        resp = await client.get(
            f"{BASE}/workorders?priority=高", headers=auth_headers(token)
        )
        assert resp.status_code == 200
        data = resp.json()
        assert all(item["priority"] == "高" for item in data)


# ==================== 工单状态流转 ====================


@pytest.mark.asyncio
class TestWorkOrderWorkflow:
    """工单完整生命周期: pending → assigned → accepted → processing → completed → closed"""

    async def test_full_lifecycle(self, client, admin_user):
        _, token = admin_user
        wo = await _create_workorder(client, token)
        wo_id = wo["id"]
        assert wo["status"] == "待处理"

        # 1. 派单
        resp = await client.post(
            f"{BASE}/workorders/{wo_id}/assign",
            json={"assignee": "张工"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "已派单"
        assert resp.json()["assignee"] == "张工"

        # 2. 接单
        resp = await client.post(
            f"{BASE}/workorders/{wo_id}/accept", headers=auth_headers(token)
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "已接单"

        # 3. 开始处理
        resp = await client.post(
            f"{BASE}/workorders/{wo_id}/start", headers=auth_headers(token)
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "处理中"

        # 4. 完成
        resp = await client.post(
            f"{BASE}/workorders/{wo_id}/complete",
            json={"solution": "更换 UPS 模块", "root_cause": "电池老化"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "已完成"
        assert resp.json()["solution"] == "更换 UPS 模块"

        # 5. 关闭
        resp = await client.post(
            f"{BASE}/workorders/{wo_id}/close", headers=auth_headers(token)
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "已关闭"

    async def test_invalid_transition(self, client, admin_user):
        """pending 状态不能直接 start"""
        _, token = admin_user
        wo = await _create_workorder(client, token)
        wo_id = wo["id"]
        resp = await client.post(
            f"{BASE}/workorders/{wo_id}/start", headers=auth_headers(token)
        )
        assert resp.status_code == 400

    async def test_assign_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.post(
            f"{BASE}/workorders/99999/assign",
            json={"assignee": "x"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_accept_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.post(
            f"{BASE}/workorders/99999/accept", headers=auth_headers(token)
        )
        assert resp.status_code == 404

    async def test_start_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.post(
            f"{BASE}/workorders/99999/start", headers=auth_headers(token)
        )
        assert resp.status_code == 404

    async def test_complete_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.post(
            f"{BASE}/workorders/99999/complete",
            json={},
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_close_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.post(
            f"{BASE}/workorders/99999/close", headers=auth_headers(token)
        )
        assert resp.status_code == 404


# ==================== 工单日志 ====================


@pytest.mark.asyncio
class TestWorkOrderLogs:
    """工单日志"""

    async def test_logs_after_create(self, client, admin_user):
        """创建工单后应有一条创建日志"""
        _, token = admin_user
        wo = await _create_workorder(client, token)
        wo_id = wo["id"]
        resp = await client.get(
            f"{BASE}/workorders/{wo_id}/logs", headers=auth_headers(token)
        )
        assert resp.status_code == 200
        logs = resp.json()
        assert len(logs) >= 1
        assert any("创建" in log.get("action", "") for log in logs)

    async def test_add_log(self, client, admin_user):
        _, token = admin_user
        wo = await _create_workorder(client, token)
        wo_id = wo["id"]
        resp = await client.post(
            f"{BASE}/workorders/{wo_id}/logs",
            json={"action": "备注", "content": "已联系供应商", "operator": "张工"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["content"] == "已联系供应商"

    async def test_logs_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.get(
            f"{BASE}/workorders/99999/logs", headers=auth_headers(token)
        )
        assert resp.status_code == 404

    async def test_add_log_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.post(
            f"{BASE}/workorders/99999/logs",
            json={"action": "备注", "content": "测试", "operator": "x"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 404


# ==================== 审批管理 ====================


@pytest.mark.asyncio
class TestApprovals:
    """工单审批流程"""

    async def _prepare_change_order(self, client, token):
        """创建一个变更类型工单并推进到 accepted 状态"""
        wo = await _create_workorder(client, token, order_type="变更请求")
        wo_id = wo["id"]
        await client.post(
            f"{BASE}/workorders/{wo_id}/assign",
            json={"assignee": "张工"},
            headers=auth_headers(token),
        )
        await client.post(
            f"{BASE}/workorders/{wo_id}/accept", headers=auth_headers(token)
        )
        return wo_id

    async def test_submit_and_approve(self, client, admin_user):
        _, token = admin_user
        wo_id = await self._prepare_change_order(client, token)

        # 提交审批
        resp = await client.post(
            f"{BASE}/workorders/{wo_id}/submit-approval",
            json={"approver": "李经理", "timeout_hours": 48},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        approval = resp.json()
        assert approval["status"] == "待审批"
        approval_id = approval["id"]

        # 批准
        resp = await client.post(
            f"{BASE}/approvals/{approval_id}/approve",
            json={"reason": "同意变更"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "已批准"

    async def test_submit_and_reject(self, client, admin_user):
        _, token = admin_user
        wo_id = await self._prepare_change_order(client, token)

        resp = await client.post(
            f"{BASE}/workorders/{wo_id}/submit-approval",
            json={"approver": "王经理"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        approval_id = resp.json()["id"]

        # 驳回
        resp = await client.post(
            f"{BASE}/approvals/{approval_id}/reject",
            json={"reason": "方案不完善"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "已驳回"

    async def test_list_approvals(self, client, admin_user):
        _, token = admin_user
        resp = await client.get(f"{BASE}/approvals", headers=auth_headers(token))
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_approval_detail_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.get(f"{BASE}/approvals/99999", headers=auth_headers(token))
        assert resp.status_code == 404

    async def test_approve_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.post(
            f"{BASE}/approvals/99999/approve",
            json={"reason": "ok"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_reject_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.post(
            f"{BASE}/approvals/99999/reject",
            json={"reason": "no"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_submit_approval_order_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.post(
            f"{BASE}/workorders/99999/submit-approval",
            json={"approver": "x"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_submit_approval_wrong_type(self, client, admin_user):
        """非变更类型工单不能提交审批"""
        _, token = admin_user
        wo = await _create_workorder(client, token, order_type="故障报修")
        resp = await client.post(
            f"{BASE}/workorders/{wo['id']}/submit-approval",
            json={"approver": "x"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 400

    async def test_submit_approval_wrong_status(self, client, admin_user):
        """非 accepted 状态不能提交审批"""
        _, token = admin_user
        wo = await _create_workorder(client, token, order_type="变更请求")
        # 工单还是 pending 状态
        resp = await client.post(
            f"{BASE}/workorders/{wo['id']}/submit-approval",
            json={"approver": "x"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 400

    async def test_duplicate_approval(self, client, admin_user):
        """同一工单不能重复提交审批"""
        _, token = admin_user
        wo_id = await self._prepare_change_order(client, token)
        await client.post(
            f"{BASE}/workorders/{wo_id}/submit-approval",
            json={"approver": "A"},
            headers=auth_headers(token),
        )
        resp = await client.post(
            f"{BASE}/workorders/{wo_id}/submit-approval",
            json={"approver": "B"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 400

    async def test_approve_already_resolved(self, client, admin_user):
        """已批准/驳回的审批不能再批准"""
        _, token = admin_user
        wo_id = await self._prepare_change_order(client, token)
        resp = await client.post(
            f"{BASE}/workorders/{wo_id}/submit-approval",
            json={"approver": "M"},
            headers=auth_headers(token),
        )
        approval_id = resp.json()["id"]
        # 先批准
        await client.post(
            f"{BASE}/approvals/{approval_id}/approve",
            json={},
            headers=auth_headers(token),
        )
        # 再批准应失败
        resp = await client.post(
            f"{BASE}/approvals/{approval_id}/approve",
            json={},
            headers=auth_headers(token),
        )
        assert resp.status_code == 400


# ==================== 巡检计划 ====================


@pytest.mark.asyncio
class TestInspectionPlans:
    """巡检计划 CRUD"""

    async def test_list_empty(self, client, admin_user):
        _, token = admin_user
        resp = await client.get(f"{BASE}/plans", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_create_and_get(self, client, admin_user):
        _, token = admin_user
        created = await _create_plan(client, token)
        assert created["name"] == "机房日巡"

        plan_id = created["id"]
        resp = await client.get(f"{BASE}/plans/{plan_id}", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["name"] == "机房日巡"

    async def test_update(self, client, admin_user):
        _, token = admin_user
        created = await _create_plan(client, token)
        plan_id = created["id"]
        resp = await client.put(
            f"{BASE}/plans/{plan_id}",
            json={"name": "机房周巡", "frequency": "weekly"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "机房周巡"

    async def test_delete(self, client, admin_user):
        _, token = admin_user
        created = await _create_plan(client, token)
        plan_id = created["id"]
        resp = await client.delete(f"{BASE}/plans/{plan_id}", headers=auth_headers(token))
        assert resp.status_code == 200

        resp = await client.get(f"{BASE}/plans/{plan_id}", headers=auth_headers(token))
        assert resp.status_code == 404

    async def test_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.get(f"{BASE}/plans/99999", headers=auth_headers(token))
        assert resp.status_code == 404

    async def test_update_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.put(
            f"{BASE}/plans/99999", json={"name": "x"}, headers=auth_headers(token)
        )
        assert resp.status_code == 404

    async def test_delete_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.delete(f"{BASE}/plans/99999", headers=auth_headers(token))
        assert resp.status_code == 404

    async def test_no_auth(self, client):
        resp = await client.get(f"{BASE}/plans")
        assert resp.status_code in (401, 403)

    async def test_list_with_name_filter(self, client, admin_user):
        _, token = admin_user
        await _create_plan(client, token, name="电力巡检")
        await _create_plan(client, token, name="空调巡检")
        resp = await client.get(
            f"{BASE}/plans?name=电力", headers=auth_headers(token)
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1


# ==================== 巡检任务 ====================


@pytest.mark.asyncio
class TestInspectionTasks:
    """巡检任务 CRUD + 状态流转"""

    async def test_list_empty(self, client, admin_user):
        _, token = admin_user
        resp = await client.get(f"{BASE}/tasks", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_create_and_get(self, client, admin_user):
        _, token = admin_user
        created = await _create_task(client, token)
        assert created["task_no"].startswith("IT-")
        assert created["status"] == "待巡检"

        task_id = created["id"]
        resp = await client.get(f"{BASE}/tasks/{task_id}", headers=auth_headers(token))
        assert resp.status_code == 200

    async def test_update(self, client, admin_user):
        _, token = admin_user
        created = await _create_task(client, token)
        task_id = created["id"]
        resp = await client.put(
            f"{BASE}/tasks/{task_id}",
            json={"assignee": "王工", "remarks": "需携带红外测温仪"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200

    async def test_task_workflow(self, client, admin_user):
        """pending → in_progress → completed"""
        _, token = admin_user
        task = await _create_task(client, token)
        task_id = task["id"]

        # 开始
        resp = await client.post(
            f"{BASE}/tasks/{task_id}/start", headers=auth_headers(token)
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "巡检中"

        # 完成
        resp = await client.post(
            f"{BASE}/tasks/{task_id}/complete",
            json={"result": '{"温度": "正常"}', "abnormal_count": 0},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "已完成"

    async def test_invalid_task_transition(self, client, admin_user):
        """pending 不能直接 complete"""
        _, token = admin_user
        task = await _create_task(client, token)
        resp = await client.post(
            f"{BASE}/tasks/{task['id']}/complete",
            json={},
            headers=auth_headers(token),
        )
        assert resp.status_code == 400

    async def test_delete(self, client, admin_user):
        _, token = admin_user
        task = await _create_task(client, token)
        task_id = task["id"]
        resp = await client.delete(f"{BASE}/tasks/{task_id}", headers=auth_headers(token))
        assert resp.status_code == 200

        resp = await client.get(f"{BASE}/tasks/{task_id}", headers=auth_headers(token))
        assert resp.status_code == 404

    async def test_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.get(f"{BASE}/tasks/99999", headers=auth_headers(token))
        assert resp.status_code == 404

    async def test_start_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.post(
            f"{BASE}/tasks/99999/start", headers=auth_headers(token)
        )
        assert resp.status_code == 404

    async def test_complete_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.post(
            f"{BASE}/tasks/99999/complete", json={}, headers=auth_headers(token)
        )
        assert resp.status_code == 404

    async def test_delete_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.delete(f"{BASE}/tasks/99999", headers=auth_headers(token))
        assert resp.status_code == 404

    async def test_update_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.put(
            f"{BASE}/tasks/99999", json={"assignee": "x"}, headers=auth_headers(token)
        )
        assert resp.status_code == 404

    async def test_no_auth(self, client):
        resp = await client.get(f"{BASE}/tasks")
        assert resp.status_code in (401, 403)


# ==================== 从计划生成任务 ====================


@pytest.mark.asyncio
class TestGenerateTaskFromPlan:
    """从巡检计划生成任务"""

    async def test_generate_task(self, client, admin_user):
        _, token = admin_user
        plan = await _create_plan(client, token, is_active=True)
        plan_id = plan["id"]
        resp = await client.post(
            f"{BASE}/plans/{plan_id}/generate-tasks", headers=auth_headers(token)
        )
        assert resp.status_code == 200
        task = resp.json()
        assert task["task_no"].startswith("IT-")
        assert task["plan_name"] == plan["name"]

    async def test_generate_task_plan_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.post(
            f"{BASE}/plans/99999/generate-tasks", headers=auth_headers(token)
        )
        assert resp.status_code == 404

    async def test_generate_task_plan_inactive(self, client, admin_user):
        _, token = admin_user
        plan = await _create_plan(client, token, is_active=False)
        resp = await client.post(
            f"{BASE}/plans/{plan['id']}/generate-tasks", headers=auth_headers(token)
        )
        assert resp.status_code == 400


# ==================== 告警工单规则 ====================


@pytest.mark.asyncio
class TestAlarmRules:
    """告警工单规则 CRUD + 告警检查"""

    async def test_list_empty(self, client, admin_user):
        _, token = admin_user
        resp = await client.get(f"{BASE}/alarm-rules", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_create_and_list(self, client, admin_user):
        _, token = admin_user
        created = await _create_alarm_rule(client, token)
        assert created["name"] == "紧急告警自动建单"

        resp = await client.get(f"{BASE}/alarm-rules", headers=auth_headers(token))
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    async def test_update(self, client, admin_user):
        _, token = admin_user
        created = await _create_alarm_rule(client, token)
        rule_id = created["id"]
        resp = await client.put(
            f"{BASE}/alarm-rules/{rule_id}",
            json={"name": "更新后的规则", "assignee": "自动派单-王工"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "更新后的规则"

    async def test_delete(self, client, admin_user):
        _, token = admin_user
        created = await _create_alarm_rule(client, token)
        rule_id = created["id"]
        resp = await client.delete(
            f"{BASE}/alarm-rules/{rule_id}", headers=auth_headers(token)
        )
        assert resp.status_code == 200

        resp = await client.get(f"{BASE}/alarm-rules", headers=auth_headers(token))
        assert resp.json() == []

    async def test_update_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.put(
            f"{BASE}/alarm-rules/99999",
            json={"name": "x"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_delete_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.delete(
            f"{BASE}/alarm-rules/99999", headers=auth_headers(token)
        )
        assert resp.status_code == 404

    async def test_check_alarm_matched(self, client, admin_user, async_db):
        """告警匹配规则后自动创建工单"""
        _, token = admin_user
        await _create_alarm_rule(client, token, alarm_level="critical")
        alarm = await _create_alarm(async_db, "OP-CHECK-001", "critical", "温度超过阈值")
        resp = await client.post(
            f"{BASE}/alarm-rules/check",
            json={
                "alarm_id": alarm.id,
                "alarm_level": "critical",
                "alarm_message": "温度超过阈值",
            },
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["matched"] is True
        assert data["work_order"] is not None

    async def test_check_alarm_no_match(self, client, admin_user, async_db):
        """无匹配规则时不创建工单"""
        _, token = admin_user
        alarm = await _create_alarm(async_db, "OP-CHECK-002", "info", "信息告警")
        resp = await client.post(
            f"{BASE}/alarm-rules/check",
            json={
                "alarm_id": alarm.id,
                "alarm_level": "info",
                "alarm_message": "信息告警",
            },
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["matched"] is False

    async def test_check_alarm_auto_assign(self, client, admin_user, async_db):
        """规则设置了 assignee 时自动派单"""
        _, token = admin_user
        await _create_alarm_rule(
            client, token, alarm_level="critical", assignee="值班员"
        )
        alarm = await _create_alarm(async_db, "OP-CHECK-003", "critical", "UPS 故障")
        resp = await client.post(
            f"{BASE}/alarm-rules/check",
            json={
                "alarm_id": alarm.id,
                "alarm_level": "critical",
                "alarm_message": "UPS 故障",
            },
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        wo = resp.json()["work_order"]
        assert wo["assignee"] == "值班员"
        assert wo["status"] == "已派单"

    async def test_no_auth(self, client):
        resp = await client.get(f"{BASE}/alarm-rules")
        assert resp.status_code in (401, 403)


# ==================== 知识库 ====================


@pytest.mark.asyncio
class TestKnowledgeBase:
    """知识库 CRUD"""

    async def test_list_empty(self, client, admin_user):
        _, token = admin_user
        resp = await client.get(f"{BASE}/knowledge", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["total"] == 0

    async def test_create_and_get(self, client, admin_user):
        _, token = admin_user
        created = await _create_knowledge(client, token)
        assert created["title"] == "UPS 维护手册"

        article_id = created["id"]
        resp = await client.get(
            f"{BASE}/knowledge/{article_id}", headers=auth_headers(token)
        )
        assert resp.status_code == 200
        detail = resp.json()
        assert detail["view_count"] >= 1  # 获取详情会增加浏览量

    async def test_update(self, client, admin_user):
        _, token = admin_user
        created = await _create_knowledge(client, token)
        article_id = created["id"]
        resp = await client.put(
            f"{BASE}/knowledge/{article_id}",
            json={"title": "UPS 维护手册 V2", "tags": "UPS,电池,维护,V2"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "UPS 维护手册 V2"

    async def test_delete(self, client, admin_user):
        _, token = admin_user
        created = await _create_knowledge(client, token)
        article_id = created["id"]
        resp = await client.delete(
            f"{BASE}/knowledge/{article_id}", headers=auth_headers(token)
        )
        assert resp.status_code == 200

        resp = await client.get(
            f"{BASE}/knowledge/{article_id}", headers=auth_headers(token)
        )
        assert resp.status_code == 404

    async def test_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.get(f"{BASE}/knowledge/99999", headers=auth_headers(token))
        assert resp.status_code == 404

    async def test_update_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.put(
            f"{BASE}/knowledge/99999",
            json={"title": "x"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 404

    async def test_delete_not_found(self, client, admin_user):
        _, token = admin_user
        resp = await client.delete(
            f"{BASE}/knowledge/99999", headers=auth_headers(token)
        )
        assert resp.status_code == 404

    async def test_no_auth(self, client):
        resp = await client.get(f"{BASE}/knowledge")
        assert resp.status_code in (401, 403)

    async def test_list_with_category(self, client, admin_user):
        _, token = admin_user
        await _create_knowledge(client, token, category="设备维护")
        await _create_knowledge(client, token, category="应急预案", title="火灾应急")
        resp = await client.get(
            f"{BASE}/knowledge?category=应急预案", headers=auth_headers(token)
        )
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        assert len(items) == 1
        assert items[0]["category"] == "应急预案"

    async def test_list_with_keyword(self, client, admin_user):
        _, token = admin_user
        await _create_knowledge(client, token, title="空调维护指南", content="定期清洗滤网")
        resp = await client.get(
            f"{BASE}/knowledge?keyword=空调", headers=auth_headers(token)
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] >= 1

    async def test_list_pagination(self, client, admin_user):
        _, token = admin_user
        await _create_knowledge(client, token, title="文章A")
        await _create_knowledge(client, token, title="文章B")
        resp = await client.get(
            f"{BASE}/knowledge?page=1&page_size=1", headers=auth_headers(token)
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data["items"]) == 1
        assert data["total"] == 2


# ==================== 运维统计 ====================


@pytest.mark.asyncio
class TestStatistics:
    """运维统计"""

    async def test_statistics_empty(self, client, admin_user):
        _, token = admin_user
        resp = await client.get(f"{BASE}/statistics", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_orders"] == 0
        assert data["knowledge_count"] == 0

    async def test_statistics_after_data(self, client, admin_user):
        """创建数据后统计应反映变化"""
        _, token = admin_user
        await _create_workorder(client, token)
        await _create_knowledge(client, token)

        resp = await client.get(f"{BASE}/statistics", headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_orders"] >= 1
        assert data["pending_orders"] >= 1
        assert data["knowledge_count"] >= 1

    async def test_no_auth(self, client):
        resp = await client.get(f"{BASE}/statistics")
        assert resp.status_code in (401, 403)


# ==================== 权限测试 ====================


@pytest.mark.asyncio
class TestPermissions:
    """验证 viewer 只能读、不能写"""

    async def test_viewer_can_list(self, client, admin_user, viewer_user):
        """viewer 可以查看列表"""
        _, admin_token = admin_user
        _, viewer_token = viewer_user
        # 先用 admin 创建数据
        await _create_workorder(client, admin_token)

        resp = await client.get(f"{BASE}/workorders", headers=auth_headers(viewer_token))
        assert resp.status_code == 200

    async def test_viewer_cannot_create(self, client, viewer_user):
        """viewer 不能创建工单"""
        _, token = viewer_user
        resp = await client.post(
            f"{BASE}/workorders",
            json={"title": "测试"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 403

    async def test_viewer_cannot_delete(self, client, admin_user, viewer_user):
        """viewer 不能删除工单"""
        _, admin_token = admin_user
        _, viewer_token = viewer_user
        wo = await _create_workorder(client, admin_token)
        resp = await client.delete(
            f"{BASE}/workorders/{wo['id']}", headers=auth_headers(viewer_token)
        )
        assert resp.status_code == 403
