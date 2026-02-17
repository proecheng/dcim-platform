# Story 7.6: 容量趋势预测

Status: ready-for-dev

## Story

As a 运维主管,
I want 查看容量趋势预测和扩容建议,
So that 我可以提前规划机房扩容，避免容量不足影响业务。

## FR 追溯

- FR61: 运维主管可以查看容量趋势预测和扩容建议

## Acceptance Criteria

1. Given 系统已积累容量历史数据
   When 运维主管查看容量趋势页面
   Then 显示空间/电力/制冷/承重四维容量的历史趋势图（支持按 hour/day/week/month 粒度聚合）

2. Given 运维主管选择预测周期（3/6/12 个月）
   When 查看容量预测
   Then 基于历史数据线性回归预测未来容量使用率，预测结果附带置信区间（上界/下界）

3. Given 预测容量将在 N 个月内超过阈值（默认 80%）
   When 系统检测到超阈值风险
   Then 自动生成扩容建议，包含具体的资源需求量和预估超阈值时间点

4. Given 系统刚部署或历史数据不足
   When 运维主管查看趋势/预测
   Then 趋势端点返回已有数据（可能为空数组），预测端点返回 demo 预测数据并标注 `is_demo: true`

## 现有代码分析

### 已有实现（直接复用）

| 层级 | 文件 | 内容 |
|------|------|------|
| CapacityHistory 模型 | `backend/app/models/capacity.py` L147-159 | 含 capacity_type, reference_id, reference_name, total_value, used_value, usage_rate, recorded_at |
| CapacityType 枚举 | `backend/app/models/capacity.py` L14-20 | space/power/cooling/weight/network |
| CapacityTrend Schema | `backend/app/schemas/capacity.py` L237-241 | timestamps: List[datetime], values: List[float], capacity_type: CapacityType |
| 前端 getCapacityTrend | `frontend/src/api/modules/capacity.ts` L391-404 | GET /v1/capacity/trend, params: type/start_time/end_time/interval, 返回 {timestamps, total, used, usage_rate} |
| 前端 getCapacityForecast | `frontend/src/api/modules/capacity.ts` L406-417 | GET /v1/capacity/forecast, params: type/days, 返回 {timestamps, predicted_usage, confidence_upper, confidence_lower} |
| 负荷预测参考 | `backend/app/services/forecasting.py` L1-80 | LoadForecaster 使用 numpy 做负荷预测，可参考模式 |
| 容量统计端点 | `backend/app/api/v1/capacity.py` L1040-1130 | get_capacity_statistics 聚合四维容量数据 |
| 数据模拟器 | `backend/app/services/simulator.py` | 每5秒写入 PointHistory，但不写 CapacityHistory |

### 缺失实现（需新增）

| 缺失项 | 说明 |
|--------|------|
| `GET /v1/capacity/trend` 端点 | 后端无此端点，前端已有调用函数 |
| `GET /v1/capacity/forecast` 端点 | 后端无此端点，前端已有调用函数 |
| 容量历史数据填充 | CapacityHistory 表无数据写入逻辑，需在 simulator 中增加容量快照 |
| 前端趋势/预测标签页 | capacity/index.vue 无趋势/预测 tab，现有 tab: 空间/电力/制冷/承重/上架评估/容量预警 |
| 预测 Schema | schemas/capacity.py 无 forecast 响应 Schema |
| 扩容建议 Schema | 无扩容建议数据结构 |

### 关键设计决策

#### 1. 前后端数据结构对齐

前端 `getCapacityTrend` 期望返回：
```json
{ "timestamps": string[], "total": number[], "used": number[], "usage_rate": number[] }
```

现有 `CapacityTrend` Schema 只有 `timestamps + values + capacity_type`，不匹配。
**决策**: 新建 `CapacityTrendResponse` Schema 对齐前端期望，保留现有 `CapacityTrend` 不动。

前端 `getCapacityForecast` 期望返回：
```json
{ "timestamps": string[], "predicted_usage": number[], "confidence_upper": number[], "confidence_lower": number[] }
```

**决策**: 新建 `CapacityForecastResponse` Schema。

#### 2. 容量历史数据来源

CapacityHistory 按 reference_id 存储单条容量记录的快照。趋势端点需要聚合级别的数据。
**决策**: 在 simulator.py 中增加容量快照逻辑，每 60 秒将四维容量表的聚合值写入 CapacityHistory（reference_id=0 表示全局聚合）。趋势端点查询 reference_id=0 的记录。
**[C3 修复]**: 容量快照必须在**独立的 async_session()** 中执行，与点位采集事务隔离。在 simulator 的 while 循环中用独立计数器，每 12 次循环后单独调用 `_snapshot_capacity_history()` 方法，该方法使用自己的 session 和 try/except，失败不影响点位采集。

#### 3. 线性回归实现

