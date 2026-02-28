"""
供配电设备种子数据 - 创建UPS、电池组、配电柜、PDU及其关联点位
"""

from datetime import date
from sqlalchemy import select

from ...core.database import async_session
from ...models.device import Device
from ...models.point import Point
from ...models.power import UPSDevice, BatteryGroup

import logging

logger = logging.getLogger(__name__)


# ========== UPS设备定义 ==========
UPS_DEVICES = [
    {
        "device_code": "UPS-A01",
        "device_name": "A区1号UPS",
        "area_code": "A1",
        "manufacturer": "华为",
        "model": "UPS5000-E-200kVA",
        "ups_type": "modular",
        "rated_capacity": 200.0,
        "rated_voltage": 380.0,
        "phase_count": 3,
        "battery_group_count": 2,
        "bypass_enabled": True,
    },
    {
        "device_code": "UPS-A02",
        "device_name": "A区2号UPS",
        "area_code": "A2",
        "manufacturer": "华为",
        "model": "UPS5000-E-120kVA",
        "ups_type": "standalone",
        "rated_capacity": 120.0,
        "rated_voltage": 380.0,
        "phase_count": 3,
        "battery_group_count": 2,
        "bypass_enabled": True,
    },
]

# ========== 配电柜定义 ==========
CABINET_DEVICES = [
    {
        "device_code": "CAB-A01",
        "device_name": "A区主配电柜",
        "area_code": "A1",
        "manufacturer": "施耐德",
        "model": "Prisma iPM",
    },
    {
        "device_code": "CAB-B01",
        "device_name": "B区主配电柜",
        "area_code": "B1",
        "manufacturer": "ABB",
        "model": "MNS3.0",
    },
]

# ========== PDU定义 ==========
PDU_DEVICES = [
    {
        "device_code": "PDU-A01",
        "device_name": "A1区列头柜1",
        "area_code": "A1",
        "manufacturer": "台达",
        "model": "PDU-32A-3P",
        "rated_power": 22.0,
    },
    {
        "device_code": "PDU-A02",
        "device_name": "A1区列头柜2",
        "area_code": "A1",
        "manufacturer": "台达",
        "model": "PDU-32A-3P",
        "rated_power": 22.0,
    },
    {
        "device_code": "PDU-B01",
        "device_name": "B1区列头柜1",
        "area_code": "B1",
        "manufacturer": "台达",
        "model": "PDU-32A-3P",
        "rated_power": 22.0,
    },
    {
        "device_code": "PDU-B02",
        "device_name": "B1区列头柜2",
        "area_code": "B1",
        "manufacturer": "台达",
        "model": "PDU-32A-3P",
        "rated_power": 22.0,
    },
]


def _ups_points(code: str):
    """生成UPS设备的点位列表"""
    return [
        # AI 点位
        {
            "suffix": "input_voltage_a",
            "name": "输入电压A相",
            "type": "AI",
            "unit": "V",
            "min": 340,
            "max": 420,
            "addr": "40001",
        },
        {
            "suffix": "input_voltage_b",
            "name": "输入电压B相",
            "type": "AI",
            "unit": "V",
            "min": 340,
            "max": 420,
            "addr": "40002",
        },
        {
            "suffix": "input_voltage_c",
            "name": "输入电压C相",
            "type": "AI",
            "unit": "V",
            "min": 340,
            "max": 420,
            "addr": "40003",
        },
        {
            "suffix": "output_voltage_a",
            "name": "输出电压A相",
            "type": "AI",
            "unit": "V",
            "min": 210,
            "max": 230,
            "addr": "40004",
        },
        {
            "suffix": "output_voltage_b",
            "name": "输出电压B相",
            "type": "AI",
            "unit": "V",
            "min": 210,
            "max": 230,
            "addr": "40005",
        },
        {
            "suffix": "output_voltage_c",
            "name": "输出电压C相",
            "type": "AI",
            "unit": "V",
            "min": 210,
            "max": 230,
            "addr": "40006",
        },
        {
            "suffix": "input_freq",
            "name": "输入频率",
            "type": "AI",
            "unit": "Hz",
            "min": 49.0,
            "max": 51.0,
            "addr": "40007",
        },
        {
            "suffix": "output_freq",
            "name": "输出频率",
            "type": "AI",
            "unit": "Hz",
            "min": 49.5,
            "max": 50.5,
            "addr": "40008",
        },
        {
            "suffix": "input_power_factor",
            "name": "输入功率因数",
            "type": "AI",
            "unit": "",
            "min": 0.8,
            "max": 1.0,
            "addr": "40009",
        },
        {
            "suffix": "output_power_factor",
            "name": "输出功率因数",
            "type": "AI",
            "unit": "",
            "min": 0.8,
            "max": 1.0,
            "addr": "40010",
        },
        {"suffix": "load_rate", "name": "负载率", "type": "AI", "unit": "%", "min": 0, "max": 100, "addr": "40011"},
        {
            "suffix": "backup_time",
            "name": "备电时间",
            "type": "AI",
            "unit": "min",
            "min": 10,
            "max": 120,
            "addr": "40012",
        },
        {"suffix": "bus_temp", "name": "母排温度", "type": "AI", "unit": "℃", "min": 20, "max": 60, "addr": "40013"},
        # DI 点位
        {"suffix": "mains_status", "name": "市电状态", "type": "DI", "unit": "", "min": 0, "max": 1, "addr": "10001"},
        {"suffix": "surge_status", "name": "防雷状态", "type": "DI", "unit": "", "min": 0, "max": 1, "addr": "10002"},
    ]


