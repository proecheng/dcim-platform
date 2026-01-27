"""
设备调节能力初始化脚本
为power_devices表中的设备自动生成:
1. device_shift_configs - 设备负荷转移配置
2. load_regulation_configs - 设备参数调节配置

根据设备类型自动判断:
- 是否可转移负荷
- 可转移功率比例
- 调节方式（温度、频率、亮度等）
- 允许/禁止的转移时段
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

# 确保能够导入app模块
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session, init_db
from app.models.energy import (
    PowerDevice, DeviceShiftConfig, LoadRegulationConfig
)


# ==================== 设备类型配置规则 ====================

# 设备类型 -> 转移配置模板
SHIFT_CONFIG_TEMPLATES: Dict[str, Dict[str, Any]] = {
    # 空调/暖通设备 - 可调节温度/频率转移负荷
    "AC": {
        "is_shiftable": True,
        "shiftable_power_ratio": 0.30,  # 可转移30%功率
        "is_critical": False,
        "allowed_shift_hours": [0, 1, 2, 3, 4, 5, 6, 10, 11, 12, 13, 14, 15, 22, 23],  # 非峰时可转移
        "forbidden_shift_hours": [8, 9, 18, 19, 20, 21],  # 峰时不可转移
        "min_continuous_runtime": 0.5,  # 至少运行30分钟
        "max_shift_duration": 4.0,  # 最大转移4小时
        "min_power": None,  # 最低功率由设备决定
        "max_ramp_rate": 5.0,  # 5kW/分钟
        "shift_notice_time": 15,  # 提前15分钟通知
        "requires_manual_approval": False
    },
    "HVAC": {
        "is_shiftable": True,
        "shiftable_power_ratio": 0.35,
        "is_critical": False,
        "allowed_shift_hours": [0, 1, 2, 3, 4, 5, 6, 10, 11, 12, 13, 14, 15, 22, 23],
        "forbidden_shift_hours": [8, 9, 18, 19, 20, 21],
        "min_continuous_runtime": 0.5,
        "max_shift_duration": 4.0,
        "min_power": None,
        "max_ramp_rate": 10.0,
        "shift_notice_time": 15,
        "requires_manual_approval": False
    },
    # 照明 - 可分区控制/调光转移
    "LIGHT": {
        "is_shiftable": True,
        "shiftable_power_ratio": 0.50,  # 可转移50%功率
        "is_critical": False,
        "allowed_shift_hours": list(range(24)),  # 全天可转移
        "forbidden_shift_hours": [],
        "min_continuous_runtime": 0.0,
        "max_shift_duration": 8.0,
        "min_power": 0,
        "max_ramp_rate": 100.0,  # 照明可快速调节
        "shift_notice_time": 5,
        "requires_manual_approval": False
    },
    "LIGHTING": {
        "is_shiftable": True,
        "shiftable_power_ratio": 0.50,
        "is_critical": False,
        "allowed_shift_hours": list(range(24)),
        "forbidden_shift_hours": [],
        "min_continuous_runtime": 0.0,
        "max_shift_duration": 8.0,
        "min_power": 0,
        "max_ramp_rate": 100.0,
        "shift_notice_time": 5,
        "requires_manual_approval": False
    },
    # 水泵/风机 - 可变频调速
    "PUMP": {
        "is_shiftable": True,
        "shiftable_power_ratio": 0.40,
        "is_critical": False,
        "allowed_shift_hours": [0, 1, 2, 3, 4, 5, 6, 22, 23],
        "forbidden_shift_hours": [8, 9, 10, 18, 19, 20],
        "min_continuous_runtime": 1.0,
        "max_shift_duration": 3.0,
        "min_power": None,
        "max_ramp_rate": 3.0,
        "shift_notice_time": 30,
        "requires_manual_approval": False
    },
    # 冷水机组 - 可调节冷冻水温度
    "CHILLER": {
        "is_shiftable": True,
        "shiftable_power_ratio": 0.25,
        "is_critical": False,
        "allowed_shift_hours": [0, 1, 2, 3, 4, 5, 22, 23],
        "forbidden_shift_hours": [8, 9, 10, 14, 15, 16, 18, 19],
        "min_continuous_runtime": 2.0,
        "max_shift_duration": 2.0,
        "min_power": None,
        "max_ramp_rate": 2.0,
        "shift_notice_time": 60,
        "requires_manual_approval": True
    },
    # UPS - 可切换ECO模式
    "UPS": {
        "is_shiftable": False,  # UPS通常不可转移
        "shiftable_power_ratio": 0.0,
        "is_critical": True,
        "allowed_shift_hours": [],
        "forbidden_shift_hours": list(range(24)),
        "min_continuous_runtime": 0,
        "max_shift_duration": 0,
        "min_power": None,
        "max_ramp_rate": 0,
        "shift_notice_time": 0,
        "requires_manual_approval": True
    },
    # IT设备 - 关键负荷，不可转移
    "IT": {
        "is_shiftable": False,
        "shiftable_power_ratio": 0.0,
        "is_critical": True,
        "allowed_shift_hours": [],
        "forbidden_shift_hours": list(range(24)),
        "min_continuous_runtime": 0,
        "max_shift_duration": 0,
        "min_power": None,
        "max_ramp_rate": 0,
        "shift_notice_time": 0,
        "requires_manual_approval": True
    },
    "IT_SERVER": {
        "is_shiftable": False,
        "shiftable_power_ratio": 0.0,
        "is_critical": True,
        "allowed_shift_hours": [],
        "forbidden_shift_hours": list(range(24)),
        "min_continuous_runtime": 0,
        "max_shift_duration": 0,
        "min_power": None,
        "max_ramp_rate": 0,
        "shift_notice_time": 0,
        "requires_manual_approval": True
    },
    "IT_STORAGE": {
        "is_shiftable": False,
        "shiftable_power_ratio": 0.0,
        "is_critical": True,
        "allowed_shift_hours": [],
        "forbidden_shift_hours": list(range(24)),
        "min_continuous_runtime": 0,
        "max_shift_duration": 0,
        "min_power": None,
        "max_ramp_rate": 0,
        "shift_notice_time": 0,
        "requires_manual_approval": True
    },
}

# 设备类型 -> 调节配置模板
REGULATION_CONFIG_TEMPLATES: Dict[str, Dict[str, Any]] = {
    # 空调 - 温度调节
    "AC": {
        "regulation_type": "temperature",
        "min_value": 20.0,  # 最低温度20°C
        "max_value": 28.0,  # 最高温度28°C
        "default_value": 24.0,  # 默认24°C
        "current_value": 24.0,
        "step_size": 0.5,  # 0.5°C步长
        "unit": "°C",
        "power_factor": -3.0,  # 每升高1°C，降低3kW功率
        "base_power": None,  # 由设备额定功率决定
        "priority": 3,
        "comfort_impact": "medium",  # 舒适度影响中等
        "performance_impact": "none",
        "is_auto": False,
        # 功率曲线: 温度 -> 相对功率比例
        "power_curve": [
            {"value": 20.0, "power_ratio": 1.2},
            {"value": 22.0, "power_ratio": 1.0},
            {"value": 24.0, "power_ratio": 0.85},
            {"value": 26.0, "power_ratio": 0.7},
            {"value": 28.0, "power_ratio": 0.55}
        ]
    },
    "HVAC": {
        "regulation_type": "temperature",
        "min_value": 18.0,
        "max_value": 28.0,
        "default_value": 23.0,
        "current_value": 23.0,
        "step_size": 0.5,
        "unit": "°C",
        "power_factor": -4.0,
        "base_power": None,
        "priority": 3,
        "comfort_impact": "medium",
        "performance_impact": "none",
        "is_auto": False,
        "power_curve": [
            {"value": 18.0, "power_ratio": 1.3},
            {"value": 20.0, "power_ratio": 1.1},
            {"value": 23.0, "power_ratio": 0.85},
            {"value": 25.0, "power_ratio": 0.7},
            {"value": 28.0, "power_ratio": 0.5}
        ]
    },
    # 照明 - 亮度调节
    "LIGHT": {
        "regulation_type": "brightness",
        "min_value": 20.0,  # 最低亮度20%
        "max_value": 100.0,  # 最高亮度100%
        "default_value": 80.0,  # 默认80%
        "current_value": 80.0,
        "step_size": 5.0,  # 5%步长
        "unit": "%",
        "power_factor": 0.01,  # 每增加1%亮度，增加1%功率
        "base_power": None,
        "priority": 5,
        "comfort_impact": "low",
        "performance_impact": "none",
        "is_auto": False,
        "power_curve": [
            {"value": 20, "power_ratio": 0.2},
            {"value": 40, "power_ratio": 0.4},
            {"value": 60, "power_ratio": 0.6},
            {"value": 80, "power_ratio": 0.8},
            {"value": 100, "power_ratio": 1.0}
        ]
    },
    "LIGHTING": {
        "regulation_type": "brightness",
        "min_value": 20.0,
        "max_value": 100.0,
        "default_value": 80.0,
        "current_value": 80.0,
        "step_size": 5.0,
        "unit": "%",
        "power_factor": 0.01,
        "base_power": None,
        "priority": 5,
        "comfort_impact": "low",
        "performance_impact": "none",
        "is_auto": False,
        "power_curve": [
            {"value": 20, "power_ratio": 0.2},
            {"value": 40, "power_ratio": 0.4},
            {"value": 60, "power_ratio": 0.6},
            {"value": 80, "power_ratio": 0.8},
            {"value": 100, "power_ratio": 1.0}
        ]
    },
    # 水泵/风机 - 频率调节
    "PUMP": {
        "regulation_type": "load",  # 负载/频率调节
        "min_value": 30.0,  # 最低频率30Hz
        "max_value": 50.0,  # 最高频率50Hz
        "default_value": 45.0,  # 默认45Hz
        "current_value": 45.0,
        "step_size": 1.0,  # 1Hz步长
        "unit": "Hz",
        "power_factor": 2.5,  # 每增加1Hz，增加约2.5%功率（近似立方关系简化）
        "base_power": None,
        "priority": 4,
        "comfort_impact": "none",
        "performance_impact": "low",
        "is_auto": False,
        "power_curve": [
            {"value": 30, "power_ratio": 0.22},  # (30/50)^3 ≈ 0.216
            {"value": 35, "power_ratio": 0.34},
            {"value": 40, "power_ratio": 0.51},
            {"value": 45, "power_ratio": 0.73},
            {"value": 50, "power_ratio": 1.0}
        ]
    },
    # 冷水机组 - 冷冻水出水温度调节
    "CHILLER": {
        "regulation_type": "temperature",
        "min_value": 5.0,  # 最低出水温度5°C
        "max_value": 12.0,  # 最高出水温度12°C
        "default_value": 7.0,  # 默认7°C
        "current_value": 7.0,
        "step_size": 0.5,
        "unit": "°C",
        "power_factor": -5.0,  # 每升高1°C，降低约5%功率
        "base_power": None,
        "priority": 2,
        "comfort_impact": "none",
        "performance_impact": "medium",  # 可能影响制冷能力
        "is_auto": False,
        "power_curve": [
            {"value": 5.0, "power_ratio": 1.15},
            {"value": 7.0, "power_ratio": 1.0},
            {"value": 9.0, "power_ratio": 0.85},
            {"value": 12.0, "power_ratio": 0.65}
        ]
    },
    # UPS - 运行模式调节
    "UPS": {
        "regulation_type": "mode",  # 模式切换
        "min_value": 0,  # 0=正常模式
        "max_value": 1,  # 1=ECO模式
        "default_value": 0,
        "current_value": 0,
        "step_size": 1,
        "unit": "",
        "power_factor": -2.0,  # ECO模式可降低约2%损耗
        "base_power": None,
        "priority": 1,  # 优先级低，需要谨慎操作
        "comfort_impact": "none",
        "performance_impact": "high",  # 可能影响供电质量
        "is_auto": False,
        "power_curve": [
            {"value": 0, "power_ratio": 1.0, "label": "正常模式"},
            {"value": 1, "power_ratio": 0.97, "label": "ECO模式"}
        ]
    },
}


def get_shift_config_for_device(device: PowerDevice) -> Optional[Dict[str, Any]]:
    """
    根据设备类型获取转移配置

    Args:
        device: 用电设备

    Returns:
        转移配置字典，如果设备类型不支持则返回None
    """
    device_type = device.device_type.upper() if device.device_type else ""

    # 查找匹配的模板
    template = SHIFT_CONFIG_TEMPLATES.get(device_type)

    if not template:
        # 默认配置 - 不可转移
        return {
            "device_id": device.id,
            "is_shiftable": False,
            "shiftable_power_ratio": 0.0,
            "is_critical": device.is_critical or False,
            "allowed_shift_hours": [],
            "forbidden_shift_hours": list(range(24)),
            "min_continuous_runtime": 0,
            "max_shift_duration": 0,
            "min_power": None,
            "max_ramp_rate": 0,
            "shift_notice_time": 0,
            "requires_manual_approval": True
        }

    # 计算min_power（基于额定功率的20%）
    min_power = None
    if template.get("is_shiftable") and device.rated_power:
        min_power = device.rated_power * 0.2

    return {
        "device_id": device.id,
        **template,
        "min_power": min_power or template.get("min_power")
    }


def get_regulation_config_for_device(device: PowerDevice) -> Optional[Dict[str, Any]]:
    """
    根据设备类型获取调节配置

    Args:
        device: 用电设备

    Returns:
        调节配置字典，如果设备类型不支持调节则返回None
    """
    device_type = device.device_type.upper() if device.device_type else ""

    # 查找匹配的模板
    template = REGULATION_CONFIG_TEMPLATES.get(device_type)

    if not template:
        return None  # 该类型设备不支持调节

    # 计算base_power（设备额定功率）
    base_power = device.rated_power or 0

    # 处理功率曲线 - 转换power_ratio为实际功率
    power_curve = None
    if template.get("power_curve"):
        power_curve = [
            {
                **point,
                "power": round(base_power * point.get("power_ratio", 1.0), 2)
            }
            for point in template["power_curve"]
        ]

    config = {
        "device_id": device.id,
        "regulation_type": template["regulation_type"],
        "min_value": template["min_value"],
        "max_value": template["max_value"],
        "default_value": template["default_value"],
        "current_value": template["current_value"],
        "step_size": template["step_size"],
        "unit": template.get("unit", ""),
        "power_factor": template.get("power_factor"),
        "base_power": base_power,
        "power_curve": power_curve,
        "priority": template.get("priority", 5),
        "comfort_impact": template.get("comfort_impact", "none"),
        "performance_impact": template.get("performance_impact", "none"),
        "is_enabled": True,
        "is_auto": template.get("is_auto", False)
    }

    return config


async def init_device_regulation_configs(force: bool = False, interactive: bool = True):
    """
    初始化设备调节配置

    Args:
        force: 是否强制覆盖现有配置（不询问确认）
        interactive: 是否为交互模式（非交互模式跳过确认提示）
    """
    await init_db()

    async with async_session() as session:
        # 1. 获取所有用电设备
        result = await session.execute(select(PowerDevice).where(PowerDevice.is_enabled == True))
        devices = result.scalars().all()

        if not devices:
            print("没有找到用电设备，请先运行 init_energy.py 初始化设备数据")
            return

        print(f"找到 {len(devices)} 个用电设备")

        # 2. 检查是否已有配置
        shift_count = await session.execute(
            select(func.count(DeviceShiftConfig.id))
        )
        existing_shift = shift_count.scalar()

        reg_count = await session.execute(
            select(func.count(LoadRegulationConfig.id))
        )
        existing_reg = reg_count.scalar()

        if existing_shift > 0 or existing_reg > 0:
            print(f"已存在配置: 转移配置 {existing_shift} 条, 调节配置 {existing_reg} 条")

            if not force:
                if interactive:
                    confirm = input("是否清除现有配置并重新生成? (y/n): ")
                    if confirm.lower() != 'y':
                        print("取消操作")
                        return
                else:
                    print("非交互模式，跳过重新生成（已有配置）")
                    return

            # 清除现有配置
            await session.execute(delete(DeviceShiftConfig))
            await session.execute(delete(LoadRegulationConfig))
            await session.commit()
            print("已清除现有配置")

        # 3. 为每个设备生成配置
        shift_configs_created = 0
        reg_configs_created = 0
        shiftable_count = 0
        adjustable_count = 0

        print("\n开始生成设备配置...")
        print("-" * 60)

        for device in devices:
            print(f"\n设备: {device.device_name} ({device.device_code})")
            print(f"  类型: {device.device_type}, 额定功率: {device.rated_power}kW")

            # 生成转移配置
            shift_config = get_shift_config_for_device(device)
            if shift_config:
                config = DeviceShiftConfig(**shift_config)
                session.add(config)
                shift_configs_created += 1

                if shift_config["is_shiftable"]:
                    shiftable_count += 1
                    shiftable_power = (device.rated_power or 0) * shift_config["shiftable_power_ratio"]
                    print(f"  [OK] 可转移负荷: {shiftable_power:.1f}kW ({shift_config['shiftable_power_ratio']*100:.0f}%)")
                    print(f"       允许时段: {format_hours(shift_config['allowed_shift_hours'])}")
                else:
                    print(f"  [NO] 不可转移 (关键负荷: {shift_config['is_critical']})")

            # 生成调节配置
            reg_config = get_regulation_config_for_device(device)
            if reg_config:
                config = LoadRegulationConfig(**reg_config)
                session.add(config)
                reg_configs_created += 1
                adjustable_count += 1

                reg_type_name = {
                    "temperature": "温度调节",
                    "brightness": "亮度调节",
                    "load": "负载/频率调节",
                    "mode": "模式切换"
                }.get(reg_config["regulation_type"], reg_config["regulation_type"])

                print(f"  [OK] 可调节: {reg_type_name}")
                print(f"       范围: {reg_config['min_value']}-{reg_config['max_value']}{reg_config['unit']}")
                print(f"       当前值: {reg_config['current_value']}{reg_config['unit']}")

        await session.commit()

        # 4. 输出统计
        print("\n" + "=" * 60)
        print("配置生成完成!")
        print("=" * 60)
        print(f"\n设备总数: {len(devices)}")
        print(f"转移配置: {shift_configs_created} 条 (其中可转移: {shiftable_count})")
        print(f"调节配置: {reg_configs_created} 条")

        # 计算总可转移功率
        total_shiftable_power = sum(
            (d.rated_power or 0) * (get_shift_config_for_device(d) or {}).get("shiftable_power_ratio", 0)
            for d in devices
        )
        print(f"\n总可转移功率: {total_shiftable_power:.1f} kW")

        # 按设备类型统计
        print("\n按设备类型统计:")
        type_stats = {}
        for device in devices:
            dt = device.device_type or "OTHER"
            if dt not in type_stats:
                type_stats[dt] = {"count": 0, "shiftable": 0, "adjustable": 0}
            type_stats[dt]["count"] += 1

            shift_cfg = get_shift_config_for_device(device)
            if shift_cfg and shift_cfg.get("is_shiftable"):
                type_stats[dt]["shiftable"] += 1

            if get_regulation_config_for_device(device):
                type_stats[dt]["adjustable"] += 1

        for dt, stats in type_stats.items():
            print(f"  {dt}: {stats['count']}台, 可转移{stats['shiftable']}台, 可调节{stats['adjustable']}台")


def format_hours(hours: List[int]) -> str:
    """格式化小时列表为时段字符串"""
    if not hours:
        return "无"
    if len(hours) == 24:
        return "全天"

    hours = sorted(hours)
    ranges = []
    start = hours[0]
    end = hours[0]

    for i in range(1, len(hours)):
        if hours[i] == end + 1:
            end = hours[i]
        else:
            ranges.append(f"{start}:00-{end+1}:00")
            start = hours[i]
            end = hours[i]
    ranges.append(f"{start}:00-{end+1}:00")

    return ", ".join(ranges)


if __name__ == "__main__":
    import sys

    # 支持命令行参数
    force = False
    interactive = True

    if len(sys.argv) > 1:
        if "--force" in sys.argv or "-f" in sys.argv:
            force = True
        if "--yes" in sys.argv or "-y" in sys.argv:
            interactive = False
            force = True  # --yes 隐含 --force

    asyncio.run(init_device_regulation_configs(force=force, interactive=interactive))
