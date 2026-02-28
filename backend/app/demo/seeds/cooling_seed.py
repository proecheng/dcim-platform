"""
制冷设备种子数据 - 创建精密空调、群控组、冷通道及其关联点位
"""

from datetime import date
from sqlalchemy import select

from ...core.database import async_session
from ...models.device import Device
from ...models.point import Point
from ...models.cooling import CoolingUnit, CoolingGroup, ColdAisle

import logging

logger = logging.getLogger(__name__)


# ========== 群控组定义 ==========
COOLING_GROUPS = [
    {
        "group_name": "A区群控组",
        "group_mode": "linked",
        "description": "A区精密空调群控",
    },
    {
        "group_name": "B区群控组",
        "group_mode": "linked",
        "description": "B区精密空调群控",
    },
]

# ========== 精密空调定义 ==========
INDOOR_AC_DEVICES = [
    {
        "device_code": "AC-A01",
        "device_name": "A区1号精密空调",
        "area_code": "A1",
        "manufacturer": "华为",
        "model": "NetCol8000-C070",
        "cooling_capacity_kw": 70.0,
        "refrigerant_type": "R410A",
        "compressor_count": 2,
        "fan_count": 3,
        "group_name": "A区群控组",
    },
    {
        "device_code": "AC-A02",
        "device_name": "A区2号精密空调",
        "area_code": "A1",
        "manufacturer": "华为",
        "model": "NetCol8000-C070",
        "cooling_capacity_kw": 70.0,
        "refrigerant_type": "R410A",
        "compressor_count": 2,
        "fan_count": 3,
        "group_name": "A区群控组",
    },
    {
        "device_code": "AC-B01",
        "device_name": "B区1号精密空调",
        "area_code": "B1",
        "manufacturer": "艾默生",
        "model": "PEX4-70",
        "cooling_capacity_kw": 70.0,
        "refrigerant_type": "R410A",
        "compressor_count": 2,
        "fan_count": 3,
        "group_name": "B区群控组",
    },
]

OUTDOOR_AC_DEVICES = [
    {
        "device_code": "AC-OUT-A01",
        "device_name": "A区1号室外机",
        "area_code": "A1",
        "manufacturer": "华为",
        "model": "NetCol8000-A070",
        "cooling_capacity_kw": 70.0,
        "refrigerant_type": "R410A",
        "compressor_count": 1,
        "fan_count": 2,
    },
    {
        "device_code": "AC-OUT-A02",
        "device_name": "A区2号室外机",
        "area_code": "A1",
        "manufacturer": "华为",
        "model": "NetCol8000-A070",
        "cooling_capacity_kw": 70.0,
        "refrigerant_type": "R410A",
        "compressor_count": 1,
        "fan_count": 2,
    },
]

# ========== 冷通道定义 ==========
COLD_AISLE_DEVICES = [
    {
        "device_code": "CA-A01",
        "device_name": "A区1号冷通道",
        "area_code": "A1",
        "manufacturer": "华为",
        "model": "FusionModule2000",
        "aisle_code": "CA-A01",
        "aisle_name": "A区1号通道",
        "skylight_count": 4,
        "location": "A区机房1排",
    },
    {
        "device_code": "CA-A02",
        "device_name": "A区2号冷通道",
        "area_code": "A1",
        "manufacturer": "华为",
        "model": "FusionModule2000",
        "aisle_code": "CA-A02",
        "aisle_name": "A区2号通道",
        "skylight_count": 4,
        "location": "A区机房2排",
    },
]


