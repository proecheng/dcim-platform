"""
负荷转移系统 API 端点设计

基于 docs/负荷转移系统技术文档.md V3.0
"""

# ==================== API 端点结构 ====================

"""
负荷转移 API 端点 (挂载到 /api/v1/energy/shift)

## 1. 转移计划管理

### 1.1 计划 CRUD
- GET    /shift/plans                    # 获取计划列表
- POST   /shift/plans                    # 创建计划
- GET    /shift/plans/{plan_id}          # 获取计划详情
- PUT    /shift/plans/{plan_id}          # 更新计划
- DELETE /shift/plans/{plan_id}          # 删除计划

### 1.2 计划审批
- POST   /shift/plans/{plan_id}/submit   # 提交审批
- POST   /shift/plans/{plan_id}/approve  # 审批通过
- POST   /shift/plans/{plan_id}/reject   # 审批拒绝

### 1.3 计划执行
- POST   /shift/plans/{plan_id}/execute  # 执行计划
- POST   /shift/plans/{plan_id}/cancel   # 取消执行
- GET    /shift/plans/{plan_id}/status   # 获取执行状态

## 2. 转移机会分析

### 2.1 机会发现
- POST   /shift/opportunities/analyze    # 触发机会分析
- GET    /shift/opportunities             # 获取机会列表
- GET    /shift/opportunities/{opp_id}   # 获取机会详情
- POST   /shift/opportunities/{opp_id}/convert  # 转换为计划

### 2.2 可行性分析
- POST   /shift/analysis/feasibility     # 可行性分析
- POST   /shift/analysis/constraints     # 约束检查
- POST   /shift/analysis/risk            # 风险评估
- POST   /shift/analysis/benefit         # 收益分析

## 3. 设备管理

### 3.1 可转移设备
- GET    /shift/devices/shiftable        # 获取可转移设备列表
- GET    /shift/devices/{device_id}/shift-potential  # 获取设备转移潜力
- PUT    /shift/devices/{device_id}/shift-config     # 更新设备转移配置

### 3.2 设备状态
- GET    /shift/devices/{device_id}/status           # 获取设备当前状态
- GET    /shift/devices/{device_id}/history          # 获取设备转移历史

## 4. 约束管理

### 4.1 约束配置
- GET    /shift/constraints              # 获取约束列表
- POST   /shift/constraints              # 创建约束
- PUT    /shift/constraints/{id}         # 更新约束
- DELETE /shift/constraints/{id}         # 删除约束

### 4.2 约束验证
- POST   /shift/constraints/validate     # 验证计划是否满足约束

## 5. 执行记录

### 5.1 执行历史
- GET    /shift/executions               # 获取执行记录列表
- GET    /shift/executions/{exec_id}     # 获取执行详情
- GET    /shift/executions/{exec_id}/devices  # 获取设备执行详情

### 5.2 执行统计
- GET    /shift/executions/statistics    # 获取执行统计
- GET    /shift/executions/summary       # 获取执行汇总

## 6. 制冷联动

### 6.1 联动配置
- GET    /shift/cooling/config           # 获取制冷联动配置
- PUT    /shift/cooling/config           # 更新制冷联动配置

### 6.2 联动监控
- GET    /shift/cooling/status           # 获取制冷系统状态
- GET    /shift/cooling/records          # 获取制冷联动记录
- GET    /shift/cooling/efficiency       # 获取制冷效率趋势

## 7. 设备寿命管理

### 7.1 寿命影响
- GET    /shift/lifespan/impacts         # 获取寿命影响记录
- GET    /shift/lifespan/devices/{device_id}  # 获取设备寿命影响

### 7.2 维护建议
- GET    /shift/lifespan/maintenance     # 获取维护建议列表

## 8. 报表与统计

### 8.1 收益报表
- GET    /shift/reports/savings          # 获取节省收益报表
- GET    /shift/reports/monthly          # 获取月度报表
- GET    /shift/reports/yearly           # 获取年度报表

### 8.2 导出
- GET    /shift/reports/export/excel     # 导出Excel报表
- GET    /shift/reports/export/pdf       # 导出PDF报表

## 9. 仪表盘

### 9.1 概览
- GET    /shift/dashboard/overview       # 获取仪表盘概览
- GET    /shift/dashboard/realtime       # 获取实时数据
- GET    /shift/dashboard/trends         # 获取趋势数据
"""


# ==================== 请求/响应 Schema 设计 ====================

