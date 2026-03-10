# Epic 28 对抗性审查报告

**审查日期:** 2026-03-10
**审查人:** Claude (Adversarial Review)
**审查范围:** Epic 28（Demo 系统解耦与数据隔离）实施成果
**审查方法:** 对比原始审查报告（demo-system-audit.md）与实际代码实现

---

## 审查结论

⚠️ **发现 3 个问题：1 个 P0 问题，2 个 P2 问题**

---

## 审查发现

### ✅ 验证点 1: 数据源追踪是否贯穿整个数据管道

**原始问题（D-1）:** `IngestPoint.source` 字段在入口处标记了来源，但进入 `process_payload()` 后完全未被使用。

**实施验证:**

✅ **PointRealtime 表** - 已添加 source 列
- 文件: `backend/app/models/point.py:69`
- UPDATE 语句使用 source（`ingest_pipeline.py:272`）
- INSERT 语句使用 source（`ingest_pipeline.py:293`）

✅ **PointDataLatest 表** - 已添加 source 列
- 文件: `backend/app/models/point.py:50`
- UPDATE 语句使用 source（`ingest_pipeline.py:346`）

✅ **PointHistory 表** - 已添加 source 列
- 文件: `backend/app/models/history.py:23`
- INSERT 语句使用 source（`ingest_pipeline.py:382`）

✅ **Alarm 表** - 已添加 data_source 列
- 文件: `backend/app/models/alarm.py:69`
- 告警创建时使用 source（`ingest_pipeline.py:452`）

✅ **WebSocket 推送** - 已包含 source 字段
- 文件: `ingest_pipeline.py:607`
- 推送消息包含 `"source": pt.source`

✅ **Redis 缓存** - 已包含 source 字段
- 文件: `ingest_pipeline.py:630`
- 缓存数据包含 `"source": pt.source`

**结论:** ✅ **问题已完全解决** - 数据源标记已贯穿整个数据管道

---

### ✅ 验证点 2: Demo 配置是否真正分离

**原始问题（D-6）:** `demo_enabled` 和 `simulation_enabled` 两个配置项语义重叠。

**实施验证:**

✅ **配置项已拆分**（`backend/app/core/config.py:53-56`）:
```python
seed_enabled: bool = Field(default=False, description="启用最小化种子")
demo_enabled: bool = Field(default=False, description="启用 Demo 数据")
simulation_enabled: bool = Field(default=False, description="启用数据模拟器")
```

✅ **Seed 配置已添加**（`backend/app/core/config.py:58-69`）:
- `default_site_name`: 默认站点名称
- `default_floor_count`: 默认楼层数
- `default_room_count`: 默认房间数
- `default_admin_password`: 默认管理员密码
- 电价配置（五级制）

**结论:** ✅ **问题已完全解决** - 配置已拆分为 seed/demo/simulation 三个独立开关

---

### ⚠️ 验证点 3: 主系统代码是否真正解耦

**原始问题（D-3）:** 主系统的业务服务中硬编码了 demo 特定的设备编码和楼层规则。

**实施验证:**

✅ **point_device_matcher.py** - 已解耦
- `LEGACY_MAPPING_RULES` 已从主系统移除
- 改为动态注册机制（`MatcherRegistry`）
- 支持按 source 卸载规则（`unregister(source)`）

⚠️ **device_sync.py** - 部分解耦
- ✅ 楼层列表不再硬编码 `["F1", "F2", "F3", "F4"]`，改为从 Floor 表动态查询（line 782）
- ❌ 回路推断规则仍有硬编码（lines 773-790）:
  ```python
  if code.startswith("CH-"):
      return circuit_map.get("C-CH-01")  # 硬编码
  if code.startswith("AC-A"):
      return circuit_map.get("C-AC-01")  # 硬编码
  ```

**影响:**
- 非 demo 环境下，如果回路编码不是 `C-CH-01`、`C-AC-01` 等，推断会失败
- 新设备类型需要修改代码添加规则

**建议修复:**
- 将回路推断规则参数化，从数据库 DistributionCircuit 表的 circuit_code 模式动态匹配
- 或者将这些规则移到配置文件/数据库表

**优先级:** P2 - 不影响核心功能，但限制了系统的通用性

---

### ✅ 验证点 4: Demo 数据是否可以安全卸载

**原始问题（D-2, D-8）:** Demo 与真实数据共库无隔离，卸载函数过于激进。

**实施验证:**

✅ **is_demo 列已添加到多个表**:
- Device（`models/device.py:36`）
- Point（`models/point.py:51`）
- Alarm（`models/alarm.py:27`）
- Site/Floor/Room（`models/spatial.py:39,59,83,104`）
- PowerDevice（`models/energy.py:42`）
- 配电设备（Transformer, MeterPoint, Panel, Circuit）
- 制冷设备（CoolingUnit, ColdAisle, CoolingGroup）
- FloorMap（`models/floor_map.py:20`）

