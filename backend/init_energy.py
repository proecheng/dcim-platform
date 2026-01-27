"""
能源数据初始化脚本 - 初始化配电系统相关数据
包括变压器、计量点、配电柜、回路、用电设备、需量数据
"""
import asyncio
import random
from datetime import datetime, timedelta
from app.core.database import async_session, init_db
from app.models.energy import (
    Transformer, MeterPoint, DistributionPanel, DistributionCircuit,
    PowerDevice, EnergyHourly, EnergyDaily, PUEHistory,
    ElectricityPricing, Demand15MinData
)


# 变压器配置
TRANSFORMERS = [
    {
        "transformer_code": "TR-001",
        "transformer_name": "1#变压器",
        "rated_capacity": 1000,
        "voltage_high": 10.0,
        "voltage_low": 0.4,
        "efficiency": 98.5,
        "location": "配电室A",
        "status": "running"
    },
    {
        "transformer_code": "TR-002",
        "transformer_name": "2#变压器",
        "rated_capacity": 800,
        "voltage_high": 10.0,
        "voltage_low": 0.4,
        "efficiency": 98.0,
        "location": "配电室B",
        "status": "running"
    }
]

# 计量点配置
METER_POINTS = [
    {
        "meter_code": "M001",
        "meter_name": "总进线计量点",
        "meter_no": "DZ001234567",
        "transformer_code": "TR-001",
        "declared_demand": 800,
        "demand_type": "kW",
        "customer_no": "GD20240001",
        "customer_name": "数据中心总表"
    },
    {
        "meter_code": "M002",
        "meter_name": "IT负载计量点",
        "meter_no": "DZ001234568",
        "transformer_code": "TR-001",
        "declared_demand": 500,
        "demand_type": "kW",
        "customer_no": "GD20240002",
        "customer_name": "IT设备分表"
    },
    {
        "meter_code": "M003",
        "meter_name": "制冷系统计量点",
        "meter_no": "DZ001234569",
        "transformer_code": "TR-002",
        "declared_demand": 300,
        "demand_type": "kW",
        "customer_no": "GD20240003",
        "customer_name": "空调系统分表"
    }
]

# 配电柜配置
DISTRIBUTION_PANELS = [
    {"panel_code": "MDP-001", "panel_name": "主配电柜", "panel_type": "main", "rated_current": 2000, "location": "配电室A", "area_code": "A1"},
    {"panel_code": "ATS-001", "panel_name": "ATS切换柜", "panel_type": "sub", "rated_current": 1600, "location": "配电室A", "area_code": "A1", "parent_code": "MDP-001"},
    {"panel_code": "UPS-IN-001", "panel_name": "UPS输入柜", "panel_type": "ups_input", "rated_current": 800, "location": "UPS室", "area_code": "A1", "parent_code": "ATS-001"},
    {"panel_code": "UPS-OUT-001", "panel_name": "UPS输出柜", "panel_type": "ups_output", "rated_current": 600, "location": "UPS室", "area_code": "A1"},
    {"panel_code": "PDU-A1-001", "panel_name": "A1区列头柜1", "panel_type": "sub", "rated_current": 250, "location": "机房A1区", "area_code": "A1", "parent_code": "UPS-OUT-001"},
    {"panel_code": "PDU-A1-002", "panel_name": "A1区列头柜2", "panel_type": "sub", "rated_current": 250, "location": "机房A1区", "area_code": "A1", "parent_code": "UPS-OUT-001"},
    {"panel_code": "AC-PANEL-001", "panel_name": "空调配电柜", "panel_type": "sub", "rated_current": 400, "location": "配电室B", "area_code": "B1", "parent_code": "MDP-001"},
]

# 配电回路配置
DISTRIBUTION_CIRCUITS = [
    {"circuit_code": "C-A1-01", "circuit_name": "A1机柜列1回路", "panel_code": "PDU-A1-001", "load_type": "IT", "rated_current": 63, "is_shiftable": False},
    {"circuit_code": "C-A1-02", "circuit_name": "A1机柜列2回路", "panel_code": "PDU-A1-001", "load_type": "IT", "rated_current": 63, "is_shiftable": False},
    {"circuit_code": "C-A1-03", "circuit_name": "A1机柜列3回路", "panel_code": "PDU-A1-002", "load_type": "IT", "rated_current": 63, "is_shiftable": False},
    {"circuit_code": "C-AC-01", "circuit_name": "精密空调1回路", "panel_code": "AC-PANEL-001", "load_type": "AC", "rated_current": 100, "is_shiftable": True, "shift_priority": 1},
    {"circuit_code": "C-AC-02", "circuit_name": "精密空调2回路", "panel_code": "AC-PANEL-001", "load_type": "AC", "rated_current": 100, "is_shiftable": True, "shift_priority": 2},
    {"circuit_code": "C-LIGHT", "circuit_name": "照明回路", "panel_code": "MDP-001", "load_type": "LIGHT", "rated_current": 32, "is_shiftable": True, "shift_priority": 3},
]

