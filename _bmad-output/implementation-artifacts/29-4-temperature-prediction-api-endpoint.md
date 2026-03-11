# Story 29.4: 温度预测 API 端点

Status: done

## Story

As a 前端开发人员,
I want 后端提供温度预测和热参数查询的 REST API,
So that 前端可以展示温度预测数据。

## 依赖

- Story 29.1（数据模型）— done
- Story 29.2（RC 模型）— done
- Story 29.3（THM 模式）— done

## Acceptance Criteria

1. Given 温度预测服务已实现（Story 29.2 ThermalModel + Story 29.3 THM）
   When 前端调用温度预测 API
   Then `POST /api/v1/precool/zones/{zone_id}/predict` 端点:
   - 接收请求体 `{q_cool_schedule: list[float] | null, hours: float}`
   - hours 范围 0.5~24.0，默认 1.0（Pydantic `Field(ge=0.5, le=24.0, default=1.0)` 自动校验，超限返回 422）
   - q_cool_schedule 为制冷功率计划（kW），如果不为 null，长度必须等于 `int(hours × 12)`（5 分钟一步），长度不匹配时返回 422 + 详细错误信息；如果为 null 则使用当前制冷功率
   - 调用 `ThermalModel().predict_temperature(zone_id, hours, q_cool_schedule)` 获取预测结果
   - 成功时返回 `{code: 200, message: "success", data: {zone_id, predicted_temp, prediction_horizon_min, temperature_trajectory, time_steps, model_version, data_quality}}`
   - ThermalModel 返回 error 时的处理策略:
     - `zone_not_found` → 404 Not Found
     - `parameters_not_calibrated` → **THM 兜底**: 调用 `calculate_shiftable_power_for_zone(zone_id, session)` 获取 THM 估算结果，将 THM 结果封装为预测响应格式返回（`predicted_temp` 使用 T_current_max, `temperature_trajectory` 为空列表, `model_version` 设为 "THM-fallback", `data_quality` 设为 null），同时在 data 中附加 `thm_result` 字段包含完整 THM 输出
     - `insufficient_data` / `sensor_offline` / `data_fetch_failed` / `insufficient_history` → 503 Service Unavailable + error details
     - `numerical_instability` / `invalid_parameters` / `invalid_q_cool_schedule` / `temperature_out_of_bounds` → 422 Unprocessable Entity + error details
     - 其他 error → 500 Internal Server Error
   - 权限: operator+ 角色（`require_role(["admin", "operator"])`）

2. And `GET /api/v1/precool/zones/{zone_id}/parameters` 端点:
   - 返回指定制冷区域的 R/C 标定参数历史
   - 查询 `thermal_parameters` 表，按 `created_at DESC` 排序
   - 支持分页: `skip` (int, 默认 0, ge=0), `limit` (int, 默认 20, ge=1, le=100)
   - 返回 `{code: 200, message: "success", data: {items: list[ThermalParameterOut], total: int}}`
   - `ThermalParameterOut` schema 字段: id, cooling_zone_id, thermal_R (Optional[float]), thermal_C (Optional[float]), fitting_r_squared (Optional[float]), fitting_method (Optional[str]), sample_count (Optional[int]), calibrated_at (Optional[datetime]), is_active (bool), created_at (datetime)
   - zone_id 不存在时返回空列表（不报 404，因为可能是新建区域尚未标定）
   - 权限: operator+ 角色

3. And `GET /api/v1/precool/zones/{zone_id}/validation` 端点:
   - 返回模型验证报告
   - 查询 `temperature_prediction_logs` 表最近 7 天数据，**仅使用已回填 actual_temp 的记录**（`actual_temp IS NOT NULL`）
   - mae_1h: 筛选 `prediction_horizon_min <= 60` 的记录，计算 `mean(abs(deviation))`
   - mae_3h: 筛选 `prediction_horizon_min <= 180` 的记录，计算 `mean(abs(deviation))`
   - max_deviation: 所有有效记录中 `max(abs(deviation))`
   - sample_count: 有效记录总数
   - 如果无有效记录，所有指标返回 null，sample_count 返回 0
   - 返回 `{code: 200, message: "success", data: {zone_id, mae_1h, mae_3h, max_deviation, sample_count, period_days: 7}}`
   - 权限: operator+ 角色

