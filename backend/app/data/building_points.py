"""
算力中心大楼完整点位定义
- B1: 地下制冷机房
- F1: 1楼机房区 (20台机柜)
- F2: 2楼机房区 (15台机柜)
- F3: 3楼办公监控区 (8台机柜)
"""

# 楼层配置
FLOOR_CONFIG = {
    "B1": {"name": "地下制冷机房", "area": 500, "cabinets": 0},
    "F1": {"name": "1楼机房区A", "area": 1000, "cabinets": 20},
    "F2": {"name": "2楼机房区B", "area": 1000, "cabinets": 15},
    "F3": {"name": "3楼办公监控", "area": 1000, "cabinets": 8},
}

# B1 地下制冷系统点位
B1_COOLING_POINTS = {
    "AI": [
        # 冷水机组 (2台)
        {"point_code": "B1_CH_AI_001", "point_name": "1#冷水机组冷冻水出水温度", "device_type": "CH", "unit": "℃", "min_range": 5, "max_range": 15},
        {"point_code": "B1_CH_AI_002", "point_name": "1#冷水机组冷冻水回水温度", "device_type": "CH", "unit": "℃", "min_range": 8, "max_range": 18},
        {"point_code": "B1_CH_AI_003", "point_name": "1#冷水机组冷却水出水温度", "device_type": "CH", "unit": "℃", "min_range": 25, "max_range": 40},
        {"point_code": "B1_CH_AI_004", "point_name": "1#冷水机组冷却水回水温度", "device_type": "CH", "unit": "℃", "min_range": 28, "max_range": 45},
        {"point_code": "B1_CH_AI_005", "point_name": "1#冷水机组功率", "device_type": "CH", "unit": "kW", "min_range": 0, "max_range": 500},
        {"point_code": "B1_CH_AI_006", "point_name": "1#冷水机组负载率", "device_type": "CH", "unit": "%", "min_range": 0, "max_range": 100},
        {"point_code": "B1_CH_AI_011", "point_name": "2#冷水机组冷冻水出水温度", "device_type": "CH", "unit": "℃", "min_range": 5, "max_range": 15},
        {"point_code": "B1_CH_AI_012", "point_name": "2#冷水机组冷冻水回水温度", "device_type": "CH", "unit": "℃", "min_range": 8, "max_range": 18},
        {"point_code": "B1_CH_AI_013", "point_name": "2#冷水机组冷却水出水温度", "device_type": "CH", "unit": "℃", "min_range": 25, "max_range": 40},
        {"point_code": "B1_CH_AI_014", "point_name": "2#冷水机组冷却水回水温度", "device_type": "CH", "unit": "℃", "min_range": 28, "max_range": 45},
        {"point_code": "B1_CH_AI_015", "point_name": "2#冷水机组功率", "device_type": "CH", "unit": "kW", "min_range": 0, "max_range": 500},
        {"point_code": "B1_CH_AI_016", "point_name": "2#冷水机组负载率", "device_type": "CH", "unit": "%", "min_range": 0, "max_range": 100},
        # 冷却塔 (2台)
        {"point_code": "B1_CT_AI_001", "point_name": "1#冷却塔出水温度", "device_type": "CT", "unit": "℃", "min_range": 20, "max_range": 40},
        {"point_code": "B1_CT_AI_002", "point_name": "1#冷却塔风机频率", "device_type": "CT", "unit": "Hz", "min_range": 0, "max_range": 50},
        {"point_code": "B1_CT_AI_003", "point_name": "2#冷却塔出水温度", "device_type": "CT", "unit": "℃", "min_range": 20, "max_range": 40},
        {"point_code": "B1_CT_AI_004", "point_name": "2#冷却塔风机频率", "device_type": "CT", "unit": "Hz", "min_range": 0, "max_range": 50},
        # 水泵 (冷冻水泵2台 + 冷却水泵2台)
        {"point_code": "B1_CHWP_AI_001", "point_name": "1#冷冻水泵频率", "device_type": "PUMP", "unit": "Hz", "min_range": 0, "max_range": 50},
        {"point_code": "B1_CHWP_AI_002", "point_name": "1#冷冻水泵电流", "device_type": "PUMP", "unit": "A", "min_range": 0, "max_range": 100},
        {"point_code": "B1_CHWP_AI_003", "point_name": "2#冷冻水泵频率", "device_type": "PUMP", "unit": "Hz", "min_range": 0, "max_range": 50},
        {"point_code": "B1_CHWP_AI_004", "point_name": "2#冷冻水泵电流", "device_type": "PUMP", "unit": "A", "min_range": 0, "max_range": 100},
        {"point_code": "B1_CWP_AI_001", "point_name": "1#冷却水泵频率", "device_type": "PUMP", "unit": "Hz", "min_range": 0, "max_range": 50},
        {"point_code": "B1_CWP_AI_002", "point_name": "1#冷却水泵电流", "device_type": "PUMP", "unit": "A", "min_range": 0, "max_range": 100},
        {"point_code": "B1_CWP_AI_003", "point_name": "2#冷却水泵频率", "device_type": "PUMP", "unit": "Hz", "min_range": 0, "max_range": 50},
        {"point_code": "B1_CWP_AI_004", "point_name": "2#冷却水泵电流", "device_type": "PUMP", "unit": "A", "min_range": 0, "max_range": 100},
        # 管道压力
        {"point_code": "B1_PIPE_AI_001", "point_name": "冷冻水供水压力", "device_type": "PIPE", "unit": "MPa", "min_range": 0, "max_range": 1},
        {"point_code": "B1_PIPE_AI_002", "point_name": "冷冻水回水压力", "device_type": "PIPE", "unit": "MPa", "min_range": 0, "max_range": 1},
        {"point_code": "B1_PIPE_AI_003", "point_name": "冷却水供水压力", "device_type": "PIPE", "unit": "MPa", "min_range": 0, "max_range": 1},
    ],
    "DI": [
        {"point_code": "B1_CH_DI_001", "point_name": "1#冷水机组运行状态", "device_type": "CH", "data_type": "boolean"},
        {"point_code": "B1_CH_DI_002", "point_name": "1#冷水机组故障状态", "device_type": "CH", "data_type": "boolean"},
        {"point_code": "B1_CH_DI_003", "point_name": "2#冷水机组运行状态", "device_type": "CH", "data_type": "boolean"},
        {"point_code": "B1_CH_DI_004", "point_name": "2#冷水机组故障状态", "device_type": "CH", "data_type": "boolean"},
        {"point_code": "B1_CT_DI_001", "point_name": "1#冷却塔运行状态", "device_type": "CT", "data_type": "boolean"},
        {"point_code": "B1_CT_DI_002", "point_name": "2#冷却塔运行状态", "device_type": "CT", "data_type": "boolean"},
        {"point_code": "B1_CHWP_DI_001", "point_name": "1#冷冻水泵运行状态", "device_type": "PUMP", "data_type": "boolean"},
        {"point_code": "B1_CHWP_DI_002", "point_name": "2#冷冻水泵运行状态", "device_type": "PUMP", "data_type": "boolean"},
        {"point_code": "B1_CWP_DI_001", "point_name": "1#冷却水泵运行状态", "device_type": "PUMP", "data_type": "boolean"},
        {"point_code": "B1_CWP_DI_002", "point_name": "2#冷却水泵运行状态", "device_type": "PUMP", "data_type": "boolean"},
        {"point_code": "B1_WATER_DI_001", "point_name": "B1机房漏水检测", "device_type": "WATER", "data_type": "boolean"},
    ],
}

