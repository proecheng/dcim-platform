"""
误诊反馈报告服务
Story 26.2: 误诊反馈报告
Story 26.6: 月度误判分析报告（使用 ReportRecord 模型）
"""

import logging
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List, Any
from sqlalchemy import select, func, and_, or_, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.diagnosis import (
    DiagnosisSession,
    DiagnosisResult,
    DiagnosisAnnotation,
    SystemReport,
    DiagnosisImprovementRule,
)
from app.models.report import ReportRecord
from app.models.alarm import Alarm
from app.models.operation import WorkOrder
from app.core.redis import redis_service
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


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


# ============================================================
# Story 26.6: 月度误判分析报告（使用 ReportRecord 模型）
# ============================================================


class MisdiagnosisReportServiceV2:
    """
    误判分析报告服务 V2 - Story 26.6
    使用棕地 ReportRecord 模型，支持 PostgreSQL 和 SQLite
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.db_type = db.bind.dialect.name  # postgresql or sqlite

    async def generate_monthly_report_v2(
        self,
        start_date: datetime,
        end_date: datetime,
        generated_by: Optional[int] = None
    ) -> int:
        """
        生成月度误判分析报告（Story 26.6）

        Args:
            start_date: 统计开始时间（UTC）
            end_date: 统计结束时间（UTC）
            generated_by: 生成人ID（定时任务为 None）

        Returns:
            report_id: 报告ID

        Raises:
            ValueError: 如果相同周期的报告已存在
        """
        # 1. 检查重复
        existing = await self._check_existing_report(start_date, end_date)
        if existing:
            raise ValueError(f"该时间段的报告已存在，report_id: {existing.id}")

        # 2. 生成报告名称
        report_name = f"{start_date.year}年{start_date.month}月误判分析报告"

        # 3. 检查依赖表是否存在
        work_orders_exists = await self._check_table_exists("work_orders")
        fault_tree_nodes_exists = await self._check_table_exists("fault_tree_nodes")

        # 4. 创建报告记录（状态: generating）
        report = ReportRecord(
            report_name=report_name,
            report_type="diagnosis_monthly",
            start_time=start_date,
            end_time=end_date,
            status="generating",
            generated_by=generated_by,
        )
        self.db.add(report)
        await self.db.flush()
        report_id = report.id

        try:
            # 5. 执行统计查询
            summary = await self._query_diagnosis_summary(start_date, end_date)
            false_positive_stats = await self._query_false_positive_stats(start_date, end_date)
            false_negative_stats = await self._query_false_negative_stats(
                start_date, end_date, work_orders_exists
            )
            top_nodes = await self._query_top_misdiagnosed_nodes(
                start_date, end_date, fault_tree_nodes_exists
            )
            device_type_dist = await self._query_device_type_distribution(start_date, end_date)

            # 6. 生成改进建议
            recommendations = self._generate_recommendations(top_nodes)

            # 7. 构建 report_data JSON
            report_data = {
                "period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                },
                "summary": summary,
                "misdiagnosis_distribution": {
                    **false_positive_stats,
                    **false_negative_stats,
                    "false_negative_available": work_orders_exists,
                },
                "top_misdiagnosed_nodes": top_nodes,
                "device_type_distribution": device_type_dist,
                "recommendations": recommendations,
            }

            # 8. 渲染 Markdown 报告
            markdown_content = self._render_markdown_report(
                start_date, end_date, report_data
            )

            # 9. 保存 Markdown 文件
            file_path, file_size = await self._save_markdown_file(
                start_date, markdown_content
            )

            # 10. 更新报告记录
            report.file_path = file_path
            report.file_size = file_size
            report.report_data = json.dumps(report_data, ensure_ascii=False)
            report.status = "completed"
            await self.db.commit()

            logger.info(f"报告生成成功: {report_name}, report_id={report_id}")
            return report_id

        except Exception as e:
            # 失败处理
            report.status = "failed"
            report.error_message = str(e)
            await self.db.commit()
            logger.error(f"报告生成失败: {report_name}, error={e}")
            raise

    async def _check_existing_report(
        self, start_date: datetime, end_date: datetime
    ) -> Optional[ReportRecord]:
        """检查相同周期的报告是否已存在"""
        stmt = select(ReportRecord).where(
            ReportRecord.report_type == "diagnosis_monthly",
            ReportRecord.start_time == start_date,
            ReportRecord.end_time == end_date,
            ReportRecord.status.in_(["completed", "generating"])
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _check_table_exists(self, table_name: str) -> bool:
        """检查表是否存在"""
        if self.db_type == "sqlite":
            query = text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=:table_name"
            )
        else:  # postgresql
            query = text(
                "SELECT tablename FROM pg_tables WHERE tablename=:table_name"
            )

        result = await self.db.execute(query, {"table_name": table_name})
        return result.scalar_one_or_none() is not None

    async def _query_diagnosis_summary(
        self, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """查询诊断概览统计"""
        if self.db_type == "sqlite":
            query = text("""
                SELECT
                    COUNT(*) AS total_diagnosis_count,
                    COUNT(da.id) AS annotated_count,
                    CAST(COUNT(da.id) AS REAL) / NULLIF(COUNT(*), 0) AS annotation_coverage_rate
                FROM diagnosis_results dr
                LEFT JOIN diagnosis_annotations da ON dr.id = da.diagnosis_result_id
                WHERE dr.created_at BETWEEN :start_date AND :end_date
            """)
        else:  # postgresql
            query = text("""
                SELECT
                    COUNT(*) AS total_diagnosis_count,
                    COUNT(da.id) AS annotated_count,
                    CAST(COUNT(da.id) AS FLOAT) / NULLIF(COUNT(*), 0) AS annotation_coverage_rate
                FROM diagnosis_results dr
                LEFT JOIN diagnosis_annotations da ON dr.id = da.diagnosis_result_id
                WHERE dr.created_at BETWEEN :start_date AND :end_date
            """)

        result = await self.db.execute(query, {"start_date": start_date, "end_date": end_date})
        row = result.fetchone()

        return {
            "total_diagnosis_count": row.total_diagnosis_count,
            "annotated_count": row.annotated_count,
            "annotation_coverage_rate": row.annotation_coverage_rate or 0.0,
        }

    async def _query_false_positive_stats(
        self, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """查询误报统计"""
        if self.db_type == "sqlite":
            query = text("""
                SELECT
                    SUM(CASE WHEN dr.root_cause IS NOT NULL AND da.is_accurate = 0 THEN 1 ELSE 0 END) AS false_positive_count,
                    SUM(CASE WHEN dr.root_cause IS NOT NULL THEN 1 ELSE 0 END) AS total_positive_count
                FROM diagnosis_results dr
                JOIN diagnosis_annotations da ON dr.id = da.diagnosis_result_id
                WHERE dr.created_at BETWEEN :start_date AND :end_date
            """)
        else:  # postgresql
            query = text("""
                SELECT
                    COUNT(*) FILTER (WHERE dr.root_cause IS NOT NULL AND da.is_accurate = false) AS false_positive_count,
                    COUNT(*) FILTER (WHERE dr.root_cause IS NOT NULL) AS total_positive_count
                FROM diagnosis_results dr
                JOIN diagnosis_annotations da ON dr.id = da.diagnosis_result_id
                WHERE dr.created_at BETWEEN :start_date AND :end_date
            """)

        result = await self.db.execute(query, {"start_date": start_date, "end_date": end_date})
        row = result.fetchone()

        total_positive = row.total_positive_count or 0
        false_positive = row.false_positive_count or 0

        return {
            "false_positive_count": false_positive,
            "false_positive_rate": false_positive / total_positive if total_positive > 0 else 0.0,
        }

    async def _query_false_negative_stats(
        self, start_date: datetime, end_date: datetime, work_orders_exists: bool
    ) -> Dict[str, Any]:
        """查询漏报统计"""
        if not work_orders_exists:
            return {
                "false_negative_count": 0,
                "false_negative_rate": 0.0,
            }

        if self.db_type == "sqlite":
            query = text("""
                SELECT
                    SUM(CASE
                        WHEN dr.root_cause IS NULL
                        AND dr.alarm_id IS NOT NULL
                        AND EXISTS (
                            SELECT 1 FROM work_orders wo
                            WHERE wo.alarm_id = dr.alarm_id
                            AND wo.work_order_type = 'fault_repair'
                            AND datetime(wo.created_at) <= datetime(dr.created_at, '+30 minutes')
                        )
                        THEN 1 ELSE 0 END
                    ) AS false_negative_count,
                    COUNT(*) AS total_count
                FROM diagnosis_results dr
                WHERE dr.created_at BETWEEN :start_date AND :end_date
            """)
        else:  # postgresql
            query = text("""
                SELECT
                    COUNT(*) FILTER (
                        WHERE dr.root_cause IS NULL
                        AND dr.alarm_id IS NOT NULL
                        AND EXISTS (
                            SELECT 1 FROM work_orders wo
                            WHERE wo.alarm_id = dr.alarm_id
                            AND wo.work_order_type = 'fault_repair'
                            AND wo.created_at <= dr.created_at + INTERVAL '30 minutes'
                        )
                    ) AS false_negative_count,
                    COUNT(*) AS total_count
                FROM diagnosis_results dr
                WHERE dr.created_at BETWEEN :start_date AND :end_date
            """)

        result = await self.db.execute(query, {"start_date": start_date, "end_date": end_date})
        row = result.fetchone()

        total_count = row.total_count or 0
        false_negative = row.false_negative_count or 0

        return {
            "false_negative_count": false_negative,
            "false_negative_rate": false_negative / total_count if total_count > 0 else 0.0,
        }

    async def _query_top_misdiagnosed_nodes(
        self, start_date: datetime, end_date: datetime, fault_tree_nodes_exists: bool
    ) -> List[Dict[str, Any]]:
        """查询高频误判根因节点"""
        if fault_tree_nodes_exists:
            # JOIN 节点表获取节点名称
            if self.db_type == "sqlite":
                query = text("""
                    SELECT
                        dr.root_cause AS node_id,
                        COALESCE(ftn.node_name, dr.root_cause) AS node_name,
                        SUM(CASE WHEN da.is_accurate = 0 THEN 1 ELSE 0 END) AS misdiagnosis_count,
                        SUM(CASE WHEN da.is_accurate = 1 THEN 1 ELSE 0 END) AS accurate_count,
                        COUNT(*) AS total_count,
                        CAST(SUM(CASE WHEN da.is_accurate = 0 THEN 1 ELSE 0 END) AS REAL) / COUNT(*) AS misdiagnosis_rate
                    FROM diagnosis_results dr
                    JOIN diagnosis_annotations da ON dr.id = da.diagnosis_result_id
                    LEFT JOIN fault_tree_nodes ftn ON dr.root_cause = ftn.node_id
                    WHERE dr.created_at BETWEEN :start_date AND :end_date
                      AND dr.root_cause IS NOT NULL
                    GROUP BY dr.root_cause, ftn.node_name
                    HAVING SUM(CASE WHEN da.is_accurate = 0 THEN 1 ELSE 0 END) > 0
                    ORDER BY misdiagnosis_count DESC
                    LIMIT 5
                """)
            else:  # postgresql
                query = text("""
                    SELECT
                        dr.root_cause AS node_id,
                        COALESCE(ftn.node_name, dr.root_cause) AS node_name,
                        COUNT(*) FILTER (WHERE da.is_accurate = false) AS misdiagnosis_count,
                        COUNT(*) FILTER (WHERE da.is_accurate = true) AS accurate_count,
                        COUNT(*) AS total_count,
                        CAST(COUNT(*) FILTER (WHERE da.is_accurate = false) AS FLOAT) / COUNT(*) AS misdiagnosis_rate
                    FROM diagnosis_results dr
                    JOIN diagnosis_annotations da ON dr.id = da.diagnosis_result_id
                    LEFT JOIN fault_tree_nodes ftn ON dr.root_cause = ftn.node_id
                    WHERE dr.created_at BETWEEN :start_date AND :end_date
                      AND dr.root_cause IS NOT NULL
                    GROUP BY dr.root_cause, ftn.node_name
                    HAVING COUNT(*) FILTER (WHERE da.is_accurate = false) > 0
                    ORDER BY misdiagnosis_count DESC
                    LIMIT 5
                """)
        else:
            # 不 JOIN 节点表，使用 root_cause 作为 node_name
            if self.db_type == "sqlite":
                query = text("""
                    SELECT
                        dr.root_cause AS node_id,
                        dr.root_cause AS node_name,
                        SUM(CASE WHEN da.is_accurate = 0 THEN 1 ELSE 0 END) AS misdiagnosis_count,
                        SUM(CASE WHEN da.is_accurate = 1 THEN 1 ELSE 0 END) AS accurate_count,
                        COUNT(*) AS total_count,
                        CAST(SUM(CASE WHEN da.is_accurate = 0 THEN 1 ELSE 0 END) AS REAL) / COUNT(*) AS misdiagnosis_rate
                    FROM diagnosis_results dr
                    JOIN diagnosis_annotations da ON dr.id = da.diagnosis_result_id
                    WHERE dr.created_at BETWEEN :start_date AND :end_date
                      AND dr.root_cause IS NOT NULL
                    GROUP BY dr.root_cause
                    HAVING SUM(CASE WHEN da.is_accurate = 0 THEN 1 ELSE 0 END) > 0
                    ORDER BY misdiagnosis_count DESC
                    LIMIT 5
                """)
            else:  # postgresql
                query = text("""
                    SELECT
                        dr.root_cause AS node_id,
                        dr.root_cause AS node_name,
                        COUNT(*) FILTER (WHERE da.is_accurate = false) AS misdiagnosis_count,
                        COUNT(*) FILTER (WHERE da.is_accurate = true) AS accurate_count,
                        COUNT(*) AS total_count,
                        CAST(COUNT(*) FILTER (WHERE da.is_accurate = false) AS FLOAT) / COUNT(*) AS misdiagnosis_rate
                    FROM diagnosis_results dr
                    JOIN diagnosis_annotations da ON dr.id = da.diagnosis_result_id
                    WHERE dr.created_at BETWEEN :start_date AND :end_date
                      AND dr.root_cause IS NOT NULL
                    GROUP BY dr.root_cause
                    HAVING COUNT(*) FILTER (WHERE da.is_accurate = false) > 0
                    ORDER BY misdiagnosis_count DESC
                    LIMIT 5
                """)

        result = await self.db.execute(query, {"start_date": start_date, "end_date": end_date})
        rows = result.fetchall()

        return [
            {
                "node_id": row.node_id,
                "node_name": row.node_name,
                "misdiagnosis_count": row.misdiagnosis_count,
                "total_count": row.total_count,
                "misdiagnosis_rate": row.misdiagnosis_rate,
            }
            for row in rows
        ]

    async def _query_device_type_distribution(
        self, start_date: datetime, end_date: datetime
    ) -> List[Dict[str, Any]]:
        """查询设备类型误判分布"""
        if self.db_type == "sqlite":
            query = text("""
                SELECT
                    dr.device_type,
                    COUNT(*) AS total_count,
                    SUM(CASE WHEN da.is_accurate = 0 THEN 1 ELSE 0 END) AS misdiagnosis_count,
                    CAST(SUM(CASE WHEN da.is_accurate = 0 THEN 1 ELSE 0 END) AS REAL) / COUNT(*) AS misdiagnosis_rate
                FROM diagnosis_results dr
                JOIN diagnosis_annotations da ON dr.id = da.diagnosis_result_id
                WHERE dr.created_at BETWEEN :start_date AND :end_date
                GROUP BY dr.device_type
                HAVING COUNT(*) > 0
                ORDER BY misdiagnosis_rate DESC
            """)
        else:  # postgresql
            query = text("""
                SELECT
                    dr.device_type,
                    COUNT(*) AS total_count,
                    COUNT(*) FILTER (WHERE da.is_accurate = false) AS misdiagnosis_count,
                    CAST(COUNT(*) FILTER (WHERE da.is_accurate = false) AS FLOAT) / COUNT(*) AS misdiagnosis_rate
                FROM diagnosis_results dr
                JOIN diagnosis_annotations da ON dr.id = da.diagnosis_result_id
                WHERE dr.created_at BETWEEN :start_date AND :end_date
                GROUP BY dr.device_type
                HAVING COUNT(*) > 0
                ORDER BY misdiagnosis_rate DESC
            """)

        result = await self.db.execute(query, {"start_date": start_date, "end_date": end_date})
        rows = result.fetchall()

        return [
            {
                "device_type": row.device_type,
                "total_count": row.total_count,
                "misdiagnosis_count": row.misdiagnosis_count,
                "misdiagnosis_rate": row.misdiagnosis_rate,
            }
            for row in rows
        ]

    def _generate_recommendations(self, top_nodes: List[Dict[str, Any]]) -> List[str]:
        """生成改进建议"""
        recommendations = []

        for node in top_nodes:
            node_name = node["node_name"]
            misdiagnosis_rate = node["misdiagnosis_rate"]
            total_count = node["total_count"]

            if total_count < 10:
                recommendations.append(
                    f"节点 {node_name} 样本量不足（{total_count}），建议继续收集标注数据"
                )
            elif misdiagnosis_rate > 0.3:
                recommendations.append(
                    f"节点 {node_name} 误判率 {misdiagnosis_rate:.1%}（样本量 {total_count}），建议检查先验概率或增加证据维度"
                )
            elif misdiagnosis_rate >= 0.2:
                recommendations.append(
                    f"节点 {node_name} 误判率 {misdiagnosis_rate:.1%}（样本量 {total_count}），建议审查诊断逻辑"
                )
            elif misdiagnosis_rate >= 0.1:
                recommendations.append(
                    f"节点 {node_name} 误判率 {misdiagnosis_rate:.1%}（样本量 {total_count}），建议增加标注样本"
                )
            else:
                recommendations.append(
                    f"节点 {node_name} 误判率 {misdiagnosis_rate:.1%}（样本量 {total_count}），诊断效果良好，继续观察"
                )

        return recommendations

    def _render_markdown_report(
        self, start_date: datetime, end_date: datetime, report_data: Dict[str, Any]
    ) -> str:
        """渲染 Markdown 报告"""
        summary = report_data["summary"]
        misdiagnosis_dist = report_data["misdiagnosis_distribution"]
        top_nodes = report_data["top_misdiagnosed_nodes"]
        device_type_dist = report_data["device_type_distribution"]
        recommendations = report_data["recommendations"]

        # 渲染漏报统计部分
        if misdiagnosis_dist["false_negative_available"]:
            false_negative_section = f"""
