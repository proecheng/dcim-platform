"""劣化分析配置 — Story 36.1"""

# 默认分析窗口天数
DEFAULT_WINDOW_DAYS = 30

# 设备类型 → 插件标识映射
# Device.device_type → 插件 registry key
DEVICE_TYPE_MAP: dict[str, str] = {
    "UPS": "ups",                       # TODO: UPS 插件待 Story 36.5 实现
    "AC": "hvac",
    "PRECISION_AC_INDOOR": "hvac",
    "PRECISION_AC_OUTDOOR": "hvac",
    "PDU": "pdu",                       # TODO: PDU 插件待 Story 36.5 实现
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

# PointHistory 降级查询限制天数
# 注意：7天数据在 data_sufficiency 判断中永远无法达到 "full"
# （需 day_span >= window_days * 0.8 = 24天），这是有意的降级限制
FALLBACK_HISTORY_DAYS = 7
