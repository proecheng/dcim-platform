"""
算力中心完整种子数据 - 创建站点/楼层/房间/设备/点位/实时值
4层数据中心: ~628台设备, ~2830个监控点位
"""

import logging
from datetime import date
from typing import Any

from sqlalchemy import select

from ...core.database import async_session
from ...models.spatial import Site, Floor, Room
from ...models.device import Device
from ...models.point import Point, PointRealtime

logger = logging.getLogger(__name__)


# ==================== 空间拓扑定义 ====================

SITE = {
    "site_code": "SZ-DC-01",
    "site_name": "深圳算力中心",
    "address": "广东省深圳市光明区科学城大道88号",
    "contact_person": "张工",
    "contact_phone": "0755-88886666",
    "status": "active",
    "description": "深圳算力中心，4层建筑，总面积约8000平方米",
}

FLOORS = [
    {"floor_code": "F1", "floor_name": "一层", "sort_order": 1},
    {"floor_code": "F2", "floor_name": "二层", "sort_order": 2},
    {"floor_code": "F3", "floor_name": "三层", "sort_order": 3},
    {"floor_code": "F4", "floor_name": "四层", "sort_order": 4},
]

ROOMS: dict[str, list[dict[str, Any]]] = {
    "F1": [
        {"room_code": "F1-HV", "room_name": "高压配电室", "area_sqm": 200.0},
        {"room_code": "F1-LV", "room_name": "低压配电室", "area_sqm": 300.0},
        {"room_code": "F1-CL", "room_name": "制冷机房", "area_sqm": 400.0},
        {"room_code": "F1-GN", "room_name": "柴发机房", "area_sqm": 250.0},
    ],
    "F2": [
        {"room_code": "F2-A1", "room_name": "A1机房", "area_sqm": 500.0},
        {"room_code": "F2-A2", "room_name": "A2机房", "area_sqm": 500.0},
        {"room_code": "F2-PD", "room_name": "A区列头柜间", "area_sqm": 80.0},
        {"room_code": "F2-CR", "room_name": "A区走廊", "area_sqm": 120.0},
    ],
    "F3": [
        {"room_code": "F3-B1", "room_name": "B1机房", "area_sqm": 500.0},
        {"room_code": "F3-B2", "room_name": "B2机房", "area_sqm": 500.0},
        {"room_code": "F3-PD", "room_name": "B区列头柜间", "area_sqm": 80.0},
        {"room_code": "F3-CR", "room_name": "B区走廊", "area_sqm": 120.0},
    ],
    "F4": [
        {"room_code": "F4-C1", "room_name": "C1机房", "area_sqm": 500.0},
        {"room_code": "F4-C2", "room_name": "C2机房", "area_sqm": 500.0},
        {"room_code": "F4-NC", "room_name": "网络核心机房", "area_sqm": 200.0},
        {"room_code": "F4-CR", "room_name": "C区走廊", "area_sqm": 120.0},
    ],
}


# ==================== 点位模板定义 ====================
# 每种设备类型的点位模板: (suffix, name, point_type, unit, min_range, max_range)

PT_HV_CABINET: list[tuple[str, str, str, str, float, float]] = [
    ("Ua", "A相电压", "AI", "V", 9500.0, 10500.0),
    ("Ub", "B相电压", "AI", "V", 9500.0, 10500.0),
    ("Uc", "C相电压", "AI", "V", 9500.0, 10500.0),
    ("Ia", "A相电流", "AI", "A", 0.0, 200.0),
    ("Ib", "B相电流", "AI", "A", 0.0, 200.0),
    ("Ic", "C相电流", "AI", "A", 0.0, 200.0),
    ("P", "有功功率", "AI", "kW", 0.0, 3000.0),
    ("T", "柜内温度", "AI", "℃", 15.0, 55.0),
]

PT_TRANSFORMER: list[tuple[str, str, str, str, float, float]] = [
    ("HV_U", "高压侧电压", "AI", "kV", 9.5, 10.5),
    ("HV_I", "高压侧电流", "AI", "A", 0.0, 120.0),
    ("LV_U", "低压侧电压", "AI", "V", 370.0, 410.0),
    ("LV_I", "低压侧电流", "AI", "A", 0.0, 2500.0),
    ("T_oil", "油温", "AI", "℃", 20.0, 95.0),
    ("T_wind", "绕组温度", "AI", "℃", 20.0, 120.0),
    ("Load", "负载率", "AI", "%", 0.0, 100.0),
    ("P", "有功功率", "AI", "kW", 0.0, 1600.0),
]

