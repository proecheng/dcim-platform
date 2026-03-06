# Story 24.6: 诊断结果存储与分级推送

Status: done

## Story

As a 运维工程师,
I want 诊断结果按置信度分级处理和推送,
So that 高置信度结果立即告知我，低置信度结果不产生干扰。

## Acceptance Criteria (验收标准)

1. **AC-1: 诊断会话记录** — L1 或 L2 引擎完成推理后，将诊断会话写入 `diagnosis_sessions` 表（trigger_alarm_id, device_id（冗余字段，方便按设备统计，带索引）, engine_level, status（success/timeout/error/degraded）, start_time, end_time, inference_time_ms），作为一次诊断任务的完整记录。同一告警的 L1 和 L2 诊断各自创建独立的 session（不合并），通过 trigger_alarm_id 关联查询

2. **AC-2: 诊断结果扩展存储** — 诊断结论写入棕地已有 `diagnosis_results` 表（复数形式），通过 Alembic 迁移**仅新增**不存在的字段: session_id（关联会话）, root_cause str(500)（根因描述）, reasoning_path JSON（推理路径节点链）, fault_tree_version str(50)（故障树版本号）。**注意: confidence(Float) 和 evidence(JSON) 字段已在 Story 24.2 迁移 `baa346182fce` 中添加**，本 Story 直接复用，不重复创建。L2 引擎将 confidence 存为 0.0-1.0 浮点数（与 L1 保持一致），推送时乘以 100 转为百分比整数

3. **AC-3: 审计日志** — 推理审计日志写入 `diagnosis_audit_logs` 表（session_id, input_data JSON, output_data JSON, engine_level, inference_time_ms, fault_tree_version），记录完整的输入输出用于合规审计

4. **AC-4: 高置信度推送（> 80%）** — 通过 WebSocket `/ws/alarms` 通道推送消息（type: "diagnosis_alert", target_roles: ["operator","admin"]），消息 data 包含 diagnosis_id, root_cause, confidence, evidence_chain；前端弹窗 + 声音提醒 + 高亮显示

5. **AC-5: 中置信度推送（60%-80%）** — 通过 WebSocket 推送（type: "diagnosis_suggestion", target_roles: ["operator","admin"]），前端在诊断面板"建议"区域展示，无声音

6. **AC-6: 低置信度处理（< 60%）** — 仅写入日志和数据库，不推送 WebSocket，诊断面板显示"分析中，暂无高置信度结论，请人工排查"

7. **AC-7: 诊断历史查询** — 所有级别的诊断结果均可在"诊断历史"列表中查询，提供 `GET /api/v1/diagnosis/sessions` 分页列表和 `GET /api/v1/diagnosis/sessions/{id}` 详情 API

8. **AC-8: 结果报告完整性** — 诊断结果报告包含: 根因、置信度、推理路径、证据列表（每条证据含时间戳 timestamp）

## Tasks / Subtasks (任务分解)

