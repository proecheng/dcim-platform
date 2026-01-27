"""
展示数据生成器 - 典型中小型算力中心
Demo Data Generator for Typical Small-Medium Data Center

功能：
1. 生成配电拓扑数据（变压器、计量点、配电柜、回路、设备）
2. 生成历史能耗数据（小时/日/月）
3. 生成15分钟需量数据
4. 生成节能建议
5. 生成告警数据

典型配置：
- 总容量：500kVA (1台变压器)
- IT负荷：约300kW (服务器、存储、网络)
- 制冷负荷：约100kW (精密空调)
- UPS容量：400kVA
- 目标PUE：1.5-1.8
"""

import asyncio
import random
from datetime import datetime, timedelta, date
from typing import List, Dict, Any
import math

# 典型中小型算力中心配置
DATACENTER_CONFIG = {
    "name": "智算中心机房",
    "total_capacity_kva": 500,
    "transformer": {
        "code": "TR-001",
        "name": "1#变压器",
        "capacity": 500,
        "voltage_high": 10.0,
        "voltage_low": 0.4,
    },
    "meter_point": {
        "code": "M001",
        "name": "总计量点",
        "declared_demand": 400,  # 申报需量 kW
    },
    # 配电柜配置
    "panels": [
        {"code": "ATS-001", "name": "ATS自动切换柜", "type": "main", "current": 800},
        {"code": "UPS-IN-001", "name": "UPS输入柜", "type": "ups_input", "current": 630},
        {"code": "UPS-OUT-001", "name": "UPS输出柜", "type": "ups_output", "current": 630},
        {"code": "PDU-A01", "name": "列头柜A1", "type": "sub", "current": 250},
        {"code": "PDU-A02", "name": "列头柜A2", "type": "sub", "current": 250},
        {"code": "PDU-B01", "name": "列头柜B1", "type": "sub", "current": 250},
        {"code": "AC-001", "name": "空调配电柜", "type": "sub", "current": 400},
        {"code": "LT-001", "name": "照明配电柜", "type": "sub", "current": 100},
    ],
    # 用电设备配置
    "devices": [
        # IT设备 - 服务器
        {"code": "SRV-A01-01", "name": "A1机柜服务器组", "type": "IT_SERVER", "power": 25, "is_it": True, "circuit": "PDU-A01"},
        {"code": "SRV-A01-02", "name": "A1机柜GPU服务器", "type": "IT_SERVER", "power": 40, "is_it": True, "circuit": "PDU-A01"},
        {"code": "SRV-A02-01", "name": "A2机柜服务器组", "type": "IT_SERVER", "power": 30, "is_it": True, "circuit": "PDU-A02"},
        {"code": "SRV-A02-02", "name": "A2机柜存储阵列", "type": "IT_STORAGE", "power": 15, "is_it": True, "circuit": "PDU-A02"},
        {"code": "SRV-B01-01", "name": "B1机柜服务器组", "type": "IT_SERVER", "power": 35, "is_it": True, "circuit": "PDU-B01"},
        {"code": "SRV-B01-02", "name": "B1机柜网络设备", "type": "IT_SERVER", "power": 8, "is_it": True, "circuit": "PDU-B01"},
        {"code": "SRV-B01-03", "name": "B1机柜AI训练服务器", "type": "IT_SERVER", "power": 60, "is_it": True, "circuit": "PDU-B01"},
        {"code": "STG-001", "name": "集中存储系统", "type": "IT_STORAGE", "power": 20, "is_it": True, "circuit": "PDU-A01"},
        {"code": "NET-001", "name": "核心网络交换机", "type": "IT_SERVER", "power": 5, "is_it": True, "circuit": "PDU-A02"},
        {"code": "NET-002", "name": "汇聚交换机组", "type": "IT_SERVER", "power": 3, "is_it": True, "circuit": "PDU-B01"},
        # UPS
        {"code": "UPS-001", "name": "1#UPS(400kVA)", "type": "UPS", "power": 40, "is_it": False, "circuit": "UPS-IN-001"},
        # 空调设备
        {"code": "CRAC-001", "name": "1#精密空调", "type": "HVAC", "power": 30, "is_it": False, "circuit": "AC-001", "adjustable": True},
        {"code": "CRAC-002", "name": "2#精密空调", "type": "HVAC", "power": 30, "is_it": False, "circuit": "AC-001", "adjustable": True},
        {"code": "CRAC-003", "name": "3#精密空调", "type": "HVAC", "power": 25, "is_it": False, "circuit": "AC-001", "adjustable": True},
        {"code": "AHU-001", "name": "新风机组", "type": "HVAC", "power": 8, "is_it": False, "circuit": "AC-001"},
        # 照明
        {"code": "LT-MAIN", "name": "主机房照明", "type": "LIGHTING", "power": 5, "is_it": False, "circuit": "LT-001", "adjustable": True},
        {"code": "LT-AUX", "name": "辅助区照明", "type": "LIGHTING", "power": 3, "is_it": False, "circuit": "LT-001", "adjustable": True},
        # 其他
        {"code": "PUMP-001", "name": "冷冻水泵", "type": "PUMP", "power": 15, "is_it": False, "circuit": "AC-001"},
        {"code": "PUMP-002", "name": "冷却水泵", "type": "PUMP", "power": 12, "is_it": False, "circuit": "AC-001"},
    ],
    # 电价配置 (峰谷平)
    "pricing": [
        {"name": "尖峰", "type": "sharp", "start": "10:00", "end": "12:00", "price": 1.2},
        {"name": "尖峰", "type": "sharp", "start": "14:00", "end": "17:00", "price": 1.2},
        {"name": "高峰", "type": "peak", "start": "08:00", "end": "10:00", "price": 1.0},
        {"name": "高峰", "type": "peak", "start": "12:00", "end": "14:00", "price": 1.0},
        {"name": "高峰", "type": "peak", "start": "17:00", "end": "21:00", "price": 1.0},
        {"name": "平段", "type": "flat", "start": "07:00", "end": "08:00", "price": 0.7},
        {"name": "平段", "type": "flat", "start": "21:00", "end": "23:00", "price": 0.7},
        {"name": "低谷", "type": "valley", "start": "23:00", "end": "07:00", "price": 0.4},
    ],
}


