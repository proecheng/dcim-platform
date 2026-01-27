"""
历史数据生成器
为点位生成过去30天的模拟历史数据

功能：
1. 为所有 AI 类型点位生成历史数据
2. 数据符合真实物理规律（日夜波动、峰谷变化等）
3. 每5分钟一条记录，30天约8640条/点位
"""

import sqlite3
import math
import random
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Any


# 点位数据生成配置
POINT_CONFIG = {
    # 温度点位 (单位: ℃)
    'TH_AI_001': {
        'base': 24.0,       # 基准值
        'day_var': 2.0,     # 日间波动
        'night_var': -1.5,  # 夜间偏移
        'random_var': 0.5,  # 随机波动
        'min': 18.0,
        'max': 30.0
    },
    # 湿度点位 (单位: %RH)
    'TH_AI_002': {
        'base': 50.0,
        'day_var': -5.0,    # 日间湿度低
        'night_var': 5.0,   # 夜间湿度高
        'random_var': 3.0,
        'min': 30.0,
        'max': 70.0
    },
    # UPS 输入电压 (单位: V)
    'UPS_AI_001': {
        'base': 220.0,
        'day_var': -3.0,    # 白天负载高，电压略低
        'night_var': 2.0,
        'random_var': 2.0,
        'min': 200.0,
        'max': 240.0
    },
    # UPS 输出电压 (单位: V)
    'UPS_AI_002': {
        'base': 220.0,
        'day_var': 0.0,     # UPS 稳压输出
        'night_var': 0.0,
        'random_var': 0.5,
        'min': 218.0,
        'max': 222.0
    },
    # UPS 负载率 (单位: %)
    'UPS_AI_003': {
        'base': 60.0,
        'day_var': 15.0,    # 白天负载高
        'night_var': -10.0,
        'random_var': 5.0,
        'min': 30.0,
        'max': 90.0
    },
    # 电池容量 (单位: %)
    'UPS_AI_004': {
        'base': 95.0,
        'day_var': -2.0,
        'night_var': 2.0,
        'random_var': 1.0,
        'min': 85.0,
        'max': 100.0
    },
    # UPS 频率 (单位: Hz)
    'UPS_AI_005': {
        'base': 50.0,
        'day_var': 0.0,
        'night_var': 0.0,
        'random_var': 0.1,
        'min': 49.5,
        'max': 50.5
    },
    # UPS 温度 (单位: ℃)
    'UPS_AI_006': {
        'base': 35.0,
        'day_var': 3.0,
        'night_var': -2.0,
        'random_var': 1.0,
        'min': 25.0,
        'max': 45.0
    },
    # PDU 电流 (单位: A)
    'PDU_AI_001': {
        'base': 80.0,
        'day_var': 20.0,
        'night_var': -15.0,
        'random_var': 5.0,
        'min': 40.0,
        'max': 120.0
    },
    'PDU_AI_002': {
        'base': 75.0,
        'day_var': 18.0,
        'night_var': -12.0,
        'random_var': 5.0,
        'min': 40.0,
        'max': 110.0
    },
    'PDU_AI_003': {
        'base': 78.0,
        'day_var': 19.0,
        'night_var': -14.0,
        'random_var': 5.0,
        'min': 40.0,
        'max': 115.0
    },
    # PDU 总功率 (单位: kW)
    'PDU_AI_004': {
        'base': 150.0,
        'day_var': 40.0,
        'night_var': -30.0,
        'random_var': 10.0,
        'min': 80.0,
        'max': 220.0
    },
    # 空调送风温度 (单位: ℃)
    'AC_AI_001': {
        'base': 16.0,
        'day_var': 1.0,
        'night_var': -0.5,
        'random_var': 0.5,
        'min': 12.0,
        'max': 20.0
    },
    # 空调回风温度 (单位: ℃)
    'AC_AI_002': {
        'base': 26.0,
        'day_var': 2.0,
        'night_var': -1.5,
        'random_var': 0.8,
        'min': 20.0,
        'max': 32.0
    },
}

# DI 点位状态变化概率（每小时）
DI_CHANGE_PROBABILITY = 0.02


