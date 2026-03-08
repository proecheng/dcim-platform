"""
误诊反馈报告服务
Story 26.2: 误诊反馈报告
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.diagnosis import (
    DiagnosisSession,
    DiagnosisResult,
    DiagnosisAnnotation,
    SystemReport,
    DiagnosisImprovementRule,
)
from app.models.alarm import Alarm
from app.models.operation import WorkOrder
from app.core.redis import redis_service

logger = logging.getLogger(__name__)


class MisdiagnosisReportService:
    """误诊反馈报告服务"""

    @staticmethod
    async def generate_monthly_report(
        period: str,
        db: AsyncSession,
    ) -> Optional[SystemReport]:
        """
        生成月度误诊分析报告

        Args:
            period: 报告周期，格式 YYYY-MM
            db: 数据库会话

        Returns:
            SystemReport 或 None（如果数据不足或获取锁失败）
        """
        logger.info("开始生成误诊分析报告: period=%s", period)

        # 1. 获取分布式锁（TTL 70秒）
        lock_key = f"report:misdiagnosis:lock:{period}"
        lock_acquired = False

        if redis_service.is_available:
            try:
                lock_acquired = redis_service.set_with_expiry(lock_key, "locked", 70)
                if not lock_acquired:
                    logger.warning("无法获取分布式锁，可能有其他任务正在执行: period=%s", period)
                    return None
            except Exception as e:
                logger.warning("Redis 锁获取失败，继续执行: %s", e)
                lock_acquired = False

        try:
            # 2. 检查报告是否已存在
            existing_report = await db.execute(
                select(SystemReport).where(
                    and_(
                        SystemReport.report_type == "misdiagnosis_monthly",
                        SystemReport.report_period == period,
                        SystemReport.deleted_at.is_(None),
                    )
                )
            )
            existing = existing_report.scalar_one_or_none()
            if existing:
                logger.info("报告已存在: period=%s", period)
                return existing

            # 3. 解析周期，计算时间范围
            try:
                year, month = map(int, period.split("-"))
                start_date = datetime(year, month, 1)
                if month == 12:
                    end_date = datetime(year + 1, 1, 1)
                else:
                    end_date = datetime(year, month + 1, 1)
            except (ValueError, IndexError) as e:
                logger.error("无效的周期格式: period=%s, error=%s", period, e)
                return None

            # 4. 统计总诊断次数
            total_diagnoses_result = await db.execute(
                select(func.count(DiagnosisSession.id)).where(
                    and_(
                        DiagnosisSession.created_at >= start_date,
                        DiagnosisSession.created_at < end_date,
                    )
                )
            )
            total_diagnoses = total_diagnoses_result.scalar() or 0

            if total_diagnoses == 0:
                logger.warning("无诊断数据: period=%s", period)
                return None

            # 5. 统计已标注次数
            annotated_count_result = await db.execute(
                select(func.count(DiagnosisAnnotation.id)).where(
                    and_(
                        DiagnosisAnnotation.created_at >= start_date,
                        DiagnosisAnnotation.created_at < end_date,
                    )
                )
            )
            annotated_count = annotated_count_result.scalar() or 0

            # 6. 识别误报（诊断有结论但标注为"不准确"）
            false_positives = await MisdiagnosisReportService._identify_false_positives(
                start_date, end_date, db
            )
            false_positive_count = len(false_positives)

            # 7. 识别漏报（告警产生但诊断引擎无结论或失败）
            false_negatives = await MisdiagnosisReportService._identify_false_negatives(
                start_date, end_date, db
            )
            false_negative_count = len(false_negatives)

            # 8. 计算准确率
            if annotated_count + false_negative_count == 0:
                accuracy_rate = None
            else:
                accuracy_rate = (annotated_count - false_positive_count) / (
                    annotated_count + false_negative_count
                )

            # 9. 统计高频误判节点
            top_misdiagnosed_nodes = await MisdiagnosisReportService._get_top_misdiagnosed_nodes(
                false_positives, top_n=5
            )

            # 10. 统计高频漏报故障类型
            top_missed_fault_types = await MisdiagnosisReportService._get_top_missed_fault_types(
                false_negatives, top_n=5
            )

            # 11. 统计设备类型分布
            device_type_distribution = await MisdiagnosisReportService._get_device_type_distribution(
                false_positives, db
            )

            # 12. 查询历史趋势（最多3个月）
            accuracy_trend = await MisdiagnosisReportService._get_accuracy_trend(
                period, db
            )

            # 13. 生成改进建议
            improvement_suggestions = await MisdiagnosisReportService._generate_improvement_suggestions(
                top_misdiagnosed_nodes, top_missed_fault_types, db
            )

            # 14. 生成 Markdown 报告
            content = MisdiagnosisReportService._generate_markdown_report(
                period=period,
                total_diagnoses=total_diagnoses,
                annotated_count=annotated_count,
                annotation_coverage=annotated_count / total_diagnoses if total_diagnoses > 0 else 0,
                accuracy_rate=accuracy_rate,
                false_positive_count=false_positive_count,
                false_negative_count=false_negative_count,
                top_misdiagnosed_nodes=top_misdiagnosed_nodes,
                top_missed_fault_types=top_missed_fault_types,
                device_type_distribution=device_type_distribution,
                accuracy_trend=accuracy_trend,
                improvement_suggestions=improvement_suggestions,
            )

            # 15. 构建摘要
            summary = {
                "total_diagnoses": total_diagnoses,
                "annotated_count": annotated_count,
                "annotation_coverage": annotated_count / total_diagnoses if total_diagnoses > 0 else 0,
                "accuracy_rate": accuracy_rate,
                "false_positive_count": false_positive_count,
                "false_negative_count": false_negative_count,
                "top_misdiagnosed_nodes": top_misdiagnosed_nodes,
                "top_missed_fault_types": top_missed_fault_types,
            }

            # 16. 创建报告记录
            report = SystemReport(
                report_type="misdiagnosis_monthly",
                report_period=period,
                report_version="v1.0",
                content=content,
                summary=summary,
                generated_by="system",
            )
            db.add(report)
            await db.commit()
            await db.refresh(report)

            logger.info("误诊分析报告生成完成: period=%s, report_id=%s", period, report.id)
            return report

        finally:
            # 释放分布式锁
            if lock_acquired and redis_service.is_available:
                try:
                    redis_service.delete(lock_key)
                except Exception as e:
                    logger.warning("释放 Redis 锁失败: %s", e)

    @staticmethod
    async def _identify_false_positives(
        start_date: datetime,
        end_date: datetime,
        db: AsyncSession,
    ) -> list:
        """识别误报"""
        result = await db.execute(
            select(DiagnosisResult, DiagnosisAnnotation)
            .join(DiagnosisAnnotation, DiagnosisResult.id == DiagnosisAnnotation.result_id)
            .where(
                and_(
                    DiagnosisResult.confidence > 0.3,
                    DiagnosisAnnotation.annotation == "inaccurate",
                    DiagnosisResult.created_at >= start_date,
                    DiagnosisResult.created_at < end_date,
                )
            )
        )
        return [{"result": r, "annotation": a} for r, a in result.all()]

    @staticmethod
    async def _identify_false_negatives(
        start_date: datetime,
        end_date: datetime,
        db: AsyncSession,
    ) -> list:
        """识别漏报"""
        # 检查工单系统是否可用
        work_order_available = await MisdiagnosisReportService._check_work_order_system(db)

        if not work_order_available:
            logger.warning("工单系统不可用，跳过漏报识别")
            return []

        # 查询告警产生但诊断引擎无结论或失败的场景
        result = await db.execute(
            select(Alarm, WorkOrder)
            .outerjoin(DiagnosisSession, Alarm.id == DiagnosisSession.trigger_alarm_id)
            .join(WorkOrder, Alarm.id == WorkOrder.related_alarm_id)
            .where(
                and_(
                    Alarm.created_at >= start_date,
                    Alarm.created_at < end_date,
                    or_(
                        DiagnosisSession.id.is_(None),
                        DiagnosisSession.status == "failed",
                    ),
                    WorkOrder.order_type == "fault_repair",
                    WorkOrder.status == "completed",
                    Alarm.severity.in_(["critical", "major"]),
                )
            )
        )
        return [{"alarm": a, "work_order": wo} for a, wo in result.all()]

    @staticmethod
    async def _check_work_order_system(db: AsyncSession) -> bool:
        """检查工单系统是否可用"""
        try:
            # 尝试查询 work_orders 表
            await db.execute(select(WorkOrder).limit(1))
            return True
        except Exception as e:
            logger.warning("工单系统不可用: %s", e)
            return False

    @staticmethod
    async def _get_top_misdiagnosed_nodes(
        false_positives: list,
        top_n: int = 5,
    ) -> list:
        """统计高频误判节点"""
        node_counts = {}
        for fp in false_positives:
            result = fp["result"]
            root_cause = result.root_cause or "unknown"
            node_counts[root_cause] = node_counts.get(root_cause, 0) + 1

        sorted_nodes = sorted(node_counts.items(), key=lambda x: x[1], reverse=True)
        total = sum(node_counts.values()) if node_counts else 1

        return [
            {
                "node_id": node_id,
                "misdiagnosis_count": count,
                "percentage": count / total,
            }
            for node_id, count in sorted_nodes[:top_n]
        ]

    @staticmethod
    async def _get_top_missed_fault_types(
        false_negatives: list,
        top_n: int = 5,
    ) -> list:
        """统计高频漏报故障类型"""
        fault_type_counts = {}
        for fn in false_negatives:
            work_order = fn["work_order"]
            fault_type = work_order.fault_type or "unknown"
            fault_type_counts[fault_type] = fault_type_counts.get(fault_type, 0) + 1

        sorted_types = sorted(fault_type_counts.items(), key=lambda x: x[1], reverse=True)
        total = sum(fault_type_counts.values()) if fault_type_counts else 1

        return [
            {
                "fault_type": fault_type,
                "missed_count": count,
                "percentage": count / total,
            }
            for fault_type, count in sorted_types[:top_n]
        ]

    @staticmethod
    async def _get_device_type_distribution(
        false_positives: list,
        db: AsyncSession,
    ) -> list:
        """统计设备类型误判分布"""
        device_type_counts = {}
        for fp in false_positives:
            result = fp["result"]
            device_type = result.device_type or "unknown"
            device_type_counts[device_type] = device_type_counts.get(device_type, 0) + 1

        total = sum(device_type_counts.values()) if device_type_counts else 1

        return [
            {
                "device_type": device_type,
                "misdiagnosis_count": count,
                "percentage": count / total,
            }
            for device_type, count in sorted(
                device_type_counts.items(), key=lambda x: x[1], reverse=True
            )
        ]

    @staticmethod
    async def _get_accuracy_trend(
        current_period: str,
        db: AsyncSession,
    ) -> list:
        """查询历史准确率趋势（最多3个月）"""
        # 解析当前周期
        try:
            year, month = map(int, current_period.split("-"))
        except (ValueError, IndexError):
            return []

        trend = []
        for i in range(3):
            # 计算前 i 个月
            target_month = month - i
            target_year = year
            if target_month <= 0:
                target_month += 12
                target_year -= 1

            period = f"{target_year:04d}-{target_month:02d}"

            # 查询历史报告
            result = await db.execute(
                select(SystemReport).where(
                    and_(
                        SystemReport.report_type == "misdiagnosis_monthly",
                        SystemReport.report_period == period,
                        SystemReport.deleted_at.is_(None),
                    )
                )
            )
            report = result.scalar_one_or_none()

            if report and report.summary:
                trend.append({
                    "period": period,
                    "accuracy_rate": report.summary.get("accuracy_rate"),
                })

        return list(reversed(trend))

    @staticmethod
    async def _generate_improvement_suggestions(
        top_misdiagnosed_nodes: list,
        top_missed_fault_types: list,
        db: AsyncSession,
    ) -> list:
        """生成改进建议"""
        suggestions = []

        # 为误报节点生成建议
        for node in top_misdiagnosed_nodes:
            node_id = node["node_id"]
            rule = await MisdiagnosisReportService._find_improvement_rule(
                "false_positive", node_id=node_id, db=db
            )
            if rule:
                suggestions.append({
                    "type": "false_positive",
                    "target": node_id,
                    "suggestion": rule.suggestion_template,
                })

        # 为漏报故障类型生成建议
        for fault in top_missed_fault_types:
            fault_type = fault["fault_type"]
            rule = await MisdiagnosisReportService._find_improvement_rule(
                "false_negative", fault_type=fault_type, db=db
            )
            if rule:
                suggestions.append({
                    "type": "false_negative",
                    "target": fault_type,
                    "suggestion": rule.suggestion_template,
                })

        return suggestions

    @staticmethod
    async def _find_improvement_rule(
        rule_type: str,
        node_id: Optional[str] = None,
        fault_type: Optional[str] = None,
        db: AsyncSession = None,
    ) -> Optional[DiagnosisImprovementRule]:
        """查找改进建议规则"""
        # 优先查找精确匹配规则
        if rule_type == "false_positive" and node_id:
            result = await db.execute(
                select(DiagnosisImprovementRule)
                .where(
                    and_(
                        DiagnosisImprovementRule.rule_type == rule_type,
                        DiagnosisImprovementRule.node_id == node_id,
                        DiagnosisImprovementRule.is_active == True,
                    )
                )
                .order_by(DiagnosisImprovementRule.priority.desc())
                .limit(1)
            )
            rule = result.scalar_one_or_none()
            if rule:
                return rule

        if rule_type == "false_negative" and fault_type:
            result = await db.execute(
                select(DiagnosisImprovementRule)
                .where(
                    and_(
                        DiagnosisImprovementRule.rule_type == rule_type,
                        DiagnosisImprovementRule.fault_type == fault_type,
                        DiagnosisImprovementRule.is_active == True,
                    )
                )
                .order_by(DiagnosisImprovementRule.priority.desc())
                .limit(1)
            )
            rule = result.scalar_one_or_none()
            if rule:
                return rule

        # 查找通用兜底规则
        if rule_type == "false_positive":
            result = await db.execute(
                select(DiagnosisImprovementRule)
                .where(
                    and_(
                        DiagnosisImprovementRule.rule_type == rule_type,
                        DiagnosisImprovementRule.node_id == "*",
                        DiagnosisImprovementRule.is_active == True,
                    )
                )
                .limit(1)
            )
        else:
            result = await db.execute(
                select(DiagnosisImprovementRule)
                .where(
                    and_(
                        DiagnosisImprovementRule.rule_type == rule_type,
                        DiagnosisImprovementRule.fault_type == "*",
                        DiagnosisImprovementRule.is_active == True,
                    )
                )
                .limit(1)
            )

        return result.scalar_one_or_none()

    @staticmethod
    def _generate_markdown_report(
        period: str,
        total_diagnoses: int,
        annotated_count: int,
        annotation_coverage: float,
        accuracy_rate: Optional[float],
        false_positive_count: int,
        false_negative_count: int,
        top_misdiagnosed_nodes: list,
        top_missed_fault_types: list,
        device_type_distribution: list,
        accuracy_trend: list,
        improvement_suggestions: list,
    ) -> str:
        """生成 Markdown 格式报告"""
        # 格式化准确率
        accuracy_str = f"{accuracy_rate:.1%}" if accuracy_rate is not None else "N/A"

        # 生成报告内容
        content = f"""# 误诊分析报告 ({period})