def get_time_period(hour: int) -> str:
    """根据小时获取电价时段"""
    if 10 <= hour < 12 or 14 <= hour < 17:
        return "sharp"
    elif 8 <= hour < 10 or 12 <= hour < 14 or 17 <= hour < 21:
        return "peak"
    elif 7 <= hour < 8 or 21 <= hour < 23:
        return "flat"
    else:
        return "valley"


def get_price_by_period(period: str) -> float:
    """根据时段获取电价"""
    prices = {"sharp": 1.2, "peak": 1.0, "flat": 0.7, "valley": 0.4}
    return prices.get(period, 0.7)


def generate_load_curve(hour: int, device_type: str, base_power: float) -> float:
    """
    生成设备负荷曲线
    根据设备类型和时间生成典型负荷
    """
    # IT设备 - 相对稳定，但有日间波动
    if device_type in ["IT_SERVER", "IT_STORAGE"]:
        # 工作时间负载较高
        if 9 <= hour <= 18:
            factor = 0.85 + random.uniform(-0.05, 0.1)
        elif 0 <= hour <= 6:
            factor = 0.6 + random.uniform(-0.05, 0.05)
        else:
            factor = 0.7 + random.uniform(-0.05, 0.08)
        return base_power * factor

    # 空调 - 随温度和IT负载变化
    elif device_type == "HVAC":
        # 白天负载高，夜间低
        if 10 <= hour <= 17:
            factor = 0.9 + random.uniform(-0.05, 0.1)
        elif 0 <= hour <= 6:
            factor = 0.5 + random.uniform(-0.05, 0.1)
        else:
            factor = 0.7 + random.uniform(-0.05, 0.1)
        return base_power * factor

    # 照明 - 工作时间开启
    elif device_type == "LIGHTING":
        if 8 <= hour <= 20:
            factor = 0.9 + random.uniform(-0.1, 0.1)
        else:
            factor = 0.2 + random.uniform(-0.05, 0.1)
        return base_power * factor

    # UPS - 损耗相对稳定
    elif device_type == "UPS":
        factor = 0.8 + random.uniform(-0.05, 0.05)
        return base_power * factor

    # 水泵 - 随空调运行
    elif device_type == "PUMP":
        if 10 <= hour <= 17:
            factor = 0.85 + random.uniform(-0.05, 0.1)
        else:
            factor = 0.6 + random.uniform(-0.05, 0.1)
        return base_power * factor

    # 默认
    else:
        return base_power * (0.7 + random.uniform(-0.1, 0.1))


