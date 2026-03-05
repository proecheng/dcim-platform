# DCIM Demo 系统与主系统数据链路审查报告

**日期:** 2026-03-05
**审查范围:** backend/app/demo/, backend/app/services/, frontend/src/components/DemoDataLoader.vue
**审查目的:** 识别 demo 系统与主系统之间的数据耦合、来源混淆和隔离缺失问题

---

## 一、Demo 系统架构概览

```
┌────────────────────────────────────────────────────────────────────┐
│                    三大数据源（并行入口）                            │
├──────────────────┬────────────────────┬────────────────────────────┤
│ MQTT Gateway     │ DemoEngine         │ DataSourceBridge           │
│ source="mqtt"    │ source="demo"      │ source="bridge"            │
├──────────────────┴────────────────────┴────────────────────────────┤
│                process_payload() [统一管道]                         │
│  Phase 1: 写DB (PointDataLatest/Realtime/History) ← 无 source 列  │
│  Phase 2: 告警评估 + 告警创建 (Alarm表)         ← 无 source 列   │
│  Phase 3: WebSocket推送 + Redis缓存              ← 无 source 标记 │
└────────────────────────────────────────────────────────────────────┘
```

**核心问题:** `IngestPoint.source` 字段在入口处标记了来源（demo/mqtt/bridge），但进入 `process_payload()` 后**完全未被使用**，下游数据库、WebSocket、Redis 均不保留来源信息。

---

## 二、已识别的问题

### D-1: 数据来源标记创建即丢弃 (Critical)

**问题:** `IngestPoint` 有 `source` 字段（ingest_pipeline.py:45），DemoEngine 标记 `source="demo"`（engine.py:148），但 pipeline 后续流程完全不使用该字段。

**影响链路:**
| 存储层 | 是否保留 source | 后果 |
|--------|----------------|------|
| PointDataLatest | 无 source 列 | 无法区分数据来源 |
| PointRealtime | 无 source 列 | 无法区分数据来源 |
| PointHistory | 无 source 列 | 历史回溯无法过滤 demo 数据 |
| Alarm | 无 source 列 | 告警无法追溯触发来源 |
| WebSocket 消息 | 不含 source 字段 | 前端无法区分 demo 推送 |
| Redis 缓存 | key 不含 source | 缓存数据完全混合 |

**文件位置:**
- `backend/app/services/ingest_pipeline.py` 第 34-46 行（IngestPoint 定义）
- `backend/app/services/ingest_pipeline.py` 第 166-199 行（写 DB，未传 source）
- `backend/app/services/ingest_pipeline.py` 第 586-600 行（WS 推送，未传 source）
- `backend/app/services/ingest_pipeline.py` 第 603-635 行（Redis 缓存，未传 source）

---

### D-2: Demo 与真实数据共库无隔离 (Critical)

**问题:** Demo 种子数据、模拟器数据与（未来的）真实采集数据写入**同一组数据库表**，无任何标记区分。

**表影响范围:**
- 种子数据创建: Site, Floor, Room, Device, Point, PointRealtime（~2830 条点位）
- 模拟器持续写入: PointDataLatest, PointRealtime, PointHistory, Alarm
- 历史生成器写入: EnergyHourly, EnergyDaily, EnergyMonthly, PUEHistory, Demand15MinData 等

**后果:**
- 真实网关接入后，demo 数据与真实数据**无法分离**
- 无法按来源过滤告警（运维人员无法区分 demo 告警和真实告警）
- 能耗统计混入 demo 生成的虚假数据，导致 PUE 等指标失真
- 卸载 demo 数据时会**删除 51+ 张表的全部数据**（service.py:1304-1456），包括用户自定义的配置

---

### D-3: 主系统代码硬依赖 Demo 数据编码 (Major)

**问题:** 主系统的业务服务中硬编码了 demo 特定的设备编码和楼层规则。

**耦合点 1: point_device_matcher.py（第 34-78 行）**
```python
LEGACY_MAPPING_RULES = {
    "SRV-001": {"prefix": "A1_SRV_AI_", ...},
    "UPS-F1-01": {"prefix": "A1_UPS_AI_", ...},
    "CH-F1-01": {"prefix": "B1_CH_AI_", ...},
    # 20+ 条硬编码 demo 设备码映射
}
```