| 指标 | 数值 |
|------|------|
| 漏报次数 | {misdiagnosis_dist['false_negative_count']} |
| 漏报率 | {misdiagnosis_dist['false_negative_rate']:.1%} |
"""
        else:
            false_negative_section = "\n⚠️ 工单系统未配置，漏报统计不可用\n"

        # 渲染高频误判节点部分
        if top_nodes:
            top_nodes_section = """
| 排名 | 节点ID | 节点名称 | 误判次数 | 总诊断次数 | 误判率 |
|------|--------|---------|---------|-----------|--------|
"""
            for i, node in enumerate(top_nodes, 1):
                top_nodes_section += f"| {i} | {node['node_id']} | {node['node_name']} | {node['misdiagnosis_count']} | {node['total_count']} | {node['misdiagnosis_rate']:.1%} |\n"
        else:
            top_nodes_section = "\n暂无误判节点数据\n"

        # 渲染设备类型分布部分
        if device_type_dist:
            device_type_section = """
| 设备类型 | 总诊断次数 | 误判次数 | 误判率 |
|---------|-----------|---------|--------|
"""
            for device in device_type_dist:
                device_type_section += f"| {device['device_type']} | {device['total_count']} | {device['misdiagnosis_count']} | {device['misdiagnosis_rate']:.1%} |\n"
        else:
            device_type_section = "\n暂无设备类型误判数据\n"

        # 渲染改进建议
        recommendations_text = "\n".join([f"{i}. {rec}" for i, rec in enumerate(recommendations, 1)])
        if not recommendations_text:
            recommendations_text = "暂无改进建议"

        # 生成完整报告
        content = f"""# {start_date.year}年{start_date.month}月误判分析报告

