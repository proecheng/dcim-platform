"""
负荷转移系统数据模型

基于 docs/负荷转移系统技术文档.md V3.0 设计
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, Float, Text, DateTime, Date, Time, ForeignKey, JSON, Numeric
from sqlalchemy.orm import relationship

from ..core.database import Base


# ==================== 负荷转移计划模型 ====================


class ShiftPlan(Base):
    """负荷转移计划表

    存储用户创建的负荷转移计划，包含转移时段、目标设备、约束条件等
    """

    __tablename__ = "shift_plans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plan_code = Column(String(50), unique=True, nullable=False, comment="计划编号 如 SP-20260303-001")
    plan_name = Column(String(200), nullable=False, comment="计划名称")

    # 转移时段
    shift_from_period = Column(String(20), nullable=False, comment="转出时段: peak/sharp")
    shift_to_period = Column(String(20), nullable=False, comment="转入时段: valley/flat")
    shift_date = Column(Date, nullable=False, comment="转移日期")
    start_time = Column(Time, nullable=False, comment="转移开始时间")
    end_time = Column(Time, nullable=False, comment="转移结束时间")

    # 目标/结果功率与收益
    target_shift_power = Column(Float, nullable=False, comment="目标转移功率 kW")
    selected_devices = Column(JSON, comment="选中设备列表")
    constraints = Column(JSON, comment="约束配置")
    expected_cost_saving = Column(Float, comment="预期节省电费 元")
    expected_energy_saving = Column(Float, comment="预期节省电量 kWh")
    actual_shift_power = Column(Float, comment="实际转移功率 kW")
    actual_cost_saving = Column(Float, comment="实际节省电费 元")
    actual_energy_saving = Column(Float, comment="实际节省电量 kWh")

    # 状态管理
    status = Column(String(20), default="draft", nullable=False, comment="状态")
    approval_status = Column(String(20), default="pending", nullable=False, comment="审批状态")
    execution_status = Column(String(20), default="not_started", nullable=False, comment="执行状态")

    # 描述/失败信息
    description = Column(Text, comment="计划描述")
    error_message = Column(Text, comment="错误信息")

    # 流程信息
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False, comment="创建人ID")
    approved_by = Column(Integer, ForeignKey("users.id"), comment="审批人ID")
    approval_comment = Column(Text, comment="审批意见")
    created_at = Column(DateTime, default=datetime.now, nullable=False, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    approved_at = Column(DateTime, comment="审批时间")
    executed_at = Column(DateTime, comment="执行时间")
    completed_at = Column(DateTime, comment="完成时间")

    # 关系
    executions = relationship("ShiftExecution", back_populates="plan", cascade="all, delete-orphan")
    analysis_records = relationship("ShiftAnalysisRecord", back_populates="plan", cascade="all, delete-orphan")


class ShiftExecution(Base):
    """负荷转移执行记录表

    记录每次转移计划的执行过程和结果
    """

    __tablename__ = "shift_executions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plan_id = Column(Integer, ForeignKey("shift_plans.id", ondelete="CASCADE"), nullable=False, comment="关联计划ID")
    execution_code = Column(String(50), unique=True, nullable=False, comment="执行编号 如 SE-20260303-001")

    # 执行时间
    start_time = Column(DateTime, nullable=False, comment="开始时间")
    end_time = Column(DateTime, comment="结束时间")
    duration_minutes = Column(Integer, comment="执行时长 分钟")

    # 执行前状态
    before_total_power = Column(Float, comment="执行前总功率 kW")
    before_device_states = Column(JSON, comment="执行前设备状态快照")

    # 执行后状态
    after_total_power = Column(Float, comment="执行后总功率 kW")
    after_device_states = Column(JSON, comment="执行后设备状态快照")

    # 实际效果
    actual_shift_power = Column(Float, comment="实际转移功率 kW")
    actual_cost_saving = Column(Numeric(10, 2), comment="实际节省电费 元")
    actual_energy_saving = Column(Numeric(10, 2), comment="实际节省电量 kWh")

    # 执行状态
    status = Column(
        String(20), default="pending", comment="状态: pending/executing/completed/failed/cancelled/reverted"
    )
    success_rate = Column(Float, comment="成功率 0-1")

    # 失败信息
    failure_reason = Column(Text, comment="失败原因")
    error_details = Column(JSON, comment="错误详情")

    # 设备执行详情 (JSON)
    device_execution_details = Column(
        JSON,
        comment="""设备执行详情 JSON:
        [
            {
                "device_id": 123,
                "device_name": "空调-1",
                "action": "reduce_temp",
                "before_value": 24.0,
                "after_value": 26.0,
                "power_before": 50.0,
                "power_after": 40.0,
                "power_saved": 10.0,
                "status": "success",
                "executed_at": "2026-03-03T14:00:00"
            },
            ...
        ]
    """,
    )

    # 制冷联动记录
    cooling_linkage_data = Column(
        JSON,
        comment="""制冷联动数据 JSON:
        {
            "cooling_lag_minutes": 20,
            "cooling_power_before": 200.0,
            "cooling_power_after": 180.0,
            "cooling_efficiency_before": 3.5,
            "cooling_efficiency_after": 3.8,
            "supply_temp_before": 18.0,
            "supply_temp_after": 19.0
        }
    """,
    )

    # 执行人
    executed_by = Column(Integer, ForeignKey("users.id"), comment="执行人ID")

    # 时间戳
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")

    # 关系
    plan = relationship("ShiftPlan", back_populates="executions")


class ShiftConstraint(Base):
    """负荷转移约束配置表

    存储全局和设备级别的转移约束规则
    """

    __tablename__ = "shift_constraints"

    id = Column(Integer, primary_key=True, autoincrement=True)
    constraint_name = Column(String(100), nullable=False, comment="约束名称")
    constraint_type = Column(
        String(30), nullable=False, comment="约束类型: power/time/device/cooling/safety/electrical"
    )
    constraint_level = Column(String(20), default="global", comment="约束级别: global/device/circuit")

    # 关联对象
    device_id = Column(Integer, ForeignKey("power_devices.id"), comment="关联设备ID (设备级约束)")
    circuit_id = Column(Integer, ForeignKey("distribution_circuits.id"), comment="关联回路ID (回路级约束)")

    # 约束参数 (JSON)
    constraint_params = Column(
        JSON,
        nullable=False,
        comment="""约束参数 JSON:
        # 功率约束
        {
            "type": "power",
            "max_shift_power": 500,
            "min_shift_power": 100,
            "max_ramp_rate": 10  # kW/min
        }

        # 时间约束
        {
            "type": "time",
            "min_continuous_runtime": 2.0,  # 小时
            "max_shift_duration": 4.0,  # 小时
            "allowed_hours": [0, 1, 2, 22, 23],  # 允许转移的小时
            "forbidden_hours": [8, 9, 10, 11, 12, 13, 14, 15, 16, 17]  # 禁止转移的小时
        }

        # 设备约束
        {
            "type": "device",
            "max_devices": 10,
            "allow_critical_devices": false,
            "device_startup_time": 5,  # 分钟
            "device_shutdown_time": 3  # 分钟
        }

        # 制冷约束
        {
            "type": "cooling",
            "cooling_lag_minutes": 20,
            "max_temp_rise": 2.0,  # ℃
            "min_cooling_efficiency": 3.0  # COP
        }

        # 安全约束
        {
            "type": "safety",
            "safety_factor": 0.85,
            "min_ups_capacity_ratio": 0.2,  # UPS剩余容量比例
            "max_it_load_ratio": 0.8  # IT负载比例
        }

        # 电气约束
        {
            "type": "electrical",
            "three_phase_balance_threshold": 0.1,  # 三相不平衡度阈值
            "max_thd": 0.05,  # 总谐波畸变率
            "voltage_deviation_threshold": 0.07  # 电压偏差阈值
        }
    """,
    )

    # 优先级
    priority = Column(Integer, default=5, comment="优先级 1-10 (1最高)")

    # 启用状态
    is_enabled = Column(Boolean, default=True, comment="是否启用")
    is_mandatory = Column(Boolean, default=False, comment="是否强制约束")

    # 违反处理
    violation_action = Column(String(20), default="reject", comment="违反处理: reject/warn/ignore")

    # 时间戳
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    # 备注
    remark = Column(Text, comment="备注")

    @property
    def constraint_config(self) -> dict:
        """兼容读取：统一使用 constraint_config 访问约束参数。"""
        return self.constraint_params or {}

    @constraint_config.setter
    def constraint_config(self, value: dict):
        self.constraint_params = value or {}

    @property
    def description(self) -> str | None:
        """兼容字段：description 映射到 remark。"""
        return self.remark

    @description.setter
    def description(self, value: str | None):
        self.remark = value

    @property
    def is_active(self) -> bool:
        """兼容字段：is_active 映射到 is_enabled。"""
        return bool(self.is_enabled)

    @is_active.setter
    def is_active(self, value: bool):
        self.is_enabled = bool(value)


class ShiftOpportunity(Base):
    """负荷转移机会分析表

    系统自动分析并推荐的转移机会
    """

    __tablename__ = "shift_opportunities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    opportunity_code = Column(String(50), unique=True, nullable=False, comment="机会编号 如 SO-20260303-001")
    opportunity_name = Column(String(200), nullable=False, comment="机会名称")

    # 分析时段
    recommended_date = Column(Date, nullable=False, comment="推荐日期")
    analysis_period = Column(String(20), comment="分析时段: peak/sharp")

    # 推荐转移方案
    recommended_shift_from = Column(String(20), comment="推荐转出时段")
    recommended_shift_to = Column(String(20), comment="推荐转入时段")
    recommended_shift_power = Column(Float, comment="推荐转移功率 kW")
    recommended_devices = Column(JSON, comment="推荐设备列表")

    # 收益预测
    estimated_cost_saving = Column(Numeric(10, 2), comment="预测节省电费 元")
    estimated_energy_saving = Column(Numeric(10, 2), comment="预测节省电量 kWh")
    confidence_score = Column(Float, comment="置信度评分 0-1")

    # 分析数据 (JSON)
    analysis_data = Column(
        JSON,
        comment="""分析数据 JSON:
        {
            "current_peak_power": 1000.0,
            "current_valley_power": 400.0,
            "peak_valley_diff": 600.0,
            "available_shift_power": 500.0,
            "price_diff": 0.8,  # 元/kWh
            "constraint_violations": [],
            "risk_factors": []
        }
    """,
    )

    # 状态
    status = Column(String(20), default="discovered", comment="状态: discovered/reviewed/accepted/rejected/converted")
    priority = Column(String(20), default="medium", comment="优先级: high/medium/low")

    # 转换为计划
    converted_to_plan_id = Column(Integer, ForeignKey("shift_plans.id"), comment="转换为计划ID")
    converted_at = Column(DateTime, comment="转换时间")

    # 时间戳
    discovered_at = Column(DateTime, default=datetime.now, comment="发现时间")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")


class ShiftAnalysisRecord(Base):
    """负荷转移分析记录表

    记录每次转移计划的分析过程和结果
    """

    __tablename__ = "shift_analysis_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plan_id = Column(Integer, ForeignKey("shift_plans.id", ondelete="CASCADE"), comment="关联计划ID")
    analysis_type = Column(String(30), nullable=False, comment="分析类型: feasibility/constraint/risk/benefit")

    # 分析结果
    analysis_result = Column(String(20), comment="分析结果: pass/fail/warning")
    analysis_score = Column(Float, comment="分析评分 0-100")

    # 分析详情 (JSON)
    analysis_details = Column(
        JSON,
        comment="""分析详情 JSON:
        {
            "constraint_checks": [
                {
                    "constraint_name": "最大转移功率",
                    "constraint_value": 500,
                    "actual_value": 450,
                    "status": "pass"
                },
                ...
            ],
            "risk_assessment": {
                "risk_level": "low",
                "risk_factors": [],
                "mitigation_measures": []
            },
            "benefit_analysis": {
                "cost_saving": 1000.0,
                "energy_saving": 500.0,
                "roi": 0.95
            }
        }
    """,
    )

    # 建议
    recommendations = Column(JSON, comment="优化建议列表")
    warnings = Column(JSON, comment="警告信息列表")

    # 时间戳
    analyzed_at = Column(DateTime, default=datetime.now, comment="分析时间")

    # 关系
    plan = relationship("ShiftPlan", back_populates="analysis_records")


# ==================== 制冷联动模型 ====================


class CoolingLinkageConfig(Base):
    """制冷联动配置表

    配置负荷转移与制冷系统的联动规则
    """

    __tablename__ = "cooling_linkage_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cooling_zone_id = Column(
        Integer, ForeignKey("cooling_zones.id", ondelete="CASCADE"), nullable=False, comment="关联制冷区域"
    )
    enabled = Column(Boolean, default=True, comment="是否启用制冷联动")
    lag_time_minutes = Column(Integer, default=20, comment="制冷滞后时间 分钟")

    # COP 参数
    target_cop = Column(Float, default=3.0, comment="目标 COP")
    cop_lower_threshold = Column(Float, default=2.0, comment="COP 下限阈值")
    cop_upper_threshold = Column(Float, default=4.5, comment="COP 上限阈值")

    # 温度参数
    target_supply_temp = Column(Float, default=10.0, comment="供水温度目标值 ℃")
    supply_temp_lower = Column(Float, default=5.0, comment="供水温度下限 ℃")
    supply_temp_upper = Column(Float, default=15.0, comment="供水温度上限 ℃")
    target_return_temp = Column(Float, default=15.0, comment="回水温度目标值 ℃")
    return_temp_lower = Column(Float, default=10.0, comment="回水温度下限 ℃")
    return_temp_upper = Column(Float, default=20.0, comment="回水温度上限 ℃")

    # 调整策略
    power_adjust_step = Column(Integer, default=20, comment="功率调整步长 kW")
    max_adjust_ratio = Column(Float, default=0.25, comment="最大调整幅度")
    adjust_interval_minutes = Column(Integer, default=10, comment="调整间隔时间 分钟")

    # 安全保护
    safety_protection_enabled = Column(Boolean, default=True, comment="启用安全保护")
    min_cooling_power = Column(Float, default=100, comment="最小制冷功率 kW")
    max_cooling_power = Column(Float, default=2000, comment="最大制冷功率 kW")

    # 预冷功能（Story 29.1 新增）
    precool_target_temp = Column(Float, nullable=True, comment="预冷目标温度 °C")
    precool_enabled = Column(Boolean, default=False, comment="是否启用预冷功能")

    # 时间戳
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")


class CoolingLinkageRecord(Base):
    """制冷联动记录表

    记录每次负荷转移时的制冷系统响应
    """

    __tablename__ = "cooling_linkage_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    execution_id = Column(Integer, ForeignKey("shift_executions.id", ondelete="CASCADE"), comment="关联执行ID")

    # 时间信息
    timestamp = Column(DateTime, nullable=False, default=datetime.now, comment="记录时间")
    event_type = Column(String(20), comment="事件类型: adjust/alarm/recovery/manual")

    # 功率数据
    before_power = Column(Float, comment="调整前功率 kW")
    after_power = Column(Float, comment="调整后功率 kW")
    power_change = Column(Float, comment="功率变化 kW")

    # COP 数据
    cop_before = Column(Float, comment="调整前 COP")
    cop_after = Column(Float, comment="调整后 COP")

    # 温度数据
    supply_temp_before = Column(Float, comment="调整前供水温度 ℃")
    supply_temp_after = Column(Float, comment="调整后供水温度 ℃")
    return_temp_before = Column(Float, comment="调整前回水温度 ℃")
    return_temp_after = Column(Float, comment="调整后回水温度 ℃")

    # 调整原因
    reason = Column(Text, comment="调整原因")

    # 时间戳
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")


# ==================== 设备寿命管理模型 ====================


class DeviceLifespanImpact(Base):
    """设备寿命影响记录表

    记录负荷转移对设备寿命的影响
    """

    __tablename__ = "device_lifespan_impacts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(Integer, ForeignKey("power_devices.id"), nullable=False, comment="设备ID")
    execution_id = Column(Integer, ForeignKey("shift_executions.id", ondelete="CASCADE"), comment="关联执行ID")

    # 操作类型
    operation_type = Column(String(20), comment="操作类型: startup/shutdown/load_change")
    operation_count = Column(Integer, default=1, comment="操作次数")

    # 寿命影响
    lifespan_loss_hours = Column(Float, comment="寿命损失 小时")
    lifespan_loss_percentage = Column(Float, comment="寿命损失百分比")

    # 累计影响
    cumulative_startups = Column(Integer, comment="累计启动次数")
    cumulative_lifespan_loss = Column(Float, comment="累计寿命损失 小时")

    # 维护建议
    maintenance_recommended = Column(Boolean, default=False, comment="是否建议维护")
    maintenance_reason = Column(Text, comment="维护原因")
    next_maintenance_date = Column(Date, comment="建议维护日期")

    # 时间戳
    recorded_at = Column(DateTime, default=datetime.now, comment="记录时间")