PT_LV_CABINET: list[tuple[str, str, str, str, float, float]] = [
    ("Ua", "A相电压", "AI", "V", 370.0, 410.0),
    ("Ub", "B相电压", "AI", "V", 370.0, 410.0),
    ("Uc", "C相电压", "AI", "V", 370.0, 410.0),
    ("Ia", "A相电流", "AI", "A", 0.0, 1600.0),
    ("Ib", "B相电流", "AI", "A", 0.0, 1600.0),
    ("Ic", "C相电流", "AI", "A", 0.0, 1600.0),
    ("P", "有功功率", "AI", "kW", 0.0, 800.0),
    ("T", "柜内温度", "AI", "℃", 15.0, 55.0),
]

PT_COLUMN_PDU: list[tuple[str, str, str, str, float, float]] = [
    ("Ia", "A相电流", "AI", "A", 0.0, 63.0),
    ("Ib", "B相电流", "AI", "A", 0.0, 63.0),
    ("Ic", "C相电流", "AI", "A", 0.0, 63.0),
    ("P", "总功率", "AI", "kW", 0.0, 40.0),
    ("Ua", "A相电压", "AI", "V", 210.0, 240.0),
    ("PF", "功率因数", "AI", "", 0.80, 1.00),
    ("kWh", "累计电量", "AI", "kWh", 0.0, 99999.0),
    ("T", "柜内温度", "AI", "℃", 15.0, 50.0),
]

PT_UPS: list[tuple[str, str, str, str, float, float]] = [
    ("Uin", "输入电压", "AI", "V", 340.0, 420.0),
    ("Uout", "输出电压", "AI", "V", 210.0, 230.0),
    ("Iin", "输入电流", "AI", "A", 0.0, 400.0),
    ("Iout", "输出电流", "AI", "A", 0.0, 400.0),
    ("Load", "负载率", "AI", "%", 0.0, 100.0),
    ("Ubat", "电池电压", "AI", "V", 340.0, 440.0),
    ("Tbat", "电池温度", "AI", "℃", 15.0, 45.0),
    ("Pin", "输入功率", "AI", "kW", 0.0, 300.0),
    ("Pout", "输出功率", "AI", "kW", 0.0, 300.0),
    ("Freq", "输出频率", "AI", "Hz", 49.5, 50.5),
    ("Eff", "效率", "AI", "%", 85.0, 99.0),
    ("Run", "运行状态", "DI", "", 0.0, 1.0),
]

PT_BATTERY: list[tuple[str, str, str, str, float, float]] = [
    ("U", "电压", "AI", "V", 340.0, 440.0),
    ("I", "电流", "AI", "A", -100.0, 100.0),
    ("T", "温度", "AI", "℃", 15.0, 45.0),
    ("SOC", "荷电状态", "AI", "%", 0.0, 100.0),
    ("SOH", "健康度", "AI", "%", 60.0, 100.0),
    ("Ri", "内阻", "AI", "mΩ", 0.5, 5.0),
]

PT_CHILLER: list[tuple[str, str, str, str, float, float]] = [
    ("Tsup", "供水温度", "AI", "℃", 5.0, 15.0),
    ("Tret", "回水温度", "AI", "℃", 10.0, 22.0),
    ("P", "功率", "AI", "kW", 0.0, 350.0),
    ("Freq", "压缩机频率", "AI", "Hz", 20.0, 60.0),
    ("COP", "能效比", "AI", "", 3.0, 7.0),
    ("Flow", "流量", "AI", "m³/h", 0.0, 200.0),
    ("Load", "负载率", "AI", "%", 0.0, 100.0),
    ("Run", "运行状态", "DI", "", 0.0, 1.0),
    ("Fault", "故障状态", "DI", "", 0.0, 1.0),
]

PT_PUMP: list[tuple[str, str, str, str, float, float]] = [
    ("Run", "运行状态", "DI", "", 0.0, 1.0),
    ("Freq", "频率", "AI", "Hz", 20.0, 50.0),
    ("P", "功率", "AI", "kW", 0.0, 45.0),
    ("Fault", "故障状态", "DI", "", 0.0, 1.0),
    ("I", "电流", "AI", "A", 0.0, 80.0),
]

PT_COOLING_TOWER: list[tuple[str, str, str, str, float, float]] = [
    ("Freq", "风机频率", "AI", "Hz", 15.0, 50.0),
    ("Tin", "进水温度", "AI", "℃", 25.0, 40.0),
    ("Tout", "出水温度", "AI", "℃", 20.0, 35.0),
    ("Run", "运行状态", "DI", "", 0.0, 1.0),
    ("P", "功率", "AI", "kW", 0.0, 30.0),
    ("Fault", "故障状态", "DI", "", 0.0, 1.0),
]