# 节能建议模板
SUGGESTION_TEMPLATES = [
    {
        "id": "SHIFT_LOAD_PEAK_TO_VALLEY",
        "category": "cost",
        "rule_name": "负荷转移-峰转谷",
        "template": "建议将{device_name}的运行时间从{from_period}({from_hours})转移到{to_period}({to_hours})，预计每月可节省电费{saving}元",
        "priority": "high",
        "difficulty": "medium",
    },
    {
        "id": "REDUCE_HVAC_SETPOINT",
        "category": "efficiency",
        "rule_name": "空调温度优化",
        "template": "建议将{device_name}的设定温度从{current_temp}℃提高到{target_temp}℃，可降低制冷能耗约{saving_percent}%",
        "priority": "medium",
        "difficulty": "easy",
    },
    {
        "id": "REDUCE_LIGHTING_INTENSITY",
        "category": "efficiency",
        "rule_name": "照明亮度优化",
        "template": "建议在{time_period}将{device_name}亮度从{current_level}%降低到{target_level}%，预计节省{saving}kWh/月",
        "priority": "low",
        "difficulty": "easy",
    },
    {
        "id": "DEMAND_OPTIMIZATION",
        "category": "demand",
        "rule_name": "需量优化",
        "template": "当前申报需量{declared}kW，建议调整为{recommended}kW，可节省需量电费{saving}元/月",
        "priority": "high",
        "difficulty": "medium",
    },
    {
        "id": "PUE_IMPROVEMENT",
        "category": "pue",
        "rule_name": "PUE优化",
        "template": "当前PUE为{current_pue}，通过{action}可将PUE降低至{target_pue}，年节省电费约{saving}元",
        "priority": "high",
        "difficulty": "hard",
    },
    {
        "id": "EQUIPMENT_EFFICIENCY",
        "category": "efficiency",
        "rule_name": "设备效率提升",
        "template": "{device_name}当前负载率{load_rate}%，建议{action}以提高运行效率",
        "priority": "medium",
        "difficulty": "medium",
    },
    {
        "id": "PEAK_SHAVING",
        "category": "demand",
        "rule_name": "削峰填谷",
        "template": "在{peak_time}时段，建议降低{device_name}功率{reduce_power}kW，避免超过申报需量",
        "priority": "urgent",
        "difficulty": "medium",
    },
    {
        "id": "IDLE_DEVICE_SHUTDOWN",
        "category": "efficiency",
        "rule_name": "空闲设备关停",
        "template": "{device_name}在{time_period}负载率低于{threshold}%，建议在此时段关闭或降低功率",
        "priority": "medium",
        "difficulty": "easy",
    },
]


