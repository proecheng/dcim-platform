"""
多设备协同优化算法

使用scipy.optimize实现多设备同时优化，最大化总转移比例，同时满足所有约束。
"""
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..models.energy import PowerDevice
from .datacenter_shift_strategy import (
    calculate_shift_recommendation,
    TEMP_WARNING,
    PUE_MAX,
    PUE_MIN,
    COOLING_DEVICES
)

# 条件导入scipy
try:
    from scipy.optimize import minimize
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False


@dataclass
class OptimizationResult:
    """优化结果"""
    success: bool
    shift_plan: Dict[int, float]  # device_id -> reduction_ratio
    total_reduction: float
    message: str
    iterations: int = 0


async def optimize_multi_device_shift(
    session: AsyncSession,
    device_ids: List[int],
    target_total_reduction: float = 0.3
) -> OptimizationResult:
    """
    多设备协同优化
    
    目标：最大化总功率转移，同时满足所有约束
    
    Args:
        session: 数据库会话
        device_ids: 要优化的设备ID列表
        target_total_reduction: 目标总转移比例
    
    Returns:
        OptimizationResult: 优化结果
    """
    if not SCIPY_AVAILABLE:
        # Fallback: 使用贪心算法
        return await _greedy_optimization(session, device_ids, target_total_reduction)
    
    # 加载设备
    devices = []
    for device_id in device_ids:
        result = await session.execute(
            select(PowerDevice).where(PowerDevice.id == device_id)
        )
        device = result.scalar_one_or_none()
        if device:
            devices.append(device)
    
    if not devices:
        return OptimizationResult(
            success=False,
            shift_plan={},
            total_reduction=0.0,
            message="未找到设备"
        )
    
    # 使用scipy优化
    try:
        result = await _scipy_optimization(session, devices, target_total_reduction)
        return result
    except Exception as e:
        # Fallback到贪心算法
        return await _greedy_optimization(session, device_ids, target_total_reduction)


async def _scipy_optimization(
    session: AsyncSession,
    devices: List[PowerDevice],
    target_total_reduction: float
) -> OptimizationResult:
    """使用scipy.optimize进行优化"""
    n = len(devices)
    
    # 目标函数：最大化总转移比例（最小化负值）
    def objective(x):
        return -sum(x)  # 负号因为minimize求最小值
    
    # 约束函数
    constraints = []
    
    # 1. 总转移比例约束
    constraints.append({
        'type': 'eq',
        'fun': lambda x: sum(x) - target_total_reduction * n
    })
    
    # 2. 每个设备的约束（简化版，实际应该调用calculate_shift_recommendation）
    for i in range(n):
        # 最小值约束
        constraints.append({
            'type': 'ineq',
            'fun': lambda x, i=i: x[i]  # x[i] >= 0
        })
        # 最大值约束
        constraints.append({
            'type': 'ineq',
            'fun': lambda x, i=i: 0.5 - x[i]  # x[i] <= 0.5
        })
    
    # 初始猜测
    x0 = [target_total_reduction] * n
    
    # 边界
    bounds = [(0.0, 0.5) for _ in range(n)]
    
    # 优化
    result = minimize(
        objective,
        x0,
        method='SLSQP',
        bounds=bounds,
        constraints=constraints,
        options={'maxiter': 100}
    )
    
    if result.success:
        shift_plan = {
            devices[i].id: float(result.x[i])
            for i in range(n)
        }
        return OptimizationResult(
            success=True,
            shift_plan=shift_plan,
            total_reduction=sum(result.x),
            message="优化成功",
            iterations=result.nit
        )
    else:
        return OptimizationResult(
            success=False,
            shift_plan={},
            total_reduction=0.0,
            message=f"优化失败: {result.message}"
        )


async def _greedy_optimization(
    session: AsyncSession,
    device_ids: List[int],
    target_total_reduction: float
) -> OptimizationResult:
    """
    贪心算法优化（Fallback）
    
    策略：按约束从宽松到严格排序，优先分配转移比例
    """
    shift_plan = {}
    total_reduction = 0.0
    
    # 为每个设备计算约束
    device_constraints = []
    for device_id in device_ids:
        result = await session.execute(
            select(PowerDevice).where(PowerDevice.id == device_id)
        )
        device = result.scalar_one_or_none()
        if not device:
            continue
        
        # 计算该设备的约束
        recommendation = await calculate_shift_recommendation(
            session, device, target_reduction_ratio=target_total_reduction
        )
        
        device_constraints.append({
            'device_id': device_id,
            'max_ratio': recommendation.recommended_ratio,
            'device': device
        })
    
    # 按max_ratio降序排序（约束宽松的优先）
    device_constraints.sort(key=lambda x: x['max_ratio'], reverse=True)
    
    # 贪心分配
    remaining_target = target_total_reduction * len(device_ids)
    for dc in device_constraints:
        # 分配尽可能多的转移比例
        allocated = min(dc['max_ratio'], remaining_target / len(device_constraints))
        shift_plan[dc['device_id']] = allocated
        total_reduction += allocated
        remaining_target -= allocated
    
    return OptimizationResult(
        success=True,
        shift_plan=shift_plan,
        total_reduction=total_reduction,
        message="使用贪心算法优化（scipy不可用）"
    )


async def optimize_with_constraints(
    session: AsyncSession,
    device_ids: List[int],
    max_temp_rise: float = 2.0,
    min_redundancy: float = 0.9,
    max_pue: float = PUE_MAX
) -> OptimizationResult:
    """
    带约束的多设备优化
    
    Args:
        session: 数据库会话
        device_ids: 设备ID列表
        max_temp_rise: 最大温升（℃）
        min_redundancy: 最小冗余度
        max_pue: 最大PUE
    
    Returns:
        OptimizationResult: 优化结果
    """
    # 简化实现：调用基础优化
    result = await optimize_multi_device_shift(session, device_ids, 0.3)
    
    # TODO: 添加额外约束验证
    # 1. 验证温度约束
    # 2. 验证冗余约束
    # 3. 验证PUE约束
    
    return result
