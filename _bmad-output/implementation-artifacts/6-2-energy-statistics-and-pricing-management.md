# Story 6.2: 能耗统计与电价管理

Status: ready-for-dev

## Story

As a 能源管理员,
I want 查看能耗统计和管理电价策略,
So that 我可以分析电费构成并优化用电成本。

## Acceptance Criteria (验收标准)

1. **AC-1: 日/月能耗统计适配真实数据** — 现有 `GET /energy/statistics/daily` 和 `/statistics/monthly` 端点已有"无数据时 fallback 到模拟"逻辑。需增加 `settings.simulation_enabled` 判断：`false` 时查询真实 EnergyDaily/EnergyMonthly 表，`true` 时保留现有模拟逻辑。响应新增 `data_source` 字段
2. **AC-2: 能耗汇总使用真实电价** — 现有 `GET /energy/statistics/summary` 端点在有真实数据时，peak_cost/normal_cost/valley_cost 使用硬编码乘数（1.2/0.8/0.4）。需改为调用 PricingService 获取真实电价计算分段电费
3. **AC-3: 能耗趋势适配真实数据** — 现有 `GET /energy/statistics/trend` 端点始终返回模拟数据。需增加真实数据查询逻辑（按 granularity 查询 EnergyHourly/EnergyDaily/EnergyMonthly），无数据时 fallback 到模拟
4. **AC-4: 同环比对比适配真实数据** — 现有 `GET /energy/statistics/comparison` 端点始终返回模拟数据。需增加真实数据查询逻辑，根据 comparison_type 和 period 计算本期/上期时间范围，查询 EnergyDaily 聚合
5. **AC-5: 电费统计使用真实电价** — 现有 `GET /energy/cost/daily` 和 `/cost/monthly` 端点在有真实数据时使用硬编码乘数。需改为调用 PricingService 获取真实电价
6. **AC-6: 数据导出端点已存在** — 现有 `GET /energy/export/daily` 和 `/export/monthly` 端点已实现，无需新增
7. **AC-7: 能耗数据聚合定时任务** — 新增定时任务：每小时聚合 PointHistory → EnergyHourly，每日聚合 EnergyHourly → EnergyDaily（含峰谷平分段），每月聚合 EnergyDaily → EnergyMonthly。仅在 `simulation_enabled=false` 时运行
8. **AC-8: 前端数据源标识** — statistics.vue 显示数据来源标识（"实时数据"/"模拟数据"），与 Story 6-1 的 monitor.vue 保持一致
9. **AC-9: 电价配置已完整** — config.vue 的电价配置 tab 已存在且调用 `/v1/energy/pricing` 系列 API（energy.py 中已注册），无需修改
10. **AC-10: 后端测试** — 测试统计端点（真实数据模式和模拟模式）、测试电费计算、测试数据聚合逻辑
11. **AC-11: 前端构建验证** — `npm run build` 构建成功

## Tasks / Subtasks (任务分解)