class DemoDataGenerator:
    """展示数据生成器"""

    def __init__(self, db_path: str = None):
        import sqlite3
        if db_path is None:
            import os
            db_path = os.path.join(os.path.dirname(__file__), '..', '..', 'dcim.db')
        self.db_path = db_path
        self.conn = None

    def connect(self):
        import sqlite3
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        return self.conn

    def close(self):
        if self.conn:
            self.conn.close()

    # 允许清除的表白名单
    ALLOWED_TABLES = frozenset([
        'energy_suggestions', 'pue_history', 'energy_monthly', 'energy_daily',
        'energy_hourly', 'demand_15min_data', 'power_curve_data',
        'regulation_history', 'load_regulation_configs',
        'device_shift_configs', 'device_load_profiles',
        'power_devices', 'distribution_circuits', 'distribution_panels',
        'meter_points', 'transformers', 'electricity_pricing'
    ])

    def clear_demo_data(self):
        """清除旧的演示数据"""
        cursor = self.conn.cursor()
        # 按依赖顺序删除，使用白名单验证防止SQL注入
        tables = [
            'energy_suggestions', 'pue_history', 'energy_monthly', 'energy_daily',
            'energy_hourly', 'demand_15min_data', 'power_curve_data',
            'regulation_history', 'load_regulation_configs',
            'device_shift_configs', 'device_load_profiles',
            'power_devices', 'distribution_circuits', 'distribution_panels',
            'meter_points', 'transformers', 'electricity_pricing'
        ]
        for table in tables:
            # 白名单验证，防止SQL注入
            if table not in self.ALLOWED_TABLES:
                print(f"警告: 表名 {table} 不在白名单中，跳过")
                continue
            try:
                cursor.execute(f"DELETE FROM [{table}]")
            except Exception as e:
                print(f"清除{table}失败: {e}")
        self.conn.commit()
        print("已清除旧数据")

    def generate_transformer(self):
        """生成变压器数据"""
        cursor = self.conn.cursor()
        config = DATACENTER_CONFIG["transformer"]
        cursor.execute("""
            INSERT INTO transformers (transformer_code, transformer_name, rated_capacity,
                voltage_high, voltage_low, connection_type, efficiency, status, is_enabled,
                location, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'Dyn11', 98.5, 'running', 1, '配电室', datetime('now'), datetime('now'))
        """, (config["code"], config["name"], config["capacity"], config["voltage_high"], config["voltage_low"]))
        self.conn.commit()
        transformer_id = cursor.lastrowid
        print(f"已创建变压器: {config['name']} (ID={transformer_id})")
        return transformer_id

    def generate_meter_point(self, transformer_id: int):
        """生成计量点数据"""
        cursor = self.conn.cursor()
        config = DATACENTER_CONFIG["meter_point"]
        cursor.execute("""
            INSERT INTO meter_points (meter_code, meter_name, meter_no, transformer_id,
                ct_ratio, pt_ratio, multiplier, declared_demand, demand_type, demand_period,
                customer_no, customer_name, status, is_enabled, created_at, updated_at)
            VALUES (?, ?, 'DDB001', ?, '400/5', '10000/100', 80, ?, 'kW', 15,
                'GD202401001', '智算中心', 'normal', 1, datetime('now'), datetime('now'))
        """, (config["code"], config["name"], transformer_id, config["declared_demand"]))
        self.conn.commit()
        meter_id = cursor.lastrowid
        print(f"已创建计量点: {config['name']} (ID={meter_id})")
        return meter_id

    def generate_pricing(self):
        """生成电价配置"""
        cursor = self.conn.cursor()
        today = date.today()
        for p in DATACENTER_CONFIG["pricing"]:
            cursor.execute("""
                INSERT INTO electricity_pricing (pricing_name, period_type, start_time, end_time,
                    price, effective_date, is_enabled, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, datetime('now'), datetime('now'))
            """, (p["name"], p["type"], p["start"], p["end"], p["price"], today.isoformat()))
        self.conn.commit()
        print(f"已创建电价配置: {len(DATACENTER_CONFIG['pricing'])}条")

    def generate_panels(self, meter_id: int):
        """生成配电柜数据"""
        cursor = self.conn.cursor()
        panel_ids = {}
        for p in DATACENTER_CONFIG["panels"]:
            cursor.execute("""
                INSERT INTO distribution_panels (panel_code, panel_name, panel_type,
                    rated_current, rated_voltage, meter_point_id, location, status,
                    is_enabled, created_at, updated_at)
                VALUES (?, ?, ?, ?, 380, ?, '配电室', 'running', 1, datetime('now'), datetime('now'))
            """, (p["code"], p["name"], p["type"], p["current"], meter_id))
            panel_ids[p["code"]] = cursor.lastrowid
        self.conn.commit()
        print(f"已创建配电柜: {len(panel_ids)}个")
        return panel_ids

    def generate_circuits(self, panel_ids: dict):
        """生成配电回路数据"""
        cursor = self.conn.cursor()
        circuit_ids = {}
        # 为每个配电柜创建回路
        circuit_configs = [
            {"code": "C-PDU-A01-01", "name": "A1列头柜主回路", "panel": "PDU-A01", "type": "it_equipment", "current": 250},
            {"code": "C-PDU-A02-01", "name": "A2列头柜主回路", "panel": "PDU-A02", "type": "it_equipment", "current": 250},
            {"code": "C-PDU-B01-01", "name": "B1列头柜主回路", "panel": "PDU-B01", "type": "it_equipment", "current": 250},
            {"code": "C-UPS-IN-01", "name": "UPS输入回路", "panel": "UPS-IN-001", "type": "ups", "current": 630},
            {"code": "C-AC-01", "name": "空调主回路", "panel": "AC-001", "type": "hvac", "current": 400},
            {"code": "C-LT-01", "name": "照明主回路", "panel": "LT-001", "type": "lighting", "current": 100},
        ]
        for c in circuit_configs:
            panel_id = panel_ids.get(c["panel"])
            if panel_id:
                cursor.execute("""
                    INSERT INTO distribution_circuits (circuit_code, circuit_name, panel_id,
                        rated_current, load_type, is_shiftable, shift_priority, is_enabled,
                        created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, 5, 1, datetime('now'), datetime('now'))
                """, (c["code"], c["name"], panel_id, c["current"], c["type"],
                      1 if c["type"] in ["hvac", "lighting"] else 0))
                circuit_ids[c["panel"]] = cursor.lastrowid
        self.conn.commit()
        print(f"已创建配电回路: {len(circuit_ids)}个")
        return circuit_ids

    def generate_devices(self, circuit_ids: dict):
        """生成用电设备数据"""
        cursor = self.conn.cursor()
        device_ids = {}
        for d in DATACENTER_CONFIG["devices"]:
            circuit_id = circuit_ids.get(d["circuit"])
            cursor.execute("""
                INSERT INTO power_devices (device_code, device_name, device_type, rated_power,
                    rated_voltage, power_factor, circuit_id, is_it_load, is_critical, is_metered,
                    is_enabled, created_at, updated_at)
                VALUES (?, ?, ?, ?, 380, 0.9, ?, ?, ?, 1, 1, datetime('now'), datetime('now'))
            """, (d["code"], d["name"], d["type"], d["power"], circuit_id,
                  1 if d["is_it"] else 0, 1 if d["type"] in ["IT_SERVER", "UPS"] else 0))
            device_ids[d["code"]] = cursor.lastrowid
        self.conn.commit()
        print(f"已创建用电设备: {len(device_ids)}个")
        return device_ids

    def generate_regulation_configs(self, device_ids: dict):
        """生成负荷调节配置"""
        cursor = self.conn.cursor()
        count = 0
        for d in DATACENTER_CONFIG["devices"]:
            if d.get("adjustable"):
                device_id = device_ids.get(d["code"])
                if device_id:
                    if d["type"] == "HVAC":
                        # 空调温度调节
                        cursor.execute("""
                            INSERT INTO load_regulation_configs (device_id, regulation_type,
                                min_value, max_value, current_value, default_value, step_size, unit,
                                power_factor, base_power, priority, comfort_impact, is_enabled, is_auto,
                                created_at, updated_at)
                            VALUES (?, 'temperature', 18, 28, 24, 24, 1, '℃', ?, ?, 3, 'medium', 1, 0,
                                datetime('now'), datetime('now'))
                        """, (device_id, d["power"] * 0.03, d["power"]))
                        count += 1
                    elif d["type"] == "LIGHTING":
                        # 照明亮度调节
                        cursor.execute("""
                            INSERT INTO load_regulation_configs (device_id, regulation_type,
                                min_value, max_value, current_value, default_value, step_size, unit,
                                power_factor, base_power, priority, comfort_impact, is_enabled, is_auto,
                                created_at, updated_at)
                            VALUES (?, 'brightness', 30, 100, 100, 100, 10, '%', ?, ?, 5, 'low', 1, 0,
                                datetime('now'), datetime('now'))
                        """, (device_id, d["power"] * 0.007, d["power"]))
                        count += 1
        self.conn.commit()
        print(f"已创建负荷调节配置: {count}个")

    def generate_energy_history(self, device_ids: dict, days: int = 30):
        """生成历史能耗数据"""
        cursor = self.conn.cursor()
        now = datetime.now()
        hourly_count = 0
        daily_count = 0

        for d in DATACENTER_CONFIG["devices"]:
            device_id = device_ids.get(d["code"])
            if not device_id:
                continue

            # 生成每日数据
            for day_offset in range(days):
                stat_date = (now - timedelta(days=day_offset)).date()
                daily_energy = 0
                peak_energy = 0
                valley_energy = 0
                normal_energy = 0
                max_power = 0
                power_sum = 0

                # 生成每小时数据
                for hour in range(24):
                    stat_time = datetime.combine(stat_date, datetime.min.time()) + timedelta(hours=hour)
                    power = generate_load_curve(hour, d["type"], d["power"])
                    energy = power  # 1小时的能耗 = 功率 * 1h

                    period = get_time_period(hour)
                    price = get_price_by_period(period)

                    cursor.execute("""
                        INSERT INTO energy_hourly (device_id, stat_time, total_energy, avg_power,
                            max_power, min_power, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                    """, (device_id, stat_time.isoformat(), energy, power,
                          power * 1.05, power * 0.95))
                    hourly_count += 1

                    daily_energy += energy
                    power_sum += power
                    max_power = max(max_power, power)

                    if period == "peak" or period == "sharp":
                        peak_energy += energy
                    elif period == "valley":
                        valley_energy += energy
                    else:
                        normal_energy += energy

                # 计算日电费
                energy_cost = peak_energy * 1.0 + normal_energy * 0.7 + valley_energy * 0.4
                avg_power = power_sum / 24

                cursor.execute("""
                    INSERT INTO energy_daily (device_id, stat_date, total_energy, peak_energy,
                        normal_energy, valley_energy, max_power, avg_power, energy_cost, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """, (device_id, stat_date.isoformat(), daily_energy, peak_energy,
                      normal_energy, valley_energy, max_power, avg_power, energy_cost))
                daily_count += 1

            # 每100条提交一次
            if hourly_count % 1000 == 0:
                self.conn.commit()

        self.conn.commit()
        print(f"已创建小时能耗数据: {hourly_count}条")
        print(f"已创建日能耗数据: {daily_count}条")

    def generate_demand_15min(self, meter_id: int, days: int = 7):
        """生成15分钟需量数据"""
        cursor = self.conn.cursor()
        now = datetime.now()
        declared_demand = DATACENTER_CONFIG["meter_point"]["declared_demand"]
        count = 0

        for day_offset in range(days):
            base_date = (now - timedelta(days=day_offset)).date()
            daily_max = 0
            daily_max_time = None

            for hour in range(24):
                for minute in [0, 15, 30, 45]:
                    timestamp = datetime.combine(base_date, datetime.min.time()) + timedelta(hours=hour, minutes=minute)

                    # 计算总功率 (所有设备功率之和)
                    total_power = sum(
                        generate_load_curve(hour, d["type"], d["power"])
                        for d in DATACENTER_CONFIG["devices"]
                    )
                    # 添加随机波动
                    total_power *= (1 + random.uniform(-0.05, 0.05))

                    period = get_time_period(hour)
                    is_peak = period in ["peak", "sharp"]
                    is_over = total_power > declared_demand
                    demand_ratio = (total_power / declared_demand) * 100

                    if total_power > daily_max:
                        daily_max = total_power
                        daily_max_time = timestamp

                    cursor.execute("""
                        INSERT INTO demand_15min_data (meter_point_id, timestamp, average_power,
                            max_power, min_power, rolling_demand, declared_demand, demand_ratio,
                            is_peak_period, time_period, is_over_declared, recorded_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                    """, (meter_id, timestamp.isoformat(), total_power,
                          total_power * 1.02, total_power * 0.98, total_power,
                          declared_demand, demand_ratio, 1 if is_peak else 0,
                          period, 1 if is_over else 0))
                    count += 1

            # 标记当日最大需量
            if daily_max_time:
                cursor.execute("""
                    UPDATE demand_15min_data SET is_max_of_day = 1
                    WHERE meter_point_id = ? AND timestamp = ?
                """, (meter_id, daily_max_time.isoformat()))

        self.conn.commit()
        print(f"已创建15分钟需量数据: {count}条")

    def generate_pue_history(self, days: int = 30):
        """生成PUE历史数据"""
        cursor = self.conn.cursor()
        now = datetime.now()
        count = 0

        for day_offset in range(days):
            for hour in range(24):
                record_time = now - timedelta(days=day_offset, hours=23-hour)

                # 计算IT负载
                it_power = sum(
                    generate_load_curve(hour, d["type"], d["power"])
                    for d in DATACENTER_CONFIG["devices"] if d["is_it"]
                )

                # 计算制冷功率
                cooling_power = sum(
                    generate_load_curve(hour, d["type"], d["power"])
                    for d in DATACENTER_CONFIG["devices"] if d["type"] == "HVAC"
                )

                # 计算其他功率
                ups_loss = 40 * 0.05  # UPS损耗约5%
                lighting_power = sum(
                    generate_load_curve(hour, d["type"], d["power"])
                    for d in DATACENTER_CONFIG["devices"] if d["type"] == "LIGHTING"
                )
                other_power = sum(
                    generate_load_curve(hour, d["type"], d["power"])
                    for d in DATACENTER_CONFIG["devices"] if d["type"] == "PUMP"
                )

                total_power = it_power + cooling_power + ups_loss + lighting_power + other_power
                pue = total_power / it_power if it_power > 0 else 1.5

                cursor.execute("""
                    INSERT INTO pue_history (record_time, total_power, it_power, cooling_power,
                        ups_loss, lighting_power, other_power, pue, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """, (record_time.isoformat(), total_power, it_power, cooling_power,
                      ups_loss, lighting_power, other_power, round(pue, 3)))
                count += 1

        self.conn.commit()
        print(f"已创建PUE历史数据: {count}条")

    def generate_suggestions(self, device_ids: dict):
        """生成节能建议"""
        cursor = self.conn.cursor()
        import json
        suggestions = []

        # 1. 负荷转移建议 - 空调
        for d in DATACENTER_CONFIG["devices"]:
            if d["type"] == "HVAC" and d.get("adjustable"):
                device_id = device_ids.get(d["code"])
                saving = d["power"] * 0.3 * 5 * 30 * (1.0 - 0.4)  # 30%功率转移5小时，峰谷差价
                suggestions.append({
                    "rule_id": "SHIFT_LOAD_PEAK_TO_VALLEY",
                    "rule_name": "负荷转移-峰转谷",
                    "device_id": device_id,
                    "category": "cost",
                    "suggestion": f"建议将{d['name']}的部分运行负荷从高峰时段(10:00-12:00, 14:00-17:00)转移到低谷时段(23:00-07:00)，预计每月可节省电费{saving:.0f}元",
                    "priority": "high",
                    "potential_saving": d["power"] * 0.3 * 5 * 30,
                    "potential_cost_saving": saving,
                    "difficulty": "medium",
                    "implementation_steps": json.dumps([
                        {"step": 1, "description": "分析空调负荷曲线，确定可转移时段"},
                        {"step": 2, "description": "调整空调运行策略，夜间预冷"},
                        {"step": 3, "description": "监测室内温度，确保不影响设备运行"}
                    ]),
                })

        # 2. 温度优化建议
        suggestions.append({
            "rule_id": "REDUCE_HVAC_SETPOINT",
            "rule_name": "空调温度优化",
            "device_id": None,
            "category": "efficiency",
            "suggestion": "建议将机房空调设定温度从24℃提高到26℃，可降低制冷能耗约15%，每月节省约2000kWh",
            "priority": "medium",
            "potential_saving": 2000,
            "potential_cost_saving": 2000 * 0.7,
            "difficulty": "easy",
            "implementation_steps": json.dumps([
                {"step": 1, "description": "逐步提高设定温度，每次1℃"},
                {"step": 2, "description": "监测服务器进风温度，确保不超过27℃"},
                {"step": 3, "description": "观察一周，确认设备运行正常"}
            ]),
        })

        # 3. 需量优化建议
        suggestions.append({
            "rule_id": "DEMAND_OPTIMIZATION",
            "rule_name": "需量优化",
            "device_id": None,
            "category": "demand",
            "suggestion": "当前申报需量400kW，实际最大需量约350kW，建议调整申报需量为380kW，可节省需量电费约600元/月",
            "priority": "high",
            "potential_saving": 0,
            "potential_cost_saving": 600,
            "difficulty": "medium",
            "implementation_steps": json.dumps([
                {"step": 1, "description": "收集近3个月需量数据"},
                {"step": 2, "description": "分析需量分布，确定合理申报值"},
                {"step": 3, "description": "向供电局申请调整申报需量"}
            ]),
        })

        # 4. PUE优化建议
        suggestions.append({
            "rule_id": "PUE_IMPROVEMENT",
            "rule_name": "PUE优化",
            "device_id": None,
            "category": "pue",
            "suggestion": "当前PUE为1.65，通过优化空调运行策略和提高冷通道封闭效果，可将PUE降低至1.50，年节省电费约50000元",
            "priority": "high",
            "potential_saving": 50000 / 0.7,
            "potential_cost_saving": 50000,
            "difficulty": "hard",
            "implementation_steps": json.dumps([
                {"step": 1, "description": "完善冷热通道隔离"},
                {"step": 2, "description": "优化空调送风温度和风量"},
                {"step": 3, "description": "安装变频控制，按需制冷"},
                {"step": 4, "description": "定期清洁空调滤网和盘管"}
            ]),
        })

        # 5. 照明优化建议
        for d in DATACENTER_CONFIG["devices"]:
            if d["type"] == "LIGHTING":
                device_id = device_ids.get(d["code"])
                saving = d["power"] * 0.3 * 12 * 30  # 降低30%亮度，每天12小时
                suggestions.append({
                    "rule_id": "REDUCE_LIGHTING_INTENSITY",
                    "rule_name": "照明亮度优化",
                    "device_id": device_id,
                    "category": "efficiency",
                    "suggestion": f"建议在非工作时段(20:00-08:00)将{d['name']}亮度从100%降低到50%，预计节省{saving:.0f}kWh/月",
                    "priority": "low",
                    "potential_saving": saving,
                    "potential_cost_saving": saving * 0.5,
                    "difficulty": "easy",
                    "implementation_steps": json.dumps([
                        {"step": 1, "description": "安装照明控制系统或定时器"},
                        {"step": 2, "description": "设置分时段亮度策略"},
                        {"step": 3, "description": "保留应急照明"}
                    ]),
                })

        # 6. 削峰建议
        suggestions.append({
            "rule_id": "PEAK_SHAVING",
            "rule_name": "削峰填谷",
            "device_id": None,
            "category": "demand",
            "suggestion": "在14:00-17:00尖峰时段，建议降低非关键负荷功率约30kW，避免超过申报需量，预防需量罚款",
            "priority": "urgent",
            "potential_saving": 0,
            "potential_cost_saving": 30 * 2 * 30,  # 超需量罚款
            "difficulty": "medium",
            "implementation_steps": json.dumps([
                {"step": 1, "description": "识别可调节的非关键负荷"},
                {"step": 2, "description": "设置需量预警阈值(90%)"},
                {"step": 3, "description": "制定应急降负荷预案"},
                {"step": 4, "description": "在需量接近阈值时自动或手动降负荷"}
            ]),
        })

        # 插入数据库
        for s in suggestions:
            cursor.execute("""
                INSERT INTO energy_suggestions (rule_id, rule_name, device_id, category,
                    suggestion, priority, potential_saving, potential_cost_saving, difficulty,
                    implementation_steps, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', datetime('now'), datetime('now'))
            """, (s["rule_id"], s["rule_name"], s.get("device_id"), s["category"],
                  s["suggestion"], s["priority"], s["potential_saving"],
                  s["potential_cost_saving"], s["difficulty"], s.get("implementation_steps")))

        self.conn.commit()
        print(f"已创建节能建议: {len(suggestions)}条")

    def run(self):
        """执行完整的数据生成"""
        print("=" * 50)
        print("开始生成展示数据...")
        print("=" * 50)

        self.connect()

        try:
            # 清除旧数据
            self.clear_demo_data()

            # 生成配电拓扑
            transformer_id = self.generate_transformer()
            meter_id = self.generate_meter_point(transformer_id)
            self.generate_pricing()
            panel_ids = self.generate_panels(meter_id)
            circuit_ids = self.generate_circuits(panel_ids)
            device_ids = self.generate_devices(circuit_ids)

            # 生成负荷调节配置
            self.generate_regulation_configs(device_ids)

            # 生成历史数据
            print("\n生成历史数据(可能需要几分钟)...")
            self.generate_energy_history(device_ids, days=30)
            self.generate_demand_15min(meter_id, days=7)
            self.generate_pue_history(days=30)

            # 生成节能建议
            self.generate_suggestions(device_ids)

            print("\n" + "=" * 50)
            print("展示数据生成完成!")
            print("=" * 50)

        finally:
            self.close()


def main():
    """主函数"""
    import sys
    import os

    # 确定数据库路径
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        # 默认路径
        db_path = os.path.join(os.path.dirname(__file__), '..', '..', 'dcim.db')

    db_path = os.path.abspath(db_path)
    print(f"数据库路径: {db_path}")

    if not os.path.exists(db_path):
        print(f"错误: 数据库文件不存在: {db_path}")
        sys.exit(1)

    generator = DemoDataGenerator(db_path)
    generator.run()


if __name__ == "__main__":
    main()
