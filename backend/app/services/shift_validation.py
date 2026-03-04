"""
功率转移前安全性模拟验证

在执行功率转移前，模拟转移后的系统状态，验证是否安全。
"""
from typing import Dict, List, Optional
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..models.energy import PowerDevice
from ..models.history import PointHistory
from .datacenter_shift_strategy import (
    calculate_shift_recommendation,
    TEMP_WARNING,
    PUE_MAX,
    PUE_MIN
)


@dataclass
class ValidationResult:
    """验证结果"""
    is_safe: bool
    warnings: List[str]
    errors: List[str]
    projected_state: Dict
    
    def __init__(self):
        self.is_safe = True
        self.warnings = []
        self.errors = []
        self.projected_state = {}


async def validate_shift_plan(
    session: AsyncSession,
    shift_plan: Dict[int, float]  # device_id -> reduction_ratio
) -> ValidationResult:
    """
    验证功率转移计划的安全性
    
    Args:
        session: 数据库会话
        shift_plan: 转移计划 {device_id: reduction_ratio}
    
    Returns:
        ValidationResult: 验证结果
    """
    result = ValidationResult()
    
    try:
        # 1. 加载当前系统状态
        current_state = await _load_current_state(session)
        result.projected_state['current'] = current_state
        
        # 2. 模拟功率转移
        projected_state = await _simulate_power_shift(
            session, current_state, shift_plan
        )
        result.projected_state['projected'] = projected_state
        
        # 3. 验证温度约束
        temp_violations = _check_temperature_violations(projected_state)
        if temp_violations:
            result.errors.extend(temp_violations)
            result.is_safe = False
        
        # 4. 验证冗余约束
        redundancy_violations = _check_redundancy_violations(projected_state)
        if redundancy_violations:
            result.errors.extend(redundancy_violations)
            result.is_safe = False
        
        # 5. 验证PUE约束
        pue_violations = _check_pue_violations(projected_state)
        if pue_violations:
            result.warnings.extend(pue_violations)
            # PUE违规是警告，不阻止执行
        
        # 6. 生成总结
        if result.is_safe:
            result.warnings.append(
                f"验证通过：{len(shift_plan)}个设备的功率转移计划安全"
            )
        else:
            result.errors.append(
                f"验证失败：发现{len(result.errors)}个安全问题"
            )
        
    except Exception as e:
        result.is_safe = False
        result.errors.append(f"验证过程失败: {str(e)}")
    
    return result


async def _load_current_state(session: AsyncSession) -> Dict:
    """加载当前系统状态"""
    state = {
        'devices': {},
        'total_power': 0.0,
        'it_power': 0.0,
        'cooling_power': 0.0,
        'pue': 0.0
    }
    
    # 查询所有设备
    devices_query = select(PowerDevice).where(PowerDevice.is_enabled == True)
    devices_result = await session.execute(devices_query)
    devices = devices_result.scalars().all()
    
    for device in devices:
        device_state = {
            'id': device.id,
            'name': device.device_name,
            'type': device.device_type,
            'rated_power': device.rated_power or 0.0,
            'current_power': 0.0
        }
        
        # 获取当前功率
        if device.power_point_id:
            power_query = select(PointHistory).where(
                PointHistory.point_id == device.power_point_id
            ).order_by(PointHistory.recorded_at.desc()).limit(1)
            power_result = await session.execute(power_query)
            latest_power = power_result.scalar_one_or_none()
            
            if latest_power and latest_power.value is not None:
                device_state['current_power'] = float(latest_power.value)
        
        state['devices'][device.id] = device_state
        state['total_power'] += device_state['current_power']
        
        if device.is_it_load:
            state['it_power'] += device_state['current_power']
        elif device.device_type in ['AC', 'CHILLER', 'COOLING_TOWER', 'HVAC']:
            state['cooling_power'] += device_state['current_power']
    
    # 计算PUE
    if state['it_power'] > 0:
        state['pue'] = state['total_power'] / state['it_power']
    
    return state


