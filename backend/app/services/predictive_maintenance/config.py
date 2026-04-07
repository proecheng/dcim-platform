"""劣化分析配置 — Story 36.1 / 36.5"""

# 默认分析窗口天数
DEFAULT_WINDOW_DAYS = 30

# 设备类型 → 插件标识映射
# Device.device_type → 插件 registry key
DEVICE_TYPE_MAP: dict[str, str] = {
    "UPS": "ups",
    "AC": "hvac",
    "PRECISION_AC_INDOOR": "hvac",
    "PRECISION_AC_OUTDOOR": "hvac",
    "PDU": "pdu",
    "BATTERY": "battery",
    # TH/DOOR/SMOKE/WATER/IR/FAN/LIGHT 等不参与劣化分析
}

# 数据质量过滤阈值（quality < 此值视为有效数据）
VALID_QUALITY_THRESHOLD = 2

# HVAC 插件配置
HVAC_CONFIG = {
    # 必需 point_code 后缀模式
    "required_point_suffixes": ["return_temp"],
    # 压缩机状态后缀（必需，支持多个压缩机）
    "compressor_status_suffixes": ["compressor1_status", "compressor2_status"],
    # 可选 point_code 后缀模式
    "optional_point_suffixes": ["cop", "compressor_hours", "filter_alarm"],
    # COP 月度斜率劣化阈值（低于此值视为劣化信号）
    "cop_slope_threshold_per_month": -0.05,
    # 压缩机维保周期（小时）
    "compressor_maintenance_hours": 20000,
    # 回风温度偏差斜率劣化阈值（>0 表示持续上升）
    "return_temp_slope_threshold": 0.0,
    # 综合评分权重
    "weights": {
        "return_temp_trend": 0.30,
        "compressor_status": 0.25,
        "cop_trend": 0.20,
        "compressor_hours": 0.15,
        "filter_alarm": 0.10,
    },
}

# UPS 插件配置 — Story 36.5
UPS_CONFIG = {
    "required_point_suffixes": ["input_voltage", "output_voltage"],
    "optional_point_suffixes": ["efficiency", "transfer_count", "temperature"],
    "weights": {
        "voltage_stability": 0.35,
        "efficiency_trend": 0.25,
        "transfer_count": 0.20,
        "temperature": 0.20,
    },
    "voltage_std_threshold": 2.0,  # 电压标准差劣化阈值（V）
    "efficiency_slope_threshold_per_month": -0.5,  # 效率月度下降阈值（%）
    "transfer_count_threshold": 5,  # 30天切换次数劣化阈值
    "voltage_segment_count": 7,  # 电压分段数
    "min_segments_for_trend": 3,  # 最少段数才做趋势
}

# PDU 插件配置 — Story 36.5
PDU_CONFIG = {
    "required_point_suffixes": ["load_percentage", "voltage"],
    "optional_point_suffixes": ["thd", "temperature_rise"],
    "weights": {
        "load_trend": 0.35,
        "voltage_stability": 0.25,
        "thd_trend": 0.20,
        "temperature_rise": 0.20,
    },
    "load_high_threshold": 80.0,  # 负载率高位阈值（%）
    "thd_slope_threshold_per_month": 0.5,  # THD 月度上升阈值（%）
    "voltage_std_threshold": 0.5,  # PDU 电压稳定性阈值（V，低于 UPS）
}

# Battery 插件配置 — Story 36.5
BATTERY_CONFIG = {
    "required_point_suffixes": ["internal_resistance"],
    "optional_point_suffixes": ["cycle_count", "temperature"],
    "virtual_point_suffixes": ["soh_percent"],  # 由 Analyzer 从 BatterySOHRecord 注入
    "weights": {
        "soh": 0.50,
        "resistance_trend": 0.30,
        "temperature": 0.20,
    },
}

# PointHistory 降级查询限制天数
# 注意：7天数据在 data_sufficiency 判断中永远无法达到 "full"
# （需 day_span >= window_days * 0.8 = 24天），这是有意的降级限制
FALLBACK_HISTORY_DAYS = 7
