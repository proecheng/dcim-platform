"""
实时调度调整服务
监控当前功率，预测需量超标风险，触发紧急调整
"""
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
import random


class AlertLevel(Enum):
    """预警级别"""
    NORMAL = 'normal'      # 正常 < 85%
    ATTENTION = 'attention'  # 关注 85-90%
    WARNING = 'warning'    # 预警 90-95%
    CRITICAL = 'critical'  # 临界 95-100%
    EXCEEDED = 'exceeded'  # 超标 > 100%


class AdjustmentAction(Enum):
    """调整动作类型"""
    CURTAIL = 'curtail'        # 削减负荷
    DISCHARGE = 'discharge'    # 储能放电
    SHIFT = 'shift'            # 延迟启动
    RESTORE = 'restore'        # 恢复运行


@dataclass
class PowerReading:
    """功率读数"""
    timestamp: datetime
    power: float  # kW
    source: str = 'meter'


@dataclass
class DemandPrediction:
    """需量预测结果"""
    current_window_avg: float      # 当前窗口平均功率
    predicted_window_avg: float    # 预测窗口结束时平均功率
    time_remaining: int            # 窗口剩余秒数
    demand_target: float           # 需量目标
    utilization_ratio: float       # 利用率
    alert_level: AlertLevel        # 预警级别
    trend: str                     # 趋势: up/down/stable
    risk_score: float              # 风险评分 0-100


@dataclass
class AdjustmentCommand:
    """调整指令"""
    id: str
    action: AdjustmentAction
    device_id: Optional[int]
    device_name: str
    power_change: float           # 功率变化量 (kW, 正数表示减少)
    duration: int                 # 持续时间 (秒)
    priority: int                 # 优先级 1-10
    reason: str
    status: str = 'pending'       # pending/executing/completed/failed
    created_at: datetime = field(default_factory=datetime.now)
    executed_at: Optional[datetime] = None


