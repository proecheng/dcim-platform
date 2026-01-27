"""
点位初始化脚本 - 初始化 52 个监控点位
"""
import asyncio
from app.core.database import async_session, init_db
from app.models import Point, PointRealtime, AlarmThreshold

# AI - 模拟量输入点位 (24点)
AI_POINTS = [
    {"point_code": "A1_TH_AI_001", "point_name": "A1区温度", "device_type": "TH", "area_code": "A1", "unit": "℃", "min_range": -20, "max_range": 60, "collect_interval": 10},
    {"point_code": "A1_TH_AI_002", "point_name": "A1区湿度", "device_type": "TH", "area_code": "A1", "unit": "%RH", "min_range": 0, "max_range": 100, "collect_interval": 10},
    {"point_code": "A2_TH_AI_001", "point_name": "A2区温度", "device_type": "TH", "area_code": "A2", "unit": "℃", "min_range": -20, "max_range": 60, "collect_interval": 10},
    {"point_code": "A2_TH_AI_002", "point_name": "A2区湿度", "device_type": "TH", "area_code": "A2", "unit": "%RH", "min_range": 0, "max_range": 100, "collect_interval": 10},
    {"point_code": "B1_TH_AI_001", "point_name": "B1区温度", "device_type": "TH", "area_code": "B1", "unit": "℃", "min_range": -20, "max_range": 60, "collect_interval": 10},
    {"point_code": "B1_TH_AI_002", "point_name": "B1区湿度", "device_type": "TH", "area_code": "B1", "unit": "%RH", "min_range": 0, "max_range": 100, "collect_interval": 10},
    {"point_code": "A1_UPS_AI_001", "point_name": "UPS-1输入电压", "device_type": "UPS", "area_code": "A1", "unit": "V", "min_range": 0, "max_range": 300, "collect_interval": 5},
    {"point_code": "A1_UPS_AI_002", "point_name": "UPS-1输出电压", "device_type": "UPS", "area_code": "A1", "unit": "V", "min_range": 0, "max_range": 300, "collect_interval": 5},
    {"point_code": "A1_UPS_AI_003", "point_name": "UPS-1负载率", "device_type": "UPS", "area_code": "A1", "unit": "%", "min_range": 0, "max_range": 100, "collect_interval": 5},
    {"point_code": "A1_UPS_AI_004", "point_name": "UPS-1电池电量", "device_type": "UPS", "area_code": "A1", "unit": "%", "min_range": 0, "max_range": 100, "collect_interval": 5},
    {"point_code": "A1_UPS_AI_005", "point_name": "UPS-1输入频率", "device_type": "UPS", "area_code": "A1", "unit": "Hz", "min_range": 45, "max_range": 55, "collect_interval": 5},
    {"point_code": "A1_UPS_AI_006", "point_name": "UPS-1电池温度", "device_type": "UPS", "area_code": "A1", "unit": "℃", "min_range": -20, "max_range": 60, "collect_interval": 10},
    {"point_code": "A2_UPS_AI_001", "point_name": "UPS-2输入电压", "device_type": "UPS", "area_code": "A2", "unit": "V", "min_range": 0, "max_range": 300, "collect_interval": 5},
    {"point_code": "A2_UPS_AI_002", "point_name": "UPS-2输出电压", "device_type": "UPS", "area_code": "A2", "unit": "V", "min_range": 0, "max_range": 300, "collect_interval": 5},
    {"point_code": "A2_UPS_AI_003", "point_name": "UPS-2负载率", "device_type": "UPS", "area_code": "A2", "unit": "%", "min_range": 0, "max_range": 100, "collect_interval": 5},
    {"point_code": "A2_UPS_AI_004", "point_name": "UPS-2电池电量", "device_type": "UPS", "area_code": "A2", "unit": "%", "min_range": 0, "max_range": 100, "collect_interval": 5},
    {"point_code": "A1_PDU_AI_001", "point_name": "PDU-1 A相电流", "device_type": "PDU", "area_code": "A1", "unit": "A", "min_range": 0, "max_range": 100, "collect_interval": 5},
    {"point_code": "A1_PDU_AI_002", "point_name": "PDU-1 B相电流", "device_type": "PDU", "area_code": "A1", "unit": "A", "min_range": 0, "max_range": 100, "collect_interval": 5},
    {"point_code": "A1_PDU_AI_003", "point_name": "PDU-1 C相电流", "device_type": "PDU", "area_code": "A1", "unit": "A", "min_range": 0, "max_range": 100, "collect_interval": 5},
    {"point_code": "A1_PDU_AI_004", "point_name": "PDU-1 总功率", "device_type": "PDU", "area_code": "A1", "unit": "kW", "min_range": 0, "max_range": 200, "collect_interval": 5},
    {"point_code": "A1_AC_AI_001", "point_name": "精密空调-1回风温度", "device_type": "AC", "area_code": "A1", "unit": "℃", "min_range": -20, "max_range": 60, "collect_interval": 10},
    {"point_code": "A1_AC_AI_002", "point_name": "精密空调-1送风温度", "device_type": "AC", "area_code": "A1", "unit": "℃", "min_range": -20, "max_range": 60, "collect_interval": 10},
    {"point_code": "A2_AC_AI_001", "point_name": "精密空调-2回风温度", "device_type": "AC", "area_code": "A2", "unit": "℃", "min_range": -20, "max_range": 60, "collect_interval": 10},
    {"point_code": "A2_AC_AI_002", "point_name": "精密空调-2送风温度", "device_type": "AC", "area_code": "A2", "unit": "℃", "min_range": -20, "max_range": 60, "collect_interval": 10},
]