def generate_floor_points(floor: str, cabinet_count: int) -> dict:
    """生成楼层点位"""
    points = {"AI": [], "DI": [], "AO": [], "DO": []}

    # 温湿度传感器 (每层4个区域)
    for zone in range(1, 5):
        points["AI"].extend([
            {"point_code": f"{floor}_TH_AI_{zone:03d}1", "point_name": f"{floor}区域{zone}温度", "device_type": "TH", "unit": "℃", "min_range": 15, "max_range": 35},
            {"point_code": f"{floor}_TH_AI_{zone:03d}2", "point_name": f"{floor}区域{zone}湿度", "device_type": "TH", "unit": "%RH", "min_range": 20, "max_range": 80},
        ])

    # UPS (每层1-2台)
    ups_count = 2 if floor in ["F1", "F2"] else 1
    for ups in range(1, ups_count + 1):
        points["AI"].extend([
            {"point_code": f"{floor}_UPS_AI_{ups:03d}1", "point_name": f"{floor} UPS-{ups}输入电压", "device_type": "UPS", "unit": "V", "min_range": 360, "max_range": 420},
            {"point_code": f"{floor}_UPS_AI_{ups:03d}2", "point_name": f"{floor} UPS-{ups}输出电压", "device_type": "UPS", "unit": "V", "min_range": 380, "max_range": 400},
            {"point_code": f"{floor}_UPS_AI_{ups:03d}3", "point_name": f"{floor} UPS-{ups}负载率", "device_type": "UPS", "unit": "%", "min_range": 0, "max_range": 100},
            {"point_code": f"{floor}_UPS_AI_{ups:03d}4", "point_name": f"{floor} UPS-{ups}电池电量", "device_type": "UPS", "unit": "%", "min_range": 0, "max_range": 100},
            {"point_code": f"{floor}_UPS_AI_{ups:03d}5", "point_name": f"{floor} UPS-{ups}电池温度", "device_type": "UPS", "unit": "℃", "min_range": 15, "max_range": 45},
        ])
        points["DI"].extend([
            {"point_code": f"{floor}_UPS_DI_{ups:03d}1", "point_name": f"{floor} UPS-{ups}市电状态", "device_type": "UPS", "data_type": "boolean"},
            {"point_code": f"{floor}_UPS_DI_{ups:03d}2", "point_name": f"{floor} UPS-{ups}电池状态", "device_type": "UPS", "data_type": "boolean"},
            {"point_code": f"{floor}_UPS_DI_{ups:03d}3", "point_name": f"{floor} UPS-{ups}旁路状态", "device_type": "UPS", "data_type": "boolean"},
        ])

    # 精密空调 (每层2-4台)
    ac_count = 4 if floor in ["F1", "F2"] else 2
    for ac in range(1, ac_count + 1):
        points["AI"].extend([
            {"point_code": f"{floor}_AC_AI_{ac:03d}1", "point_name": f"{floor} 精密空调-{ac}回风温度", "device_type": "AC", "unit": "℃", "min_range": 15, "max_range": 35},
            {"point_code": f"{floor}_AC_AI_{ac:03d}2", "point_name": f"{floor} 精密空调-{ac}送风温度", "device_type": "AC", "unit": "℃", "min_range": 10, "max_range": 25},
            {"point_code": f"{floor}_AC_AI_{ac:03d}3", "point_name": f"{floor} 精密空调-{ac}回风湿度", "device_type": "AC", "unit": "%RH", "min_range": 20, "max_range": 80},
        ])
        points["DI"].extend([
            {"point_code": f"{floor}_AC_DI_{ac:03d}1", "point_name": f"{floor} 精密空调-{ac}运行状态", "device_type": "AC", "data_type": "boolean"},
            {"point_code": f"{floor}_AC_DI_{ac:03d}2", "point_name": f"{floor} 精密空调-{ac}故障状态", "device_type": "AC", "data_type": "boolean"},
        ])
        points["AO"].extend([
            {"point_code": f"{floor}_AC_AO_{ac:03d}1", "point_name": f"{floor} 精密空调-{ac}设定温度", "device_type": "AC", "unit": "℃", "min_range": 18, "max_range": 28},
        ])
        points["DO"].extend([
            {"point_code": f"{floor}_AC_DO_{ac:03d}1", "point_name": f"{floor} 精密空调-{ac}启停控制", "device_type": "AC", "data_type": "boolean"},
        ])

    # 配电柜 (每层1台总配电+1台IT配电)
    points["AI"].extend([
        {"point_code": f"{floor}_PDB_AI_001", "point_name": f"{floor} 总配电柜A相电流", "device_type": "PDB", "unit": "A", "min_range": 0, "max_range": 500},
        {"point_code": f"{floor}_PDB_AI_002", "point_name": f"{floor} 总配电柜B相电流", "device_type": "PDB", "unit": "A", "min_range": 0, "max_range": 500},
        {"point_code": f"{floor}_PDB_AI_003", "point_name": f"{floor} 总配电柜C相电流", "device_type": "PDB", "unit": "A", "min_range": 0, "max_range": 500},
        {"point_code": f"{floor}_PDB_AI_004", "point_name": f"{floor} 总配电柜有功功率", "device_type": "PDB", "unit": "kW", "min_range": 0, "max_range": 500},
        {"point_code": f"{floor}_PDB_AI_005", "point_name": f"{floor} 总配电柜电能累计", "device_type": "PDB", "unit": "kWh", "min_range": 0, "max_range": 999999},
    ])

    # PDU (每台机柜1个PDU)
    for cab in range(1, cabinet_count + 1):
        points["AI"].extend([
            {"point_code": f"{floor}_PDU_AI_{cab:03d}1", "point_name": f"{floor} 机柜{cab:02d} PDU电流", "device_type": "PDU", "unit": "A", "min_range": 0, "max_range": 32},
            {"point_code": f"{floor}_PDU_AI_{cab:03d}2", "point_name": f"{floor} 机柜{cab:02d} PDU功率", "device_type": "PDU", "unit": "kW", "min_range": 0, "max_range": 20},
            {"point_code": f"{floor}_PDU_AI_{cab:03d}3", "point_name": f"{floor} 机柜{cab:02d} PDU电能", "device_type": "PDU", "unit": "kWh", "min_range": 0, "max_range": 99999},
        ])

    # 环境监控
    points["DI"].extend([
        {"point_code": f"{floor}_SMOKE_DI_001", "point_name": f"{floor} 烟感报警", "device_type": "SMOKE", "data_type": "boolean"},
        {"point_code": f"{floor}_WATER_DI_001", "point_name": f"{floor} 漏水检测", "device_type": "WATER", "data_type": "boolean"},
        {"point_code": f"{floor}_DOOR_DI_001", "point_name": f"{floor} 主入口门禁", "device_type": "DOOR", "data_type": "boolean"},
    ])

    return points