def _battery_points(ups_code: str, group_idx: int):
    """生成电池组的点位列表"""
    prefix = f"{ups_code}_BAT{group_idx}"
    return [
        {
            "suffix": "soh",
            "name": f"电池组{group_idx}健康度",
            "type": "AI",
            "unit": "%",
            "min": 60,
            "max": 100,
            "addr": f"4010{group_idx}",
        },
        {
            "suffix": "soc",
            "name": f"电池组{group_idx}荷电状态",
            "type": "AI",
            "unit": "%",
            "min": 0,
            "max": 100,
            "addr": f"4011{group_idx}",
        },
        {
            "suffix": "voltage",
            "name": f"电池组{group_idx}电压",
            "type": "AI",
            "unit": "V",
            "min": 360,
            "max": 440,
            "addr": f"4012{group_idx}",
        },
        {
            "suffix": "current",
            "name": f"电池组{group_idx}电流",
            "type": "AI",
            "unit": "A",
            "min": -50,
            "max": 50,
            "addr": f"4013{group_idx}",
        },
        {
            "suffix": "temperature",
            "name": f"电池组{group_idx}温度",
            "type": "AI",
            "unit": "℃",
            "min": 15,
            "max": 45,
            "addr": f"4014{group_idx}",
        },
        {
            "suffix": "internal_resistance",
            "name": f"电池组{group_idx}内阻",
            "type": "AI",
            "unit": "mΩ",
            "min": 1,
            "max": 5,
            "addr": f"4015{group_idx}",
        },
        {
            "suffix": "backup_time",
            "name": f"电池组{group_idx}备电时间",
            "type": "AI",
            "unit": "min",
            "min": 10,
            "max": 120,
            "addr": f"4016{group_idx}",
        },
        {
            "suffix": "status",
            "name": f"电池组{group_idx}状态",
            "type": "DI",
            "unit": "",
            "min": 0,
            "max": 1,
            "addr": f"1010{group_idx}",
        },
    ], prefix


def _cabinet_points(code: str):
    """生成配电柜的点位列表"""
    return [
        {"suffix": "total_power", "name": "总功率", "type": "AI", "unit": "kW", "min": 0, "max": 500, "addr": "40001"},
        {
            "suffix": "input_voltage_a",
            "name": "输入电压A相",
            "type": "AI",
            "unit": "V",
            "min": 340,
            "max": 420,
            "addr": "40002",
        },
        {
            "suffix": "input_voltage_b",
            "name": "输入电压B相",
            "type": "AI",
            "unit": "V",
            "min": 340,
            "max": 420,
            "addr": "40003",
        },
        {
            "suffix": "input_voltage_c",
            "name": "输入电压C相",
            "type": "AI",
            "unit": "V",
            "min": 340,
            "max": 420,
            "addr": "40004",
        },
        {
            "suffix": "output_current_a",
            "name": "输出电流A相",
            "type": "AI",
            "unit": "A",
            "min": 0,
            "max": 800,
            "addr": "40005",
        },
        {
            "suffix": "output_current_b",
            "name": "输出电流B相",
            "type": "AI",
            "unit": "A",
            "min": 0,
            "max": 800,
            "addr": "40006",
        },
        {
            "suffix": "output_current_c",
            "name": "输出电流C相",
            "type": "AI",
            "unit": "A",
            "min": 0,
            "max": 800,
            "addr": "40007",
        },
        {"suffix": "bus_temp", "name": "母排温度", "type": "AI", "unit": "℃", "min": 20, "max": 60, "addr": "40008"},
    ]