# DI - 开关量输入点位 (18点)
DI_POINTS = [
    {"point_code": "A1_UPS_DI_001", "point_name": "UPS-1市电状态", "device_type": "UPS", "area_code": "A1", "data_type": "boolean", "collect_interval": 1},
    {"point_code": "A1_UPS_DI_002", "point_name": "UPS-1电池状态", "device_type": "UPS", "area_code": "A1", "data_type": "boolean", "collect_interval": 1},
    {"point_code": "A1_UPS_DI_003", "point_name": "UPS-1逆变状态", "device_type": "UPS", "area_code": "A1", "data_type": "boolean", "collect_interval": 1},
    {"point_code": "A2_UPS_DI_001", "point_name": "UPS-2市电状态", "device_type": "UPS", "area_code": "A2", "data_type": "boolean", "collect_interval": 1},
    {"point_code": "A2_UPS_DI_002", "point_name": "UPS-2电池状态", "device_type": "UPS", "area_code": "A2", "data_type": "boolean", "collect_interval": 1},
    {"point_code": "A2_UPS_DI_003", "point_name": "UPS-2逆变状态", "device_type": "UPS", "area_code": "A2", "data_type": "boolean", "collect_interval": 1},
    {"point_code": "A1_AC_DI_001", "point_name": "精密空调-1运行状态", "device_type": "AC", "area_code": "A1", "data_type": "boolean", "collect_interval": 5},
    {"point_code": "A1_AC_DI_002", "point_name": "精密空调-1故障状态", "device_type": "AC", "area_code": "A1", "data_type": "boolean", "collect_interval": 1},
    {"point_code": "A2_AC_DI_001", "point_name": "精密空调-2运行状态", "device_type": "AC", "area_code": "A2", "data_type": "boolean", "collect_interval": 5},
    {"point_code": "A2_AC_DI_002", "point_name": "精密空调-2故障状态", "device_type": "AC", "area_code": "A2", "data_type": "boolean", "collect_interval": 1},
    {"point_code": "A1_DOOR_DI_001", "point_name": "主入口门禁状态", "device_type": "DOOR", "area_code": "A1", "data_type": "boolean", "collect_interval": 1},
    {"point_code": "A1_DOOR_DI_002", "point_name": "后门门禁状态", "device_type": "DOOR", "area_code": "A1", "data_type": "boolean", "collect_interval": 1},
    {"point_code": "A1_SMOKE_DI_001", "point_name": "A1区烟感报警", "device_type": "SMOKE", "area_code": "A1", "data_type": "boolean", "collect_interval": 1},
    {"point_code": "A2_SMOKE_DI_001", "point_name": "A2区烟感报警", "device_type": "SMOKE", "area_code": "A2", "data_type": "boolean", "collect_interval": 1},
    {"point_code": "B1_SMOKE_DI_001", "point_name": "B1区烟感报警", "device_type": "SMOKE", "area_code": "B1", "data_type": "boolean", "collect_interval": 1},
    {"point_code": "A1_WATER_DI_001", "point_name": "A1区漏水检测", "device_type": "WATER", "area_code": "A1", "data_type": "boolean", "collect_interval": 1},
    {"point_code": "A2_WATER_DI_001", "point_name": "A2区漏水检测", "device_type": "WATER", "area_code": "A2", "data_type": "boolean", "collect_interval": 1},
    {"point_code": "A1_IR_DI_001", "point_name": "红外入侵检测", "device_type": "IR", "area_code": "A1", "data_type": "boolean", "collect_interval": 1},
]