def get_point_config(point_code: str) -> Dict[str, float]:
    """根据点位编码获取配置"""
    # 提取点位类型 (如 TH_AI_001 从 A1_TH_AI_001 中提取)
    parts = point_code.split('_')
    if len(parts) >= 4:
        point_type = '_'.join(parts[1:])  # TH_AI_001
        if point_type in POINT_CONFIG:
            return POINT_CONFIG[point_type]

    # 尝试匹配更短的模式
    for key in POINT_CONFIG:
        if key in point_code:
            return POINT_CONFIG[key]

    # 默认配置
    return {
        'base': 50.0,
        'day_var': 5.0,
        'night_var': -3.0,
        'random_var': 2.0,
        'min': 0.0,
        'max': 100.0
    }


def generate_ai_value(config: Dict[str, float], timestamp: datetime, prev_value: float = None) -> float:
    """生成 AI 点位数值"""
    hour = timestamp.hour

    # 日夜变化（正弦曲线模拟）
    # 白天高点在 14:00，夜间低点在 02:00
    day_factor = math.sin((hour - 2) * math.pi / 12)  # -1 到 1

    if day_factor > 0:
        day_offset = config['day_var'] * day_factor
    else:
        day_offset = config['night_var'] * abs(day_factor)

    # 随机波动
    random_offset = random.uniform(-config['random_var'], config['random_var'])

    # 计算最终值
    value = config['base'] + day_offset + random_offset

    # 如果有前一个值，添加平滑过渡
    if prev_value is not None:
        # 限制变化幅度，使数据更平滑
        max_change = config['random_var'] * 0.5
        if abs(value - prev_value) > max_change:
            value = prev_value + max_change * (1 if value > prev_value else -1)

    # 限制在范围内
    value = max(config['min'], min(config['max'], value))

    return round(value, 2)


def generate_di_value(prev_value: int, timestamp: datetime) -> int:
    """生成 DI 点位状态（0 或 1）"""
    # 低概率状态变化
    if random.random() < DI_CHANGE_PROBABILITY / 12:  # 每5分钟检查
        return 1 - prev_value
    return prev_value


