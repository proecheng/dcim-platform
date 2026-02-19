# Story 9.3: 智能故障诊断

Status: ready-for-dev

## Story

As a 运维工程师,
I want 系统自动分析告警的可能原因,
So that 我可以快速定位故障根因。

## FR 追溯

- FR34: 系统可以基于规则和历史数据自动分析告警的可能原因（覆盖 Top 20 高频故障场景）
- Architecture 2.3: 后端分层 - engines/ 目录
- Architecture 7.1: 联动引擎架构 - 事件总线订阅
- Architecture 9.5: 故障影响分析

## Acceptance Criteria

1. Given 诊断规则已通过 YAML 预定义并加载到内存
   When 告警触发（alarm.triggered 事件发布到事件总线）
   Then 诊断引擎自动分析告警，在 2 秒内给出可能原因列表
   And 诊断结果通过 WebSocket "alarms" 通道推送到前端

2. Given 诊断规则覆盖 Top 20 高频故障场景
   When 告警匹配到诊断规则
   Then 每个可能原因附带置信度（0-100）和建议操作
   And 原因列表按置信度降序排列

3. Given 系统已积累历史告警数据
   When 诊断引擎分析告警
   Then 置信度计算综合考虑：规则匹配强度（基础分）、历史频率加权（同类告警历史出现次数）、上下文因子（同区域/同设备近期告警关联）

4. Given 诊断规则支持 YAML 预定义和数据库自定义
   When 管理员通过 API 管理诊断规则
   Then 支持规则 CRUD（数据库自定义规则）
   And 支持 YAML 规则重载（系统预定义规则）
   And YAML 规则标记为 is_system=True，不可删除

5. Given 诊断结果已生成
   When 运维工程师通过 API 查询
   Then 支持按告警 ID 查询诊断结果
   And 支持按时间范围查询诊断历史
   And 支持手动触发对指定告警的重新诊断

6. Given 前端告警管理页面
   When 查看告警详情
   Then 显示该告警的诊断结果面板（原因列表+置信度+建议操作）
   And 提供"重新诊断"按钮

7. Given 前端诊断规则管理页面（管理员）
   When 管理诊断规则
   Then 显示规则列表（含系统规则标识）
   And 支持自定义规则的新增/编辑/删除/启用/禁用
   And 提供 YAML 规则重载按钮

## 现有代码分析

### 已有实现（直接复用）

| 组件 | 文件 | 说明 |
|------|------|------|
| 事件总线 | `engines/event_bus.py` | InMemoryEventBus, EventPriority, Event(is_test), get_event_bus() |
| 联动引擎 | `engines/linkage_engine.py` | 事件订阅模式参考, _evaluate() 条件匹配模式 |
| 交叉确认 | `engines/cross_confirmation.py` | 事件总线订阅 + 内存缓存模式参考 |
| 告警模型 | `models/alarm.py` | Alarm(alarm_no, point_id, alarm_level, alarm_type, status, trigger_value), AlarmDailyStats |
| 设备模型 | `models/device.py` | Device(device_type, device_code, area_code) - 设备类型: UPS/AC/PDU/TH/DOOR/SMOKE/WATER |
| 点位模型 | `models/point.py` | Point(device_id, device_type, area_code, point_type) |
| 联动模型 | `models/linkage.py` | LinkagePolicy(is_system, trigger_condition JSON) - YAML+DB 双存储模式参考 |
| 联动 Schema | `schemas/linkage.py` | Pydantic v2 ConfigDict(from_attributes=True) 模式参考 |
| 联动 API | `api/v1/linkage.py` | 分页+筛选+CRUD+is_system 保护模式参考 |
| 消防 YAML 服务 | `services/fire_protection.py` | YAML 加载 + sync_to_database + reload 模式参考 |
| WebSocket | `services/websocket.py` | ws_manager.broadcast_alarm() - 告警通道推送 |
| 告警事件发布 | `services/simulator.py:270-293` | alarm.triggered 事件 payload 格式（含 device_type, zone） |
| 数据库基类 | `core/database.py` | Base, async_session, get_db |
| 依赖注入 | `api/deps.py` | get_current_user, require_admin, require_operator |
| 路由注册 | `api/v1/__init__.py` | api_router.include_router() 模式 |
| 前端 API | `api/modules/linkage.ts` | TypeScript 接口 + API 函数模式参考 |
| 前端页面 | `views/linkage/policy.vue` | el-table + el-dialog + 系统标识模式参考 |
| main.py | `main.py` | lifespan 中事件总线订阅 + YAML 同步模式 |