"""
Pydantic Schema 设计 (backend/app/schemas/load_shift.py)

## 1. 转移计划 Schema

### ShiftPlanCreate
- plan_name: str
- shift_from_period: str  # peak/sharp
- shift_to_period: str    # valley/flat
- shift_date: date
- shift_start_time: str   # HH:MM
- shift_end_time: str     # HH:MM
- target_shift_power: float
- constraints: dict
- selected_devices: list[dict]

### ShiftPlanUpdate
- plan_name: Optional[str]
- shift_start_time: Optional[str]
- shift_end_time: Optional[str]
- target_shift_power: Optional[float]
- selected_devices: Optional[list[dict]]

### ShiftPlanResponse
- id: int
- plan_code: str
- plan_name: str
- shift_date: date
- shift_from_period: str
- shift_to_period: str
- target_shift_power: float
- actual_shift_power: Optional[float]
- expected_cost_saving: Decimal
- status: str
- approval_status: Optional[str]
- created_at: datetime

### ShiftPlanDetail (extends ShiftPlanResponse)
- constraints: dict
- selected_devices: list[dict]
- executions: list[ShiftExecutionResponse]
- analysis_records: list[ShiftAnalysisResponse]

## 2. 转移执行 Schema

### ShiftExecutionCreate
- plan_id: int
- start_time: datetime

### ShiftExecutionResponse
- id: int
- plan_id: int
- execution_code: str
- start_time: datetime
- end_time: Optional[datetime]
- actual_shift_power: Optional[float]
- actual_cost_saving: Optional[Decimal]
- status: str
- success_rate: Optional[float]

### ShiftExecutionDetail (extends ShiftExecutionResponse)
- before_total_power: Optional[float]
- after_total_power: Optional[float]
- device_execution_details: list[dict]
- cooling_linkage_data: Optional[dict]

## 3. 转移机会 Schema

### ShiftOpportunityResponse
- id: int
- opportunity_code: str
- opportunity_name: str
- analysis_date: date
- recommended_shift_from: str
- recommended_shift_to: str
- recommended_shift_power: float
- predicted_cost_saving: Decimal
- confidence_score: float
- status: str
- priority: str

### ShiftOpportunityDetail (extends ShiftOpportunityResponse)
- recommended_devices: list[dict]
- analysis_data: dict

## 4. 约束 Schema

### ShiftConstraintCreate
- constraint_name: str
- constraint_type: str
- constraint_level: str
- device_id: Optional[int]
- circuit_id: Optional[int]
- constraint_params: dict
- priority: int
- is_mandatory: bool

### ShiftConstraintResponse
- id: int
- constraint_name: str
- constraint_type: str
- constraint_level: str
- constraint_params: dict
- priority: int
- is_enabled: bool
- is_mandatory: bool

## 5. 分析结果 Schema

### FeasibilityAnalysisRequest
- shift_date: date
- shift_from_period: str
- shift_to_period: str
- target_shift_power: float
- selected_devices: list[int]

### FeasibilityAnalysisResponse
- is_feasible: bool
- analysis_score: float
- constraint_violations: list[dict]
- warnings: list[str]
- recommendations: list[str]

### ConstraintCheckResult
- constraint_name: str
- constraint_type: str
- is_satisfied: bool
- actual_value: float
- limit_value: float
- violation_severity: str  # low/medium/high

### RiskAssessmentResponse
- risk_level: str  # low/medium/high
- risk_score: float
- risk_factors: list[dict]
- mitigation_measures: list[str]

### BenefitAnalysisResponse
- cost_saving: Decimal
- energy_saving: Decimal
- roi: float
- payback_period_days: int
- confidence: float

## 6. 设备转移潜力 Schema

### DeviceShiftPotentialResponse
- device_id: int
- device_name: str
- device_type: str
- rated_power: float
- shiftable_power: float
- shiftable_ratio: float
- is_critical: bool
- shift_priority: int
- constraints: list[str]

## 7. 制冷联动 Schema

### CoolingLinkageConfigResponse
- id: int
- config_name: str
- cooling_lag_minutes: int
- target_cop: float
- target_supply_temp: float
- max_temp_rise: float
- is_enabled: bool

### CoolingStatusResponse
- current_cooling_power: float
- current_cop: float
- supply_temp: float
- return_temp: float
- it_load_power: float
- pue_value: float

## 8. 仪表盘 Schema

### ShiftDashboardOverview
- total_plans: int
- active_plans: int
- completed_plans: int
- total_cost_saving: Decimal
- total_energy_saving: Decimal
- avg_success_rate: float
- recent_executions: list[ShiftExecutionResponse]

### ShiftRealtimeData
- current_total_power: float
- current_peak_power: float
- current_valley_power: float
- available_shift_power: float
- active_shift_plans: list[ShiftPlanResponse]

### ShiftTrendData
- date: date
- shift_count: int
- cost_saving: Decimal
- energy_saving: Decimal
- success_rate: float
"""


# ==================== 服务层设计 ====================