class HistoryDataGenerator:
    """历史数据生成器"""

    def __init__(self, db_path: str = 'dcim.db'):
        self.db_path = db_path
        self.conn = None
        self.points = []

    def connect(self):
        """连接数据库"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        return self.conn

    def close(self):
        """关闭连接"""
        if self.conn:
            self.conn.close()

    def load_points(self):
        """加载所有点位"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id, point_code, point_name, point_type, unit
            FROM points
            WHERE is_enabled = 1 OR is_enabled IS NULL
            ORDER BY id
        """)
        self.points = cursor.fetchall()
        print(f"加载了 {len(self.points)} 个点位")
        return self.points

    def clear_old_history(self, days: int = 30):
        """清除旧的历史数据（保留指定天数内的实时数据）"""
        cursor = self.conn.cursor()
        cutoff_time = datetime.now() - timedelta(days=days)

        # 先统计当前数据量
        cursor.execute("SELECT COUNT(*) FROM point_history")
        before_count = cursor.fetchone()[0]

        # 删除旧数据
        cursor.execute("""
            DELETE FROM point_history
            WHERE recorded_at < ?
        """, (cutoff_time.isoformat(),))

        self.conn.commit()

        cursor.execute("SELECT COUNT(*) FROM point_history")
        after_count = cursor.fetchone()[0]

        print(f"清理历史数据: {before_count} -> {after_count} 条")

    def generate_history(self, days: int = 30, interval_minutes: int = 5):
        """
        生成历史数据

        Args:
            days: 生成多少天的历史数据
            interval_minutes: 数据间隔（分钟）
        """
        cursor = self.conn.cursor()

        now = datetime.now()
        start_time = now - timedelta(days=days)

        # 计算总数据点数
        total_intervals = (days * 24 * 60) // interval_minutes
        total_records = len(self.points) * total_intervals

        print(f"\n开始生成历史数据...")
        print(f"时间范围: {start_time.strftime('%Y-%m-%d %H:%M')} 到 {now.strftime('%Y-%m-%d %H:%M')}")
        print(f"数据间隔: {interval_minutes} 分钟")
        print(f"预计生成: {total_records:,} 条记录")
        print("-" * 50)

        batch_size = 5000
        insert_count = 0
        batch_data = []

        # 为每个点位生成数据
        for point in self.points:
            point_id = point['id']
            point_code = point['point_code']
            point_type = point['point_type']

            config = get_point_config(point_code)
            prev_value = None

            # 从 start_time 开始，每隔 interval_minutes 分钟生成一条记录
            current_time = start_time
            while current_time < now:
                if point_type == 'AI':
                    value = generate_ai_value(config, current_time, prev_value)
                    prev_value = value
                elif point_type == 'DI':
                    if prev_value is None:
                        prev_value = 0
                    value = generate_di_value(int(prev_value), current_time)
                    prev_value = value
                elif point_type == 'AO':
                    # AO 点位通常是设定值，变化较少
                    if prev_value is None:
                        prev_value = config['base']
                    if random.random() < 0.001:  # 极低概率变化
                        prev_value = config['base'] + random.uniform(-2, 2)
                    value = prev_value
                elif point_type == 'DO':
                    # DO 点位状态
                    if prev_value is None:
                        prev_value = 1  # 默认开启
                    if random.random() < 0.0005:
                        prev_value = 1 - int(prev_value)
                    value = int(prev_value)
                else:
                    value = config['base']

                # 添加到批次
                batch_data.append((
                    point_id,
                    round(value, 2),
                    0,  # quality = 0 (good)
                    current_time.isoformat()
                ))

                # 批量插入
                if len(batch_data) >= batch_size:
                    cursor.executemany("""
                        INSERT INTO point_history (point_id, value, quality, recorded_at)
                        VALUES (?, ?, ?, ?)
                    """, batch_data)
                    self.conn.commit()
                    insert_count += len(batch_data)

                    # 显示进度
                    progress = (insert_count / total_records) * 100
                    print(f"\r进度: {progress:.1f}% ({insert_count:,}/{total_records:,})", end='', flush=True)

                    batch_data = []

                current_time += timedelta(minutes=interval_minutes)

        # 插入剩余数据
        if batch_data:
            cursor.executemany("""
                INSERT INTO point_history (point_id, value, quality, recorded_at)
                VALUES (?, ?, ?, ?)
            """, batch_data)
            self.conn.commit()
            insert_count += len(batch_data)

        print(f"\r进度: 100.0% ({insert_count:,}/{total_records:,})")
        print("-" * 50)
        print(f"历史数据生成完成! 共插入 {insert_count:,} 条记录")

    def verify_data(self):
        """验证生成的数据"""
        cursor = self.conn.cursor()

        print("\n=== 数据验证 ===")

        # 总数据量
        cursor.execute("SELECT COUNT(*) FROM point_history")
        total = cursor.fetchone()[0]
        print(f"总记录数: {total:,}")

        # 时间范围
        cursor.execute("SELECT MIN(recorded_at), MAX(recorded_at) FROM point_history")
        time_range = cursor.fetchone()
        print(f"时间范围: {time_range[0]} 到 {time_range[1]}")

        # 每个点位的数据量
        cursor.execute("""
            SELECT p.point_code, p.point_type, COUNT(h.id) as cnt,
                   MIN(h.value) as min_val, MAX(h.value) as max_val, AVG(h.value) as avg_val
            FROM points p
            LEFT JOIN point_history h ON p.id = h.point_id
            GROUP BY p.id
            ORDER BY p.id
            LIMIT 10
        """)

        print("\n前10个点位数据统计:")
        print(f"{'点位编码':<20} {'类型':<5} {'数量':>10} {'最小值':>10} {'最大值':>10} {'平均值':>10}")
        print("-" * 75)
        for row in cursor.fetchall():
            print(f"{row[0]:<20} {row[1]:<5} {row[2]:>10,} {row[3]:>10.2f} {row[4]:>10.2f} {row[5]:>10.2f}")

    def run(self, days: int = 30):
        """执行数据生成"""
        print("=" * 60)
        print("  历史数据生成器 - 算力中心智能监控系统")
        print("=" * 60)

        self.connect()

        try:
            # 加载点位
            self.load_points()

            # 清理旧数据（可选）
            # self.clear_old_history(days)

            # 生成历史数据
            self.generate_history(days=days, interval_minutes=5)

            # 验证数据
            self.verify_data()

            print("\n" + "=" * 60)
            print("  历史数据生成完成!")
            print("=" * 60)

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
        db_path = os.path.join(os.path.dirname(__file__), 'dcim.db')

    db_path = os.path.abspath(db_path)
    print(f"数据库路径: {db_path}")

    if not os.path.exists(db_path):
        print(f"错误: 数据库文件不存在: {db_path}")
        sys.exit(1)

    # 默认生成30天数据
    days = 30
    if len(sys.argv) > 2:
        days = int(sys.argv[2])

    generator = HistoryDataGenerator(db_path)
    generator.run(days=days)


if __name__ == "__main__":
    main()
