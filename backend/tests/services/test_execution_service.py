"""
执行计划服务测试

覆盖:
  - ExecutionService.get_plan_with_tasks: 获取计划详情
  - ExecutionService.execute_auto_task: 执行自动任务
  - ExecutionService.complete_manual_task: 完成手动任务
  - ExecutionService.update_plan_status: 更新计划状态
  - ExecutionService.generate_task_checklist: 生成执行清单
  - ExecutionService._generate_conclusion: 效果结论生成
  - ExecutionService._get_regulation_type: 任务类型映射
  - ExecutionService._get_status_text: 状态文本
  - ExecutionService._get_average_price: 平均电价
"""

import pytest

from app.services.command_registry import CommandPolicyError
from app.services.execution_service import ExecutionService
from app.models.energy import ExecutionPlan, ExecutionTask, EnergyOpportunity


class TestGenerateConclusion:
    """效果结论生成测试"""

    def test_excellent(self):
        """达成率>=100%: 优秀"""
        svc = ExecutionService(None)
        assert "优秀" in svc._generate_conclusion(120)

    def test_good(self):
        """达成率>=80%: 良好"""
        svc = ExecutionService(None)
        assert "良好" in svc._generate_conclusion(85)

    def test_average(self):
        """达成率>=50%: 一般"""
        svc = ExecutionService(None)
        assert "一般" in svc._generate_conclusion(60)

    def test_poor(self):
        """达成率>0但<50%: 不佳"""
        svc = ExecutionService(None)
        assert "不佳" in svc._generate_conclusion(30)

    def test_no_data(self):
        """达成率<=0: 暂无数据"""
        svc = ExecutionService(None)
        assert "暂无" in svc._generate_conclusion(0)


class TestGetRegulationType:
    """任务类型映射测试"""

    def test_temp_adjust(self):
        svc = ExecutionService(None)
        assert svc._get_regulation_type("temp_adjust") == "temperature"

    def test_brightness_adjust(self):
        svc = ExecutionService(None)
        assert svc._get_regulation_type("brightness_adjust") == "brightness"

    def test_load_adjust(self):
        svc = ExecutionService(None)
        assert svc._get_regulation_type("load_adjust") == "load"

    def test_unknown_task_type_is_rejected(self):
        svc = ExecutionService(None)
        with pytest.raises(CommandPolicyError, match="未知自动任务类型"):
            svc._get_regulation_type("unknown_type")


class TestGetStatusText:
    """状态文本测试"""

    def test_known_statuses(self):
        svc = ExecutionService(None)
        assert "待执行" in svc._get_status_text("pending")
        assert "执行中" in svc._get_status_text("executing")
        assert "已完成" in svc._get_status_text("completed")
        assert "失败" in svc._get_status_text("failed")

    def test_unknown_status(self):
        svc = ExecutionService(None)
        assert svc._get_status_text("custom") == "custom"


class TestGetPlanWithTasks:
    """获取计划详情测试"""

    @pytest.mark.asyncio
    async def test_plan_not_found(self, async_db):
        """计划不存在时返回 None"""
        svc = ExecutionService(async_db)
        result = await svc.get_plan_with_tasks(99999)
        assert result is None

    @pytest.mark.asyncio
    async def test_plan_with_tasks(self, async_db):
        """获取包含任务的计划详情"""
        # 创建机会
        opp = EnergyOpportunity(
            title="测试机会",
            category="peak_valley",
            priority="high",
            source_plugin="peak_valley_optimizer",
            status="executing",
        )
        async_db.add(opp)
        await async_db.flush()

        # 创建计划
        plan = ExecutionPlan(
            opportunity_id=opp.id,
            plan_name="测试计划",
            expected_saving=50000,
            status="pending",
        )
        async_db.add(plan)
        await async_db.flush()

        # 创建任务
        task = ExecutionTask(
            plan_id=plan.id,
            task_type="temp_adjust",
            task_name="调节空调温度",
            target_object="精密空调1",
            execution_mode="auto",
            status="pending",
            sort_order=1,
        )
        async_db.add(task)
        await async_db.flush()

        svc = ExecutionService(async_db)
        result = await svc.get_plan_with_tasks(plan.id)
        assert result is not None
        assert result["plan"]["plan_name"] == "测试计划"
        assert result["task_stats"]["total"] == 1
        assert result["task_stats"]["pending"] == 1
        assert len(result["tasks"]) == 1