def _ac_points(code: str):
    """生成精密空调的点位列表"""
    return [
        # 送风回风温湿度
        {"suffix": "supply_temp", "name": "送风温度", "type": "AI", "unit": "℃", "min": 18, "max": 25, "addr": "40001"},
        {
            "suffix": "supply_humidity",
            "name": "送风湿度",
            "type": "AI",
            "unit": "%",
            "min": 30,
            "max": 60,
            "addr": "40002",
        },
        {"suffix": "return_temp", "name": "回风温度", "type": "AI", "unit": "℃", "min": 25, "max": 35, "addr": "40003"},
        {
            "suffix": "return_humidity",
            "name": "回风湿度",
            "type": "AI",
            "unit": "%",
            "min": 30,
            "max": 70,
            "addr": "40004",
        },
        # 压缩机
        {
            "suffix": "compressor1_voltage",
            "name": "压缩机1电压",
            "type": "AI",
            "unit": "V",
            "min": 360,
            "max": 400,
            "addr": "40005",
        },
        {
            "suffix": "compressor1_current",
            "name": "压缩机1电流",
            "type": "AI",
            "unit": "A",
            "min": 5,
            "max": 20,
            "addr": "40006",
        },
        {
            "suffix": "compressor2_voltage",
            "name": "压缩机2电压",
            "type": "AI",
            "unit": "V",
            "min": 360,
            "max": 400,
            "addr": "40007",
        },
        {
            "suffix": "compressor2_current",
            "name": "压缩机2电流",
            "type": "AI",
            "unit": "A",
            "min": 5,
            "max": 20,
            "addr": "40008",
        },
        {
            "suffix": "compressor1_freq",
            "name": "压缩机1频率",
            "type": "AI",
            "unit": "Hz",
            "min": 30,
            "max": 100,
            "addr": "40009",
        },
        {
            "suffix": "compressor2_freq",
            "name": "压缩机2频率",
            "type": "AI",
            "unit": "Hz",
            "min": 30,
            "max": 100,
            "addr": "40010",
        },
        # 风机
        {"suffix": "fan1_speed", "name": "风机1转速", "type": "AI", "unit": "%", "min": 0, "max": 100, "addr": "40011"},
        {"suffix": "fan2_speed", "name": "风机2转速", "type": "AI", "unit": "%", "min": 0, "max": 100, "addr": "40012"},
        {"suffix": "fan3_speed", "name": "风机3转速", "type": "AI", "unit": "%", "min": 0, "max": 100, "addr": "40013"},
        # 制冷量与功率
        {
            "suffix": "cooling_capacity",
            "name": "制冷量",
            "type": "AI",
            "unit": "kW",
            "min": 0,
            "max": 70,
            "addr": "40014",
        },
        {"suffix": "power", "name": "功耗", "type": "AI", "unit": "kW", "min": 0, "max": 25, "addr": "40015"},
        {"suffix": "cop", "name": "COP", "type": "AI", "unit": "", "min": 2, "max": 5, "addr": "40016"},
        # DI状态
        {
            "suffix": "compressor1_status",
            "name": "压缩机1状态",
            "type": "DI",
            "unit": "",
            "min": 0,
            "max": 1,
            "addr": "10001",
        },
        {
            "suffix": "compressor2_status",
            "name": "压缩机2状态",
            "type": "DI",
            "unit": "",
            "min": 0,
            "max": 1,
            "addr": "10002",
        },
        {"suffix": "fan1_status", "name": "风机1状态", "type": "DI", "unit": "", "min": 0, "max": 1, "addr": "10003"},
        {"suffix": "fan2_status", "name": "风机2状态", "type": "DI", "unit": "", "min": 0, "max": 1, "addr": "10004"},
        {"suffix": "filter_alarm", "name": "滤网告警", "type": "DI", "unit": "", "min": 0, "max": 1, "addr": "10005"},
        {
            "suffix": "high_temp_alarm",
            "name": "高温告警",
            "type": "DI",
            "unit": "",
            "min": 0,
            "max": 1,
            "addr": "10006",
        },
    ]


def _outdoor_ac_points(code: str):
    """生成室外机的点位列表"""
    return [
        {
            "suffix": "ambient_temp",
            "name": "环境温度",
            "type": "AI",
            "unit": "℃",
            "min": -10,
            "max": 45,
            "addr": "40001",
        },
        {
            "suffix": "condenser_temp",
            "name": "冷凝器温度",
            "type": "AI",
            "unit": "℃",
            "min": 30,
            "max": 70,
            "addr": "40002",
        },
        {
            "suffix": "discharge_pressure",
            "name": "排气压力",
            "type": "AI",
            "unit": "bar",
            "min": 10,
            "max": 30,
            "addr": "40003",
        },
        {
            "suffix": "suction_pressure",
            "name": "吸气压力",
            "type": "AI",
            "unit": "bar",
            "min": 3,
            "max": 10,
            "addr": "40004",
        },
        {"suffix": "fan_speed", "name": "风机转速", "type": "AI", "unit": "%", "min": 0, "max": 100, "addr": "40005"},
        {
            "suffix": "compressor_status",
            "name": "压缩机状态",
            "type": "DI",
            "unit": "",
            "min": 0,
            "max": 1,
            "addr": "10001",
        },
    ]


def _cold_aisle_points(code: str):
    """生成冷通道的点位列表"""
    return [
        {"suffix": "aisle_temp", "name": "通道温度", "type": "AI", "unit": "℃", "min": 20, "max": 30, "addr": "40001"},
        {
            "suffix": "aisle_humidity",
            "name": "通道湿度",
            "type": "AI",
            "unit": "%",
            "min": 30,
            "max": 70,
            "addr": "40002",
        },
        {
            "suffix": "differential_pressure",
            "name": "通道压差",
            "type": "AI",
            "unit": "Pa",
            "min": 0,
            "max": 50,
            "addr": "40003",
        },
        {
            "suffix": "skylight1_status",
            "name": "天窗1状态",
            "type": "DI",
            "unit": "",
            "min": 0,
            "max": 1,
            "addr": "10001",
        },
        {
            "suffix": "skylight2_status",
            "name": "天窗2状态",
            "type": "DI",
            "unit": "",
            "min": 0,
            "max": 1,
            "addr": "10002",
        },
        {"suffix": "fire_alarm", "name": "消防告警", "type": "DI", "unit": "", "min": 0, "max": 1, "addr": "10003"},
    ]


