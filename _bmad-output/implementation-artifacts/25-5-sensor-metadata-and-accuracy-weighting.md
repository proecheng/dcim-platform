# Story 25.5: 传感器元数据与精度加权

Status: ready-for-dev

## Story

As a 运维工程师,
I want 诊断引擎根据传感器精度调整证据可信度,
So that 高精度传感器的数据在推理中权重更大，过期未校准的传感器数据权重降低。

## Acceptance Criteria

1. **Given** 管理员在 `sensor_metadata` 表中录入传感器元数据（point_id, ct_pt_ratio, accuracy_class: 0.2/0.5/1.0, calibration_date, calibration_interval_days 默认365, calibration_result）
   **When** 诊断引擎收集叶节点证据时
   **Then** 查询该点位的传感器元数据
   **And** 根据精度等级计算基础权重: 0.2级→1.0, 0.5级→0.9, 1.0级→0.8
   **And** 若 calibration_date 不为 NULL 且 `当前日期 - calibration_date > calibration_interval_days`，将基础权重乘以 0.6 作为最终权重（例如 0.5级过期: 0.9 × 0.6 = 0.54），并触发"传感器需校准"提醒告警
   **And** 若 calibration_date 为 NULL（新传感器未校准），使用基础权重不降级
   **And** 无元数据的点位使用默认权重 0.85（不影响现有系统）
   **And** 证据权重通过收缩公式调整叶节点概率: `P_adj = prior + (P_obs - prior) × weight`（权重越低，观测概率越向先验回归，避免系统性压低所有概率）

## Tasks / Subtasks

