# 算力中心大楼模拟数据系统实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 构建一个完整的3层算力中心大楼模拟数据系统，包含配电室、机房、空调、监控等设施，生成1个月的历史数据，支持真实运行模式切换。

**Architecture:**
- 大楼结构: 地下1层(空调主机房) + 地上3层(1-2层机房区+3层办公监控区)
- 数据生成: 点位初始化 → 历史数据回填 → 实时模拟采集
- 模式切换: 模拟模式(自动生成) ↔ 真实模式(外部数据源)

**Tech Stack:** Python, SQLAlchemy, AsyncIO, SQLite

---

## 大楼布局设计

### 楼层规划

| 楼层 | 面积 | 用途 | 机柜数 | 主要设备 |
|------|------|------|--------|----------|
| B1 | 500㎡ | 空调主机房 | - | 冷水机组、冷却塔、水泵 |
| F1 | 1000㎡ | 机房区A | 20台 | 机柜、UPS、PDU、精密空调、配电柜 |
| F2 | 1000㎡ | 机房区B | 15台 | 机柜、UPS、PDU、精密空调、配电柜 |
| F3 | 1000㎡ | 办公监控 | 8台 | 小型机房+监控中心+办公室 |

### 配电系统架构

```
变电站 (10kV → 400V)
  └─→ 总配电室 (F1)
       ├─→ F1机房配电柜 → UPS-1 → PDU (20台机柜)
       ├─→ F2机房配电柜 → UPS-2 → PDU (15台机柜)
       ├─→ F3办公配电柜 → UPS-3 → PDU (8台机柜)
       └─→ B1制冷配电柜 → 冷水机组/水泵
```

---

## Phase 1: 点位定义扩展

### Task 1.1: 创建大楼点位定义文件

**Files:**
- Create: `backend/app/data/building_points.py`

**Step 1: 创建点位定义结构**

创建文件 `backend/app/data/building_points.py`:

```python
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
```

**Step 2: 验证点位定义**

Run:
```bash
cd /d/mytest1 && python -c "from backend.app.data.building_points import count_points; print(count_points())"
```

Expected: 显示点位统计，总数约200-300个

---

### Task 1.2: 创建告警阈值定义

**Files:**
- Modify: `backend/app/data/building_points.py`

**Step 1: 在文件末尾添加告警阈值定义**

```python
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
```

**Step 2: 验证阈值函数**

Run:
```bash
cd /d/mytest1 && python -c "
from backend.app.data.building_points import get_threshold_for_point
print(get_threshold_for_point('F1_TH_AI_0011', 'F1区域1温度'))
print(get_threshold_for_point('F1_UPS_AI_0013', 'F1 UPS-1负载率'))
"
```

Expected: 输出对应的阈值配置列表

---

## Phase 2: 点位初始化脚本

### Task 2.1: 创建大楼点位初始化脚本

**Files:**
- Create: `backend/init_building_points.py`

**Step 1: 创建初始化脚本**

```python
"""
大楼点位初始化脚本 - 初始化约250个监控点位
"""
import asyncio
from datetime import datetime
from app.core.database import async_session, init_db
from app.models import Point, PointRealtime, AlarmThreshold
from app.data.building_points import get_all_points, get_threshold_for_point

async def init_building_points():
    """初始化大楼所有点位"""
    await init_db()

    async with async_session() as session:
        # 检查是否已初始化
        from sqlalchemy import select, func
        result = await session.execute(select(func.count(Point.id)))
        existing_count = result.scalar()

        if existing_count > 100:
            print(f"点位已初始化 ({existing_count}个)，跳过")
            return

        points = get_all_points()
        total_created = 0

        for point_type, point_list in points.items():
            for p in point_list:
                # 创建点位
                point = Point(
                    point_code=p["point_code"],
                    point_name=p["point_name"],
                    point_type=point_type,
                    device_type=p["device_type"],
                    area_code=p["point_code"].split("_")[0],  # 从编码提取楼层
                    unit=p.get("unit", ""),
                    data_type=p.get("data_type", "float" if point_type == "AI" else "boolean"),
                    min_range=p.get("min_range"),
                    max_range=p.get("max_range"),
                    collect_interval=p.get("collect_interval", 10),
                    is_enabled=True,
                )
                session.add(point)
                await session.flush()

                # 创建实时数据记录
                realtime = PointRealtime(
                    point_id=point.id,
                    value=0,
                    status="normal",
                    collected_at=datetime.now(),
                )
                session.add(realtime)

                # 创建告警阈值
                thresholds = get_threshold_for_point(p["point_code"], p["point_name"])
                for t in thresholds:
                    threshold = AlarmThreshold(
                        point_id=point.id,
                        threshold_type=t["type"],
                        threshold_value=t["value"],
                        alarm_level=t["level"],
                        alarm_message=t["message"],
                        is_enabled=True,
                    )
                    session.add(threshold)

                total_created += 1

        await session.commit()
        print(f"成功创建 {total_created} 个点位")

if __name__ == "__main__":
    asyncio.run(init_building_points())
```