**生成时间**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}
**统计周期**: {start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}

---

## 1. 诊断概览

| 指标 | 数值 |
|------|------|
| 总诊断次数 | {summary['total_diagnosis_count']} |
| 已标注次数 | {summary['annotated_count']} |
| 标注覆盖率 | {summary['annotation_coverage_rate']:.1%} |

---

## 2. 误判类型分布

### 2.1 误报统计

**误报定义**: 诊断给出了根因，但标注为不准确。

| 指标 | 数值 |
|------|------|
| 误报次数 | {misdiagnosis_dist['false_positive_count']} |
| 误报率 | {misdiagnosis_dist['false_positive_rate']:.1%} |

### 2.2 漏报统计

**漏报定义**: 告警产生后30分钟内诊断引擎无任何结论，但告警最终被人工确认为真实故障（通过工单系统关联告警且工单类型=故障修复来识别）。

{false_negative_section}

---

## 3. 高频误判故障树节点

**Top 5 被标注为"不准确"最多的根因节点**:

{top_nodes_section}

---

## 4. 设备类型误判分布

**按设备类型统计误判率**:

{device_type_section}

---

## 5. 改进建议

{recommendations_text}

---

**报告生成**: 智能诊断系统自动生成
**数据来源**: diagnosis_results + diagnosis_annotations
"""
        return content

    async def _save_markdown_file(
        self, start_date: datetime, markdown_content: str
    ) -> tuple[str, int]:
        """保存 Markdown 文件到磁盘"""
        # 获取报告目录
        report_dir = getattr(settings, "REPORT_DIR", "reports")
        if not os.path.isabs(report_dir):
            # 相对路径，转换为绝对路径
            report_dir = os.path.abspath(report_dir)

        diagnosis_dir = os.path.join(report_dir, "diagnosis")
        os.makedirs(diagnosis_dir, exist_ok=True)

        # 生成文件名
        filename = f"{start_date.year}-{start_date.month:02d}-misdiagnosis.md"
        file_path = os.path.join(diagnosis_dir, filename)

        # 写入文件
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)

        # 设置文件权限 644
        os.chmod(file_path, 0o644)

        # 获取文件大小
        file_size = os.path.getsize(file_path)

        return file_path, file_size


        return content