# 生成各楼层点位
F1_POINTS = generate_floor_points("F1", 20)
F2_POINTS = generate_floor_points("F2", 15)
F3_POINTS = generate_floor_points("F3", 8)

# F3 额外的办公区点位
F3_OFFICE_POINTS = {
    "AI": [
        {"point_code": "F3_OFFICE_TH_001", "point_name": "监控中心温度", "device_type": "TH", "unit": "℃", "min_range": 18, "max_range": 30},
        {"point_code": "F3_OFFICE_TH_002", "point_name": "监控中心湿度", "device_type": "TH", "unit": "%RH", "min_range": 30, "max_range": 70},
        {"point_code": "F3_MEET_TH_001", "point_name": "会议室温度", "device_type": "TH", "unit": "℃", "min_range": 18, "max_range": 30},
    ],
    "DI": [
        {"point_code": "F3_OFFICE_DOOR_001", "point_name": "监控中心门禁", "device_type": "DOOR", "data_type": "boolean"},
        {"point_code": "F3_MEET_DOOR_001", "point_name": "会议室门禁", "device_type": "DOOR", "data_type": "boolean"},
    ],
}

def get_all_points() -> dict:
    """获取所有点位"""
    all_points = {"AI": [], "DI": [], "AO": [], "DO": []}

    # B1 制冷系统
    for ptype, plist in B1_COOLING_POINTS.items():
        all_points[ptype].extend(plist)

    # F1-F3 机房
    for floor_points in [F1_POINTS, F2_POINTS, F3_POINTS]:
        for ptype, plist in floor_points.items():
            all_points[ptype].extend(plist)

    # F3 办公区
    for ptype, plist in F3_OFFICE_POINTS.items():
        all_points[ptype].extend(plist)

    return all_points