async def _simulate_power_shift(
    session: AsyncSession,
    current_state: Dict,
    shift_plan: Dict[int, float]
) -> Dict:
    """模拟功率转移后的状态"""
    projected_state = {
        'devices': {},
        'total_power': 0.0,
        'it_power': 0.0,
        'cooling_power': 0.0,
        'pue': 0.0,
        'temperature_rise': {}
    }
    
    for device_id, device_state in current_state['devices'].items():
        new_state = device_state.copy()
        
        # 应用转移计划
        if device_id in shift_plan:
            reduction_ratio = shift_plan[device_id]
            new_state['current_power'] *= (1 - reduction_ratio)
            new_state['reduction_ratio'] = reduction_ratio
        else:
            new_state['reduction_ratio'] = 0.0
        
        projected_state['devices'][device_id] = new_state
        projected_state['total_power'] += new_state['current_power']
        
        # 分类统计
        if device_state['type'] in ['IT_SERVER', 'IT_STORAGE', 'NETWORK_SWITCH']:
            projected_state['it_power'] += new_state['current_power']
        elif device_state['type'] in ['AC', 'CHILLER', 'COOLING_TOWER', 'HVAC']:
            projected_state['cooling_power'] += new_state['current_power']
            
            # 估算温度上升
            if device_id in shift_plan:
                # 简化模型：功率降低10%，温度上升约1℃
                temp_rise = shift_plan[device_id] * 10.0
                projected_state['temperature_rise'][device_id] = temp_rise
    
    # 计算预测PUE
    if projected_state['it_power'] > 0:
        projected_state['pue'] = projected_state['total_power'] / projected_state['it_power']
    
    return projected_state


def _check_temperature_violations(projected_state: Dict) -> List[str]:
    """检查温度违规"""
    violations = []
    
    for device_id, temp_rise in projected_state.get('temperature_rise', {}).items():
        # 假设当前温度为25℃（实际应该从传感器读取）
        current_temp = 25.0
        projected_temp = current_temp + temp_rise
        
        if projected_temp > TEMP_WARNING:
            device = projected_state['devices'].get(device_id, {})
            violations.append(
                f"设备 {device.get('name', device_id)} 预测温度 {projected_temp:.1f}℃ "
                f"超过警告阈值 {TEMP_WARNING}℃"
            )
    
    return violations


def _check_redundancy_violations(projected_state: Dict) -> List[str]:
    """检查冗余违规"""
    violations = []
    
    # 按设备类型和区域分组
    device_groups = {}
    for device_id, device_state in projected_state['devices'].items():
        device_type = device_state['type']
        if device_type in ['AC', 'UPS', 'CHILLER']:
            key = device_type  # 简化：只按类型分组
            if key not in device_groups:
                device_groups[key] = []
            device_groups[key].append(device_state)
    
    # 检查每组的N+1冗余
    for group_key, devices in device_groups.items():
        if len(devices) < 2:
            continue  # 单台设备无法验证冗余
        
        total_capacity = sum(d['rated_power'] for d in devices)
        total_load = sum(d['current_power'] for d in devices)
        
        # N+1容量 = (N-1) × 平均容量 × 0.9
        n = len(devices)
        avg_capacity = total_capacity / n
        n_plus_one_capacity = (n - 1) * avg_capacity * 0.9
        
        if total_load > n_plus_one_capacity:
            violations.append(
                f"{group_key} 设备组 N+1 冗余不足：负载 {total_load:.1f}kW "
                f"> N+1容量 {n_plus_one_capacity:.1f}kW"
            )
    
    return violations


def _check_pue_violations(projected_state: Dict) -> List[str]:
    """检查PUE违规"""
    violations = []
    
    pue = projected_state.get('pue', 0.0)
    
    if pue > PUE_MAX:
        violations.append(
            f"预测PUE {pue:.2f} 超过最大值 {PUE_MAX}"
        )
    elif pue < PUE_MIN and pue > 0:
        violations.append(
            f"预测PUE {pue:.2f} 低于最小值 {PUE_MIN}，可能制冷不足"
        )
    
    return violations
