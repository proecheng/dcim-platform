"""
节能机会测试数据初始化脚本
初始化节能机会、措施、执行计划、任务等测试数据
"""
import asyncio
import random
from datetime import datetime, timedelta
from decimal import Decimal
from app.core.database import async_session, init_db, engine, Base
from app.models.energy import (
    EnergyOpportunity, OpportunityMeasure,
    ExecutionPlan, ExecutionTask, ExecutionResult,
    PricingConfig, PowerDevice, LoadRegulationConfig
)


# ==================== 节能机会测试数据 ====================

OPPORTUNITIES = [
    # 类别1: 电费结构优化
    {
        "category": 1,
        "title": "需量申报优化 - 降低申报需量至750kW",
        "description": "当前申报需量800kW，实际最大需量稳定在680kW左右，建议将申报需量调整为750kW",
        "priority": "high",
        "potential_saving": Decimal("28800"),  # 年度节省
        "confidence": Decimal("0.92"),
        "source_plugin": "demand_optimizer",
        "analysis_data": {
            "current_declared": 800,
            "recommended_declared": 750,
            "max_demand_12m": 685,
            "avg_demand_12m": 520,
            "demand_unit_price": 28,
            "monthly_saving": 1400,
            "risk_level": "low"
        }
    },
    {
        "category": 1,
        "title": "峰谷套利优化 - 转移100kW峰时负荷至谷时",
        "description": "通过调整可转移负荷的运行时段，将100kW负荷从峰时转移至谷时运行",
        "priority": "high",
        "potential_saving": Decimal("43800"),
        "confidence": Decimal("0.88"),
        "source_plugin": "peak_valley_optimizer",
        "analysis_data": {
            "shift_power": 100,
            "shift_hours": 4,
            "peak_price": 1.2,
            "valley_price": 0.4,
            "price_diff": 0.8,
            "shiftable_devices": [5, 6, 7],
            "daily_saving": 120
        }
    },
    {
        "category": 1,
        "title": "力调电费优化 - 提高功率因数至0.95",
        "description": "当前功率因数0.88，建议增加无功补偿设备，将功率因数提高至0.95以上",
        "priority": "medium",
        "potential_saving": Decimal("18000"),
        "confidence": Decimal("0.85"),
        "source_plugin": "power_factor_optimizer",
        "analysis_data": {
            "current_pf": 0.88,
            "target_pf": 0.95,
            "penalty_rate": 0.05,
            "monthly_bill": 50000,
            "monthly_saving": 1500
        }
    },
    # 类别2: 设备运行优化
    {
        "category": 2,
        "title": "精密空调温度优化 - 提高设定温度至26℃",
        "description": "将数据中心精密空调设定温度从24℃提高至26℃，预计节能15%",
        "priority": "high",
        "potential_saving": Decimal("52000"),
        "confidence": Decimal("0.90"),
        "source_plugin": "hvac_optimizer",
        "analysis_data": {
            "current_temp": 24,
            "target_temp": 26,
            "cooling_power": 150,
            "energy_reduction_rate": 0.15,
            "comfort_impact": "low",
            "affected_devices": [1, 2, 3]
        }
    },
    {
        "category": 2,
        "title": "照明系统优化 - 实施智能照明控制",
        "description": "在办公区域实施人体感应+光照感应智能控制，减少不必要的照明能耗",
        "priority": "medium",
        "potential_saving": Decimal("12000"),
        "confidence": Decimal("0.82"),
        "source_plugin": "lighting_optimizer",
        "analysis_data": {
            "current_usage_hours": 12,
            "optimized_hours": 8,
            "lighting_power": 30,
            "reduction_rate": 0.33
        }
    },
    {
        "category": 2,
        "title": "UPS负载均衡优化",
        "description": "调整UPS负载分配，使各台UPS负载率保持在40-60%最佳效率区间",
        "priority": "medium",
        "potential_saving": Decimal("8500"),
        "confidence": Decimal("0.78"),
        "source_plugin": "ups_optimizer",
        "analysis_data": {
            "current_efficiency": 0.92,
            "target_efficiency": 0.95,
            "ups_loss_reduction": 0.03
        }
    },
    # 类别3: 设备改造升级
    {
        "category": 3,
        "title": "老旧空调更换为变频机组",
        "description": "将3台老旧定频空调更换为高效变频机组，预计节能30%",
        "priority": "low",
        "potential_saving": Decimal("36000"),
        "confidence": Decimal("0.75"),
        "source_plugin": "equipment_upgrade",
        "analysis_data": {
            "equipment_count": 3,
            "upgrade_cost": 150000,
            "annual_saving": 36000,
            "payback_years": 4.2,
            "energy_reduction_rate": 0.30
        }
    },
    {
        "category": 3,
        "title": "增加无功补偿装置",
        "description": "安装SVG动态无功补偿装置，实现功率因数自动调节",
        "priority": "medium",
        "potential_saving": Decimal("24000"),
        "confidence": Decimal("0.80"),
        "source_plugin": "equipment_upgrade",
        "analysis_data": {
            "equipment_type": "SVG",
            "capacity": 200,
            "upgrade_cost": 80000,
            "payback_years": 3.3
        }
    },
    # 类别4: 综合能效提升
    {
        "category": 4,
        "title": "综合能效管理方案",
        "description": "结合需量控制、峰谷套利、设备调节的综合优化方案",
        "priority": "high",
        "potential_saving": Decimal("85000"),
        "confidence": Decimal("0.85"),
        "source_plugin": "comprehensive_optimizer",
        "analysis_data": {
            "demand_saving": 28800,
            "peak_valley_saving": 43800,
            "operation_saving": 12400,
            "components": ["demand", "peak_valley", "hvac"]
        }
    }
]