# 用电设备配置
POWER_DEVICES = [
    # IT设备
    {"device_code": "SRV-001", "device_name": "服务器机柜1", "device_type": "IT", "rated_power": 20, "is_it_load": True, "area_code": "A1", "circuit_code": "C-A1-01"},
    {"device_code": "SRV-002", "device_name": "服务器机柜2", "device_type": "IT", "rated_power": 20, "is_it_load": True, "area_code": "A1", "circuit_code": "C-A1-01"},
    {"device_code": "SRV-003", "device_name": "服务器机柜3", "device_type": "IT", "rated_power": 25, "is_it_load": True, "area_code": "A1", "circuit_code": "C-A1-02"},
    {"device_code": "SRV-004", "device_name": "服务器机柜4", "device_type": "IT", "rated_power": 25, "is_it_load": True, "area_code": "A1", "circuit_code": "C-A1-02"},
    {"device_code": "NET-001", "device_name": "网络机柜1", "device_type": "IT", "rated_power": 10, "is_it_load": True, "area_code": "A1", "circuit_code": "C-A1-03"},
    {"device_code": "STO-001", "device_name": "存储机柜1", "device_type": "IT", "rated_power": 30, "is_it_load": True, "area_code": "A1", "circuit_code": "C-A1-03"},
    # UPS
    {"device_code": "UPS-001", "device_name": "UPS主机1", "device_type": "UPS", "rated_power": 200, "is_it_load": False, "area_code": "A1"},
    {"device_code": "UPS-002", "device_name": "UPS主机2", "device_type": "UPS", "rated_power": 200, "is_it_load": False, "area_code": "A1"},
    # 空调
    {"device_code": "AC-001", "device_name": "精密空调1", "device_type": "AC", "rated_power": 50, "is_it_load": False, "area_code": "B1", "circuit_code": "C-AC-01"},
    {"device_code": "AC-002", "device_name": "精密空调2", "device_type": "AC", "rated_power": 50, "is_it_load": False, "area_code": "B1", "circuit_code": "C-AC-02"},
    {"device_code": "AC-003", "device_name": "精密空调3", "device_type": "AC", "rated_power": 45, "is_it_load": False, "area_code": "B1", "circuit_code": "C-AC-02"},
    # 照明
    {"device_code": "LIGHT-001", "device_name": "机房照明", "device_type": "LIGHT", "rated_power": 5, "is_it_load": False, "area_code": "A1", "circuit_code": "C-LIGHT"},
]

# 电价配置
ELECTRICITY_PRICING = [
    {"pricing_name": "峰时电价", "period_type": "peak", "start_time": "08:00", "end_time": "11:00", "price": 1.2},
    {"pricing_name": "峰时电价", "period_type": "peak", "start_time": "18:00", "end_time": "21:00", "price": 1.2},
    {"pricing_name": "平时电价", "period_type": "normal", "start_time": "07:00", "end_time": "08:00", "price": 0.8},
    {"pricing_name": "平时电价", "period_type": "normal", "start_time": "11:00", "end_time": "18:00", "price": 0.8},
    {"pricing_name": "平时电价", "period_type": "normal", "start_time": "21:00", "end_time": "23:00", "price": 0.8},
    {"pricing_name": "谷时电价", "period_type": "valley", "start_time": "23:00", "end_time": "07:00", "price": 0.4},
]