### 缺失实现（需新增）

| 缺失项 | 说明 |
|--------|------|
| 诊断规则模型 | DiagnosisRule（数据库存储诊断规则） |
| 诊断结果模型 | DiagnosisResult, DiagnosisCause（诊断结果+原因列表） |
| 诊断规则 YAML | Top 20 高频故障场景的预定义规则 |
| 诊断引擎 | DiagnosisEngine - 订阅事件总线，规则匹配+置信度计算 |
| 诊断服务 | DiagnosisService - YAML 加载、规则管理、历史频率统计 |
| 诊断 API | 规则 CRUD、诊断结果查询、手动触发诊断、YAML 重载 |
| 诊断 Schema | 请求/响应 Pydantic 模型 |
| 前端诊断结果面板 | 告警详情中的诊断结果展示组件 |
| 前端诊断规则管理页 | 规则列表+新增/编辑/删除 |
| 前端 API 模块 | diagnosis.ts |

## 详细设计

### 1. Top 20 高频故障场景诊断规则

以下为数据中心 Top 20 高频故障场景，每条规则定义触发条件、可能原因、基础置信度和建议操作：

| 序号 | 故障场景 | 触发条件（alarm_type + device_type） | 可能原因 | 基础置信度 |
|------|---------|--------------------------------------|---------|-----------|
| 1 | 温度过高 | threshold + TH, alarm_level=critical | 空调故障停机/空调制冷不足/机柜前门未关/服务器负载突增 | 85/70/60/50 |
| 2 | 湿度异常 | threshold + TH | 空调加湿器故障/除湿器故障/外部环境渗透/管道泄漏 | 80/75/55/50 |
| 3 | UPS 故障 | threshold + UPS | 电池老化/逆变器故障/市电异常/过载运行 | 80/75/65/55 |
| 4 | 空调故障 | threshold + AC | 压缩机故障/冷凝器脏堵/制冷剂泄漏/风机故障 | 85/70/65/55 |
| 5 | 漏水检测 | threshold + WATER | 空调冷凝水管堵塞/管道接头松动/地板下积水/外部渗水 | 80/70/60/45 |
| 6 | 烟雾告警 | threshold + SMOKE | 设备过热冒烟/线缆短路/灰尘积累误报/传感器故障 | 85/75/55/40 |
| 7 | 电力过载 | threshold + PDU | 单回路负载过高/三相不平衡/新设备上架未评估/PDU容量不足 | 80/70/60/50 |
| 8 | 通信中断 | communication + any | 网关故障/网络设备故障/线缆松动/交换机端口故障 | 80/70/60/50 |
| 9 | PDU 故障 | threshold + PDU | 断路器跳闸/接触器故障/过温保护/输入电源异常 | 85/70/60/55 |
| 10 | 制冷失效 | threshold + AC, 多点温度升高 | 冷冻水系统故障/冷却塔故障/水泵故障/阀门异常 | 80/75/65/55 |
| 11 | 电池老化 | threshold + UPS, 电池相关点位 | 电池组老化/单体电池失效/充电器故障/环境温度过高 | 85/70/60/50 |
| 12 | 三相不平衡 | threshold + PDU | 负载分配不均/单相设备集中/相线接触不良/中性线异常 | 80/70/55/45 |
| 13 | 功率因数低 | threshold + PDU | 无功补偿装置故障/感性负载过多/谐波干扰/电容器老化 | 75/70/60/50 |
| 14 | PUE 异常 | threshold + system | 制冷效率下降/IT负载突变/照明系统异常/配电损耗增加 | 75/70/55/45 |
| 15 | 风机故障 | threshold + AC | 风机轴承磨损/电机故障/皮带松动/风道堵塞 | 85/70/60/50 |
| 16 | 传感器漂移 | threshold + TH | 传感器老化/安装位置不当/电磁干扰/校准过期 | 75/65/55/45 |
| 17 | 门禁异常 | threshold + DOOR | 门磁传感器故障/门锁机械故障/控制器通信异常/非法闯入 | 80/70/60/50 |
| 18 | 消防预警 | threshold + SMOKE | 真实火情/设备过热/施工扬尘/传感器误报 | 90/75/55/40 |
| 19 | 网络中断 | communication + any, 多设备同时离线 | 核心交换机故障/光纤断裂/网关宕机/DHCP服务异常 | 85/75/60/45 |
| 20 | 存储温度异常 | threshold + TH, 存储区域 | 存储设备散热不良/局部气流短路/冷通道封闭破损/存储负载过高 | 80/70/60/50 |