class TestCompleteManualTask:
    """完成手动任务测试"""

    @pytest.mark.asyncio
    async def test_task_not_found(self, async_db):
        """任务不存在"""
        svc = ExecutionService(async_db)
        result = await svc.complete_manual_task(99999)
        assert result["success"] is False
        assert "不存在" in result["error"]

    @pytest.mark.asyncio
    async def test_complete_manual_task(self, async_db):
        """成功完成手动任务"""
        opp = EnergyOpportunity(
            title="手动任务机会",
            category="demand",
            priority="medium",
            source_plugin="demand_optimizer",
            status="executing",
        )
        async_db.add(opp)
        await async_db.flush()

        plan = ExecutionPlan(
            opportunity_id=opp.id,
            plan_name="手动计划",
            expected_saving=10000,
            status="executing",
        )
        async_db.add(plan)
        await async_db.flush()

        task = ExecutionTask(
            plan_id=plan.id,
            task_type="manual_check",
            task_name="人工检查",
            target_object="配电柜",
            execution_mode="manual",
            status="pending",
            sort_order=1,
        )
        async_db.add(task)
        await async_db.flush()

        svc = ExecutionService(async_db)
        result = await svc.complete_manual_task(task.id, completed_by="张三", notes="已完成检查")
        assert result["success"] is True
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_already_completed_task(self, async_db):
        """已完成的任务不能重复完成"""
        opp = EnergyOpportunity(
            title="重复完成机会",
            category="demand",
            priority="low",
            source_plugin="test",
            status="executing",
        )
        async_db.add(opp)
        await async_db.flush()

        plan = ExecutionPlan(
            opportunity_id=opp.id,
            plan_name="重复计划",
            expected_saving=5000,
            status="executing",
        )
        async_db.add(plan)
        await async_db.flush()

        task = ExecutionTask(
            plan_id=plan.id,
            task_type="manual_check",
            task_name="已完成任务",
            target_object="设备",
            execution_mode="manual",
            status="completed",
            sort_order=1,
        )
        async_db.add(task)
        await async_db.flush()

        svc = ExecutionService(async_db)
        result = await svc.complete_manual_task(task.id)
        assert result["success"] is False
        assert "已完成" in result["error"]


class TestUpdatePlanStatus:
    """更新计划状态测试"""

    @pytest.mark.asyncio
    async def test_plan_not_found(self, async_db):
        """计划不存在返回 unknown"""
        svc = ExecutionService(async_db)
        status = await svc.update_plan_status(99999)
        assert status == "unknown"

    @pytest.mark.asyncio
    async def test_all_tasks_completed(self, async_db):
        """所有任务完成时计划状态为 completed"""
        opp = EnergyOpportunity(
            title="完成机会",
            category="pue",
            priority="high",
            source_plugin="pue_optimizer",
            status="executing",
        )
        async_db.add(opp)
        await async_db.flush()

        plan = ExecutionPlan(
            opportunity_id=opp.id,
            plan_name="完成计划",
            expected_saving=20000,
            status="executing",
        )
        async_db.add(plan)
        await async_db.flush()

        task = ExecutionTask(
            plan_id=plan.id,
            task_type="temp_adjust",
            task_name="任务1",
            target_object="设备1",
            execution_mode="auto",
            status="completed",
            sort_order=1,
        )
        async_db.add(task)
        await async_db.flush()

        svc = ExecutionService(async_db)
        new_status = await svc.update_plan_status(plan.id)
        assert new_status == "completed"


class TestGetAveragePrice:
    """平均电价测试"""

    @pytest.mark.asyncio
    async def test_default_price(self, async_db):
        """无电价配置时返回默认值 0.6"""
        svc = ExecutionService(async_db)
        price = await svc._get_average_price()
        assert price == 0.6