def _create_point(device_id: int, device_type: str, device_code: str, pt: dict, sort_idx: int):
    """创建Point对象"""
    point_code = f"{device_code}_{pt['suffix']}"
    return Point(
        point_code=point_code,
        point_name=pt["name"],
        point_type=pt["type"],
        device_id=device_id,
        device_type=device_type,
        area_code="A1",
        unit=pt["unit"],
        data_type="float" if pt["type"] == "AI" else "int",
        min_range=pt["min"],
        max_range=pt["max"],
        precision=2 if pt["type"] == "AI" else 0,
        collect_interval=5,
        store_interval=60,
        is_enabled=True,
        register_address=pt.get("addr"),
        scale_factor=1.0,
        sort_order=sort_idx,
    )


async def seed_cooling_devices():
    """种子数据：创建制冷设备及关联点位"""
    async with async_session() as session:
        # 检查是否已有AC-A01设备，避免重复创建
        existing = await session.execute(select(Device).where(Device.device_code == "AC-A01"))
        if existing.scalar_one_or_none():
            logger.info("制冷种子数据已存在，跳过")
            return

        logger.info("开始创建制冷种子数据...")

        # ===== 1. 创建群控组 =====
        group_map = {}
        for group_data in COOLING_GROUPS:
            group = CoolingGroup(
                group_name=group_data["group_name"],
                group_mode=group_data["group_mode"],
                description=group_data["description"],
            )
            session.add(group)
            await session.flush()
            group_map[group_data["group_name"]] = group.id
            logger.info(f"创建群控组: {group_data['group_name']}")

        # ===== 2. 创建室内精密空调 =====
        for ac_data in INDOOR_AC_DEVICES:
            # 创建设备
            device = Device(
                device_code=ac_data["device_code"],
                device_name=ac_data["device_name"],
                device_type="PRECISION_AC_INDOOR",
                area_code=ac_data["area_code"],
                manufacturer=ac_data["manufacturer"],
                model=ac_data["model"],
                status="running",
                install_date=date.today(),
            )
            session.add(device)
            await session.flush()

            # 创建扩展记录
            group_id = group_map.get(ac_data.get("group_name"))
            ac_unit = CoolingUnit(
                device_id=device.id,
                unit_type="indoor",
                cooling_capacity_kw=ac_data["cooling_capacity_kw"],
                refrigerant_type=ac_data["refrigerant_type"],
                compressor_count=ac_data["compressor_count"],
                fan_count=ac_data["fan_count"],
                group_id=group_id,
            )
            session.add(ac_unit)

            # 创建点位
            for idx, pt in enumerate(_ac_points(ac_data["device_code"])):
                point = _create_point(device.id, "PRECISION_AC_INDOOR", ac_data["device_code"], pt, idx)
                session.add(point)

            logger.info(f"创建室内空调: {ac_data['device_code']}")

        # ===== 3. 创建室外机 =====
        for ac_data in OUTDOOR_AC_DEVICES:
            device = Device(
                device_code=ac_data["device_code"],
                device_name=ac_data["device_name"],
                device_type="PRECISION_AC_OUTDOOR",
                area_code=ac_data["area_code"],
                manufacturer=ac_data["manufacturer"],
                model=ac_data["model"],
                status="running",
                install_date=date.today(),
            )
            session.add(device)
            await session.flush()

            ac_unit = CoolingUnit(
                device_id=device.id,
                unit_type="outdoor",
                cooling_capacity_kw=ac_data["cooling_capacity_kw"],
                refrigerant_type=ac_data["refrigerant_type"],
                compressor_count=ac_data["compressor_count"],
                fan_count=ac_data["fan_count"],
            )
            session.add(ac_unit)

            for idx, pt in enumerate(_outdoor_ac_points(ac_data["device_code"])):
                point = _create_point(device.id, "PRECISION_AC_OUTDOOR", ac_data["device_code"], pt, idx)
                session.add(point)

            logger.info(f"创建室外机: {ac_data['device_code']}")

        # ===== 4. 创建冷通道 =====
        for ca_data in COLD_AISLE_DEVICES:
            device = Device(
                device_code=ca_data["device_code"],
                device_name=ca_data["device_name"],
                device_type="COLD_AISLE",
                area_code=ca_data["area_code"],
                manufacturer=ca_data["manufacturer"],
                model=ca_data["model"],
                status="running",
                install_date=date.today(),
            )
            session.add(device)
            await session.flush()

            aisle = ColdAisle(
                device_id=device.id,
                aisle_code=ca_data["aisle_code"],
                aisle_name=ca_data["aisle_name"],
                skylight_count=ca_data["skylight_count"],
                location=ca_data["location"],
            )
            session.add(aisle)

            for idx, pt in enumerate(_cold_aisle_points(ca_data["device_code"])):
                point = _create_point(device.id, "COLD_AISLE", ca_data["device_code"], pt, idx)
                session.add(point)

            logger.info(f"创建冷通道: {ca_data['device_code']}")

        await session.commit()
        logger.info("制冷种子数据创建完成")