"""
服务层设计 (backend/app/services/load_shift/)

## 1. shift_plan_service.py
- ShiftPlanService
  - create_plan(plan_data) -> ShiftPlan
  - update_plan(plan_id, plan_data) -> ShiftPlan
  - delete_plan(plan_id) -> bool
  - get_plan(plan_id) -> ShiftPlan
  - list_plans(filters) -> list[ShiftPlan]
  - submit_for_approval(plan_id) -> ShiftPlan
  - approve_plan(plan_id, approver_id, comment) -> ShiftPlan
  - reject_plan(plan_id, approver_id, comment) -> ShiftPlan

## 2. shift_execution_service.py
- ShiftExecutionService
  - execute_plan(plan_id, executor_id) -> ShiftExecution
  - cancel_execution(execution_id) -> bool
  - get_execution_status(execution_id) -> dict
  - record_device_execution(execution_id, device_data) -> bool
  - complete_execution(execution_id) -> ShiftExecution

## 3. shift_analysis_service.py
- ShiftAnalysisService
  - analyze_feasibility(plan_data) -> FeasibilityAnalysisResponse
  - check_constraints(plan_data) -> list[ConstraintCheckResult]
  - assess_risk(plan_data) -> RiskAssessmentResponse
  - analyze_benefit(plan_data) -> BenefitAnalysisResponse
  - find_opportunities(analysis_date) -> list[ShiftOpportunity]

## 4. shift_constraint_service.py
- ShiftConstraintService
  - create_constraint(constraint_data) -> ShiftConstraint
  - update_constraint(constraint_id, constraint_data) -> ShiftConstraint
  - delete_constraint(constraint_id) -> bool
  - validate_plan_constraints(plan_data) -> list[ConstraintCheckResult]
  - get_applicable_constraints(device_id, circuit_id) -> list[ShiftConstraint]

## 5. shift_device_service.py
- ShiftDeviceService
  - get_shiftable_devices() -> list[PowerDevice]
  - get_device_shift_potential(device_id) -> DeviceShiftPotentialResponse
  - update_device_shift_config(device_id, config_data) -> DeviceShiftConfig
  - get_device_shift_history(device_id) -> list[ShiftExecution]

## 6. cooling_linkage_service.py
- CoolingLinkageService
  - get_config() -> CoolingLinkageConfig
  - update_config(config_data) -> CoolingLinkageConfig
  - get_cooling_status() -> CoolingStatusResponse
  - record_cooling_linkage(execution_id, cooling_data) -> CoolingLinkageRecord
  - calculate_cooling_impact(shift_power) -> dict

## 7. lifespan_service.py
- LifespanService
  - record_lifespan_impact(device_id, execution_id, operation_type) -> DeviceLifespanImpact
  - get_device_lifespan_impacts(device_id) -> list[DeviceLifespanImpact]
  - calculate_lifespan_loss(device_id, operation_type) -> float
  - get_maintenance_recommendations() -> list[dict]

## 8. shift_report_service.py
- ShiftReportService
  - generate_savings_report(start_date, end_date) -> dict
  - generate_monthly_report(year, month) -> dict
  - generate_yearly_report(year) -> dict
  - export_excel(report_data) -> BytesIO
  - export_pdf(report_data) -> BytesIO

## 9. shift_dashboard_service.py
- ShiftDashboardService
  - get_overview() -> ShiftDashboardOverview
  - get_realtime_data() -> ShiftRealtimeData
  - get_trend_data(start_date, end_date) -> list[ShiftTrendData]
"""


# ==================== 算法模块设计 ====================

"""
算法模块设计 (backend/app/services/load_shift/algorithms/)

## 1. constraint_checker.py
- ConstraintChecker
  - check_power_constraints(plan_data) -> list[ConstraintCheckResult]
  - check_time_constraints(plan_data) -> list[ConstraintCheckResult]
  - check_device_constraints(plan_data) -> list[ConstraintCheckResult]
  - check_cooling_constraints(plan_data) -> list[ConstraintCheckResult]
  - check_safety_constraints(plan_data) -> list[ConstraintCheckResult]
  - check_electrical_constraints(plan_data) -> list[ConstraintCheckResult]

## 2. benefit_calculator.py
- BenefitCalculator
  - calculate_cost_saving(shift_power, from_period, to_period) -> Decimal
  - calculate_energy_saving(shift_power, duration) -> Decimal
  - calculate_roi(cost_saving, investment) -> float
  - calculate_payback_period(cost_saving, investment) -> int

## 3. risk_assessor.py
- RiskAssessor
  - assess_overall_risk(plan_data) -> RiskAssessmentResponse
  - identify_risk_factors(plan_data) -> list[dict]
  - calculate_risk_score(risk_factors) -> float
  - suggest_mitigation_measures(risk_factors) -> list[str]

## 4. opportunity_finder.py
- OpportunityFinder
  - find_daily_opportunities(analysis_date) -> list[ShiftOpportunity]
  - analyze_peak_valley_diff(date) -> dict
  - recommend_shift_devices(target_power) -> list[dict]
  - calculate_confidence_score(opportunity_data) -> float

## 5. cooling_calculator.py
- CoolingCalculator
  - calculate_cooling_load(it_power, ambient_temp) -> float
  - calculate_cop(cooling_power, it_power) -> float
  - calculate_supply_temp(cooling_load, cop) -> float
  - estimate_cooling_lag_impact(shift_power, lag_minutes) -> dict

## 6. lifespan_calculator.py
- LifespanCalculator
  - calculate_startup_loss(device_type) -> float
  - calculate_shutdown_loss(device_type) -> float
  - calculate_load_change_loss(device_type, load_change) -> float
  - estimate_maintenance_date(device_id, cumulative_loss) -> date
"""