**耦合点 2: device_sync.py（第 717-830 行）**
```python
# 硬编码楼层列表
for floor in ["F1", "F2", "F3", "F4"]:  # 第 720 行
# 硬编码回路码
circuit_map.get("C-CH-01")   # 第 801 行
circuit_map.get("C-AC-01")   # 第 813 行
```

**耦合点 3: building_points.py（第 1-1078 行）**
- 既是 demo 数据定义（点位编码 B1_CH_AI_*、F1_TH_AI_* 等）
- 又被主系统 `demo/service.py` 导入
- 包含告警阈值规则，与 demo 建筑结构耦合

**后果:**
- 非 demo 环境下，点位匹配引擎的回退规则无法工作
- 新楼层/新设备编码无法被自动推断关联到配电回路
- building_points.py 无法安全移除

---

### D-4: Demo 禁用后系统缺乏最小化种子 (Major)

**问题:** `DEMO_ENABLED=false` 时，`lifecycle.py:28` 直接 return，不执行任何数据初始化。

**缺失的数据:**
| 缺失数据 | 影响功能 | 严重性 |
|----------|---------|--------|
| Site/Floor/Room | 空间结构页面为空 | 严重 |
| Device/Point | 无设备可监控、实时数据无来源 | 严重 |
| Transformer/MeterPoint/Panel/Circuit | 配电拓扑为空、能源管理不可用 | 严重 |
| AlarmThreshold | 无告警规则、告警功能不可用 | 严重 |
| ElectricityPricing | 电价计算不可用 | 中等 |
| FloorMap | 数字孪生无楼层布局 | 轻微 |

**后果:** 系统启动成功但**功能完全不可用**，用户需从零手工录入所有基础数据。

---

### D-5: 历史数据生成器绕过统一管道 (Major)

**问题:** `history_generator.py` 直接写入 PointHistory 和能耗模型表，绕过 `process_payload()`。

**文件位置:** `backend/app/services/history_generator.py` 第 110-184 行

**后果:**
- 历史数据不触发告警评估（这是有意为之，但缺乏文档说明）
- 历史数据不经过降采样逻辑（与实时数据的 store_interval 不一致）
- 历史数据无 source 标记，与实时管道写入的数据格式相同但生成路径不同

---

### D-6: Demo 配置项语义重叠 (Minor)

**问题:** `demo_enabled` 和 `simulation_enabled` 两个配置项语义重叠。

**文件位置:** `backend/app/core/config.py` 第 49-52 行
```python
simulation_enabled: bool = False  # 是否启用模拟数据
demo_enabled: bool = False        # 演示模式开关
```

**判断逻辑:** `demo/config.py:9` — `return settings.demo_enabled or settings.simulation_enabled`

**后果:**
- 用户困惑：两个配置有什么区别？
- 无法独立控制"加载种子数据"和"启动模拟器"
- 注释说"过渡期两者等价"，但从未过渡

---

### D-7: 前端 Demo 加载后刷新不完整 (Minor)

**问题:** Dashboard 的 `refreshData()` 直接调用 API 更新本地 ref，不经过 Pinia Store。

**文件位置:** `frontend/src/views/dashboard/index.vue` 第 412-478 行

**后果:**
- Demo 数据加载后，Dashboard 的数据刷新了，但其他已打开页面（告警列表、能源监控、环境监控）的数据不会刷新
- Pinia Store（AlarmStore、EnergyStore、RealtimeStore）的数据不会更新
- 用户需要手动刷新其他页面才能看到 demo 数据
- 与 `docs/data-flow-audit.md` 中 P0-1（告警数据三源割裂）问题叠加

---

### D-8: 卸载函数过于激进 (Minor)

**问题:** `unload_demo_data()` 删除 51+ 张表的**全部数据**，不区分 demo 和用户自定义数据。

**文件位置:** `backend/app/demo/service.py` 第 1291-1456 行