async def init_energy_data():
    """初始化能源数据"""
    await init_db()

    async with async_session() as session:
        from sqlalchemy import select, func

        # 检查是否已初始化
        result = await session.execute(select(func.count(Transformer.id)))
        count = result.scalar()

        if count > 0:
            print(f"数据库已存在 {count} 个变压器，跳过能源数据初始化")
            return

        print("开始初始化能源数据...")

        # 1. 创建变压器
        transformer_map = {}
        for t in TRANSFORMERS:
            transformer = Transformer(**t)
            session.add(transformer)
            await session.flush()
            transformer_map[t["transformer_code"]] = transformer.id
        print(f"  创建 {len(TRANSFORMERS)} 个变压器")

        # 2. 创建计量点
        meter_point_map = {}
        for mp in METER_POINTS:
            data = mp.copy()
            transformer_code = data.pop("transformer_code")
            data["transformer_id"] = transformer_map.get(transformer_code)
            meter_point = MeterPoint(**data)
            session.add(meter_point)
            await session.flush()
            meter_point_map[mp["meter_code"]] = meter_point.id
        print(f"  创建 {len(METER_POINTS)} 个计量点")

        # 3. 创建配电柜
        panel_map = {}
        for p in DISTRIBUTION_PANELS:
            data = p.copy()
            parent_code = data.pop("parent_code", None)
            if parent_code and parent_code in panel_map:
                data["parent_panel_id"] = panel_map[parent_code]
            panel = DistributionPanel(**data)
            session.add(panel)
            await session.flush()
            panel_map[p["panel_code"]] = panel.id
        print(f"  创建 {len(DISTRIBUTION_PANELS)} 个配电柜")

        # 4. 创建配电回路
        circuit_map = {}
        for c in DISTRIBUTION_CIRCUITS:
            data = c.copy()
            panel_code = data.pop("panel_code")
            data["panel_id"] = panel_map.get(panel_code)
            circuit = DistributionCircuit(**data)
            session.add(circuit)
            await session.flush()
            circuit_map[c["circuit_code"]] = circuit.id
        print(f"  创建 {len(DISTRIBUTION_CIRCUITS)} 个配电回路")

        # 5. 创建用电设备
        for d in POWER_DEVICES:
            data = d.copy()
            circuit_code = data.pop("circuit_code", None)
            if circuit_code and circuit_code in circuit_map:
                data["circuit_id"] = circuit_map[circuit_code]
            device = PowerDevice(**data)
            session.add(device)
        await session.flush()
        print(f"  创建 {len(POWER_DEVICES)} 个用电设备")

        # 6. 创建电价配置
        for ep in ELECTRICITY_PRICING:
            pricing = ElectricityPricing(
                **ep,
                effective_date=datetime.now().date()
            )
            session.add(pricing)
        print(f"  创建 {len(ELECTRICITY_PRICING)} 条电价配置")

        # 7. 生成15分钟需量数据 (最近7天)
        await generate_demand_15min_data(session, meter_point_map)

        # 8. 生成小时能耗数据 (最近30天)
        await generate_hourly_energy_data(session)

        # 9. 生成日能耗数据 (最近30天)
        await generate_daily_energy_data(session)

        # 10. 生成PUE历史数据 (最近30天)
        await generate_pue_history(session)

        await session.commit()
        print("\n能源数据初始化完成!")


async def generate_demand_15min_data(session, meter_point_map):
    """生成15分钟需量数据"""
    print("  生成15分钟需量数据...")

    # 检查是否有 Demand15MinData 模型
    try:
        from app.models.energy import Demand15MinData
    except ImportError:
        print("    Demand15MinData 模型不存在，跳过")
        return

    now = datetime.now()
    records = []

    for meter_code, meter_point_id in meter_point_map.items():
        # 获取申报需量
        declared_demand = 800 if meter_code == "M001" else 500 if meter_code == "M002" else 300

        # 生成7天数据
        for day_offset in range(7):
            date = now - timedelta(days=day_offset)

            # 每15分钟一个数据点
            for hour in range(24):
                for minute in [0, 15, 30, 45]:
                    timestamp = date.replace(hour=hour, minute=minute, second=0, microsecond=0)

                    # 模拟需量波动：工作时间高，夜间低
                    base_ratio = 0.7 if 8 <= hour <= 18 else 0.4
                    fluctuation = random.uniform(-0.1, 0.1)
                    demand = declared_demand * (base_ratio + fluctuation)

                    # 偶尔超过申报需量
                    is_over = random.random() < 0.05
                    if is_over:
                        demand = declared_demand * random.uniform(1.0, 1.15)

                    # 判断时段
                    if 8 <= hour < 11 or 18 <= hour < 21:
                        time_period = "peak"
                        is_peak = True
                    elif 23 <= hour or hour < 7:
                        time_period = "valley"
                        is_peak = False
                    else:
                        time_period = "flat"
                        is_peak = False

                    record = Demand15MinData(
                        meter_point_id=meter_point_id,
                        timestamp=timestamp,
                        average_power=round(demand, 2),
                        max_power=round(demand * random.uniform(1.0, 1.1), 2),
                        min_power=round(demand * random.uniform(0.9, 1.0), 2),
                        rolling_demand=round(demand, 2),
                        declared_demand=declared_demand,
                        demand_ratio=round(demand / declared_demand * 100, 2),
                        is_peak_period=is_peak,
                        time_period=time_period,
                        is_over_declared=is_over
                    )
                    records.append(record)

    session.add_all(records)
    print(f"    生成 {len(records)} 条15分钟需量数据")