使用 numpy 的 `np.polyfit(x, y, 1)` 做一次线性回归。置信区间基于残差标准差计算：
- `predicted = slope * x + intercept`
- `residual_std = np.std(y - predicted_y)`
- `confidence_upper = predicted + 1.96 * residual_std`
- `confidence_lower = predicted - 1.96 * residual_std`
- **[H2 备注]**: 常数宽度置信带对远端预测会低估不确定性，但对内部运维工具可接受。前端 tooltip 标注"预测仅供参考"。

**[M5 修复]** 数据充分性阈值：预测 N 天至少需要 30 个日粒度数据点（约 1 个月历史）。不足时生成 demo 预测数据，标注 `is_demo: true`。

#### 4. 扩容建议生成

当预测 usage_rate 在预测周期内超过阈值（默认 80%）时：
- 计算超阈值时间点（线性插值）
- 计算超阈值时的资源缺口 = predicted_used - threshold_value
- 生成建议文本

#### 5. [H1 修复] 前端 forecast 参数：months vs days

前端 `getCapacityForecast` 参数为 `days?: number`。AC2 要求"3/6/12 个月"。
**决策**: 保持后端接受 `days` 参数（兼容前端已有签名），前端传 `days=90/180/365`。前端选择器显示"3个月/6个月/12个月"，映射为天数传给后端。不修改前端已有 API 函数签名。

#### 6. [H4 修复] type 参数限制

`CapacityType` 枚举包含 `network` 但无 NetworkCapacity 表。
**决策**: 趋势/预测端点的 `type` 参数使用 `Literal["space", "power", "cooling", "weight"]` 限制，不接受 `network`。

## Tasks / Subtasks

### Task 1: 后端 — Schema 定义 (AC: #1, #2, #3)

- [ ] 1.1 在 `schemas/capacity.py` 新增 `CapacityTrendResponse`：timestamps(List[str]), total(List[float]), used(List[float]), usage_rate(List[float])
- [ ] 1.2 新增 `CapacityForecastResponse`：timestamps(List[str]), predicted_usage(List[float]), confidence_upper(List[float]), confidence_lower(List[float]), is_demo(bool), expansion_suggestions(List[ExpansionSuggestion])
- [ ] 1.3 新增 `ExpansionSuggestion`：capacity_type(str), current_usage_rate(float), predicted_exceed_date(str), predicted_usage_rate(float), resource_gap(str), suggestion(str)

### Task 2: 后端 — 容量历史数据填充 (AC: #1, #4)

- [ ] 2.1 在 `simulator.py` 增加 `_snapshot_capacity_history()` 独立方法
  - **[C3]** 使用独立的 `async_session()` 执行，不与点位采集共享事务
  - 聚合 SpaceCapacity/PowerCapacity/CoolingCapacity/WeightCapacity 四表的 total/used/usage_rate
  - 写入 CapacityHistory（reference_id=0, reference_name="全局聚合"）
  - 每 60 秒执行一次（在 while 循环中用计数器，每 12 次循环后调用）
  - 整个方法包裹在 try/except 中，失败仅 logger.warning，不影响主循环
- [ ] 2.2 在 `models/capacity.py` 添加 CapacityHistory 复合索引
  - **[H3]** `Index('ix_capacity_history_type_time', 'capacity_type', 'recorded_at')`
  - 无需 Alembic 迁移（SQLite 开发环境，表会自动重建）
- [ ] 2.3 确认 CapacityHistory 已在 models/__init__.py 导出（已确认存在）

### Task 3: 后端 — 趋势端点 GET /capacity/trend (AC: #1)

- [ ] 3.1 在 `capacity.py` 新增 `GET /trend` 端点
  - 参数: type(可选, 默认 space, **[H4] 限制为 Literal["space","power","cooling","weight"]**), start_time(可选), end_time(可选), interval(可选)
  - **[M2 修复]** interval 默认值根据时间范围自动选择：≤2天→hour, ≤30天→day, ≤180天→week, >180天→month
  - 查询 CapacityHistory WHERE capacity_type=type AND reference_id=0 AND recorded_at BETWEEN start_time AND end_time
  - **[C1 修复]** week 聚合不使用 SQLite strftime %W，改为在 Python 层处理：从 DB 取 day 粒度数据后按 `isocalendar()` 重新分组
  - 按 interval 聚合：对每个时间桶取 AVG(total_value), AVG(used_value), AVG(usage_rate)
  - 返回 CapacityTrendResponse
- [ ] 3.2 路由放在 `/statistics` 路由块附近（第 1037 行之后），与其他静态路径端点放在一起 **[C2 修复]**

### Task 4: 后端 — 预测端点 GET /capacity/forecast (AC: #2, #3, #4)

- [ ] 4.1 在 `capacity.py` 新增 `GET /forecast` 端点
  - 参数: type(可选, 默认 space, **[H4] Literal 限制**), days(可选, 默认 90)
  - 查询最近 90 天的 CapacityHistory（reference_id=0, capacity_type=type, 按日聚合）
  - **[M5 修复]** 数据点 >= 30：numpy 线性回归 → 预测 + 置信区间 + 扩容建议
  - 数据点 < 30：生成 demo 预测数据（基于当前容量统计 + 模拟增长趋势），is_demo=true
  - **[M1 修复]** Demo 基准值：先查对应容量表当前聚合值；若容量表也为空，使用硬编码默认值（space: 1000U/400U, power: 500kW/200kW, cooling: 300kW/120kW, weight: 5000kg/2000kg）
  - 返回 CapacityForecastResponse