# AO - 模拟量输出点位 (4点)
AO_POINTS = [
    {"point_code": "A1_AC_AO_001", "point_name": "精密空调-1设定温度", "device_type": "AC", "area_code": "A1", "unit": "℃", "min_range": 18, "max_range": 28, "collect_interval": 10},
    {"point_code": "A1_AC_AO_002", "point_name": "精密空调-1风机转速", "device_type": "AC", "area_code": "A1", "unit": "%", "min_range": 0, "max_range": 100, "collect_interval": 10},
    {"point_code": "A2_AC_AO_001", "point_name": "精密空调-2设定温度", "device_type": "AC", "area_code": "A2", "unit": "℃", "min_range": 18, "max_range": 28, "collect_interval": 10},
    {"point_code": "A2_AC_AO_002", "point_name": "精密空调-2风机转速", "device_type": "AC", "area_code": "A2", "unit": "%", "min_range": 0, "max_range": 100, "collect_interval": 10},
]

# DO - 开关量输出点位 (6点)
DO_POINTS = [
    {"point_code": "A1_AC_DO_001", "point_name": "精密空调-1启停", "device_type": "AC", "area_code": "A1", "data_type": "boolean", "collect_interval": 5},
    {"point_code": "A2_AC_DO_001", "point_name": "精密空调-2启停", "device_type": "AC", "area_code": "A2", "data_type": "boolean", "collect_interval": 5},
    {"point_code": "A1_FAN_DO_001", "point_name": "新风机-1启停", "device_type": "FAN", "area_code": "A1", "data_type": "boolean", "collect_interval": 5},
    {"point_code": "A1_FAN_DO_002", "point_name": "排风扇-1启停", "device_type": "FAN", "area_code": "A1", "data_type": "boolean", "collect_interval": 5},
    {"point_code": "A1_LIGHT_DO_001", "point_name": "机房照明控制", "device_type": "LIGHT", "area_code": "A1", "data_type": "boolean", "collect_interval": 5},
    {"point_code": "A1_EPO_DO_001", "point_name": "紧急断电(EPO)", "device_type": "EPO", "area_code": "A1", "data_type": "boolean", "collect_interval": 5},
]

