# Story 6.1: PUE 监控与配电拓扑适配

Status: ready-for-dev

## Story

As a 能源管理员,
I want 查看基于真实电表数据的 PUE 值和配电拓扑,
So that 我可以准确掌握数据中心的能效水平。

## Acceptance Criteria (验收标准)

1. **AC-1: PUE 计算适配真实数据** — 后端 PUE 计算逻辑从确定性模拟数据切换为基于 PowerDevice 关联的真实点位数据（通过 `power_point_id` 读取 PointRealtime）。当 `SIMULATION_ENABLED=true` 时保留现有模拟逻辑，`false` 时使用真实数据。IT 负载功率为 0 或数据缺失时 PUE 显示为 "--"（不可用）
2. **AC-2: 实时功率汇总适配** — `GET /energy/realtime/summary` 端点从 PowerDevice 关联的真实点位读取实时功率，计算总功率、IT 功率、制冷功率、PUE。模拟模式保留现有逻辑
3. **AC-3: 配电拓扑实时数据** — 配电拓扑 API（`GET /energy/topology`）在拓扑节点中注入真实功率数据（从 PointRealtime 读取），前端拓扑树节点显示实时功率值
4. **AC-4: PUE 历史记录写入** — 新增定时任务（每 15 分钟），将当前 PUE 值写入 PUEHistory 表。仅在 `SIMULATION_ENABLED=false` 时运行。PUE 趋势 API 优先读取 PUEHistory 真实记录
5. **AC-5: 前端 PUE 数据源标识** — 前端 PUE 监控页面（monitor.vue）和仪表盘（dashboard）显示数据来源标识："实时数据" 或 "模拟数据"，帮助用户区分
6. **AC-6: 前端拓扑实时功率展示** — 配电拓扑页面（topology.vue）的拓扑树节点显示实时功率值（kW），功率数据缺失时显示 "--"
7. **AC-7: 数据缺失降级处理** — 当真实数据不可用时（点位离线、数据质量不可靠），PUE 和功率显示降级为 "--" 并附带提示，不使用过期数据计算
8. **AC-8: 后端测试** — 测试 PUE 计算（真实数据模式和模拟模式）、测试功率汇总、测试拓扑数据注入、测试 PUE 历史写入
9. **AC-9: 前端构建验证** — `npm run build` 构建成功

## Tasks / Subtasks (任务分解)

