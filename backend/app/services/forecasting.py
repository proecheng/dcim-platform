"""
负荷预测服务模块
基于历史数据预测未来24小时负荷曲线
"""
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import random


class LoadForecaster:
    """负荷预测器"""

    # 典型负荷曲线模式（24小时，每小时一个比例系数）
    # 工作日模式
    WORKDAY_PATTERN = [
        0.40, 0.35, 0.32, 0.30,  # 0-3点: 深谷
        0.35, 0.45, 0.60, 0.75,  # 4-7点: 谷时上升
        0.85, 0.95, 1.00, 0.98,  # 8-11点: 峰时
        0.90, 0.85, 0.88, 0.90,  # 12-15点: 平时
        0.92, 0.98, 1.00, 0.95,  # 16-19点: 峰时
        0.85, 0.70, 0.55, 0.45,  # 20-23点: 下降
    ]

    # 周末模式
    WEEKEND_PATTERN = [
        0.35, 0.32, 0.30, 0.28,  # 0-3点
        0.30, 0.35, 0.45, 0.55,  # 4-7点
        0.65, 0.70, 0.72, 0.70,  # 8-11点
        0.65, 0.60, 0.62, 0.65,  # 12-15点
        0.68, 0.70, 0.72, 0.68,  # 16-19点
        0.60, 0.50, 0.42, 0.38,  # 20-23点
    ]

    # 季节调整系数
    SEASONAL_FACTORS = {
        1: 1.10,   # 1月: 冬季高峰
        2: 1.08,   # 2月
        3: 1.00,   # 3月: 春季平稳
        4: 0.95,   # 4月
        5: 0.92,   # 5月
        6: 1.05,   # 6月: 夏季开始
        7: 1.15,   # 7月: 夏季高峰
        8: 1.18,   # 8月: 夏季最高
        9: 1.05,   # 9月
        10: 0.95,  # 10月
        11: 1.00,  # 11月
        12: 1.08,  # 12月: 冬季
    }

    def __init__(self, base_load: float = 500.0, peak_load: float = 1000.0):
        """
        初始化预测器

        Args:
            base_load: 基础负荷 (kW)
            peak_load: 峰值负荷 (kW)
        """
        self.base_load = base_load
        self.peak_load = peak_load

    def forecast_day(
        self,
        target_date: datetime,
        historical_data: Optional[List[Dict]] = None,
        noise_level: float = 0.05
    ) -> Dict:
        """
        预测指定日期的24小时负荷曲线

        Args:
            target_date: 目标日期
            historical_data: 历史数据（可选，用于校准）
            noise_level: 噪声水平 (0-1)

        Returns:
            预测结果字典，包含96个15分钟时段的数据
        """
        is_weekend = target_date.weekday() >= 5
        month = target_date.month

        # 选择基础模式
        base_pattern = self.WEEKEND_PATTERN if is_weekend else self.WORKDAY_PATTERN

        # 应用季节系数
        seasonal_factor = self.SEASONAL_FACTORS.get(month, 1.0)

        # 如果有历史数据，计算调整系数
        adjustment_factor = 1.0
        if historical_data and len(historical_data) > 0:
            # 简单计算历史平均负荷与预设的比值
            hist_avg = np.mean([d.get('power', 500) for d in historical_data])
            expected_avg = (self.base_load + self.peak_load) / 2
            adjustment_factor = hist_avg / expected_avg if expected_avg > 0 else 1.0

        # 生成96个15分钟时段的预测
        forecasts = []
        forecast_96 = []

        for hour in range(24):
            base_ratio = base_pattern[hour]

            # 每小时4个15分钟时段
            for quarter in range(4):
                # 计算基础预测值
                predicted_power = (
                    self.base_load +
                    (self.peak_load - self.base_load) * base_ratio *
                    seasonal_factor * adjustment_factor
                )

                # 添加随机噪声
                noise = np.random.normal(0, predicted_power * noise_level)
                predicted_power = max(0, predicted_power + noise)

                # 计算置信区间
                confidence_margin = predicted_power * 0.1  # 10%置信区间

                time_slot = hour * 4 + quarter
                time_str = f"{hour:02d}:{quarter * 15:02d}"

                forecast_96.append({
                    'time_slot': time_slot,
                    'time': time_str,
                    'hour': hour,
                    'quarter': quarter,
                    'predicted_power': round(predicted_power, 2),
                    'lower_bound': round(predicted_power - confidence_margin, 2),
                    'upper_bound': round(predicted_power + confidence_margin, 2),
                    'period': self._get_period(hour)
                })

        # 计算统计信息
        powers = [f['predicted_power'] for f in forecast_96]

        return {
            'date': target_date.strftime('%Y-%m-%d'),
            'is_weekend': is_weekend,
            'seasonal_factor': seasonal_factor,
            'adjustment_factor': round(adjustment_factor, 3),
            'forecasts': forecast_96,
            'statistics': {
                'max_power': round(max(powers), 2),
                'min_power': round(min(powers), 2),
                'avg_power': round(np.mean(powers), 2),
                'total_energy': round(sum(powers) * 0.25, 2),  # kWh (15分钟=0.25小时)
            },
            'period_summary': self._calculate_period_summary(forecast_96)
        }

    def _get_period(self, hour: int) -> str:
        """根据小时获取时段类型"""
        if hour in [11, 18]:
            return 'sharp'  # 尖峰
        elif hour in [9, 10, 12, 13, 17, 19, 20]:
            return 'peak'  # 峰
        elif hour in [8, 14, 15, 16, 21]:
            return 'flat'  # 平
        elif hour in [4, 5, 6, 7, 22, 23]:
            return 'valley'  # 谷
        else:
            return 'deep_valley'  # 深谷 (0-3)

    def _calculate_period_summary(self, forecasts: List[Dict]) -> Dict:
        """计算各时段汇总"""
        period_data = {
            'sharp': {'energy': 0, 'max_power': 0, 'hours': 0},
            'peak': {'energy': 0, 'max_power': 0, 'hours': 0},
            'flat': {'energy': 0, 'max_power': 0, 'hours': 0},
            'valley': {'energy': 0, 'max_power': 0, 'hours': 0},
            'deep_valley': {'energy': 0, 'max_power': 0, 'hours': 0},
        }

        for f in forecasts:
            period = f['period']
            power = f['predicted_power']
            period_data[period]['energy'] += power * 0.25  # 15分钟的电量
            period_data[period]['max_power'] = max(period_data[period]['max_power'], power)
            period_data[period]['hours'] += 0.25

        # 四舍五入
        for period in period_data:
            period_data[period]['energy'] = round(period_data[period]['energy'], 2)
            period_data[period]['max_power'] = round(period_data[period]['max_power'], 2)

        return period_data

    def forecast_with_devices(
        self,
        target_date: datetime,
        base_forecast: Dict,
        dispatchable_devices: List[Dict]
    ) -> Dict:
        """
        考虑可调度设备的负荷预测

        Args:
            target_date: 目标日期
            base_forecast: 基础预测结果
            dispatchable_devices: 可调度设备列表

        Returns:
            包含设备影响的预测结果
        """
        # 复制基础预测
        forecasts = [f.copy() for f in base_forecast['forecasts']]

        # 分离可调度负荷和刚性负荷
        shiftable_load = np.zeros(96)
        rigid_load = np.array([f['predicted_power'] for f in forecasts])

        for device in dispatchable_devices:
            device_type = device.get('device_type', 'rigid')
            rated_power = device.get('rated_power', 0)

            if device_type == 'shiftable':
                # 时移型负荷：标记为可调度
                run_duration = device.get('run_duration', 2)  # 小时
                daily_runs = device.get('daily_runs', 1)

                # 简化：假设当前运行在默认时段
                default_start = 9  # 默认9点开始
                slots = int(run_duration * 4)  # 15分钟时段数

                for run in range(daily_runs):
                    start_slot = (default_start + run * 4) * 4
                    for i in range(slots):
                        if start_slot + i < 96:
                            shiftable_load[start_slot + i] += rated_power
                            rigid_load[start_slot + i] -= rated_power

        # 更新预测结果
        for i, f in enumerate(forecasts):
            f['rigid_load'] = round(max(0, rigid_load[i]), 2)
            f['shiftable_load'] = round(shiftable_load[i], 2)
            f['total_load'] = round(rigid_load[i] + shiftable_load[i], 2)

        return {
            **base_forecast,
            'forecasts': forecasts,
            'has_dispatchable': True,
            'total_shiftable_energy': round(sum(shiftable_load) * 0.25, 2)
        }


async def get_load_forecast(
    db: AsyncSession,
    target_date: datetime,
    meter_point_id: Optional[int] = None
) -> Dict:
    """
    获取负荷预测（API服务入口）

    Args:
        db: 数据库会话
        target_date: 目标日期
        meter_point_id: 计量点ID（可选）

    Returns:
        预测结果
    """
    # 尝试从历史数据获取基准负荷
    # 这里简化处理，使用默认值
    base_load = 300.0
    peak_load = 800.0

    # TODO: 从数据库查询历史数据来调整基准
    # 可以查询过去30天的同类型日期数据

    forecaster = LoadForecaster(base_load=base_load, peak_load=peak_load)
    forecast = forecaster.forecast_day(target_date)

    return forecast


def generate_demo_forecast(target_date: Optional[datetime] = None) -> Dict:
    """
    生成演示用的预测数据

    Args:
        target_date: 目标日期，默认为明天

    Returns:
        预测结果
    """
    if target_date is None:
        target_date = datetime.now() + timedelta(days=1)

    forecaster = LoadForecaster(base_load=350.0, peak_load=850.0)
    return forecaster.forecast_day(target_date, noise_level=0.03)
