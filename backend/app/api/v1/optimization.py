"""
日前调度优化 API
提供负荷预测、优化计算、调度计划管理
"""
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pydantic import BaseModel, Field

from ..deps import get_db, get_current_user
from ...models.user import User
from ...services.forecasting import LoadForecaster, generate_demo_forecast
from ...services.optimizer import (
    run_day_ahead_optimization,
    PricingConfig,
    StorageConfig,
)

router = APIRouter()


# ==================== Pydantic 模型 ====================

class ForecastRequest(BaseModel):
    """负荷预测请求"""
    target_date: Optional[str] = Field(None, description="目标日期 YYYY-MM-DD")
    meter_point_id: Optional[int] = Field(None, description="计量点ID")
    base_load: Optional[float] = Field(300.0, description="基础负荷 kW")
    peak_load: Optional[float] = Field(800.0, description="峰值负荷 kW")


class OptimizationRequest(BaseModel):
    """优化请求"""
    target_date: Optional[str] = Field(None, description="目标日期")
    demand_target: Optional[float] = Field(None, description="需量目标 kW")

    # 电价配置
    demand_price: float = Field(40.0, description="需量单价 元/kW·月")
    declared_demand: float = Field(800.0, description="申报需量 kW")
    period_prices: Optional[dict] = Field(None, description="分时电价")

    # 储能配置
    use_storage: bool = Field(True, description="是否使用储能")
    storage_capacity: float = Field(500.0, description="储能容量 kWh")
    storage_charge_power: float = Field(100.0, description="最大充电功率 kW")
    storage_discharge_power: float = Field(100.0, description="最大放电功率 kW")
    storage_initial_soc: float = Field(0.5, description="初始SOC")


class ScheduleUpdateRequest(BaseModel):
    """调度状态更新请求"""
    status: str = Field(..., description="状态: pending/executed/skipped")
    notes: Optional[str] = Field(None, description="备注")


# ==================== API 端点 ====================