- [ ] Task 1: 后端 — PUE 计算服务重构 (AC: #1, #7)
  - [ ] 1.1 新建 `backend/app/services/pue_calculator.py`，封装 PUE 计算逻辑：
    - `async def calculate_realtime_pue(db: AsyncSession) -> PUEResult`
    - 查询所有启用的 PowerDevice，按 `is_it_load` 分组
    - **批量查询**所有 PowerDevice 的 power_point_id，一次性从 PointRealtime 加载（避免 N+1）：
      ```python
      point_ids = [d.power_point_id for d in devices if d.power_point_id]
      rt_result = await db.execute(select(PointRealtime).where(PointRealtime.point_id.in_(point_ids)))
      realtime_map = {r.point_id: r for r in rt_result.scalars().all()}
      ```
    - 对每个设备，从 realtime_map 读取 PointRealtime.value（注意：字段名是 `value` 不是 `current_value`）
    - 检查数据质量（PointRealtime.quality，0=正常，1=不可靠，2=中断）：quality==2 跳过，quality==1 标记不可靠
    - 检查数据过期：`updated_at` 距今超过 300 秒的点位视为不可靠
    - 计算 `total_power = sum(所有设备功率)`，`it_power = sum(is_it_load=True 的设备功率)`
    - `cooling_power = sum(device_type in ['AC','CHILLER','CT','PUMP'] 的设备功率)`
    - `ups_loss = max(0, sum(device_type=='UPS' 的设备功率) - it_power)`（UPS 损耗，负值归零）
    - PUE = total_power / it_power（it_power <= 0 时返回 None，前端显示 "--"）
    - 返回 `PUEResult(current_pue, total_power, it_power, cooling_power, ups_loss, data_source, unreliable_count)`
    - `data_source`: "realtime" 或 "simulation"
  - [ ] 1.2 `PUEResult` 数据类定义在同文件中（dataclass 或 TypedDict）

- [ ] Task 2: 后端 — 能源 API 适配 (AC: #1, #2, #3)
  - [ ] 2.1 修改 `backend/app/api/v1/energy.py` 的 `get_current_pue()`（约第636行）：
    - 读取 `settings.SIMULATION_ENABLED`
    - `SIMULATION_ENABLED=false` 时调用 `pue_calculator.calculate_realtime_pue(db)`
    - `SIMULATION_ENABLED=true` 时保留现有确定性模拟逻辑不变
    - 在 PUEData 响应中新增 `data_source` 字段
  - [ ] 2.2 修改 `get_realtime_summary()`（约第516行）：
    - `SIMULATION_ENABLED=false` 时从 PowerDevice 关联的 PointRealtime 读取真实功率
    - 保留现有模拟逻辑作为 fallback
    - 在 RealtimePowerSummary 响应中新增 `data_source` 字段
  - [ ] 2.3 验证 `get_pue_trend()`（约第692行）：
    - 现有逻辑已优先查询 PUEHistory 表，无记录时 fallback 到模拟数据 — 无需修改
    - 仅需确认 Task 4 的定时任务会写入真实 PUE 数据即可
  - [ ] 2.4 修改 `get_realtime_power()`（约第516行之前的实时功率端点）：
    - `SIMULATION_ENABLED=false` 时从 PointRealtime 读取真实功率
    - 保留现有模拟逻辑

- [ ] Task 3: 后端 — 配电拓扑实时数据增强 (AC: #3)
  - [ ] 3.1 修改 `backend/app/services/energy_topology.py` 的 `get_full_topology()` 方法（第29行）：
    - 在入口处一次性批量加载所有 PowerDevice 的 PointRealtime 数据到 dict，传递给各层级构建函数（避免 N+1）
    - 设备节点已有 `realtime_data` 字段（第246行，含 power 和 update_time），需增加 `data_quality` 字段
    - 对 panel/circuit/transformer 节点，新增 `realtime_power`（汇总下游设备功率）和 `device_count`（下游设备数）
  - [ ] 3.2 修改 `_build_device_node()`（第230行）：
    - 在现有 `realtime_data` dict 中新增 `quality` 字段（从 PointRealtime.quality 读取）
    - 改用传入的 realtime_map 而非单独查询（第288-298行的单独查询改为从 map 读取）
  - [ ] 3.3 修改 `_build_circuit_node()`（第194行）：新增 `realtime_power` 字段，汇总下游设备的 `realtime_data.power`
  - [ ] 3.4 修改 `_build_panel_node()`（第135行）：新增 `realtime_power` 字段，汇总下游回路的 `realtime_power`
  - [ ] 3.5 修改 `_build_transformer_node()`（第56行）：新增 `realtime_power` 字段，汇总下游配电柜的 `realtime_power`
  - [ ] 3.6 各层级构建函数签名新增 `realtime_map: Dict[int, PointRealtime]` 参数

- [ ] Task 4: 后端 — PUE 历史定时写入 (AC: #4)
  - [ ] 4.1 在 `backend/app/main.py` 的 `lifespan()` 中新增 PUE 历史写入定时任务（每 15 分钟）：
    ```python
    async def _pue_history_loop():
        await asyncio.sleep(10)  # 启动后短暂等待
        while True:
            if not settings.SIMULATION_ENABLED:
                try:
                    async with async_session() as session:
                        await write_pue_history(session)
                except Exception as e:
                    logger.warning("PUE历史写入失败: %s", e)
            await asyncio.sleep(900)  # 15分钟
    pue_history_task = asyncio.create_task(_pue_history_loop())
    ```
  - [ ] 4.2 在 `pue_calculator.py` 中新增 `async def write_pue_history(db: AsyncSession)`：
    - 调用 `calculate_realtime_pue(db)` 获取当前 PUE
    - PUE 有效时（非 None）写入 PUEHistory 记录
    - PUEHistory 模型已存在（energy.py 中），字段：record_time, pue, total_power, it_power, cooling_power
  - [ ] 4.3 在 lifespan yield 后取消：`pue_history_task.cancel()`
  - [ ] 4.4 添加启动日志：`print("PUE历史记录任务已启动，每15分钟记录一次")`

- [ ] Task 5: 后端 — Schema 更新 (AC: #1, #2, #5)
  - [ ] 5.1 修改 `backend/app/schemas/energy.py`：
    - **CRITICAL**: `PUEData.current_pue` 从 `float = Field(...)` 改为 `Optional[float] = None`（支持 IT 负载为 0 时返回 None）
    - **CRITICAL**: `RealtimePowerSummary.current_pue` 从 `float = Field(...)` 改为 `Optional[float] = None`
    - `PUEData` 新增 `data_source: Optional[str] = None`（"realtime" 或 "simulation"）
    - `PUEData` 新增 `unreliable_count: Optional[int] = 0`（不可靠点位数量）
    - `RealtimePowerSummary` 新增 `data_source: Optional[str] = None`
    - `RealtimePowerData` 新增 `data_quality: Optional[int] = 0`（0=正常，1=不可靠，2=中断）
    - 注意：`RealtimePowerSummary` 用 `ups_power` 字段名，`PUEData` 用 `ups_loss` 字段名 — 保持现有命名不变

- [ ] Task 6: 前端 — API 类型更新 (AC: #5, #6)
  - [ ] 6.1 修改 `frontend/src/api/modules/energy.ts`：
    - **CRITICAL**: `PUEData.current_pue` 从 `number` 改为 `number | null`（与后端 Optional[float] 对齐）
    - **CRITICAL**: `RealtimePowerSummary.current_pue` 从 `number` 改为 `number | null`
    - `PUEData` 接口新增 `data_source?: string`、`unreliable_count?: number`
    - `RealtimePowerSummary` 接口新增 `data_source?: string`
    - `RealtimePowerData` 接口新增 `data_quality?: number`
    - 拓扑相关：`TopologyTransformerNode`/`TopologyPanelNode`/`TopologyCircuitNode` 新增 `realtime_power?: number`
    - 注意：设备节点的实时功率在 `realtime_data.power` 中（已有），不要新增重复字段

- [ ] Task 7: 前端 — PUE 监控页面适配 (AC: #5, #7)
  - [ ] 7.1 修改 `frontend/src/views/energy/monitor.vue`：
    - 在 PUE 仪表盘区域显示数据来源标识 Tag：`data_source === 'realtime'` 显示绿色 "实时数据"，否则显示灰色 "模拟数据"
    - PUE 值为 null/undefined 时显示 "--"（不可用），不显示 0
    - 不可靠点位数 > 0 时显示警告提示："有 N 个点位数据不可靠，PUE 可能不准确"
    - 功率 breakdown（total_power, it_power, cooling_power, ups_loss）为 null 时显示 "--"

- [ ] Task 8: 前端 — 配电拓扑实时功率展示 (AC: #6)
  - [ ] 8.1 修改 `frontend/src/views/energy/topology.vue`：
    - 在拓扑树节点标签中显示实时功率值：
      - 设备节点：从 `node.realtime_data?.power` 读取（已有字段）
      - transformer/panel/circuit 节点：从 `node.realtime_power` 读取（Task 3 新增）
      - 格式：`{node.label} ({power?.toFixed(1) || '--'} kW)`
    - 功率值着色仅应用于设备节点（有 rated_power）：>80% 红色，60-80% 橙色，<60% 绿色
    - 数据质量不可靠（`realtime_data.quality > 0`）时功率值显示为灰色斜体
  - [ ] 8.2 修改 `buildTransformerNode`、`buildMeterPointNode` 等函数，传递 `realtime_power` 字段到树节点

- [ ] Task 9: 前端 — 仪表盘 PUE 数据源标识 (AC: #5)
  - [ ] 9.1 检查 `frontend/src/views/dashboard/index.vue` 中 PUEIndicatorCard 的使用
  - [ ] 9.2 如果 PUEIndicatorCard 接收 data_source prop，添加数据来源标识
  - [ ] 9.3 如果 PUEIndicatorCard 不支持，修改组件或在 dashboard 中直接显示

- [ ] Task 10: 后端测试 (AC: #8)
  - [ ] 10.1 新建 `backend/tests/test_pue_calculator.py`
  - [ ] 10.2 测试 PUE 计算（真实数据模式）：有 IT 负载时正确计算 PUE
  - [ ] 10.3 测试 PUE 计算（IT 负载为 0）：返回 None
  - [ ] 10.4 测试 PUE 计算（数据质量中断）：跳过 quality==2 的点位
  - [ ] 10.5 测试功率汇总 API（模拟模式）：保留现有行为
  - [ ] 10.6 测试功率汇总 API（真实数据模式）：从 PointRealtime 读取
  - [ ] 10.7 测试 PUE 历史写入：正确写入 PUEHistory 记录
  - [ ] 10.8 测试拓扑数据注入：设备节点包含 realtime_power 字段

- [ ] Task 11: 前端构建验证 (AC: #9)
  - [ ] 11.1 `npm run build` 构建成功

## Dev Notes (开发指南)

### 1. 核心设计思路

本 Story 的核心是**适配**而非重建。现有能源模块已有完整的 PUE 计算、配电拓扑、前端展示。需要做的是：
- 后端：在现有 API 端点中增加"真实数据"分支，通过 `SIMULATION_ENABLED` 环境变量切换
- 前端：在现有页面中增加数据来源标识和降级处理
- 不要重写现有的模拟数据逻辑，保留作为开发环境的 fallback

### 2. 文件位置

```
backend/app/services/pue_calculator.py                 # 新建 — PUE 计算服务
backend/app/api/v1/energy.py                           # 修改 — PUE/功率/拓扑 API 适配（3874行大文件，谨慎修改）
backend/app/services/energy_topology.py                # 修改 — 拓扑节点注入实时功率
backend/app/schemas/energy.py                          # 修改 — 新增 data_source 等字段
backend/app/main.py                                    # 修改 — 新增 PUE 历史定时任务
backend/tests/test_pue_calculator.py                   # 新建 — PUE 计算测试
frontend/src/api/modules/energy.ts                     # 修改 — 新增类型字段
frontend/src/views/energy/monitor.vue                  # 修改 — 数据来源标识、降级处理
frontend/src/views/energy/topology.vue                 # 修改 — 拓扑节点实时功率展示
frontend/src/views/dashboard/index.vue                 # 修改 — PUE 数据来源标识（如需）
```

### 3. 现有基础设施（关键参考）

**PUE 计算现有逻辑**（energy.py 第634-689行）：
- `get_current_pue()` 使用确定性模拟数据（`_deterministic_ratio`/`_deterministic_offset` 函数）
- 从 PowerDevice 查询设备，按 `is_it_load` 分组，用 `rated_power * ratio` 模拟功率
- PUE = total_power / it_power

**PowerDevice 模型**（energy.py）关键字段：
- `power_point_id`: 关联的功率点位 ID（ForeignKey → points.id）
- `energy_point_id`: 关联的电量点位 ID
- `is_it_load`: 是否为 IT 负载
- `device_type`: 设备类型（IT/UPS/AC/CHILLER/CT/PUMP/LIGHT 等）
- `rated_power`: 额定功率 kW

**PointRealtime 模型**（point.py）关键字段：
- `point_id`: 点位 ID
- `value`: 当前工程值（即实时功率值）— 注意：字段名是 `value` 不是 `current_value`
- `quality`: 数据质量（0=正常，1=不可靠，2=中断）— Story 5-4 新增
- `updated_at`: 最后更新时间（超过 300 秒视为过期）

**PUEHistory 模型**（energy.py）已存在：
- `record_time`: 记录时间
- `pue`: PUE 值
- `total_power`: 总功率
- `it_power`: IT 功率
- `cooling_power`: 制冷功率

**配电拓扑服务**（energy_topology.py）：
- `EnergyTopologyService.get_full_topology(db)` 返回完整拓扑树
- `_build_device_node()` 已有 `realtime_data` 字段（第246行），含 `power` 和 `update_time`
- `_build_device_node()` 第288-298行已通过 `power_point_id` 单独查询 PointRealtime — 需改为使用批量 map
- panel/circuit/transformer 节点目前没有实时功率汇总 — 需要新增 `realtime_power` 字段

**前端 PUE 展示**：
- `views/energy/monitor.vue`: 直接用 ECharts Gauge 绘制 PUE，调用 `getCurrentPUE()` 和 `getPUETrend()`
- `components/energy/PUEGauge.vue`: 独立 PUE Gauge 组件
- `components/energy/PUEIndicatorCard.vue`: 仪表盘 PUE 指示卡
- `stores/energy.ts`: Pinia store 存储 pueData、powerSummary
- `composables/useEnergy.ts`: 数据加载编排（loadPUE、loadPowerSummary 等）

**前端拓扑展示**：
- `views/energy/topology.vue`: ElTree 渲染拓扑树，调用 `getDistributionTopology()`
- 节点类型层级：grid → transformer → meter_point → panel → circuit → device → point
- `buildTransformerNode(t)` 等函数构建树节点

**SIMULATION_ENABLED 配置**：
- `backend/app/core/config.py` 中 `Settings.SIMULATION_ENABLED: bool`
- 通过环境变量 `SIMULATION_ENABLED=true/false` 控制
- 现有模拟器（simulator.py）已使用此配置

### 4. 数据流路径

```
真实数据路径:
  采集网关 → MQTT → PointRealtime 表 → PowerDevice.power_point_id 关联 → PUE 计算

模拟数据路径（保留）:
  PowerDevice.rated_power × deterministic_ratio → 模拟功率 → PUE 计算
```

### 5. 关键约束

- **energy.py 是 3874 行大文件**：修改时只改动目标函数，不要重构整个文件
- **确定性模拟函数不要删除**：`_deterministic_ratio`、`_deterministic_offset`、`_device_seed`、`_time_seed`、`_date_seed` 在模拟模式下仍需使用
- **PUEHistory 模型已存在**：不需要新建模型或迁移，直接使用
- **PowerDevice.power_point_id 可能为 NULL**：未关联点位的设备在真实模式下功率为 0，不参与计算
- **PointRealtime 字段名是 `value`**：不是 `current_value`，这是最常见的错误
- **PUEData.current_pue 必须改为 Optional[float]**：否则 IT 负载为 0 时返回 None 会触发 Pydantic ValidationError
- **批量查询避免 N+1**：PUE 计算和拓扑构建都必须一次性加载所有 PointRealtime，不要逐个查询
- **拓扑设备节点已有 realtime_data 字段**：不要新增重复的 realtime_power，利用现有字段并增加 quality
- **UPS 损耗可能为负**：使用 `max(0, ups_total - it_power)` 防止负值
- **数据过期判断**：PointRealtime.updated_at 超过 300 秒的数据视为不可靠
- **RealtimePowerSummary 用 `ups_power`，PUEData 用 `ups_loss`**：两个 Schema 的 UPS 字段命名不同，不要混淆
- **数据质量字段**：PointRealtime.quality 是 Story 5-4 新增的字段（0=正常，1=不可靠，2=中断），PUE 计算需要检查
- **前端自动导入**：Vue API（ref, computed, onMounted 等）无需手动 import，但自定义组件需要手动 import
- **前端 API 模块**：energy.ts 已有 2300+ 行，新增类型字段时注意不要破坏现有接口
- **定时任务模式**：参考 main.py 中已有的告警引擎（30s）、通信监控（30s）、升级引擎（60s）的定时任务模式

### 6. Story 5.2-5.5 经验教训

- broadcast 必须在 session.commit() 后发送
- ORM commit 后属性可能过期，使用已知值构建消息
- 前端自定义组件需要手动 import（unplugin-auto-import 不覆盖）
- 前端 .ts 文件中 onMounted/onUnmounted 需要显式从 'vue' import
- 大文件修改时只改目标函数，不要重构
- 测试中使用 `override_get_db` fixture 注入测试数据库

### 7. IT 负载功率为 0 的处理

```python
# PUE 计算中 IT 负载为 0 的处理
if it_power <= 0:
    return PUEResult(
        current_pue=None,  # 前端显示 "--"
        total_power=total_power,
        it_power=0,
        cooling_power=cooling_power,
        ups_loss=0,
        data_source="realtime",
        unreliable_count=unreliable_count
    )
# UPS 损耗防负值
ups_loss = max(0, ups_total - it_power)
```

### References

- [Source: api/v1/energy.py#L634-689] PUE 计算现有逻辑
- [Source: api/v1/energy.py#L516-582] 实时功率汇总现有逻辑
- [Source: api/v1/energy.py#L692-771] PUE 趋势现有逻辑
- [Source: models/energy.py#L12-44] Transformer 模型
- [Source: models/energy.py] PowerDevice 模型（power_point_id, is_it_load, device_type, rated_power）
- [Source: models/energy.py] PUEHistory 模型（record_time, pue, total_power, it_power, cooling_power）
- [Source: models/point.py] PointRealtime 模型（point_id, current_value, quality, updated_at）
- [Source: services/energy_topology.py#L29] get_full_topology() 拓扑构建入口
- [Source: services/energy_topology.py#L56-230] 各层级节点构建函数
- [Source: views/energy/monitor.vue#L30-102] PUE 展示区域
- [Source: views/energy/monitor.vue#L300-320] API 导入和数据加载
- [Source: views/energy/topology.vue#L62-70] 拓扑树渲染区域
- [Source: views/energy/topology.vue#L825-863] buildTransformerNode 等函数
- [Source: stores/energy.ts#L22-42] PUE 状态和计算属性
- [Source: api/modules/energy.ts#L103-128] PUEData/PUETrend 接口定义
- [Source: api/modules/energy.ts#L794-835] 拓扑节点接口定义
- [Source: main.py] 定时任务模式（告警引擎、通信监控、升级引擎）
- [Source: prd.md#L787-788] FR45: PUE 实时值及历史趋势；FR46: 配电拓扑图
- [Source: architecture.md#L193-194] 能源管理和配电拓扑数据模型

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
