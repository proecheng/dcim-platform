"""
概率调参服务
Story 26.3: 闭环学习自动调参
"""

import logging
from datetime import datetime
from typing import Optional
from sqlalchemy import select, and_, func, desc
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session
from app.models.diagnosis import ProbabilityAdjustmentLog, DiagnosisResult, DiagnosisAnnotation
from app.models.fault_tree import FaultTreeNode
from app.schemas.probability_tuning import ProbabilityAdjustmentCreate

logger = logging.getLogger(__name__)


class ProbabilityTuningService:
    """概率调参服务"""

    def __init__(self):
        pass

    async def analyze_all_trees(self) -> dict:
        """
        分析所有活跃故障树，生成调参建议

        Returns:
            dict: {
                "analyzed_trees": int,
                "total_adjustments": int,
                "pending_approvals": int
            }
        """
        logger.info("开始执行概率调参分析")

        # Story 26.9: 前置训练数据质量检查
        audit_result = None
        try:
            from app.services.diagnosis.training_data_audit_service import training_data_audit_service
            audit_result = await training_data_audit_service.run_anomaly_detection()
            if audit_result.get("status") == "aborted":
                logger.critical("训练数据质量检查未通过，中止概率调参")
                result = {
                    "analyzed_trees": 0,
                    "analyzed_nodes": 0,
                    "total_adjustments": 0,
                    "pending_approvals": 0,
                }
                result["audit_result"] = audit_result
                return result
        except ImportError:
            logger.info("training_data_audit_service 不可用，跳过数据质量检查")
        except Exception as e:
            logger.error(f"训练数据质量检查失败: {e}", exc_info=True)

        analyzed_trees = 0
        total_adjustments = 0

        async with async_session() as session:
            # 查询所有活跃故障树
            # 注意：这里假设 FaultTree 模型已存在（Story 24.4）
            # 实际实现时需要导入 FaultTree 模型
            # from app.models.fault_tree import FaultTree
            # result = await session.execute(
            #     select(FaultTree).where(FaultTree.status == 'active')
            # )
            # active_trees = result.scalars().all()

            # 临时实现：假设没有活跃故障树
            active_trees = []

            for tree in active_trees:
                try:
                    adjustments = await self._analyze_tree(session, tree.id)
                    total_adjustments += len(adjustments)
                    analyzed_trees += 1
                except Exception as e:
                    logger.error(f"分析故障树 {tree.id} 失败: {e}", exc_info=True)

            await session.commit()

        logger.info(f"概率调参分析完成: 分析了 {analyzed_trees} 个故障树，生成 {total_adjustments} 条调参建议")

        return {
            "analyzed_trees": analyzed_trees,
            "analyzed_nodes": 0,
            "total_adjustments": total_adjustments,
            "pending_approvals": total_adjustments
        }

    async def _analyze_tree(self, session: AsyncSession, tree_id: int) -> list[ProbabilityAdjustmentLog]:
        """
        分析单个故障树，生成调参建议

        Args:
            session: 数据库会话
            tree_id: 故障树ID

        Returns:
            list[ProbabilityAdjustmentLog]: 生成的调参记录列表
        """
        adjustments = []

        # 查询所有节点
        # 注意：这里假设 FaultTreeNode 模型已存在（Story 24.4）
        # from app.models.fault_tree import FaultTreeNode
        # result = await session.execute(
        #     select(FaultTreeNode).where(FaultTreeNode.tree_id == tree_id)
        # )
        # nodes = result.scalars().all()

        # 临时实现：假设没有节点
        nodes = []

        for node in nodes:
            # 查询该节点的标注数据统计
            annotation_stats = await self._get_annotation_stats(session, node.id)

            if annotation_stats['total_count'] < 50:
                logger.info(f"节点 {node.id} 样本数不足（{annotation_stats['total_count']} < 50），跳过调参")
                continue

            # 根据节点类型计算调参建议
            if node.node_type == 'root':
                proposed_prob, adjustment_pct = self._calculate_root_node_adjustment(
                    node.id,
                    node.prior_probability,
                    annotation_stats['accurate_count'],
                    annotation_stats['total_count']
                )
            else:
                # 中间/叶节点
                diagnoses_with_node = await self._get_diagnoses_with_node(session, node.id)
                proposed_prob, adjustment_pct, should_adjust = self._calculate_intermediate_node_adjustment(
                    node.id,
                    node.prior_probability,
                    diagnoses_with_node
                )

                if not should_adjust:
                    continue

            # 创建调参记录
            adjustment = ProbabilityAdjustmentLog(
                tree_id=tree_id,
                node_id=node.id,
                node_name=node.name,
                node_type=node.node_type,
                current_probability=node.prior_probability,
                proposed_probability=proposed_prob,
                adjustment_percent=adjustment_pct,
                sample_count=annotation_stats['total_count'],
                accurate_count=annotation_stats['accurate_count'],
                inaccurate_count=annotation_stats['inaccurate_count'],
                accuracy_rate=annotation_stats['accuracy_rate'],
                status='pending'
            )

            session.add(adjustment)
            adjustments.append(adjustment)

        return adjustments

    async def _get_annotation_stats(self, session: AsyncSession, node_id: int) -> dict:
        """
        获取节点的标注数据统计

        Args:
            session: 数据库会话
            node_id: 节点ID

        Returns:
            dict: {
                "total_count": int,
                "accurate_count": int,
                "inaccurate_count": int,
                "accuracy_rate": float
            }
        """
        # 查询该节点作为根因的诊断结果的标注统计
        # 通过 root_cause 字段匹配节点名称（因为 root_cause 存储的是节点名称）
        node = await session.get(FaultTreeNode, node_id)
        if not node:
            return {
                "total_count": 0,
                "accurate_count": 0,
                "inaccurate_count": 0,
                "accuracy_rate": 0.0
            }

        result = await session.execute(
            select(
                func.count(DiagnosisAnnotation.id).label('total_count'),
                func.sum(
                    func.case((DiagnosisAnnotation.annotation == 'accurate', 1), else_=0)
                ).label('accurate_count'),
                func.sum(
                    func.case((DiagnosisAnnotation.annotation == 'inaccurate', 1), else_=0)
                ).label('inaccurate_count')
            )
            .select_from(DiagnosisAnnotation)
            .join(DiagnosisResult, DiagnosisAnnotation.result_id == DiagnosisResult.id)
            .where(DiagnosisResult.root_cause == node.name)
        )

        row = result.first()

        total_count = row.total_count or 0
        accurate_count = row.accurate_count or 0
        inaccurate_count = row.inaccurate_count or 0

        accuracy_rate = accurate_count / total_count if total_count > 0 else 0.0

        return {
            "total_count": total_count,
            "accurate_count": accurate_count,
            "inaccurate_count": inaccurate_count,
            "accuracy_rate": accuracy_rate
        }

    async def _get_diagnoses_with_node(self, session: AsyncSession, node_id: int) -> list[DiagnosisResult]:
        """
        获取该节点参与的所有诊断（推理过程中后验概率 > 0）

        Args:
            session: 数据库会话
            node_id: 节点ID

        Returns:
            list[DiagnosisResult]: 诊断结果列表
        """
        # 获取节点名称
        node = await session.get(FaultTreeNode, node_id)
        if not node:
            return []

        # 查询 evidence 字段中包含该节点名称的诊断结果
        # evidence 是 JSON 字段，包含推理过程中的证据信息
        # 如果节点参与了诊断，其名称会出现在 evidence 中
        result = await session.execute(
            select(DiagnosisResult)
            .where(DiagnosisResult.evidence.like(f'%{node.name}%'))
            .options(selectinload(DiagnosisResult.annotation))
        )

        return list(result.scalars().all())

    def _calculate_root_node_adjustment(
        self,
        node_id: int,
        current_prior: float,
        accurate_count: int,
        total_count: int
    ) -> tuple[float, float]:
        """
        计算根因节点的调参建议

        Args:
            node_id: 节点ID
            current_prior: 当前先验概率
            accurate_count: 准确标注次数
            total_count: 总标注次数

        Returns:
            (proposed_probability, adjustment_percent)
        """
        # 防止除零错误
        if total_count == 0:
            logger.warning(f"节点 {node_id} 标注总数为 0，跳过调参")
            return current_prior, 0.0

        # 计算准确率
        accuracy_rate = accurate_count / total_count

        # 调整方向 = 准确率 - 先验概率
        adjustment = accuracy_rate - current_prior

        # 限制调整幅度：最多 ±10%（至少 0.01，避免零先验永远无法增长）
        max_adjustment = max(current_prior * 0.10, 0.01)
        if abs(adjustment) > max_adjustment:
            adjustment = max_adjustment if adjustment > 0 else -max_adjustment

        proposed_probability = current_prior + adjustment

        # 确保概率在 [0.01, 0.99] 范围内
        proposed_probability = max(0.01, min(0.99, proposed_probability))

        # 重新计算实际调整量（因为可能被边界截断）
        actual_adjustment = proposed_probability - current_prior

        # 防止除零错误
        if current_prior == 0:
            adjustment_percent = 0.0
        else:
            adjustment_percent = (actual_adjustment / current_prior) * 100

        return proposed_probability, adjustment_percent

    def _calculate_intermediate_node_adjustment(
        self,
        node_id: int,
        current_prior: float,
        diagnoses_with_node: list[DiagnosisResult]
    ) -> tuple[float, float, bool]:
        """
        计算中间/叶节点的调参建议

        "参与诊断"定义: 该节点在推理过程中被激活（后验概率 > 0）
        "准确诊断"定义: 该节点参与的诊断，其最终根因结论被标注为"准确"

        Args:
            node_id: 节点ID
            current_prior: 当前先验概率
            diagnoses_with_node: 该节点参与的诊断列表

        Returns:
            (proposed_probability, adjustment_percent, should_adjust)
        """
        # 统计该节点参与的所有诊断中，最终结论被标注为"准确"的比例
        accurate_diagnoses = [
            d for d in diagnoses_with_node
            if hasattr(d, 'annotation') and d.annotation and d.annotation.annotation == 'accurate'
        ]

        if not diagnoses_with_node:
            logger.info(f"节点 {node_id} 未参与任何诊断，跳过调参")
            return current_prior, 0.0, False

        participation_accuracy = len(accurate_diagnoses) / len(diagnoses_with_node)

        # 若与当前先验概率偏差 > 10%，标记为"建议调参"
        deviation = abs(participation_accuracy - current_prior)
        should_adjust = deviation > 0.10

        if should_adjust:
            # 调整方向：向参与准确率靠拢
            adjustment = participation_accuracy - current_prior

            # 限制调整幅度：最多 ±10%（至少 0.01，避免零先验永远无法增长）
            max_adjustment = max(current_prior * 0.10, 0.01)
            if abs(adjustment) > max_adjustment:
                adjustment = max_adjustment if adjustment > 0 else -max_adjustment

            proposed_probability = current_prior + adjustment
            proposed_probability = max(0.01, min(0.99, proposed_probability))

            # 重新计算实际调整量（因为可能被边界截断）
            actual_adjustment = proposed_probability - current_prior

            # 防止除零错误
            if current_prior == 0:
                adjustment_percent = 0.0
            else:
                adjustment_percent = (actual_adjustment / current_prior) * 100
        else:
            proposed_probability = current_prior
            adjustment_percent = 0.0

        return proposed_probability, adjustment_percent, should_adjust

    async def notify_admins(self, result: dict):
        """
        通知管理员审批

        Args:
            result: 调参分析结果
        """
        from app.core.database import async_session
        from app.models.user import User
        from app.services.email_service import email_service
        from app.services.websocket import ws_manager

        logger.info(f"通知管理员审批: {result['pending_approvals']} 条待审批调参建议")

        # 查询所有管理员
        async with async_session() as session:
            admins_result = await session.execute(
                select(User).where(User.role == 'admin', User.is_active == True)
            )
            admins = admins_result.scalars().all()

        if not admins:
            logger.warning("没有找到管理员用户，跳过通知")
            return

        # 发送邮件通知
        if email_service.is_available():
            subject = "智能诊断系统 - 概率调参审批通知"
            html_content = f"""
            <html>
            <body>
                <h2>概率调参审批通知</h2>
                <p>系统已完成概率调参分析，生成了 <strong>{result['pending_approvals']}</strong> 条待审批的调参建议。</p>
                <h3>分析摘要</h3>
                <ul>
                    <li>分析故障树数量: {result['analyzed_trees']}</li>
                    <li>分析节点数量: {result['analyzed_nodes']}</li>
                    <li>生成调参建议: {result['total_adjustments']}</li>
                    <li>待审批数量: {result['pending_approvals']}</li>
                </ul>
                <p>请登录系统查看详情并进行审批。</p>
            </body>
            </html>
            """

            for admin in admins:
                if admin.email:
                    try:
                        await email_service.send_html_email(
                            to_email=admin.email,
                            subject=subject,
                            html_content=html_content
                        )
                    except Exception as e:
                        logger.error(f"发送邮件给 {admin.email} 失败: {e}")

        # 发送 WebSocket 通知
        for admin in admins:
            try:
                await ws_manager.send_to_user(
                    admin.id,
                    {
                        'type': 'probability_tuning_approval',
                        'pending_count': result['pending_approvals'],
                        'analyzed_trees': result['analyzed_trees'],
                        'analyzed_nodes': result['analyzed_nodes'],
                        'total_adjustments': result['total_adjustments']
                    }
                )
            except Exception as e:
                logger.error(f"发送 WebSocket 通知给用户 {admin.id} 失败: {e}")