**后果:**
- 用户如果在 demo 数据基础上自定义了告警规则、配电拓扑等，卸载时全部丢失
- 无备份/恢复机制
- 无确认提示（前端有确认对话框，但后端无保护）

---

## 三、整改方案

### 方案 G: 数据来源标记贯穿（解决 D-1, D-2）

**目标:** 从数据入口到存储层全链路保留来源标识。

**具体修改:**

1. **数据库层**
   - Point 表增加 `source: str` 列（默认 "manual"），标记点位创建来源
   - PointHistory 表增加 `source: str` 列（默认 "unknown"）
   - Alarm 表增加 `data_source: str` 列（默认 "unknown"），记录触发该告警的数据来源
   - 迁移脚本: `alembic revision --autogenerate -m "add source tracking columns"`

2. **管道层**
   - `process_payload()` 将 `IngestPoint.source` 传递到 PointHistory 写入逻辑
   - `_evaluate_alarms()` 将 source 写入 Alarm.data_source
   - `_broadcast_realtime()` 在 WebSocket 消息中增加 `source` 字段
   - Redis 缓存数据增加 `source` 字段（在 JSON 值中，不改 key）

3. **查询层**
   - 告警列表 API 支持 `?source=demo` / `?source=mqtt` 过滤
   - 历史数据 API 支持按 source 过滤
   - 前端告警列表增加"来源"列和筛选器

### 方案 H: Demo 数据编码解耦（解决 D-3）

**目标:** 移除主系统对 demo 特定编码的硬依赖。

**具体修改:**

1. **point_device_matcher.py**
   - 将 `LEGACY_MAPPING_RULES` 从代码中移除
   - 迁移到 `backend/app/demo/data/legacy_mapping.py`
   - 主系统仅保留通用的 `derive_point_prefix()` 和 `identify_point_usage()` 算法
   - 通用算法通过数据库关联（device_id → points）匹配，不依赖编码规则

2. **device_sync.py**
   - 楼层列表从数据库 Floor 表动态查询，不硬编码 `["F1", "F2", "F3", "F4"]`
   - 回路推断规则参数化，从 DistributionCircuit 表的 circuit_code 模式动态匹配
   - 将 demo 特定的推断规则（AC-A→C-AC-01 等）移到 demo 配置

3. **building_points.py**
   - 移动到 `backend/app/demo/data/building_points.py`
   - 主系统不再直接导入该文件

### 方案 I: 最小化种子与 Demo 分离（解决 D-4, D-6, D-8）

**目标:** 将系统基础数据初始化与 demo 演示数据分离。

**具体修改:**

1. **配置项拆分**（config.py）
   - `seed_enabled: bool = True` — 是否初始化最小种子数据（Site、默认配置）
   - `demo_enabled: bool = False` — 是否加载完整 demo 数据（设备、点位、历史）
   - `simulation_enabled: bool = False` — 是否启动数据模拟器
   - 移除 `demo_enabled or simulation_enabled` 的合并逻辑

2. **最小化种子**（新建 `backend/app/seeds/minimal_seed.py`）
   - 创建默认 Site（可配置名称）
   - 创建基础 Floor/Room 结构
   - 创建默认电价配置
   - 创建默认告警级别配置
   - 不创建设备和点位

3. **Demo 数据标记**
   - 所有 demo 创建的记录在 Point/Device 表增加 `is_demo: bool = False` 列
   - 种子数据标记 `is_demo=True`
   - 卸载时仅删除 `is_demo=True` 的记录，保留用户自定义数据

4. **lifecycle.py 重构**
   ```
   startup():
     if seed_enabled:
       await minimal_seed()          # 始终执行
     if demo_enabled:
       await full_demo_seed()        # 完整 demo 数据
     if simulation_enabled:
       await simulator.start()       # 独立控制模拟器
   ```

### 方案 J: 历史生成器规范化（解决 D-5）

**目标:** 统一历史数据生成路径，保留来源标记。

**具体修改:**