PT_COLD_AISLE: list[tuple[str, str, str, str, float, float]] = [
    ("Tsup", "送风温度", "AI", "℃", 18.0, 27.0),
    ("Tret", "回风温度", "AI", "℃", 25.0, 40.0),
    ("Hsup", "送风湿度", "AI", "%RH", 20.0, 70.0),
    ("Hret", "回风湿度", "AI", "%RH", 20.0, 70.0),
    ("DP", "压差", "AI", "Pa", 0.0, 50.0),
    ("Run", "天窗状态", "DI", "", 0.0, 1.0),
]

PT_TH: list[tuple[str, str, str, str, float, float]] = [
    ("T", "温度", "AI", "℃", 15.0, 40.0),
    ("H", "湿度", "AI", "%RH", 20.0, 80.0),
    ("Td", "露点温度", "AI", "℃", 5.0, 25.0),
    ("HI", "热指数", "AI", "℃", 15.0, 45.0),
    ("CO2", "CO2浓度", "AI", "ppm", 300.0, 1500.0),
]

PT_DOOR: list[tuple[str, str, str, str, float, float]] = [
    ("St", "门状态", "DI", "", 0.0, 1.0),
    ("Lock", "锁状态", "DI", "", 0.0, 1.0),
    ("Cnt", "开门次数", "AI", "", 0.0, 9999.0),
]

PT_SMOKE: list[tuple[str, str, str, str, float, float]] = [
    ("St", "烟感状态", "DI", "", 0.0, 1.0),
    ("Conc", "烟雾浓度", "AI", "%", 0.0, 100.0),
]

PT_WATER: list[tuple[str, str, str, str, float, float]] = [
    ("St", "漏水状态", "DI", "", 0.0, 1.0),
    ("Pos", "漏水位置", "AI", "m", 0.0, 50.0),
]

# ==================== 设备布局定义 ====================
# (prefix, name_template, device_type, floor_codes, counts_per_floor, point_template, manufacturer, model)
DEVICE_LAYOUT: list[
    tuple[str, str, str, list[str], list[int], list[tuple[str, str, str, str, float, float]], str, str]
] = [
    # --- F1 供配电 ---
    ("HV", "{}高压柜{}号", "HV_CABINET", ["F1"], [4], PT_HV_CABINET, "施耐德", "SM6-24kV"),
    ("TX", "{}变压器{}号", "TRANSFORMER", ["F1"], [4], PT_TRANSFORMER, "西门子", "GEAFOL-1600kVA"),
    ("LV", "{}低压柜{}号", "LV_CABINET", ["F1"], [8], PT_LV_CABINET, "ABB", "MNS3.0"),
    ("UPS", "{} {}号UPS", "UPS", ["F1"], [8], PT_UPS, "华为", "UPS5000-E-200kVA"),
    ("BAT", "{}电池组{}号", "BATTERY", ["F1"], [16], PT_BATTERY, "双登", "6-GFM-100Ah"),
    # --- F1 制冷 ---
    ("CH", "{}冷机{}号", "AC", ["F1"], [6], PT_CHILLER, "约克", "YVWA-400TR"),
    ("PMP", "{}水泵{}号", "AC", ["F1"], [12], PT_PUMP, "格兰富", "NB65-200"),
    ("CT", "{}冷却塔{}号", "AC", ["F1"], [4], PT_COOLING_TOWER, "良机", "LRCM-200"),
    # --- F2-F4 IT机房 ---
    ("PDU", "{}列头柜{}号", "PDU", ["F2", "F3", "F4"], [18, 18, 18], PT_COLUMN_PDU, "台达", "PDU-63A-3P"),
    ("CA", "{}冷通道{}号", "AC", ["F2", "F3", "F4"], [18, 18, 18], PT_COLD_AISLE, "华为", "FusionCol5000"),
    ("TH", "{}温湿度{}号", "TH", ["F2", "F3", "F4"], [74, 74, 74], PT_TH, "海康", "DS-TH100"),
    # --- 安防消防 (分布在各楼层) ---
    ("DR", "{}门禁{}号", "DOOR", ["F1", "F2", "F3", "F4"], [8, 8, 10, 10], PT_DOOR, "海康", "DS-K1T671M"),
    ("SM", "{}烟感{}号", "SMOKE", ["F1", "F2", "F3", "F4"], [16, 40, 40, 36], PT_SMOKE, "海湾", "JTY-GD-G3"),
    ("WL", "{}漏水{}号", "WATER", ["F1", "F2", "F3", "F4"], [8, 20, 20, 20], PT_WATER, "泰和安", "TX3402"),
]


# ==================== 辅助函数 ====================


def _mid_value(min_r: float, max_r: float) -> float:
    """计算量程中间值作为初始值"""
    return round((min_r + max_r) / 2.0, 2)


# ==================== 主种子函数 ====================