- [ ] Task 1: 后端 — 提取确定性模拟辅助函数 (AC: #1-#5)
  - [ ] 1.1 新建 `backend/app/utils/deterministic.py`，将 energy.py 中的以下模块级函数移入：
    - `_deterministic_ratio(seed, min_val, max_val) -> float`（energy.py 第58行）
    - `_deterministic_offset(seed, amplitude) -> float`（energy.py 第72行）
    - `_device_seed(device_id, base_seed) -> int`（energy.py 第84行）
    - `_time_seed(dt, idx) -> int`（energy.py 第91行）
    - `_date_seed(d, idx) -> int`（energy.py 第98行）
  - [ ] 1.2 修改 energy.py 中的导入，改为 `from ...utils.deterministic import ...`
  - [ ] 1.3 确保 `backend/app/utils/__init__.py` 存在
  - [ ] 1.4 运行现有测试确认无回归

- [ ] Task 2: 后端 — Schema 适配 (AC: #1-#5)
  - [ ] 2.1 在 `backend/app/schemas/energy.py` 中：
    - EnergyStat 新增 `data_source: Optional[str] = None`
    - EnergyTrend 新增 `data_source: Optional[str] = None`
    - EnergyComparison 新增 `data_source: Optional[str] = None`
  - [ ] 2.2 不修改 EnergyDaily model（不加分段电费字段），日电费分段在查询时实时计算

- [ ] Task 3: 后端 — 修改现有统计端点适配真实数据 (AC: #1-#5)
  - [ ] 3.1 修改 `get_daily_statistics()`（energy.py 第847行）：
    - 在函数开头读取 `settings = _get_energy_settings()`
    - `simulation_enabled == True` 时：直接走现有模拟逻辑
    - `simulation_enabled == False` 时：查询 EnergyDaily 表，无数据返回空列表
    - 在 ResponseModel 中附加 data_source
  - [ ] 3.2 修改 `get_monthly_statistics()`（energy.py 第901行）：同上模式
  - [ ] 3.3 修改 `get_energy_summary()`（energy.py 第956行）：
    - 真实数据模式下，替换硬编码电价乘数（第1026-1028行的 `peak * 1.2` 等）
    - 改为调用 `PricingService(db).get_all_prices()` 获取真实电价
    - 注意：PricingService 返回的 key 是 `normal`（不是 `flat`），与 EnergyDaily 的 `normal_energy` 字段一致
    - 使用 `if value is not None` 判断（避免 falsy 0.0 陷阱）
  - [ ] 3.4 修改 `get_energy_trend()`（energy.py 第1037行）：
    - 当前始终返回模拟数据，无 simulation_enabled 判断
    - 真实数据模式下：
      - `granularity='daily'`: 查询 EnergyDaily，time_label = stat_date.strftime("%Y-%m-%d")
      - `granularity='monthly'`: 查询 EnergyMonthly，time_label = f"{stat_year}-{stat_month:02d}"
      - `granularity='hourly'`: 查询 EnergyHourly，time_label = stat_time.strftime("%Y-%m-%d %H:00")
    - 无数据时 fallback 到现有模拟逻辑
  - [ ] 3.5 修改 `get_energy_comparison()`（energy.py 第1115行）：
    - 当前始终返回模拟数据
    - 真实数据模式下：
      - `period='month'`: 本期 = 本月1日~今日，上期 = 上月同日期范围（环比）或去年同月（同比）
      - `period='week'`: 本期 = 本周一~今日，上期 = 上周同日期范围
      - `period='day'`: 本期 = 今日，上期 = 昨日（环比）或去年今日（同比）
      - 查询 EnergyDaily 聚合 SUM(total_energy) 等
      - 计算 change_rate = (current - previous) / previous（previous 为 0 时 rate = 0）
    - 无数据时 fallback 到现有模拟逻辑
  - [ ] 3.6 修改 `get_daily_cost()`（energy.py 第1188行）：
    - 替换硬编码电价乘数，调用 PricingService 获取真实电价
  - [ ] 3.7 修改 `get_monthly_cost()`（energy.py 第1245行）：
    - EnergyMonthly 已有 peak_cost/normal_cost/valley_cost 字段，直接使用
    - 仅在模拟模式下使用硬编码乘数

- [ ] Task 4: 后端 — 能耗数据聚合定时任务 (AC: #7)
  - [ ] 4.1 新建 `backend/app/services/energy_aggregator.py`，封装聚合逻辑：
    - `async def aggregate_hourly(db)`:
      - 查询所有启用的 PowerDevice，获取其 `power_point_id`
      - 从 PointHistory 查询上一个整点到当前整点的数据
      - PointHistory 字段：`point_id`(Int), `value`(Float, 瞬时功率kW), `recorded_at`(DateTime), `quality`(Int, 0=好/1=不确定/2=坏)
      - 过滤 quality != 2（排除坏数据）
      - 计算 `total_energy = AVG(value) * 1.0`（平均功率kW × 1小时 = kWh）
      - 计算 avg_power, max_power, min_power
      - 写入 EnergyHourly（幂等：先检查同 device_id + stat_time 记录）
    - `async def aggregate_daily(db)`:
      - 从 EnergyHourly 聚合昨日数据到 EnergyDaily
      - 峰谷平分段：查询 ElectricityPricing 获取时段配置
      - **映射关系**：ElectricityPricing.period_type `flat` → EnergyDaily.`normal_energy`，`sharp`+`peak` → `peak_energy`，`valley`+`deep_valley` → `valley_energy`
      - energy_cost = peak_energy × peak_price + normal_energy × flat_price + valley_energy × valley_price
      - pue：从 PUEHistory 取当日平均值
      - 写入 EnergyDaily（幂等）
    - `async def aggregate_monthly(db)`:
      - 从 EnergyDaily 聚合上月数据到 EnergyMonthly
      - peak_cost/normal_cost/valley_cost 从分段电量 × 电价计算
      - 写入 EnergyMonthly（幂等）
  - [ ] 4.2 在 `backend/app/main.py` 的 `lifespan()` 中注册定时任务：
    - 小时聚合循环：`await asyncio.sleep(10)` 首次执行，然后每 3600 秒循环
    - 日聚合循环：启动时补齐缺失天数，然后每 86400 秒循环
    - 月聚合循环：启动时补齐缺失月份，然后每 86400 秒循环（内部判断是否月初）
    - 仅在 `settings.simulation_enabled == False` 时启动
    - 使用 try/except + rollback 保护
    - 每个循环函数使用独立的 `async_session()` 上下文

- [ ] Task 5: 前端 — statistics.vue 数据源标识 (AC: #8)
  - [ ] 5.1 在 statistics.vue 的筛选条件区域添加数据来源 Tag（参考 monitor.vue）
  - [ ] 5.2 处理 null/undefined 值，使用 `value !== null && value !== undefined` 而非 `value || 0`

- [ ] Task 6: 后端测试 (AC: #10)
  - [ ] 6.1 新建 `backend/tests/test_energy_statistics.py`
  - [ ] 6.2 新建 `backend/tests/test_energy_aggregator.py`

- [ ] Task 7: 前端构建验证 (AC: #11)
  - [ ] 7.1 运行 `npm run build` 确认构建成功

## Dev Notes (开发注意事项)

### 对抗性审查修复（4 CRITICAL + 7 HIGH）

**[C1] 端点已存在，不新增** — energy.py 已有 80+ 个端点，包括 `/statistics/daily`(第847行)、`/statistics/monthly`(第901行)、`/statistics/summary`(第956行)、`/statistics/trend`(第1037行)、`/statistics/comparison`(第1115行)、`/cost/daily`(第1188行)、`/cost/monthly`(第1245行)、`/export/daily`(第1898行)、`/export/monthly`(第2004行)、`/pricing`(第1306行)。**不新增端点，只修改现有端点的内部实现**。

**[C2] 辅助函数提取** — `_deterministic_ratio` 等函数定义在 energy.py（API 路由文件）中，无法从 services 层导入（会循环依赖）。Task 1 将其提取到 `backend/app/utils/deterministic.py`。

**[C3] 电价时段映射** — ElectricityPricing.period_type 使用 `flat`（平段），但 EnergyDaily/EnergyMonthly 的字段名是 `normal_energy`/`normal_cost`。PricingService 内部已有别名映射（`flat` → `normal`）。聚合时：`flat` 时段电量写入 `normal_energy`。查询时：PricingService.get_all_prices() 返回 `normal` key。

**[C4] 电价路由已存在** — 前端调用 `/v1/energy/pricing`，energy.py 中已有 `/pricing` CRUD 端点（第1306-1381行）。独立的 `pricing_router`（`/v1/pricing/xxx`）是供内部服务使用的。无需修改。

**[H1/H2] 硬编码电价替换** — summary(第1026-1028行)、cost/daily(第1236-1238行)、comparison(第1133/1144行) 中的 `peak * 1.2`、`normal * 0.8`、`valley * 0.4` 替换为 PricingService 真实电价。

**[H3] 导出端点已存在** — export/daily(第1898行) 和 export/monthly(第2004行) 已实现。前端传 `format='excel'`，后端参数也是 `format: str = Query("excel")`，已匹配。

**[H4/H5] trend/comparison 适配真实数据** — 这两个端点当前始终返回模拟数据，需增加真实数据查询逻辑。

**[H6] PointHistory 字段确认** — `value`(Float, 瞬时功率kW), `recorded_at`(DateTime), `quality`(Int), `point_id`(Int)。使用 `PowerDevice.power_point_id` 关联。

**[H7] EnergyDaily 不加分段电费字段** — 避免 migration，日电费分段在查询时实时计算。

### 关键代码位置

| 端点 | 行号 | 当前状态 | 需要修改 |
|------|------|---------|---------|
| `/statistics/daily` | 847 | 有真实数据查询+模拟fallback | 增加 simulation_enabled 判断、data_source |
| `/statistics/monthly` | 901 | 有真实数据查询+模拟fallback | 同上 |
| `/statistics/summary` | 956 | 有真实数据查询，但电费用硬编码 | 替换硬编码电价为 PricingService |
| `/statistics/trend` | 1037 | 始终模拟 | 增加真实数据查询 |
| `/statistics/comparison` | 1115 | 始终模拟 | 增加真实数据查询 |
| `/cost/daily` | 1188 | 有真实数据查询，但电费用硬编码 | 替换硬编码电价 |
| `/cost/monthly` | 1245 | 有真实数据查询，但电费用硬编码 | 替换硬编码电价 |
| `/export/daily` | 1898 | 已实现 | 无需修改 |
| `/export/monthly` | 2004 | 已实现 | 无需修改 |
| `/pricing` CRUD | 1306-1381 | 已实现 | 无需修改 |

### 模式参考

- **模拟/真实切换**: 参考 Story 6-1 的 `get_current_pue()` 和 `get_power_summary()`，使用 `settings.simulation_enabled`
- **falsy 0.0 陷阱**: 使用 `if value is not None` 而非 `value or fallback`
- **定时任务模式**: 参考 `main.py` 中已有的 PUE 历史写入任务
- **try/except + rollback**: 参考 `pue_calculator.py` 的 `write_pue_history`
- **settings 属性名**: `settings.simulation_enabled`（小写）

### 文件修改清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/utils/deterministic.py` | 新建 | 提取确定性模拟辅助函数 |
| `backend/app/utils/__init__.py` | 新建(如不存在) | 空文件 |
| `backend/app/api/v1/energy.py` | 修改 | 修改 7 个现有端点，导入改为 utils |
| `backend/app/schemas/energy.py` | 修改 | 新增 data_source 字段 |
| `backend/app/services/energy_aggregator.py` | 新建 | 能耗数据聚合服务 |
| `backend/app/main.py` | 修改 | 注册聚合定时任务 |
| `frontend/src/views/energy/statistics.vue` | 修改 | 添加数据源标识 Tag |
| `backend/tests/test_energy_statistics.py` | 新建 | 统计端点测试 |
| `backend/tests/test_energy_aggregator.py` | 新建 | 聚合逻辑测试 |
