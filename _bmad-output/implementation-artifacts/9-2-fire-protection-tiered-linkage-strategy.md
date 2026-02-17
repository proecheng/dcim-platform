# Story 9.2: 消防分级联动策略

Status: done

## Story

As a 运维工程师,
I want 系统支持消防分级联动,
So that 火灾信号可以触发自动应急响应，保障人员和设备安全。

## FR 追溯

- FR37: 系统支持消防分级联动（单传感器→预警通知，多传感器交叉确认→立即执行全部联动策略）
- Architecture 7.2: 消防分级联动策略
- Architecture 7.4: 消防信号最高优先级
- Architecture 7.5: 联动策略配置方式（YAML 预定义）
- GB 50116: 消防联动响应 ≤ 3 秒、消防信号最高优先级、联动记录永久保存

## Acceptance Criteria

1. Given 消防联动策略已通过 YAML 预定义
   When 系统启动或管理员触发重载
   Then YAML 中定义的消防策略自动写入数据库（is_system=True），已存在则跳过

2. Given 单一传感器触发（烟雾 OR VESDA）
   When 联动引擎收到 alarm.triggered 事件且 alarm_type 匹配烟感/VESDA
   Then 执行预警级别策略：发送预警通知 + 调取区域摄像头（VIDEO_POPUP）+ 等待确认
   And 响应时间 ≤ 5 秒

3. Given 多传感器交叉确认（烟雾 AND VESDA 同区域同时触发）或消防主机干接点信号
   When 联动引擎收到 fire_signal 优先级事件
   Then 执行联动级别策略：关空调 + 启排烟 + 切非关键电源 + 解锁门禁 + 应急照明 + 全区录像 + 紧急通知
   And 响应时间 ≤ 3 秒
   And 消防联动不需要双重确认（生命安全优先，GB 50116）

4. Given 联动动作部分失败
   When 某个动作执行失败（如空调关闭成功但门禁解锁失败）
   Then 已成功的动作不回滚
   And 失败动作立即重试 1 次（retry_count=1）
   And 所有动作执行结果强制记录到联动日志

5. Given 联动执行完成后存在失败动作
   When 执行状态为 partial_failure 或 failed
   Then 自动发送告警通知运维工程师人工介入

6. Given 消防策略为系统内置（is_system=True）
   When 管理员尝试修改或删除
   Then 禁止修改 trigger_type 和 trigger_condition
   And 禁止删除
   And 允许修改动作配置（如更新 webhook URL）

7. Given 前端联动策略管理页面
   When 查看消防策略
   Then 系统策略有明显标识，显示消防分级（预警/联动）
   And 提供 YAML 重载按钮（仅管理员可见）

## 现有代码分析

### Story 9-1 已实现（直接复用）

| 组件 | 文件 | 说明 |
|------|------|------|
| 事件总线 | `engines/event_bus.py` | InMemoryEventBus, EventPriority(fire_signal/critical/normal), Event(is_test) |
| 联动引擎 | `engines/linkage_engine.py` | _evaluate() 条件匹配, _execute_policy() 并行执行, dict 缓存 |
| 动作处理器 | `engines/action_handlers.py` | 5 种处理器(ALARM_NOTIFY/WEBHOOK 已实现, MQTT/VIDEO_RECORD/VIDEO_POPUP 占位) |
| 数据模型 | `models/linkage.py` | LinkagePolicy(is_system, priority, trigger_condition), LinkageAction(retry_count) |
| API | `api/v1/linkage.py` | 10 个端点, is_system 保护逻辑已实现 |
| 告警事件发布 | `services/simulator.py:270-293` | alarm.triggered 事件发布到 "linkage" 通道 |

### 现有告警模型

| 字段 | 值 | 说明 |
|------|-----|------|
| alarm_level | critical/major/minor/info | 告警级别 |
| alarm_type | threshold/communication/system | 告警类型 |
| 事件 payload | alarm_id, alarm_no, alarm_level, alarm_type, alarm_message, point_id, trigger_value, threshold_value | simulator.py 中已定义 |

### 现有事件优先级映射（simulator.py）

```python
_priority_map = {
    "critical": EventPriority.critical,
    "major": EventPriority.critical,
    "minor": EventPriority.normal,
    "info": EventPriority.normal,
}
```

### 缺失实现（需新增）