1. `history_generator.py` 写入 PointHistory 时增加 `source="demo_backfill"` 标记
2. 在文件头部增加注释说明为何绕过 process_payload（避免触发告警）
3. 确保生成的历史数据与 ingest_pipeline 的降采样间隔一致

---

## 四、与现有审查报告的关系

| 本报告问题 | 关联 data-flow-audit.md 问题 | 交叉影响 |
|-----------|---------------------------|---------|
| D-1 数据来源丢失 | P0-1 告警三源割裂 | 告警来源不可追溯加剧割裂问题 |
| D-2 共库无隔离 | P0-2 实时数据双源割裂 | demo 实时数据与 store 数据混合 |
| D-7 刷新不完整 | P2-8 Dashboard 缓存不一致 | demo 加载后 Dashboard 缓存与 Store 脱节 |
| D-4 缺乏最小种子 | P1-6 站点过滤未贯穿 | 无站点数据则站点过滤无意义 |

---

## 五、实施优先级

| 优先级 | 方案 | 解决问题 | 涉及文件 | 风险 |
|--------|------|---------|---------|------|
| **P0** | I: 种子分离 + 配置拆分 | D-4, D-6, D-8 | config.py, lifecycle.py, 新建 minimal_seed.py | 中 — 影响启动流程 |
| **P1** | G: 来源标记贯穿 | D-1, D-2 | ingest_pipeline.py, alarm 模型, WS 推送 | 中 — 需 DB 迁移 |
| **P1** | H: 编码解耦 | D-3 | point_device_matcher.py, device_sync.py, building_points.py | 中 — 匹配逻辑重构 |
| **P2** | J: 历史生成规范 | D-5 | history_generator.py | 低 |

---

## 六、数据流全景图（Demo + 主系统）

```
┌─────────── 数据创建层 ───────────────────────────────────────────┐
│                                                                  │
│  [Demo Seeds]          [Demo Loader]        [用户手动录入]        │
│  datacenter_seed.py    service.py           /api/v1/devices/     │
│  power_seed.py         load_demo_data()     /api/v1/points/      │
│  cooling_seed.py                            /api/v1/energy/      │
│  ↓                     ↓                    ↓                    │
│  Site/Floor/Room       Point/Device         Point/Device         │
│  Device/Point          History/Energy       (同表, 无标记区分)    │
│  (is_demo=true*)       (is_demo=true*)      (is_demo=false*)     │
│  (* 待实现)            (* 待实现)            (* 待实现)           │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────── 实时数据层 ──────────────────────────────────────────┐
│                                                                  │
│  [DemoEngine]          [MQTT Gateway]        [DataSourceBridge]  │
│  engine.py             mqtt/client.py        datasource_bridge   │
│  source="demo"         source="mqtt"         source="bridge"     │
│  每60秒一轮            事件驱动              轮询/推送            │
│  ↓                     ↓                     ↓                   │
│  ┌──────────────── process_payload() ──────────────────┐         │
│  │ IngestPoint(source=...) → 统一管道                  │         │
│  │                                                     │         │
│  │ DB写入:  PointDataLatest/Realtime/History           │         │
│  │          (source 字段被丢弃)                        │         │
│  │ 告警:    Alarm 表 (无 data_source 列)              │         │
│  │ WS推送:  broadcast_realtime() (无 source 字段)     │         │
│  │ Redis:   point:{id}:latest (无 source 标记)        │         │
│  └─────────────────────────────────────────────────────┘         │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────── 前端消费层 ──────────────────────────────────────────┐
│                                                                  │
│  Dashboard              告警列表             能源监控            │
│  (局部ref+缓存)         (useAlarm)           (energyStore)       │
│  ← 无法区分来源         ← 无法区分来源       ← 能耗混入demo数据  │
│                                                                  │
│  DemoDataLoader                                                  │
│  仅在 Dashboard 使用                                             │
│  加载后仅刷新当前页面                                             │
│  其他页面需手动刷新                                               │
└──────────────────────────────────────────────────────────────────┘
```

---

*本报告由 demo 系统深度审查生成，建议与 `docs/data-flow-audit.md`（前端数据链路审查）配合使用，在 Sprint Planning 前确认整改方案。*
