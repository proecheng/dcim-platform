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
from ..models.cooling import CoolingUnit, ColdAisle

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
        "CHILLER": "AC",
        "CT": "AC",
        "PUMP": "AC",
        "LIGHT": "LIGHT",
    }

    # Device.device_type → 拓扑 PowerDevice.device_type
    DEVICE_TO_POWER_TYPE_MAP = {
        "UPS": "UPS",
        "AC": "HVAC",
        "PDU": "PDU",
        "IT": "IT_SERVER",
        "PRECISION_AC_INDOOR": "HVAC",
        "PRECISION_AC_OUTDOOR": "HVAC",
        "COLD_AISLE": "HVAC",
    }

    # 映射到 DistributionPanel 的 Device 类型
    PANEL_DEVICE_TYPES = {"CABINET"}

    # 映射到 PowerDevice 的 Device 类型
    POWER_DEVICE_TYPES = {"UPS", "PDU", "AC", "IT", "PRECISION_AC_INDOOR", "PRECISION_AC_OUTDOOR", "COLD_AISLE"}

    # Device 自动同步到 PowerDevice 时的默认额定功率 (kW)
    DEFAULT_RATED_POWER = {
        "UPS": 200.0,
        "PDU": 22.0,      # 32A × 380V × 0.9功率因数 / 1000 ≈ 10.9kW/相, 三相约22kW
        "HVAC": 50.0,
        "IT_SERVER": 20.0,
        "IT_STORAGE": 30.0,
    }

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
            existing = await self.db.execute(select(Device).where(Device.device_code == panel.panel_code))
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
            existing = await self.db.execute(select(Device).where(Device.device_code == power_device.device_code))
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
                ups_existing = await self.db.execute(select(UPSDevice).where(UPSDevice.device_id == device.id))
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
                    select(DistributionPanel).where(DistributionPanel.panel_code == device.device_code)
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
                    select(PowerDevice).where(PowerDevice.device_code == device.device_code)
                )
                pd = existing.scalar_one_or_none()
                if pd:
                    pd.monitor_device_id = device.id
                    return ("device", pd.id)

                # 创建新 PowerDevice（未挂载到任何回路，用户可在拓扑中拖拽连接）
                power_type = self.DEVICE_TO_POWER_TYPE_MAP.get(device.device_type, "OTHER")
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
            result = await self.db.execute(select(Device).where(Device.id == panel.device_id))
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
            result = await self.db.execute(select(Device).where(Device.id == power_device.monitor_device_id))
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
                    select(DistributionPanel).where(DistributionPanel.device_id == device.id)
                )
                panel = result.scalar_one_or_none()
                if panel:
                    panel.panel_name = device.device_name
                    panel.panel_code = device.device_code
                    panel.updated_at = datetime.now()

            elif device.device_type in self.POWER_DEVICE_TYPES:
                result = await self.db.execute(select(PowerDevice).where(PowerDevice.monitor_device_id == device.id))
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
            result = await self.db.execute(select(DistributionPanel).where(DistributionPanel.id == panel_id))
            panel = result.scalar_one_or_none()
            if panel and panel.device_id:
                dev_result = await self.db.execute(select(Device).where(Device.id == panel.device_id))
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
            result = await self.db.execute(select(PowerDevice).where(PowerDevice.id == power_device_id))
            pd = result.scalar_one_or_none()
            if pd and pd.monitor_device_id:
                dev_result = await self.db.execute(select(Device).where(Device.id == pd.monitor_device_id))
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
                    select(DistributionPanel).where(DistributionPanel.device_id == device.id)
                )
                panel = result.scalar_one_or_none()
                if panel:
                    panel.is_enabled = False
                    panel.device_id = None
                    panel.updated_at = datetime.now()

            elif device.device_type in self.POWER_DEVICE_TYPES:
                result = await self.db.execute(select(PowerDevice).where(PowerDevice.monitor_device_id == device.id))
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
            (
                await self.db.execute(
                    select(DistributionPanel).where(
                        DistributionPanel.device_id.is_(None),
                        DistributionPanel.is_enabled == True,
                    )
                )
            )
            .scalars()
            .all()
        )

        for panel in panels:
            device = (
                await self.db.execute(select(Device).where(Device.device_code == panel.panel_code))
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
            (
                await self.db.execute(
                    select(PowerDevice).where(
                        PowerDevice.monitor_device_id.is_(None),
                        PowerDevice.is_enabled == True,
                    )
                )
            )
            .scalars()
            .all()
        )

        for pd in power_devices:
            device_type = self.POWER_DEVICE_TYPE_MAP.get(pd.device_type)
            if not device_type:
                continue

            device = (
                await self.db.execute(select(Device).where(Device.device_code == pd.device_code))
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
            (
                await self.db.execute(
                    select(Device).where(
                        Device.device_type == self.PANEL_TO_DEVICE_TYPE,
                        Device.is_enabled == True,
                    )
                )
            )
            .scalars()
            .all()
        )

        for dev in cabinet_devices:
            # 检查是否已有关联的 Panel（通过 device_id 或 device_code）
            existing_panel = (
                await self.db.execute(
                    select(DistributionPanel).where(
                        (DistributionPanel.device_id == dev.id) | (DistributionPanel.panel_code == dev.device_code)
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

        # 先构建 circuit_code -> circuit_id 映射
        from ..models.energy import DistributionCircuit
        circuit_result = await self.db.execute(select(DistributionCircuit))
        circuit_map = {c.circuit_code: c.id for c in circuit_result.scalars().all()}

        for dev_type, power_type in self.DEVICE_TO_POWER_TYPE_MAP.items():
            devs = (
                (
                    await self.db.execute(
                        select(Device).where(
                            Device.device_type == dev_type,
                            Device.is_enabled == True,
                        )
                    )
                )
                .scalars()
                .all()
            )
            for dev in devs:
                existing_pd = (
                    await self.db.execute(
                        select(PowerDevice).where(
                            (PowerDevice.monitor_device_id == dev.id) | (PowerDevice.device_code == dev.device_code)
                        )
                    )
                ).scalar_one_or_none()
                if not existing_pd:
                    # 智能分配 circuit_id
                    circuit_id = self._infer_circuit_id(dev, circuit_map)

                    pd = PowerDevice(
                        device_code=dev.device_code,
                        device_name=dev.device_name,
                        device_type=power_type,
                        rated_power=self.DEFAULT_RATED_POWER.get(power_type, 20.0),
                        area_code=dev.area_code or "A1",
                        circuit_id=circuit_id,  # 新增：分配回路
                        monitor_device_id=dev.id,
                        is_enabled=True,
                        created_at=datetime.now(),
                        updated_at=datetime.now(),
                    )
                    self.db.add(pd)
                    await self.db.flush()
                    created_power_for_devices += 1
                elif not existing_pd.rated_power:
                    # 补充已有设备缺失的额定功率
                    existing_pd.rated_power = self.DEFAULT_RATED_POWER.get(power_type, 20.0)
                    existing_pd.updated_at = datetime.now()

                # 补充已有设备缺失的 circuit_id
                if existing_pd and not existing_pd.circuit_id:
                    circuit_id = self._infer_circuit_id(dev, circuit_map)
                    if circuit_id:
                        existing_pd.circuit_id = circuit_id
                        existing_pd.updated_at = datetime.now()
        # 5. 为所有已有 Device 补全扩展记录 (UPSDevice / CoolingUnit / ColdAisle)
        created_ups_ext = 0
        created_cooling_ext = 0
        created_cold_aisle_ext = 0

        # 5a. UPS → UPSDevice
        ups_devices = (
            await self.db.execute(
                select(Device).where(Device.device_type == "UPS", Device.is_enabled == True)
            )
        ).scalars().all()
        for dev in ups_devices:
            existing = (
                await self.db.execute(select(UPSDevice).where(UPSDevice.device_id == dev.id))
            ).scalar_one_or_none()
            if not existing:
                # 尝试从 PowerDevice 获取额定功率
                pd_match = (
                    await self.db.execute(
                        select(PowerDevice).where(PowerDevice.monitor_device_id == dev.id)
                    )
                ).scalar_one_or_none()
                rated = pd_match.rated_power if pd_match and pd_match.rated_power else 200.0
                ups = UPSDevice(
                    device_id=dev.id,
                    rated_capacity=rated,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )
                self.db.add(ups)
                created_ups_ext += 1

        # 5b. AC/PRECISION_AC_INDOOR/PRECISION_AC_OUTDOOR → CoolingUnit
        ac_types = ("AC", "PRECISION_AC_INDOOR", "PRECISION_AC_OUTDOOR")
        for ac_type in ac_types:
            ac_devs = (
                await self.db.execute(
                    select(Device).where(Device.device_type == ac_type, Device.is_enabled == True)
                )
            ).scalars().all()
            for dev in ac_devs:
                existing = (
                    await self.db.execute(select(CoolingUnit).where(CoolingUnit.device_id == dev.id))
                ).scalar_one_or_none()
                if not existing:
                    unit_type = "outdoor" if ac_type == "PRECISION_AC_OUTDOOR" else "indoor"
                    cu = CoolingUnit(
                        device_id=dev.id,
                        unit_type=unit_type,
                        created_at=datetime.now(),
                        updated_at=datetime.now(),
                    )
                    self.db.add(cu)
                    created_cooling_ext += 1

        # 5c. COLD_AISLE → ColdAisle
        ca_devs = (
            await self.db.execute(
                select(Device).where(Device.device_type == "COLD_AISLE", Device.is_enabled == True)
            )
        ).scalars().all()
        for dev in ca_devs:
            existing = (
                await self.db.execute(select(ColdAisle).where(ColdAisle.device_id == dev.id))
            ).scalar_one_or_none()
            if not existing:
                ca = ColdAisle(
                    device_id=dev.id,
                    aisle_code=dev.device_code,
                    aisle_name=dev.device_name,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )
                self.db.add(ca)
                created_cold_aisle_ext += 1

        if created_ups_ext or created_cooling_ext or created_cold_aisle_ext:
            await self.db.flush()

        await self.db.commit()

        return {
            "linked_panels": linked_panels,
            "linked_power_devices": linked_power_devices,
            "created_devices_for_panels": created_devices_for_panels,
            "created_devices_for_power": created_devices_for_power,
            "created_panels_for_devices": created_panels_for_devices,
            "created_power_for_devices": created_power_for_devices,
            "created_ups_extensions": created_ups_ext,
            "created_cooling_extensions": created_cooling_ext,
            "created_cold_aisle_extensions": created_cold_aisle_ext,
        }

    def _infer_circuit_id(self, device: Device, circuit_map: dict) -> Optional[int]:
        """
        根据设备编码和类型智能推断应该绑定的回路ID

        规则：
        - UPS-FX-XX → C-FX-UPS-01
        - PDU-FX-XX → C-FX-PDU-01/02 (轮询)
        - CA-FX-XX (冷通道) → C-FX-CA-01
        - PMP-F1-0[1-4] (冷冻水泵) → C-CHWP-01
        - PMP-F1-0[7-9] (冷却水泵) → C-CWP-01
        - PMP-F1-XX (其他水泵) → C-PMP-01/02 (轮询)
        - AC-OUT-XX (室外机) → C-AC-OUT-01
        - CA-AXX (区域冷通道) → C-CA-A-01
        - CH-XX (冷机) → C-CH-01
        - CT-XX (冷却塔) → C-CT-01
        - AC-A/B (精密空调) → C-AC-01/02
        - FX-AC-XX (楼层空调) → C-FX-AC-01
        - LIGHT → C-LIGHT
        """
        code = device.device_code
        dev_type = device.device_type

        # UPS 设备
        if dev_type == "UPS":
            # UPS-F1-XX → C-F1-UPS-01
            for floor in ["F1", "F2", "F3", "F4"]:
                if code.startswith(f"UPS-{floor}-") or code.startswith(f"{floor}-UPS-"):
                    return circuit_map.get(f"C-{floor}-UPS-01")

        # PDU 设备
        elif dev_type == "PDU":
            # PDU-F2-XX → C-F2-PDU-GENERIC
            if code.startswith("PDU-F2-"):
                return circuit_map.get("C-F2-PDU-GENERIC")
            elif code.startswith("PDU-F3-"):
                return circuit_map.get("C-F3-PDU-GENERIC")
            elif code.startswith("PDU-F4-"):
                return circuit_map.get("C-F4-PDU-GENERIC")
            
            # 旧的 A1/B1 区域 PDU
            area = device.area_code or ""
            if "A1" in area or "A" in code:
                return circuit_map.get("C-A1-01")
            elif "B1" in area or "B" in code:
                return circuit_map.get("C-B1-01")

        # HVAC 设备 (制冷、空调、水泵等)
        elif dev_type in ("AC", "HVAC"):
            # 冷通道 CA-XX → C-CA-GENERIC (通用回路)
            if code.startswith("CA-"):
                return circuit_map.get("C-CA-GENERIC")
            
            # 水泵 PMP-F1-XX
            if code.startswith("PMP-"):
                # 冷冻水泵 01-04
                if any(code.endswith(f"-0{i}") for i in [1, 2, 3, 4]):
                    return circuit_map.get("C-CHWP-01")
                # 冷却水泵 07-09
                elif any(code.endswith(f"-0{i}") for i in [7, 8, 9]):
                    return circuit_map.get("C-CWP-01")
                # 其他水泵 → 通用回路
                else:
                    return circuit_map.get("C-PMP-GENERIC")
            
            # 室外机 AC-OUT-XX → C-AC-OUT-GENERIC
            if code.startswith("AC-OUT-"):
                return circuit_map.get("C-AC-OUT-GENERIC")
            
            # 冷机 CH-XX → C-CH-01
            if code.startswith("CH-"):
                return circuit_map.get("C-CH-01")
            
            # 冷却塔 CT-XX → C-CT-01
            if code.startswith("CT-"):
                return circuit_map.get("C-CT-01")
            
            # 楼层空调 F1-AC-XX → C-F1-AC-01
            for floor in ["F1", "F2", "F3", "F4"]:
                if code.startswith(f"{floor}-AC-"):
                    return circuit_map.get(f"C-{floor}-AC-01")
            
            # 精密空调 AC-A/B → C-AC-01/02
            if code.startswith("AC-A"):
                return circuit_map.get("C-AC-01")
            elif code.startswith("AC-B"):
                return circuit_map.get("C-AC-02")
        elif dev_type in ("AC", "HVAC"):
            # 冷通道 CA-F2-XX → C-F2-CA-01
            for floor in ["F2", "F3", "F4"]:
                if code.startswith(f"CA-{floor}-"):
                    return circuit_map.get(f"C-{floor}-CA-01")
            
            # 区域冷通道 CA-A01 → C-CA-A-01
            if code.startswith("CA-A"):
                return circuit_map.get("C-CA-A-01")
            
            # 水泵 PMP-F1-XX
            if code.startswith("PMP-"):
                # 冷冻水泵 01-04
                if any(code.endswith(f"-0{i}") for i in [1, 2, 3, 4]):
                    return circuit_map.get("C-CHWP-01")
                # 冷却水泵 07-09
                elif any(code.endswith(f"-0{i}") for i in [7, 8, 9]):
                    return circuit_map.get("C-CWP-01")
                # 其他水泵 05-06, 10-12 → 轮询分配
                else:
                    try:
                        num = int(code.split("-")[-1])
                        circuit_suffix = "01" if num % 2 == 1 else "02"
                        return circuit_map.get(f"C-PMP-{circuit_suffix}")
                    except (ValueError, IndexError):
                        return circuit_map.get("C-PMP-01")
            
            # 室外机 AC-OUT-XX → C-AC-OUT-01
            if code.startswith("AC-OUT-"):
                return circuit_map.get("C-AC-OUT-01")
            
            # 冷机 CH-XX → C-CH-01
            if code.startswith("CH-"):
                return circuit_map.get("C-CH-01")
            
            # 冷却塔 CT-XX → C-CT-01
            if code.startswith("CT-"):
                return circuit_map.get("C-CT-01")
            
            # 楼层空调 F1-AC-XX → C-F1-AC-01
            for floor in ["F1", "F2", "F3", "F4"]:
                if code.startswith(f"{floor}-AC-"):
                    return circuit_map.get(f"C-{floor}-AC-01")
            
            # 精密空调 AC-A/B → C-AC-01/02
            if code.startswith("AC-A"):
                return circuit_map.get("C-AC-01")
            elif code.startswith("AC-B"):
                return circuit_map.get("C-AC-02")

        # IT 设备
        elif dev_type == "IT":
            area = device.area_code or ""
            if "A1" in area or "A" in code:
                return circuit_map.get("C-A1-01")
            elif "B1" in area or "B" in code:
                return circuit_map.get("C-B1-01")

        # 照明
        elif dev_type == "LIGHT":
            return circuit_map.get("C-LIGHT")

        return None