| 缺失项 | 说明 |
|--------|------|
| YAML 消防策略定义文件 | 预定义预警/联动两级策略 |
| YAML 加载服务 | 启动时读取 YAML 并写入数据库 |
| 交叉确认逻辑 | 多传感器同区域同时触发 → fire_signal 升级 |
| 失败重试机制 | retry_count > 0 时自动重试 |
| 失败告警通知 | partial_failure/failed 时自动通知 |
| YAML 重载 API | 管理员手动触发重载 |
| 前端消防策略展示增强 | 系统策略标识、分级显示、重载按钮 |

## 详细设计

### 1. YAML 消防策略定义

```yaml
# backend/app/config/fire_protection_policies.yaml

fire_protection_policies:
  # 预警级别 — 单一传感器触发
  - name: "消防预警-烟感触发"
    description: "单一烟雾传感器触发时发送预警通知并调取区域摄像头"
    trigger_type: "alarm.triggered"
    trigger_condition:
      alarm_type: "threshold"
      device_type: ["SMOKE", "SMOKE_DETECTOR"]
      fire_level: "warning"
    priority: "critical"
    actions:
      - action_type: "ALARM_NOTIFY"
        action_config:
          message: "消防预警：烟雾传感器触发，请值班人员确认"
          alarm_level: "critical"
        sort_order: 0
        timeout_seconds: 3
        retry_count: 1
      - action_type: "VIDEO_POPUP"
        action_config:
          zone: "auto"
          message: "消防预警：调取区域摄像头"
        sort_order: 1
        timeout_seconds: 5
        retry_count: 0

  - name: "消防预警-VESDA触发"
    description: "极早期火灾探测器(VESDA)触发时发送预警通知"
    trigger_type: "alarm.triggered"
    trigger_condition:
      alarm_type: "threshold"
      device_type: ["VESDA", "VESDA_DETECTOR"]
      fire_level: "warning"
    priority: "critical"
    actions:
      - action_type: "ALARM_NOTIFY"
        action_config:
          message: "消防预警：VESDA探测器触发，请值班人员确认"
          alarm_level: "critical"
        sort_order: 0
        timeout_seconds: 3
        retry_count: 1
      - action_type: "VIDEO_POPUP"
        action_config:
          zone: "auto"
          message: "消防预警：调取区域摄像头"
        sort_order: 1
        timeout_seconds: 5
        retry_count: 0

  # 联动级别 — 消防主机干接点信号或交叉确认
  - name: "消防联动-全区域应急响应"
    description: "消防主机干接点信号或多传感器交叉确认时执行全部联动策略"
    trigger_type: "alarm.triggered"
    trigger_condition:
      alarm_type: "threshold"
      device_type: ["FIRE_PANEL", "FIRE_ALARM_PANEL", "CROSS_CONFIRMED"]
      fire_level: "linkage"
    priority: "fire_signal"
    actions:
      - action_type: "MQTT_COMMAND"
        action_config:
          command: "shutdown"
          target_type: "HVAC"
          message: "关闭空调系统"
        sort_order: 0
        timeout_seconds: 3
        retry_count: 1
      - action_type: "MQTT_COMMAND"
        action_config:
          command: "start"
          target_type: "EXHAUST_FAN"
          message: "启动排烟风机"
        sort_order: 1
        timeout_seconds: 3
        retry_count: 1
      - action_type: "MQTT_COMMAND"
        action_config:
          command: "cutoff"
          target_type: "NON_CRITICAL_POWER"
          message: "切断非关键电源"
        sort_order: 2
        timeout_seconds: 3
        retry_count: 1
      - action_type: "MQTT_COMMAND"
        action_config:
          command: "unlock"
          target_type: "ACCESS_CONTROL"
          message: "解锁门禁系统"
        sort_order: 3
        timeout_seconds: 3
        retry_count: 1
      - action_type: "MQTT_COMMAND"
        action_config:
          command: "activate"
          target_type: "EMERGENCY_LIGHTING"
          message: "开启应急照明"
        sort_order: 4
        timeout_seconds: 3
        retry_count: 1
      - action_type: "VIDEO_RECORD"
        action_config:
          zone: "all"
          message: "全区域录像"
        sort_order: 5
        timeout_seconds: 5
        retry_count: 0
      - action_type: "ALARM_NOTIFY"
        action_config:
          message: "紧急通知：消防联动已触发，全区域应急响应已启动"
          alarm_level: "critical"
        sort_order: 6
        timeout_seconds: 3
        retry_count: 1
```

### 2. YAML 加载服务