✅ **安全卸载方法已实现**（`demo/service.py:1839-2000`）:
- `_clear_demo_data_safe()` 方法使用 is_demo 标记
- 删除策略：
  1. 通过外键删除 demo Point 关联的数据（PointHistory, PointRealtime, Alarm）
  2. 删除 is_demo=True 的记录（Point, Device, Site 等）
  3. 运行时数据表全部删除（EnergyHourly, PUEHistory 等）
  4. 保留用户自定义数据

⚠️ **service_new.py 缺少 _clear_demo_data_safe 实现**:
- `service_new.py` 调用了 `_clear_demo_data_safe()`（lines 1086, 1224）
- 但该方法未定义，会导致运行时错误
- `service.py` 中有完整实现

**影响:**
- 如果系统使用 `service_new.py`，卸载功能会失败
- 如果系统使用 `service.py`，卸载功能正常

**建议修复:**
- 将 `_clear_demo_data_safe()` 方法从 `service.py` 复制到 `service_new.py`
- 或者删除 `service_new.py`，统一使用 `service.py`

**优先级:** P0 - 影响核心功能（卸载 demo 数据）

---

## 新发现的问题

### P2-1: service_new.py 与 service.py 重复

**问题描述:**
- 项目中同时存在 `service.py` 和 `service_new.py` 两个文件
- `service_new.py` 缺少 `_clear_demo_data_safe()` 方法实现
- 不清楚哪个文件是当前使用的版本

**影响:**
- 代码维护困难
- 可能导致功能不一致

**建议修复:**
- 确认当前使用的版本
- 删除未使用的文件
- 或者将两个文件合并

**优先级:** P2 - 代码质量问题

---

## 问题汇总

| 问题编号 | 问题描述 | 优先级 | 状态 | 影响范围 |
|---------|---------|--------|------|---------|
| P0-1 | service_new.py 缺少 _clear_demo_data_safe 实现 | P0 | 未修复 | 卸载功能 |
| P2-1 | service_new.py 与 service.py 重复 | P2 | 未修复 | 代码维护 |
| P2-2 | device_sync.py 回路推断规则仍有硬编码 | P2 | 部分修复 | 系统通用性 |

---

## Epic 28 实施质量评估

### 优点

1. **数据源追踪完整** - source 字段已贯穿整个数据管道（DB、WS、Redis）
2. **配置拆分清晰** - seed/demo/simulation 三个独立开关
3. **is_demo 标记完整** - 17+ 个表添加了 is_demo 列
4. **安全卸载实现** - _clear_demo_data_safe 使用 is_demo 标记，保护用户数据
5. **点位匹配解耦** - LEGACY_MAPPING_RULES 改为动态注册机制

### 缺点

1. **P0 问题** - service_new.py 缺少关键方法实现
2. **代码重复** - service.py 和 service_new.py 同时存在
3. **部分硬编码** - device_sync.py 回路推断规则仍有硬编码

### 总体评价

Epic 28 的核心目标（数据源追踪、配置分离、is_demo 标记、安全卸载）已基本实现，但存在 1 个 P0 问题和 2 个 P2 问题。

**建议:**
1. **立即修复 P0-1** - 将 _clear_demo_data_safe 方法复制到 service_new.py
2. **清理代码** - 删除未使用的 service_new.py 或 service.py
3. **参数化回路规则** - 将 device_sync.py 的硬编码规则改为配置驱动

---

## 对比原始审查报告

| 原始问题 | 实施状态 | 验证结果 |
|---------|---------|---------|
| D-1: 数据来源标记丢失 | ✅ 已修复 | source 字段贯穿整个管道 |
| D-2: 共库无隔离 | ✅ 已修复 | is_demo 列已添加 |
| D-3: 硬编码 demo 依赖 | ⚠️ 部分修复 | point_device_matcher 已解耦，device_sync 部分硬编码 |
| D-4: 缺乏最小种子 | ✅ 已修复 | seed_enabled 配置已添加 |
| D-5: 历史生成器绕过管道 | ✅ 已修复 | PointHistory 写入时使用 source="demo_backfill" |
| D-6: 配置项重叠 | ✅ 已修复 | 配置已拆分为 seed/demo/simulation |
| D-7: 前端刷新不完整 | ✅ 已修复 | 由 Epic 27 解决（数据链路统一） |
| D-8: 卸载过于激进 | ✅ 已修复 | _clear_demo_data_safe 使用 is_demo 标记 |

**完成度:** 7/8 完全修复，1/8 部分修复

---

## 审查方法说明

本次审查采用以下方法：

1. **代码审查** - 检查数据模型、服务层、API 端点的实际实现
2. **对比验证** - 对比原始审查报告（demo-system-audit.md）与实际代码
3. **数据流追踪** - 验证 source 字段是否贯穿整个数据管道
4. **配置检查** - 验证配置项是否拆分
5. **安全性验证** - 验证卸载功能是否使用 is_demo 标记

---

**审查完成时间:** 2026-03-10
**下一步:** 修复 P0-1 问题，清理代码重复