def count_points() -> dict:
    """统计点位数量"""
    points = get_all_points()
    return {
        "AI": len(points["AI"]),
        "DI": len(points["DI"]),
        "AO": len(points["AO"]),
        "DO": len(points["DO"]),
        "total": sum(len(v) for v in points.values())
    }


# 默认告警阈值配置
ALARM_THRESHOLDS = {
    # 温度阈值
    "TH_temp": [
        {"type": "high", "value": 28, "level": "major", "message_template": "{point_name}过高"},
        {"type": "high", "value": 32, "level": "critical", "message_template": "{point_name}严重过高"},
        {"type": "low", "value": 18, "level": "minor", "message_template": "{point_name}过低"},
    ],
    # 湿度阈值
    "TH_humid": [
        {"type": "high", "value": 70, "level": "major", "message_template": "{point_name}过高"},
        {"type": "low", "value": 30, "level": "minor", "message_template": "{point_name}过低"},
    ],
    # UPS负载率
    "UPS_load": [
        {"type": "high", "value": 80, "level": "major", "message_template": "{point_name}过高"},
        {"type": "high", "value": 90, "level": "critical", "message_template": "{point_name}严重过高"},
    ],
    # UPS电池电量
    "UPS_battery": [
        {"type": "low", "value": 50, "level": "major", "message_template": "{point_name}较低"},
        {"type": "low", "value": 20, "level": "critical", "message_template": "{point_name}过低"},
    ],
    # 冷水机组
    "CH_temp": [
        {"type": "high", "value": 12, "level": "major", "message_template": "{point_name}偏高"},
        {"type": "high", "value": 15, "level": "critical", "message_template": "{point_name}过高"},
    ],
    # PDU电流
    "PDU_current": [
        {"type": "high", "value": 25, "level": "major", "message_template": "{point_name}过高"},
        {"type": "high", "value": 30, "level": "critical", "message_template": "{point_name}严重过高"},
    ],
}