# ==================== 措施模板 ====================

def get_measures_for_opportunity(opp_data: dict, opp_id: int) -> list:
    """根据机会类型生成措施列表"""
    measures = []
    category = opp_data["category"]

    if category == 1 and "demand" in opp_data.get("source_plugin", ""):
        # 需量优化措施
        measures = [
            {
                "opportunity_id": opp_id,
                "measure_type": "demand_adjust",
                "measure_name": "调整申报需量",
                "regulation_object": "计量点M001",
                "current_state": {"declared_demand": 800},
                "target_state": {"declared_demand": 750},
                "execution_mode": "manual",
                "annual_benefit": 28800,
                "sort_order": 1
            },
            {
                "opportunity_id": opp_id,
                "measure_type": "monitoring",
                "measure_name": "设置需量预警",
                "regulation_object": "监控系统",
                "current_state": {"alert_threshold": None},
                "target_state": {"alert_threshold": 720},
                "execution_mode": "auto",
                "annual_benefit": 0,
                "sort_order": 2
            }
        ]
    elif category == 1 and "peak_valley" in opp_data.get("source_plugin", ""):
        # 峰谷套利措施
        measures = [
            {
                "opportunity_id": opp_id,
                "measure_type": "load_shift",
                "measure_name": "转移空调负荷至谷时",
                "regulation_object": "精密空调组",
                "current_state": {"run_period": "08:00-22:00"},
                "target_state": {"run_period": "00:00-08:00,12:00-18:00"},
                "execution_mode": "auto",
                "annual_benefit": 30000,
                "selected_devices": [5, 6],
                "sort_order": 1
            },
            {
                "opportunity_id": opp_id,
                "measure_type": "load_shift",
                "measure_name": "转移充电负荷至谷时",
                "regulation_object": "UPS充电",
                "current_state": {"charge_period": "peak"},
                "target_state": {"charge_period": "valley"},
                "execution_mode": "manual",
                "annual_benefit": 13800,
                "sort_order": 2
            }
        ]
    elif category == 2 and "hvac" in opp_data.get("source_plugin", ""):
        # 空调温度优化措施
        measures = [
            {
                "opportunity_id": opp_id,
                "measure_type": "temp_adjust",
                "measure_name": "调整1#精密空调温度",
                "regulation_object": "精密空调PAC-001",
                "current_state": {"temperature": 24},
                "target_state": {"temperature": 26},
                "execution_mode": "auto",
                "annual_benefit": 18000,
                "selected_devices": [1],
                "sort_order": 1
            },
            {
                "opportunity_id": opp_id,
                "measure_type": "temp_adjust",
                "measure_name": "调整2#精密空调温度",
                "regulation_object": "精密空调PAC-002",
                "current_state": {"temperature": 24},
                "target_state": {"temperature": 26},
                "execution_mode": "auto",
                "annual_benefit": 17000,
                "selected_devices": [2],
                "sort_order": 2
            },
            {
                "opportunity_id": opp_id,
                "measure_type": "temp_adjust",
                "measure_name": "调整3#精密空调温度",
                "regulation_object": "精密空调PAC-003",
                "current_state": {"temperature": 24},
                "target_state": {"temperature": 26},
                "execution_mode": "auto",
                "annual_benefit": 17000,
                "selected_devices": [3],
                "sort_order": 3
            }
        ]
    else:
        # 通用措施
        measures = [
            {
                "opportunity_id": opp_id,
                "measure_type": "general",
                "measure_name": f"执行{opp_data['title'][:20]}",
                "regulation_object": "相关设备",
                "current_state": {},
                "target_state": {},
                "execution_mode": "manual",
                "annual_benefit": float(opp_data["potential_saving"]) * 0.8,
                "sort_order": 1
            }
        ]

    return measures