def _pdu_points(code: str):
    """生成PDU的点位列表"""
    points = [
        {"suffix": "total_current", "name": "总电流", "type": "AI", "unit": "A", "min": 0, "max": 32, "addr": "40001"},
        {"suffix": "temperature", "name": "温度", "type": "AI", "unit": "℃", "min": 15, "max": 50, "addr": "40002"},
    ]
    for i in range(1, 5):
        points.append(
            {
                "suffix": f"outlet_current_{i}",
                "name": f"支路{i}电流",
                "type": "AI",
                "unit": "A",
                "min": 0,
                "max": 16,
                "addr": f"4001{i}",
            }
        )
        points.append(
            {
                "suffix": f"outlet_power_{i}",
                "name": f"支路{i}功率",
                "type": "AI",
                "unit": "kW",
                "min": 0,
                "max": 5,
                "addr": f"4002{i}",
            }
        )
    return points


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


async def seed_power_devices():
    """种子数据：创建供配电设备及关联点位"""
    async with async_session() as session:
        # 检查是否已有UPS-A01设备，避免重复创建
        existing = await session.execute(select(Device).where(Device.device_code == "UPS-A01"))
        if existing.scalar_one_or_none():
            logger.info("供配电种子数据已存在，跳过")
            return

        logger.info("开始创建供配电种子数据...")

        # ===== 1. 创建UPS设备 =====
        for ups_def in UPS_DEVICES:
            code = ups_def["device_code"]
            # 创建Device记录
            device = Device(
                device_code=code,
                device_name=ups_def["device_name"],
                device_type="UPS",
                area_code=ups_def["area_code"],
                manufacturer=ups_def.get("manufacturer"),
                model=ups_def.get("model"),
                install_date=date(2025, 6, 1),
                status="online",
                is_enabled=True,
            )
            session.add(device)
            await session.flush()

            # 创建UPSDevice扩展记录
            ups_ext = UPSDevice(
                device_id=device.id,
                ups_type=ups_def["ups_type"],
                rated_capacity=ups_def["rated_capacity"],
                rated_voltage=ups_def["rated_voltage"],
                phase_count=ups_def["phase_count"],
                battery_group_count=ups_def["battery_group_count"],
                bypass_enabled=ups_def["bypass_enabled"],
            )
            session.add(ups_ext)
            await session.flush()

            # 创建UPS点位
            for idx, pt in enumerate(_ups_points(code)):
                session.add(_create_point(device.id, "UPS", code, pt, idx))

            # 创建电池组 + 点位
            for g in range(1, ups_def["battery_group_count"] + 1):
                bg = BatteryGroup(
                    ups_device_id=ups_ext.id,
                    group_name=f"BAT{g}",
                    battery_type="lead_acid" if g == 1 else "lithium",
                    rated_capacity=100.0,
                    rated_voltage=384.0,
                    cell_count=32,
                    install_date=date(2025, 6, 1),
                )
                session.add(bg)

                bat_points, prefix = _battery_points(code, g)
                for idx, pt in enumerate(bat_points):
                    pt_code = f"{prefix}_{pt['suffix']}"
                    p = Point(
                        point_code=pt_code,
                        point_name=pt["name"],
                        point_type=pt["type"],
                        device_id=device.id,
                        device_type="UPS",
                        area_code=ups_def["area_code"],
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
                        sort_order=100 + g * 10 + idx,
                    )
                    session.add(p)

        # ===== 2. 创建配电柜 =====
        for cab_def in CABINET_DEVICES:
            code = cab_def["device_code"]
            device = Device(
                device_code=code,
                device_name=cab_def["device_name"],
                device_type="CABINET",
                area_code=cab_def["area_code"],
                manufacturer=cab_def.get("manufacturer"),
                model=cab_def.get("model"),
                install_date=date(2025, 6, 1),
                status="online",
                is_enabled=True,
            )
            session.add(device)
            await session.flush()

            for idx, pt in enumerate(_cabinet_points(code)):
                session.add(_create_point(device.id, "CABINET", code, pt, idx))

        # ===== 3. 创建PDU =====
        for pdu_def in PDU_DEVICES:
            code = pdu_def["device_code"]
            device = Device(
                device_code=code,
                device_name=pdu_def["device_name"],
                device_type="PDU",
                area_code=pdu_def["area_code"],
                manufacturer=pdu_def.get("manufacturer"),
                model=pdu_def.get("model"),
                install_date=date(2025, 6, 1),
                status="online",
                is_enabled=True,
            )
            session.add(device)
            await session.flush()

            for idx, pt in enumerate(_pdu_points(code)):
                session.add(_create_point(device.id, "PDU", code, pt, idx))

        await session.commit()
        logger.info("供配电种子数据创建完成")