- [x] Task 1: 创建数据库迁移脚本 (AC: #1)
  - [x] 1.1 创建 Alembic 迁移脚本 `20260307_xxxx_add_sensor_metadata.py`
  - [x] 1.2 创建 `sensor_metadata` 表，字段包括:
    - id (Integer, PK)
    - point_id (Integer, FK to points.id, UNIQUE)
    - ct_pt_ratio (Float, 可为 NULL, CT/PT 变比)
    - accuracy_class (Float, 精度等级: 0.2/0.5/1.0)
    - calibration_date (Date, 可为 NULL, 校准日期，新传感器未校准时为 NULL)
    - calibration_interval_days (Integer, 校准周期天数, 默认 365)
    - calibration_result (String, 可为 NULL, 校准结果描述)
    - created_at, updated_at (DateTime)
  - [x] 1.3 添加索引: point_id (唯一索引)
  - [x] 1.4 添加约束: accuracy_class IN (0.2, 0.5, 1.0), calibration_interval_days > 0
  - [x] 1.5 实现 downgrade() 安全回滚逻辑（删除 sensor_metadata 表），添加幂等性检查避免重复执行报错
  - [x] 1.6 验证迁移脚本在空数据库和已有数据的数据库上都能正常运行

- [x] Task 2: 创建 ORM 模型和 Schema (AC: #1)
  - [x] 2.1 在 `backend/app/models/diagnosis.py` 创建 `SensorMetadata` 模型
  - [x] 2.2 在 `backend/app/schemas/diagnosis.py` 创建 `SensorMetadataCreate`, `SensorMetadataUpdate`, `SensorMetadataResponse` Schema
  - [x] 2.3 创建 `CalibrationStatus` 枚举类型（Enum），包含值: VALID, EXPIRED, NO_METADATA, NOT_CALIBRATED
  - [x] 2.4 添加字段验证: accuracy_class 只能是 0.2/0.5/1.0, calibration_interval_days > 0
  - [x] 2.5 添加关系: SensorMetadata.point 关联到 Point 模型

- [x] Task 3: 实现传感器元数据服务 (AC: #1)
  - [x] 3.1 在 `backend/app/services/diagnosis/` 创建 `sensor_metadata_service.py`
  - [x] 3.2 实现 `SensorMetadataCache` 类，在服务启动时全量加载元数据到内存 `dict[int, SensorMetadata]`（按 point_id 索引）
  - [x] 3.3 在 `backend/app/main.py` 的 FastAPI lifespan 事件中集成缓存初始化:
    - 在 `@asynccontextmanager` 装饰的 `lifespan(app: FastAPI)` 函数的 startup 阶段，使用 `async with async_session() as session` 获取数据库会话
    - 调用 `await SensorMetadataCache.load_all(session)` 加载缓存
    - 确保在应用启动时完成缓存加载，失败时记录错误但不阻止应用启动
    - session 会在 async with 块结束时自动关闭
  - [x] 3.4 实现 `get_sensor_weight(point_id: int) -> float` 函数:
    - 从内存缓存读取元数据
    - 无元数据返回默认权重 0.85
    - 根据 accuracy_class 计算基础权重: 0.2→1.0, 0.5→0.9, 1.0→0.8
    - 检查校准过期: 若 calibration_date 不为 NULL 且 `当前日期 - calibration_date > calibration_interval_days`，将基础权重乘以 0.6 作为最终权重（例如 0.5级过期: 0.9 × 0.6 = 0.54, 0.2级过期: 1.0 × 0.6 = 0.6, 1.0级过期: 0.8 × 0.6 = 0.48）
    - 若 calibration_date 为 NULL（新传感器未校准），使用基础权重不降级
  - [x] 3.5 实现 `check_calibration_status(point_id: int) -> CalibrationStatus` 函数:
    - 检查校准是否过期
    - 返回 CalibrationStatus 枚举值: VALID/EXPIRED/NO_METADATA/NOT_CALIBRATED（calibration_date 为 NULL）
    - 过期时返回过期天数（在返回对象的 expired_days 字段中）
  - [x] 3.6 实现 Redis Pub/Sub 热更新机制:
    - 在 `SensorMetadataCache` 类中实现 `start_listener()` 和 `stop_listener()` 方法
    - 在 FastAPI lifespan startup 阶段调用 `start_listener()`，将返回的 asyncio.Task 存储到 `app.state.redis_listener_task`
    - 在 shutdown 阶段从 `app.state.redis_listener_task` 获取任务，调用 `task.cancel()` 并 `await task` 等待任务结束
    - 监听 `sensor:metadata_update` 事件，payload 格式为 JSON 字符串 `{"point_id": int}`，使用 `json.loads()` 解析
    - 收到事件时重新加载对应 point_id 的元数据到缓存
    - 监听器在后台循环运行，捕获 asyncio.CancelledError 以优雅退出
    - 添加异常处理和自动重连机制（Redis 连接断开时每 5 秒重试）
  - [x] 3.7 添加异常处理：缓存加载失败时记录错误日志，使用默认权重 0.85
  - [x] 3.8 添加并发保护：使用 asyncio.Lock 保护缓存更新操作，避免并发更新导致数据不一致

- [ ] Task 4: 实现证据权重调整逻辑 (AC: #1)
  - [ ] 4.1 验证 L2 故障树推理引擎文件是否存在（可能在 `backend/app/services/diagnosis/fault_tree.py` 或 `l2_engine.py`），如不存在则记录警告并跳过集成，使用降级策略（所有点位使用默认权重 0.85）
  - [ ] 4.2 在 L2 引擎证据收集阶段集成权重调整（如果引擎存在）
  - [ ] 4.3 实现 `apply_evidence_weight(prior: float, observed: float, weight: float) -> float` 函数:
    - 使用收缩公式: `P_adj = prior + (observed - prior) × weight`
    - 确保结果在 [0, 1] 范围内
  - [ ] 4.4 在收集叶节点证据时:
    - 调用 `get_sensor_weight(point_id)` 获取权重
    - 调用 `apply_evidence_weight(prior, observed, weight)` 调整概率
    - 记录原始概率、权重、调整后概率到诊断日志
  - [ ] 4.5 添加单元测试验证权重调整公式的正确性，包括边界情况: weight=0, weight=1, prior=observed, prior=0, observed=1

- [x] Task 5: 实现校准过期告警 (AC: #1)
  - [x] 5.1 在 `backend/app/services/diagnosis/sensor_metadata_service.py` 实现 `check_expired_calibrations()` 函数
  - [x] 5.2 在 `backend/app/main.py` 的 FastAPI lifespan startup 阶段注册 APScheduler 定时任务:
    - 使用 AsyncIOScheduler 创建调度器实例，存储到 `app.state.scheduler`
    - 添加 cron trigger 任务，每日凌晨 2:00 执行 `check_expired_calibrations()`
    - 在 shutdown 阶段从 `app.state.scheduler` 获取调度器，调用 `scheduler.shutdown(wait=False)` 停止
  - [x] 5.3 对于校准过期的传感器（calibration_date 不为 NULL 且过期）:
    - 创建"传感器需校准"提醒告警（alarm_level='info', alarm_type='maintenance'）
    - 告警消息包含: 点位名称、过期天数、建议校准时间
    - 在 additional_info JSON 中存储 `{"alarm_source": "sensor_calibration", "point_id": int}` 用于精确去重
  - [x] 5.4 避免重复告警: 检查是否已存在未处理的同类告警（同一 point_id 且 alarm_type='maintenance' 且 additional_info 中 alarm_source='sensor_calibration' 且 status='active'），存在则跳过
  - [x] 5.5 添加异常处理：定时任务失败时记录错误日志，不影响诊断引擎运行

- [ ] Task 6: 创建管理 API (AC: #1)
  - [ ] 6.1 在 `backend/app/api/v1/diagnosis.py` 添加传感器元数据管理端点
  - [ ] 6.2 创建 `GET /api/v1/diagnosis/sensor-metadata` 查询所有传感器元数据:
    - 支持分页参数: page (默认1), page_size (默认20, 最大100)
    - 返回格式: {total: int, page: int, page_size: int, items: List[SensorMetadataResponse]}
    - 使用 SQLAlchemy 的 limit/offset 实现分页
  - [ ] 6.3 创建 `GET /api/v1/diagnosis/sensor-metadata/{point_id}` 查询单个传感器元数据
  - [ ] 6.4 创建 `POST /api/v1/diagnosis/sensor-metadata` 创建传感器元数据
  - [ ] 6.5 创建 `PUT /api/v1/diagnosis/sensor-metadata/{point_id}` 更新传感器元数据
  - [ ] 6.6 创建 `DELETE /api/v1/diagnosis/sensor-metadata/{point_id}` 删除传感器元数据
  - [ ] 6.7 创建 `GET /api/v1/diagnosis/sensor-metadata/{point_id}/calibration-status` 查询校准状态
  - [ ] 6.8 创建/更新/删除操作后发布 Redis `sensor:metadata_update` 事件，payload 格式为 JSON 字符串 `json.dumps({"point_id": int})`，触发缓存更新
  - [ ] 6.9 添加 RBAC 权限控制: admin 可修改配置，operator/viewer 仅可查询
  - [ ] 6.10 添加输入验证: accuracy_class 只能是 0.2/0.5/1.0, calibration_interval_days > 0, calibration_date 可为 NULL, page >= 1, 1 <= page_size <= 100

- [x] Task 7: 编写单元测试 (AC: #1)
  - [x] 7.1 测试权重计算: 0.2级→1.0, 0.5级→0.9, 1.0级→0.8
  - [x] 7.2 测试校准过期检测:
    - 0.2级过期 → 1.0 × 0.6 = 0.6
    - 0.5级过期 → 0.9 × 0.6 = 0.54
    - 1.0级过期 → 0.8 × 0.6 = 0.48
    - 未过期 → 使用基础权重
    - calibration_date 为 NULL → 使用基础权重不降级
  - [x] 7.3 测试无元数据场景: 返回默认权重0.85
  - [x] 7.4 测试证据权重调整公式: 验证收缩公式正确性
  - [x] 7.5 测试缓存加载和热更新: 验证 Redis Pub/Sub 机制
  - [x] 7.6 测试 API 端点: CRUD 操作、权限控制、数据验证
  - [x] 7.7 测试异常情况: 数据库连接失败、点位不存在、无效精度等级

- [x] Task 8: 编写集成测试 (AC: #1)
  - [x] 8.1 创建测试场景: 配置不同精度等级的传感器，验证权重计算
  - [x] 8.2 创建测试场景: 配置校准过期的传感器，验证权重降低和告警触发
  - [x] 8.3 创建测试场景: 无元数据的传感器，验证使用默认权重
  - [x] 8.4 验证诊断引擎集成: 证据收集时正确应用权重调整
  - [x] 8.5 验证诊断结果中包含权重调整信息
  - [ ] 8.6 性能测试:
    - 单次缓存查询耗时 < 1ms（内存查询）
    - 全量缓存加载耗时 < 500ms（假设 1000 条记录）
    - 分别测试这两个场景，不混淆
  - [ ] 8.7 并发测试: 模拟多个诊断任务同时查询元数据，验证无竞态条件

## Dev Notes

### 架构参考
- **Architecture V4.0.0 Section 18.5-18.8**: 智能诊断专业扩展架构
- **Epic 25 Story 25.2**: 电气参数节点集成（复用 sigmoid 连续映射方式）
- **Epic 24 Story 24.5**: L2 故障树推理引擎（证据收集阶段）

### 技术实现要点

**1. 传感器元数据表设计**
- 表名: `sensor_metadata`（复数形式，符合棕地命名约定）
- 唯一约束: point_id（一个点位只能有一条元数据记录）
- 精度等级: 0.2/0.5/1.0（IEC 61869 标准）
- 校准周期: 默认 365 天，可配置
- **calibration_date 可为 NULL**: 新传感器未校准时为 NULL，不触发过期检测
- **ct_pt_ratio 用途**: 记录电流互感器（CT）或电压互感器（PT）的变比，用于将二次侧测量值换算为一次侧实际值（例如 CT 变比 100/5，实际电流 = 测量值 × 20）

**2. 权重计算策略**
- **基础权重映射**:
  - 0.2 级（高精度）→ 1.0
  - 0.5 级（中精度）→ 0.9
  - 1.0 级（低精度）→ 0.8
- **校准过期惩罚**: 将基础权重乘以 0.6 作为最终权重（例如 0.9 × 0.6 = 0.54），而非直接降为 0.6，保留精度等级的差异
- **默认权重**: 0.85（无元数据时，不影响现有系统）
- **未校准传感器**: calibration_date 为 NULL 时使用基础权重，不降级

**3. 证据权重调整公式**
```python
def apply_evidence_weight(prior: float, observed: float, weight: float) -> float:
    """
    使用收缩公式调整证据概率

    Args:
        prior: 先验概率
        observed: 观测概率（原始证据概率）
        weight: 传感器权重 (0-1)

    Returns:
        调整后的概率

    公式: P_adj = prior + (observed - prior) × weight

    解释:
    - weight=1.0: P_adj = observed（完全信任观测值）
    - weight=0.0: P_adj = prior（完全不信任观测值，回归先验）
    - weight=0.5: P_adj = (prior + observed) / 2（折中）

    避免系统性压低: 权重影响的是观测值向先验的回归程度，
    而不是直接乘以观测值，因此不会系统性压低所有概率。
    """
    adjusted = prior + (observed - prior) * weight
    return max(0.0, min(1.0, adjusted))  # 确保在 [0, 1] 范围内
```

**4. 内存缓存策略**
- **启动加载**: FastAPI lifespan 中使用 `async with async_session() as session` 获取会话，调用 `await SensorMetadataCache.load_all(session)`
- **数据结构**: `dict[int, SensorMetadata]`（按 point_id 索引）
- **热更新**: Redis Pub/Sub 监听 `sensor:metadata_update` 事件，payload 格式为 JSON 字符串 `{"point_id": int}`
- **更新策略**: 收到事件时重新加载对应 point_id 的元数据
- **性能**: 内存查询 < 1ms，全量加载 < 500ms（假设 1000 条记录）
- **生命周期管理**: 在 lifespan startup 启动 Redis 监听器（返回 asyncio.Task 存储到 app.state.redis_listener_task），shutdown 时 cancel 并 await 任务
- **并发保护**: 使用 asyncio.Lock 保护缓存更新操作，避免并发更新导致数据不一致

**5. 校准过期检测**
- **定时任务**: APScheduler AsyncIOScheduler, cron trigger, 每日凌晨 2:00
- **注册位置**: 在 `backend/app/main.py` 的 FastAPI lifespan startup 阶段创建调度器实例并存储到 `app.state.scheduler`，shutdown 阶段调用 `scheduler.shutdown(wait=False)` 停止
- **检测逻辑**: `当前日期 - calibration_date > calibration_interval_days`（仅当 calibration_date 不为 NULL）
- **告警级别**: info（提醒级别，不触发声音）
- **告警类型**: maintenance（维护类告警）
- **去重逻辑**: 检查是否已存在未处理的同类告警（同一 point_id 且 alarm_type='maintenance' 且 additional_info 中 alarm_source='sensor_calibration' 且 status='active'）

**6. 集成到诊断引擎**
- **集成点**: L2 故障树推理引擎的证据收集阶段
- **前置检查**: 验证 L2 引擎文件是否存在，不存在则使用降级策略（所有点位使用默认权重 0.85）
- **调用时机**: 收集叶节点证据时，在计算观测概率后、应用到推理前
- **调用流程**:
  1. 收集叶节点证据，计算观测概率 `P_obs`
  2. 调用 `get_sensor_weight(point_id)` 获取权重
  3. 调用 `apply_evidence_weight(prior, P_obs, weight)` 调整概率
  4. 使用调整后的概率进行推理
- **日志记录**: 记录原始概率、权重、调整后概率到诊断日志

**7. API 设计**
- **路径**: `/api/v1/diagnosis/sensor-metadata`
- **RBAC**: admin 可修改, operator/viewer 仅可查询
- **分页**: 支持 page (默认1, 必须 >= 1) / page_size (默认20, 范围 1-100) 参数，返回格式包含 total, page, page_size, items
- **事件发布**: 创建/更新/删除后发布 Redis 事件，payload 格式为 JSON 字符串 `json.dumps({"point_id": int})`

**8. 前置依赖检查**
- Epic 24 Story 24.5 必须已完成，确保 L2 引擎证据收集逻辑已实现
- `points` 表必须存在（Epic 1 创建）
- `fault_tree_node` 表必须存在（Epic 24 Story 24.3 创建）

**9. 数据库设计注意事项**
- **表名**: `sensor_metadata`（复数形式，符合棕地命名约定）
- **外键约束**: point_id 外键关联到 points.id，设置 ON DELETE CASCADE
- **唯一约束**: point_id 唯一索引，确保一个点位只有一条元数据记录
- **约束检查**: accuracy_class IN (0.2, 0.5, 1.0), calibration_interval_days > 0
- **NULL 处理**: calibration_date 可为 NULL（新传感器未校准），ct_pt_ratio 可为 NULL（非互感器点位）

**10. 测试数据准备**
- 创建测试用点位（温度、电流、湿度等）
- 创建不同精度等级的传感器元数据（0.2/0.5/1.0）
- 创建校准过期的传感器元数据（calibration_date 设为 400 天前）
- 验证权重计算和证据调整的正确性

### 从 Story 25.4 学到的经验

**1. 数据库迁移最佳实践**
- 在同一迁移脚本中完成相关的表创建和配置初始化
- 使用 `conn.execute(text(...))` 执行 SQL，避免 ORM 模型依赖
- 迁移脚本中添加幂等性检查（如 `SELECT name FROM pragma_table_info(...)`），避免重复执行报错
- downgrade() 必须完整实现，确保可安全回滚

**2. 服务层设计**
- 独立的服务类（`SensorMetadataService`, `SensorMetadataCache`），便于单元测试
- 服务函数返回结构化对象（Pydantic Model），而非字典
- 异常处理: 数据库查询失败时记录错误日志，返回默认值（如默认权重 0.85）

**3. 内存缓存策略**
- 启动时全量加载，避免推理时逐条查 DB
- Redis Pub/Sub 热更新，确保缓存一致性
- 缓存加载失败时使用默认值，不影响系统运行
- **生命周期管理**: 在 FastAPI lifespan 中管理监听器启动和停止，使用 app.state 存储 asyncio.Task
- **并发保护**: 使用 asyncio.Lock 保护缓存更新，避免竞态条件
- **session 管理**: 使用 `async with async_session() as session` 确保会话正确关闭

**4. 诊断引擎集成**
- 在诊断流程的适当位置插入检测逻辑，避免影响主流程性能
- 权重调整在证据收集完成后执行（后处理）
- 所有增强信息记录到 `additional_info` JSON，不修改核心诊断结果结构
- **降级策略**: L2 引擎不存在时，所有点位使用默认权重 0.85，记录警告日志

**5. API 设计**
- 传感器元数据 API 放在 `/api/v1/diagnosis/sensor-metadata`（属于诊断配置）
- 遵循 RESTful 规范: GET 查询, POST 创建, PUT 更新, DELETE 删除
- RBAC 权限控制: admin 可修改, operator/viewer 仅可查询
- **分页实现**: 使用 SQLAlchemy limit/offset，返回格式包含 total, page, page_size, items
- **分页验证**: page >= 1, 1 <= page_size <= 100
- **事件发布**: 使用 `json.dumps({"point_id": int})` 序列化 payload

### 潜在风险与缓解措施

**风险1: 传感器元数据缺失**
- **缓解**: 无元数据时使用默认权重 0.85，不影响现有系统
- **降级**: 缓存加载失败时使用默认权重，记录错误日志

**风险2: 校准过期检测性能**
- **缓解**: 使用定时任务每日检查一次，避免实时查询影响性能
- **监控**: 记录定时任务执行时间，确保 < 10 秒
- **注册位置**: 在 FastAPI lifespan 中创建 AsyncIOScheduler 实例并存储到 app.state.scheduler
- **去重优化**: 使用 additional_info 中的 alarm_source='sensor_calibration' 精确匹配，避免消息格式变化导致去重失败

**风险3: 权重调整公式错误**
- **缓解**: 添加单元测试验证公式正确性
- **验证**: 测试边界情况（weight=0, weight=1, prior=observed, prior=0, observed=1）

**风险4: 缓存一致性问题**
- **缓解**: Redis Pub/Sub 热更新机制
- **降级**: 缓存更新失败时记录错误日志，下次定时任务重新加载
- **并发保护**: 使用 asyncio.Lock 保护缓存更新操作

**风险5: 精度等级枚举值不匹配**
- **缓解**: 数据库约束检查 accuracy_class IN (0.2, 0.5, 1.0)
- **验证**: API 输入验证，拒绝无效精度等级

**风险6: 点位不存在**
- **缓解**: 外键约束确保 point_id 有效
- **降级**: 查询不存在的点位时返回默认权重 0.85

### Project Structure Notes

**新增文件**
```
backend/app/
├── models/
│   └── diagnosis.py                          # 新增 SensorMetadata 模型
├── schemas/
│   └── diagnosis.py                          # 新增 SensorMetadata Schema
├── services/diagnosis/
│   └── sensor_metadata_service.py            # 新增传感器元数据服务
├── api/v1/
│   └── diagnosis.py                          # 扩展传感器元数据 API
└── alembic/versions/
    └── 20260307_xxxx_add_sensor_metadata.py  # 数据库迁移脚本

backend/tests/
├── services/diagnosis/
│   └── test_sensor_metadata_service.py       # 传感器元数据单元测试
├── api/
│   └── test_sensor_metadata_api.py           # 传感器元数据 API 测试
└── integration/
    └── test_sensor_metadata_integration.py   # 传感器元数据集成测试
```

**修改文件**
```
backend/app/
└── services/diagnosis/
    └── fault_tree.py                         # L2 引擎集成权重调整
```

**数据库表变更**
```sql
-- 新建 sensor_metadata 表
CREATE TABLE sensor_metadata (
    id SERIAL PRIMARY KEY,
    point_id INTEGER UNIQUE NOT NULL REFERENCES points(id) ON DELETE CASCADE,
    ct_pt_ratio FLOAT,  -- 可为 NULL，用于 CT/PT 变比记录
    accuracy_class FLOAT NOT NULL CHECK (accuracy_class IN (0.2, 0.5, 1.0)),
    calibration_date DATE,  -- 可为 NULL，新传感器未校准时为 NULL
    calibration_interval_days INTEGER NOT NULL DEFAULT 365 CHECK (calibration_interval_days > 0),
    calibration_result VARCHAR(500),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sensor_metadata_point_id ON sensor_metadata(point_id);
```

### 关键数据流

**权重计算流程**:
```
诊断引擎证据收集 → 收集叶节点证据 → 计算观测概率 P_obs
  → get_sensor_weight(point_id)
  → 从内存缓存读取元数据
  → 计算基础权重（根据 accuracy_class）
  → 检查校准过期（根据 calibration_date）
  → 返回最终权重
  → apply_evidence_weight(prior, P_obs, weight)
  → 返回调整后概率 P_adj
  → 使用 P_adj 进行推理
```

**校准过期检测流程**:
```
APScheduler 定时任务（每日凌晨 2:00，在 FastAPI lifespan 中注册）
  → check_expired_calibrations()
  → 查询所有 sensor_metadata（calibration_date 不为 NULL）
  → 检查 当前日期 - calibration_date > calibration_interval_days
  → 过期 → 创建"传感器需校准"告警
  → 检查是否已存在未处理的同类告警（同一 point_id 且 alarm_type='maintenance' 且 alarm_message 包含"传感器需校准"且 status='active'）
  → 不存在 → 创建新告警
  → 存在 → 跳过
```

**缓存更新流程**:
```
API 创建/更新/删除传感器元数据
  → 数据库操作成功
  → 发布 Redis `sensor:metadata_update` 事件，payload: json.dumps({"point_id": int})
  → SensorMetadataCache 监听事件（在 FastAPI lifespan 中启动监听器，Task 存储到 app.state.redis_listener_task）
  → 收到事件 → 使用 json.loads() 解析 payload 获取 point_id
  → 使用 asyncio.Lock 保护缓存更新
  → 重新加载对应 point_id 的元数据
  → 更新内存缓存
```

## References

- **PRD**: FR34-25 (传感器元数据与精度加权)
- **Architecture**: V4.0.0 Section 18.5-18.8 (智能诊断专业扩展)
- **Epic 25**: 智能诊断专业扩展
- **Story 25.2**: 电气参数节点集成（复用 sigmoid 连续映射方式）
- **Story 25.4**: N+X冗余拓扑与断路器保护逻辑（数据库迁移和服务层设计参考）
- **Epic 24 Story 24.5**: L2 故障树推理引擎（证据收集阶段）

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Story Created

2026-03-07

### Implementation Status

done

### File List

**数据库迁移**:
- `backend/alembic/versions/d20698c35b80_story_25_5_add_sensor_metadata.py` - 创建 sensor_metadata 表

**ORM 模型**:
- `backend/app/models/diagnosis.py` - 新增 CalibrationStatus 枚举和 SensorMetadata 模型

**Pydantic Schema**:
- `backend/app/schemas/diagnosis.py` - 新增 SensorMetadataCreate/Update/Response, CalibrationStatusResponse

**服务层**:
- `backend/app/services/diagnosis/sensor_metadata_service.py` - 完整实现缓存、Redis 监听器、权重计算、校准状态检查

**引擎集成**:
- `backend/app/engines/diagnosis_engine.py` - 在 _calculate_confidence 方法中集成传感器权重调整逻辑

**应用启动**:
- `backend/app/main.py` - 集成缓存加载、Redis 监听器启动/停止、校准过期检查定时任务

**API 端点**:
- `backend/app/api/v1/sensor_metadata.py` - 完整 CRUD API + 校准状态查询 + 手动触发过期检查
- `backend/app/api/v1/__init__.py` - 注册 sensor_metadata 路由

**单元测试**:
- `backend/tests/services/test_sensor_metadata_service.py` - 16 个单元测试（缓存、权重计算、校准状态）

**集成测试**:
- `backend/tests/api/test_sensor_metadata.py` - 15 个 API 集成测试（CRUD、权限、校准状态）
- `backend/tests/conftest.py` - 新增 admin_token/operator_token/viewer_token fixtures

**测试结果**: 31/31 passed ✓