@router.get("/forecast", summary="获取负荷预测")
async def get_load_forecast(
    target_date: Optional[str] = Query(None, description="目标日期 YYYY-MM-DD"),
    meter_point_id: Optional[int] = Query(None, description="计量点ID"),
    base_load: float = Query(350.0, description="基础负荷 kW"),
    peak_load: float = Query(850.0, description="峰值负荷 kW"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取指定日期的24小时负荷预测

    返回96个15分钟时段的预测数据，包括：
    - 预测功率
    - 置信区间
    - 时段分类
    - 统计汇总
    """
    # 解析目标日期
    if target_date:
        try:
            date_obj = datetime.strptime(target_date, '%Y-%m-%d')
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式错误，请使用 YYYY-MM-DD")
    else:
        date_obj = datetime.now() + timedelta(days=1)

    # 创建预测器
    forecaster = LoadForecaster(base_load=base_load, peak_load=peak_load)

    # 执行预测
    forecast = forecaster.forecast_day(date_obj, noise_level=0.03)

    return {
        'code': 0,
        'message': 'success',
        'data': forecast
    }


@router.post("/day-ahead", summary="执行日前优化")
async def run_optimization(
    request: OptimizationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    执行日前调度优化

    流程：
    1. 获取负荷预测
    2. 加载可调度设备和储能配置
    3. 执行MILP优化
    4. 返回最优调度计划
    """
    # 解析目标日期
    if request.target_date:
        try:
            date_obj = datetime.strptime(request.target_date, '%Y-%m-%d')
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式错误")
    else:
        date_obj = datetime.now() + timedelta(days=1)

    # 1. 获取负荷预测
    forecast_data = generate_demo_forecast(date_obj)

    # 2. 构建电价配置
    pricing_config = {
        'demand_price': request.demand_price,
        'declared_demand': request.declared_demand,
        'period_prices': request.period_prices or {
            'sharp': 1.20,
            'peak': 0.95,
            'flat': 0.65,
            'valley': 0.35,
            'deep_valley': 0.20,
        }
    }

    # 3. 构建储能配置
    storage_config = None
    if request.use_storage:
        storage_config = {
            'capacity': request.storage_capacity,
            'max_charge_power': request.storage_charge_power,
            'max_discharge_power': request.storage_discharge_power,
            'initial_soc': request.storage_initial_soc,
            'charge_efficiency': 0.95,
            'discharge_efficiency': 0.95,
            'min_soc': 0.10,
            'max_soc': 0.90,
            'cycle_cost': 0.10,
        }

    # 4. TODO: 从数据库加载可调度设备
    devices = []

    # 5. 执行优化
    result = run_day_ahead_optimization(
        forecast_data=forecast_data,
        pricing_config=pricing_config,
        storage_config=storage_config,
        devices=devices,
        demand_target=request.demand_target,
    )

    # 6. TODO: 保存调度计划到数据库

    return {
        'code': 0,
        'message': 'success',
        'data': result
    }


@router.get("/day-ahead/{date}", summary="获取日前调度计划")
async def get_schedule(
    date: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取指定日期的调度计划

    如果数据库中没有，则实时计算
    """
    try:
        date_obj = datetime.strptime(date, '%Y-%m-%d')
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式错误")

    # TODO: 从数据库查询已保存的调度计划
    # 暂时返回实时计算的结果

    # 生成预测和优化
    forecast_data = generate_demo_forecast(date_obj)

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
        'charge_efficiency': 0.95,
        'discharge_efficiency': 0.95,
        'min_soc': 0.10,
        'max_soc': 0.90,
        'cycle_cost': 0.10,
    }

    result = run_day_ahead_optimization(
        forecast_data=forecast_data,
        pricing_config=pricing_config,
        storage_config=storage_config,
        devices=[],
        demand_target=None,
    )

    return {
        'code': 0,
        'message': 'success',
        'data': {
            'date': date,
            'forecast': forecast_data,
            'optimization': result,
            'status': 'generated',  # 'saved' or 'generated'
        }
    }


@router.put("/schedule/{schedule_id}", summary="更新调度状态")
async def update_schedule_status(
    schedule_id: int,
    request: ScheduleUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新调度项的执行状态

    状态：
    - pending: 待执行
    - executed: 已执行
    - skipped: 已跳过
    """
    # TODO: 从数据库更新调度状态
    # 暂时返回模拟结果

    return {
        'code': 0,
        'message': 'success',
        'data': {
            'schedule_id': schedule_id,
            'status': request.status,
            'updated_at': datetime.now().isoformat(),
        }
    }


@router.get("/summary", summary="获取优化汇总")
async def get_optimization_summary(
    month: Optional[str] = Query(None, description="月份 YYYY-MM"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取优化效果汇总

    包括：
    - 本月累计节省
    - 峰谷套利收益
    - 需量优化收益
    - 执行成功率
    """
    if not month:
        month = datetime.now().strftime('%Y-%m')

    # TODO: 从数据库聚合统计
    # 暂时返回模拟数据

    return {
        'code': 0,
        'message': 'success',
        'data': {
            'month': month,
            'total_saving': 12580.50,
            'peak_valley_saving': 8420.30,
            'demand_saving': 4160.20,
            'storage_cycles': 45,
            'execution_rate': 0.92,
            'schedule_count': 30,
            'executed_count': 28,
            'skipped_count': 2,
        }
    }


@router.get("/compare", summary="计划vs实际对比")
async def get_plan_actual_comparison(
    date: str = Query(..., description="日期 YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取计划与实际执行的对比数据

    用于分析预测准确性和优化效果
    """
    try:
        date_obj = datetime.strptime(date, '%Y-%m-%d')
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式错误")

    # TODO: 从数据库获取计划和实际数据
    # 暂时返回模拟数据

    # 生成计划数据
    forecast_data = generate_demo_forecast(date_obj)
    planned_load = [f['predicted_power'] for f in forecast_data['forecasts']]

    # 模拟实际数据（添加随机偏差）
    import numpy as np
    actual_load = [
        max(0, p + np.random.normal(0, p * 0.08))
        for p in planned_load
    ]

    return {
        'code': 0,
        'message': 'success',
        'data': {
            'date': date,
            'planned_load': [round(p, 2) for p in planned_load],
            'actual_load': [round(a, 2) for a in actual_load],
            'deviation': {
                'mean_absolute_error': round(np.mean(np.abs(np.array(planned_load) - np.array(actual_load))), 2),
                'mean_percentage_error': round(np.mean(np.abs(np.array(planned_load) - np.array(actual_load)) / np.array(planned_load)) * 100, 2),
                'max_deviation': round(max(np.abs(np.array(planned_load) - np.array(actual_load))), 2),
            },
            'cost_comparison': {
                'planned_cost': round(sum(planned_load) * 0.25 * 0.65, 2),  # 简化计算
                'actual_cost': round(sum(actual_load) * 0.25 * 0.65, 2),
            }
        }
    }


# ==================== 反馈学习 API ====================

@router.get("/learning/metrics", summary="获取学习指标")
async def get_learning_metrics(
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取预测模型的学习指标

    包括：
    - MAE: 平均绝对误差
    - MAPE: 平均百分比误差
    - RMSE: 均方根误差
    - Bias: 偏差
    - 准确率
    """
    from app.services.feedback_learning import get_feedback_learner, generate_sample_history

    learner = get_feedback_learner()

    # 如果没有历史数据，生成样本数据
    if len(learner.deviation_history) < 100:
        generate_sample_history(30)

    # 解析日期
    start = None
    end = None
    if start_date:
        start = datetime.strptime(start_date, '%Y-%m-%d')
    if end_date:
        end = datetime.strptime(end_date, '%Y-%m-%d')

    metrics = learner.calculate_metrics(start, end)

    return {
        'code': 0,
        'message': 'success',
        'data': {
            'period': metrics.period,
            'total_records': metrics.total_records,
            'mae': metrics.mae,
            'mape': metrics.mape,
            'rmse': metrics.rmse,
            'bias': metrics.bias,
            'max_deviation': metrics.max_deviation,
            'accuracy_rate': metrics.accuracy_rate,
        }
    }


@router.post("/learning/adjust", summary="执行参数调整")
async def run_parameter_adjustment(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    基于历史偏差执行参数自动调整

    返回调整后的预测参数
    """
    from app.services.feedback_learning import get_feedback_learner

    learner = get_feedback_learner()
    new_params = learner.learn_and_adjust()

    return {
        'code': 0,
        'message': 'success',
        'data': {
            'adjusted_params': new_params,
            'history_count': len(learner.deviation_history),
        }
    }


@router.get("/learning/report", summary="获取优化效果报告")
async def get_optimization_report(
    month: Optional[str] = Query(None, description="月份 YYYY-MM"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取指定月份的优化效果报告

    包括：
    - 成本节省分析
    - 调度执行统计
    - 需量控制情况
    - 预测质量评估
    - 改进建议
    """
    from app.services.feedback_learning import get_feedback_learner, generate_sample_history

    learner = get_feedback_learner()

    # 确保有历史数据
    if len(learner.deviation_history) < 100:
        generate_sample_history(30)

    # 解析月份
    if month:
        year, mon = map(int, month.split('-'))
        start_date = datetime(year, mon, 1)
        if mon == 12:
            end_date = datetime(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = datetime(year, mon + 1, 1) - timedelta(days=1)
    else:
        now = datetime.now()
        start_date = datetime(now.year, now.month, 1)
        end_date = now

    report = learner.generate_report(start_date, end_date)

    return {
        'code': 0,
        'message': 'success',
        'data': {
            'period': report.period,
            'start_date': report.start_date,
            'end_date': report.end_date,
            'cost_analysis': {
                'planned_saving': report.planned_saving,
                'actual_saving': report.actual_saving,
                'saving_achievement': report.saving_achievement,
            },
            'execution_stats': {
                'total_schedules': report.total_schedules,
                'executed_schedules': report.executed_schedules,
                'success_rate': report.success_rate,
            },
            'demand_control': {
                'violations': report.demand_violations,
                'max_reached': report.max_demand_reached,
                'target': report.demand_target,
                'utilization': report.demand_utilization,
            },
            'forecast_quality': {
                'mae': report.forecast_metrics.mae,
                'mape': report.forecast_metrics.mape,
                'accuracy_rate': report.forecast_metrics.accuracy_rate,
                'bias': report.forecast_metrics.bias,
            },
            'recommendations': report.recommendations,
        }
    }


@router.post("/learning/feedback", summary="提交反馈数据")
async def submit_feedback_data(
    planned: float = Query(..., description="计划值"),
    actual: float = Query(..., description="实际值"),
    timestamp: Optional[str] = Query(None, description="时间戳 ISO格式"),
    source: str = Query('manual', description="数据来源"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    提交计划vs实际对比数据用于学习

    可用于手动录入执行结果
    """
    from app.services.feedback_learning import get_feedback_learner

    learner = get_feedback_learner()

    if timestamp:
        ts = datetime.fromisoformat(timestamp)
    else:
        ts = datetime.now()

    record = learner.add_comparison_data(
        timestamp=ts,
        planned=planned,
        actual=actual,
        source=source
    )

    return {
        'code': 0,
        'message': 'success',
        'data': {
            'timestamp': record.timestamp.isoformat(),
            'planned': record.planned_value,
            'actual': record.actual_value,
            'deviation': record.deviation,
            'deviation_percent': record.deviation_percent,
            'deviation_type': record.deviation_type.value,
        }
    }


# ==================== 节能中心集成 API ====================

@router.post("/integration/create-opportunity", summary="从优化结果创建节能机会")
async def create_opportunity_from_optimization(
    target_date: Optional[str] = Query(None, description="目标日期 YYYY-MM-DD"),
    optimization_type: str = Query('day_ahead', description="优化类型"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    从优化结果创建节能机会

    自动执行优化并将结果转化为节能机会
    """
    from app.services.optimization_integration import OptimizationIntegrationService
    from app.services.forecasting import generate_demo_forecast
    from app.services.optimizer import run_day_ahead_optimization

    # 解析日期
    if target_date:
        date_obj = datetime.strptime(target_date, '%Y-%m-%d')
    else:
        date_obj = datetime.now() + timedelta(days=1)

    # 执行优化
    forecast = generate_demo_forecast(date_obj)

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
    service = OptimizationIntegrationService(db)
    opportunity = await service.create_opportunity_from_optimization(
        optimization_result=result,
        optimization_type=optimization_type,
        target_date=date_obj.strftime('%Y-%m-%d')
    )

    if opportunity:
        return {
            'code': 0,
            'message': 'success',
            'data': {
                'opportunity_id': opportunity.id,
                'title': opportunity.title,
                'potential_saving': opportunity.potential_saving,
                'priority': opportunity.priority,
                'optimization_result': {
                    'expected_saving': result.get('expected_saving'),
                    'saving_ratio': result.get('saving_ratio'),
                    'max_demand': result.get('max_demand'),
                }
            }
        }
    else:
        return {
            'code': 400,
            'message': '优化结果无节省潜力，未创建机会',
            'data': None
        }


@router.post("/integration/auto-generate", summary="自动生成节能机会")
async def auto_generate_opportunities(
    days: int = Query(7, description="生成未来几天的机会", ge=1, le=30),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    自动为未来几天生成节能机会

    批量执行优化并创建节能机会
    """
    from app.services.optimization_integration import auto_generate_opportunities as gen_opps

    opportunities = await gen_opps(db, days)

    return {
        'code': 0,
        'message': 'success',
        'data': {
            'generated_count': len(opportunities),
            'opportunities': [
                {
                    'id': o.id,
                    'title': o.title,
                    'potential_saving': o.potential_saving,
                    'priority': o.priority,
                }
                for o in opportunities
            ]
        }
    }


@router.get("/integration/statistics", summary="获取优化统计")
async def get_optimization_statistics(
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取优化相关的统计数据

    包括机会数量、潜在节省、实际节省等
    """
    from app.services.optimization_integration import OptimizationIntegrationService

    service = OptimizationIntegrationService(db)

    start = datetime.strptime(start_date, '%Y-%m-%d') if start_date else None
    end = datetime.strptime(end_date, '%Y-%m-%d') if end_date else None

    stats = await service.get_optimization_statistics(start, end)

    return {
        'code': 0,
        'message': 'success',
        'data': stats
    }