# ==================== 全局电价配置 ====================

PRICING_CONFIG = {
    "config_name": "2024年度电价配置",
    "effective_date": datetime(2024, 1, 1),
    "expire_date": datetime(2025, 12, 31),
    "billing_mode": "demand",
    "demand_price": 38.0,
    "declared_demand": 800.0,
    "over_demand_multiplier": 2.0,
    "capacity_price": 28.0,
    "transformer_capacity": 1800.0,
    "power_factor_baseline": 0.90,
    "power_factor_rules": [
        {"min": 0.95, "max": 1.0, "adjustment": -0.75},
        {"min": 0.90, "max": 0.95, "adjustment": 0},
        {"min": 0.85, "max": 0.90, "adjustment": 1.5},
        {"min": 0, "max": 0.85, "adjustment": 3.0}
    ],
    "transmission_fee": 0.15,
    "government_fund": 0.05,
    "auxiliary_fee": 0.02,
    "other_fee": 0.0,
    "is_enabled": True
}


async def create_tables():
    """创建新表"""
    print("创建数据库表...")
    async with engine.begin() as conn:
        # 只创建新表，不删除已有表
        await conn.run_sync(Base.metadata.create_all)
    print("[OK] 表结构创建完成")


async def init_pricing_config():
    """初始化全局电价配置"""
    print("\n初始化全局电价配置...")
    async with async_session() as session:
        # 检查是否已存在
        from sqlalchemy import select
        result = await session.execute(
            select(PricingConfig).where(PricingConfig.is_enabled == True)
        )
        existing = result.scalar_one_or_none()

        if existing:
            print(f"  已存在配置: {existing.config_name}")
            return existing.id

        config = PricingConfig(**PRICING_CONFIG)
        session.add(config)
        await session.commit()
        await session.refresh(config)
        print(f"[OK] 创建电价配置: {config.config_name} (ID: {config.id})")
        return config.id


async def init_opportunities():
    """初始化节能机会数据"""
    print("\n初始化节能机会...")
    async with async_session() as session:
        from sqlalchemy import select

        # 检查是否已有数据
        result = await session.execute(select(EnergyOpportunity))
        existing = result.scalars().all()
        if existing:
            print(f"  已存在 {len(existing)} 条机会数据")
            return [o.id for o in existing]

        opportunity_ids = []
        for opp_data in OPPORTUNITIES:
            opp = EnergyOpportunity(
                category=opp_data["category"],
                title=opp_data["title"],
                description=opp_data.get("description"),
                priority=opp_data["priority"],
                status="discovered",
                potential_saving=opp_data["potential_saving"],
                confidence=opp_data.get("confidence", Decimal("0.80")),
                source_plugin=opp_data.get("source_plugin"),
                analysis_data=opp_data.get("analysis_data"),
                discovered_at=datetime.now() - timedelta(days=random.randint(1, 30))
            )
            session.add(opp)
            await session.flush()
            opportunity_ids.append(opp.id)
            print(f"  [OK] 机会 #{opp.id}: {opp.title[:30]}...")

            # 添加措施
            measures = get_measures_for_opportunity(opp_data, opp.id)
            for m_data in measures:
                measure = OpportunityMeasure(**m_data)
                session.add(measure)

        await session.commit()
        print(f"[OK] 创建 {len(opportunity_ids)} 条节能机会")
        return opportunity_ids


