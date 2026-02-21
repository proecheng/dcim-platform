"""
设备双向同步服务
Device ↔ Topology 双向同步

当拓扑节点(DistributionPanel/PowerDevice)创建/更新/删除时，自动同步到 Device 表；
当 Device 创建/更新/删除时，自动同步到拓扑表。
使用 contextvars 防止循环触发。
"""

import contextvars
from datetime import datetime
from typing import Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..models.device import Device
from ..models.energy import DistributionPanel, PowerDevice
from ..models.power import UPSDevice

# 防循环重入标志 (per-coroutine，不会跨请求泄漏)
_syncing: contextvars.ContextVar[bool] = contextvars.ContextVar("_device_syncing", default=False)


class DeviceSyncService:
    """设备双向同步服务"""

    # ========== 类型映射 ==========

    # 配电柜(Panel) → Device 类型
    PANEL_TO_DEVICE_TYPE = "CABINET"

    # 拓扑 PowerDevice.device_type → Device.device_type
    POWER_DEVICE_TYPE_MAP = {
        "UPS": "UPS",
        "HVAC": "AC",
        "PDU": "PDU",
        "IT_SERVER": "IT",
        "IT_STORAGE": "IT",
    }

    # Device.device_type → 拓扑 PowerDevice.device_type
    DEVICE_TO_POWER_TYPE_MAP = {
        "UPS": "UPS",
        "AC": "HVAC",
        "PDU": "PDU",
        "IT": "IT_SERVER",
    }

    # 映射到 DistributionPanel 的 Device 类型
    PANEL_DEVICE_TYPES = {"CABINET"}

    # 映射到 PowerDevice 的 Device 类型
    POWER_DEVICE_TYPES = {"UPS", "PDU", "AC", "IT"}

    def __init__(self, db: AsyncSession):
        self.db = db

    # ========== 重入保护 ==========

    @staticmethod
    def is_syncing() -> bool:
        return _syncing.get()

    @staticmethod
    def _set_syncing(value: bool):
        _syncing.set(value)

    # ========== Topology → Device 方向 ==========

    async def on_panel_created(self, panel: DistributionPanel) -> Optional[int]:
        """
        配电柜创建后 → 自动创建或关联 Device(CABINET)
        返回关联的 device.id
        """
        if self.is_syncing():
            return None
        self._set_syncing(True)
        try:
            # 先检查是否已有同编码的 Device（避免唯一约束冲突）
            existing = await self.db.execute(
                select(Device).where(Device.device_code == panel.panel_code)
            )
            device = existing.scalar_one_or_none()
            if device:
                # 已存在，直接关联
                panel.device_id = device.id
                return device.id

            # 不存在，创建新 Device
            device = Device(
                device_code=panel.panel_code,
                device_name=panel.panel_name,
                device_type=self.PANEL_TO_DEVICE_TYPE,
                area_code=panel.area_code or "A1",
                status="online",
                is_enabled=True,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            self.db.add(device)
            await self.db.flush()
            panel.device_id = device.id
            return device.id
        finally:
            self._set_syncing(False)

    async def on_power_device_created(self, power_device: PowerDevice) -> Optional[int]:
        """
        用电设备创建后 → 自动创建或关联 Device + 可选 UPSDevice
        返回关联的 device.id
        """
        if self.is_syncing():
            return None
        device_type = self.POWER_DEVICE_TYPE_MAP.get(power_device.device_type)
        if not device_type:
            return None  # LIGHTING, PUMP, OTHER 等不需要同步
        self._set_syncing(True)
        try:
            # 先检查是否已有同编码的 Device
            existing = await self.db.execute(
                select(Device).where(Device.device_code == power_device.device_code)
            )
            device = existing.scalar_one_or_none()
            if device:
                power_device.monitor_device_id = device.id
                return device.id

            # 创建新 Device
            device = Device(
                device_code=power_device.device_code,
                device_name=power_device.device_name,
                device_type=device_type,
                area_code=power_device.area_code or "A1",
                status="online",
                is_enabled=True,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            self.db.add(device)
            await self.db.flush()
            power_device.monitor_device_id = device.id

            # UPS 自动创建扩展记录
            if device_type == "UPS":
                # 检查是否已有 UPSDevice 扩展
                ups_existing = await self.db.execute(
                    select(UPSDevice).where(UPSDevice.device_id == device.id)
                )
                if not ups_existing.scalar_one_or_none():
                    ups = UPSDevice(
                        device_id=device.id,
                        rated_capacity=power_device.rated_power,
                        created_at=datetime.now(),
                        updated_at=datetime.now(),
                    )
                    self.db.add(ups)

            return device.id
        finally:
            self._set_syncing(False)

    # ========== Device → Topology 方向 ==========

    async def on_device_created(self, device: Device) -> Optional[Tuple[str, int]]:
        """
        动环设备创建后 → 自动创建拓扑节点
        返回 (node_type, node_id) 或 None
        """
        if self.is_syncing():
            return None
        self._set_syncing(True)
        try:
            if device.device_type in self.PANEL_DEVICE_TYPES:
                # 检查是否已有同编码的 Panel
                existing = await self.db.execute(
                    select(DistributionPanel).where(
                        DistributionPanel.panel_code == device.device_code
                    )
                )
                panel = existing.scalar_one_or_none()
                if panel:
                    panel.device_id = device.id
                    return ("panel", panel.id)

                # 创建新 Panel（未挂载到任何计量点，用户可在拓扑中拖拽连接）
                panel = DistributionPanel(
                    panel_code=device.device_code,
                    panel_name=device.device_name,
                    panel_type="distribution",
                    area_code=device.area_code,
                    device_id=device.id,
                    status="running",
                    is_enabled=True,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )
                self.db.add(panel)
                await self.db.flush()
                return ("panel", panel.id)

            elif device.device_type in self.POWER_DEVICE_TYPES:
                # 检查是否已有同编码的 PowerDevice
                existing = await self.db.execute(
                    select(PowerDevice).where(
                        PowerDevice.device_code == device.device_code
                    )
                )
                pd = existing.scalar_one_or_none()
                if pd:
                    pd.monitor_device_id = device.id
                    return ("device", pd.id)

                # 创建新 PowerDevice（未挂载到任何回路，用户可在拓扑中拖拽连接）
                power_type = self.DEVICE_TO_POWER_TYPE_MAP.get(
                    device.device_type, "OTHER"
                )
                pd = PowerDevice(
                    device_code=device.device_code,
                    device_name=device.device_name,
                    device_type=power_type,
                    monitor_device_id=device.id,
                    area_code=device.area_code,
                    is_enabled=True,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )
                self.db.add(pd)
                await self.db.flush()
                return ("device", pd.id)

            return None
        finally:
            self._set_syncing(False)

    # ========== 双向更新 ==========

    async def on_panel_updated(self, panel: DistributionPanel):
        """配电柜更新 → 同步 Device 名称/编码"""
        if self.is_syncing() or not panel.device_id:
            return
        self._set_syncing(True)
        try:
            result = await self.db.execute(
                select(Device).where(Device.id == panel.device_id)
            )
            device = result.scalar_one_or_none()
            if device:
                device.device_name = panel.panel_name
                device.device_code = panel.panel_code
                device.updated_at = datetime.now()
        finally:
            self._set_syncing(False)

    async def on_power_device_updated(self, power_device: PowerDevice):
        """用电设备更新 → 同步 Device 名称/编码"""
        if self.is_syncing() or not power_device.monitor_device_id:
            return
        self._set_syncing(True)
        try:
            result = await self.db.execute(
                select(Device).where(Device.id == power_device.monitor_device_id)
            )
            device = result.scalar_one_or_none()
            if device:
                device.device_name = power_device.device_name
                device.device_code = power_device.device_code
                device.updated_at = datetime.now()
        finally:
            self._set_syncing(False)

    async def on_device_updated(self, device: Device):
        """动环设备更新 → 同步拓扑节点名称/编码"""
        if self.is_syncing():
            return
        self._set_syncing(True)
        try:
            if device.device_type in self.PANEL_DEVICE_TYPES:
                result = await self.db.execute(
                    select(DistributionPanel).where(
                        DistributionPanel.device_id == device.id
                    )
                )
                panel = result.scalar_one_or_none()
                if panel:
                    panel.panel_name = device.device_name
                    panel.panel_code = device.device_code
                    panel.updated_at = datetime.now()

            elif device.device_type in self.POWER_DEVICE_TYPES:
                result = await self.db.execute(
                    select(PowerDevice).where(
                        PowerDevice.monitor_device_id == device.id
                    )
                )
                pd = result.scalar_one_or_none()
                if pd:
                    pd.device_name = device.device_name
                    pd.device_code = device.device_code
                    pd.updated_at = datetime.now()
        finally:
            self._set_syncing(False)

    # ========== 双向删除（软删除：禁用而非物理删除） ==========

    async def on_panel_deleted(self, panel_id: int):
        """配电柜删除 → 禁用关联 Device"""
        if self.is_syncing():
            return
        self._set_syncing(True)
        try:
            result = await self.db.execute(
                select(DistributionPanel).where(DistributionPanel.id == panel_id)
            )
            panel = result.scalar_one_or_none()
            if panel and panel.device_id:
                dev_result = await self.db.execute(
                    select(Device).where(Device.id == panel.device_id)
                )
                device = dev_result.scalar_one_or_none()
                if device:
                    device.status = "offline"
                    device.is_enabled = False
                    device.updated_at = datetime.now()
        finally:
            self._set_syncing(False)

    async def on_power_device_deleted(self, power_device_id: int):
        """用电设备删除 → 禁用关联 Device"""
        if self.is_syncing():
            return
        self._set_syncing(True)
        try:
            result = await self.db.execute(
                select(PowerDevice).where(PowerDevice.id == power_device_id)
            )
            pd = result.scalar_one_or_none()
            if pd and pd.monitor_device_id:
                dev_result = await self.db.execute(
                    select(Device).where(Device.id == pd.monitor_device_id)
                )
                device = dev_result.scalar_one_or_none()
                if device:
                    device.status = "offline"
                    device.is_enabled = False
                    device.updated_at = datetime.now()
        finally:
            self._set_syncing(False)

    async def on_device_deleted(self, device: Device):
        """动环设备删除 → 禁用拓扑节点"""
        if self.is_syncing():
            return
        self._set_syncing(True)
        try:
            if device.device_type in self.PANEL_DEVICE_TYPES:
                result = await self.db.execute(
                    select(DistributionPanel).where(
                        DistributionPanel.device_id == device.id
                    )
                )
                panel = result.scalar_one_or_none()
                if panel:
                    panel.is_enabled = False
                    panel.device_id = None
                    panel.updated_at = datetime.now()

            elif device.device_type in self.POWER_DEVICE_TYPES:
                result = await self.db.execute(
                    select(PowerDevice).where(
                        PowerDevice.monitor_device_id == device.id
                    )
                )
                pd = result.scalar_one_or_none()
                if pd:
                    pd.is_enabled = False
                    pd.monitor_device_id = None
                    pd.updated_at = datetime.now()
        finally:
            self._set_syncing(False)

    # ========== 存量数据迁移 ==========

    async def migrate_existing_data(self) -> dict:
        """
        一次性迁移：为已有记录建立双向关联
        通过 device_code 匹配
        """
        linked_panels = 0
        linked_power_devices = 0
        created_devices_for_panels = 0
        created_devices_for_power = 0

        # 1. DistributionPanel ↔ Device (by panel_code == device_code)
        panels = (
            await self.db.execute(
                select(DistributionPanel).where(
                    DistributionPanel.device_id.is_(None),
                    DistributionPanel.is_enabled == True,
                )
            )
        ).scalars().all()

        for panel in panels:
            device = (
                await self.db.execute(
                    select(Device).where(Device.device_code == panel.panel_code)
                )
            ).scalar_one_or_none()
            if device:
                panel.device_id = device.id
                linked_panels += 1
            else:
                # 创建 Device
                device = Device(
                    device_code=panel.panel_code,
                    device_name=panel.panel_name,
                    device_type=self.PANEL_TO_DEVICE_TYPE,
                    area_code=panel.area_code or "A1",
                    status="online",
                    is_enabled=True,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )
                self.db.add(device)
                await self.db.flush()
                panel.device_id = device.id
                created_devices_for_panels += 1

        # 2. PowerDevice ↔ Device (by device_code)
        power_devices = (
            await self.db.execute(
                select(PowerDevice).where(
                    PowerDevice.monitor_device_id.is_(None),
                    PowerDevice.is_enabled == True,
                )
            )
        ).scalars().all()

        for pd in power_devices:
            device_type = self.POWER_DEVICE_TYPE_MAP.get(pd.device_type)
            if not device_type:
                continue

            device = (
                await self.db.execute(
                    select(Device).where(Device.device_code == pd.device_code)
                )
            ).scalar_one_or_none()
            if device:
                pd.monitor_device_id = device.id
                linked_power_devices += 1
            else:
                device = Device(
                    device_code=pd.device_code,
                    device_name=pd.device_name,
                    device_type=device_type,
                    area_code=pd.area_code or "A1",
                    status="online",
                    is_enabled=True,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )
                self.db.add(device)
                await self.db.flush()
                pd.monitor_device_id = device.id
                created_devices_for_power += 1

        # 3. Device → DistributionPanel (反向: 已有 CABINET 设备但无 Panel)
        created_panels_for_devices = 0
        cabinet_devices = (
            await self.db.execute(
                select(Device).where(
                    Device.device_type == self.PANEL_TO_DEVICE_TYPE,
                    Device.is_enabled == True,
                )
            )
        ).scalars().all()

        for dev in cabinet_devices:
            # 检查是否已有关联的 Panel（通过 device_id 或 device_code）
            existing_panel = (
                await self.db.execute(
                    select(DistributionPanel).where(
                        (DistributionPanel.device_id == dev.id)
                        | (DistributionPanel.panel_code == dev.device_code)
                    )
                )
            ).scalar_one_or_none()
            if not existing_panel:
                panel = DistributionPanel(
                    panel_code=dev.device_code,
                    panel_name=dev.device_name,
                    panel_type="distribution",
                    area_code=dev.area_code or "A1",
                    device_id=dev.id,
                    status="running",
                    is_enabled=True,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )
                self.db.add(panel)
                await self.db.flush()
                created_panels_for_devices += 1

        # 4. Device → PowerDevice (反向: 已有 UPS/AC/PDU 设备但无 PowerDevice)
        created_power_for_devices = 0
        for dev_type, power_type in self.DEVICE_TO_POWER_TYPE_MAP.items():
            devs = (
                await self.db.execute(
                    select(Device).where(
                        Device.device_type == dev_type,
                        Device.is_enabled == True,
                    )
                )
            ).scalars().all()

            for dev in devs:
                existing_pd = (
                    await self.db.execute(
                        select(PowerDevice).where(
                            (PowerDevice.monitor_device_id == dev.id)
                            | (PowerDevice.device_code == dev.device_code)
                        )
                    )
                ).scalar_one_or_none()
                if not existing_pd:
                    pd = PowerDevice(
                        device_code=dev.device_code,
                        device_name=dev.device_name,
                        device_type=power_type,
                        area_code=dev.area_code or "A1",
                        monitor_device_id=dev.id,
                        is_enabled=True,
                        created_at=datetime.now(),
                        updated_at=datetime.now(),
                    )
                    self.db.add(pd)
                    await self.db.flush()
                    created_power_for_devices += 1

        await self.db.commit()

        return {
            "linked_panels": linked_panels,
            "linked_power_devices": linked_power_devices,
            "created_devices_for_panels": created_devices_for_panels,
            "created_devices_for_power": created_devices_for_power,
            "created_panels_for_devices": created_panels_for_devices,
            "created_power_for_devices": created_power_for_devices,
        }