```
FireProtectionService (新建)
├── load_yaml_policies() — 读取 YAML 文件
├── sync_to_database() — 写入数据库（is_system=True）
│   ├── 按 name 查找已存在策略
│   ├── 已存在 → 跳过（不覆盖用户修改的动作配置）
│   └── 不存在 → 创建策略 + 动作
├── reload() — 重新加载（删除旧系统策略 + 重新创建）
└── get_fire_level(policy) — 返回消防分级标识 warning/linkage
```

### 3. 交叉确认逻辑

```
CrossConfirmationService (新建)
├── _recent_alarms: Dict[str, List[AlarmEvent]] — 按区域缓存最近告警
├── on_alarm_event(event) — 订阅 alarm.triggered 事件
│   ├── 检查 device_type 是否为消防传感器
│   ├── 记录到 _recent_alarms[zone]
│   ├── 检查同区域是否有不同类型传感器在时间窗口内触发
│   └── 满足交叉确认 → 发布 fire_signal 优先级事件
├── _check_cross_confirm(zone) → bool
│   ├── 时间窗口: 60 秒内
│   └── 条件: 同区域至少 2 种不同 device_type 触发
└── _cleanup_expired() — 清理过期记录
```

### 4. 失败重试机制

在 `linkage_engine.py` 中修改：

**4a. `load_policies()` 缓存 retry_count**（审查修复 C1）：
- 现有 actions_data dict 缺少 retry_count 字段
- 必须添加 `"retry_count": a.retry_count` 到缓存 dict

**4b. `_execute_action()` 增加重试逻辑**（审查修复 C3）：
- 读取 action 的 retry_count（用 `if retry_count is not None` 判断）
- 每次尝试（含重试）有独立的 `asyncio.wait_for(timeout)` 超时
- 总超时 = timeout × (1 + retry_count)
- 首次执行失败后，循环重试 retry_count 次，每次间隔 500ms
- 重试结果覆盖原始结果

### 5. 失败告警通知

在 `linkage_engine.py` 的 `_execute_policy()` 中：
- 执行完成后检查 status
- 如果 status 为 partial_failure 或 failed
- 自动调用 AlarmNotifyHandler 发送失败告警

### 6. API 扩展

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| POST | `/api/v1/linkage/fire-protection/reload` | 重载 YAML 消防策略 | admin |
| GET | `/api/v1/linkage/fire-protection/status` | 获取消防策略状态（加载时间、策略数量） | viewer |

## Tasks / Subtasks

### 后端

