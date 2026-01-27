"""
优化集成服务
将日前调度优化结果与节能中心打通
"""
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_

from ..models.energy import EnergyOpportunity, ExecutionPlan, ExecutionTask, ExecutionResult


class OptimizationIntegrationService:
    """优化集成服务"""

    # 优化类型到机会类别的映射
    OPTIMIZATION_TO_CATEGORY = {
        'day_ahead': 1,          # 电费结构优化
        'demand_control': 1,      # 电费结构优化
        'storage_arbitrage': 1,   # 电费结构优化
        'load_shifting': 2,       # 设备运行优化
        'peak_shaving': 2,        # 设备运行优化
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_opportunity_from_optimization(
        self,
        optimization_result: Dict,
        optimization_type: str = 'day_ahead',
        target_date: Optional[str] = None
    ) -> Optional[EnergyOpportunity]:
        """
        从优化结果创建节能机会

        Args:
            optimization_result: 优化结果字典
            optimization_type: 优化类型
            target_date: 目标日期

        Returns:
            创建的节能机会对象
        """
        if optimization_result.get('status') != 'success':
            return None

        expected_saving = optimization_result.get('expected_saving', 0)
        if expected_saving <= 0:
            return None

        # 计算年化节省
        annual_saving = expected_saving * 250  # 按250工作日计算

        # 确定优先级
        if annual_saving > 50000:
            priority = 'high'
        elif annual_saving > 20000:
            priority = 'medium'
        else:
            priority = 'low'

        # 构建分析数据
        analysis_data = {
            'optimization_type': optimization_type,
            'target_date': target_date or datetime.now().strftime('%Y-%m-%d'),
            'forecast_date': optimization_result.get('forecast_date'),
            'max_demand': optimization_result.get('max_demand'),
            'demand_target': optimization_result.get('demand_target'),
            'cost_breakdown': optimization_result.get('cost_breakdown'),
            'baseline_cost': optimization_result.get('baseline_cost'),
            'optimal_value': optimization_result.get('optimal_value'),
            'storage_schedule_summary': self._summarize_storage_schedule(
                optimization_result.get('storage_schedule', [])
            ),
            'device_schedule_summary': self._summarize_device_schedule(
                optimization_result.get('schedule', [])
            ),
        }

        # 生成标题和描述
        title = self._generate_title(optimization_type, optimization_result)
        description = self._generate_description(optimization_type, optimization_result)

        # 创建机会
        opportunity = EnergyOpportunity(
            category=self.OPTIMIZATION_TO_CATEGORY.get(optimization_type, 1),
            title=title,
            description=description,
            potential_saving=annual_saving,
            priority=priority,
            confidence=optimization_result.get('confidence', 0.85),
            status='ready',
            source_plugin=f'optimizer_{optimization_type}',
            analysis_data=analysis_data,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        self.db.add(opportunity)
        await self.db.commit()
        await self.db.refresh(opportunity)

        return opportunity

    def _generate_title(self, optimization_type: str, result: Dict) -> str:
        """生成机会标题"""
        saving = result.get('expected_saving', 0)
        saving_ratio = result.get('saving_ratio', 0)

        titles = {
            'day_ahead': f'日前调度优化 - 预计日节省¥{saving:.0f}',
            'demand_control': f'需量控制优化 - 降低需量{saving_ratio:.1f}%',
            'storage_arbitrage': f'储能峰谷套利 - 预计日收益¥{saving:.0f}',
            'load_shifting': f'负荷转移优化 - 预计日节省¥{saving:.0f}',
            'peak_shaving': f'削峰优化 - 减少需量电费',
        }
        return titles.get(optimization_type, f'电费优化方案 - ¥{saving:.0f}/日')

    def _generate_description(self, optimization_type: str, result: Dict) -> str:
        """生成机会描述"""
        cost_breakdown = result.get('cost_breakdown', {})
        storage_schedule = result.get('storage_schedule', [])

        lines = []

        if optimization_type == 'day_ahead':
            lines.append('通过日前负荷预测和优化调度，实现电费成本最小化。')
            if cost_breakdown:
                lines.append(f"预计电量电费: ¥{cost_breakdown.get('energy_cost', 0):.2f}")
                lines.append(f"预计需量电费: ¥{cost_breakdown.get('demand_cost', 0):.2f}")

        if storage_schedule:
            charge_count = sum(1 for s in storage_schedule if s.get('charge_power', 0) > 0)
            discharge_count = sum(1 for s in storage_schedule if s.get('discharge_power', 0) > 0)
            if charge_count > 0 or discharge_count > 0:
                lines.append(f"储能调度: {charge_count}个时段充电, {discharge_count}个时段放电")

        return '\n'.join(lines)

    def _summarize_storage_schedule(self, schedule: List[Dict]) -> Dict:
        """汇总储能调度计划"""
        if not schedule:
            return {}

        total_charge = sum(s.get('charge_power', 0) for s in schedule) * 0.25  # kWh
        total_discharge = sum(s.get('discharge_power', 0) for s in schedule) * 0.25  # kWh

        charge_periods = []
        discharge_periods = []

        for s in schedule:
            hour = s.get('hour', 0)
            if s.get('charge_power', 0) > 10:
                charge_periods.append(hour)
            if s.get('discharge_power', 0) > 10:
                discharge_periods.append(hour)

        return {
            'total_charge_energy': round(total_charge, 2),
            'total_discharge_energy': round(total_discharge, 2),
            'charge_hours': sorted(set(charge_periods)),
            'discharge_hours': sorted(set(discharge_periods)),
        }

    def _summarize_device_schedule(self, schedules: List[Dict]) -> List[Dict]:
        """汇总设备调度计划"""
        summaries = []
        for device_schedule in schedules:
            actions = device_schedule.get('actions', [])
            if not actions:
                continue

            summaries.append({
                'device_id': device_schedule.get('device_id'),
                'device_name': device_schedule.get('device_name'),
                'device_type': device_schedule.get('device_type'),
                'action_count': len(actions),
                'action_hours': sorted(set(a.get('hour', 0) for a in actions)),
            })

        return summaries

    async def sync_execution_status(
        self,
        opportunity_id: int,
        execution_data: Dict
    ) -> bool:
        """
        同步执行状态

        Args:
            opportunity_id: 机会ID
            execution_data: 执行数据

        Returns:
            是否成功
        """
        # 查询机会
        result = await self.db.execute(
            select(EnergyOpportunity).where(EnergyOpportunity.id == opportunity_id)
        )
        opportunity = result.scalar_one_or_none()

        if not opportunity:
            return False

        # 更新状态
        new_status = execution_data.get('status')
        if new_status:
            opportunity.status = new_status

        # 更新分析数据中的执行结果
        if opportunity.analysis_data is None:
            opportunity.analysis_data = {}

        opportunity.analysis_data['execution'] = {
            'last_sync': datetime.now().isoformat(),
            'executed_count': execution_data.get('executed_count', 0),
            'success_count': execution_data.get('success_count', 0),
            'actual_saving': execution_data.get('actual_saving', 0),
        }

        opportunity.updated_at = datetime.now()

        await self.db.commit()
        return True

    async def get_optimization_statistics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict:
        """
        获取优化统计数据

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            统计数据
        """
        if start_date is None:
            start_date = datetime.now().replace(day=1)
        if end_date is None:
            end_date = datetime.now()

        # 查询期间创建的优化机会
        query = select(EnergyOpportunity).where(
            and_(
                EnergyOpportunity.source_plugin.like('optimizer_%'),
                EnergyOpportunity.created_at >= start_date,
                EnergyOpportunity.created_at <= end_date
            )
        )
        result = await self.db.execute(query)
        opportunities = result.scalars().all()

        # 统计
        total_count = len(opportunities)
        total_potential_saving = sum(o.potential_saving or 0 for o in opportunities)

        by_status = {}
        by_type = {}

        for o in opportunities:
            # 按状态统计
            status = o.status or 'unknown'
            by_status[status] = by_status.get(status, 0) + 1

            # 按类型统计
            source = o.source_plugin or 'unknown'
            opt_type = source.replace('optimizer_', '')
            by_type[opt_type] = by_type.get(opt_type, 0) + 1

        # 计算实际节省（从已完成的执行计划）
        exec_query = select(ExecutionResult).join(ExecutionPlan).where(
            and_(
                ExecutionResult.status == 'completed',
                ExecutionResult.tracking_end >= start_date.date(),
                ExecutionResult.tracking_end <= end_date.date()
            )
        )
        exec_result = await self.db.execute(exec_query)
        execution_results = exec_result.scalars().all()

        actual_saving = sum(r.actual_saving or 0 for r in execution_results)

        return {
            'period': {
                'start': start_date.strftime('%Y-%m-%d'),
                'end': end_date.strftime('%Y-%m-%d'),
            },
            'opportunities': {
                'total_count': total_count,
                'total_potential_saving': round(total_potential_saving, 2),
                'by_status': by_status,
                'by_type': by_type,
            },
            'execution': {
                'completed_count': len(execution_results),
                'actual_saving': round(actual_saving, 2),
                'achievement_rate': round(
                    actual_saving / total_potential_saving * 100
                    if total_potential_saving > 0 else 0,
                    2
                ),
            }
        }


async def auto_generate_opportunities(
    db: AsyncSession,
    days: int = 7
) -> List[EnergyOpportunity]:
    """
    自动生成节能机会

    根据最近的优化结果自动创建节能机会

    Args:
        db: 数据库会话
        days: 生成未来几天的机会

    Returns:
        创建的机会列表
    """
    from ..services.forecasting import generate_demo_forecast
    from ..services.optimizer import run_day_ahead_optimization

    service = OptimizationIntegrationService(db)
    opportunities = []

    # 为未来几天生成优化方案
    for i in range(days):
        target_date = datetime.now() + timedelta(days=i + 1)
        date_str = target_date.strftime('%Y-%m-%d')

        # 生成预测和优化
        forecast = generate_demo_forecast(target_date)

        pricing_config = {
            'demand_price': 40.0,
            'declared_demand': 800.0,
            'period_prices': {
                'sharp': 1.20,
                'peak': 0.95,
                'flat': 0.65,
                'valley': 0.35,
                'deep_valley': 0.20,
            }
        }

        storage_config = {
            'capacity': 500.0,
            'max_charge_power': 100.0,
            'max_discharge_power': 100.0,
            'initial_soc': 0.50,
        }

        result = run_day_ahead_optimization(
            forecast_data=forecast,
            pricing_config=pricing_config,
            storage_config=storage_config,
            devices=[],
        )

        # 创建机会
        opportunity = await service.create_opportunity_from_optimization(
            optimization_result=result,
            optimization_type='day_ahead',
            target_date=date_str
        )

        if opportunity:
            opportunities.append(opportunity)

    return opportunities
