"""
Shift Plan Service - Business logic for shift plan management
转移计划服务
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, date
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.load_shift import ShiftPlan
from app.schemas.load_shift import (
    ShiftPlanCreate,
    ShiftPlanUpdate,
    ShiftPlanStatus,
    ApprovalStatus,
    ExecutionStatus,
    ShiftPlanApproval,
)


class ShiftPlanService:
    """Shift plan service - 转移计划服务"""

    @staticmethod
    async def create_plan(db: AsyncSession, plan_data: ShiftPlanCreate, user_id: int) -> ShiftPlan:
        """
        Create shift plan - 创建转移计划

        Args:
            db: Database session
            plan_data: Plan creation data
            user_id: Creator user ID

        Returns:
            Created shift plan
        """
        # Generate plan code
        plan_code = await ShiftPlanService._generate_plan_code(db, plan_data.shift_date)

        # Create plan instance
        plan = ShiftPlan(
            plan_code=plan_code,
            plan_name=plan_data.plan_name,
            shift_from_period=plan_data.shift_from_period,
            shift_to_period=plan_data.shift_to_period,
            shift_date=plan_data.shift_date,
            start_time=plan_data.start_time,
            end_time=plan_data.end_time,
            target_shift_power=plan_data.target_shift_power,
            selected_devices=plan_data.selected_devices,
            constraints=plan_data.constraints or {},
            expected_cost_saving=plan_data.expected_cost_saving,
            expected_energy_saving=plan_data.expected_energy_saving,
            description=plan_data.description,
            status=ShiftPlanStatus.DRAFT,
            approval_status=ApprovalStatus.PENDING,
            execution_status=ExecutionStatus.NOT_STARTED,
            created_by=user_id,
        )

        db.add(plan)
        await db.commit()
        await db.refresh(plan)

        return plan

    @staticmethod
    async def get_plan(db: AsyncSession, plan_id: int) -> Optional[ShiftPlan]:
        """
        Get shift plan by ID - 获取转移计划

        Args:
            db: Database session
            plan_id: Plan ID

        Returns:
            Shift plan or None
        """
        result = await db.execute(select(ShiftPlan).where(ShiftPlan.id == plan_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_plans(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        status: Optional[ShiftPlanStatus] = None,
        shift_date_from: Optional[date] = None,
        shift_date_to: Optional[date] = None,
        created_by: Optional[int] = None,
    ) -> List[ShiftPlan]:
        """
        Get shift plans with filters - 获取转移计划列表

        Args:
            db: Database session
            skip: Offset
            limit: Limit
            status: Filter by status
            shift_date_from: Filter by shift date from (inclusive)
            shift_date_to: Filter by shift date to (inclusive)
            created_by: Filter by creator

        Returns:
            List of shift plans
        """
        query = select(ShiftPlan)

        # Apply filters
        conditions = []
        if status:
            conditions.append(ShiftPlan.status == status)
        if shift_date_from:
            conditions.append(ShiftPlan.shift_date >= shift_date_from)
        if shift_date_to:
            conditions.append(ShiftPlan.shift_date <= shift_date_to)
        if created_by:
            conditions.append(ShiftPlan.created_by == created_by)

        if conditions:
            query = query.where(and_(*conditions))

        # Order by created_at desc
        query = query.order_by(ShiftPlan.created_at.desc())

        # Pagination
        query = query.offset(skip).limit(limit)

        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def update_plan(db: AsyncSession, plan_id: int, plan_data: ShiftPlanUpdate) -> Optional[ShiftPlan]:
        """
        Update shift plan - 更新转移计划

        Args:
            db: Database session
            plan_id: Plan ID
            plan_data: Plan update data

        Returns:
            Updated shift plan or None
        """
        plan = await ShiftPlanService.get_plan(db, plan_id)
        if not plan:
            return None

        # Only allow update if plan is in draft or pending_approval status
        if plan.status not in [ShiftPlanStatus.DRAFT, ShiftPlanStatus.PENDING_APPROVAL]:
            raise ValueError(f"Cannot update plan in status: {plan.status}")

        # Update fields
        update_data = plan_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(plan, field, value)

        await db.commit()
        await db.refresh(plan)

        return plan

    @staticmethod
    async def delete_plan(db: AsyncSession, plan_id: int) -> bool:
        """
        Delete shift plan - 删除转移计划

        Args:
            db: Database session
            plan_id: Plan ID

        Returns:
            True if deleted, False if not found
        """
        plan = await ShiftPlanService.get_plan(db, plan_id)
        if not plan:
            return False

        # Only allow delete if plan is in draft status
        if plan.status != ShiftPlanStatus.DRAFT:
            raise ValueError(f"Cannot delete plan in status: {plan.status}")

        await db.delete(plan)
        await db.commit()

        return True

    @staticmethod
    async def submit_for_approval(db: AsyncSession, plan_id: int) -> Optional[ShiftPlan]:
        """
        Submit plan for approval - 提交审批

        Args:
            db: Database session
            plan_id: Plan ID

        Returns:
            Updated shift plan or None
        """
        plan = await ShiftPlanService.get_plan(db, plan_id)
        if not plan:
            return None

        # Only allow submit if plan is in draft status
        if plan.status != ShiftPlanStatus.DRAFT:
            raise ValueError(f"Cannot submit plan in status: {plan.status}")

        plan.status = ShiftPlanStatus.PENDING_APPROVAL
        plan.approval_status = ApprovalStatus.PENDING

        await db.commit()
        await db.refresh(plan)

        return plan

    @staticmethod
    async def approve_plan(
        db: AsyncSession, plan_id: int, approval_data: ShiftPlanApproval, approver_id: int
    ) -> Optional[ShiftPlan]:
        """
        Approve or reject plan - 审批计划

        Args:
            db: Database session
            plan_id: Plan ID
            approval_data: Approval data
            approver_id: Approver user ID

        Returns:
            Updated shift plan or None
        """
        plan = await ShiftPlanService.get_plan(db, plan_id)
        if not plan:
            return None

        # Only allow approve if plan is pending approval
        if plan.status != ShiftPlanStatus.PENDING_APPROVAL:
            raise ValueError(f"Cannot approve plan in status: {plan.status}")

        plan.approval_status = approval_data.approval_status
        plan.approval_comment = approval_data.approval_comment
        plan.approved_by = approver_id
        plan.approved_at = datetime.now()

        # Update plan status based on approval result
        if approval_data.approval_status == ApprovalStatus.APPROVED:
            plan.status = ShiftPlanStatus.APPROVED
        elif approval_data.approval_status == ApprovalStatus.REJECTED:
            plan.status = ShiftPlanStatus.REJECTED

        await db.commit()
        await db.refresh(plan)

        return plan

    @staticmethod
    async def start_execution(db: AsyncSession, plan_id: int) -> Optional[ShiftPlan]:
        """
        Start plan execution - 开始执行计划

        Args:
            db: Database session
            plan_id: Plan ID

        Returns:
            Updated shift plan or None
        """
        plan = await ShiftPlanService.get_plan(db, plan_id)
        if not plan:
            return None

        # Only allow execution if plan is approved
        if plan.status != ShiftPlanStatus.APPROVED:
            raise ValueError(f"Cannot execute plan in status: {plan.status}")

        plan.status = ShiftPlanStatus.EXECUTING
        plan.execution_status = ExecutionStatus.IN_PROGRESS
        plan.executed_at = datetime.now()

        await db.commit()
        await db.refresh(plan)

        return plan

    @staticmethod
    async def complete_execution(
        db: AsyncSession,
        plan_id: int,
        actual_shift_power: float,
        actual_cost_saving: float,
        actual_energy_saving: float,
    ) -> Optional[ShiftPlan]:
        """
        Complete plan execution - 完成执行

        Args:
            db: Database session
            plan_id: Plan ID
            actual_shift_power: Actual shift power
            actual_cost_saving: Actual cost saving
            actual_energy_saving: Actual energy saving

        Returns:
            Updated shift plan or None
        """
        plan = await ShiftPlanService.get_plan(db, plan_id)
        if not plan:
            return None

        # Only allow complete if plan is executing
        if plan.status != ShiftPlanStatus.EXECUTING:
            raise ValueError(f"Cannot complete plan in status: {plan.status}")

        plan.status = ShiftPlanStatus.COMPLETED
        plan.execution_status = ExecutionStatus.COMPLETED
        plan.actual_shift_power = actual_shift_power
        plan.actual_cost_saving = actual_cost_saving
        plan.actual_energy_saving = actual_energy_saving
        plan.completed_at = datetime.now()

        await db.commit()
        await db.refresh(plan)

        return plan

    @staticmethod
    async def fail_execution(db: AsyncSession, plan_id: int, error_message: str) -> Optional[ShiftPlan]:
        """
        Mark plan execution as failed - 标记执行失败

        Args:
            db: Database session
            plan_id: Plan ID
            error_message: Error message

        Returns:
            Updated shift plan or None
        """
        plan = await ShiftPlanService.get_plan(db, plan_id)
        if not plan:
            return None

        plan.status = ShiftPlanStatus.FAILED
        plan.execution_status = ExecutionStatus.FAILED
        plan.error_message = error_message

        await db.commit()
        await db.refresh(plan)

        return plan

    @staticmethod
    async def cancel_plan(db: AsyncSession, plan_id: int) -> Optional[ShiftPlan]:
        """
        Cancel plan - 取消计划

        Args:
            db: Database session
            plan_id: Plan ID

        Returns:
            Updated shift plan or None
        """
        plan = await ShiftPlanService.get_plan(db, plan_id)
        if not plan:
            return None

        # Only allow cancel if plan is not completed or failed
        if plan.status in [ShiftPlanStatus.COMPLETED, ShiftPlanStatus.FAILED]:
            raise ValueError(f"Cannot cancel plan in status: {plan.status}")

        plan.status = ShiftPlanStatus.CANCELLED
        plan.execution_status = ExecutionStatus.CANCELLED

        await db.commit()
        await db.refresh(plan)

        return plan

    @staticmethod
    async def get_plan_statistics(
        db: AsyncSession, start_date: Optional[date] = None, end_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Get plan statistics - 获取计划统计

        Args:
            db: Database session
            start_date: Start date filter
            end_date: End date filter

        Returns:
            Statistics dictionary
        """
        query = select(ShiftPlan)

        # Apply date filters
        conditions = []
        if start_date:
            conditions.append(ShiftPlan.shift_date >= start_date)
        if end_date:
            conditions.append(ShiftPlan.shift_date <= end_date)

        if conditions:
            query = query.where(and_(*conditions))

        result = await db.execute(query)
        plans = result.scalars().all()

        # Calculate statistics
        total_plans = len(plans)
        completed_plans = len([p for p in plans if p.status == ShiftPlanStatus.COMPLETED])
        failed_plans = len([p for p in plans if p.status == ShiftPlanStatus.FAILED])
        pending_approval = len([p for p in plans if p.status == ShiftPlanStatus.PENDING_APPROVAL])
        executing = len([p for p in plans if p.status == ShiftPlanStatus.EXECUTING])

        total_shift_power = sum(p.actual_shift_power or 0 for p in plans if p.status == ShiftPlanStatus.COMPLETED)
        total_cost_saving = sum(p.actual_cost_saving or 0 for p in plans if p.status == ShiftPlanStatus.COMPLETED)
        total_energy_saving = sum(p.actual_energy_saving or 0 for p in plans if p.status == ShiftPlanStatus.COMPLETED)

        success_rate = completed_plans / total_plans if total_plans > 0 else 0

        return {
            "total_plans": total_plans,
            "completed_plans": completed_plans,
            "failed_plans": failed_plans,
            "pending_approval": pending_approval,
            "executing": executing,
            "total_shift_power": total_shift_power,
            "total_cost_saving": total_cost_saving,
            "total_energy_saving": total_energy_saving,
            "success_rate": success_rate,
        }

    @staticmethod
    async def _generate_plan_code(db: AsyncSession, shift_date: date) -> str:
        """
        Generate unique plan code - 生成唯一计划编码

        Args:
            db: Database session
            shift_date: Shift date

        Returns:
            Plan code (format: SHIFT-YYYYMMDD-NNNN)
        """
        date_str = shift_date.strftime("%Y%m%d")
        prefix = f"SHIFT-{date_str}"

        # Get count of plans on this date
        result = await db.execute(select(func.count(ShiftPlan.id)).where(ShiftPlan.plan_code.like(f"{prefix}%")))
        count = result.scalar() or 0

        # Generate code with 4-digit sequence number
        plan_code = f"{prefix}-{count + 1:04d}"

        return plan_code