### 2. YAML 诊断规则定义格式

```yaml
# backend/app/config/diagnosis_rules.yaml

diagnosis_rules:
  - name: "温度过高诊断"
    description: "机房温度超过告警阈值时的故障诊断"
    match_condition:
      alarm_type: "threshold"
      device_type: ["TH"]
      alarm_level: ["critical", "major"]
      point_keywords: ["温度", "temperature", "temp"]
    causes:
      - cause: "空调故障停机"
        base_confidence: 85
        suggestion: "检查关联空调运行状态，确认压缩机和风机是否正常工作"
        related_device_types: ["AC"]
      - cause: "空调制冷不足"
        base_confidence: 70
        suggestion: "检查空调出风温度和回风温度差值，确认制冷量是否满足需求"
        related_device_types: ["AC"]
      - cause: "机柜前门未关闭"
        base_confidence: 60
        suggestion: "检查告警区域机柜门禁状态，确认是否有门未关闭导致冷热气流混合"
        related_device_types: ["DOOR"]
      - cause: "服务器负载突增"
        base_confidence: 50
        suggestion: "检查机柜内服务器CPU利用率和功耗变化，确认是否有异常负载"
        related_device_types: []
    is_enabled: true
    category: "环境"

  # ... 其余 19 条规则格式相同
```

### 3. 数据模型设计

```
DiagnosisRule (诊断规则)
+-- id: Integer PK
+-- name: String(100) NOT NULL
+-- description: Text
+-- match_condition: JSON          # 匹配条件（alarm_type, device_type, alarm_level, point_keywords）
+-- causes: JSON                   # 原因列表（cause, base_confidence, suggestion, related_device_types）
+-- category: String(50)           # 规则分类（环境/电力/安全/通信/设备）
+-- is_enabled: Boolean default=True
+-- is_system: Boolean default=False  # True=YAML预定义不可删
+-- created_at: DateTime
+-- updated_at: DateTime

DiagnosisResult (诊断结果)
+-- id: Integer PK
+-- alarm_id: Integer FK(alarms.id)  # 关联告警
+-- alarm_no: String(50)             # 告警编号（冗余，方便查询）
+-- rule_id: Integer FK(diagnosis_rules.id) nullable  # 匹配的规则（可能为空=无匹配）
+-- device_type: String(20)          # 设备类型
+-- area_code: String(10)            # 区域代码
+-- status: String(20)               # pending/completed/no_match
+-- diagnosed_at: DateTime
+-- causes -> DiagnosisCause[]

DiagnosisCause (诊断原因)
+-- id: Integer PK
+-- result_id: Integer FK(diagnosis_results.id)
+-- cause: String(200)               # 原因描述
+-- confidence: Integer              # 最终置信度 0-100
+-- base_confidence: Integer         # 基础置信度
+-- history_factor: Float            # 历史频率因子
+-- context_factor: Float            # 上下文因子
+-- suggestion: Text                 # 建议操作
+-- related_device_types: JSON       # 关联设备类型
+-- sort_order: Integer              # 排序（按置信度降序）
```

### 4. 诊断引擎设计

```
DiagnosisEngine (单例，lifespan 启动)
+-- _rule_cache: Dict[int, dict]     # 内存缓存已启用规则
+-- _history_stats: Dict[str, int]   # 历史告警频率统计缓存（device_type -> count）
+--
+-- start() - 订阅事件总线 "linkage" 通道，加载规则缓存
+-- stop() - 取消订阅
+-- on_alarm_event(event) - 事件处理入口
|   +-- 仅处理 alarm.triggered 事件
|   +-- 调用 diagnose()
+-- diagnose(alarm_payload) -> DiagnosisResult
|   +-- 1. 匹配规则：遍历 _rule_cache，按 match_condition 匹配
|   +-- 2. 计算置信度：base_confidence * history_factor * context_factor
|   +-- 3. 排序：按最终置信度降序
|   +-- 4. 存储结果到数据库
|   +-- 5. 推送到 WebSocket
+-- _match_rule(rule, payload) -> bool
|   +-- 匹配 alarm_type（精确匹配）
|   +-- 匹配 device_type（列表包含）
|   +-- 匹配 alarm_level（列表包含，可选）
|   +-- 匹配 point_keywords（告警消息关键词，可选）
+-- _calc_history_factor(device_type, alarm_type) -> float
|   +-- 查询最近 30 天同类告警数量
|   +-- count >= 10: factor = 1.2（高频故障，置信度提升）
|   +-- count >= 5: factor = 1.1
|   +-- count >= 1: factor = 1.0
|   +-- count == 0: factor = 0.9（罕见故障，置信度降低）
+-- _calc_context_factor(payload, cause) -> float
|   +-- 检查同区域近 10 分钟内是否有关联设备告警
|   +-- 有关联告警: factor = 1.3（强关联，如温度高+空调告警）
|   +-- 无关联告警: factor = 1.0
+-- load_rules() - 从数据库加载规则到缓存
+-- reload_rules() - copy-on-write 刷新缓存
+-- refresh_history_stats() - 刷新历史频率统计
```