**Step 2: 运行初始化脚本**

Run:
```bash
cd /d/mytest1 && python backend/init_building_points.py
```

Expected: 输出 "成功创建 XXX 个点位"

---

## Phase 3: 历史数据回填

### Task 3.1: 创建历史数据生成器

**Files:**
- Create: `backend/app/services/history_generator.py`

**Step 1: 创建历史数据生成服务**

```python
"""
历史数据生成器 - 生成30天的模拟历史数据
"""
import asyncio
import random
import math
from datetime import datetime, timedelta
from typing import List, Dict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import async_session
from ..models import Point, PointHistory, EnergyHourly, EnergyDaily, PUEHistory


class HistoryGenerator:
    """历史数据生成器"""

    def __init__(self, days: int = 30):
        self.days = days
        self.base_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    def generate_daily_pattern(self, hour: int, base_value: float, variation: float) -> float:
        """生成日内波动模式
        - 白天(8-20)负载较高
        - 夜间(20-8)负载较低
        """
        if 8 <= hour < 20:
            # 白天：基础值 + 10-20%
            factor = 1.0 + random.uniform(0.1, 0.2)
        else:
            # 夜间：基础值 - 10-20%
            factor = 1.0 - random.uniform(0.1, 0.2)

        # 添加随机波动
        noise = random.uniform(-variation, variation)
        return base_value * factor + noise

    def generate_seasonal_pattern(self, day_offset: int, base_value: float) -> float:
        """生成季节性波动（简化为30天周期）"""
        # 模拟月初月末的小幅变化
        cycle = math.sin(2 * math.pi * day_offset / 30)
        return base_value * (1 + 0.05 * cycle)

    def generate_point_history(self, point: Point, hours: int) -> List[Dict]:
        """生成单个点位的历史数据"""
        records = []

        # 根据点位类型确定基础值和波动范围
        if point.point_type == "AI":
            min_val = point.min_range or 0
            max_val = point.max_range or 100
            base_value = (min_val + max_val) / 2
            variation = (max_val - min_val) * 0.05

            # 特定设备类型的基础值调整
            if "温度" in point.point_name and "TH" in point.device_type:
                base_value = 24  # 机房温度基准
            elif "湿度" in point.point_name:
                base_value = 50  # 湿度基准
            elif "负载率" in point.point_name:
                base_value = 45  # 负载率基准
            elif "电池电量" in point.point_name:
                base_value = 85  # 电池电量基准
            elif "功率" in point.point_name and "kW" in (point.unit or ""):
                base_value = max_val * 0.4  # 功率基准
        else:
            # DI/DO 点位
            base_value = 0
            variation = 0

        for h in range(hours):
            record_time = self.base_time - timedelta(hours=hours-h)
            day_offset = (self.base_time - record_time).days
            hour = record_time.hour

            if point.point_type == "AI":
                seasonal_base = self.generate_seasonal_pattern(day_offset, base_value)
                value = self.generate_daily_pattern(hour, seasonal_base, variation)
                # 确保在量程范围内
                value = max(point.min_range or 0, min(point.max_range or 100, value))
                value = round(value, 2)
            else:
                # 开关量：极低概率为1
                value = 1 if random.random() < 0.001 else 0

            records.append({
                "point_id": point.id,
                "value": value,
                "status": "normal",
                "recorded_at": record_time,
            })

        return records

    async def generate_all_history(self, batch_size: int = 1000):
        """生成所有点位的历史数据"""
        total_hours = self.days * 24

        async with async_session() as session:
            # 获取所有点位
            result = await session.execute(select(Point).where(Point.is_enabled == True))
            points = result.scalars().all()

            print(f"开始生成 {len(points)} 个点位 x {total_hours} 小时的历史数据...")

            total_records = 0
            batch_records = []

            for i, point in enumerate(points):
                records = self.generate_point_history(point, total_hours)

                for r in records:
                    batch_records.append(PointHistory(**r))

                    if len(batch_records) >= batch_size:
                        session.add_all(batch_records)
                        await session.commit()
                        total_records += len(batch_records)
                        print(f"  已写入 {total_records} 条记录...")
                        batch_records = []

                if (i + 1) % 50 == 0:
                    print(f"  已处理 {i+1}/{len(points)} 个点位")

            # 写入剩余记录
            if batch_records:
                session.add_all(batch_records)
                await session.commit()
                total_records += len(batch_records)

            print(f"历史数据生成完成，共 {total_records} 条记录")

    async def generate_energy_history(self):
        """生成能耗历史数据"""
        async with async_session() as session:
            print("生成能耗历史数据...")

            for day_offset in range(self.days):
                record_date = (self.base_time - timedelta(days=day_offset)).date()

                for hour in range(24):
                    record_time = datetime.combine(record_date, datetime.min.time()) + timedelta(hours=hour)

                    # 基础功率 + 日内波动
                    it_power = self.generate_daily_pattern(hour, 150, 20)
                    cooling_power = it_power * 0.35  # 制冷功率约为IT功率的35%
                    other_power = 20 + random.uniform(-5, 5)  # 其他功率
                    total_power = it_power + cooling_power + other_power

                    # PUE计算
                    pue = total_power / it_power if it_power > 0 else 1.5

                    # 创建PUE历史
                    pue_record = PUEHistory(
                        total_power=round(total_power, 2),
                        it_power=round(it_power, 2),
                        cooling_power=round(cooling_power, 2),
                        other_power=round(other_power, 2),
                        pue=round(pue, 3),
                        recorded_at=record_time,
                    )
                    session.add(pue_record)

                # 每天提交一次
                await session.commit()
                if (day_offset + 1) % 5 == 0:
                    print(f"  已生成 {day_offset+1}/{self.days} 天能耗数据")

            print("能耗历史数据生成完成")


async def run_history_generation(days: int = 30):
    """运行历史数据生成"""
    generator = HistoryGenerator(days=days)
    await generator.generate_all_history()
    await generator.generate_energy_history()


if __name__ == "__main__":
    asyncio.run(run_history_generation())
```