# ==================== 前端页面设计 ====================

"""
前端页面设计 (frontend/src/views/energy/shift/)

## 1. 转移计划管理
- ShiftPlanList.vue          # 计划列表页
- ShiftPlanCreate.vue        # 创建计划页
- ShiftPlanDetail.vue        # 计划详情页
- ShiftPlanEdit.vue          # 编辑计划页

## 2. 转移机会分析
- ShiftOpportunityList.vue   # 机会列表页
- ShiftOpportunityDetail.vue # 机会详情页
- ShiftAnalysis.vue          # 分析工具页

## 3. 执行监控
- ShiftExecutionList.vue     # 执行记录列表
- ShiftExecutionDetail.vue   # 执行详情页
- ShiftExecutionMonitor.vue  # 实时监控页

## 4. 配置管理
- ShiftConstraintConfig.vue  # 约束配置页
- CoolingLinkageConfig.vue   # 制冷联动配置页
- DeviceShiftConfig.vue      # 设备转移配置页

## 5. 报表与统计
- ShiftReportSavings.vue     # 收益报表页
- ShiftReportMonthly.vue     # 月度报表页
- ShiftReportYearly.vue      # 年度报表页

## 6. 仪表盘
- ShiftDashboard.vue         # 转移仪表盘
  - 概览卡片
  - 实时数据
  - 趋势图表
  - 最近执行记录
"""


# ==================== 前端组件设计 ====================

"""
前端组件设计 (frontend/src/components/energy/shift/)

## 1. 计划相关组件
- ShiftPlanForm.vue          # 计划表单组件
- ShiftPlanCard.vue          # 计划卡片组件
- ShiftPlanTimeline.vue      # 计划时间线组件
- DeviceSelector.vue         # 设备选择器组件

## 2. 分析相关组件
- ConstraintCheckResult.vue  # 约束检查结果组件
- RiskAssessment.vue         # 风险评估组件
- BenefitAnalysis.vue        # 收益分析组件
- OpportunityCard.vue        # 机会卡片组件

## 3. 执行相关组件
- ExecutionProgress.vue      # 执行进度组件
- DeviceExecutionTable.vue   # 设备执行表格组件
- CoolingLinkageChart.vue    # 制冷联动图表组件

## 4. 图表组件
- ShiftPowerChart.vue        # 转移功率图表
- CostSavingChart.vue        # 成本节省图表
- EfficiencyTrendChart.vue   # 效率趋势图表
- PeakValleyChart.vue        # 峰谷对比图表

## 5. 配置组件
- ConstraintEditor.vue       # 约束编辑器组件
- CoolingConfigForm.vue      # 制冷配置表单组件
"""


# ==================== 数据库迁移 ====================

"""
数据库迁移 (backend/alembic/versions/)

创建迁移文件:
```bash
cd backend
alembic revision --autogenerate -m "add load shift tables"
alembic upgrade head
```

迁移内容:
- 创建 shift_plans 表
- 创建 shift_executions 表
- 创建 shift_constraints 表
- 创建 shift_opportunities 表
- 创建 shift_analysis_records 表
- 创建 cooling_linkage_configs 表
- 创建 cooling_linkage_records 表
- 创建 device_lifespan_impacts 表
- 添加外键约束
- 添加索引
"""


# ==================== 权限设计 ====================

"""
权限设计

## 角色权限
- admin: 所有权限
- operator: 创建/编辑/执行计划，查看报表
- viewer: 仅查看权限

## 权限点
- shift:plan:create      # 创建计划
- shift:plan:edit        # 编辑计划
- shift:plan:delete      # 删除计划
- shift:plan:approve     # 审批计划
- shift:plan:execute     # 执行计划
- shift:config:edit      # 编辑配置
- shift:report:view      # 查看报表
- shift:report:export    # 导出报表
"""
