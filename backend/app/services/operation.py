"""
运维管理服务
Operation Management Service

提供工单管理、巡检计划、巡检任务、知识库管理功能
"""
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..models.operation import (
    WorkOrder, WorkOrderLog, WorkOrderStatus,
    InspectionPlan, InspectionTask, InspectionStatus,
    KnowledgeBase
)
from ..schemas.operation import (
    WorkOrderCreate, WorkOrderUpdate,
    InspectionPlanCreate, InspectionPlanUpdate,
    InspectionTaskCreate, InspectionTaskUpdate,
    KnowledgeCreate, KnowledgeUpdate,
    OperationStatistics
)


class OperationService:
    """运维管理服务"""

    # ==================== 辅助方法 ====================

    def _generate_order_no(self, db: Session, prefix: str) -> str:
        """
        生成订单/任务编号

        Args:
            db: 数据库会话
            prefix: 编号前缀 (WO 或 IT)

        Returns:
            格式化的编号 (如 WO-20240115-001)
        """
        today = datetime.now().strftime("%Y%m%d")

        if prefix == "WO":
            # 统计今天创建的工单数量
            count = db.query(func.count(WorkOrder.id)).filter(
                WorkOrder.order_no.like(f"WO-{today}-%")
            ).scalar() or 0
        elif prefix == "IT":
            # 统计今天创建的巡检任务数量
            count = db.query(func.count(InspectionTask.id)).filter(
                InspectionTask.task_no.like(f"IT-{today}-%")
            ).scalar() or 0
        else:
            count = 0

        return f"{prefix}-{today}-{count + 1:03d}"

    # ==================== 工单管理 ====================

    def get_work_orders(
        self,
        db: Session,
        skip: int = 0,
        limit: int = 100,
        status: Optional[WorkOrderStatus] = None,
        priority: Optional[str] = None
    ) -> List[WorkOrder]:
        """
        获取工单列表

        Args:
            db: 数据库会话
            skip: 跳过记录数
            limit: 返回记录数
            status: 工单状态过滤
            priority: 优先级过滤

        Returns:
            工单列表
        """
        query = db.query(WorkOrder)

        if status:
            query = query.filter(WorkOrder.status == status)
        if priority:
            query = query.filter(WorkOrder.priority == priority)

        return query.order_by(WorkOrder.created_at.desc()).offset(skip).limit(limit).all()

    def get_work_order(
        self,
        db: Session,
        order_id: int
    ) -> Optional[WorkOrder]:
        """
        根据ID获取工单

        Args:
            db: 数据库会话
            order_id: 工单ID

        Returns:
            工单对象或None
        """
        return db.query(WorkOrder).filter(WorkOrder.id == order_id).first()

    def create_work_order(
        self,
        db: Session,
        data: WorkOrderCreate
    ) -> WorkOrder:
        """
        创建工单

        Args:
            db: 数据库会话
            data: 工单创建数据

        Returns:
            创建的工单对象
        """
        order_no = self._generate_order_no(db, "WO")
        order = WorkOrder(
            order_no=order_no,
            **data.model_dump()
        )

        db.add(order)
        db.commit()
        db.refresh(order)

        # 添加创建日志
        self.add_work_order_log(db, order.id, "创建", f"工单 {order_no} 创建成功", "系统")

        return order

    def update_work_order(
        self,
        db: Session,
        order_id: int,
        data: WorkOrderUpdate
    ) -> Optional[WorkOrder]:
        """
        更新工单

        Args:
            db: 数据库会话
            order_id: 工单ID
            data: 更新数据

        Returns:
            更新后的工单对象或None
        """
        order = self.get_work_order(db, order_id)
        if not order:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if value is not None:
                setattr(order, key, value)

        db.commit()
        db.refresh(order)
        return order

    def delete_work_order(
        self,
        db: Session,
        order_id: int
    ) -> bool:
        """
        删除工单

        Args:
            db: 数据库会话
            order_id: 工单ID

        Returns:
            是否删除成功
        """
        order = self.get_work_order(db, order_id)
        if not order:
            return False

        db.delete(order)
        db.commit()
        return True

    def assign_work_order(
        self,
        db: Session,
        order_id: int,
        assignee: str
    ) -> Optional[WorkOrder]:
        """
        派单给指定处理人

        Args:
            db: 数据库会话
            order_id: 工单ID
            assignee: 处理人

        Returns:
            更新后的工单对象或None
        """
        order = self.get_work_order(db, order_id)
        if not order:
            return None

        order.assignee = assignee
        order.assigned_at = datetime.now()
        order.status = WorkOrderStatus.assigned

        db.commit()
        db.refresh(order)

        # 添加派单日志
        self.add_work_order_log(db, order_id, "派单", f"工单已派发给 {assignee}", "系统")

        return order

    def start_work_order(
        self,
        db: Session,
        order_id: int
    ) -> Optional[WorkOrder]:
        """
        开始处理工单

        Args:
            db: 数据库会话
            order_id: 工单ID

        Returns:
            更新后的工单对象或None
        """
        order = self.get_work_order(db, order_id)
        if not order:
            return None

        order.status = WorkOrderStatus.processing
        order.started_at = datetime.now()

        db.commit()
        db.refresh(order)

        # 添加开始处理日志
        self.add_work_order_log(db, order_id, "开始处理", "工单开始处理", order.assignee or "系统")

        return order

    def complete_work_order(
        self,
        db: Session,
        order_id: int,
        solution: Optional[str] = None,
        root_cause: Optional[str] = None
    ) -> Optional[WorkOrder]:
        """
        完成工单

        Args:
            db: 数据库会话
            order_id: 工单ID
            solution: 解决方案
            root_cause: 根本原因

        Returns:
            更新后的工单对象或None
        """
        order = self.get_work_order(db, order_id)
        if not order:
            return None

        order.status = WorkOrderStatus.completed
        order.completed_at = datetime.now()
        if solution:
            order.solution = solution
        if root_cause:
            order.root_cause = root_cause

        db.commit()
        db.refresh(order)

        # 添加完成日志
        self.add_work_order_log(db, order_id, "完成", "工单处理完成", order.assignee or "系统")

        return order

    def add_work_order_log(
        self,
        db: Session,
        order_id: int,
        action: str,
        content: str,
        operator: str
    ) -> WorkOrderLog:
        """
        添加工单日志

        Args:
            db: 数据库会话
            order_id: 工单ID
            action: 操作类型
            content: 操作内容
            operator: 操作人

        Returns:
            创建的日志对象
        """
        log = WorkOrderLog(
            order_id=order_id,
            action=action,
            content=content,
            operator=operator
        )

        db.add(log)
        db.commit()
        db.refresh(log)
        return log

    def get_work_order_logs(
        self,
        db: Session,
        order_id: int
    ) -> List[WorkOrderLog]:
        """
        获取工单日志

        Args:
            db: 数据库会话
            order_id: 工单ID

        Returns:
            日志列表
        """
        return db.query(WorkOrderLog).filter(
            WorkOrderLog.order_id == order_id
        ).order_by(WorkOrderLog.created_at.desc()).all()

    # ==================== 巡检计划管理 ====================

    def get_inspection_plans(
        self,
        db: Session,
        skip: int = 0,
        limit: int = 100
    ) -> List[InspectionPlan]:
        """
        获取巡检计划列表

        Args:
            db: 数据库会话
            skip: 跳过记录数
            limit: 返回记录数

        Returns:
            巡检计划列表
        """
        return db.query(InspectionPlan).offset(skip).limit(limit).all()

    def get_inspection_plan(
        self,
        db: Session,
        plan_id: int
    ) -> Optional[InspectionPlan]:
        """
        根据ID获取巡检计划

        Args:
            db: 数据库会话
            plan_id: 计划ID

        Returns:
            巡检计划对象或None
        """
        return db.query(InspectionPlan).filter(InspectionPlan.id == plan_id).first()

    def create_inspection_plan(
        self,
        db: Session,
        data: InspectionPlanCreate
    ) -> InspectionPlan:
        """
        创建巡检计划

        Args:
            db: 数据库会话
            data: 巡检计划创建数据

        Returns:
            创建的巡检计划对象
        """
        plan = InspectionPlan(**data.model_dump())

        db.add(plan)
        db.commit()
        db.refresh(plan)
        return plan

    def update_inspection_plan(
        self,
        db: Session,
        plan_id: int,
        data: InspectionPlanUpdate
    ) -> Optional[InspectionPlan]:
        """
        更新巡检计划

        Args:
            db: 数据库会话
            plan_id: 计划ID
            data: 更新数据

        Returns:
            更新后的巡检计划对象或None
        """
        plan = self.get_inspection_plan(db, plan_id)
        if not plan:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if value is not None:
                setattr(plan, key, value)

        plan.updated_at = datetime.now()
        db.commit()
        db.refresh(plan)
        return plan

    def delete_inspection_plan(
        self,
        db: Session,
        plan_id: int
    ) -> bool:
        """
        删除巡检计划

        Args:
            db: 数据库会话
            plan_id: 计划ID

        Returns:
            是否删除成功
        """
        plan = self.get_inspection_plan(db, plan_id)
        if not plan:
            return False

        db.delete(plan)
        db.commit()
        return True

    # ==================== 巡检任务管理 ====================

    def get_inspection_tasks(
        self,
        db: Session,
        skip: int = 0,
        limit: int = 100,
        status: Optional[InspectionStatus] = None
    ) -> List[InspectionTask]:
        """
        获取巡检任务列表

        Args:
            db: 数据库会话
            skip: 跳过记录数
            limit: 返回记录数
            status: 任务状态过滤

        Returns:
            巡检任务列表
        """
        query = db.query(InspectionTask)

        if status:
            query = query.filter(InspectionTask.status == status)

        return query.order_by(InspectionTask.created_at.desc()).offset(skip).limit(limit).all()

    def get_inspection_task(
        self,
        db: Session,
        task_id: int
    ) -> Optional[InspectionTask]:
        """
        根据ID获取巡检任务

        Args:
            db: 数据库会话
            task_id: 任务ID

        Returns:
            巡检任务对象或None
        """
        return db.query(InspectionTask).filter(InspectionTask.id == task_id).first()

    def create_inspection_task(
        self,
        db: Session,
        data: InspectionTaskCreate
    ) -> InspectionTask:
        """
        创建巡检任务

        Args:
            db: 数据库会话
            data: 巡检任务创建数据

        Returns:
            创建的巡检任务对象
        """
        task_no = self._generate_order_no(db, "IT")
        task = InspectionTask(
            task_no=task_no,
            **data.model_dump()
        )

        db.add(task)
        db.commit()
        db.refresh(task)
        return task

    def update_inspection_task(
        self,
        db: Session,
        task_id: int,
        data: InspectionTaskUpdate
    ) -> Optional[InspectionTask]:
        """
        更新巡检任务

        Args:
            db: 数据库会话
            task_id: 任务ID
            data: 更新数据

        Returns:
            更新后的巡检任务对象或None
        """
        task = self.get_inspection_task(db, task_id)
        if not task:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if value is not None:
                setattr(task, key, value)

        db.commit()
        db.refresh(task)
        return task

    def start_inspection_task(
        self,
        db: Session,
        task_id: int
    ) -> Optional[InspectionTask]:
        """
        开始巡检任务

        Args:
            db: 数据库会话
            task_id: 任务ID

        Returns:
            更新后的巡检任务对象或None
        """
        task = self.get_inspection_task(db, task_id)
        if not task:
            return None

        task.status = InspectionStatus.in_progress
        task.started_at = datetime.now()

        db.commit()
        db.refresh(task)
        return task

    def complete_inspection_task(
        self,
        db: Session,
        task_id: int,
        result: Optional[str] = None,
        abnormal_count: Optional[int] = None
    ) -> Optional[InspectionTask]:
        """
        完成巡检任务

        Args:
            db: 数据库会话
            task_id: 任务ID
            result: 巡检结果(JSON)
            abnormal_count: 异常数量

        Returns:
            更新后的巡检任务对象或None
        """
        task = self.get_inspection_task(db, task_id)
        if not task:
            return None

        task.status = InspectionStatus.completed
        task.completed_at = datetime.now()
        if result:
            task.result = result
        if abnormal_count is not None:
            task.abnormal_count = abnormal_count

        db.commit()
        db.refresh(task)
        return task

    # ==================== 知识库管理 ====================

    def get_knowledge_list(
        self,
        db: Session,
        skip: int = 0,
        limit: int = 100,
        category: Optional[str] = None
    ) -> List[KnowledgeBase]:
        """
        获取知识库列表

        Args:
            db: 数据库会话
            skip: 跳过记录数
            limit: 返回记录数
            category: 分类过滤

        Returns:
            知识库条目列表
        """
        query = db.query(KnowledgeBase)

        if category:
            query = query.filter(KnowledgeBase.category == category)

        return query.order_by(KnowledgeBase.created_at.desc()).offset(skip).limit(limit).all()

    def get_knowledge(
        self,
        db: Session,
        knowledge_id: int
    ) -> Optional[KnowledgeBase]:
        """
        根据ID获取知识库条目，并增加查看次数

        Args:
            db: 数据库会话
            knowledge_id: 条目ID

        Returns:
            知识库条目对象或None
        """
        knowledge = db.query(KnowledgeBase).filter(KnowledgeBase.id == knowledge_id).first()
        if knowledge:
            knowledge.view_count = (knowledge.view_count or 0) + 1
            db.commit()
            db.refresh(knowledge)
        return knowledge

    def create_knowledge(
        self,
        db: Session,
        data: KnowledgeCreate
    ) -> KnowledgeBase:
        """
        创建知识库条目

        Args:
            db: 数据库会话
            data: 知识库条目创建数据

        Returns:
            创建的知识库条目对象
        """
        knowledge = KnowledgeBase(**data.model_dump())

        db.add(knowledge)
        db.commit()
        db.refresh(knowledge)
        return knowledge

    def update_knowledge(
        self,
        db: Session,
        knowledge_id: int,
        data: KnowledgeUpdate
    ) -> Optional[KnowledgeBase]:
        """
        更新知识库条目

        Args:
            db: 数据库会话
            knowledge_id: 条目ID
            data: 更新数据

        Returns:
            更新后的知识库条目对象或None
        """
        knowledge = db.query(KnowledgeBase).filter(KnowledgeBase.id == knowledge_id).first()
        if not knowledge:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if value is not None:
                setattr(knowledge, key, value)

        knowledge.updated_at = datetime.now()
        db.commit()
        db.refresh(knowledge)
        return knowledge

    def delete_knowledge(
        self,
        db: Session,
        knowledge_id: int
    ) -> bool:
        """
        删除知识库条目

        Args:
            db: 数据库会话
            knowledge_id: 条目ID

        Returns:
            是否删除成功
        """
        knowledge = db.query(KnowledgeBase).filter(KnowledgeBase.id == knowledge_id).first()
        if not knowledge:
            return False

        db.delete(knowledge)
        db.commit()
        return True

    # ==================== 统计分析 ====================

    def get_statistics(self, db: Session) -> OperationStatistics:
        """
        获取运维统计信息

        Args:
            db: 数据库会话

        Returns:
            运维统计对象
        """
        # 工单统计
        total_orders = db.query(func.count(WorkOrder.id)).scalar() or 0
        pending_orders = db.query(func.count(WorkOrder.id)).filter(
            WorkOrder.status == WorkOrderStatus.pending
        ).scalar() or 0
        processing_orders = db.query(func.count(WorkOrder.id)).filter(
            WorkOrder.status == WorkOrderStatus.processing
        ).scalar() or 0
        completed_orders = db.query(func.count(WorkOrder.id)).filter(
            WorkOrder.status == WorkOrderStatus.completed
        ).scalar() or 0

        # 逾期巡检统计
        overdue_inspections = db.query(func.count(InspectionTask.id)).filter(
            InspectionTask.status == InspectionStatus.overdue
        ).scalar() or 0

        # 知识库统计
        knowledge_count = db.query(func.count(KnowledgeBase.id)).scalar() or 0

        return OperationStatistics(
            total_orders=total_orders,
            pending_orders=pending_orders,
            processing_orders=processing_orders,
            completed_orders=completed_orders,
            overdue_inspections=overdue_inspections,
            knowledge_count=knowledge_count
        )


# 单例实例
operation_service = OperationService()