- [ ] Task 1: YAML 消防策略定义文件 (AC: #1)
  - [ ] 1.1 新建 `backend/app/config/` 目录（目录当前不存在）[审查修复: H2]
  - [ ] 1.2 新建 `backend/app/config/fire_protection_policies.yaml`
  - [ ] 1.3 定义预警级别策略 2 条（烟感、VESDA）
  - [ ] 1.4 定义联动级别策略 1 条（消防主机干接点 → 7 个动作）+ 交叉确认触发策略 1 条（device_type=CROSS_CONFIRMED）
  - [ ] 1.5 每条策略的 trigger_condition 中包含 `fire_level` 字段标识消防分级（warning/linkage）[审查修复: M2]
  - [ ] 1.6 预警策略 device_type 使用现有系统值 SMOKE（当前系统仅有此类型），VESDA/FIRE_PANEL 为预留类型 [审查修复: H4]

- [ ] Task 2: YAML 加载服务 (AC: #1, #6)
  - [ ] 2.1 新建 `backend/app/services/fire_protection.py`
  - [ ] 2.2 `load_yaml_policies()`: 用 PyYAML 读取 YAML 文件，文件不存在时 log warning 并返回空列表（不阻塞启动）
  - [ ] 2.3 `sync_to_database(db)`: 遍历策略列表，按 name 查找已存在策略，不存在则创建（is_system=True），已存在则跳过
  - [ ] 2.4 `reload(db)`: 删除所有 is_system=True 且 trigger_condition 中包含 `fire_level` 字段的策略，重新创建 [审查修复: M3]
  - [ ] 2.5 PyYAML 不在 requirements.txt 中，必须添加 `PyYAML>=6.0` [审查修复: H1]
  - [ ] 2.6 在 `main.py` lifespan 中调用 `sync_to_database()`，在 linkage_engine.load_policies() 之前执行

- [ ] Task 3: 交叉确认服务 (AC: #3)
  - [ ] 3.1 新建 `backend/app/engines/cross_confirmation.py`
  - [ ] 3.2 `CrossConfirmationService` 类：`_recent_alarms: Dict[str, List[dict]]` 按区域缓存
  - [ ] 3.3 `on_alarm_event(event)`: 首先检查 device_type 不是 "CROSS_CONFIRMED"（防重入）[审查修复: H3]，然后检查是否为消防传感器类型（SMOKE/SMOKE_DETECTOR/VESDA/VESDA_DETECTOR），记录到缓存
  - [ ] 3.4 `_check_cross_confirm(zone)`: 60 秒时间窗口内同区域至少 2 种不同 device_type → 返回 True
  - [ ] 3.5 交叉确认成功时：发布新事件到事件总线，event_type="alarm.triggered", priority=fire_signal, payload 中增加 device_type="CROSS_CONFIRMED", cross_confirm_details
  - [ ] 3.6 `_cleanup_expired()`: 清理超过 120 秒的过期记录
  - [ ] 3.7 在 `main.py` lifespan 中订阅事件总线 "linkage" 通道

- [ ] Task 3B: 告警事件 payload 扩展 (AC: #2, #3) [审查修复: C2]
  - [ ] 3B.1 修改 `services/simulator.py` 的告警事件 payload，添加 `device_type` 和 `zone` 字段
  - [ ] 3B.2 device_type 从关联的 Point → Device 获取（需查询 point.device_id → device.device_type）
  - [ ] 3B.3 zone 从 Point 的 area_code 字段获取（如无则用 "default"）
  - [ ] 3B.4 确保 payload 中 device_type 和 zone 字段在所有告警事件中都存在

- [ ] Task 4: 失败重试机制 (AC: #4)
  - [ ] 4.1 修改 `engines/linkage_engine.py` 的 `load_policies()` 方法，在 actions_data dict 中添加 `"retry_count": a.retry_count` [审查修复: C1]
  - [ ] 4.2 修改 `_execute_action()` 方法，读取 retry_count（用 `retry_count = action.get("retry_count")`, `if retry_count is None: retry_count = 0`）[审查修复: M4]
  - [ ] 4.3 重构执行逻辑：每次尝试（含重试）有独立的 `asyncio.wait_for(timeout)` 超时 [审查修复: C3]
  - [ ] 4.4 首次执行失败后，循环重试 retry_count 次，每次间隔 0.5 秒（asyncio.sleep(0.5)）
  - [ ] 4.5 重试时更新 LinkageLog 的 status 和 error_message
  - [ ] 4.6 最终结果（成功或最后一次重试的失败）写入日志

- [ ] Task 5: 失败告警通知 (AC: #5)
  - [ ] 5.1 修改 `engines/linkage_engine.py` 的 `_execute_policy()` 方法
  - [ ] 5.2 执行完成后检查 status 是否为 partial_failure 或 failed
  - [ ] 5.3 如果是，调用 ws_manager.broadcast_alarm() 发送失败告警通知
  - [ ] 5.4 告警消息包含策略名称、失败动作数量、event_id

- [ ] Task 6: API 扩展 (AC: #7)
  - [ ] 6.1 在 `api/v1/linkage.py` 新增 POST `/fire-protection/reload` 端点
  - [ ] 6.2 调用 FireProtectionService.reload() + linkage_engine.reload_policies()
  - [ ] 6.3 新增 GET `/fire-protection/status` 端点，返回消防策略数量和加载状态
  - [ ] 6.4 注意路由顺序：静态路由 `/fire-protection/reload` 必须在参数化路由 `/policies/{policy_id}` 之前注册

- [ ] Task 7: 后端测试 (AC: all)
  - [ ] 7.1 test_yaml_load — YAML 文件解析正确性
  - [ ] 7.2 test_sync_to_database — 首次同步创建策略，重复同步跳过
  - [ ] 7.3 test_reload — 重载删除旧策略并重新创建
  - [ ] 7.4 test_cross_confirmation — 单传感器不触发交叉确认，多传感器触发
  - [ ] 7.5 test_retry_mechanism — 失败动作重试 1 次
  - [ ] 7.6 test_failure_notification — partial_failure 时发送告警通知
  - [ ] 7.7 test_fire_protection_api — reload 和 status 端点

### 前端

- [ ] Task 8: 前端策略页面增强 (AC: #7)
  - [ ] 8.1 修改 `views/linkage/policy.vue`
  - [ ] 8.2 系统策略行添加 "系统" 标签（el-tag type="danger"）
  - [ ] 8.3 消防策略显示分级标识：预警（橙色标签）/ 联动（红色标签）
  - [ ] 8.4 添加 "重载消防策略" 按钮（仅管理员可见），调用 reload API
  - [ ] 8.5 系统策略的编辑对话框中，trigger_type 和 trigger_condition 字段禁用

- [ ] Task 9: 前端 API 扩展 (AC: #7)
  - [ ] 9.1 在 `api/modules/linkage.ts` 新增 `reloadFireProtection()` 和 `getFireProtectionStatus()` 函数

## Dev Notes

### 后端模式参考

- 异步数据库：`Depends(get_db)` + AsyncSession，所有写操作必须 `await db.commit()`
- 权限：admin 管理策略和重载，operator 启用/禁用和测试，viewer 查看
- JSON 字段：SQLite 用 `Column(JSON)` 存储
- 引擎文件放在 `engines/` 目录，服务文件放在 `services/` 目录
- `value or fallback` 陷阱：用 `if value is not None` 判断
- 前后端枚举一致性：所有枚举值前后端必须完全一致（英文）

### YAML 加载要点

- 项目中目前无 YAML 配置文件，这是首次引入
- 需要新建 `backend/app/config/` 目录 [审查修复: H2]
- 使用 `pathlib.Path(__file__).parent.parent / "config"` 定位配置目录（fire_protection.py 在 services/ 下）
- YAML 文件路径：`backend/app/config/fire_protection_policies.yaml`
- PyYAML 不在 requirements.txt 中，必须添加 [审查修复: H1]
- 加载时机：main.py lifespan 中，在 linkage_engine.load_policies() 之前
- YAML 文件不存在时 log warning 并返回空列表，不阻塞启动

### 交叉确认设计要点

- CrossConfirmationService 也订阅 "linkage" 通道
- 事件总线使用 asyncio.gather 并发调用所有 handler，订阅顺序不保证执行完成顺序 [审查修复: H3]
- 交叉确认成功时内部 publish 会触发新一轮 handler 调用（re-entrant），linkage_engine 会在新一轮中处理 fire_signal 事件
- CrossConfirmationService 必须检查 device_type != "CROSS_CONFIRMED" 防止重入递归 [审查修复: H3]
- 区域信息从 event.payload 中提取（字段名 zone，如无则用 "default"）
- 交叉确认产生的新事件 payload 中增加 `device_type: "CROSS_CONFIRMED"` 和 `cross_confirm_details`
- 消防传感器类型列表：SMOKE（现有系统）, SMOKE_DETECTOR, VESDA, VESDA_DETECTOR（预留）[审查修复: H4]
- 联动级策略的 trigger_condition 必须包含 device_type: ["FIRE_PANEL", "FIRE_ALARM_PANEL", "CROSS_CONFIRMED"] 以匹配交叉确认事件

### 重试机制要点

- 在 `_execute_action()` 中实现，不修改 `_execute_policy()` 的并行执行逻辑
- 每次尝试（含重试）有独立的 `asyncio.wait_for(timeout)` 超时 [审查修复: C3]
- 总超时 = timeout × (1 + retry_count)，不在单个 wait_for 内重试
- 重试间隔 500ms（asyncio.sleep(0.5)）
- retry_count 读取必须用 `if retry_count is not None` 模式 [审查修复: M4]
- 必须先修改 `load_policies()` 缓存 retry_count 字段 [审查修复: C1]
- 日志记录：重试次数和每次重试结果

### 失败通知要点

- 在 `_execute_policy()` 末尾，status 判断后执行
- 使用 ws_manager.broadcast_alarm() 而非 broadcast_linkage()
- 消息格式：`{"action": "linkage_failure", "alarm_level": "critical", "alarm_message": "...", "execution_id": ..., "policy_name": "..."}`

### 路由顺序（重要）

- FastAPI 路由匹配是按注册顺序的
- `/fire-protection/reload` 和 `/fire-protection/status` 必须在 `/policies/{policy_id}` 之前注册
- 否则 "fire-protection" 会被当作 policy_id 参数

### 与 Story 9-1 的关系

- 复用：事件总线、联动引擎、动作处理器、数据模型、API 框架
- 扩展：linkage_engine.load_policies() 缓存 retry_count、_execute_action() 增加重试、_execute_policy() 增加失败通知
- 扩展：simulator.py 告警事件 payload 添加 device_type 和 zone [审查修复: C2]
- 新增：YAML 加载服务、交叉确认服务、2 个 API 端点
- 不修改：event_bus.py、action_handlers.py、models/linkage.py、schemas/linkage.py

### 与后续 Story 的关系

- Story 9-4（联动恢复流程）：使用本 Story 的消防策略，添加恢复动作序列
- Story 9-5（事件时间线报告）：基于消防联动执行记录生成报告

### Project Structure Notes

- 后端新增: `app/config/` 目录（新建）, `app/config/fire_protection_policies.yaml`, `app/services/fire_protection.py`, `app/engines/cross_confirmation.py`
- 后端修改: `app/engines/linkage_engine.py`（load_policies 缓存 retry_count + 重试 + 失败通知）, `app/api/v1/linkage.py`（2 个新端点）, `app/main.py`（lifespan 集成）, `app/services/simulator.py`（payload 扩展 device_type/zone）, `requirements.txt`（添加 PyYAML）
- 前端修改: `views/linkage/policy.vue`（系统策略标识+重载按钮）, `api/modules/linkage.ts`（2 个新函数）

### References

- [Source: architecture.md#7.2] 消防分级联动策略
- [Source: architecture.md#7.4] 消防信号最高优先级
- [Source: architecture.md#7.5] 联动策略配置方式
- [Source: prd.md#FR37] 消防分级联动
- [Source: prd.md#消防联动策略（分级）] 预警/联动/恢复三级
- [Source: prd.md#GB50116] 消防联动响应 ≤ 3 秒
- [Source: epic-8-retrospective.md#A6] GB 50116 消防规则完整性验证

## 对抗性审查修复

### C1: retry_count 未被缓存到策略 dict 中
**问题**: linkage_engine.py load_policies() 构建 actions_data dict 时没有包含 retry_count 字段，重试机制永远不生效。
**修复**: Task 4.1 明确要求修改 load_policies()，在 actions_data dict 中添加 `"retry_count": a.retry_count`。

### C2: 告警事件 payload 中不包含 device_type 和 zone
**问题**: simulator.py 发布的告警事件 payload 不包含 device_type 和 zone 字段，消防策略的 trigger_condition 永远无法匹配。
**修复**: 新增 Task 3B，修改 simulator.py 的告警事件 payload，从 Point → Device 获取 device_type，从 Point.area_code 获取 zone。

### C3: 重试与 asyncio.wait_for 超时冲突
**问题**: 如果重试逻辑放在 wait_for 内部，timeout_seconds=3 + retry_count=1 时重试根本来不及完成。
**修复**: 改为每次尝试有独立的 wait_for 超时，总超时 = timeout × (1 + retry_count)。

### H1: PyYAML 不在 requirements.txt 中
**问题**: Dev Notes 错误描述"PyYAML 已在 requirements.txt 中"。
**修复**: 修正 Dev Notes，Task 2.5 明确必须添加 PyYAML。

### H2: backend/app/config/ 目录不存在
**问题**: 需要新建 config 目录。
**修复**: Task 1.1 明确新建目录。

### H3: 交叉确认 re-entrant 事件处理
**问题**: asyncio.gather 并发执行，订阅顺序不保证执行完成顺序。
**修复**: 修正 Dev Notes 解释，CrossConfirmationService 必须检查 device_type != "CROSS_CONFIRMED" 防止重入。

### H4: device_type 枚举值与现有系统不匹配
**问题**: VESDA/FIRE_PANEL 等类型在现有系统中不存在。
**修复**: Task 1.6 说明当前系统仅有 SMOKE 类型，其他为预留。联动级策略 trigger_condition 增加 CROSS_CONFIRMED。

### M2: fire_level 字段存储方式
**问题**: YAML 中的 level 字段在 LinkagePolicy 模型中无对应列。
**修复**: 存入 trigger_condition JSON 中作为 fire_level 字段。

### M3: reload 逻辑依赖名称前缀
**问题**: 按名称前缀"消防"删除策略逻辑脆弱。
**修复**: 改为按 trigger_condition 中是否包含 fire_level 字段来识别消防策略。

### M4: retry_count 的 value or fallback 陷阱
**问题**: 读取 retry_count 时可能使用 `or 0` 模式。
**修复**: Task 4.2 明确使用 `if retry_count is not None` 模式。

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