async def seed_datacenter() -> None:
    """创建4层算力中心完整种子数据（幂等）"""
    async with async_session() as session:
        # --- 幂等性检查 ---
        result = await session.execute(select(Site).where(Site.site_code == "SZ-DC-01"))
        if result.scalar_one_or_none():
            logger.info("算力中心种子数据已存在，跳过")
            return

        logger.info("开始创建算力中心种子数据...")

        # ===== 1. 创建站点 =====
        site = Site(**SITE)
        session.add(site)
        await session.flush()
        site_id: int = site.id  # type: ignore[assignment]
        logger.info("创建站点: %s (id=%d)", SITE["site_name"], site_id)

        # ===== 2. 创建楼层 =====
        floor_map: dict[str, int] = {}  # floor_code -> floor.id
        for f_def in FLOORS:
            floor = Floor(site_id=site_id, **f_def)
            session.add(floor)
            await session.flush()
            floor_map[f_def["floor_code"]] = floor.id  # type: ignore[assignment]
        logger.info("创建 %d 个楼层", len(FLOORS))

        # ===== 3. 创建房间 =====
        room_count = 0
        for floor_code, room_list in ROOMS.items():
            fid = floor_map[floor_code]
            for r_def in room_list:
                room = Room(floor_id=fid, **r_def)
                session.add(room)
                room_count += 1
        await session.flush()
        logger.info("创建 %d 个房间", room_count)

        # ===== 4. 创建设备和点位 =====
        total_devices = 0
        total_points = 0
        pending_realtimes: list[tuple[int, float, str]] = []  # (point_id, init_val, pt_type)
        batch_counter = 0

        for prefix, name_tpl, dev_type, floor_codes, counts, pt_template, manufacturer, model_name in DEVICE_LAYOUT:
            seq = 0  # 全局序号
            for floor_code, count in zip(floor_codes, counts):
                area_code = floor_code
                for i in range(1, count + 1):
                    seq += 1
                    device_code = f"{prefix}-{floor_code}-{seq:02d}"
                    device_name = name_tpl.format(floor_code, seq)

                    device = Device(
                        device_code=device_code,
                        device_name=device_name,
                        device_type=dev_type,
                        area_code=area_code,
                        manufacturer=manufacturer,
                        model=model_name,
                        install_date=date(2025, 6, 1),
                        status="online",
                        site_id=site_id,
                        is_enabled=True,
                    )
                    session.add(device)
                    await session.flush()
                    device_id: int = device.id  # type: ignore[assignment]
                    total_devices += 1

                    # 创建点位
                    for idx, (suffix, pt_name, pt_type, unit, min_r, max_r) in enumerate(pt_template):
                        point_code = f"{device_code}-{suffix}"
                        full_name = f"{device_name}{pt_name}"
                        point = Point(
                            point_code=point_code,
                            point_name=full_name,
                            point_type=pt_type,
                            device_id=device_id,
                            device_type=dev_type,
                            area_code=area_code,
                            unit=unit,
                            data_type="float" if pt_type == "AI" else "int",
                            min_range=min_r,
                            max_range=max_r,
                            precision=2 if pt_type == "AI" else 0,
                            collect_interval=5,
                            store_interval=60,
                            is_enabled=True,
                            scale_factor=1.0,
                            sort_order=idx,
                        )
                        session.add(point)
                        total_points += 1
                        batch_counter += 1

                        # 记录待创建的实时值
                        init_val = 0.0 if pt_type == "DI" else _mid_value(min_r, max_r)
                        pending_realtimes.append((point, init_val, pt_type))  # type: ignore[arg-type]

                    # 每200条记录 flush 一次获取ID
                    if batch_counter >= 200:
                        await session.flush()
                        batch_counter = 0

        # 最后一次 flush 确保所有点位都有 id
        await session.flush()
        logger.info("创建 %d 台设备, %d 个点位", total_devices, total_points)

        # ===== 5. 创建 PointRealtime 记录 =====
        rt_count = 0
        for point_obj, init_val, pt_type in pending_realtimes:  # type: ignore[misc]
            point_id: int = point_obj.id  # type: ignore[union-attr]
            rt = PointRealtime(
                point_id=point_id,
                raw_value=init_val,
                value=init_val,
                value_text="正常" if pt_type == "DI" else str(init_val),
                quality=0,
                status="normal",
                change_count=0,
            )
            session.add(rt)
            rt_count += 1
            if rt_count % 500 == 0:
                await session.flush()

        await session.commit()
        logger.info(
            "算力中心种子数据创建完成: 站点1个, 楼层%d, 房间%d, 设备%d, 点位%d, 实时值%d",
            len(FLOORS),
            room_count,
            total_devices,
            total_points,
            rt_count,
        )