def get_threshold_for_point(point_code: str, point_name: str) -> list:
    """根据点位类型获取适用的阈值"""
    thresholds = []

    if "_TH_AI_" in point_code:
        if point_code.endswith("1"):  # 温度
            for t in ALARM_THRESHOLDS["TH_temp"]:
                thresholds.append({**t, "message": t["message_template"].format(point_name=point_name)})
        else:  # 湿度
            for t in ALARM_THRESHOLDS["TH_humid"]:
                thresholds.append({**t, "message": t["message_template"].format(point_name=point_name)})
    elif "_UPS_AI_" in point_code:
        if "负载率" in point_name:
            for t in ALARM_THRESHOLDS["UPS_load"]:
                thresholds.append({**t, "message": t["message_template"].format(point_name=point_name)})
        elif "电池电量" in point_name:
            for t in ALARM_THRESHOLDS["UPS_battery"]:
                thresholds.append({**t, "message": t["message_template"].format(point_name=point_name)})
    elif "_CH_AI_" in point_code and "冷冻水出水" in point_name:
        for t in ALARM_THRESHOLDS["CH_temp"]:
            thresholds.append({**t, "message": t["message_template"].format(point_name=point_name)})
    elif "_PDU_AI_" in point_code and "电流" in point_name:
        for t in ALARM_THRESHOLDS["PDU_current"]:
            thresholds.append({**t, "message": t["message_template"].format(point_name=point_name)})

    return thresholds