### 5. 置信度计算算法

```
最终置信度 = min(100, round(base_confidence * history_factor * context_factor))

其中：
- base_confidence: 规则中预定义的基础置信度（0-100）
- history_factor: 历史频率因子（0.9 - 1.2）
  - 最近 30 天同类告警 >= 10 次: 1.2
  - 最近 30 天同类告警 >= 5 次: 1.1
  - 最近 30 天同类告警 >= 1 次: 1.0
  - 最近 30 天同类告警 = 0 次: 0.9
- context_factor: 上下文关联因子（1.0 - 1.3）
  - 同区域 10 分钟内有 related_device_types 中的设备告警: 1.3
  - 同区域 10 分钟内有其他告警（非关联设备）: 1.1
  - 无关联告警: 1.0
```

### 6. API 设计

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/v1/diagnosis/rules` | 诊断规则列表（分页+筛选） | viewer |
| GET | `/api/v1/diagnosis/rules/{id}` | 规则详情 | viewer |
| POST | `/api/v1/diagnosis/rules` | 创建自定义规则 | admin |
| PUT | `/api/v1/diagnosis/rules/{id}` | 更新规则（is_system=True 时限制修改） | admin |
| DELETE | `/api/v1/diagnosis/rules/{id}` | 删除规则（is_system=True 禁止删除） | admin |
| PUT | `/api/v1/diagnosis/rules/{id}/toggle` | 启用/禁用规则 | operator |
| POST | `/api/v1/diagnosis/reload` | 重载 YAML 诊断规则 | admin |
| GET | `/api/v1/diagnosis/results` | 诊断结果列表（分页+筛选） | viewer |
| GET | `/api/v1/diagnosis/results/by-alarm/{alarm_id}` | 按告警 ID 查询诊断结果 | viewer |
| POST | `/api/v1/diagnosis/diagnose/{alarm_id}` | 手动触发对指定告警的诊断 | operator |
| GET | `/api/v1/diagnosis/stats` | 诊断统计（规则命中率、Top 故障原因） | viewer |

### 7. 前端页面设计

**7a. 告警详情诊断面板（嵌入现有告警页面）**
- 在告警详情对话框/抽屉中新增"智能诊断"标签页
- 显示诊断结果：原因列表（原因描述 + 置信度进度条 + 建议操作）
- 置信度颜色：>= 80 红色, >= 60 橙色, < 60 蓝色
- "重新诊断"按钮（调用 POST /diagnosis/diagnose/{alarm_id}）
- 无诊断结果时显示"暂无诊断结果"

**7b. 诊断规则管理页面（新页面，管理员）**
- 规则列表表格：name, category, match_condition 摘要, causes 数量, is_enabled, is_system, updated_at
- 系统规则行添加"系统"标签（el-tag type="danger"）
- 新建/编辑规则对话框：基本信息 + 匹配条件 + 原因列表（可增删）
- 启用/禁用开关、删除确认（is_system 禁止删除）
- "重载诊断规则"按钮（仅管理员可见）

**7c. 诊断统计面板（可选，嵌入仪表盘）**
- Top 5 高频故障原因饼图
- 诊断命中率趋势

## Tasks / Subtasks

### 后端

- [ ] Task 1: 诊断数据模型 (AC: #4, #5)
  - [ ] 1.1 新建 `backend/app/models/diagnosis.py`
  - [ ] 1.2 DiagnosisRule: name, description, match_condition(JSON), causes(JSON), category(String(50)), is_enabled, is_system, created_at, updated_at
  - [ ] 1.3 DiagnosisResult: alarm_id(FK alarms.id), alarm_no(String(50)), rule_id(FK diagnosis_rules.id nullable), device_type, area_code, status("pending"/"completed"/"no_match"), diagnosed_at
  - [ ] 1.4 DiagnosisCause: result_id(FK diagnosis_results.id), cause(String(200)), confidence(Integer), base_confidence(Integer), history_factor(Float), context_factor(Float), suggestion(Text), related_device_types(JSON), sort_order(Integer)
  - [ ] 1.5 DiagnosisResult.causes 关系: relationship("DiagnosisCause", backref="result", lazy="selectin", cascade="all, delete-orphan")
  - [ ] 1.6 在 `models/__init__.py` 注册 DiagnosisRule, DiagnosisResult, DiagnosisCause

- [ ] Task 2: 诊断 Schema (AC: #4, #5)
  - [ ] 2.1 新建 `backend/app/schemas/diagnosis.py`
  - [ ] 2.2 DiagnosisRuleCreate: name, description, match_condition(dict), causes(list[dict]), category, is_enabled
  - [ ] 2.3 DiagnosisRuleUpdate: 所有字段 Optional
  - [ ] 2.4 DiagnosisRuleResponse: model_config = ConfigDict(from_attributes=True)，含所有字段
  - [ ] 2.5 DiagnosisCauseResponse: cause, confidence, base_confidence, history_factor, context_factor, suggestion, related_device_types, sort_order
  - [ ] 2.6 DiagnosisResultResponse: 含 causes 嵌套列表, alarm_no, device_type, area_code, status, diagnosed_at
  - [ ] 2.7 DiagnosisStatsResponse: total_diagnoses, match_rate, top_causes(list)

- [ ] Task 3: YAML 诊断规则定义文件 (AC: #2)
  - [ ] 3.1 新建 `backend/app/config/diagnosis_rules.yaml`
  - [ ] 3.2 定义 20 条诊断规则，覆盖 Top 20 高频故障场景
  - [ ] 3.3 每条规则包含: name, description, match_condition, causes(含 base_confidence + suggestion + related_device_types), category, is_enabled
  - [ ] 3.4 match_condition 格式: alarm_type(str), device_type(list[str]), alarm_level(list[str] optional), point_keywords(list[str] optional)
  - [ ] 3.5 category 分类: 环境/电力/安全/通信/设备

- [ ] Task 4: 诊断服务 - YAML 加载 (AC: #4)
  - [ ] 4.1 新建 `backend/app/services/diagnosis_service.py`
  - [ ] 4.2 `load_yaml_rules()`: 用 PyYAML 读取 YAML 文件（复用 fire_protection.py 的 pathlib 定位模式），文件不存在时 log warning 返回空列表
  - [ ] 4.3 `sync_to_database(db)`: 遍历规则列表，按 name 查找已存在规则，不存在则创建（is_system=True），已存在则跳过
  - [ ] 4.4 `reload(db)`: 删除所有 is_system=True 的诊断规则，重新创建
  - [ ] 4.5 `get_history_stats(db)`: 查询最近 30 天 Alarm 表，按 (alarm_type, device_type) 分组统计数量，返回 Dict
  - [ ] 4.6 `get_recent_alarms(db, area_code, minutes=10)`: 查询指定区域最近 N 分钟的告警列表

- [ ] Task 5: 诊断引擎核心 (AC: #1, #2, #3)
  - [ ] 5.1 新建 `backend/app/engines/diagnosis_engine.py`
  - [ ] 5.2 DiagnosisEngine 类: _rule_cache(Dict[int, dict]), _history_stats(Dict[str, int])
  - [ ] 5.3 `load_rules()`: 从数据库加载 is_enabled=True 的规则到 _rule_cache（copy-on-write 模式）
  - [ ] 5.4 `reload_rules()`: 公开接口，调用 load_rules()
  - [ ] 5.5 `on_alarm_event(event)`: 事件处理入口，仅处理 event_type="alarm.triggered"，调用 diagnose()
  - [ ] 5.6 `diagnose(alarm_payload, alarm_id=None, alarm_no=None)`: 核心诊断逻辑
    - 遍历 _rule_cache 匹配规则
    - 对每条匹配规则的每个 cause 计算最终置信度
    - 合并所有匹配规则的 causes，按置信度降序排列
    - 存储 DiagnosisResult + DiagnosisCause 到数据库
    - 推送诊断结果到 WebSocket
  - [ ] 5.7 `_match_rule(rule, payload)`: 匹配逻辑
    - alarm_type 精确匹配
    - device_type 列表包含匹配
    - alarm_level 列表包含匹配（可选，未指定则跳过）
    - point_keywords 关键词匹配 alarm_message（可选，未指定则跳过）
  - [ ] 5.8 `_calc_history_factor(device_type, alarm_type)`: 历史频率因子计算
    - 使用 _history_stats 缓存，避免每次查库
    - count >= 10: 1.2, >= 5: 1.1, >= 1: 1.0, == 0: 0.9
  - [ ] 5.9 `_calc_context_factor(payload, cause)`: 上下文关联因子
    - 查询同区域近 10 分钟告警（使用 diagnosis_service.get_recent_alarms）
    - 有 related_device_types 匹配: 1.3
    - 有其他告警: 1.1
    - 无关联: 1.0
  - [ ] 5.10 `refresh_history_stats()`: 刷新历史频率统计缓存
  - [ ] 5.11 全局单例 `diagnosis_engine = DiagnosisEngine()`

- [ ] Task 6: 诊断 API (AC: #4, #5, #6)
  - [ ] 6.1 新建 `backend/app/api/v1/diagnosis.py`
  - [ ] 6.2 GET /rules - 规则列表（分页，支持 category/is_enabled/is_system 筛选）
  - [ ] 6.3 GET /rules/{id} - 规则详情
  - [ ] 6.4 POST /rules - 创建自定义规则（is_system 强制为 False），调用 engine.reload_rules()
  - [ ] 6.5 PUT /rules/{id} - 更新规则，is_system=True 时禁止修改 match_condition
  - [ ] 6.6 DELETE /rules/{id} - 删除规则，is_system=True 返回 403
  - [ ] 6.7 PUT /rules/{id}/toggle - 启用/禁用规则，调用 engine.reload_rules()
  - [ ] 6.8 POST /reload - 重载 YAML 诊断规则 + engine.reload_rules()
  - [ ] 6.9 GET /results - 诊断结果列表（分页，支持 alarm_no/device_type/status/时间范围筛选）
  - [ ] 6.10 GET /results/by-alarm/{alarm_id} - 按告警 ID 查询诊断结果（含 causes）
  - [ ] 6.11 POST /diagnose/{alarm_id} - 手动触发诊断（从 Alarm 表读取告警信息，调用 engine.diagnose）
  - [ ] 6.12 GET /stats - 诊断统计
  - [ ] 6.13 注意路由顺序：静态路由 `/reload`, `/stats`, `/results/by-alarm/{alarm_id}` 必须在参数化路由之前注册
  - [ ] 6.14 在 `api/v1/__init__.py` 注册路由: `api_router.include_router(diagnosis_router, prefix="/diagnosis", tags=["智能诊断"])`

- [ ] Task 7: 引擎生命周期集成 (AC: #1)
  - [ ] 7.1 在 `main.py` lifespan 中：
    - 在 linkage_engine.load_policies() 之后调用 diagnosis YAML sync_to_database()
    - 调用 diagnosis_engine.load_rules()
    - 调用 diagnosis_engine.refresh_history_stats()
    - 订阅事件总线: `await event_bus.subscribe("linkage", diagnosis_engine.on_alarm_event)`
  - [ ] 7.2 历史统计定时刷新：每 30 分钟刷新一次 _history_stats 缓存（新增定时任务循环）
  - [ ] 7.3 在 lifespan yield 后 cancel 定时任务

- [ ] Task 8: 后端测试 (AC: all)
  - [ ] 8.1 test_diagnosis_rule_crud - 规则 CRUD API（创建/读取/更新/删除）
  - [ ] 8.2 test_diagnosis_rule_system_protect - is_system=True 禁止删除/修改 match_condition
  - [ ] 8.3 test_diagnosis_engine_match - 规则匹配逻辑（alarm_type + device_type + alarm_level + keywords）
  - [ ] 8.4 test_diagnosis_confidence_calc - 置信度计算（base * history * context）
  - [ ] 8.5 test_diagnosis_on_alarm_event - 事件触发自动诊断
  - [ ] 8.6 test_diagnosis_manual_trigger - 手动触发诊断 API
  - [ ] 8.7 test_diagnosis_result_query - 诊断结果查询（按 alarm_id、时间范围）
  - [ ] 8.8 test_yaml_load_and_reload - YAML 加载和重载

### 前端

- [ ] Task 9: 前端 API 模块 (AC: #5, #6, #7)
  - [ ] 9.1 新建 `frontend/src/api/modules/diagnosis.ts`
  - [ ] 9.2 TypeScript 接口: DiagnosisRule, DiagnosisCause, DiagnosisResult, DiagnosisStats
  - [ ] 9.3 API 函数: getDiagnosisRules, getDiagnosisRule, createDiagnosisRule, updateDiagnosisRule, deleteDiagnosisRule, toggleDiagnosisRule, reloadDiagnosisRules, getDiagnosisResults, getDiagnosisResultByAlarm, triggerDiagnosis, getDiagnosisStats

- [ ] Task 10: 告警详情诊断面板组件 (AC: #6)
  - [ ] 10.1 新建 `frontend/src/components/common/DiagnosisPanel.vue`
  - [ ] 10.2 Props: alarmId(number), alarmNo(string)
  - [ ] 10.3 自动加载诊断结果（调用 getDiagnosisResultByAlarm）
  - [ ] 10.4 原因列表展示：原因描述 + el-progress 置信度进度条（颜色分级）+ 建议操作折叠面板
  - [ ] 10.5 "重新诊断"按钮（调用 triggerDiagnosis）
  - [ ] 10.6 无结果时显示空状态提示
  - [ ] 10.7 在现有告警详情对话框中集成此组件（修改 `views/alarm/index.vue`）

- [ ] Task 11: 诊断规则管理页面 (AC: #7)
  - [ ] 11.1 新建 `frontend/src/views/diagnosis/rules.vue`
  - [ ] 11.2 规则列表表格: name, category, is_enabled(开关), is_system(标签), causes 数量, updated_at
  - [ ] 11.3 系统规则行添加"系统"标签（el-tag type="danger"）
  - [ ] 11.4 新建/编辑规则对话框: 基本信息 + 匹配条件表单 + 原因列表（可增删）
  - [ ] 11.5 匹配条件表单: alarm_type 下拉, device_type 多选, alarm_level 多选, point_keywords 标签输入
  - [ ] 11.6 原因列表: cause 输入 + base_confidence 数字输入 + suggestion 文本域 + related_device_types 多选
  - [ ] 11.7 启用/禁用开关、删除确认（is_system 禁止删除）
  - [ ] 11.8 "重载诊断规则"按钮（仅管理员可见），调用 reloadDiagnosisRules API
  - [ ] 11.9 2.5D 样式: `@use '@/styles/mixins-25d' as *` + `@include page-list`

- [ ] Task 12: 路由注册 (AC: all)
  - [ ] 12.1 在 `router/index.ts` 新增诊断管理路由:
    - `/diagnosis/rules` - 诊断规则管理
  - [ ] 12.2 侧边栏菜单: 在"联动管理"分组下新增"智能诊断"子菜单

## Dev Notes

### 后端模式参考

- 异步数据库：`Depends(get_db)` + AsyncSession，所有写操作必须 `await db.commit()`
- 权限：admin 管理规则和重载，operator 启用/禁用和手动诊断，viewer 查看
- JSON 字段：SQLite 用 `Column(JSON)` 存储（参考 `models/linkage.py` 的 trigger_condition）
- 引擎文件放在 `engines/` 目录，服务文件放在 `services/` 目录
- `value or fallback` 陷阱：用 `if value is not None` 判断，不要用 `value or default`
- 前后端枚举一致性：status、category 等枚举值前后端必须完全一致（英文）
- copy-on-write 缓存刷新：构建新 dict 后原子替换引用（参考 linkage_engine.py:69）

### YAML 加载要点

- 复用 Story 9-2 的 fire_protection.py 模式
- 使用 `pathlib.Path(__file__).parent.parent / "config"` 定位配置目录（diagnosis_service.py 在 services/ 下）
- YAML 文件路径：`backend/app/config/diagnosis_rules.yaml`
- PyYAML 已在 requirements.txt 中（Story 9-2 已添加）
- 加载时机：main.py lifespan 中，在 linkage_engine.load_policies() 之后
- YAML 文件不存在时 log warning 并返回空列表，不阻塞启动

### 诊断引擎设计要点

- DiagnosisEngine 也订阅 "linkage" 通道（与 cross_confirmation_service 和 linkage_engine 并列）
- 事件总线使用 asyncio.gather 并发调用所有 handler，诊断引擎与联动引擎互不阻塞
- 诊断引擎仅处理 event_type="alarm.triggered" 事件，忽略其他事件类型
- 诊断结果通过 ws_manager.broadcast_alarm() 推送，消息格式: `{"action": "diagnosis_result", "alarm_id": ..., "alarm_no": ..., "causes": [...]}`
- _history_stats 缓存每 30 分钟刷新一次，避免每次诊断都查库
- _rule_cache 使用 copy-on-write 模式，规则变更时原子替换

### 置信度计算要点

- 最终置信度 = min(100, round(base_confidence * history_factor * context_factor))
- base_confidence 来自规则定义（0-100）
- history_factor 基于最近 30 天同类告警频率（0.9-1.2）
- context_factor 基于同区域近 10 分钟关联告警（1.0-1.3）
- 所有因子相乘后取整，上限 100

### 路由顺序（重要）

- FastAPI 路由匹配是按注册顺序的
- `/reload` 和 `/stats` 必须在 `/rules/{rule_id}` 之前注册
- `/results/by-alarm/{alarm_id}` 必须在 `/results/{result_id}` 之前注册（如果有的话）
- 否则 "reload" 会被当作 rule_id 参数

### 与 Story 9-1/9-2 的关系

- 复用：事件总线订阅模式、YAML 加载模式、is_system 保护模式、copy-on-write 缓存模式
- 复用：前端 el-table + el-dialog + 系统标签模式
- 不修改：event_bus.py、linkage_engine.py、action_handlers.py、cross_confirmation.py
- 不修改：models/linkage.py、schemas/linkage.py
- 修改：main.py（lifespan 集成）、models/__init__.py（注册模型）、api/v1/__init__.py（注册路由）
- 修改：views/alarm/index.vue（集成诊断面板组件）

### 与后续 Story 的关系

- Story 9-4（联动恢复流程）：诊断结果可辅助恢复决策
- Story 9-5（事件时间线报告）：诊断结果纳入事件报告
- Story 9-7（传感器漂移检测）：漂移检测结果可作为诊断的上下文因子

### 前端模式参考

- 2.5D 样式: `@use '@/styles/mixins-25d' as *` + `@include page-list`
- 自动导入: Vue/Pinia API 无需手动 import
- API 模块: 参考 `api/modules/linkage.ts` 的结构（import request, 接口定义, API 函数）
- 表格: 使用 Element Plus `el-table` + `el-pagination`
- 对话框: `el-dialog` + `el-form`
- 路由: 参考现有 linkage 路由结构
- 组件: DiagnosisPanel 作为独立组件放在 `components/common/`，通过 Props 接收 alarmId

## Project Structure Notes

**后端新增:**
- `backend/app/models/diagnosis.py` - 3 个数据模型 (DiagnosisRule/DiagnosisResult/DiagnosisCause)
- `backend/app/schemas/diagnosis.py` - Pydantic v2 请求/响应 Schema
- `backend/app/config/diagnosis_rules.yaml` - Top 20 高频故障诊断规则 YAML
- `backend/app/services/diagnosis_service.py` - YAML 加载 + 历史统计 + 关联告警查询
- `backend/app/engines/diagnosis_engine.py` - 诊断引擎核心（规则匹配 + 置信度计算 + 结果存储）
- `backend/app/api/v1/diagnosis.py` - 12 个 REST API 端点
- `backend/tests/test_diagnosis.py` - 8 个测试用例

**后端修改:**
- `backend/app/models/__init__.py` - 注册 3 个诊断模型
- `backend/app/api/v1/__init__.py` - 注册诊断路由
- `backend/app/main.py` - lifespan 集成（YAML 同步 + 规则加载 + 事件订阅 + 历史统计定时刷新）

**前端新增:**
- `frontend/src/api/modules/diagnosis.ts` - TypeScript 接口 + 11 个 API 函数
- `frontend/src/components/common/DiagnosisPanel.vue` - 诊断结果面板组件
- `frontend/src/views/diagnosis/rules.vue` - 诊断规则管理页面

**前端修改:**
- `frontend/src/views/alarm/index.vue` - 告警详情中集成 DiagnosisPanel 组件
- `frontend/src/router/index.ts` - 新增诊断管理路由

## References

- [Source: prd.md#FR34] 基于规则和历史数据自动分析告警可能原因（Top 20 高频故障场景）
- [Source: prd.md#旅程1] 智能诊断模块给出三个可能原因（空调故障/门未关/负载突增）
- [Source: prd.md#成功指标] 智能诊断覆盖 Top 20 高频故障场景，准确率 >= 80%
- [Source: architecture.md#2.3] 后端分层 - engines/ 目录
- [Source: architecture.md#7.1] 联动引擎架构 - 事件总线
- [Source: architecture.md#7.5] 联动策略配置方式 - YAML 预定义 + DB 自定义
- [Source: architecture.md#9.5] 故障影响分析
- [Source: epics.md#9.3] Story 定义和 Acceptance Criteria
- [Source: 9-1-linkage-engine-core-framework.md] 事件总线、联动引擎、engines/ 目录模式
- [Source: 9-2-fire-protection-tiered-linkage-strategy.md] YAML 加载、交叉确认、重试机制模式

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