- [ ] 4.2 扩容建议逻辑：遍历预测点，找到首个 usage_rate > 80% 的时间点，生成 ExpansionSuggestion
- [ ] 4.3 边界处理：
  - 当前无容量数据 → 返回空数组 + is_demo=true
  - usage_rate 已 > 80% → 立即生成"当前已超阈值"建议
  - predicted_usage 不应超过 100%（cap at 100）
  - confidence_lower 不应低于 0（floor at 0）

### Task 5: 后端 — 测试 (AC: #1-#4)

- [ ] 5.1 测试趋势端点：有数据/无数据/不同 interval
- [ ] 5.2 测试预测端点：充足数据/不足数据(demo)/已超阈值/无数据
- [ ] 5.3 测试容量快照逻辑

### Task 6: 前端 — 趋势预测标签页 (AC: #1, #2, #3)

- [ ] 6.1 在 capacity/index.vue 新增"容量趋势"标签页（放在"容量预警"之后）
  - 容量类型选择器（space/power/cooling/weight）
  - 时间范围选择器（最近7天/30天/90天/自定义）
  - 粒度选择器（hour/day/week/month）
  - ECharts 折线图：total(虚线) + used(实线) + usage_rate(右Y轴百分比)
- [ ] 6.2 新增"容量预测"区域（同一标签页内，趋势图下方）
  - 预测周期选择器（3个月/6个月/12个月）
  - ECharts 折线图：predicted_usage(实线) + confidence_upper/lower(填充区域)
  - 如果 is_demo=true，显示提示"当前为演示数据，系统需积累更多历史数据"
- [ ] 6.3 扩容建议卡片区域
  - 当 expansion_suggestions 非空时，显示告警卡片列表
  - 每张卡片：容量类型图标 + 预计超阈值日期 + 资源缺口 + 建议文本
- [ ] 6.4 前端需更新 `getCapacityForecast` 响应类型，增加 `is_demo` 和 `expansion_suggestions` 字段 **[M3 修复]**

## Dev Notes

### 后端模式参考

- **[C2]** 路由位置：`/trend` 和 `/forecast` 放在 `/statistics` 路由块附近（~L1037），与其他静态路径端点一起
- 异步数据库：使用 `async with async_session() as session` 或 `Depends(get_db)`
- **[C1]** 时间聚合：hour 用 `strftime('%Y-%m-%d %H', recorded_at)`，day 用 `strftime('%Y-%m-%d', recorded_at)`，month 用 `strftime('%Y-%m', recorded_at)`。**week 不用 SQLite strftime**，改为 Python 层 `isocalendar()` 分组
- numpy 已在项目中使用（forecasting.py, optimizer.py），无需新增依赖
- `expire_on_commit=False` 已全局设置

### 前端模式参考

- ECharts 已在项目中广泛使用（能源模块有大量折线图参考）
- Element Plus 组件：el-select, el-date-picker, el-card
- Axios 拦截器 `return response.data` — 前端拿到的直接是 data 层
- 自动导入：ref, computed, onMounted, watch 等无需手动 import

### 数据模拟器集成

- **[C3]** simulator 容量快照使用独立 session，与点位采集事务完全隔离
- simulator.py 主循环每 5 秒执行一次
- 容量快照每 60 秒一次（计数器 % 12 == 0）
- 快照写入 CapacityHistory 时 reference_id=0 表示全局聚合
- 四维容量各写一条记录（每次快照 4 条 INSERT）
- 快照失败仅 logger.warning，不影响主循环

### Project Structure Notes

- 后端新增文件：无（在现有 capacity.py, schemas/capacity.py, simulator.py 中扩展）
- 前端新增文件：无（在现有 capacity/index.vue 中扩展）
- 对齐现有模式：趋势/预测端点与 statistics/alerts 端点风格一致

### References

- [Source: backend/app/models/capacity.py L147-159] — CapacityHistory 模型
- [Source: backend/app/schemas/capacity.py L237-241] — CapacityTrend Schema
- [Source: frontend/src/api/modules/capacity.ts L391-417] — 前端趋势/预测 API 函数
- [Source: backend/app/services/forecasting.py L1-80] — 负荷预测参考实现
- [Source: backend/app/api/v1/capacity.py L1040-1130] — 容量统计端点参考
- [Source: _bmad-output/planning-artifacts/epics.md L756-771] — Story 7.6 定义
- [Source: _bmad-output/planning-artifacts/prd.md L806] — FR61

## Dev Agent Record

### Agent Model Used

claude-opus-4-6

### Debug Log References

### Completion Notes List

### File List