**Step 2: 验证历史生成器导入**

Run:
```bash
cd /d/mytest1 && python -c "from backend.app.services.history_generator import HistoryGenerator; print('OK')"
```

Expected: 输出 "OK"

---

### Task 3.2: 创建历史数据初始化入口脚本

**Files:**
- Create: `backend/init_history_data.py`

**Step 1: 创建入口脚本**

```python
"""
历史数据初始化脚本
生成30天的模拟历史数据用于系统展示
"""
import asyncio
import sys

from app.core.database import init_db
from app.services.history_generator import run_history_generation


async def main():
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 30

    print(f"=== 算力中心智能监控系统 - 历史数据初始化 ===")
    print(f"将生成 {days} 天的历史数据...")
    print()

    await init_db()
    await run_history_generation(days=days)

    print()
    print("=== 初始化完成 ===")


if __name__ == "__main__":
    asyncio.run(main())
```

**Step 2: 运行历史数据生成**

Run:
```bash
cd /d/mytest1 && python backend/init_history_data.py 30
```

Expected: 生成30天历史数据，输出进度信息

---

## Phase 4: 增强模拟器

### Task 4.1: 更新数据模拟器支持大楼点位

**Files:**
- Modify: `backend/app/services/simulator.py`

**Step 1: 更新模拟器添加设备特定逻辑**

在 `DataSimulator` 类中添加更智能的数值生成逻辑:

```python
def generate_ai_value(self, point: Point, current_value: float = None) -> float:
    """生成模拟量输入值 - 增强版"""
    min_val = point.min_range or 0
    max_val = point.max_range or 100

    # 根据设备类型设置基准值
    if current_value is None:
        if "温度" in point.point_name and "TH" in point.device_type:
            current_value = 24 + random.uniform(-2, 2)
        elif "湿度" in point.point_name:
            current_value = 50 + random.uniform(-5, 5)
        elif "负载率" in point.point_name:
            current_value = 45 + random.uniform(-10, 10)
        elif "电池电量" in point.point_name:
            current_value = 85 + random.uniform(-5, 5)
        elif "电压" in point.point_name and "输入" in point.point_name:
            current_value = 380 + random.uniform(-5, 5)
        elif "电压" in point.point_name and "输出" in point.point_name:
            current_value = 220 + random.uniform(-2, 2)
        elif "频率" in point.point_name:
            current_value = 50 + random.uniform(-0.5, 0.5)
        elif "冷冻水" in point.point_name and "出水" in point.point_name:
            current_value = 7 + random.uniform(-1, 1)
        elif "冷冻水" in point.point_name and "回水" in point.point_name:
            current_value = 12 + random.uniform(-1, 1)
        elif "冷却水" in point.point_name:
            current_value = 32 + random.uniform(-3, 3)
        else:
            current_value = (min_val + max_val) / 2

    # 模拟小幅波动
    variation = (max_val - min_val) * 0.02
    delta = random.uniform(-variation, variation)
    new_value = current_value + delta

    # 确保在量程范围内
    new_value = max(min_val, min(max_val, new_value))
    return round(new_value, 2)
```

**Step 2: 验证模拟器更新**

Run:
```bash
cd /d/mytest1 && python -c "from backend.app.services.simulator import DataSimulator; print('OK')"
```

Expected: 输出 "OK"

---

### Task 4.2: 添加模拟模式开关

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/services/simulator.py`

**Step 1: 在配置中添加模拟模式开关**

在 `config.py` 的 `Settings` 类中添加:

```python
# 模拟模式配置
simulation_enabled: bool = True  # 是否启用模拟数据
simulation_interval: int = 5     # 模拟数据生成间隔(秒)
```

**Step 2: 在模拟器中检查配置**

在 `simulator.py` 的 `start` 方法开头添加:

```python
async def start(self):
    """启动数据模拟"""
    from ..core.config import settings

    if not settings.simulation_enabled:
        print("模拟模式已禁用，跳过启动")
        return

    if self.running:
        return
    # ... 其余代码
```

**Step 3: 验证配置读取**

Run:
```bash
cd /d/mytest1 && python -c "from backend.app.core.config import settings; print(f'simulation_enabled={settings.simulation_enabled}')"
```

Expected: 输出 `simulation_enabled=True`

---

## Phase 5: 构建验证

### Task 5.1: 完整功能测试

**Step 1: 运行点位初始化**

Run:
```bash
cd /d/mytest1 && python backend/init_building_points.py
```

Expected: 成功创建约250个点位

**Step 2: 运行历史数据生成**

Run:
```bash
cd /d/mytest1 && python backend/init_history_data.py 7
```

Expected: 生成7天历史数据（用于快速测试）

**Step 3: 启动后端服务**

Run:
```bash
cd /d/mytest1 && python -m uvicorn backend.app.main:app --reload --port 8000
```

Expected: 服务启动成功，模拟器开始运行

**Step 4: 验证API返回新点位**

Run:
```bash
curl http://localhost:8000/api/v1/points?page_size=10 | jq '.data.items | length'
```

Expected: 返回10（有数据）

**Step 5: 前端构建验证**

Run:
```bash
cd /d/mytest1/frontend && npm run build
```

Expected: 构建成功

---

## 验证清单

- [ ] Task 1.1: 创建大楼点位定义文件
- [ ] Task 1.2: 创建告警阈值定义
- [ ] Task 2.1: 创建点位初始化脚本
- [ ] Task 3.1: 创建历史数据生成器
- [ ] Task 3.2: 创建历史数据入口脚本
- [ ] Task 4.1: 更新数据模拟器
- [ ] Task 4.2: 添加模拟模式开关
- [ ] Task 5.1: 完整功能测试

---

## 点位统计预估

| 楼层 | AI点位 | DI点位 | AO点位 | DO点位 | 合计 |
|------|--------|--------|--------|--------|------|
| B1 | 27 | 11 | 0 | 0 | 38 |
| F1 | 73 | 18 | 4 | 4 | 99 |
| F2 | 58 | 15 | 4 | 4 | 81 |
| F3 | 40 | 12 | 2 | 2 | 56 |
| **总计** | **198** | **56** | **10** | **10** | **274** |

---

*本计划将构建一个完整的3层算力中心大楼模拟数据系统，提供丰富的监控点位和历史数据支撑系统展示。*