async def generate_hourly_energy_data(session):
    """生成小时能耗数据"""
    print("  生成小时能耗数据...")

    from sqlalchemy import select
    result = await session.execute(select(PowerDevice))
    devices = result.scalars().all()

    if not devices:
        print("    没有用电设备，跳过")
        return

    now = datetime.now()
    records = []

    for device in devices[:5]:  # 只为前5个设备生成数据
        for day_offset in range(7):  # 7天
            for hour in range(24):
                timestamp = (now - timedelta(days=day_offset)).replace(hour=hour, minute=0, second=0, microsecond=0)

                # 基于设备额定功率生成数据
                rated_power = device.rated_power or 20
                load_ratio = random.uniform(0.5, 0.9)
                power = rated_power * load_ratio

                record = EnergyHourly(
                    device_id=device.id,
                    stat_time=timestamp,
                    total_energy=round(power, 2),
                    max_power=round(power * 1.1, 2),
                    avg_power=round(power, 2),
                    min_power=round(power * 0.9, 2)
                )
                records.append(record)

    session.add_all(records)
    print(f"    生成 {len(records)} 条小时能耗数据")


async def generate_daily_energy_data(session):
    """生成日能耗数据"""
    print("  生成日能耗数据...")

    from sqlalchemy import select
    result = await session.execute(select(PowerDevice))
    devices = result.scalars().all()

    if not devices:
        print("    没有用电设备，跳过")
        return

    now = datetime.now()
    records = []

    for device in devices:
        for day_offset in range(30):  # 30天
            stat_date = (now - timedelta(days=day_offset)).date()

            rated_power = device.rated_power or 20
            daily_energy = rated_power * 24 * random.uniform(0.5, 0.8)

            record = EnergyDaily(
                device_id=device.id,
                stat_date=stat_date,
                total_energy=round(daily_energy, 2),
                peak_energy=round(daily_energy * 0.35, 2),
                normal_energy=round(daily_energy * 0.45, 2),
                valley_energy=round(daily_energy * 0.2, 2),
                max_power=round(rated_power * 0.95, 2),
                avg_power=round(rated_power * 0.7, 2),
                energy_cost=round(daily_energy * 0.8, 2)
            )
            records.append(record)

    session.add_all(records)
    print(f"    生成 {len(records)} 条日能耗数据")


async def generate_pue_history(session):
    """生成PUE历史数据"""
    print("  生成PUE历史数据...")

    now = datetime.now()
    records = []

    for day_offset in range(30):
        for hour in range(24):
            timestamp = (now - timedelta(days=day_offset)).replace(hour=hour, minute=0, second=0, microsecond=0)

            # 模拟PUE波动 (1.4-1.8之间)
            base_pue = 1.6
            fluctuation = random.uniform(-0.15, 0.15)
            pue = base_pue + fluctuation

            # 计算各项功率
            total_power = random.uniform(400, 600)
            it_power = total_power / pue
            cooling_power = total_power - it_power - random.uniform(10, 30)

            record = PUEHistory(
                record_time=timestamp,
                pue=round(pue, 3),
                total_power=round(total_power, 2),
                it_power=round(it_power, 2),
                cooling_power=round(cooling_power, 2),
                ups_loss=round(total_power * 0.03, 2),
                lighting_power=round(random.uniform(3, 8), 2),
                other_power=round(random.uniform(5, 15), 2)
            )
            records.append(record)

    session.add_all(records)
    print(f"    生成 {len(records)} 条PUE历史数据")


async def main():
    """主初始化流程"""
    # 1. 初始化能源数据
    await init_energy_data()

    # 2. 初始化设备调节配置
    print("\n" + "=" * 60)
    print("开始初始化设备调节能力配置...")
    print("=" * 60)

    try:
        # 导入设备调节配置初始化模块
        import sys
        from pathlib import Path

        # 将当前目录添加到Python路径
        sys.path.insert(0, str(Path(__file__).parent))

        from init_device_regulation import init_device_regulation_configs
        # 在从 init_energy.py 调用时，使用非交互模式
        await init_device_regulation_configs(force=False, interactive=False)

        print("\n所有初始化任务完成!")
    except Exception as e:
        print(f"\n[警告] 设备调节配置初始化失败: {e}")
        print("您可以稍后手动运行: python init_device_regulation.py")


if __name__ == "__main__":
    asyncio.run(main())
