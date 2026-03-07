# Story 25.4: N+X冗余拓扑与断路器保护逻辑

Status: in-progress

## Story

As a 运维工程师,
I want 诊断引擎理解冗余供电路径和断路器保护动作,
So that 系统不会将有备用路径的单点故障或正常的保护动作误判为严重故障。

## Acceptance Criteria

1. **Given** 管理员在配电拓扑中标记了冗余路径（`power_devices` 表增加 `redundancy_type` 字段: N+1/2N/NULL）
   **When** 诊断引擎分析某配电设备故障时
   **Then** 检查该设备是否有活跃的冗余备用路径（查询同一 `redundancy_group_id` 或 `circuit_id` 中 `device_type` 相同且 `is_enabled=True` 的其他设备，排除自身）
   **And** 有活跃备用路径 → 降低故障影响等级为"受控故障"，诊断结论标注"已有备用路径自动切换"
   **And** 无活跃备用路径 → 正常故障告警等级
   **And** Alembic 迁移脚本创建 `breaker_profiles` 表（breaker_device_id, trip_curve_type B/C/D, rated_current）和 `power_devices` 表新增 `redundancy_type`, `redundancy_group_id` 字段

2. **Given** 管理员在 `breaker_profiles` 表中录入了断路器特性
   **When** 出现过流告警（`alarm_type='threshold'` 且关联点位的 `point_type` 包含 'current' 或 'CURRENT'）且关联断路器设备
   **Then** 从告警事件的 `trigger_value` 获取实际电流，从 `breaker_profiles` 获取额定电流，计算过载倍数
   **And** 根据过载倍数查找 `breaker_profiles` 中的倍数-时间范围映射表判定:
   - B型: 3倍→3-45s, 5倍→0.04-0.1s
   - C型: 5倍→1.3-15s, 10倍→0.04-0.1s
   - D型: 10倍→1-8s, 50倍→0.04-0.1s
   - 介于映射点之间的倍数使用线性插值
   - 小于最小倍数时使用最小倍数的时间范围，大于最大倍数时使用最大倍数的时间范围
   **And** 从告警创建时间到当前时间计算动作时间（秒）
   **And** 动作时间在映射范围内 → 判定为"保护动作"（非故障），在诊断结果中标注"断路器保护动作正常"，不修改告警表
   **And** 动作时间异常（超出范围）→ 判定为"动作异常"，在诊断结果中标注详细说明
   **And** 过流但断路器未动作（告警持续时间 > 预期最大时间 × 2）→ 判定为"设备故障"，在诊断结果中标注"断路器故障"

## Tasks / Subtasks