## 1. 总体概况

| 指标 | 数值 | 说明 |
|------|------|------|
| 总诊断次数 | {total_diagnoses:,} | 本月触发诊断的总次数 |
| 已标注次数 | {annotated_count:,} | 运维人员已标注的诊断结果数 |
| 标注覆盖率 | {annotation_coverage:.1%} | 已标注 / 总诊断次数 |
| 准确率 | {accuracy_str} | (已标注 - 误报) / (已标注 + 漏报) |
| 误报次数 | {false_positive_count} | 诊断有结论但标注为"不准确" |
| 漏报次数 | {false_negative_count} | 告警产生但诊断引擎无结论 |

## 2. 误判类型分布

| 类型 | 次数 | 占比 |
|------|------|------|"""

        # 计算占比（避免除零）
        total_misdiagnosis = false_positive_count + false_negative_count
        if total_misdiagnosis > 0:
            fp_percentage = false_positive_count / total_misdiagnosis * 100
            fn_percentage = false_negative_count / total_misdiagnosis * 100
        else:
            fp_percentage = 0.0
            fn_percentage = 0.0

        content += f"""| 误报 | {false_positive_count} | {fp_percentage:.1f}% |
| 漏报 | {false_negative_count} | {fn_percentage:.1f}% |

## 3. 高频误判故障树节点 (Top 5)