# 默认告警阈值配置
DEFAULT_THRESHOLDS = [
    # 温度告警
    {"point_code": "A1_TH_AI_001", "thresholds": [
        {"type": "high", "value": 28, "level": "major", "message": "A1区温度过高"},
        {"type": "low", "value": 18, "level": "minor", "message": "A1区温度过低"},
        {"type": "high", "value": 32, "level": "critical", "message": "A1区温度严重过高"},
    ]},
    {"point_code": "A2_TH_AI_001", "thresholds": [
        {"type": "high", "value": 28, "level": "major", "message": "A2区温度过高"},
        {"type": "low", "value": 18, "level": "minor", "message": "A2区温度过低"},
    ]},
    # 湿度告警
    {"point_code": "A1_TH_AI_002", "thresholds": [
        {"type": "high", "value": 70, "level": "major", "message": "A1区湿度过高"},
        {"type": "low", "value": 30, "level": "minor", "message": "A1区湿度过低"},
    ]},
    # UPS 告警
    {"point_code": "A1_UPS_AI_003", "thresholds": [
        {"type": "high", "value": 80, "level": "major", "message": "UPS-1负载率过高"},
        {"type": "high", "value": 90, "level": "critical", "message": "UPS-1负载率严重过高"},
    ]},
    {"point_code": "A1_UPS_AI_004", "thresholds": [
        {"type": "low", "value": 20, "level": "critical", "message": "UPS-1电池电量过低"},
        {"type": "low", "value": 50, "level": "major", "message": "UPS-1电池电量较低"},
    ]},
]


async def init_points():
    """初始化点位数据"""
    await init_db()

    async with async_session() as session:
        # 检查是否已初始化
        from sqlalchemy import select, func
        result = await session.execute(select(func.count(Point.id)))
        count = result.scalar()

        if count > 0:
            print(f"数据库已存在 {count} 个点位，跳过初始化")
            return

        print("开始初始化点位...")

        # 创建所有点位
        all_points = []

        # AI 点位
        for p in AI_POINTS:
            point = Point(point_type="AI", data_type="float", **p)
            all_points.append(point)

        # DI 点位
        for p in DI_POINTS:
            point = Point(point_type="DI", **p)
            all_points.append(point)

        # AO 点位
        for p in AO_POINTS:
            point = Point(point_type="AO", data_type="float", **p)
            all_points.append(point)

        # DO 点位
        for p in DO_POINTS:
            point = Point(point_type="DO", **p)
            all_points.append(point)

        session.add_all(all_points)
        await session.flush()

        # 为每个点位创建实时值记录
        for point in all_points:
            # 设置初始值
            if point.point_type == "AI":
                initial_value = (point.min_range + point.max_range) / 2 if point.min_range and point.max_range else 0
            elif point.point_type == "DI":
                initial_value = 0  # 正常状态
            elif point.point_type == "AO":
                initial_value = 24 if "温度" in point.point_name else 50
            else:  # DO
                initial_value = 1 if "启停" in point.point_name else 0

            realtime = PointRealtime(
                point_id=point.id,
                value=initial_value,
                value_text="正常" if point.point_type in ["DI", "DO"] else None,
                status="normal"
            )
            session.add(realtime)

        # 创建默认告警阈值
        for config in DEFAULT_THRESHOLDS:
            # 查找点位
            result = await session.execute(
                select(Point).where(Point.point_code == config["point_code"])
            )
            point = result.scalar_one_or_none()
            if point:
                for t in config["thresholds"]:
                    threshold = AlarmThreshold(
                        point_id=point.id,
                        threshold_type=t["type"],
                        threshold_value=t["value"],
                        alarm_level=t["level"],
                        alarm_message=t["message"]
                    )
                    session.add(threshold)

        await session.commit()
        print(f"成功初始化 {len(all_points)} 个点位")
        print(f"- AI (模拟量输入): {len(AI_POINTS)} 个")
        print(f"- DI (开关量输入): {len(DI_POINTS)} 个")
        print(f"- AO (模拟量输出): {len(AO_POINTS)} 个")
        print(f"- DO (开关量输出): {len(DO_POINTS)} 个")


if __name__ == "__main__":
    asyncio.run(init_points())