- [x] Task 1: 创建数据库迁移脚本 (AC: #1, #2)
  - [x] 1.1 创建 Alembic 迁移脚本 `20260307_xxxx_add_redundancy_and_breaker_profile.py`
  - [x] 1.2 验证 `power_devices` 表是否存在 `circuit_id` 字段（Epic 8 应已创建），如不存在则报错提示前置依赖未满足
  - [x] 1.3 为 `power_devices` 表添加 `redundancy_type` 字段（VARCHAR(10), 可选值: 'N+1', '2N', NULL）
  - [x] 1.4 为 `power_devices` 表添加 `redundancy_group_id` 字段（VARCHAR(50), 可为 NULL，用于标识同一冗余组）
  - [x] 1.5 创建 `breaker_profiles` 表，字段包括:
    - id (Integer, PK)
    - breaker_device_id (Integer, FK to power_devices.id, UNIQUE)
    - trip_curve_type (VARCHAR(1), 'B'/'C'/'D')
    - rated_current (Float, 额定电流 A)
    - created_at, updated_at (DateTime)
  - [x] 1.6 添加索引: breaker_device_id (唯一索引)
  - [x] 1.7 实现 downgrade() 安全回滚逻辑（删除 breaker_profiles 表，删除 power_devices 的两个新增字段）
  - [ ] 1.8 验证迁移脚本在空数据库和已有数据的数据库上都能正常运行 [AI-Review][MEDIUM] Downgrade lacks idempotency checks

- [x] Task 2: 创建 ORM 模型和 Schema (AC: #1, #2)
  - [x] 2.1 验证 PowerDevice 模型所在文件（可能在 `backend/app/models/energy.py`），为 PowerDevice 模型添加 `redundancy_type` 和 `redundancy_group_id` 字段
  - [x] 2.2 在 `backend/app/models/diagnosis.py` 创建 `BreakerProfile` 模型
  - [x] 2.3 在 `backend/app/schemas/diagnosis.py` 创建 `BreakerProfileCreate` 和 `BreakerProfileResponse` Schema
  - [x] 2.4 添加字段验证: trip_curve_type 只能是 'B'/'C'/'D', rated_current > 0

- [x] Task 3: 实现冗余路径检测服务 (AC: #1)
  - [x] 3.1 在 `backend/app/services/diagnosis/` 创建 `redundancy_service.py`
  - [x] 3.2 实现 `check_redundancy_backup(device_id: int) -> RedundancyStatus` 函数
  - [x] 3.3 查询该设备的 `redundancy_type`, `redundancy_group_id`, `device_type`, `circuit_id`
  - [x] 3.4 如果 `redundancy_type` 为 NULL，返回 `RedundancyStatus(has_backup=False, redundancy_type=None, backup_devices=[], backup_count=0)`
  - [x] 3.5 如果有 `redundancy_group_id`，查询同组中 `device_type` 相同且 `is_enabled=True` 的其他设备（排除自身）
  - [x] 3.6 如果没有 `redundancy_group_id`，查询同 `circuit_id` 中 `device_type` 相同且 `is_enabled=True` 的其他设备（排除自身）
  - [x] 3.7 根据 `redundancy_type` 判断备用路径是否充足:
    - N+1: 至少 1 台备用设备可用（backup_count >= 1）
    - 2N: 至少与当前设备数量相等的备用设备可用（backup_count >= 同组/同回路设备总数 / 2，向上取整）
  - [x] 3.8 返回 `RedundancyStatus` 对象（has_backup: bool, backup_devices: List[int], redundancy_type: str, backup_count: int）
  - [ ] 3.9 添加单元测试验证各种冗余场景 [AI-Review][HIGH] Tests use wrong field names, non-functional
  - [x] 3.10 添加异常处理：数据库查询失败时记录错误日志，返回 `RedundancyStatus(has_backup=False, error="Database query failed", backup_devices=[], backup_count=0)`

- [x] Task 4: 实现断路器保护动作判定服务 (AC: #2)
  - [ ] 4.1 在 `backend/app/services/diagnosis/` 创建 `breaker_service.py`
  - [ ] 4.2 定义断路器脱扣曲线常量 `BREAKER_CURVES`:
    ```python
    BREAKER_CURVES = {
        'B': [(3, 3, 45), (5, 0.04, 0.1)],      # (倍数, 最小时间s, 最大时间s)
        'C': [(5, 1.3, 15), (10, 0.04, 0.1)],
        'D': [(10, 1, 8), (50, 0.04, 0.1)]
    }
    ```
  - [ ] 4.3 实现 `interpolate_trip_time(curve_type: str, overload_ratio: float) -> Tuple[float, float]` 函数
  - [ ] 4.4 使用线性插值计算介于映射点之间的倍数对应的时间范围
  - [ ] 4.5 处理边界情况：overload_ratio < 最小倍数时使用最小倍数的时间范围，> 最大倍数时使用最大倍数的时间范围
  - [ ] 4.6 实现 `check_breaker_action(alarm: Alarm) -> BreakerActionResult` 函数
  - [ ] 4.7 从告警对象获取 `point_id`，查询点位关联的 `power_device_id`（通过 `power_devices.current_point_id` 反向查询）
  - [ ] 4.8 从 `breaker_profiles` 表查询断路器特性，如果不存在则返回 `BreakerActionResult(action_type="no_breaker_config")`
  - [ ] 4.9 从告警的 `trigger_value` 获取实际电流，计算过载倍数 = trigger_value / rated_current
  - [ ] 4.10 调用 `interpolate_trip_time` 获取预期时间范围 (min_time, max_time)
  - [ ] 4.11 计算动作时间 = (当前时间 - alarm.created_at).total_seconds()
  - [ ] 4.12 判定动作是否正常:
    - 动作时间在 [min_time, max_time] 范围内 → "保护正常动作"（confidence=0.95）
    - 动作时间 < min_time → "动作过快，可能误动作"（confidence=0.7）
    - 动作时间 > max_time 且 < max_time × 2 → "动作过慢，断路器老化"（confidence=0.8）
    - 动作时间 > max_time × 2 → "断路器故障，未动作"（confidence=0.9）
  - [ ] 4.13 返回 `BreakerActionResult` 对象（action_type: str, confidence: float, explanation: str, overload_ratio: float, expected_time_range: Tuple[float, float], actual_time: float, error: Optional[str] = None）
  - [ ] 4.14 添加单元测试验证各种曲线类型和过载倍数
  - [ ] 4.15 添加异常处理：数据库查询失败或计算异常时记录错误日志，返回 `BreakerActionResult(action_type="error", confidence=0.0, explanation="Error occurred", overload_ratio=0.0, expected_time_range=(0, 0), actual_time=0.0, error="具体错误信息")`

- [ ] Task 5: 集成到诊断引擎 (AC: #1, #2)
  - [ ] 5.1 验证 L2 故障树推理引擎文件是否存在（可能在 `backend/app/services/diagnosis/l2_fault_tree_engine.py` 或类似路径），在 `analyze_fault` 函数中集成冗余检测
  - [ ] 5.2 当诊断结果涉及配电设备故障时（通过 device_type 判断），调用 `check_redundancy_backup`
  - [ ] 5.3 验证棕地项目中告警等级枚举值（可能是 'critical', 'major', 'warning', 'info'），如果有活跃备用路径，降低故障影响等级:
    - 原等级 'critical' → 降为 'major'
    - 原等级 'major' → 降为 'warning'
    - 'warning'/'info' 不降级
  - [ ] 5.4 在诊断结论中添加标注: "已有备用路径自动切换（冗余类型: {redundancy_type}，备用设备: {backup_devices}）"
  - [ ] 5.5 验证 L1 规则引擎文件是否存在（可能在 `backend/app/services/diagnosis/l1_rule_engine.py` 或类似路径），在诊断任务中集成断路器判定（不在告警触发时立即判定，避免影响性能）
  - [ ] 5.6 当诊断任务处理过流告警时（`alarm_type='threshold'` 且点位的 `point_type` 包含 'current' 或 'CURRENT'，不区分大小写），检查是否有关联的断路器设备
  - [ ] 5.7 如果有断路器记录，调用 `check_breaker_action(alarm)` 判定动作类型
  - [ ] 5.8 如果判定为"保护正常动作"，在诊断结果的 `additional_info` 中标注"断路器保护动作正常"，不修改告警表的 `alarm_level` 字段
  - [ ] 5.9 如果判定为"动作异常"或"断路器故障"，在诊断结果的 `additional_info` 中添加详细说明
  - [ ] 5.10 在诊断结果的 `additional_info` JSON 中记录冗余检测和断路器判定结果
  - [ ] 5.11 添加 Prometheus 监控指标:
    - `diagnosis_redundancy_check_duration_seconds` (Histogram): 冗余检测耗时
    - `diagnosis_redundancy_check_total` (Counter, labels: has_backup): 冗余检测总次数
    - `diagnosis_breaker_check_duration_seconds` (Histogram): 断路器判定耗时
    - `diagnosis_breaker_action_total` (Counter, labels: action_type): 断路器动作判定总次数

- [ ] Task 6: 创建管理 API (AC: #1, #2)
  - [ ] 6.1 验证 `backend/app/api/v1/power.py` 是否存在，如不存在则创建该路由文件
  - [ ] 6.2 创建 `GET /api/v1/power/devices/{device_id}/redundancy` 查询设备冗余配置
  - [ ] 6.3 创建 `PUT /api/v1/power/devices/{device_id}/redundancy` 更新设备冗余配置（body: redundancy_type, redundancy_group_id）
  - [ ] 6.4 创建 `GET /api/v1/diagnosis/breaker-profiles` 查询所有断路器配置（支持分页，参数: page=1, page_size=20，返回: {total: int, items: List[BreakerProfileResponse]}）
  - [ ] 6.5 创建 `GET /api/v1/diagnosis/breaker-profiles/{breaker_device_id}` 查询单个断路器配置
  - [ ] 6.6 创建 `POST /api/v1/diagnosis/breaker-profiles` 创建断路器配置
  - [ ] 6.7 创建 `PUT /api/v1/diagnosis/breaker-profiles/{breaker_device_id}` 更新断路器配置
  - [ ] 6.8 创建 `DELETE /api/v1/diagnosis/breaker-profiles/{breaker_device_id}` 删除断路器配置
  - [ ] 6.9 添加 RBAC 权限控制: admin 可修改配置，operator/viewer 仅可查询
  - [ ] 6.10 在 `backend/app/api/v1/__init__.py` 中注册 power 路由（如果是新创建的）

- [ ] Task 7: 编写单元测试 (AC: #1, #2)
  - [ ] 7.1 测试冗余路径检测: N+1 有备用、N+1 无备用、2N 有备用、2N 无备用、无冗余配置
  - [ ] 7.2 测试断路器判定: B/C/D 型曲线、正常动作、动作异常、未动作
  - [ ] 7.3 测试线性插值函数: 边界值、中间值、超出范围（小于最小倍数、大于最大倍数）
  - [ ] 7.4 测试诊断引擎集成: 故障等级降级、诊断结论标注
  - [ ] 7.5 测试 API 端点: CRUD 操作、权限控制、数据验证
  - [ ] 7.6 测试异常情况: 数据库连接失败、点位不存在、设备不存在
  - [ ] 7.7 测试 RedundancyStatus 和 BreakerActionResult 对象的序列化/反序列化

- [ ] Task 8: 编写集成测试 (AC: #1, #2)
  - [ ] 8.1 创建测试场景: 配置 N+1 冗余的 PDU，模拟单台故障
  - [ ] 8.2 验证诊断引擎正确识别备用路径并降低告警等级
  - [ ] 8.3 创建测试场景: 配置断路器，模拟过流告警
  - [ ] 8.4 验证断路器判定逻辑正确识别保护动作
  - [ ] 8.5 验证诊断结果中包含完整的冗余和断路器信息
  - [ ] 8.6 性能测试: 验证冗余检测和断路器判定耗时 < 100ms
  - [ ] 8.7 并发测试: 模拟多个诊断任务同时触发冗余检测，验证无竞态条件

## Dev Notes

### 架构参考
- **Architecture V4.0.0 Section 18.5-18.8**: 智能诊断专业扩展架构
- **Epic 25 Story 25.1**: 配电拓扑级联分析（前置依赖，复用配电拓扑图）
- **Epic 8**: 机房物理拓扑（配电拓扑数据模型）

### 技术实现要点

**1. 冗余路径检测策略**
- **冗余组标识**: 使用 `redundancy_group_id` 字符串字段标识同一冗余组（如 "PDU-GROUP-A"）
- **查询逻辑**: 优先按 `redundancy_group_id` 查询，如果为 NULL 则按 `circuit_id` 查询同类设备
- **设备状态判断**: 使用 `is_enabled=True` 判断设备可用（`power_devices` 表没有 `status` 字段）
- **N+1 判定**: 至少 1 台备用设备可用（backup_count >= 1）
- **2N 判定**: 至少与当前设备数量相等的备用设备可用（backup_count >= 同组/同回路设备总数 / 2，向上取整）
- **故障等级降级规则**:
  - critical → major（有备用路径，但仍需关注）
  - major → warning（有备用路径，影响可控）
  - warning/info 不降级

**2. 断路器脱扣曲线判定**
- **曲线类型**:
  - B型: 3-5倍额定电流脱扣（用于照明、住宅）
  - C型: 5-10倍额定电流脱扣（用于配电、电机）
  - D型: 10-50倍额定电流脱扣（用于变压器、大电机）
- **线性插值算法**:
  ```python
  def interpolate_trip_time(curve_type: str, overload_ratio: float) -> Tuple[float, float]:
      points = BREAKER_CURVES[curve_type]
      # 找到 overload_ratio 所在的区间 [point1, point2]
      # 对 min_time 和 max_time 分别进行线性插值
      # 返回 (min_time, max_time)
  ```
- **判定逻辑**:
  - 动作时间在 [min_time, max_time] 范围内 → "保护正常动作"（confidence=0.95）
  - 动作时间 < min_time → "动作过快，可能误动作"（confidence=0.7）
  - 动作时间 > max_time → "动作过慢，断路器老化"（confidence=0.8）
  - 过流但未动作 → "断路器故障"（confidence=0.9）

**3. 集成到诊断引擎**
- **L2 故障树推理**: 在 `analyze_fault` 函数中，故障分析完成后调用 `check_redundancy_backup`
- **L1 规则引擎**: 在过流告警规则中，增加断路器判定分支
- **诊断结果增强**: 在 `additional_info` JSON 中添加:
  ```json
  {
    "redundancy_check": {
      "has_backup": true,
      "redundancy_type": "N+1",
      "backup_devices": [123, 124],
      "impact_level_adjusted": "MAJOR -> WARNING"
    },
    "breaker_action": {
      "action_type": "保护正常动作",
      "confidence": 0.95,
      "overload_ratio": 6.2,
      "expected_time_range": [1.3, 15],
      "actual_time": 8.5
    }
  }
  ```

**4. 数据库设计注意事项**
- **power_devices 表**: 棕地项目中已存在（表名复数形式 `power_devices`），已有 `circuit_id` 字段（Epic 8 创建）
- **PowerDevice 模型位置**: 在 `backend/app/models/energy.py` 文件中，不是 `power.py`
- **设备状态字段**: 使用 `is_enabled` (Boolean) 判断设备可用性，没有 `status` 字段
- **breaker_profiles 表**: 新建表，使用复数形式 `breaker_profiles` 符合棕地命名约定
- **外键约束**: breaker_device_id 外键关联到 power_devices.id，设置 ON DELETE CASCADE
- **唯一约束**: breaker_device_id 唯一索引，确保一台设备只有一条断路器配置

**5. 前置依赖检查**
- Story 25.1 必须已完成，确保配电拓扑图已构建并缓存到内存
- Epic 8 必须已完成，确保 `power_devices` 表有 `circuit_id` 字段
- 冗余检测基于数据库查询，不直接使用 NetworkX 图（图用于级联分析，冗余检测用于故障等级调整）
- 注意：虽然不直接使用图，但应确保数据库查询结果与图中的拓扑关系一致

**6. 断路器动作时间数据来源**
- 动作时间 = (当前时间 - 告警创建时间).total_seconds()
- 假设：断路器动作后立即触发告警，告警创建时间即为动作时间
- 如果告警持续时间 > 预期最大时间 × 2，判定为"断路器未动作"
- 注意：不需要转换为毫秒，判定逻辑中使用秒作为单位

**7. 过流告警识别逻辑**
- 通过 `alarm_type='threshold'` 且点位的 `point_type` 包含 'current' 或 'CURRENT'（不区分大小写）
- 从告警的 `point_id` 查询点位，再通过 `power_devices.current_point_id` 反向查询关联的配电设备

**8. 告警等级枚举值**
- 棕地项目中告警等级字段为 `alarm_level` (String)，可能的值需要验证
- 假设值为小写字符串: 'critical', 'major', 'warning', 'info'
- 如果实际值不同，需要在实现时调整

**9. 断路器判定时机**
- 在诊断任务中判定，不在告警触发时立即判定，避免影响告警触发性能
- 判定结果记录到诊断结果的 `additional_info` 中，不修改告警表的 `alarm_level` 字段

**10. 测试数据准备**
- 创建测试用 PDU 设备，配置 N+1 冗余（redundancy_type='N+1', redundancy_group_id='TEST-PDU-GROUP'）
- 创建测试用断路器配置（C型曲线，额定电流 63A）
- 模拟过流告警（实际电流 315A，过载倍数 5.0，这是 C 型曲线的典型过载倍数，对应预期时间范围 1.3-15s）
- 验证断路器判定结果为"保护正常动作"

### 从 Story 25.3 学到的经验

**1. 数据库迁移最佳实践**
- 在同一迁移脚本中完成相关的表创建和配置初始化
- 使用 `conn.execute(text(...))` 执行 SQL，避免 ORM 模型依赖
- 迁移脚本中添加幂等性检查（如 `SELECT id FROM ... WHERE ...`），避免重复执行报错
- downgrade() 必须完整实现，确保可安全回滚

**2. 配置管理策略**
- 断路器脱扣曲线常量定义在代码中（`BREAKER_CURVES`），不需要存储到 `system_configs`
- 如果未来需要支持自定义曲线，可扩展 `breaker_profiles` 表添加 `custom_curve_json` 字段

**3. 服务层设计**
- 独立的服务类（`RedundancyService`, `BreakerService`），便于单元测试
- 服务函数返回结构化对象（Pydantic Model），而非字典
- 异常处理: 数据库查询失败时记录错误日志，返回默认值（如 `no_redundancy`）

**4. 诊断引擎集成**
- 在诊断流程的适当位置插入检测逻辑，避免影响主流程性能
- 冗余检测在故障分析完成后执行（后处理）
- 断路器判定在告警触发时执行（前置判断）
- 所有增强信息记录到 `additional_info` JSON，不修改核心诊断结果结构

**5. API 设计**
- 冗余配置 API 放在 `/api/v1/power/devices/{device_id}/redundancy`（属于设备管理）
- 断路器配置 API 放在 `/api/v1/diagnosis/breaker-profiles`（属于诊断配置）
- 遵循 RESTful 规范: GET 查询, POST 创建, PUT 更新, DELETE 删除
- RBAC 权限控制: admin 可修改, operator/viewer 仅可查询

### 潜在风险与缓解措施

**风险1: 配电拓扑数据不完整**
- **缓解**: 在冗余检测前验证 `redundancy_type` 和 `circuit_id` 字段是否为 NULL
- **降级**: 如果数据不完整，跳过冗余检测，使用原始故障等级

**风险2: 断路器配置缺失**
- **缓解**: 在断路器判定前检查 `breaker_profiles` 表是否有记录
- **降级**: 如果无配置，跳过断路器判定，使用原始告警逻辑

**风险3: 线性插值边界情况**
- **缓解**: 在插值函数中处理边界情况（overload_ratio 小于最小倍数或大于最大倍数）
- **策略**: 小于最小倍数时使用最小倍数的时间范围，大于最大倍数时使用最大倍数的时间范围
- **实现**: Task 4.5 明确要求实现边界处理逻辑

**风险4: 性能影响**
- **缓解**: 冗余检测和断路器判定都是轻量级操作（单次数据库查询 + 简单计算）
- **监控**: 添加 Prometheus 指标监控检测耗时（Task 5.11），确保 < 100ms
- **验证**: Task 8.6 性能测试验证耗时要求

**风险5: 告警等级枚举值不匹配**
- **缓解**: Task 5.3 要求验证棕地项目中实际的告警等级枚举值
- **降级**: 如果枚举值不匹配，记录警告日志，跳过等级降级，使用原始等级

**风险6: 点位与设备关联关系缺失**
- **缓解**: Task 4.7 通过 `power_devices.current_point_id` 反向查询，如果关联不存在则跳过断路器判定
- **降级**: 记录警告日志"Point X not associated with any power device"，返回 `no_breaker_config`

## Project Structure Notes

### 新增文件
```
backend/app/
├── models/
│   └── diagnosis.py                          # 新增 BreakerProfile 模型
├── schemas/
│   └── diagnosis.py                          # 新增 BreakerProfile Schema
├── services/diagnosis/
│   ├── redundancy_service.py                 # 新增冗余检测服务
│   └── breaker_service.py                    # 新增断路器判定服务
├── api/v1/
│   ├── power.py                              # 扩展冗余配置 API
│   └── diagnosis.py                          # 扩展断路器配置 API
└── alembic/versions/
    └── 20260307_xxxx_add_redundancy_and_breaker_profile.py  # 数据库迁移脚本

backend/tests/
├── services/diagnosis/
│   ├── test_redundancy_service.py            # 冗余检测单元测试
│   └── test_breaker_service.py               # 断路器判定单元测试
└── api/
    └── test_diagnosis_breaker_api.py         # 断路器 API 集成测试
```

### 修改文件
```
backend/app/
├── models/
│   └── energy.py                             # PowerDevice 模型添加 redundancy_type, redundancy_group_id
├── services/diagnosis/
│   ├── l1_rule_engine.py (或类似文件)         # 集成断路器判定
│   └── l2_fault_tree_engine.py (或类似文件)   # 集成冗余检测
```

### 数据库表变更
```sql
-- power_devices 表新增字段（表已存在，Epic 8 创建）
ALTER TABLE power_devices ADD COLUMN redundancy_type VARCHAR(10);
ALTER TABLE power_devices ADD COLUMN redundancy_group_id VARCHAR(50);

-- 新建 breaker_profiles 表
CREATE TABLE breaker_profiles (
    id SERIAL PRIMARY KEY,
    breaker_device_id INTEGER UNIQUE NOT NULL REFERENCES power_devices(id) ON DELETE CASCADE,
    trip_curve_type VARCHAR(1) NOT NULL CHECK (trip_curve_type IN ('B', 'C', 'D')),
    rated_current FLOAT NOT NULL CHECK (rated_current > 0),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_breaker_profiles_device_id ON breaker_profiles(breaker_device_id);
```

### 关键数据流

**冗余检测流程**:
```
诊断引擎故障分析 → 识别配电设备故障 → check_redundancy_backup(device_id)
  → 查询 power_devices (redundancy_type, redundancy_group_id, device_type, circuit_id)
  → 查询同组/同回路的备用设备 (device_type 相同, status='normal')
  → 判断备用路径是否充足 (N+1: ≥1台, 2N: ≥N台)
  → 返回 RedundancyStatus → 降低故障等级 → 更新诊断结论
```

**断路器判定流程**:
```
告警触发 (alarm_type='threshold', 点位类型=电流) → check_breaker_action(alarm)
  → 从 alarm.point_id 查询关联的 power_device_id
  → 查询 breaker_profiles (trip_curve_type, rated_current)
  → 计算过载倍数 = alarm.trigger_value / rated_current
  → 线性插值获取预期时间范围 (min_time, max_time)
  → 计算动作时间 = (now - alarm.created_at).total_seconds()
  → 判定动作类型 (正常/过快/过慢/未动作)
  → 返回 BreakerActionResult → 调整告警等级 → 更新告警消息
```

## References

- **PRD**: FR34-24 (N+X冗余拓扑), FR34-26 (断路器保护逻辑)
- **Architecture**: V4.0.0 Section 18.5-18.8 (智能诊断专业扩展)
- **Epic 25**: 智能诊断专业扩展
- **Story 25.1**: 配电拓扑级联分析（前置依赖）
- **Story 25.3**: UPS电池SOH预测（数据库迁移和服务层设计参考）

## Dev Agent Record

**Agent**: Claude Opus 4.6
**Story Created**: 2026-03-07
**Implementation Status**: in-progress
**Code Review**: 2026-03-07 (8 HIGH, 5 MEDIUM issues found)

### File List
- backend/alembic/versions/20260307_1600_add_redundancy_and_breaker_profile.py (CREATED)
- backend/app/models/diagnosis.py (MODIFIED - added BreakerProfile)
- backend/app/models/energy.py (MODIFIED - added redundancy fields)
- backend/app/schemas/diagnosis.py (MODIFIED - added breaker schemas)
- backend/app/services/diagnosis/breaker_service.py (CREATED)
- backend/app/services/diagnosis/l1_engine.py (MODIFIED - integrated checks)
- backend/app/services/diagnosis/redundancy_service.py (CREATED)
- backend/app/api/v1/diagnosis.py (MODIFIED - added breaker APIs)
- backend/tests/services/test_breaker_service.py (CREATED - needs fixes)
- backend/tests/services/test_redundancy_service.py (CREATED - needs fixes)

### Review Follow-ups (AI)
- [x] [AI-Review][HIGH] Implement missing redundancy configuration APIs (GET/PUT /api/v1/power/devices/{id}/redundancy)
- [x] [AI-Review][HIGH] Integrate redundancy detection into L2 fault tree engine
- [ ] [AI-Review][HIGH] Implement alarm level downgrade logic (critical→major, major→warning)
- [x] [AI-Review][HIGH] Fix test fixtures to use correct PowerDevice schema (device_code, device_name)
- [ ] [AI-Review][HIGH] Add integration tests (Task 8: scenarios, performance, concurrency)
- [ ] [AI-Review][HIGH] Add Prometheus duration histogram metrics
- [ ] [AI-Review][MEDIUM] Fix overcurrent alarm detection to explicitly check alarm_type='threshold'
- [ ] [AI-Review][MEDIUM] Fix 2N redundancy calculation bug (account for self-exclusion)
- [ ] [AI-Review][MEDIUM] Add idempotency checks to migration downgrade()
- [ ] [AI-Review][MEDIUM] Update breaker API RBAC (GET endpoints should use require_viewer)
- [ ] [AI-Review][LOW] Move logger initialization to module level
- [ ] [AI-Review][LOW] Extract magic number (max_time * 2) to named constant
- [ ] [AI-Review][LOW] Add comprehensive docstrings