class RealtimeDispatchController:
    """实时调度控制器"""

    # 15分钟窗口 = 900秒
    WINDOW_SIZE = 900

    # 预警阈值
    THRESHOLDS = {
        AlertLevel.ATTENTION: 0.85,
        AlertLevel.WARNING: 0.90,
        AlertLevel.CRITICAL: 0.95,
        AlertLevel.EXCEEDED: 1.00,
    }

    def __init__(
        self,
        demand_target: float = 800.0,
        on_alert: Optional[Callable[[DemandPrediction], None]] = None,
        on_command: Optional[Callable[[AdjustmentCommand], None]] = None
    ):
        """
        初始化控制器

        Args:
            demand_target: 需量目标 (kW)
            on_alert: 预警回调函数
            on_command: 指令回调函数
        """
        self.demand_target = demand_target
        self.on_alert = on_alert
        self.on_command = on_command

        # 功率读数缓存 (最近15分钟)
        self.power_readings: List[PowerReading] = []

        # 可调度资源
        self.curtailable_devices: List[Dict] = []
        self.storage_available: float = 0  # 可用放电功率
        self.storage_soc: float = 0.5

        # 已执行的调整指令
        self.active_commands: List[AdjustmentCommand] = []
        self.command_history: List[AdjustmentCommand] = []

        # 状态
        self.is_running = False
        self.last_prediction: Optional[DemandPrediction] = None

    def add_power_reading(self, power: float, timestamp: Optional[datetime] = None) -> DemandPrediction:
        """
        添加功率读数并返回预测结果

        Args:
            power: 当前功率 (kW)
            timestamp: 时间戳，默认当前时间

        Returns:
            需量预测结果
        """
        if timestamp is None:
            timestamp = datetime.now()

        reading = PowerReading(timestamp=timestamp, power=power)
        self.power_readings.append(reading)

        # 清理过期读数
        self._cleanup_old_readings(timestamp)

        # 计算预测
        prediction = self._calculate_prediction(timestamp)
        self.last_prediction = prediction

        # 触发预警回调
        if self.on_alert and prediction.alert_level != AlertLevel.NORMAL:
            self.on_alert(prediction)

        # 自动触发调整
        if prediction.alert_level in [AlertLevel.CRITICAL, AlertLevel.EXCEEDED]:
            self._trigger_automatic_adjustment(prediction)

        return prediction

    def _cleanup_old_readings(self, current_time: datetime):
        """清理15分钟窗口外的读数"""
        cutoff = current_time - timedelta(seconds=self.WINDOW_SIZE)
        self.power_readings = [r for r in self.power_readings if r.timestamp >= cutoff]

    def _calculate_prediction(self, current_time: datetime) -> DemandPrediction:
        """计算需量预测"""
        if not self.power_readings:
            return DemandPrediction(
                current_window_avg=0,
                predicted_window_avg=0,
                time_remaining=self.WINDOW_SIZE,
                demand_target=self.demand_target,
                utilization_ratio=0,
                alert_level=AlertLevel.NORMAL,
                trend='stable',
                risk_score=0
            )

        # 计算当前窗口平均
        window_start = current_time - timedelta(seconds=self.WINDOW_SIZE)
        window_readings = [r for r in self.power_readings if r.timestamp >= window_start]

        if window_readings:
            current_avg = sum(r.power for r in window_readings) / len(window_readings)
        else:
            current_avg = self.power_readings[-1].power

        # 计算窗口剩余时间
        # 假设窗口从整点开始，每15分钟一个窗口
        minutes_in_day = current_time.hour * 60 + current_time.minute
        window_minute = minutes_in_day % 15
        time_remaining = (15 - window_minute) * 60 - current_time.second

        # 预测窗口结束时的平均功率
        # 简单线性外推：假设当前功率保持到窗口结束
        current_power = self.power_readings[-1].power

        # 计算趋势
        if len(self.power_readings) >= 3:
            recent_powers = [r.power for r in self.power_readings[-3:]]
            if recent_powers[-1] > recent_powers[0] * 1.02:
                trend = 'up'
            elif recent_powers[-1] < recent_powers[0] * 0.98:
                trend = 'down'
            else:
                trend = 'stable'
        else:
            trend = 'stable'

        # 预测值：加权平均（已有数据 + 预测保持当前功率）
        elapsed_seconds = self.WINDOW_SIZE - time_remaining
        if elapsed_seconds > 0:
            predicted_avg = (
                current_avg * elapsed_seconds + current_power * time_remaining
            ) / self.WINDOW_SIZE
        else:
            predicted_avg = current_power

        # 如果趋势上升，增加预测值
        if trend == 'up':
            predicted_avg *= 1.02

        # 计算利用率
        utilization = predicted_avg / self.demand_target if self.demand_target > 0 else 0

        # 判断预警级别
        alert_level = AlertLevel.NORMAL
        for level, threshold in sorted(self.THRESHOLDS.items(), key=lambda x: x[1], reverse=True):
            if utilization >= threshold:
                alert_level = level
                break

        # 计算风险评分
        risk_score = min(100, utilization * 100)
        if trend == 'up':
            risk_score += 5
        if time_remaining < 300:  # 最后5分钟风险更高
            risk_score += 10

        return DemandPrediction(
            current_window_avg=round(current_avg, 2),
            predicted_window_avg=round(predicted_avg, 2),
            time_remaining=max(0, time_remaining),
            demand_target=self.demand_target,
            utilization_ratio=round(utilization * 100, 2),
            alert_level=alert_level,
            trend=trend,
            risk_score=min(100, round(risk_score, 1))
        )

    def _trigger_automatic_adjustment(self, prediction: DemandPrediction):
        """触发自动调整"""
        # 计算需要削减的功率
        excess_power = prediction.predicted_window_avg - self.demand_target * 0.95

        if excess_power <= 0:
            return

        commands = []

        # 优先使用储能放电
        if self.storage_available > 0 and self.storage_soc > 0.2:
            discharge_power = min(self.storage_available, excess_power)
            cmd = AdjustmentCommand(
                id=f"cmd_{datetime.now().strftime('%Y%m%d%H%M%S')}_storage",
                action=AdjustmentAction.DISCHARGE,
                device_id=None,
                device_name="储能系统",
                power_change=discharge_power,
                duration=prediction.time_remaining + 60,  # 持续到窗口结束后1分钟
                priority=1,
                reason=f"需量预警，储能放电削减 {discharge_power:.1f} kW"
            )
            commands.append(cmd)
            excess_power -= discharge_power

        # 其次削减可削减设备
        for device in sorted(self.curtailable_devices, key=lambda x: x.get('priority', 5)):
            if excess_power <= 0:
                break

            curtail_power = min(
                device.get('rated_power', 0) * device.get('curtail_ratio', 0.5),
                excess_power
            )

            if curtail_power > 0:
                cmd = AdjustmentCommand(
                    id=f"cmd_{datetime.now().strftime('%Y%m%d%H%M%S')}_{device.get('id', 0)}",
                    action=AdjustmentAction.CURTAIL,
                    device_id=device.get('id'),
                    device_name=device.get('name', 'Unknown'),
                    power_change=curtail_power,
                    duration=prediction.time_remaining + 60,
                    priority=device.get('priority', 5),
                    reason=f"需量预警，削减 {curtail_power:.1f} kW"
                )
                commands.append(cmd)
                excess_power -= curtail_power

        # 记录并执行指令
        for cmd in commands:
            self.active_commands.append(cmd)
            if self.on_command:
                self.on_command(cmd)

    def set_curtailable_devices(self, devices: List[Dict]):
        """设置可削减设备列表"""
        self.curtailable_devices = devices

    def set_storage_status(self, available_power: float, soc: float):
        """设置储能状态"""
        self.storage_available = available_power
        self.storage_soc = soc

    def create_manual_command(
        self,
        action: AdjustmentAction,
        device_id: Optional[int],
        device_name: str,
        power_change: float,
        duration: int,
        reason: str = "手动调整"
    ) -> AdjustmentCommand:
        """创建手动调整指令"""
        cmd = AdjustmentCommand(
            id=f"manual_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            action=action,
            device_id=device_id,
            device_name=device_name,
            power_change=power_change,
            duration=duration,
            priority=1,
            reason=reason
        )
        self.active_commands.append(cmd)
        if self.on_command:
            self.on_command(cmd)
        return cmd

    def complete_command(self, command_id: str, success: bool = True):
        """完成指令"""
        for cmd in self.active_commands:
            if cmd.id == command_id:
                cmd.status = 'completed' if success else 'failed'
                cmd.executed_at = datetime.now()
                self.command_history.append(cmd)
                self.active_commands.remove(cmd)
                break

    def get_status(self) -> Dict:
        """获取当前状态"""
        return {
            'demand_target': self.demand_target,
            'last_prediction': {
                'current_window_avg': self.last_prediction.current_window_avg if self.last_prediction else 0,
                'predicted_window_avg': self.last_prediction.predicted_window_avg if self.last_prediction else 0,
                'utilization_ratio': self.last_prediction.utilization_ratio if self.last_prediction else 0,
                'alert_level': self.last_prediction.alert_level.value if self.last_prediction else 'normal',
                'time_remaining': self.last_prediction.time_remaining if self.last_prediction else 0,
                'trend': self.last_prediction.trend if self.last_prediction else 'stable',
                'risk_score': self.last_prediction.risk_score if self.last_prediction else 0,
            } if self.last_prediction else None,
            'active_commands': [
                {
                    'id': cmd.id,
                    'action': cmd.action.value,
                    'device_name': cmd.device_name,
                    'power_change': cmd.power_change,
                    'status': cmd.status,
                    'reason': cmd.reason,
                }
                for cmd in self.active_commands
            ],
            'storage_available': self.storage_available,
            'storage_soc': self.storage_soc,
            'curtailable_devices_count': len(self.curtailable_devices),
        }


