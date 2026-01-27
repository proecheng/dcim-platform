"""
VPP Test Data Initialization Script
虚拟电厂测试数据初始化脚本

This script populates the VPP database with realistic test data based on the
Virtual Power Plant solution document (虚拟电厂方案1_内容.txt).

Data sources:
- Electricity bills from document Table 2-1 (page 9, lines 281-286)
- Electricity prices (peak/valley/flat pricing)
- Adjustable loads (steel wire factory equipment)
- VPP configuration parameters
- 30 days of load curve data (15-min intervals, 96 points/day)
"""
from datetime import date, time, datetime, timedelta
import random
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete

from app.models.vpp_data import (
    ElectricityBill,
    LoadCurve,
    ElectricityPrice,
    AdjustableLoad,
    VPPConfig,
    TimePeriodType
)


async def clear_vpp_data(db: AsyncSession) -> None:
    """
    Clear all VPP data from database
    清除所有VPP数据
    """
    print("Clearing VPP data...")

    try:
        # Delete in order to respect potential foreign key constraints
        await db.execute(delete(LoadCurve))
        await db.execute(delete(ElectricityBill))
        await db.execute(delete(ElectricityPrice))
        await db.execute(delete(AdjustableLoad))
        await db.execute(delete(VPPConfig))

        await db.commit()
        print("VPP data cleared successfully!")
    except Exception as e:
        print(f"Note: Could not clear data (tables may not exist yet): {e}")
        await db.rollback()


