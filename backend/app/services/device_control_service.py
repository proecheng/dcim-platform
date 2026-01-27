"""
设备控制服务
Device Control Service

提供设备调节控制功能，支持自动和手动执行
暂时使用模拟控制，预留BMS对接接口
"""
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from ..models.energy import (
    PowerDevice, LoadRegulationConfig, DeviceShiftConfig
)


class ControlResult(str, Enum):
    """控制结果"""
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    PENDING = "pending"
    SIMULATED = "simulated"  # 模拟执行（未实际控制）


class ControlInterface(str, Enum):
    """控制接口类型"""
    BMS = "bms"           # 楼宇管理系统
    DIRECT = "direct"     # 直接控制
    MODBUS = "modbus"     # Modbus协议
    BACNET = "bacnet"     # BACnet协议
    MANUAL = "manual"     # 需要人工操作
    SIMULATED = "simulated"  # 模拟（开发测试）


@dataclass
class ControlAction:
    """控制动作"""
    device_id: int
    device_name: str
    action_type: str        # temperature/brightness/power/mode
    current_value: float
    target_value: float
    unit: str
    interface: ControlInterface
    result: ControlResult
    message: str
    executed_at: datetime


class DeviceControlService:
    """
    设备控制服务

    核心功能:
    1. 控制设备调节（温度、亮度、功率等）
    2. 验证控制权限和约束
    3. 执行定时控制任务
    4. 获取设备控制状态
    5. 记录控制日志

    注意：当前版本为模拟控制，实际对接需实现 _execute_*_control 方法
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        # 控制接口配置（实际部署时从配置加载）
        self._interface_config = {
            "default": ControlInterface.SIMULATED,
            "ac": ControlInterface.BMS,
            "lighting": ControlInterface.MANUAL
        }

    async def control_device_regulation(
        self,
        device_id: int,
        regulation_type: str,
        target_value: float,
        scheduled_time: Optional[datetime] = None,
        force: bool = False
    ) -> ControlAction:
        """
        控制设备调节

        Args:
            device_id: 设备ID
            regulation_type: 调节类型 (temperature/brightness/load)
            target_value: 目标值
            scheduled_time: 计划执行时间（None表示立即执行）
            force: 是否强制执行（忽略部分约束）

        Returns:
            ControlAction: 控制结果
        """
        # 1. 获取设备和调节配置
        device = await self._get_device(device_id)
        if not device:
            return ControlAction(
                device_id=device_id,
                device_name="Unknown",
                action_type=regulation_type,
                current_value=0,
                target_value=target_value,
                unit="",
                interface=ControlInterface.MANUAL,
                result=ControlResult.FAILED,
                message=f"设备ID {device_id} 不存在",
                executed_at=datetime.now()
            )

        reg_config = await self._get_regulation_config(device_id, regulation_type)
        if not reg_config:
            return ControlAction(
                device_id=device_id,
                device_name=device.device_name,
                action_type=regulation_type,
                current_value=0,
                target_value=target_value,
                unit="",
                interface=ControlInterface.MANUAL,
                result=ControlResult.FAILED,
                message=f"设备 {device.device_name} 无 {regulation_type} 调节配置",
                executed_at=datetime.now()
            )

        # 2. 验证控制权限和约束
        validation = await self.validate_control_permission(
            device_id, regulation_type, target_value, force
        )
        if not validation["is_allowed"]:
            return ControlAction(
                device_id=device_id,
                device_name=device.device_name,
                action_type=regulation_type,
                current_value=reg_config.current_value or reg_config.default_value or 0,
                target_value=target_value,
                unit=reg_config.unit or "",
                interface=ControlInterface.MANUAL,
                result=ControlResult.FAILED,
                message="; ".join(validation["reasons"]),
                executed_at=datetime.now()
            )

        # 3. 确定控制接口
        interface = self._get_control_interface(device, reg_config)

        # 4. 执行控制
        current_value = reg_config.current_value or reg_config.default_value or 0

        if scheduled_time and scheduled_time > datetime.now():
            # 定时执行
            result = ControlResult.PENDING
            message = f"已计划在 {scheduled_time.strftime('%Y-%m-%d %H:%M')} 执行"
            # TODO: 加入调度队列
        else:
            # 立即执行
            result, message = await self._execute_control(
                device, reg_config, target_value, interface
            )

        # 5. 记录控制日志
        action = ControlAction(
            device_id=device_id,
            device_name=device.device_name,
            action_type=regulation_type,
            current_value=current_value,
            target_value=target_value,
            unit=reg_config.unit or "",
            interface=interface,
            result=result,
            message=message,
            executed_at=datetime.now()
        )

        await self.log_control_action(action)

        # 6. 更新配置中的当前值（模拟执行）
        if result in [ControlResult.SUCCESS, ControlResult.SIMULATED]:
            reg_config.current_value = target_value
            await self.db.commit()

        return action

    async def validate_control_permission(
        self,
        device_id: int,
        regulation_type: str,
        target_value: float,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        验证控制权限和约束

        Returns:
            {
                "is_allowed": True/False,
                "reasons": [...],
                "warnings": [...]
            }
        """
        reasons = []
        warnings = []

        # 获取配置
        reg_config = await self._get_regulation_config(device_id, regulation_type)
        if not reg_config:
            return {"is_allowed": False, "reasons": ["未找到调节配置"], "warnings": []}

        if not reg_config.is_enabled:
            return {"is_allowed": False, "reasons": ["调节配置已禁用"], "warnings": []}

        # 检查值范围
        min_val = reg_config.min_value
        max_val = reg_config.max_value

        if min_val is not None and target_value < min_val:
            reasons.append(f"目标值 {target_value} 小于最小值 {min_val}")
        if max_val is not None and target_value > max_val:
            reasons.append(f"目标值 {target_value} 大于最大值 {max_val}")

        # 检查舒适度/性能影响
        if reg_config.comfort_impact in ["high", "critical"]:
            warnings.append(f"此调节可能显著影响舒适度({reg_config.comfort_impact})")
        if reg_config.performance_impact in ["high", "critical"]:
            warnings.append(f"此调节可能影响设备性能({reg_config.performance_impact})")

        # 检查是否为关键设备
        shift_config = await self._get_shift_config(device_id)
        if shift_config and shift_config.is_critical:
            if not force:
                warnings.append("此设备为关键负荷，调节需谨慎")

        # 如果force=True，忽略非致命错误
        if force and reasons:
            warnings.extend([f"[已忽略] {r}" for r in reasons])
            reasons = []

        return {
            "is_allowed": len(reasons) == 0,
            "reasons": reasons,
            "warnings": warnings
        }

    async def execute_scheduled_control(
        self,
        schedule_id: int
    ) -> ControlAction:
        """
        执行定时控制任务

        Args:
            schedule_id: 定时任务ID

        Returns:
            ControlAction: 执行结果
        """
        # TODO: 实现定时任务执行
        # 从调度表获取任务信息，调用 control_device_regulation
        raise NotImplementedError("定时控制功能待实现")

    async def get_control_status(
        self,
        device_id: int,
        regulation_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取设备控制状态

        Returns:
            {
                "device_id": 1,
                "device_name": "精密空调1",
                "regulations": [...],
                "is_controllable": True,
                "interface": "bms"
            }
        """
        device = await self._get_device(device_id)
        if not device:
            return {"error": f"设备ID {device_id} 不存在"}

        # 获取所有调节配置
        query = select(LoadRegulationConfig).where(
            and_(
                LoadRegulationConfig.device_id == device_id,
                LoadRegulationConfig.is_enabled == True
            )
        )
        if regulation_type:
            query = query.where(LoadRegulationConfig.regulation_type == regulation_type)

        result = await self.db.execute(query)
        configs = result.scalars().all()

        regulations = []
        for config in configs:
            interface = self._get_control_interface(device, config)
            regulations.append({
                "config_id": config.id,
                "regulation_type": config.regulation_type,
                "current_value": config.current_value,
                "default_value": config.default_value,
                "min_value": config.min_value,
                "max_value": config.max_value,
                "unit": config.unit,
                "is_auto": config.is_auto,
                "interface": interface.value,
                "is_controllable": interface != ControlInterface.MANUAL
            })

        return {
            "device_id": device_id,
            "device_name": device.device_name,
            "device_type": device.device_type,
            "regulations": regulations,
            "is_controllable": any(r["is_controllable"] for r in regulations),
            "control_count": len(regulations)
        }

    async def log_control_action(
        self,
        action: ControlAction
    ) -> None:
        """
        记录控制操作日志

        TODO: 写入操作日志表
        """
        # 暂时只打印日志
        import logging
        logger = logging.getLogger(__name__)
        logger.info(
            f"[DeviceControl] {action.device_name} ({action.device_id}) "
            f"{action.action_type}: {action.current_value} -> {action.target_value} {action.unit} "
            f"| Result: {action.result.value} | {action.message}"
        )

    async def batch_control(
        self,
        controls: List[Dict[str, Any]]
    ) -> List[ControlAction]:
        """
        批量执行控制

        Args:
            controls: 控制列表
                [
                    {"device_id": 1, "regulation_type": "temperature", "target_value": 26},
                    ...
                ]

        Returns:
            控制结果列表
        """
        results = []
        for ctrl in controls:
            action = await self.control_device_regulation(
                device_id=ctrl["device_id"],
                regulation_type=ctrl["regulation_type"],
                target_value=ctrl["target_value"],
                scheduled_time=ctrl.get("scheduled_time"),
                force=ctrl.get("force", False)
            )
            results.append(action)
        return results

    # ========== 私有方法 ==========

    async def _get_device(self, device_id: int) -> Optional[PowerDevice]:
        """获取设备"""
        result = await self.db.execute(
            select(PowerDevice).where(PowerDevice.id == device_id)
        )
        return result.scalar_one_or_none()

    async def _get_regulation_config(
        self,
        device_id: int,
        regulation_type: str
    ) -> Optional[LoadRegulationConfig]:
        """获取调节配置"""
        result = await self.db.execute(
            select(LoadRegulationConfig).where(
                and_(
                    LoadRegulationConfig.device_id == device_id,
                    LoadRegulationConfig.regulation_type == regulation_type
                )
            )
        )
        return result.scalar_one_or_none()

    async def _get_shift_config(self, device_id: int) -> Optional[DeviceShiftConfig]:
        """获取转移配置"""
        result = await self.db.execute(
            select(DeviceShiftConfig).where(DeviceShiftConfig.device_id == device_id)
        )
        return result.scalar_one_or_none()

    def _get_control_interface(
        self,
        device: PowerDevice,
        config: LoadRegulationConfig
    ) -> ControlInterface:
        """确定设备控制接口"""
        # 优先使用配置的接口
        # TODO: 从配置中读取实际接口类型

        device_type = (device.device_type or "").lower()

        # 根据设备类型判断
        if device_type in ["ac", "air_conditioner", "hvac"]:
            if config.is_auto:
                return ControlInterface.BMS
            return ControlInterface.MANUAL

        if device_type in ["lighting", "light"]:
            return ControlInterface.MANUAL  # 灯光通常需要硬件改造

        if config.is_auto:
            return ControlInterface.SIMULATED

        return ControlInterface.MANUAL

    async def _execute_control(
        self,
        device: PowerDevice,
        config: LoadRegulationConfig,
        target_value: float,
        interface: ControlInterface
    ) -> tuple[ControlResult, str]:
        """
        执行实际控制

        Returns:
            (result, message)
        """
        if interface == ControlInterface.SIMULATED:
            return await self._execute_simulated_control(device, config, target_value)

        if interface == ControlInterface.BMS:
            return await self._execute_bms_control(device, config, target_value)

        if interface == ControlInterface.MANUAL:
            return (
                ControlResult.PENDING,
                "需要人工操作，请按指引进行调节"
            )

        # 其他接口待实现
        return (
            ControlResult.FAILED,
            f"控制接口 {interface.value} 尚未实现"
        )

    async def _execute_simulated_control(
        self,
        device: PowerDevice,
        config: LoadRegulationConfig,
        target_value: float
    ) -> tuple[ControlResult, str]:
        """模拟控制执行"""
        # 模拟执行成功
        return (
            ControlResult.SIMULATED,
            f"[模拟] {device.device_name} {config.regulation_type} "
            f"已调节至 {target_value}{config.unit or ''}"
        )

    async def _execute_bms_control(
        self,
        device: PowerDevice,
        config: LoadRegulationConfig,
        target_value: float
    ) -> tuple[ControlResult, str]:
        """
        BMS控制执行

        TODO: 对接实际BMS系统
        - 通过BACnet/Modbus协议发送控制指令
        - 等待响应确认
        - 读取实际值验证
        """
        # 暂时返回模拟结果
        return (
            ControlResult.SIMULATED,
            f"[BMS模拟] {device.device_name} {config.regulation_type} "
            f"已调节至 {target_value}{config.unit or ''}"
        )
