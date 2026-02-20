"""
节能机会自动检测服务
Opportunity Auto-Detection Service

直接调用 plugin_manager 遍历插件，逐个执行 analyze()，
将 SuggestionResult 映射为 EnergyOpportunity 并写入数据库。
不使用 OpportunityEngine.generate_opportunities() 以保留 plugin_id。
"""

import logging
from datetime import date, datetime
from typing import Any, Dict, List

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .analysis_plugins import PluginPriority, SuggestionResult, plugin_manager, register_all_plugins
from .opportunity_engine import PLUGIN_CATEGORY_MAPPING, OpportunityCategory
from ..models.energy import EnergyOpportunity

logger = logging.getLogger(__name__)

# ========== 映射字典 ==========

CATEGORY_TO_INT: Dict[OpportunityCategory, int] = {
    OpportunityCategory.BILL_OPTIMIZATION: 1,
    OpportunityCategory.DEVICE_OPERATION: 2,
    OpportunityCategory.EQUIPMENT_UPGRADE: 3,
    OpportunityCategory.COMPREHENSIVE: 4,
}

PRIORITY_TO_STR: Dict[PluginPriority, str] = {
    PluginPriority.CRITICAL: "high",
    PluginPriority.HIGH: "high",
    PluginPriority.MEDIUM: "medium",
    PluginPriority.LOW: "low",
}


class OpportunityDetector:
    """节能机会自动检测器"""

    def __init__(self, db: AsyncSession):
        self.db = db
        register_all_plugins()

    async def run_detection(self, days: int = 30) -> Dict[str, Any]:
        """
        执行一轮自动检测

        Args:
            days: 分析数据天数

        Returns:
            检测结果摘要
        """
        total_analyzed = 0
        new_opportunities = 0
        skipped_duplicates = 0
        errors = 0
        details: List[Dict[str, Any]] = []

        # 构建分析上下文
        context = await plugin_manager.build_context(self.db, days)

        # 遍历所有启用的插件
        for plugin in plugin_manager.get_enabled_plugins():
            plugin_id = plugin.plugin_id
            plugin_detail = {
                "plugin_id": plugin_id,
                "opportunities_found": 0,
                "new_created": 0,
                "skipped": 0,
            }

            try:
                # 验证上下文
                if not plugin.validate_context(context):
                    logger.warning(f"插件 {plugin_id} 上下文验证失败，跳过")
                    details.append(plugin_detail)
                    continue

                # 执行分析
                results: List[SuggestionResult] = await plugin.analyze(context)
                plugin_detail["opportunities_found"] = len(results)
                total_analyzed += len(results)

                # 逐条处理结果
                for result in results:
                    category_enum = PLUGIN_CATEGORY_MAPPING.get(plugin_id, OpportunityCategory.COMPREHENSIVE)
                    category_int = CATEGORY_TO_INT.get(category_enum, 4)

                    # 去重检查（含 title 避免同插件多结果被误去重）
                    is_dup = await self._is_duplicate(plugin_id, category_int, result.title)
                    if is_dup:
                        skipped_duplicates += 1
                        plugin_detail["skipped"] += 1
                        continue

                    # 创建 EnergyOpportunity
                    opportunity = self._build_opportunity(result, plugin_id, plugin.plugin_name, category_int)
                    self.db.add(opportunity)
                    await self.db.flush()
                    new_opportunities += 1
                    plugin_detail["new_created"] += 1

            except Exception as e:
                logger.error(f"插件 {plugin_id} 检测失败: {e}", exc_info=True)
                errors += 1

            details.append(plugin_detail)

        # 统一提交
        try:
            await self.db.commit()
        except Exception as e:
            logger.error(f"提交检测结果失败: {e}")
            await self.db.rollback()
            new_opportunities = 0  # 回滚后实际未持久化
            errors += 1

        return {
            "total_analyzed": total_analyzed,
            "new_opportunities": new_opportunities,
            "skipped_duplicates": skipped_duplicates,
            "errors": errors,
            "details": details,
        }

    # ========== 私有方法 ==========

    async def _is_duplicate(self, plugin_id: str, category_int: int, title: str) -> bool:
        """
        检查今天是否已存在同插件+同类别+同标题的未关闭机会

        使用 func.date() 兼容 SQLite / PostgreSQL
        加入 title 避免同一插件产生多条不同建议时被误去重
        """
        today = date.today().isoformat()
        result = await self.db.execute(
            select(func.count(EnergyOpportunity.id)).where(
                and_(
                    EnergyOpportunity.source_plugin == plugin_id,
                    EnergyOpportunity.category == category_int,
                    EnergyOpportunity.title == title,
                    func.date(EnergyOpportunity.discovered_at) == today,
                    EnergyOpportunity.status.notin_(["rejected", "completed"]),
                )
            )
        )
        count = result.scalar() or 0
        return count > 0

    def _build_opportunity(
        self,
        result: SuggestionResult,
        plugin_id: str,
        plugin_name: str,
        category_int: int,
    ) -> EnergyOpportunity:
        """将 SuggestionResult 映射为 EnergyOpportunity"""
        priority_str = PRIORITY_TO_STR.get(result.priority, "medium")

        # confidence: int 0-100 → Numeric(3,2) 0.00-1.00
        confidence_decimal = round(result.confidence / 100.0, 2)

        # analysis_data JSON
        analysis_data = {
            "detail": result.detail,
            "estimated_saving_kwh": result.estimated_saving,
            "implementation_difficulty": result.implementation_difficulty,
            "payback_period": result.payback_period,
            "related_devices": result.related_devices,
            **result.analysis_data,
        }

        return EnergyOpportunity(
            category=category_int,
            title=result.title,
            description=result.description,
            priority=priority_str,
            status="discovered",
            potential_saving=result.estimated_cost_saving,
            confidence=confidence_decimal,
            analysis_data=analysis_data,
            source_plugin=plugin_id,
            trigger_condition=f"自动检测 - {plugin_name}",
            discovered_at=datetime.now(),
        )