async def init_vpp_test_data(db: AsyncSession) -> None:
    """
    Initialize VPP test data with realistic values from the solution document
    使用方案文档中的真实数据初始化VPP测试数据

    Args:
        db: Async database session
    """
    print("Initializing VPP test data...")

    # Clear existing data first
    await clear_vpp_data(db)

    # ==================== 1. Electricity Bills (电费清单) ====================
    # Data from document Table 2-1 (page 9, lines 281-286)
    # 月份 | 用电量(万kWh) | 电费(万元) | 平均电价(元/kWh)
    # 1月  | 2097         | 1423      | 0.678
    # 3月  | 2485         | 1717      | 0.691
    # 6月  | 2601         | 1813      | 0.697
    # 8月  | 2807         | 1971      | 0.702
    # 10月 | 2724         | 1843      | 0.677

    print("  - Inserting electricity bills...")

    bills_data = [
        {
            "month": "2025-01",
            "total_consumption": 20970000,  # 2097万kWh
            "total_cost": 14230000,          # 1423万元
            "peak_consumption": 6291000,     # 约30%峰段
            "valley_consumption": 6291000,   # 约30%谷段
            "flat_consumption": 8388000,     # 约40%平段
            "max_demand": 39900,             # 39.9 MW
            "power_factor": 0.94,
            "basic_fee": 1200000,
            "market_purchase_fee": 9800000,   # 约69%市场化购电
            "transmission_fee": 3100000,      # 约22%输配电费
            "system_operation_fee": 500000,   # 约3.5%系统运行费
            "government_fund": 430000         # 约3%政府性基金
        },
        {
            "month": "2025-03",
            "total_consumption": 24850000,  # 2485万kWh
            "total_cost": 17170000,          # 1717万元
            "peak_consumption": 7455000,
            "valley_consumption": 7455000,
            "flat_consumption": 9940000,
            "max_demand": 42000,             # 42.0 MW
            "power_factor": 0.95,
            "basic_fee": 1200000,
            "market_purchase_fee": 11800000,
            "transmission_fee": 3700000,
            "system_operation_fee": 600000,
            "government_fund": 520000
        },
        {
            "month": "2025-06",
            "total_consumption": 26010000,  # 2601万kWh
            "total_cost": 18130000,          # 1813万元
            "peak_consumption": 7803000,
            "valley_consumption": 7803000,
            "flat_consumption": 10404000,
            "max_demand": 41500,             # 41.5 MW
            "power_factor": 0.94,
            "basic_fee": 1200000,
            "market_purchase_fee": 12500000,
            "transmission_fee": 3900000,
            "system_operation_fee": 620000,
            "government_fund": 550000
        },
        {
            "month": "2025-08",
            "total_consumption": 28070000,  # 2807万kWh (highest)
            "total_cost": 19710000,          # 1971万元 (highest)
            "peak_consumption": 8421000,
            "valley_consumption": 8421000,
            "flat_consumption": 11228000,
            "max_demand": 42500,             # 42.5 MW
            "power_factor": 0.95,
            "basic_fee": 1200000,
            "market_purchase_fee": 13700000,
            "transmission_fee": 4200000,
            "system_operation_fee": 680000,
            "government_fund": 600000
        },
        {
            "month": "2025-10",
            "total_consumption": 27240000,  # 2724万kWh
            "total_cost": 18430000,          # 1843万元
            "peak_consumption": 8172000,
            "valley_consumption": 8172000,
            "flat_consumption": 10896000,
            "max_demand": 41800,             # 41.8 MW
            "power_factor": 0.94,
            "basic_fee": 1200000,
            "market_purchase_fee": 12800000,
            "transmission_fee": 3950000,
            "system_operation_fee": 650000,
            "government_fund": 580000
        }
    ]

    for bill_data in bills_data:
        bill = ElectricityBill(**bill_data)
        db.add(bill)

    # ==================== 2. Electricity Prices (电价配置) ====================
    # Peak/valley/flat pricing structure
    # Peak: 0.85 元/kWh (8:00-11:00, 18:00-21:00)
    # Valley: 0.35 元/kWh (23:00-7:00)
    # Flat: 0.55 元/kWh (other times)

    print("  - Inserting electricity prices...")

    prices_data = [
        # Peak period 1: 8:00-11:00
        {
            "period_type": TimePeriodType.PEAK,
            "price": 0.85,
            "start_time": time(8, 0),
            "end_time": time(11, 0),
            "effective_date": date(2025, 1, 1)
        },
        # Peak period 2: 18:00-21:00
        {
            "period_type": TimePeriodType.PEAK,
            "price": 0.85,
            "start_time": time(18, 0),
            "end_time": time(21, 0),
            "effective_date": date(2025, 1, 1)
        },
        # Valley period: 23:00-7:00 (overnight)
        {
            "period_type": TimePeriodType.VALLEY,
            "price": 0.35,
            "start_time": time(23, 0),
            "end_time": time(7, 0),
            "effective_date": date(2025, 1, 1)
        },
        # Flat period 1: 7:00-8:00
        {
            "period_type": TimePeriodType.FLAT,
            "price": 0.55,
            "start_time": time(7, 0),
            "end_time": time(8, 0),
            "effective_date": date(2025, 1, 1)
        },
        # Flat period 2: 11:00-18:00
        {
            "period_type": TimePeriodType.FLAT,
            "price": 0.55,
            "start_time": time(11, 0),
            "end_time": time(18, 0),
            "effective_date": date(2025, 1, 1)
        },
        # Flat period 3: 21:00-23:00
        {
            "period_type": TimePeriodType.FLAT,
            "price": 0.55,
            "start_time": time(21, 0),
            "end_time": time(23, 0),
            "effective_date": date(2025, 1, 1)
        }
    ]

    for price_data in prices_data:
        price = ElectricityPrice(**price_data)
        db.add(price)

    # ==================== 3. Adjustable Loads (可调节负荷资源) ====================
    # Typical equipment for steel wire factory (钢帘线企业)

    print("  - Inserting adjustable loads...")

    loads_data = [
        {
            "equipment_name": "拉丝机组A",
            "equipment_type": "生产设备",
            "rated_power": 2000,      # 2000 kW
            "adjustable_ratio": 30,    # 30% adjustable
            "response_time": 15,       # 15 minutes
            "adjustment_cost": 500,
            "is_active": True
        },
        {
            "equipment_name": "拉丝机组B",
            "equipment_type": "生产设备",
            "rated_power": 2000,
            "adjustable_ratio": 30,
            "response_time": 15,
            "adjustment_cost": 500,
            "is_active": True
        },
        {
            "equipment_name": "热处理炉",
            "equipment_type": "热处理设备",
            "rated_power": 5000,       # 5000 kW
            "adjustable_ratio": 20,    # 20% adjustable
            "response_time": 30,       # 30 minutes
            "adjustment_cost": 1000,
            "is_active": True
        },
        {
            "equipment_name": "中央空调系统",
            "equipment_type": "辅助设备",
            "rated_power": 3000,
            "adjustable_ratio": 50,    # 50% adjustable
            "response_time": 5,        # 5 minutes (fast response)
            "adjustment_cost": 100,
            "is_active": True
        },
        {
            "equipment_name": "压缩空气系统",
            "equipment_type": "辅助设备",
            "rated_power": 1500,
            "adjustable_ratio": 40,    # 40% adjustable
            "response_time": 10,
            "adjustment_cost": 200,
            "is_active": True
        },
        {
            "equipment_name": "水泵系统",
            "equipment_type": "辅助设备",
            "rated_power": 800,
            "adjustable_ratio": 30,
            "response_time": 5,
            "adjustment_cost": 50,
            "is_active": True
        },
        {
            "equipment_name": "照明系统",
            "equipment_type": "照明",
            "rated_power": 500,
            "adjustable_ratio": 60,    # 60% adjustable
            "response_time": 1,        # 1 minute (instant)
            "adjustment_cost": 20,
            "is_active": True
        },
        {
            "equipment_name": "镀锌生产线",
            "equipment_type": "生产设备",
            "rated_power": 1800,
            "adjustable_ratio": 25,
            "response_time": 20,
            "adjustment_cost": 400,
            "is_active": True
        }
    ]

    for load_data in loads_data:
        load = AdjustableLoad(**load_data)
        db.add(load)

    # Total adjustable capacity calculation:
    # (2000*0.3 + 2000*0.3 + 5000*0.2 + 3000*0.5 + 1500*0.4 + 800*0.3 + 500*0.6 + 1800*0.25)
    # = 600 + 600 + 1000 + 1500 + 600 + 240 + 300 + 450 = 5,290 kW

    # ==================== 4. VPP Configuration Parameters (VPP配置参数) ====================

    print("  - Inserting VPP config parameters...")

    configs_data = [
        # Peak-valley transfer parameters
        {
            "config_key": "daily_shift_hours",
            "config_value": 4.0,
            "config_unit": "小时",
            "description": "每日峰谷转移小时数"
        },

        # Demand optimization parameters
        {
            "config_key": "target_demand_ratio",
            "config_value": 0.9,
            "config_unit": "-",
            "description": "目标需量比例(削减10%)"
        },
        {
            "config_key": "demand_price",
            "config_value": 40.0,
            "config_unit": "元/kW/月",
            "description": "需量电价"
        },

        # Demand response parameters
        {
            "config_key": "response_count",
            "config_value": 20.0,
            "config_unit": "次/年",
            "description": "年需求响应次数"
        },
        {
            "config_key": "response_price",
            "config_value": 4.0,
            "config_unit": "元/kW",
            "description": "需求响应补贴单价"
        },

        # Ancillary service parameters
        {
            "config_key": "service_hours",
            "config_value": 200.0,
            "config_unit": "小时/年",
            "description": "辅助服务年小时数"
        },
        {
            "config_key": "service_price",
            "config_value": 0.75,
            "config_unit": "元/kW·h",
            "description": "辅助服务价格"
        },

        # Spot market parameters
        {
            "config_key": "arbitrage_hours",
            "config_value": 500.0,
            "config_unit": "小时/年",
            "description": "现货套利年小时数"
        },
        {
            "config_key": "price_spread_spot",
            "config_value": 0.3,
            "config_unit": "元/kWh",
            "description": "现货市场价差"
        },

        # Investment cost parameters
        {
            "config_key": "monitoring_system_cost",
            "config_value": 500000.0,
            "config_unit": "元",
            "description": "监测系统投资"
        },
        {
            "config_key": "control_system_cost",
            "config_value": 800000.0,
            "config_unit": "元",
            "description": "控制系统投资"
        },
        {
            "config_key": "platform_cost",
            "config_value": 200000.0,
            "config_unit": "元",
            "description": "平台建设投资"
        },
        {
            "config_key": "other_cost",
            "config_value": 100000.0,
            "config_unit": "元",
            "description": "其他投资"
        }
    ]

    for config_data in configs_data:
        config = VPPConfig(**config_data)
        db.add(config)

    # ==================== 5. Load Curve Data (负荷曲线数据) ====================
    # Generate 30 days of load curve data with 15-minute intervals (96 points/day)
    # Base load: 35,000 kW (35 MW)
    # Workday vs non-workday patterns
    # Peak/valley/flat time period variations

    print("  - Generating 30 days of load curve data (96 points/day)...")

    BASE_LOAD = 35000  # 35 MW base load
    START_DATE = date(2025, 10, 1)
    DAYS_TO_GENERATE = 30

    def get_time_period(hour: int) -> TimePeriodType:
        """Determine time period type based on hour"""
        if 8 <= hour < 11 or 18 <= hour < 21:
            return TimePeriodType.PEAK
        elif hour >= 23 or hour < 7:
            return TimePeriodType.VALLEY
        else:
            return TimePeriodType.FLAT

    def get_load_factor(hour: int, is_workday: bool) -> float:
        """Get load factor based on time period and workday status"""
        period = get_time_period(hour)

        if period == TimePeriodType.PEAK:
            # Peak hours: higher load, especially on workdays
            return 1.15 if is_workday else 1.05
        elif period == TimePeriodType.VALLEY:
            # Valley hours: lower load
            return 0.85
        else:
            # Flat hours: normal load
            return 1.0

    # Set random seed for reproducible results
    random.seed(42)

    load_curves_batch = []

    for day_offset in range(DAYS_TO_GENERATE):
        current_date = START_DATE + timedelta(days=day_offset)
        is_workday = current_date.weekday() < 5  # Monday=0, Sunday=6

        for hour in range(24):
            for minute in [0, 15, 30, 45]:
                timestamp = datetime(
                    current_date.year,
                    current_date.month,
                    current_date.day,
                    hour,
                    minute,
                    0
                )

                # Get time period
                period_type = get_time_period(hour)

                # Calculate load value
                load_factor = get_load_factor(hour, is_workday)

                # Add random variation ±5%
                variation = random.uniform(-0.05, 0.05)

                # Calculate final load value
                load_value = BASE_LOAD * load_factor * (1 + variation)

                # Workdays have overall higher load (10% increase)
                if is_workday:
                    load_value *= 1.1

                # Add some hourly patterns for realism
                # Morning ramp-up (6:00-8:00)
                if 6 <= hour < 8:
                    ramp_factor = (hour - 6) / 2  # 0 to 1
                    load_value *= (0.9 + 0.1 * ramp_factor)

                # Lunch dip (12:00-13:00) on workdays
                if is_workday and 12 <= hour < 13:
                    load_value *= 0.95

                # Evening ramp-down (21:00-23:00)
                if 21 <= hour < 23:
                    ramp_factor = (hour - 21) / 2  # 0 to 1
                    load_value *= (1.0 - 0.05 * ramp_factor)

                curve = LoadCurve(
                    timestamp=timestamp,
                    load_value=round(load_value, 2),
                    date=current_date,
                    time_period=period_type,
                    is_workday=is_workday
                )
                load_curves_batch.append(curve)

    # Bulk insert for better performance
    db.add_all(load_curves_batch)

    # Commit all data
    await db.commit()

    # Print summary
    print("\n" + "="*60)
    print("VPP Test Data Initialization Complete!")
    print("="*60)
    print(f"  [OK] Electricity Bills: {len(bills_data)} months")
    print(f"  [OK] Electricity Prices: {len(prices_data)} periods")
    print(f"  [OK] Adjustable Loads: {len(loads_data)} equipment")
    print(f"  [OK] VPP Configs: {len(configs_data)} parameters")
    print(f"  [OK] Load Curves: {len(load_curves_batch)} data points ({DAYS_TO_GENERATE} days x 96 points/day)")
    print(f"\nTotal Adjustable Capacity: ~5,290 kW")
    print(f"Base Load: {BASE_LOAD:,} kW (35 MW)")
    print(f"Load Curve Period: {START_DATE} to {START_DATE + timedelta(days=DAYS_TO_GENERATE-1)}")
    print("="*60 + "\n")


# Standalone execution for testing
if __name__ == "__main__":
    import asyncio
    from app.core.database import AsyncSessionLocal

    async def main():
        async with AsyncSessionLocal() as db:
            await init_vpp_test_data(db)

    asyncio.run(main())
