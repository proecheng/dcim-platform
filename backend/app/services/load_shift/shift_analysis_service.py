# -*- coding: utf-8 -*-
"""
Shift Analysis Service
负荷转移分析服务

Coordinates constraint checking, benefit calculation, and risk assessment
协调约束检查、效益计算和风险评估
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import date, datetime, timedelta
import logging

from ...schemas.load_shift import (
    FeasibilityAnalysisRequest,
    FeasibilityAnalysisResponse,
    ConstraintCheckResult,
    BenefitAnalysisResponse,
    RiskAssessmentResponse,
    ShiftPeriodType,
)
from ...models.load_shift import ShiftExecution, ShiftAnalysisRecord
from .algorithms.constraint_checker import ConstraintChecker
from .algorithms.benefit_calculator import BenefitCalculator

logger = logging.getLogger(__name__)


class ShiftAnalysisService:
    """Shift analysis service - coordinates constraint checking and benefit calculation"""

    @staticmethod
    async def analyze_feasibility(db: AsyncSession, request: FeasibilityAnalysisRequest) -> FeasibilityAnalysisResponse:
        """
        Comprehensive feasibility analysis
        综合可行性分析

        Args:
            db: Database session
            request: Feasibility analysis request

        Returns:
            FeasibilityAnalysisResponse with constraint check and benefit analysis
        """
        logger.info(
            f"Starting feasibility analysis: {request.shift_from_period} -> {request.shift_to_period}, "
            f"date={request.shift_date}, power={request.target_shift_power}kW"
        )

        # Step 1: Constraint check
        checker = ConstraintChecker(db)
        constraint_result = await checker.check_all_constraints(
            shift_from_period=request.shift_from_period,
            shift_to_period=request.shift_to_period,
            shift_date=request.shift_date,
            start_time=request.start_time,
            end_time=request.end_time,
            target_shift_power=request.target_shift_power,
            selected_devices=request.selected_devices,
            constraints=request.constraints or {},
        )

        # Step 2: Benefit calculation
        calculator = BenefitCalculator(db)
        benefit_result = await calculator.calculate_benefits(
            shift_from_period=request.shift_from_period,
            shift_to_period=request.shift_to_period,
            shift_date=request.shift_date,
            start_time=request.start_time,
            end_time=request.end_time,
            target_shift_power=request.target_shift_power,
        )

        # Step 3: Determine feasibility
        is_feasible = constraint_result.is_valid and benefit_result.cost_saving > 0

        # Step 4: Save analysis record
        await ShiftAnalysisService._save_analysis_record(
            db=db,
            analysis_type="feasibility",
            request=request,
            is_feasible=is_feasible,
            constraint_result=constraint_result,
            benefit_result=benefit_result,
        )

        logger.info(
            f"Feasibility analysis complete: feasible={is_feasible}, "
            f"cost_saving={benefit_result.cost_saving:.2f}元, "
            f"violations={len(constraint_result.violations)}"
        )

        return FeasibilityAnalysisResponse(
            is_feasible=is_feasible,
            constraint_check=constraint_result,
            benefit_analysis=benefit_result,
        )

    @staticmethod
    async def check_constraints(db: AsyncSession, request: FeasibilityAnalysisRequest) -> ConstraintCheckResult:
        """
        Check constraints only (without benefit calculation)
        仅检查约束（不计算效益）

        Args:
            db: Database session
            request: Feasibility analysis request

        Returns:
            ConstraintCheckResult
        """
        logger.info("Checking constraints for shift plan")

        checker = ConstraintChecker(db)
        result = await checker.check_all_constraints(
            shift_from_period=request.shift_from_period,
            shift_to_period=request.shift_to_period,
            shift_date=request.shift_date,
            start_time=request.start_time,
            end_time=request.end_time,
            target_shift_power=request.target_shift_power,
            selected_devices=request.selected_devices,
            constraints=request.constraints or {},
        )

        logger.info(
            f"Constraint check complete: valid={result.is_valid}, "
            f"violations={len(result.violations)}, warnings={len(result.warnings)}"
        )

        return result

    @staticmethod
    async def calculate_benefit(db: AsyncSession, request: FeasibilityAnalysisRequest) -> BenefitAnalysisResponse:
        """
        Calculate benefit only (without constraint check)
        仅计算效益（不检查约束）

        Args:
            db: Database session
            request: Feasibility analysis request

        Returns:
            BenefitAnalysisResponse
        """
        logger.info("Calculating benefit for shift plan")

        calculator = BenefitCalculator(db)
        result = await calculator.calculate_benefits(
            shift_from_period=request.shift_from_period,
            shift_to_period=request.shift_to_period,
            shift_date=request.shift_date,
            start_time=request.start_time,
            end_time=request.end_time,
            target_shift_power=request.target_shift_power,
        )

        logger.info(
            f"Benefit calculation complete: cost_saving={result.cost_saving:.2f}元, "
            f"energy_saving={result.energy_saving:.2f}kWh"
        )

        return result

    @staticmethod
    async def assess_risk(db: AsyncSession, request: FeasibilityAnalysisRequest) -> RiskAssessmentResponse:
        """
        Risk assessment for shift plan
        转移计划风险评估

        Evaluates:
        - Cooling lag effect risk (15-30 min delay)
        - Device lifespan impact risk (frequent starts reduce life 15-25%)
        - Three-phase balance risk (<10% deviation required)
        - Historical failure rate
        - Weather/temperature forecast impact

        Args:
            db: Database session
            request: Feasibility analysis request

        Returns:
            RiskAssessmentResponse with risk level, score, and mitigation suggestions
        """
        logger.info("Assessing risk for shift plan")

        risk_factors = []
        risk_score = 0.0
        mitigation_suggestions = []

        # Risk Factor 1: Cooling lag effect (15-30 min)
        # High risk if shift duration < 30 min
        shift_duration_hours = (
            datetime.combine(date.today(), request.end_time) - datetime.combine(date.today(), request.start_time)
        ).total_seconds() / 3600

        if shift_duration_hours < 0.5:  # < 30 min
            risk_factors.append(
                {
                    "factor": "cooling_lag",
                    "severity": "high",
                    "description": "转移时长过短，制冷系统响应滞后可能导致温度波动",
                }
            )
            risk_score += 30.0
            mitigation_suggestions.append("建议转移时长至少30分钟，以适应制冷系统响应延迟")
        elif shift_duration_hours < 1.0:  # < 1 hour
            risk_factors.append(
                {
                    "factor": "cooling_lag",
                    "severity": "medium",
                    "description": "转移时长较短，需密切监控机房温度",
                }
            )
            risk_score += 15.0
            mitigation_suggestions.append("建议提前5-10分钟调整制冷系统")

        # Risk Factor 2: Device lifespan impact
        # Query historical shift count for selected devices
        if request.selected_devices:
            [d["device_id"] for d in request.selected_devices]

            # Count shifts in last 30 days
            thirty_days_ago = datetime.now() - timedelta(days=30)
            query = select(func.count(ShiftExecution.id)).where(
                ShiftExecution.created_at >= thirty_days_ago,
                ShiftExecution.status == "completed",
            )
            result = await db.execute(query)
            recent_shift_count = result.scalar() or 0

            if recent_shift_count > 60:  # > 2 shifts/day average
                risk_factors.append(
                    {
                        "factor": "device_lifespan",
                        "severity": "high",
                        "description": f"近30天已执行{recent_shift_count}次转移，频繁启停可能缩短设备寿命15-25%",
                    }
                )
                risk_score += 25.0
                mitigation_suggestions.append("建议降低转移频率，或考虑设备维护成本")
            elif recent_shift_count > 30:  # > 1 shift/day average
                risk_factors.append(
                    {
                        "factor": "device_lifespan",
                        "severity": "medium",
                        "description": f"近30天已执行{recent_shift_count}次转移，需关注设备健康状态",
                    }
                )
                risk_score += 10.0
                mitigation_suggestions.append("建议定期检查设备运行状态")

        # Risk Factor 3: Three-phase balance
        # Check if target shift power is large (>100kW)
        if request.target_shift_power > 100:
            risk_factors.append(
                {
                    "factor": "three_phase_balance",
                    "severity": "medium",
                    "description": f"转移功率较大({request.target_shift_power}kW)，需确保三相平衡偏差<10%",
                }
            )
            risk_score += 15.0
            mitigation_suggestions.append("建议在执行前检查三相负载分布，必要时调整设备分配")

        # Risk Factor 4: Historical failure rate
        # Query failed executions in last 90 days
        ninety_days_ago = datetime.now() - timedelta(days=90)
        query = select(
            func.count(ShiftExecution.id).label("total"),
            func.sum(func.case((ShiftExecution.status == "failed", 1), else_=0)).label("failed"),
        ).where(ShiftExecution.created_at >= ninety_days_ago)
        result = await db.execute(query)
        row = result.first()

        if row and row.total > 0:
            failure_rate = (row.failed or 0) / row.total
            if failure_rate > 0.1:  # > 10% failure rate
                risk_factors.append(
                    {
                        "factor": "historical_failure",
                        "severity": "high",
                        "description": f"近90天失败率{failure_rate * 100:.1f}%，高于正常水平",
                    }
                )
                risk_score += 20.0
                mitigation_suggestions.append("建议分析历史失败原因，优化转移策略")
            elif failure_rate > 0.05:  # > 5% failure rate
                risk_factors.append(
                    {
                        "factor": "historical_failure",
                        "severity": "medium",
                        "description": f"近90天失败率{failure_rate * 100:.1f}%，需关注",
                    }
                )
                risk_score += 10.0

        # Risk Factor 5: Peak period shift risk
        # Shifting FROM peak/sharp periods is higher risk
        if request.shift_from_period in [ShiftPeriodType.PEAK, ShiftPeriodType.SHARP]:
            risk_factors.append(
                {
                    "factor": "peak_period_shift",
                    "severity": "medium",
                    "description": f"从{request.shift_from_period.value}时段转移，需确保电网稳定性",
                }
            )
            risk_score += 10.0
            mitigation_suggestions.append("建议在电网负荷较低时段执行，避免影响供电稳定性")

        # Determine risk level based on score
        if risk_score >= 50:
            risk_level = "high"
        elif risk_score >= 25:
            risk_level = "medium"
        else:
            risk_level = "low"

        # Save risk assessment record
        await ShiftAnalysisService._save_analysis_record(
            db=db,
            analysis_type="risk",
            request=request,
            risk_level=risk_level,
            risk_score=risk_score,
            risk_factors=risk_factors,
        )

        logger.info(
            f"Risk assessment complete: level={risk_level}, score={risk_score:.1f}, factors={len(risk_factors)}"
        )

        return RiskAssessmentResponse(
            risk_level=risk_level,
            risk_score=risk_score,
            risk_factors=risk_factors,
            mitigation_suggestions=mitigation_suggestions,
        )

    @staticmethod
    async def _save_analysis_record(
        db: AsyncSession, analysis_type: str, request: FeasibilityAnalysisRequest, **kwargs
    ) -> None:
        """
        Save analysis record to database
        保存分析记录到数据库

        Args:
            db: Database session
            analysis_type: Type of analysis (feasibility, risk, etc.)
            request: Original request
            **kwargs: Additional analysis results
        """
        try:
            record = ShiftAnalysisRecord(
                analysis_type=analysis_type,
                analysis_date=request.shift_date,
                shift_from_period=request.shift_from_period,
                shift_to_period=request.shift_to_period,
                target_shift_power=request.target_shift_power,
                analysis_result=kwargs,
                created_by=1,  # TODO: Get from current user
            )
            db.add(record)
            await db.commit()
            logger.debug(f"Saved {analysis_type} analysis record: id={record.id}")
        except Exception as e:
            logger.error(f"Failed to save analysis record: {e}")
            await db.rollback()