# 全局控制器实例（单例模式）
_controller_instance: Optional[RealtimeDispatchController] = None


def get_dispatch_controller(demand_target: float = 800.0) -> RealtimeDispatchController:
    """获取调度控制器实例"""
    global _controller_instance
    if _controller_instance is None:
        _controller_instance = RealtimeDispatchController(demand_target=demand_target)
    return _controller_instance


def simulate_realtime_monitoring(duration_minutes: int = 5) -> List[Dict]:
    """
    模拟实时监控（用于演示）

    Args:
        duration_minutes: 模拟时长（分钟）

    Returns:
        模拟结果列表
    """
    controller = get_dispatch_controller(demand_target=800.0)

    # 设置可削减设备
    controller.set_curtailable_devices([
        {'id': 1, 'name': '空调系统-1', 'rated_power': 50, 'curtail_ratio': 0.3, 'priority': 3},
        {'id': 2, 'name': '照明系统-2', 'rated_power': 30, 'curtail_ratio': 0.5, 'priority': 5},
        {'id': 3, 'name': '通风设备-3', 'rated_power': 40, 'curtail_ratio': 0.4, 'priority': 4},
    ])
    controller.set_storage_status(available_power=100, soc=0.6)

    results = []
    base_power = 700  # 基础负荷

    for i in range(duration_minutes * 4):  # 每15秒一个点
        # 模拟功率波动
        noise = random.gauss(0, 30)
        trend = 50 * (i / (duration_minutes * 4))  # 逐渐上升
        power = base_power + trend + noise

        timestamp = datetime.now() + timedelta(seconds=i * 15)
        prediction = controller.add_power_reading(power, timestamp)

        results.append({
            'timestamp': timestamp.isoformat(),
            'power': round(power, 2),
            'prediction': {
                'current_window_avg': prediction.current_window_avg,
                'predicted_window_avg': prediction.predicted_window_avg,
                'utilization_ratio': prediction.utilization_ratio,
                'alert_level': prediction.alert_level.value,
                'risk_score': prediction.risk_score,
            }
        })

    return results
