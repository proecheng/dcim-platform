"""
实时数据模拟器 - 动态展示
Realtime Data Simulator for Dynamic Display

功能：
1. 每10秒更新实时数据
2. 模拟功率波动
3. 更新PUE数据
4. 模拟需量变化

使用方法：
    python -m app.tools.realtime_simulator
"""

import sqlite3
import random
import time
import threading
from datetime import datetime
from typing import Dict, Any

# 导入配置
from .demo_data_generator import DATACENTER_CONFIG, generate_load_curve, get_time_period


class RealtimeSimulator:
    """实时数据模拟器"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            import os
            db_path = os.path.join(os.path.dirname(__file__), '..', '..', 'dcim.db')
        self.db_path = db_path
        self.running = False
        self.interval = 10  # 更新间隔(秒)
        self.device_cache = {}  # 设备缓存

    def connect(self):
        """创建数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def load_devices(self):
        """加载设备信息"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, device_code, device_name, device_type, rated_power, is_it_load
            FROM power_devices WHERE is_enabled = 1
        """)
        for row in cursor.fetchall():
            self.device_cache[row['device_code']] = dict(row)
        conn.close()
        print(f"已加载 {len(self.device_cache)} 个设备")

    def update_point_realtime(self, conn):
        """更新测点实时数据"""
        cursor = conn.cursor()
        now = datetime.now()
        hour = now.hour

        # 获取所有启用的测点
        cursor.execute("""
            SELECT id, point_code, point_type, min_range, max_range, unit
            FROM points WHERE is_enabled = 1
        """)
        points = cursor.fetchall()

        for point in points:
            point_id = point['id']
            point_code = point['point_code']
            point_type = point['point_type']
            min_val = point['min_range'] or 0
            max_val = point['max_range'] or 100

            # 根据点位类型生成模拟值
            if 'TEMP' in point_code or point['unit'] == '℃':
                # 温度: 22-28℃
                value = 24 + random.uniform(-2, 4)
            elif 'HUMI' in point_code or point['unit'] == '%RH':
                # 湿度: 40-60%
                value = 50 + random.uniform(-10, 10)
            elif 'POWER' in point_code or point['unit'] == 'kW':
                # 功率: 根据时间变化
                base = (max_val - min_val) * 0.7
                value = base * (0.8 + 0.4 * (1 if 9 <= hour <= 18 else 0.6))
                value += random.uniform(-base * 0.05, base * 0.05)
            elif 'VOLT' in point_code or point['unit'] == 'V':
                # 电压: 380V ± 5%
                value = 380 + random.uniform(-19, 19)
            elif 'CURR' in point_code or point['unit'] == 'A':
                # 电流
                value = (min_val + max_val) / 2 * (0.7 + random.uniform(-0.1, 0.2))
            else:
                # 其他: 在范围内随机
                value = min_val + (max_val - min_val) * random.uniform(0.3, 0.8)

            # 更新或插入实时数据
            cursor.execute("""
                INSERT OR REPLACE INTO point_realtime (point_id, value, quality, update_time)
                VALUES (?, ?, 'good', ?)
            """, (point_id, round(value, 2), now.isoformat()))

        conn.commit()
        return len(points)

    def update_pue_realtime(self, conn):
        """更新PUE实时数据"""
        cursor = conn.cursor()
        now = datetime.now()
        hour = now.hour

        # 计算各类功率
        it_power = 0
        cooling_power = 0
        other_power = 0

        for code, device in self.device_cache.items():
            power = generate_load_curve(hour, device['device_type'], device['rated_power'])
            if device['is_it_load']:
                it_power += power
            elif device['device_type'] == 'HVAC':
                cooling_power += power
            else:
                other_power += power

        # 添加随机波动
        it_power *= (1 + random.uniform(-0.03, 0.03))
        cooling_power *= (1 + random.uniform(-0.05, 0.05))

        total_power = it_power + cooling_power + other_power
        pue = total_power / it_power if it_power > 0 else 1.5

        # 插入PUE记录
        cursor.execute("""
            INSERT INTO pue_history (record_time, total_power, it_power, cooling_power,
                ups_loss, lighting_power, other_power, pue, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """, (now.isoformat(), round(total_power, 2), round(it_power, 2),
              round(cooling_power, 2), 2.0, 5.0, round(other_power, 2), round(pue, 3)))

        conn.commit()
        return pue

    def update_demand_realtime(self, conn):
        """更新需量实时数据"""
        cursor = conn.cursor()
        now = datetime.now()
        hour = now.hour

        # 获取计量点
        cursor.execute("SELECT id, declared_demand FROM meter_points WHERE is_enabled = 1")
        meter = cursor.fetchone()
        if not meter:
            return 0

        meter_id = meter['id']
        declared_demand = meter['declared_demand'] or 400

        # 计算总功率
        total_power = sum(
            generate_load_curve(hour, d['device_type'], d['rated_power'])
            for d in self.device_cache.values()
        )
        total_power *= (1 + random.uniform(-0.05, 0.05))

        period = get_time_period(hour)
        demand_ratio = (total_power / declared_demand) * 100

        # 只在15分钟整点插入需量数据
        if now.minute % 15 == 0 and now.second < 15:
            cursor.execute("""
                INSERT INTO demand_15min_data (meter_point_id, timestamp, average_power,
                    max_power, min_power, rolling_demand, declared_demand, demand_ratio,
                    is_peak_period, time_period, is_over_declared, recorded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (meter_id, now.replace(second=0, microsecond=0).isoformat(),
                  round(total_power, 2), round(total_power * 1.02, 2),
                  round(total_power * 0.98, 2), round(total_power, 2),
                  declared_demand, round(demand_ratio, 1),
                  1 if period in ['peak', 'sharp'] else 0, period,
                  1 if total_power > declared_demand else 0))
            conn.commit()

        return total_power

    def run_once(self):
        """执行一次更新"""
        conn = self.connect()
        try:
            points_count = self.update_point_realtime(conn)
            pue = self.update_pue_realtime(conn)
            power = self.update_demand_realtime(conn)

            now = datetime.now().strftime("%H:%M:%S")
            print(f"[{now}] 更新: {points_count}点位, PUE={pue:.3f}, 总功率={power:.1f}kW")
        finally:
            conn.close()

    def start(self):
        """启动模拟器"""
        print("=" * 50)
        print("实时数据模拟器启动")
        print(f"更新间隔: {self.interval}秒")
        print("=" * 50)

        self.load_devices()
        self.running = True

        while self.running:
            try:
                self.run_once()
                time.sleep(self.interval)
            except KeyboardInterrupt:
                print("\n收到停止信号")
                break
            except Exception as e:
                print(f"更新出错: {e}")
                time.sleep(self.interval)

        print("模拟器已停止")

    def stop(self):
        """停止模拟器"""
        self.running = False


def main():
    """主函数"""
    import sys
    import os

    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        db_path = os.path.join(os.path.dirname(__file__), '..', '..', 'dcim.db')

    db_path = os.path.abspath(db_path)
    print(f"数据库路径: {db_path}")

    simulator = RealtimeSimulator(db_path)
    simulator.start()


if __name__ == "__main__":
    main()
