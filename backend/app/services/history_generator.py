"""
历史数据生成器 - 生成30天的模拟历史数据
"""
import asyncio
import random
import math
from datetime import datetime, timedelta
from typing import List, Dict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import async_session
from ..models import Point, PointHistory, PUEHistory


class HistoryGenerator:
    """历史数据生成器"""

    def __init__(self, days: int = 30):
        self.days = days
        self.base_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    def generate_daily_pattern(self, hour: int, base_value: float, variation: float) -> float:
        """生成日内波动模式
        - 白天(8-20)负载较高
        - 夜间(20-8)负载较低
        """
        if 8 <= hour < 20:
            # 白天：基础值 + 10-20%
            factor = 1.0 + random.uniform(0.1, 0.2)
        else:
            # 夜间：基础值 - 10-20%
            factor = 1.0 - random.uniform(0.1, 0.2)

        # 添加随机波动
        noise = random.uniform(-variation, variation)
        return base_value * factor + noise

    def generate_seasonal_pattern(self, day_offset: int, base_value: float) -> float:
        """生成季节性波动（简化为30天周期）"""
        # 模拟月初月末的小幅变化
        cycle = math.sin(2 * math.pi * day_offset / 30)
        return base_value * (1 + 0.05 * cycle)

    def generate_point_history(self, point: Point, hours: int) -> List[Dict]:
        """生成单个点位的历史数据"""
        records = []

        # 根据点位类型确定基础值和波动范围
        if point.point_type == "AI":
            min_val = point.min_range or 0
            max_val = point.max_range or 100
            base_value = (min_val + max_val) / 2
            variation = (max_val - min_val) * 0.05

            # 特定设备类型的基础值调整
            if "温度" in point.point_name and "TH" in (point.device_type or ""):
                base_value = 24  # 机房温度基准
            elif "湿度" in point.point_name:
                base_value = 50  # 湿度基准
            elif "负载率" in point.point_name:
                base_value = 45  # 负载率基准
            elif "电池电量" in point.point_name:
                base_value = 85  # 电池电量基准
            elif "功率" in point.point_name and "kW" in (point.unit or ""):
                base_value = max_val * 0.4  # 功率基准
        else:
            # DI/DO 点位
            base_value = 0
            variation = 0

        for h in range(hours):
            record_time = self.base_time - timedelta(hours=hours-h)
            day_offset = (self.base_time - record_time).days
            hour = record_time.hour

            if point.point_type == "AI":
                seasonal_base = self.generate_seasonal_pattern(day_offset, base_value)
                value = self.generate_daily_pattern(hour, seasonal_base, variation)
                # 确保在量程范围内
                value = max(point.min_range or 0, min(point.max_range or 100, value))
                value = round(value, 2)
            else:
                # 开关量：极低概率为1
                value = 1 if random.random() < 0.001 else 0

            records.append({
                "point_id": point.id,
                "value": value,
                "quality": 0,
                "recorded_at": record_time,
            })

        return records

    async def generate_all_history(self, batch_size: int = 1000):
        """生成所有点位的历史数据"""
        total_hours = self.days * 24

        async with async_session() as session:
            # 获取所有点位
            result = await session.execute(select(Point).where(Point.is_enabled == True))
            points = result.scalars().all()

            print(f"开始生成 {len(points)} 个点位 x {total_hours} 小时的历史数据...")

            total_records = 0
            batch_records = []

            for i, point in enumerate(points):
                records = self.generate_point_history(point, total_hours)

                for r in records:
                    batch_records.append(PointHistory(**r))

                    if len(batch_records) >= batch_size:
                        session.add_all(batch_records)
                        await session.commit()
                        total_records += len(batch_records)
                        print(f"  已写入 {total_records} 条记录...")
                        batch_records = []

                if (i + 1) % 50 == 0:
                    print(f"  已处理 {i+1}/{len(points)} 个点位")

            # 写入剩余记录
            if batch_records:
                session.add_all(batch_records)
                await session.commit()
                total_records += len(batch_records)

            print(f"历史数据生成完成，共 {total_records} 条记录")

    async def generate_energy_history(self):
        """生成能耗历史数据"""
        async with async_session() as session:
            print("生成能耗历史数据...")

            for day_offset in range(self.days):
                record_date = (self.base_time - timedelta(days=day_offset)).date()

                for hour in range(24):
                    record_time = datetime.combine(record_date, datetime.min.time()) + timedelta(hours=hour)

                    # 基础功率 + 日内波动
                    it_power = self.generate_daily_pattern(hour, 150, 20)
                    cooling_power = it_power * 0.35  # 制冷功率约为IT功率的35%
                    other_power = 20 + random.uniform(-5, 5)  # 其他功率
                    total_power = it_power + cooling_power + other_power

                    # PUE计算
                    pue = total_power / it_power if it_power > 0 else 1.5

                    # 创建PUE历史
                    pue_record = PUEHistory(
                        total_power=round(total_power, 2),
                        it_power=round(it_power, 2),
                        cooling_power=round(cooling_power, 2),
                        other_power=round(other_power, 2),
                        pue=round(pue, 3),
                        record_time=record_time,
                    )
                    session.add(pue_record)

                # 每天提交一次
                await session.commit()
                if (day_offset + 1) % 5 == 0:
                    print(f"  已生成 {day_offset+1}/{self.days} 天能耗数据")

            print("能耗历史数据生成完成")


async def run_history_generation(days: int = 30):
    """运行历史数据生成"""
    generator = HistoryGenerator(days=days)
    await generator.generate_all_history()
    await generator.generate_energy_history()


if __name__ == "__main__":
    asyncio.run(run_history_generation())