async def init_execution_plans(opportunity_ids: list):
    """初始化执行计划（选择部分机会创建已执行的计划）"""
    print("\n初始化执行计划...")
    async with async_session() as session:
        from sqlalchemy import select

        # 检查是否已有数据
        result = await session.execute(select(ExecutionPlan))
        existing = result.scalars().all()
        if existing:
            print(f"  已存在 {len(existing)} 条计划数据")
            return

        # 为前3个机会创建执行计划
        plans_data = [
            {
                "opportunity_id": opportunity_ids[0] if len(opportunity_ids) > 0 else 1,
                "plan_name": "需量优化执行计划",
                "expected_saving": Decimal("28800"),
                "status": "completed",
                "started_at": datetime.now() - timedelta(days=20),
                "completed_at": datetime.now() - timedelta(days=15)
            },
            {
                "opportunity_id": opportunity_ids[1] if len(opportunity_ids) > 1 else 2,
                "plan_name": "峰谷套利执行计划",
                "expected_saving": Decimal("43800"),
                "status": "executing",
                "started_at": datetime.now() - timedelta(days=5)
            },
            {
                "opportunity_id": opportunity_ids[3] if len(opportunity_ids) > 3 else 4,
                "plan_name": "空调温度优化执行计划",
                "expected_saving": Decimal("52000"),
                "status": "pending"
            }
        ]

        for plan_data in plans_data:
            plan = ExecutionPlan(**plan_data)
            session.add(plan)
            await session.flush()
            print(f"  [OK] 计划 #{plan.id}: {plan.plan_name} ({plan.status})")

            # 为每个计划添加任务
            tasks = [
                {
                    "plan_id": plan.id,
                    "task_type": "config_adjust",
                    "task_name": "参数配置调整",
                    "target_object": "系统配置",
                    "execution_mode": "manual",
                    "status": "completed" if plan.status in ["completed", "executing"] else "pending",
                    "executed_at": datetime.now() - timedelta(days=18) if plan.status == "completed" else None,
                    "sort_order": 1
                },
                {
                    "plan_id": plan.id,
                    "task_type": "device_control",
                    "task_name": "设备参数调节",
                    "target_object": "相关设备",
                    "execution_mode": "auto",
                    "status": "completed" if plan.status == "completed" else ("executing" if plan.status == "executing" else "pending"),
                    "executed_at": datetime.now() - timedelta(days=16) if plan.status == "completed" else None,
                    "sort_order": 2
                },
                {
                    "plan_id": plan.id,
                    "task_type": "monitoring",
                    "task_name": "效果监控验证",
                    "target_object": "监控系统",
                    "execution_mode": "manual",
                    "status": "completed" if plan.status == "completed" else "pending",
                    "executed_at": datetime.now() - timedelta(days=15) if plan.status == "completed" else None,
                    "sort_order": 3
                }
            ]

            for task_data in tasks:
                task = ExecutionTask(**task_data)
                session.add(task)

            # 为已完成的计划添加追踪结果
            if plan.status == "completed":
                tracking = ExecutionResult(
                    plan_id=plan.id,
                    tracking_period=7,
                    tracking_start=(datetime.now() - timedelta(days=14)).date(),
                    tracking_end=(datetime.now() - timedelta(days=7)).date(),
                    actual_saving=Decimal(str(float(plan.expected_saving) * random.uniform(0.85, 1.1))),
                    achievement_rate=Decimal(str(random.uniform(85, 105))),
                    energy_before={"total_energy": 15000, "avg_power": 625},
                    energy_after={"total_energy": 13500, "avg_power": 562},
                    status="completed",
                    analysis_conclusion="执行效果良好，基本达成预期目标"
                )
                session.add(tracking)

        await session.commit()
        print(f"[OK] 创建 {len(plans_data)} 个执行计划及相关任务")


async def update_opportunity_status():
    """更新已执行机会的状态"""
    print("\n更新机会状态...")
    async with async_session() as session:
        from sqlalchemy import select, update

        # 将有执行计划的机会状态更新
        result = await session.execute(select(ExecutionPlan))
        plans = result.scalars().all()

        for plan in plans:
            status_map = {
                "pending": "ready",
                "executing": "executing",
                "completed": "completed"
            }
            new_status = status_map.get(plan.status, "discovered")

            await session.execute(
                update(EnergyOpportunity)
                .where(EnergyOpportunity.id == plan.opportunity_id)
                .values(status=new_status, updated_at=datetime.now())
            )

        await session.commit()
        print(f"[OK] 更新 {len(plans)} 条机会状态")


async def main():
    """主函数"""
    print("=" * 50)
    print("节能机会测试数据初始化")
    print("=" * 50)

    # 1. 创建表
    await create_tables()

    # 2. 初始化全局电价配置
    await init_pricing_config()

    # 3. 初始化节能机会
    opportunity_ids = await init_opportunities()

    # 4. 初始化执行计划
    await init_execution_plans(opportunity_ids)

    # 5. 更新机会状态
    await update_opportunity_status()

    print("\n" + "=" * 50)
    print("测试数据初始化完成!")
    print("=" * 50)
    print("\n可以通过以下方式验证:")
    print("  1. 启动后端: python -m uvicorn app.main:app --reload")
    print("  2. 访问API: http://localhost:8000/v1/opportunities/dashboard")
    print("  3. 启动前端: npm run dev")
    print("  4. 访问页面: http://localhost:5173/energy/center")


if __name__ == "__main__":
    asyncio.run(main())