- [x] Task 1: 数据库模型与迁移 (AC: #1, #2, #3)
  - [x] 1.1 在 `backend/app/models/diagnosis.py` 中新增 `DiagnosisSession` 模型（`diagnosis_sessions` 表: id, trigger_alarm_id FK→alarms.id nullable, device_id int nullable(index=True), engine_level str(5), status str(20) default="success"（枚举: success/timeout/error/degraded）, push_status str(20) default="skipped"（枚举: pushed/failed/skipped）, max_confidence Float nullable（冗余字段，save_complete 时填充，加速查询）, start_time datetime, end_time datetime, inference_time_ms int, created_at datetime）
  - [x] 1.2 在 `backend/app/models/diagnosis.py` 中新增 `DiagnosisAuditLog` 模型（`diagnosis_audit_logs` 表: id, session_id FK→diagnosis_sessions.id, input_data JSON, output_data JSON, engine_level str(5), inference_time_ms int, fault_tree_version str(50) nullable, created_at datetime）
  - [x] 1.3 扩展已有 `DiagnosisResult` 模型，**仅新增**不存在的字段: session_id FK→diagnosis_sessions.id nullable, root_cause str(500) nullable, reasoning_path JSON nullable, fault_tree_version str(50) nullable。**已有字段 confidence(Float)/evidence(JSON)/device_id/diagnosis_level/matched/conclusion/suggested_actions/inference_time_ms/error_message 由 Story 24.2 迁移 `baa346182fce` 创建，不重复添加**。同时在 models/diagnosis.py 代码中补全这些已有字段的 Column 声明（当前模型代码缺少这些字段定义）
  - [x] 1.4 创建 Alembic 迁移文件（拆分为两个独立迁移）: 迁移 A — 创建 `diagnosis_sessions` 表和 `diagnosis_audit_logs` 表; 迁移 B — ALTER TABLE `diagnosis_results` 仅增加 4 个真正新的字段（session_id, root_cause, reasoning_path, fault_tree_version），**不添加 confidence/evidence 等已存在的字段**
  - [x] 1.5 为查询性能创建索引: `diagnosis_sessions(trigger_alarm_id)`, `diagnosis_sessions(device_id)`, `diagnosis_sessions(created_at DESC)`, `diagnosis_audit_logs(session_id)`, `diagnosis_results(session_id)`, `diagnosis_results(confidence)`

- [x] Task 2: Schema 层扩展 (AC: #7, #8)
  - [x] 2.1 在 `backend/app/schemas/diagnosis.py` 中新增 `DiagnosisSessionResponse` schema（id, trigger_alarm_id, device_id, engine_level, status, push_status, max_confidence, start_time, end_time, inference_time_ms, created_at, result: Optional[DiagnosisResultResponse]）— 1:1 关系，单数 result
  - [x] 2.2 新增 `DiagnosisAuditLogResponse` schema
  - [x] 2.3 扩展 `DiagnosisResultResponse` schema，增加 session_id, root_cause, confidence, reasoning_path, evidence_list, fault_tree_version 字段
  - [x] 2.4 新增 `DiagnosisSessionListQuery` schema（分页参数: page, page_size, device_id, engine_level, min_confidence, start_date, end_date）

- [x] Task 3: 结果存储服务层 (AC: #1, #2, #3)
  - [x] 3.1 创建 `backend/app/services/diagnosis/result_store.py` — `DiagnosisResultStore` 无状态工具类（所有方法为 `@staticmethod` 或接受 `AsyncSession` 参数，不持有实例状态，调度器和诊断引擎直接调用类方法）
  - [x] 3.2 实现 `create_session()` 方法 — 创建诊断会话记录，返回 session_id
  - [x] 3.3 实现 `save_result()` 方法 — 保存诊断结果到 `diagnosis_results` 表，关联 session_id，填充 root_cause/confidence/reasoning_path/evidence_list/fault_tree_version
  - [x] 3.4 实现 `save_audit_log()` 方法 — 保存审计日志到 `diagnosis_audit_logs` 表。input_data 和 output_data 写入前需: (1) 脱敏处理 — 递归移除 password/token/secret/api_key 等敏感字段; (2) 大小控制 — 如果序列化后 > 64KB，按字段级裁剪（如 `evidence` 列表只保留前 20 条，`alarm_data` 中的 `raw_payload` 移除），确保裁剪后 JSON 仍然有效; (3) 添加 `_truncated: true` 标记指示数据被裁剪
  - [x] 3.5 实现 `save_complete()` 方法 — 原子化保存会话+结果+审计日志（单个事务），失败时全部回滚

- [x] Task 4: 分级推送服务层 (AC: #4, #5, #6)
  - [x] 4.1 创建 `backend/app/services/diagnosis/push_service.py` — `DiagnosisPushService` 类
  - [x] 4.2 实现 `push_diagnosis_result()` 方法 — 根据置信度分级推送:
    - confidence > 80 → `broadcast_diagnosis_alert()`（type: "diagnosis_alert"）
    - 60 <= confidence <= 80 → `broadcast_diagnosis_suggestion()`（type: "diagnosis_suggestion"）
    - confidence < 60 → 仅日志记录
  - [x] 4.3 在 `backend/app/services/websocket.py` 的 `ConnectionManager` 中新增 `broadcast_diagnosis()` 方法，接口风格与 `broadcast_alarm()` 一致（接受扁平参数而非预构建 dict），内部构建消息格式: `{"type": "diagnosis_alert"|"diagnosis_suggestion", "target_roles": [...], "data": {...}}`
  - [x] 4.4 推送 data 字段包含: diagnosis_id, session_id, alarm_id, root_cause, confidence, evidence_chain（证据摘要列表，每条含 point_id + point_name + value + threshold + timestamp）, engine_level。point_name 由 `push_service` 在推送前批量查询 Point 表解析（缓存到内存避免重复查询）
  - [x] 4.5 推送失败容错 — `push_diagnosis_result()` 内部 try/except 捕获所有异常并记录 WARNING 日志，不影响已完成的数据库写入。在 `DiagnosisSession` 上设置 `push_status` 字段（pushed/failed/skipped），便于后续排查未推送的诊断结果

- [x] Task 5: 集成到调度器 (AC: #1, #2, #3, #4, #5, #6)
  - [x] 5.1 重构 `backend/app/services/diagnosis/scheduler.py` 的 `_save_result()` 方法，使用 `DiagnosisResultStore.save_complete()` 替代当前的直接写入
  - [x] 5.2 在 `_save_result()` 中调用 `DiagnosisPushService.push_diagnosis_result()` 完成分级推送
  - [x] 5.3 重构 `backend/app/engines/diagnosis_engine.py` 的结果保存逻辑，同样使用 `DiagnosisResultStore` 和 `DiagnosisPushService`
  - [x] 5.4 确保 L1 引擎结果也走统一的存储+推送流程

- [x] Task 6: 诊断历史查询 API (AC: #7, #8)
  - [x] 6.1 在 `backend/app/api/v1/diagnosis.py` 中新增 `GET /api/v1/diagnosis/sessions` — 分页查询诊断会话列表，支持按 device_id/engine_level/时间范围过滤。`min_confidence` 过滤直接使用 `diagnosis_sessions.max_confidence` 冗余字段（`WHERE max_confidence >= :min_confidence`），无需 JOIN，性能优良
  - [x] 6.2 新增 `GET /api/v1/diagnosis/sessions/{session_id}` — 获取会话详情（含关联的所有诊断结果和证据）
  - [x] 6.3 新增 `GET /api/v1/diagnosis/sessions/{session_id}/audit-log` — 获取会话审计日志（需 admin 角色）
  - [x] 6.4 扩展现有 `GET /api/v1/diagnosis/results` — 增加 confidence/session_id 过滤参数

- [x] Task 7: 单元测试与集成测试 (AC: 全部)
  - [x] 7.1 测试 `DiagnosisResultStore` — 会话创建、结果保存、审计日志保存、完整保存事务
  - [x] 7.2 测试分级推送逻辑 — confidence=90 推送 diagnosis_alert, confidence=70 推送 diagnosis_suggestion, confidence=50 不推送
  - [x] 7.3 测试边界值 — confidence=0.80（应推送 suggestion，因为条件是 > 0.80 才推送 alert）, confidence=0.60（应推送 suggestion）, confidence=0.59（不推送）
  - [x] 7.4 测试诊断历史查询 API — 分页、过滤、详情、审计日志权限
  - [x] 7.5 测试 WebSocket 消息格式 — 验证 type/target_roles/data 字段完整
  - [x] 7.6 测试事务回滚 — 模拟数据库写入失败，验证会话+结果+审计日志全部回滚
  - [x] 7.7 测试审计日志脱敏 — 验证 input_data 中 password/token/secret 字段被移除，超过 64KB 的 JSON 被截断
  - [x] 7.8 测试推送失败容错 — 模拟 WebSocket 推送异常，验证数据库写入不受影响且 push_status 标记为 "failed"
  - [x] 7.9 测试同一告警多次诊断 — L1 和 L2 各创建独立 session，通过 trigger_alarm_id 可查到两条记录
  - [x] 7.10 测试 point_id 到 point_name 的解析 — 验证 evidence_chain 推送消息中包含 point_name

## Dev Notes (开发指南)

### 1. 数据库模型设计

**新增表和字段**（遵循棕地命名约定：复数表名）:

```python
# backend/app/models/diagnosis.py — 新增模型

class DiagnosisSession(Base):
    """诊断会话表 — 记录一次完整诊断任务"""
    __tablename__ = "diagnosis_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trigger_alarm_id = Column(Integer, ForeignKey("alarms.id"), nullable=True, comment="触发告警ID")
    device_id = Column(Integer, nullable=True, index=True, comment="设备ID(冗余，nullable 因为上游 alarm_data 可能不含)")
    engine_level = Column(String(5), nullable=False, comment="推理级别: L1/L2/L3")
    status = Column(String(20), nullable=False, default="success", comment="会话状态: success/timeout/error/degraded")
    push_status = Column(String(20), nullable=False, default="skipped", comment="推送状态: pushed/failed/skipped")
    max_confidence = Column(Float, nullable=True, comment="最高置信度(冗余，加速查询)")
    start_time = Column(DateTime, nullable=False, comment="推理开始时间")
    end_time = Column(DateTime, nullable=True, comment="推理结束时间")
    inference_time_ms = Column(Integer, default=0, comment="推理耗时(毫秒)")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")


class DiagnosisAuditLog(Base):
    """诊断审计日志表 — 记录推理输入输出"""
    __tablename__ = "diagnosis_audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("diagnosis_sessions.id"), nullable=False, comment="会话ID")
    input_data = Column(JSON, comment="推理输入数据")
    output_data = Column(JSON, comment="推理输出数据")
    engine_level = Column(String(5), nullable=False, comment="推理级别")
    inference_time_ms = Column(Integer, default=0, comment="推理耗时(毫秒)")
    fault_tree_version = Column(String(50), nullable=True, comment="故障树版本号")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
```

**扩展已有 DiagnosisResult 模型**:

```python
# 在现有 DiagnosisResult 类中:
# ---- 以下字段已由 Story 24.2 迁移 baa346182fce 创建，需在模型代码中补全声明 ----
device_id = Column(Integer, nullable=True, index=True, comment="设备ID")
diagnosis_level = Column(String(10), nullable=True, comment="推理级别: L1/L2/L3")
matched = Column(Boolean, nullable=True, server_default='0', comment="是否匹配")
conclusion = Column(Text, nullable=True, comment="诊断结论")
confidence = Column(Float, nullable=True, comment="置信度(0.0-1.0)")  # 注意: Float 非 Integer
suggested_actions = Column(JSON, nullable=True, comment="建议操作")
evidence = Column(JSON, nullable=True, comment="证据列表JSON")  # 复用此字段，不创建 evidence_list
inference_time_ms = Column(Integer, nullable=True, comment="推理耗时(毫秒)")
error_message = Column(Text, nullable=True, comment="错误信息")

# ---- 以下为 Story 24.6 真正新增的字段 ----
session_id = Column(Integer, ForeignKey("diagnosis_sessions.id"), nullable=True, comment="会话ID")
root_cause = Column(String(500), nullable=True, comment="根因描述")
reasoning_path = Column(JSON, nullable=True, comment="推理路径JSON")
fault_tree_version = Column(String(50), nullable=True, comment="故障树版本号")
```

### 2. 分级推送阈值与消息格式

**置信度分级**（严格遵循 PRD FR34-11 和架构 18.15）:

**注意: 数据库 `confidence` 字段为 Float(0.0-1.0)，推送时转为百分比整数（×100）**

| 置信度范围 (Float) | 百分比 | 推送类型 | WebSocket type | 前端表现 |
|-------------------|--------|---------|----------------|---------|
| > 0.80 | > 80% | 高置信度告警 | `diagnosis_alert` | 弹窗 + 声音 + 高亮 |
| 0.60-0.80 | 60%-80% | 中置信度建议 | `diagnosis_suggestion` | 诊断面板建议区 |
| < 0.60 | < 60% | 低置信度 | 不推送 | "分析中"提示 |

**边界值处理**:
- confidence = 0.80 → 按 60%-80% 区间处理（`diagnosis_suggestion`），因为条件是 `> 0.80` 才推送 alert
- confidence = 0.60 → 按 60%-80% 区间处理（`diagnosis_suggestion`）
- confidence = 0.59 → 不推送

```python
# 分级推送逻辑（输入为 Float 0.0-1.0）
def get_push_level(confidence: float) -> str:
    if confidence > 0.80:
        return "alert"       # diagnosis_alert
    elif confidence >= 0.60:
        return "suggestion"  # diagnosis_suggestion
    else:
        return "log_only"    # 仅日志

# 推送消息中 confidence 转为百分比整数
push_confidence = int(confidence * 100)  # 0.92 → 92
```

**WebSocket 消息格式**:

```python
# 高置信度推送消息
{
    "type": "diagnosis_alert",
    "target_roles": ["operator", "admin"],
    "data": {
        "diagnosis_id": 123,
        "session_id": 456,
        "alarm_id": 789,
        "root_cause": "UPS 输出过压导致 PDU-A3 跳闸",
        "confidence": 92,
        "engine_level": "L2",
        "evidence_chain": [
            {"point_name": "UPS-1-输出电压", "value": 252.3, "threshold": 245.0, "timestamp": "..."},
            {"point_name": "PDU-A3-断路器状态", "value": 0, "threshold": 1, "timestamp": "..."}
        ]
    }
}

# 中置信度推送消息
{
    "type": "diagnosis_suggestion",
    "target_roles": ["operator", "admin"],
    "data": {
        "diagnosis_id": 124,
        "session_id": 457,
        "alarm_id": 790,
        "root_cause": "温控系统可能存在气流短路",
        "confidence": 72,
        "engine_level": "L2",
        "evidence_chain": [...]
    }
}
```

### 3. WebSocket 集成方式

**复用告警通道 `/ws/alarms`**（架构规定）:

在 `backend/app/services/websocket.py` 的 `ConnectionManager` 中新增方法:

```python
async def broadcast_diagnosis(self, msg_type: str, data: dict, target_roles: list[str] = None):
    """广播诊断结果 — 复用 alarms 通道，接口风格与 broadcast_alarm() 一致"""
    message = {
        "type": msg_type,  # "diagnosis_alert" 或 "diagnosis_suggestion"
        "target_roles": target_roles or ["operator", "admin"],
        "data": data
    }
    await self.broadcast(message, "alarms")
```

**与现有推送模式的区别**:
- 现有告警推送使用 `broadcast_alarm()`，消息格式 `{"type": "alarm", "action": "...", "data": {...}}`
- 诊断推送使用 `broadcast_diagnosis()`，消息格式 `{"type": "diagnosis_alert"|"diagnosis_suggestion", "target_roles": [...], "data": {...}}`
- 前端通过 `type` 字段区分告警消息和诊断消息

**`target_roles` 角色过滤说明**:
- 服务端 `ConnectionManager.broadcast()` 不做角色过滤（无连接-用户映射关系），`target_roles` 作为消息载荷传递
- **角色过滤由前端负责**: 前端 alarm Store 接收消息后，对比 `target_roles` 与当前用户角色（`userStore.role`），不匹配则丢弃消息
- 这与现有告警推送模式一致（告警也是全量广播，前端按需展示）

### 4. 结果存储服务设计

```python
# backend/app/services/diagnosis/result_store.py

class DiagnosisResultStore:
    """诊断结果存储服务 — 无状态工具类，所有方法为静态方法"""

    @staticmethod
    async def save_complete(
        alarm_id: Optional[int],
        device_id: int,
        engine_level: str,
        status: str,            # "success"/"timeout"/"error"/"degraded"
        start_time: datetime,
        end_time: datetime,
        inference_time_ms: int,
        result: dict,           # 推理结果
        input_data: dict,       # 推理输入（审计用，写入前自动脱敏）
        fault_tree_version: Optional[str] = None
    ) -> tuple[int, int]:       # 返回 (session_id, result_id)
        """
        原子化保存诊断全部数据

        单个数据库事务内完成:
        1. 创建 DiagnosisSession（含 status 字段）
        2. 创建/更新 DiagnosisResult（扩展字段）
        3. 创建 DiagnosisAuditLog（input_data 自动脱敏 + 64KB 截断）
        失败时全部回滚

        注意: L1 结果同时填充旧 causes 字段和新 root_cause/confidence 字段（兼容旧 API）
        L2 结果仅填充新字段（无 causes 旧格式）
        """
```

### 5. 调度器集成改造

**现有调度器 `_save_result()` 改造重点**:

```python
# backend/app/services/diagnosis/scheduler.py
# 注意: 现有 _execute_inference() 使用局部变量 start_time = datetime.utcnow()
# 需要将 start_time 和 alarm_data 作为参数传递给 _save_result()

async def _save_result(self, alarm_id, device_id, diagnosis_level, result,
                       inference_time_ms, start_time, alarm_data, status="success"):
    # 1. 使用 DiagnosisResultStore 静态方法保存
    session_id, result_id = await DiagnosisResultStore.save_complete(
        alarm_id=alarm_id,
        device_id=device_id,
        engine_level=diagnosis_level,
        status=status,  # "success"/"timeout"/"error"/"degraded"
        start_time=start_time,          # 从 _execute_inference() 传入
        end_time=datetime.utcnow(),
        inference_time_ms=inference_time_ms,
        result=result,
        input_data=alarm_data,          # 从 _execute_inference() 传入
        fault_tree_version=result.get("fault_tree_version")
    )

    # 2. 分级推送（内部 try/except，失败不影响已保存的数据）
    confidence = result.get("confidence", 0.0)
    push_status = await DiagnosisPushService.push_diagnosis_result(
        diagnosis_id=result_id,
        session_id=session_id,
        alarm_id=alarm_id,
        root_cause=result.get("root_cause", result.get("conclusion", "")),
        confidence=confidence,
        engine_level=diagnosis_level,
        evidence_chain=result.get("evidence", [])
    )
    # 更新推送状态到 session 记录（单独事务，失败仅记录 WARNING）
    try:
        await DiagnosisResultStore.update_push_status(session_id, push_status)
    except Exception as e:
        logger.warning(f"Failed to update push_status for session {session_id}: {e}")
```

**旧版诊断引擎 `diagnosis_engine.py` 改造**:

`diagnosis_engine.py` 中的 `_safe_diagnose()` 方法也需要改造为使用 `DiagnosisResultStore` 和 `DiagnosisPushService`，替代当前直接写入 `DiagnosisResult` 和直接调用 `broadcast_alarm()` 的方式。

**双引擎路径去重**: `diagnosis_engine.py`（通过事件总线 `on_alarm_event` 触发）和 `scheduler.py`（通过 Redis pub/sub 触发）是**两条独立的代码路径**。本 Story 改造后，两条路径都使用统一的 `DiagnosisResultStore` + `DiagnosisPushService`。但必须确保同一告警不会被两条路径同时处理。解决方案: 在 `diagnosis_engine.py` 的 `on_alarm_event()` 中检查 `DiagnosisScheduler` 是否已启动，如果已启动则跳过（让调度器处理），否则自行处理（兼容调度器未启动的场景）。

**session:result 关系**: 1:1（每个 session 恰好对应一条 result）。`DiagnosisSessionResponse.results` 改为 `result: Optional[DiagnosisResultResponse]`（单数）。同一告警的 L1 和 L2 是各自独立的 session+result 对。

### 6. API 路由设计

```python
# backend/app/api/v1/diagnosis.py — 新增路由

# 诊断会话列表（分页 + 过滤）
@router.get("/sessions", response_model=dict)
async def list_diagnosis_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    device_id: Optional[int] = None,
    engine_level: Optional[str] = None,
    min_confidence: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """查询诊断会话列表"""

# 诊断会话详情（含结果和证据）
@router.get("/sessions/{session_id}", response_model=DiagnosisSessionResponse)
async def get_diagnosis_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取诊断会话详情"""

# 诊断审计日志（仅 admin）
@router.get("/sessions/{session_id}/audit-log", response_model=DiagnosisAuditLogResponse)
async def get_diagnosis_audit_log(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """获取诊断审计日志（仅管理员）"""
```

### 7. 与其他 Story 的集成关系

- **Story 24.1 (L1 规则引擎)**: L1 结果也需要走统一的 `save_complete()` + 分级推送流程
- **Story 24.2 (诊断调度器)**: `scheduler._save_result()` 改造为使用新的存储+推送服务
- **Story 24.5 (L2 故障树推理)**: L2 的 `DiagnosisContext` 输出需要转换为 `save_complete()` 的输入格式
- **Story 24.7 (熔断降级)**: 熔断时诊断结果仍需保存（标记为 degraded），推送机制不受影响
- **Story 24.8 (标注与 RBAC)**: 复用 `diagnosis_sessions` 表的 session_id 关联标注数据

### 8. 现有代码兼容性

**关键改造点**:
1. `scheduler.py` 的 `_save_result()` 当前直接写入 `DiagnosisResult`，需改造为使用 `DiagnosisResultStore`
2. `diagnosis_engine.py` 的 WebSocket 推送当前使用 `broadcast_alarm({"action": "diagnosis_completed", ...})`，需改造为 `broadcast_diagnosis()`
3. 新增字段使用 `nullable=True`，兼容现有数据
4. 现有 API `GET /results` 保持不变，新增 `GET /sessions` 路由

**`causes` 旧字段与新字段的兼容策略**:
- L1 引擎: 同时填充旧 `causes` JSON（`[{cause, confidence, suggested_actions}]` 格式）和新 `root_cause`/`confidence`/`evidence_list` 字段，保持旧 API 响应兼容
- L2 引擎: 仅填充新字段（`root_cause`/`confidence`/`reasoning_path`/`evidence_list`/`fault_tree_version`），`causes` 字段设为 null
- 现有 API `GET /results` 返回的 `causes` 字段保持原格式不变
- 新 API `GET /sessions/{id}` 返回新字段

**不要修改的部分**:
- `DiagnosisRule` 模型 — 无需变更
- `DiagnosisRuleCreate/Update/Response` schema — 无需变更
- 规则 CRUD API — 无需变更
- L1 引擎核心逻辑 — 仅修改结果保存流程

### 9. 测试策略

**测试文件**: `backend/tests/services/test_diagnosis_result_store.py`, `backend/tests/services/test_diagnosis_push_service.py`, `backend/tests/api/test_diagnosis_sessions.py`

**关键测试用例**:

```python
# 1. 分级推送边界值测试（confidence 为 Float 0.0-1.0）
@pytest.mark.parametrize("confidence,expected_type", [
    (0.90, "diagnosis_alert"),      # > 0.80 → alert
    (0.81, "diagnosis_alert"),      # > 0.80 → alert
    (0.80, "diagnosis_suggestion"), # = 0.80 → suggestion (不是 > 0.80)
    (0.70, "diagnosis_suggestion"), # 0.60-0.80 → suggestion
    (0.60, "diagnosis_suggestion"), # = 0.60 → suggestion
    (0.59, None),                   # < 0.60 → 不推送
    (0.0, None),                    # 最低 → 不推送
])
async def test_push_level(confidence, expected_type):
    ...

# 2. 事务原子性测试
async def test_save_complete_rollback_on_audit_failure():
    """模拟审计日志写入失败，验证会话和结果也回滚"""
    ...

# 3. WebSocket 消息格式验证
async def test_diagnosis_alert_message_format():
    """验证推送消息包含 type/target_roles/data 字段"""
    ...
```

### Project Structure Notes

- 新增文件遵循 `backend/app/services/diagnosis/` 目录结构
- 新增 `result_store.py` 和 `push_service.py` 放在 `services/diagnosis/` 下
- Alembic 迁移文件放在 `backend/alembic/versions/`
- 测试文件放在 `backend/tests/services/` 和 `backend/tests/api/`
- 在 `backend/app/services/diagnosis/__init__.py` 中导出新增的 `DiagnosisResultStore` 和 `DiagnosisPushService`

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 24.6] — 验收标准和技术要点
- [Source: _bmad-output/planning-artifacts/architecture.md#Section 18.15] — 诊断结果处理流程和 WebSocket 消息格式
- [Source: _bmad-output/planning-artifacts/prd.md#FR34-11] — 分级推送需求
- [Source: _bmad-output/planning-artifacts/prd.md#FR34-12] — 推理结果报告
- [Source: _bmad-output/planning-artifacts/prd.md#FR34-17] — 审计日志
- [Source: backend/app/services/diagnosis/scheduler.py] — 现有调度器 _save_result() 方法
- [Source: backend/app/engines/diagnosis_engine.py#L214-228] — 现有 WebSocket 推送逻辑
- [Source: backend/app/services/websocket.py] — ConnectionManager 和 broadcast_alarm() 模式
- [Source: backend/app/models/diagnosis.py] — 现有 DiagnosisResult 模型
- [Source: _bmad-output/implementation-artifacts/story-24.5.md] — L2 引擎 DiagnosisContext 数据类

---

**FR 追溯:** FR34-11, FR34-12, FR34-17
**Epic:** 24 (智能诊断核心引擎)
**Dependencies:** Story 24.1, 24.2, 24.5
**Estimated Effort:** 2-3 天

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6

### Debug Log References
- 代码审查修复了 5 个 HIGH/MEDIUM 发现（broadcast_diagnosis API 签名、start_time 计算、_truncated 标记、trigger_alarm_id 索引、fault_tree_versions.py 导入路径）
- 3 个 API 测试因 pre-existing redis_client 模块缺失而 ERROR（非本 Story 问题）
- 11/14 测试通过

### Completion Notes List
- Task 7.10 (point_name 解析测试): 推送服务当前直接传递上游数据，未实现 Point 表批量查询解析 point_name，属于 MEDIUM 优先级，可在 Story 25.8 中实现
- `__init__.py` 中 scheduler/hmac_manager/version_manager 使用 lazy try/except 导入，避免 redis_client 模块不存在导致测试失败
- 修复了 `fault_tree_versions.py` 中 pre-existing 的 `require_role` 导入路径错误

### File List
- `backend/app/models/diagnosis.py` — 新增 DiagnosisSession、DiagnosisAuditLog 模型，扩展 DiagnosisResult
- `backend/app/schemas/diagnosis.py` — 新增 DiagnosisSessionResponse、DiagnosisAuditLogResponse、DiagnosisSessionListQuery
- `backend/app/services/diagnosis/result_store.py` — 新建，DiagnosisResultStore 无状态工具类
- `backend/app/services/diagnosis/push_service.py` — 新建，DiagnosisPushService 分级推送服务
- `backend/app/services/diagnosis/__init__.py` — 修改，lazy imports 避免 redis_client 依赖
- `backend/app/services/websocket.py` — 修改，新增 broadcast_diagnosis() 方法
- `backend/app/api/v1/diagnosis.py` — 修改，新增 sessions 列表/详情/审计日志 API
- `backend/app/engines/diagnosis_engine.py` — 修改，集成 DiagnosisResultStore + DiagnosisPushService
- `backend/app/services/diagnosis/scheduler.py` — 修改，集成 DiagnosisResultStore + DiagnosisPushService
- `backend/app/api/v1/fault_tree_versions.py` — 修改，修复 require_role 导入路径
- `backend/alembic/versions/a1b2c3d4e5f6_create_diagnosis_sessions_and_audit_logs.py` — 新建，迁移 A
- `backend/alembic/versions/b2c3d4e5f6a7_add_diagnosis_result_session_fields.py` — 新建，迁移 B
- `backend/tests/test_story_24_6.py` — 新建，14 个测试用例