### 3.1 误报节点 (False Positives)

| 排名 | 节点ID | 误判次数 | 占比 |
|------|--------|---------|------|
"""
        for i, node in enumerate(top_misdiagnosed_nodes[:5], 1):
            content += f"| {i} | {node['node_id']} | {node['misdiagnosis_count']} | {node['percentage']:.1%} |\n"

        content += """
### 3.2 漏报故障类型 (False Negatives)

| 排名 | 故障类型 | 漏报次数 | 占比 |
|------|---------|---------|------|
"""
        for i, fault in enumerate(top_missed_fault_types[:5], 1):
            content += f"| {i} | {fault['fault_type']} | {fault['missed_count']} | {fault['percentage']:.1%} |\n"

        content += """
## 4. 设备类型误判分布

| 设备类型 | 误判次数 | 占比 |
|---------|---------|------|
"""
        for device in device_type_distribution[:10]:
            content += f"| {device['device_type']} | {device['misdiagnosis_count']} | {device['percentage']:.1%} |\n"

        content += """
## 5. 准确率趋势

| 月份 | 准确率 | 数据来源 |
|------|--------|---------|
"""
        for trend_item in accuracy_trend:
            rate_str = f"{trend_item['accuracy_rate']:.1%}" if trend_item['accuracy_rate'] is not None else "N/A"
            content += f"| {trend_item['period']} | {rate_str} | system_reports.summary |\n"

        if not accuracy_trend:
            content += f"| {period} | {accuracy_str} | 当前报告 |\n"
            content += "\n*注：首次生成报告，无历史数据。*\n"

        content += """
## 6. 改进建议

*以下建议基于规则引擎自动生成：*

"""
        for i, suggestion in enumerate(improvement_suggestions, 1):
            content += f"{i}. **{suggestion['target']}**: {suggestion['suggestion']}\n"

        content += f"""
---

*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
*数据来源: diagnosis_results, diagnosis_annotations, alarms, work_orders*
"""

        return content