4. And `GET /api/v1/precool/dashboard` 端点:
   - 返回预冷仪表盘聚合数据
   - 查询所有 CoolingZone（一次性批量查询，非逐条），对每个 zone 聚合:
     - zone_id (int), zone_name (str)
     - current_temp (Optional[float]): 最近 5 分钟最热机柜进风温度（复用 Story 29.3 的 T_current_max 查询链路: CoolingZoneCabinet → Cabinet → CabinetTemperatureSensor(inlet) → PointHistory），如果无数据则为 null
     - headroom (Optional[float]): 温度裕度 = 27.0 - current_temp，current_temp 为 null 时 headroom 也为 null
     - model_mode (str): "THM" 或 "TCL"（查询 thermal_parameters 表是否存在 `cooling_zone_id=zone_id AND is_active=True` 的记录）
     - shiftable_ratio (Optional[float]): 调用 `calculate_shiftable_power_for_zone(zone_id, session)` 获取，如果返回 error 则为 null
   - status_summary: `{total_zones: int, thm_zones: int, tcl_zones: int, offline_zones: int}`
     - offline_zones: current_temp 为 null 的 zone 数量（即无最近 5 分钟温度数据）
   - today_savings: 固定返回 0.0（占位，后续 Story 31 实现预冷节能统计）
   - Dashboard 整体超时保护: 单个 zone 计算超时（> 5 秒）时跳过该 zone，记录警告日志
   - 返回 `{code: 200, message: "success", data: {zones: list[DashboardZone], status_summary: dict, today_savings: float}}`
   - 权限: operator+ 角色

5. And 所有端点遵循项目现有 API 规范:
   - JWT 认证（通过 `get_current_user` 依赖注入）
   - RBAC 权限控制（`require_role(["admin", "operator"])` 表示 operator+ 角色）
   - 响应格式: `{code: int, message: str, data: any}`
   - 异常处理: 使用 try/except 包裹业务逻辑，捕获未预期异常返回 `{code: 500, message: "内部错误"}`
   - 路由注册: `api_router.include_router(precool_router, prefix="/precool", tags=["预冷系统"])`

6. And **Pydantic Schema 定义** (`backend/app/schemas/precool.py`):
   - `PredictRequest(BaseModel)`: q_cool_schedule (Optional[List[float]] = None), hours (float = Field(default=1.0, ge=0.5, le=24.0))
   - `PredictResponse(BaseModel)`: zone_id (int), predicted_temp (float), prediction_horizon_min (int), temperature_trajectory (List[float]), time_steps (List[str]), model_version (str), data_quality (Optional[dict] = None), thm_result (Optional[dict] = None)
   - `ThermalParameterOut(BaseModel)`: id (int), cooling_zone_id (int), thermal_R (Optional[float]), thermal_C (Optional[float]), fitting_r_squared (Optional[float]), fitting_method (Optional[str]), sample_count (Optional[int]), calibrated_at (Optional[datetime]), is_active (bool), created_at (datetime); `class Config: from_attributes = True`
   - `ValidationReport(BaseModel)`: zone_id (int), mae_1h (Optional[float]), mae_3h (Optional[float]), max_deviation (Optional[float]), sample_count (int), period_days (int = 7)
   - `DashboardZone(BaseModel)`: zone_id (int), zone_name (str), current_temp (Optional[float]), headroom (Optional[float]), model_mode (str), shiftable_ratio (Optional[float])
   - `DashboardResponse(BaseModel)`: zones (List[DashboardZone]), status_summary (dict), today_savings (float = 0.0)

## 涉及文件

- 新建 `backend/app/api/v1/precool.py` — API 路由（4 个端点）
- 新建 `backend/app/schemas/precool.py` — Pydantic schemas（6 个 schema）
- 修改 `backend/app/api/v1/__init__.py` — 注册 precool 路由
- 新建 `backend/tests/api/test_precool.py` — API 测试

## 技术说明

- 温度预测调用 `ThermalModel().predict_temperature()` —— Story 29.2 已实现
- THM 兜底调用 `calculate_shiftable_power_for_zone()` —— Story 29.3 在 `datacenter_shift_strategy.py` 中已实现
- Dashboard 端点: zone 数量通常 < 20，逐个计算可接受；单 zone 超时保护避免整体阻塞
- 验证报告: mae_1h 使用 `prediction_horizon_min <= 60` 筛选，mae_3h 使用 `prediction_horizon_min <= 180` 筛选
- `ThermalModel` 内部使用 `async_session()` 创建自己的数据库会话，不需要外部传入 session
- `calculate_shiftable_power_for_zone` 需要外部传入 `AsyncSession`，Dashboard 端点需要从 `get_db` 获取

## Tasks

- [x] 1. 创建 Pydantic schemas (`backend/app/schemas/precool.py`)
- [x] 2. 创建 API 路由 (`backend/app/api/v1/precool.py`)
- [x] 3. 注册路由到 `__init__.py`
- [x] 4. 编写测试 (`backend/tests/api/test_precool.py`)
- [x] 5. 运行测试验证 — 17/17 通过
