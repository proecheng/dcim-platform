"""
数据中心功率转移策略算法 - 温度感知版本

针对数据中心场景的功率转移策略，考虑：
1. 温度约束 - 机柜温度不超限（ASHRAE 18-27℃）
2. N+1 冗余约束 - 确保设备故障时系统仍可运行
3. PUE 约束 - 保持数据中心能效在合理范围
4. 设备特性约束 - 启停特性、最小运行时间等
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.energy import PowerDevice
from ..models.asset import Cabinet
from ..models.cooling import CoolingUnit
from ..models.point import Point
from ..models.history import PointHistory
from ..models.topology_config import CoolingZone, CoolingZoneUnit, CoolingZoneCabinet, CabinetTemperatureSensor, CabinetITLoad


# ==================== 常量定义 ====================

# 温度限制（ASHRAE TC 9.9 标准）
TEMP_RECOMMENDED_MIN = 18.0  # 推荐最低温度 ℃
TEMP_RECOMMENDED_MAX = 27.0  # 推荐最高温度 ℃
TEMP_ALLOWABLE_MIN = 15.0    # 允许最低温度 ℃
TEMP_ALLOWABLE_MAX = 32.0    # 允许最高温度 ℃
TEMP_WARNING = 27.0          # 告警阈值 ℃
TEMP_CRITICAL = 30.0         # 严重告警阈值 ℃
TEMP_SAFETY_MARGIN = 2.0     # 安全裕度 ℃

# 设备类型
COOLING_DEVICES = {'AC', 'CHILLER', 'COOLING_TOWER', 'HVAC', 'CRAC', 'CRAH'}
NON_SHIFTABLE_DEVICES = {'UPS', 'IT_SERVER', 'IT_STORAGE', 'NETWORK_SWITCH', 'CORE_ROUTER'}
SHIFTABLE_DEVICES = {'LIGHTING', 'OFFICE_AC', 'WATER_PUMP', 'FAN'}

# 冗余配置
REDUNDANCY_TYPE = 'N+1'      # 冗余类型
SAFETY_FACTOR = 0.9          # 安全系数（90%）

# PUE 约束
PUE_TARGET = 1.5             # 目标 PUE
PUE_MAX = 2.0                # 最大允许 PUE
PUE_MIN = 1.2                # 最小允许 PUE（过低可能意味着制冷不足）


# ==================== 数据结构 ====================

class TemperatureConstraint:
    """温度约束结果"""
    def __init__(self):
        self.max_reduction_ratio = 1.0  # 最大可降低比例
        self.affected_cabinets = []     # 受影响的机柜
        self.current_temps = {}         # 当前温度
        self.predicted_temps = {}       # 预测温度
        self.is_safe = True             # 是否安全
        self.reason = ""                # 原因说明


class RedundancyConstraint:
    """冗余约束结果"""
    def __init__(self):
        self.max_reduction_ratio = 1.0  # 最大可降低比例
        self.redundancy_group = []      # 冗余组设备
        self.total_capacity = 0.0       # 总容量
        self.current_load = 0.0         # 当前负载
        self.n_plus_one_capacity = 0.0  # N+1 容量
        self.is_safe = True             # 是否安全
        self.reason = ""                # 原因说明


class PUEConstraint:
    """PUE 约束结果"""
    def __init__(self):
        self.max_reduction_ratio = 1.0  # 最大可降低比例
        self.current_pue = 0.0          # 当前 PUE
        self.predicted_pue = 0.0        # 预测 PUE
        self.it_load = 0.0              # IT 负载
        self.cooling_load = 0.0         # 制冷负载
        self.is_safe = True             # 是否安全
        self.reason = ""                # 原因说明


class ShiftRecommendation:
    """转移建议结果"""
    def __init__(self):
        self.recommended_ratio = 0.0    # 推荐转移比例
        self.constraints = {}           # 各约束结果
        self.limiting_factor = ""       # 限制因素
        self.confidence = 0.0           # 置信度
        self.warnings = []              # 警告信息
        self.details = {}               # 详细信息


# ==================== 核心算法 ====================

async def calculate_shift_recommendation(
    session: AsyncSession,
    device: PowerDevice,
    target_reduction_ratio: float = 0.3
) -> ShiftRecommendation:
    """
    计算设备功率转移建议（数据中心版本）
    
    Args:
        session: 数据库会话
        device: 目标设备
        target_reduction_ratio: 目标降低比例（0-1）
    
    Returns:
        ShiftRecommendation: 转移建议
    """
    result = ShiftRecommendation()
    
    # 1. 检查设备是否可转移
    if device.device_type in NON_SHIFTABLE_DEVICES:
        result.recommended_ratio = 0.0
        result.limiting_factor = "non_shiftable_device"
        result.warnings.append(f"设备类型 {device.device_type} 不可转移")
        return result
    
    # 2. 计算各类约束
    constraints = {}
    
    # 2.1 温度约束（仅对制冷设备）
    if device.device_type in COOLING_DEVICES:
        temp_constraint = await _calculate_temperature_constraint(session, device, target_reduction_ratio)
        constraints['temperature'] = temp_constraint
    
    # 2.2 N+1 冗余约束（仅对关键设备）
    if device.device_type in COOLING_DEVICES or device.device_type == 'UPS':
        redundancy_constraint = await _calculate_redundancy_constraint(session, device, target_reduction_ratio)
        constraints['redundancy'] = redundancy_constraint
    
    # 2.3 PUE 约束（仅对制冷设备）
    if device.device_type in COOLING_DEVICES:
        pue_constraint = await _calculate_pue_constraint(session, device, target_reduction_ratio)
        constraints['pue'] = pue_constraint
    
    # 2.4 设备特性约束
    device_constraint = await _calculate_device_constraint(session, device, target_reduction_ratio)
    constraints['device'] = device_constraint
    
    # 3. 综合约束，取最小值
    min_ratio = target_reduction_ratio
    limiting_factor = "target"
    
    for constraint_name, constraint in constraints.items():
        if hasattr(constraint, 'max_reduction_ratio'):
            if constraint.max_reduction_ratio < min_ratio:
                min_ratio = constraint.max_reduction_ratio
                limiting_factor = constraint_name
    
    # 4. 填充结果
    result.recommended_ratio = min_ratio
    result.constraints = constraints
    result.limiting_factor = limiting_factor
    result.confidence = _calculate_confidence(constraints)
    
    # 5. 生成警告信息
    for constraint_name, constraint in constraints.items():
        if hasattr(constraint, 'is_safe') and not constraint.is_safe:
            result.warnings.append(f"{constraint_name}: {constraint.reason}")
    
    # 6. 填充详细信息
    result.details = {
        'device_id': device.id,
        'device_name': device.device_name,
        'device_type': device.device_type,
        'target_reduction_ratio': target_reduction_ratio,
        'recommended_ratio': min_ratio,
        'limiting_factor': limiting_factor,
        'constraints_summary': {
            name: {
                'max_ratio': getattr(c, 'max_reduction_ratio', None),
                'is_safe': getattr(c, 'is_safe', None),
                'reason': getattr(c, 'reason', None)
            }
            for name, c in constraints.items()
        }
    }
    
    return result


async def _calculate_temperature_constraint(
    session: AsyncSession,
    device: PowerDevice,
    target_reduction_ratio: float
) -> TemperatureConstraint:
    """
    计算温度约束（使用新数据模型）
    
    对于空调设备，降低功率会导致制冷能力下降，机柜温度上升。
    需要确保所有受影响的机柜温度不超过 ASHRAE 推荐上限（27℃）。
    
    算法：
    1. 通过 CoolingZoneUnit 查找该空调服务的制冷区域
    2. 通过 CoolingZoneCabinet 查找区域内的机柜
    3. 通过 CabinetTemperatureSensor 获取机柜当前温度
    4. 估算功率降低后的温度上升
    5. 确保所有机柜温度 < 27℃ - 安全裕度
    """
    constraint = TemperatureConstraint()
    
    try:
        # 1. 查找该设备关联的制冷单元
        cooling_unit_query = select(CoolingUnit).where(CoolingUnit.device_id == device.id)
        cooling_unit_result = await session.execute(cooling_unit_query)
        cooling_unit = cooling_unit_result.scalar_one_or_none()
        
        if not cooling_unit:
            constraint.reason = "未找到制冷单元配置（cooling_units表中无记录）"
            constraint.max_reduction_ratio = 0.5  # 保守估计
            return constraint
        
        # 2. 查找该空调服务的制冷区域
        zone_unit_query = select(CoolingZoneUnit).where(
            CoolingZoneUnit.cooling_unit_id == cooling_unit.id
        )
        zone_unit_result = await session.execute(zone_unit_query)
        zone_units = zone_unit_result.scalars().all()
        
        if not zone_units:
            # 没有配置制冷区域，使用 area_code 作为 fallback
            if device.area_code:
                # 查找同一区域的机柜
                cabinets_query = select(Cabinet).where(
                    Cabinet.area_code == device.area_code
                ).limit(50)
                cabinets_result = await session.execute(cabinets_query)
                cabinets = cabinets_result.scalars().all()
            else:
                constraint.reason = "未配置制冷区域，且设备无 area_code"
                constraint.max_reduction_ratio = 0.5
                return constraint
        else:
            # 通过制冷区域查找机柜
            zone_ids = [zu.zone_id for zu in zone_units]
            zone_cabinet_query = select(CoolingZoneCabinet).where(
                CoolingZoneCabinet.zone_id.in_(zone_ids)
            )
            zone_cabinet_result = await session.execute(zone_cabinet_query)
            zone_cabinets = zone_cabinet_result.scalars().all()
            
            if not zone_cabinets:
                constraint.reason = "制冷区域内无机柜"
                constraint.max_reduction_ratio = 0.5
                return constraint
            
            # 获取机柜对象
            cabinet_ids = [zc.cabinet_id for zc in zone_cabinets]
            cabinets_query = select(Cabinet).where(Cabinet.id.in_(cabinet_ids))
            cabinets_result = await session.execute(cabinets_query)
            cabinets = cabinets_result.scalars().all()
        
        if not cabinets:
            constraint.reason = "未找到关联机柜"
            constraint.max_reduction_ratio = 0.5
            return constraint
        
        # 3. 获取机柜当前温度
        cabinet_temps = {}
        max_current_temp = 0.0
        
        for cabinet in cabinets:
            # 查找该机柜的温度传感器配置
            sensor_query = select(CabinetTemperatureSensor).where(
                and_(
                    CabinetTemperatureSensor.cabinet_id == cabinet.id,
                    CabinetTemperatureSensor.sensor_location == 'inlet'  # 优先使用进风口温度
                )
            )
            sensor_result = await session.execute(sensor_query)
            sensor = sensor_result.scalar_one_or_none()
            
            if not sensor or not sensor.point_id:
                # 尝试 outlet 或 ambient
                sensor_query = select(CabinetTemperatureSensor).where(
                    CabinetTemperatureSensor.cabinet_id == cabinet.id
                ).limit(1)
                sensor_result = await session.execute(sensor_query)
                sensor = sensor_result.scalar_one_or_none()
            
            if sensor and sensor.point_id:
                # 获取最新温度值
                latest_temp_query = select(PointHistory).where(
                    PointHistory.point_id == sensor.point_id
                ).order_by(PointHistory.recorded_at.desc()).limit(1)
                latest_temp_result = await session.execute(latest_temp_query)
                latest_temp = latest_temp_result.scalar_one_or_none()
                
                if latest_temp and latest_temp.value is not None:
                    current_temp = float(latest_temp.value)
                    cabinet_temps[cabinet.id] = current_temp
                    max_current_temp = max(max_current_temp, current_temp)
        
        if not cabinet_temps:
            constraint.reason = "未找到机柜温度数据（请配置 CabinetTemperatureSensor）"
            constraint.max_reduction_ratio = 0.3
            return constraint
        
        # 4. 估算温度上升
        cooling_capacity_kw = cooling_unit.cooling_capacity_kw or 100.0
        
        # 计算最大允许温升
        max_allowed_temp = TEMP_WARNING - TEMP_SAFETY_MARGIN  # 27 - 2 = 25℃
        max_temp_rise = max_allowed_temp - max_current_temp
        
        if max_temp_rise <= 0:
            constraint.is_safe = False
            constraint.reason = f"当前最高温度 {max_current_temp:.1f}℃ 已接近上限，不可降低制冷功率"
            constraint.max_reduction_ratio = 0.0
            constraint.current_temps = cabinet_temps
            return constraint
        
        # 估算功率降低导致的温升
        # 假设：功率降低 10%，温度上升约 1℃（经验值）
        temp_rise_per_10pct = 1.0  # ℃
        predicted_temp_rise = target_reduction_ratio * 10 * temp_rise_per_10pct
        
        # 计算最大允许降低比例
        if predicted_temp_rise > max_temp_rise:
            safe_ratio = (max_temp_rise / temp_rise_per_10pct) / 10.0
            constraint.max_reduction_ratio = max(0.0, safe_ratio)
            constraint.reason = f"温度约束：预测温升 {predicted_temp_rise:.1f}℃，最大允许 {max_temp_rise:.1f}℃"
        else:
            constraint.max_reduction_ratio = target_reduction_ratio
            constraint.reason = "温度约束满足"
        
        # 填充详细信息
        constraint.affected_cabinets = [str(c.id) for c in cabinets]
        constraint.current_temps = cabinet_temps
        constraint.predicted_temps = {
            cid: temp + predicted_temp_rise * constraint.max_reduction_ratio / target_reduction_ratio
            for cid, temp in cabinet_temps.items()
        }
        
    except Exception as e:
        constraint.is_safe = False
        constraint.reason = f"温度约束计算失败: {str(e)}"
        constraint.max_reduction_ratio = 0.0
    
    return constraint


async def _calculate_redundancy_constraint(
    session: AsyncSession,
    device: PowerDevice,
    target_reduction_ratio: float
) -> RedundancyConstraint:
    """
    计算 N+1 冗余约束
    
    对于关键设备（空调、UPS），需要确保即使一台设备故障，
    剩余设备仍能承担全部负载。
    
    算法：
    1. 找到该设备的冗余组（同类型、同区域）
    2. 计算总容量和当前负载
    3. 确保 (N-1) × 单机容量 × 安全系数 >= 当前负载
    """
    constraint = RedundancyConstraint()
    
    try:
        # 1. 查找冗余组设备（同类型、同位置）
        redundancy_group_query = select(PowerDevice).where(
            and_(
                PowerDevice.device_type == device.device_type,
                PowerDevice.area_code == device.area_code,
                PowerDevice.is_enabled == True,
                PowerDevice.id != device.id  # 排除自己
            )
        )
        redundancy_group_result = await session.execute(redundancy_group_query)
        redundancy_group = redundancy_group_result.scalars().all()
        
        if not redundancy_group:
            # 没有冗余设备，不能降低功率
            constraint.is_safe = False
            constraint.reason = "无冗余设备，不可降低功率"
            constraint.max_reduction_ratio = 0.0
            return constraint
        
        # 2. 计算总容量
        # 包括当前设备
        all_devices = [device] + list(redundancy_group)
        total_capacity = sum(d.rated_power or 0.0 for d in all_devices)
        
        # 3. 获取当前负载
        # 查询设备当前功率点位
        current_load = 0.0
        for dev in all_devices:
            # 使用 PowerDevice.power_point_id 直接关联
            if dev.power_point_id:
                latest_power_query = select(PointHistory).where(
                    PointHistory.point_id == dev.power_point_id
                ).order_by(PointHistory.recorded_at.desc()).limit(1)
                latest_power_result = await session.execute(latest_power_query)
                latest_power = latest_power_result.scalar_one_or_none()
                
                if latest_power and latest_power.value is not None:
                    current_load += float(latest_power.value)
        
        if current_load == 0:
            # 没有负载数据，保守估计
            current_load = total_capacity * 0.5  # 假设 50% 负载率
        
        # 4. 计算 N+1 容量
        # N+1 容量 = (N-1) × 单机容量 × 安全系数
        n = len(all_devices)
        single_capacity = total_capacity / n if n > 0 else 0.0
        n_plus_one_capacity = (n - 1) * single_capacity * SAFETY_FACTOR
        
        # 5. 计算最大允许降低比例
        if n_plus_one_capacity < current_load:
            # N+1 容量不足，不能降低功率
            constraint.is_safe = False
            constraint.reason = f"N+1 容量不足：{n_plus_one_capacity:.1f}kW < 当前负载 {current_load:.1f}kW"
            constraint.max_reduction_ratio = 0.0
        else:
            # 计算该设备最大可降低的功率
            # 确保降低后，N+1 容量仍 >= 当前负载
            device_current_power = current_load / n  # 简化：假设负载均分
            max_reduction = (n_plus_one_capacity - current_load) / (n - 1)
            max_reduction_ratio = max_reduction / device_current_power if device_current_power > 0 else 0.0
            
            constraint.max_reduction_ratio = min(target_reduction_ratio, max(0.0, max_reduction_ratio))
            constraint.reason = f"N+1 冗余约束满足，冗余组 {n} 台设备"
        
        # 填充详细信息
        constraint.redundancy_group = [d.id for d in all_devices]
        constraint.total_capacity = total_capacity
        constraint.current_load = current_load
        constraint.n_plus_one_capacity = n_plus_one_capacity
        
    except Exception as e:
        constraint.is_safe = False
        constraint.reason = f"冗余约束计算失败: {str(e)}"
        constraint.max_reduction_ratio = 0.0
    
    return constraint


async def _calculate_pue_constraint(
    session: AsyncSession,
    device: PowerDevice,
    target_reduction_ratio: float
) -> PUEConstraint:
    """
    计算 PUE 约束
    
    PUE = 总功率 / IT 功率
    降低制冷功率会降低总功率，但如果降低过多，可能导致温度上升，
    反而需要更多制冷，PUE 反弹。
    
    算法：
    1. 计算当前 PUE
    2. 估算功率降低后的 PUE
    3. 确保 PUE 在合理范围内（1.2 - 2.0）
    """
    constraint = PUEConstraint()
    
    try:
        # 1. 获取 IT 负载
        # 查询所有 IT 设备的功率
        it_devices_query = select(PowerDevice).where(
            PowerDevice.device_type.in_(['IT_SERVER', 'IT_STORAGE', 'NETWORK_SWITCH'])
        )
        it_devices_result = await session.execute(it_devices_query)
        it_devices = it_devices_result.scalars().all()
        
        it_load = 0.0
        for it_dev in it_devices:
            if it_dev.power_point_id:
                latest_power_query = select(PointHistory).where(
                    PointHistory.point_id == it_dev.power_point_id
                ).order_by(PointHistory.recorded_at.desc()).limit(1)
                latest_power_result = await session.execute(latest_power_query)
                latest_power = latest_power_result.scalar_one_or_none()
                
                if latest_power and latest_power.value is not None:
                    it_load += float(latest_power.value)
        
        if it_load == 0:
            # 没有 IT 负载数据，无法计算 PUE
            constraint.reason = "未找到 IT 负载数据"
            constraint.max_reduction_ratio = target_reduction_ratio
            return constraint
        
        # 2. 获取制冷负载
        cooling_devices_query = select(PowerDevice).where(
            PowerDevice.device_type.in_(list(COOLING_DEVICES))
        )
        cooling_devices_result = await session.execute(cooling_devices_query)
        cooling_devices = cooling_devices_result.scalars().all()
        
        cooling_load = 0.0
        for cooling_dev in cooling_devices:
            if cooling_dev.power_point_id:
                latest_power_query = select(PointHistory).where(
                    PointHistory.point_id == cooling_dev.power_point_id
                ).order_by(PointHistory.recorded_at.desc()).limit(1)
                latest_power_result = await session.execute(latest_power_query)
                latest_power = latest_power_result.scalar_one_or_none()
                
                if latest_power and latest_power.value is not None:
                    cooling_load += float(latest_power.value)
        
        # 3. 计算当前 PUE
        total_load = it_load + cooling_load
        current_pue = total_load / it_load if it_load > 0 else 0.0
        
        # 4. 估算功率降低后的 PUE
        # 假设该设备功率占制冷负载的比例
        device_power_ratio = (device.rated_power or 0.0) / cooling_load if cooling_load > 0 else 0.0
        cooling_reduction = cooling_load * device_power_ratio * target_reduction_ratio
        new_cooling_load = cooling_load - cooling_reduction
        new_total_load = it_load + new_cooling_load
        predicted_pue = new_total_load / it_load if it_load > 0 else 0.0
        
        # 5. 检查 PUE 是否在合理范围
        if predicted_pue < PUE_MIN:
            # PUE 过低，可能制冷不足
            constraint.is_safe = False
            constraint.reason = f"PUE 过低：{predicted_pue:.2f} < {PUE_MIN}，可能制冷不足"
            constraint.max_reduction_ratio = 0.0
        elif predicted_pue > PUE_MAX:
            # PUE 过高（理论上不会，因为降低制冷会降低 PUE）
            constraint.reason = f"PUE 过高：{predicted_pue:.2f} > {PUE_MAX}"
            constraint.max_reduction_ratio = 0.0
        else:
            # PUE 在合理范围
            constraint.max_reduction_ratio = target_reduction_ratio
            constraint.reason = f"PUE 约束满足：{current_pue:.2f} -> {predicted_pue:.2f}"
        
        # 填充详细信息
        constraint.current_pue = current_pue
        constraint.predicted_pue = predicted_pue
        constraint.it_load = it_load
        constraint.cooling_load = cooling_load
        
    except Exception as e:
        constraint.is_safe = False
        constraint.reason = f"PUE 约束计算失败: {str(e)}"
        constraint.max_reduction_ratio = 0.0
    
    return constraint


async def _calculate_device_constraint(
    session: AsyncSession,
    device: PowerDevice,
    target_reduction_ratio: float
) -> Dict:
    """
    计算设备特性约束
    
    考虑：
    1. 设备最小功率限制
    2. 设备启停特性
    3. 最小运行时间
    """
    constraint = {
        'max_reduction_ratio': target_reduction_ratio,
        'reason': '设备特性约束满足'
    }
    
    try:
        # 1. 最小功率限制
        # 设备不能低于额定功率的 30%（经验值）
        min_power_ratio = 0.3
        if target_reduction_ratio > (1.0 - min_power_ratio):
            constraint['max_reduction_ratio'] = 1.0 - min_power_ratio
            constraint['reason'] = f"设备最小功率限制：不能低于额定功率的 {min_power_ratio*100}%"
        
        # 2. 启停特性
        # 某些设备（如压缩机）频繁启停会损坏，需要最小运行时间
        if device.device_type in ['CHILLER', 'COMPRESSOR']:
            # 查询最近启动时间
            # 简化：这里假设设备已运行足够时间
            pass
        
    except Exception as e:
        constraint['reason'] = f"设备约束计算失败: {str(e)}"
        constraint['max_reduction_ratio'] = 0.0
    
    return constraint


def _calculate_confidence(constraints: Dict) -> float:
    """
    计算置信度
    
    基于约束计算的完整性和数据质量
    """
    confidence = 1.0
    
    # 如果缺少关键约束，降低置信度
    if 'temperature' not in constraints:
        confidence *= 0.8
    if 'redundancy' not in constraints:
        confidence *= 0.9
    
    # 如果约束计算失败，降低置信度
    for constraint in constraints.values():
        if hasattr(constraint, 'is_safe') and not constraint.is_safe:
            confidence *= 0.7
    
    return max(0.0, min(1.0, confidence))


# ==================== 批量计算接口 ====================

async def calculate_batch_recommendations(
    session: AsyncSession,
    device_ids: List[int],
    target_reduction_ratio: float = 0.3
) -> Dict[int, ShiftRecommendation]:
    """
    批量计算多个设备的转移建议
    
    Args:
        session: 数据库会话
        device_ids: 设备 ID 列表
        target_reduction_ratio: 目标降低比例
    
    Returns:
        Dict[int, ShiftRecommendation]: 设备 ID -> 转移建议
    """
    results = {}
    
    for device_id in device_ids:
        # 查询设备
        device_query = select(PowerDevice).where(PowerDevice.id == device_id)
        device_result = await session.execute(device_query)
        device = device_result.scalar_one_or_none()
        
        if device:
            recommendation = await calculate_shift_recommendation(
                session, device, target_reduction_ratio
            )
            results[device_id] = recommendation
    
    return results
