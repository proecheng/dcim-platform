# Story 24.8: 诊断结果标注与RBAC

**Epic**: 24 - 智能诊断核心引擎
**Story ID**: 24.8
**创建日期**: 2026-03-06
**状态**: ready-for-dev

---

## User Story

As a 运维工程师,
I want 对诊断结果进行准确性标注,
So that 系统可以积累反馈数据用于后续优化。

---

## 验收标准（Acceptance Criteria）

### 1. 标注功能

- **Given** 运维工程师查看某条诊断结果（通过 `/api/v1/diagnosis/sessions/{id}` 获取）
- **When** 点击"标注"按钮
- **Then** 可以选择"准确"、"不准确"、"未知"三种标注
- **And** 选择"不准确"时，必须从下拉列表选择或自由填写实际根因（不能为空）
- **And** 标注写入 `diagnosis_annotations` 表（复数形式，遵循棕地命名约定）：
  - session_id: 关联的诊断会话 ID（外键 → diagnosis_sessions.id）
  - annotator_id: 标注者用户 ID（外键 → users.id，允许 NULL 表示标注者已被删除）
  - annotation: 标注类型（枚举: accurate/inaccurate/unknown）
  - actual_root_cause: 实际根因（仅 annotation=inaccurate 时必填，最大 1000 字符）
  - annotated_at: 标注时间
  - notes: 可选备注（最大 2000 字符）
- **And** 同一诊断会话可被多次标注（不同用户或同一用户修改标注），每次标注创建新记录
- **And** 用户修改自己的标注时，通过再次调用 POST 创建新记录（保留历史标注记录用于审计）
- **And** 标注成功后返回 201 Created，响应包含标注 ID 和创建时间
- **And** 用户可以删除自己的标注（`DELETE /api/v1/diagnosis/annotations/{id}`，物理删除），admin 可删除任何标注
- **And** 标注删除后无法恢复，但删除操作会记录到审计日志（通过应用层日志记录 annotator_id, annotation_id, deleted_at）

### 2. 标注偏差监控

- **Given** 系统已积累一定量的标注数据（≥30 条）
- **When** APScheduler 每日凌晨 2:00 执行偏差检测任务
- **Then** 统计每个用户的"不准确"标注率：`inaccurate_count / total_annotations`
- **And** 根据样本量选择检测算法：
  - 样本量 < 100：使用绝对阈值（标注率 > 30% 触发告警）
  - 样本量 ≥ 100：使用 P95 百分位数（对所有用户的标注率排序，取第 95 百分位值作为阈值）
- **And** 触发告警时：
  - 通过 WebSocket `/ws/system` 推送消息（type: "annotation_anomaly", target_roles: ["admin"]）
  - 同时写入 `system_notifications` 表（复用棕地已有表，确保管理员登录后能看到历史告警）
  - 告警内容：用户名、标注率、检测阈值、偏差倍数（计算公式：`(user_rate - threshold) / threshold`）
  - 记录到系统日志（WARNING 级别）
- **And** 全局标注数 < 30 时，任务记录日志"Insufficient annotations for anomaly detection (N < 30)"并跳过检测
- **And** 任务执行失败时（如数据库连接失败），捕获异常并记录错误日志，不影响后续定时执行
- **And** 多实例部署时，使用 Redis 分布式锁（`SETNX diagnosis:anomaly_detection_lock`，TTL 300 秒）确保只有一个实例执行任务

### 3. 诊断结果分级展示（RBAC）

- **Given** 用户请求诊断结果详情（`GET /api/v1/diagnosis/sessions/{id}`）
- **When** 系统根据用户角色过滤返回字段
- **Then** 分级展示规则如下：
  - **viewer（只读用户）**: 仅返回基础信息
    - session_id, device_id, engine_level, status
    - conclusion（结论文本，从 diagnosis_results 表关联查询）
    - suggested_actions（建议操作列表，从 diagnosis_results 表关联查询）
    - confidence_level（置信度等级：high/medium/low，后端从 diagnosis_results.confidence 映射：[0.8, 1.0]→high, [0.6, 0.8)→medium, [0, 0.6)→low）
    - start_time, end_time
  - **operator（运维）**: 完整推理信息
    - viewer 的所有字段
    - confidence（原始置信度数值）
    - reasoning_path（推理路径 JSON）
    - evidence（证据列表 JSON）
    - root_cause（根因节点）
    - fault_tree_version（故障树版本）
  - **admin（管理员）**: 全部信息
    - operator 的所有字段
    - audit_log（审计日志对象，从 diagnosis_audit_log 表关联查询：input_data, output_data, inference_time_ms）
    - annotations（标注列表数组，从 diagnosis_annotations 表关联查询：id, annotator_name, annotation, actual_root_cause, annotated_at, notes）
    - push_status（推送状态）
- **And** 角色判断使用 `request.state.user.role`（复用棕地已有三角色体系 admin/operator/viewer）
- **And** 未授权访问返回 403 Forbidden

### 4. RBAC 权限控制

- **Given** 用户尝试访问诊断相关 API
- **When** 系统检查用户角色
- **Then** 权限规则如下：
  - **查看诊断结果列表/详情**: viewer+ (viewer, operator, admin)
  - **标注诊断结果**: operator+ (operator, admin)
  - **查看标注列表**: operator 可查看自己的标注（传入其他用户 ID 返回 403），admin 可查看所有标注
  - **删除标注**: operator 可删除自己的标注（删除其他用户标注返回 403），admin 可删除任何标注
  - **查看标注统计**: admin
  - **编辑故障树**: admin
  - **审批故障树变更**: admin
  - **查看审计日志**: admin
  - **触发手动诊断**: operator+
  - **查看健康检查**: admin
- **And** 权限检查复用 `backend/app/api/deps.py` 的依赖注入：
  - `require_viewer = Depends(get_current_user)` （所有已登录用户）
  - `require_operator = Depends(lambda user=Depends(get_current_user): check_role(user, ["operator", "admin"]))`
  - `require_admin = Depends(lambda user=Depends(get_current_user): check_role(user, ["admin"]))`
- **And** 未授权访问返回 403 Forbidden，响应包含清晰的错误信息："需要 {required_role} 角色"

---

## 技术实现要点

### 1. 数据库表结构

**新建表: diagnosis_annotations（复数形式）**

```sql
CREATE TABLE diagnosis_annotations (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES diagnosis_sessions(id) ON DELETE CASCADE,
    annotator_id INTEGER REFERENCES users(id) ON DELETE SET NULL,  -- 允许 NULL（标注者已删除）
    annotation VARCHAR(20) NOT NULL CHECK (annotation IN ('accurate', 'inaccurate', 'unknown')),
    actual_root_cause TEXT,  -- 仅 annotation='inaccurate' 时必填
    notes TEXT,
    annotated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT check_actual_root_cause CHECK (
        annotation != 'inaccurate' OR actual_root_cause IS NOT NULL
    ),
    CONSTRAINT check_actual_root_cause_length CHECK (
        actual_root_cause IS NULL OR length(actual_root_cause) <= 1000
    ),
    CONSTRAINT check_notes_length CHECK (
        notes IS NULL OR length(notes) <= 2000
    )
);

CREATE INDEX idx_annotations_session ON diagnosis_annotations(session_id);
CREATE INDEX idx_annotations_annotator ON diagnosis_annotations(annotator_id);
CREATE INDEX idx_annotations_date ON diagnosis_annotations(annotated_at);
CREATE INDEX idx_annotations_session_type ON diagnosis_annotations(session_id, annotation);  -- 复合索引，支持按会话+类型查询
```

### 2. Alembic 迁移脚本

**文件**: `backend/alembic/versions/YYYYMMDD_HHMM_add_diagnosis_annotations.py`

- 创建 `diagnosis_annotations` 表
- 创建索引
- 添加约束检查

### 3. API 端点设计

**标注 API**

```python
POST /api/v1/diagnosis/sessions/{session_id}/annotate
Headers: Authorization: Bearer <token>
Body: {
    "annotation": "accurate" | "inaccurate" | "unknown",
    "actual_root_cause": "string (optional, required if annotation=inaccurate)",
    "notes": "string (optional)"
}
Response 201: {
    "id": 123,
    "session_id": 456,
    "annotation": "inaccurate",
    "actual_root_cause": "UPS电池老化",
    "annotated_at": "2026-03-06T10:30:00Z"
}
```

**诊断结果详情 API（分级展示）**

```python
GET /api/v1/diagnosis/sessions/{id}
Headers: Authorization: Bearer <token>
Response 200: {
    # 根据用户角色返回不同字段（见 AC 3）
}
```

**标注列表 API（operator+）**

```python
GET /api/v1/diagnosis/annotations?session_id={id}&annotator_id={id}&annotation={type}&page={n}&page_size={n}
Headers: Authorization: Bearer <token>
Response 200: {
    "total": 100,
    "page": 1,
    "page_size": 20,
    "items": [...]
}
# 权限：
# - operator 只能查看自己的标注，传入其他用户 ID 返回 403 Forbidden
# - admin 可查看所有标注
# - 默认分页：page=1, page_size=20
```

**标注删除 API（operator+）**

```python
DELETE /api/v1/diagnosis/annotations/{id}
Headers: Authorization: Bearer <token>
Response 204: No Content
# 权限：
# - operator 只能删除自己的标注，尝试删除其他用户标注返回 403 Forbidden
# - admin 可删除任何标注
# - 物理删除，删除操作记录到应用层审计日志
```

**标注统计 API（admin）**

```python
GET /api/v1/diagnosis/annotations/stats?start_date={date}&end_date={date}&top_n={n}
Headers: Authorization: Bearer <token>
Response 200: {
    "total_annotations": 500,
    "by_type": {
        "accurate": 350,
        "inaccurate": 120,
        "unknown": 30
    },
    "by_user": [
        {"user_id": 1, "username": "admin", "total": 100, "inaccurate_rate": 0.15},
        ...
    ],  # 按标注数降序，最多返回 top_n 个用户（默认 50）
    "top_root_causes": [
        {"root_cause": "UPS电池老化", "count": 25},
        ...
    ]  # 最多返回 top_n 个根因（默认 20）
}
```

### 4. 偏差检测定时任务

**文件**: `backend/app/services/diagnosis/annotation_monitor.py`

```python
class AnnotationMonitor:
    @staticmethod
    async def detect_anomalies():
        """检测标注偏差异常"""
        from app.core.redis_lock import get_redis_client

        # 分布式锁，防止多实例重复执行
        redis = await get_redis_client()
        lock_key = "diagnosis:anomaly_detection_lock"
        lock_acquired = await redis.set(lock_key, "1", ex=300, nx=True)

        if not lock_acquired:
            logger.info("Another instance is running anomaly detection, skipping")
            return

        try:
            # 1. 查询所有用户的标注统计
            # 2. 根据样本量选择检测算法
            #    - 样本量 < 100: 绝对阈值 30%
            #    - 样本量 ≥ 100: P95 百分位数（对所有用户标注率排序，取第 95 百分位值）
            # 3. 识别异常用户（标注率 > 阈值）
            # 4. 计算偏差倍数：(user_rate - threshold) / threshold
            # 5. 推送 WebSocket 告警
            # 6. 写入 system_notifications 表（持久化）
        except Exception as e:
            logger.error(f"Annotation anomaly detection failed: {e}", exc_info=True)
            # 不抛出异常，确保定时任务继续执行
        finally:
            # 释放锁
            await redis.delete(lock_key)
```

**APScheduler 配置**（在 `backend/app/main.py` 的 lifespan 中）

```python
scheduler.add_job(
    AnnotationMonitor.detect_anomalies,
    trigger="cron",
    hour=2,
    minute=0,
    id="annotation_anomaly_detection"
)
```

### 5. RBAC 权限依赖注入

**文件**: `backend/app/api/deps.py`（扩展现有代码）

```python
def check_role(user: User, allowed_roles: list[str]):
    """检查用户角色是否在允许列表中"""
    if user.role not in allowed_roles:
        raise HTTPException(
            status_code=403,
            detail=f"需要 {'/'.join(allowed_roles)} 角色"
        )
    return user

def require_operator(user: User = Depends(get_current_user)):
    return check_role(user, ["operator", "admin"])

def require_admin(user: User = Depends(get_current_user)):
    return check_role(user, ["admin"])
```

### 6. 分级展示逻辑

**文件**: `backend/app/api/v1/diagnosis.py`

```python
@router.get("/sessions/{session_id}")
async def get_diagnosis_session(
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # 1. 根据用户角色使用 load_only() 和关联查询
    # 2. 所有角色都需要关联查询 diagnosis_results 获取 conclusion, suggested_actions, confidence
    # 3. 返回分级数据

    if user.role == "viewer":
        # viewer 需要 session 基础字段 + result 的 conclusion, suggested_actions, confidence
        stmt = select(DiagnosisSession).options(
            load_only(
                DiagnosisSession.id,
                DiagnosisSession.device_id,
                DiagnosisSession.engine_level,
                DiagnosisSession.status,
                DiagnosisSession.start_time,
                DiagnosisSession.end_time
            ),
            joinedload(DiagnosisSession.result).load_only(
                DiagnosisResult.conclusion,
                DiagnosisResult.suggested_actions,
                DiagnosisResult.confidence
            )
        ).where(DiagnosisSession.id == session_id)

        session = await db.execute(stmt)
        session = session.scalar_one_or_none()
        if not session:
            raise HTTPException(404, "Session not found")

        # 后端映射 confidence_level
        confidence = session.result.confidence if session.result else None
        if confidence is not None:
            if confidence >= 0.8:
                confidence_level = "high"
            elif confidence >= 0.6:
                confidence_level = "medium"
            else:
                confidence_level = "low"
        else:
            confidence_level = None

        return {
            "session_id": session.id,
            "device_id": session.device_id,
            "engine_level": session.engine_level,
            "status": session.status,
            "conclusion": session.result.conclusion if session.result else None,
            "suggested_actions": session.result.suggested_actions if session.result else None,
            "confidence_level": confidence_level,
            "start_time": session.start_time,
            "end_time": session.end_time
        }
    elif user.role == "operator":
        # operator 需要更多字段，包括 result 的完整推理信息
        stmt = select(DiagnosisSession).options(
            joinedload(DiagnosisSession.result)
        ).where(DiagnosisSession.id == session_id)
        # ... 返回 operator 字段
    else:  # admin
        # admin 需要关联查询 audit_log 和 annotations
        stmt = select(DiagnosisSession).options(
            joinedload(DiagnosisSession.result),
            joinedload(DiagnosisSession.audit_log),
            joinedload(DiagnosisSession.annotations).joinedload(DiagnosisAnnotation.annotator)
        ).where(DiagnosisSession.id == session_id)
        # ... 返回 admin 字段
```

### 7. 前端集成

**标注按钮**（在诊断结果详情页）

```vue
<el-button
  v-if="userRole !== 'viewer'"
  @click="showAnnotationDialog"
>
  标注
</el-button>

<el-dialog v-model="annotationDialogVisible" title="标注诊断结果">
  <el-form>
    <el-form-item label="标注类型">
      <el-radio-group v-model="annotation.type">
        <el-radio label="accurate">准确</el-radio>
        <el-radio label="inaccurate">不准确</el-radio>
        <el-radio label="unknown">未知</el-radio>
      </el-radio-group>
    </el-form-item>
    <el-form-item
      v-if="annotation.type === 'inaccurate'"
      label="实际根因"
      required
    >
      <el-input v-model="annotation.actualRootCause" />
    </el-form-item>
    <el-form-item label="备注">
      <el-input type="textarea" v-model="annotation.notes" />
    </el-form-item>
  </el-form>
  <template #footer>
    <el-button @click="annotationDialogVisible = false">取消</el-button>
    <el-button
      type="primary"
      @click="submitAnnotation"
      :loading="submitLoading"
      :disabled="submitLoading"
    >
      提交
    </el-button>
  </template>
</el-dialog>
```

**分级展示**（根据用户角色显示不同字段）

```vue
<script setup lang="ts">
import { computed } from 'vue'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const userRole = computed(() => userStore.role)  // 从 Pinia store 获取用户角色

// ... 其他逻辑
</script>

<template>
  <div class="diagnosis-detail">
    <!-- viewer+ 可见 -->
    <el-descriptions :column="2">
      <el-descriptions-item label="结论">{{ result.conclusion }}</el-descriptions-item>
      <el-descriptions-item label="置信度等级">
        <el-tag :type="confidenceLevelType">{{ result.confidence_level }}</el-tag>
      </el-descriptions-item>
    </el-descriptions>

    <!-- operator+ 可见 -->
    <template v-if="userRole !== 'viewer'">
      <el-descriptions :column="2">
        <el-descriptions-item label="置信度">{{ result.confidence }}</el-descriptions-item>
        <el-descriptions-item label="根因">{{ result.root_cause }}</el-descriptions-item>
      </el-descriptions>
      <el-card header="推理路径">
        <reasoning-path-tree :path="result.reasoning_path" />
      </el-card>
      <el-card header="证据列表">
        <evidence-table :evidence="result.evidence" />
      </el-card>
    </template>

    <!-- admin 可见 -->
    <template v-if="userRole === 'admin'">
      <el-card header="审计日志">
        <audit-log-viewer :log="result.audit_log" />
      </el-card>
      <el-card header="标注历史">
        <annotation-list :annotations="result.annotations" />
      </el-card>
    </template>
  </div>
</template>
```

---

## 任务分解（Tasks / Subtasks）

- [ ] **Task 1**: 数据库迁移（AC: #1, #2, #3）
  - [ ] 1.1 创建 Alembic 迁移脚本
  - [ ] 1.2 定义 `diagnosis_annotations` 表结构
  - [ ] 1.3 添加索引和约束
  - [ ] 1.4 执行迁移并验证

- [ ] **Task 2**: ORM 模型和 Schema（AC: #1）
  - [ ] 2.1 创建 `DiagnosisAnnotation` ORM 模型
  - [ ] 2.2 创建 Pydantic Schema（AnnotationCreate, AnnotationResponse）
  - [ ] 2.3 添加模型关系：
    - `DiagnosisSession.result`: `relationship("DiagnosisResult", back_populates="session", lazy="joined", uselist=False)`
    - `DiagnosisSession.annotations`: `relationship("DiagnosisAnnotation", back_populates="session", lazy="select")`
    - `DiagnosisAnnotation.session`: `relationship("DiagnosisSession", back_populates="annotations")`
    - `DiagnosisAnnotation.annotator`: `relationship("User", lazy="joined")`

- [ ] **Task 3**: 标注 API 实现（AC: #1）
  - [ ] 3.1 实现 `POST /api/v1/diagnosis/sessions/{id}/annotate` 端点
  - [ ] 3.2 添加输入验证（annotation=inaccurate 时 actual_root_cause 必填，长度限制）
  - [ ] 3.3 添加权限检查（require_operator）
  - [ ] 3.4 实现标注创建逻辑
  - [ ] 3.5 实现 `DELETE /api/v1/diagnosis/annotations/{id}` 端点（权限检查：operator 只能删除自己的，尝试删除其他用户标注返回 403）
  - [ ] 3.6 实现 `GET /api/v1/diagnosis/annotations` 列表端点（权限检查：operator 传入其他用户 ID 返回 403，添加分页）
  - [ ] 3.7 实现 `GET /api/v1/diagnosis/annotations/stats` 统计端点（admin，添加 top_n 参数）
  - [ ] 3.8 添加标注删除审计日志（应用层日志记录 annotator_id, annotation_id, deleted_at）
  - [ ] 3.9 编写单元测试

- [ ] **Task 4**: 分级展示实现（AC: #3）
  - [ ] 4.1 扩展 `GET /api/v1/diagnosis/sessions/{id}` 端点
  - [ ] 4.2 实现字段过滤逻辑（viewer/operator/admin），使用 load_only() 和 joinedload() 优化查询
  - [ ] 4.3 添加 confidence_level 后端映射逻辑（从 diagnosis_results.confidence 映射）
  - [ ] 4.4 实现所有角色的 diagnosis_results 关联查询（获取 conclusion, suggested_actions, confidence）
  - [ ] 4.5 实现 admin 角色的 audit_log 和 annotations 关联查询
  - [ ] 4.6 编写单元测试（测试三种角色的返回字段和关联查询）

- [ ] **Task 5**: RBAC 权限控制（AC: #4）
  - [ ] 5.1 扩展 `backend/app/api/deps.py` 添加 `check_role` 函数
  - [ ] 5.2 创建 `require_operator` 和 `require_admin` 依赖
  - [ ] 5.3 为所有诊断 API 端点添加权限检查
  - [ ] 5.4 编写权限测试（测试未授权访问返回 403）

- [ ] **Task 6**: 偏差检测定时任务（AC: #2）
  - [ ] 6.1 创建 `AnnotationMonitor` 服务类
  - [ ] 6.2 实现 `detect_anomalies` 方法（样本量自适应算法，P95 百分位数计算）
  - [ ] 6.3 实现 Redis 分布式锁（防止多实例重复执行）
  - [ ] 6.4 在 APScheduler 中注册定时任务
  - [ ] 6.5 实现 WebSocket 告警推送
  - [ ] 6.6 实现 system_notifications 表写入（持久化告警）
  - [ ] 6.7 实现偏差倍数计算：`(user_rate - threshold) / threshold`
  - [ ] 6.8 添加异常处理和错误日志
  - [ ] 6.9 编写单元测试（模拟异常用户、边缘情况：样本量 < 100、= 100、只有一个用户、P95 计算）

- [ ] **Task 7**: 前端标注功能（AC: #1）
  - [ ] 7.1 创建标注对话框组件
  - [ ] 7.2 实现标注表单验证
  - [ ] 7.3 调用标注 API
  - [ ] 7.4 添加 loading 状态和禁用逻辑（防止重复提交）
  - [ ] 7.5 添加成功/失败提示
  - [ ] 7.6 实现标注删除功能

- [ ] **Task 8**: 前端分级展示（AC: #3）
  - [ ] 8.1 根据用户角色条件渲染字段（从 Pinia user store 获取 userRole）
  - [ ] 8.2 实现置信度等级样式映射（high→success, medium→warning, low→danger）
  - [ ] 8.3 创建推理路径树组件（operator+）
  - [ ] 8.4 创建证据列表组件（operator+）
  - [ ] 8.5 创建审计日志查看器（admin）
  - [ ] 8.6 创建标注历史列表（admin）
  - [ ] 8.7 创建标注统计面板（admin）

- [ ] **Task 9**: 集成测试（AC: #1, #2, #3, #4）
  - [ ] 9.1 测试标注完整流程（创建→查询→删除→偏差检测）
  - [ ] 9.2 测试分级展示（三种角色）
  - [ ] 9.3 测试权限控制（未授权访问、跨用户删除标注）
  - [ ] 9.4 测试偏差检测定时任务（边缘情况：标注数 30/100、所有用户标注率相同、只有一个用户）
  - [ ] 9.5 测试并发标注场景
  - [ ] 9.6 测试标注统计 API

---

## Dev Notes

### 架构模式和约束

1. **棕地命名约定**
   - 数据库表名使用复数形式：`diagnosis_annotations`（不是 `diagnosis_annotation`）
   - 遵循现有表命名模式：`diagnosis_sessions`, `diagnosis_results`, `diagnosis_audit_log`

2. **RBAC 三角色体系**
   - 复用棕地已有角色：admin/operator/viewer（不是 engineer）
   - 权限检查复用 `backend/app/api/deps.py` 的依赖注入模式

3. **异步数据库操作**
   - 使用 SQLAlchemy 2.0 异步模式
   - 所有 DB 操作使用 `async with async_session() as session`

4. **WebSocket 推送**
   - 复用现有 WebSocket 管理器 `backend/app/services/websocket.py`
   - 消息格式：`{"type": "annotation_anomaly", "target_roles": ["admin"], "data": {...}}`

5. **APScheduler 定时任务**
   - 在 `backend/app/main.py` 的 lifespan 中注册
   - 使用 cron trigger，每日凌晨 2:00 执行

### 关键文件路径

**后端**
- `backend/alembic/versions/YYYYMMDD_HHMM_add_diagnosis_annotations.py` - 数据库迁移
- `backend/app/models/diagnosis.py` - ORM 模型（扩展）
- `backend/app/schemas/diagnosis.py` - Pydantic Schema（扩展）
- `backend/app/api/v1/diagnosis.py` - API 端点（扩展）
- `backend/app/api/deps.py` - 权限依赖注入（扩展）
- `backend/app/services/diagnosis/annotation_monitor.py` - 偏差检测服务（新建）
- `backend/app/main.py` - APScheduler 配置（扩展）

**前端**
- `frontend/src/views/diagnosis/SessionDetail.vue` - 诊断结果详情页（扩展）
- `frontend/src/components/diagnosis/AnnotationDialog.vue` - 标注对话框（新建）
- `frontend/src/components/diagnosis/ReasoningPathTree.vue` - 推理路径树（新建）
- `frontend/src/components/diagnosis/EvidenceTable.vue` - 证据列表（新建）
- `frontend/src/components/diagnosis/AuditLogViewer.vue` - 审计日志查看器（新建）
- `frontend/src/components/diagnosis/AnnotationList.vue` - 标注历史列表（新建）
- `frontend/src/api/modules/diagnosis.ts` - API 调用（扩展）

**测试**
- `backend/tests/api/test_diagnosis_annotation.py` - 标注 API 测试（新建）
- `backend/tests/services/test_annotation_monitor.py` - 偏差检测测试（新建）
- `backend/tests/api/test_diagnosis_rbac.py` - RBAC 权限测试（新建）

### 测试策略

1. **单元测试**
   - 标注 API：测试三种标注类型、必填字段验证、长度限制、权限检查、删除权限
   - 分级展示：测试三种角色的返回字段过滤、load_only() 查询优化
   - 偏差检测：模拟异常用户数据，验证告警触发，测试样本量自适应算法
   - RBAC：测试未授权访问返回 403、跨用户删除标注失败
   - 标注统计：测试各种统计维度和时间范围

2. **集成测试**
   - 完整标注流程：创建标注 → 查询标注 → 删除标注 → 偏差检测 → 告警推送 → 系统内通知
   - 分级展示：不同角色用户查询同一诊断结果，验证返回字段差异和关联查询
   - 权限控制：测试所有诊断 API 端点的权限检查

3. **边缘情况**
   - 标注数 < 30 时偏差检测跳过
   - 标注数刚好 30、100 时算法切换
   - 所有用户标注率相同时不触发告警
   - 只有一个用户有标注时不触发告警
   - annotation=inaccurate 但 actual_root_cause 为空时返回 400
   - actual_root_cause 超过 1000 字符时返回 400
   - 同一会话多次标注
   - 并发标注（同一用户同时提交）
   - 标注者被删除后查询标注（annotator_id 为 NULL）
   - 偏差检测任务执行失败时的错误处理

### 性能考虑

1. **数据库索引**
   - `idx_annotations_session`: 按会话查询标注
   - `idx_annotations_annotator`: 按用户统计标注
   - `idx_annotations_date`: 偏差检测时间范围查询

2. **查询优化**
   - 偏差检测使用聚合查询，避免 N+1 问题
   - 分级展示使用 `defer()` 延迟加载不需要的字段

3. **缓存策略**
   - 用户角色信息缓存在 JWT token 中，避免每次请求查询 DB

### 安全考虑

1. **输入验证**
   - 标注类型枚举验证
   - actual_root_cause 长度限制（最大 1000 字符，数据库层面约束）
   - notes 长度限制（最大 2000 字符，数据库层面约束）
   - SQL 注入防护（使用 ORM 参数化查询）

2. **权限控制**
   - 所有 API 端点强制权限检查
   - 标注列表 API：operator 只能查看自己的标注，admin 可查看所有
   - 标注删除 API：operator 只能删除自己的标注，admin 可删除任何
   - 未授权访问返回 403，不泄露资源是否存在

3. **审计日志**
   - 所有标注操作记录 annotator_id 和 annotated_at
   - 标注删除不物理删除，而是软删除（可选实现）或保留删除日志
   - 管理员可查看完整标注历史

4. **数据完整性**
   - annotator_id 允许 NULL（标注者被删除后不影响标注记录）
   - 外键级联删除：session 删除时自动删除关联标注
   - 约束检查：annotation=inaccurate 时 actual_root_cause 必填

### 依赖关系

**前置依赖**
- Story 24.6（诊断结果存储）：提供 `diagnosis_sessions` 表
- Story 13.2（认证与会话管理）：提供用户角色体系
- Epic 5（告警管理）：提供 WebSocket 推送基础设施

**后续依赖**
- Epic 26（闭环学习）：使用标注数据进行概率调优

### 项目结构对齐

**统一项目结构**
- 后端模块：`backend/app/services/diagnosis/` 目录下新增 `annotation_monitor.py`
- 前端组件：`frontend/src/components/diagnosis/` 目录下新增标注相关组件
- API 路由：复用 `backend/app/api/v1/diagnosis.py`，不新建路由文件

**命名约定**
- Python 类名：PascalCase（`AnnotationMonitor`）
- Python 函数名：snake_case（`detect_anomalies`）
- Vue 组件名：PascalCase（`AnnotationDialog.vue`）
- API 端点：kebab-case（`/diagnosis/sessions/{id}/annotate`）

### 第一轮审查修复说明

**修复的高严重度问题（P0）**:
1. ✅ 外键约束修复：`annotator_id` 改为允许 NULL，与 `ON DELETE SET NULL` 一致
2. ✅ 标注列表 API 权限：明确 operator 只能查看自己的标注，admin 可查看所有
3. ✅ 长度限制约束：在数据库层面添加 `CHECK` 约束（actual_root_cause ≤ 1000, notes ≤ 2000）
4. ✅ 分级展示字段结构：明确 audit_log 和 annotations 是关联查询的嵌套对象

**修复的中严重度问题（P1）**:
5. ✅ 标注修改功能：明确通过再次 POST 创建新记录，保留历史用于审计
6. ✅ 偏差检测算法：改用样本量自适应算法（< 100 用绝对阈值 30%，≥ 100 用 P95）
7. ✅ 标注删除功能：添加 DELETE 端点，operator 可删除自己的，admin 可删除任何
8. ✅ WebSocket 推送失败处理：添加系统内通知持久化，确保管理员登录后能看到历史告警
9. ✅ 定时任务错误处理：添加 try-except 包裹，记录错误日志，不影响后续执行

**修复的低严重度问题（P2）**:
10. ⚠️ 并发标注竞态：暂不添加唯一索引（允许同一用户多次标注），在实施时评估是否需要
11. ✅ 分级展示查询优化：使用 SQLAlchemy `load_only()` 和 `joinedload()` 优化查询
12. ✅ 前端加载状态：添加 `submitLoading` 状态和按钮禁用逻辑
13. ✅ confidence_level 边界值：明确为 `[0.8, 1.0]→high, [0.6, 0.8)→medium, [0, 0.6)→low`
14. ✅ 标注统计 API：添加 `GET /api/v1/diagnosis/annotations/stats` 端点
15. ✅ 测试覆盖率：在 Task 9 中添加边缘情况测试用例

### 第二轮审查修复说明

**修复的高严重度问题（P0）**:
1. ✅ 系统内通知表：明确复用棕地已有 `system_notifications` 表
2. ✅ conclusion 字段来源：明确从 `diagnosis_results` 表关联查询，所有角色都需要 joinedload(result)
3. ✅ 标注删除方式：明确使用物理删除，删除操作记录到应用层审计日志
4. ✅ 偏差检测并发安全：使用 Redis 分布式锁（SETNX + TTL 300s）防止多实例重复执行

**修复的中严重度问题（P1）**:
5. ✅ P95 百分位数计算：明确对所有用户标注率排序，取第 95 百分位值
6. ✅ ORM 模型关系：明确定义 relationship() 和 lazy 加载策略
7. ✅ 标注统计 API 分页：添加 top_n 参数（by_user 默认 50，top_root_causes 默认 20）
8. ✅ 偏差倍数计算：明确公式 `(user_rate - threshold) / threshold`
9. ✅ 标注列表 API 权限：operator 传入其他用户 ID 返回 403（而非静默过滤），添加分页参数

**修复的低严重度问题（P2）**:
10. ✅ confidence_level 映射：明确在后端映射，从 diagnosis_results.confidence 获取
11. ✅ idx_annotations_type 索引：移除单独索引，改为复合索引 `(session_id, annotation)`
12. ✅ 前端 userRole 来源：明确从 Pinia user store 获取

### References

- [Source: docs/project-knowledge/architecture.md#Section 18.12 - 诊断结果标注与反馈]
- [Source: docs/project-knowledge/prd.md#FR34-18 - 诊断结果标注]
- [Source: docs/project-knowledge/prd.md#FR34-19 - 标注偏差监控]
- [Source: docs/project-knowledge/prd.md#FR34-36 - RBAC 权限控制]
- [Source: _bmad-output/planning-artifacts/epics.md#Epic 24 Story 24.8]
- [Source: backend/app/api/deps.py - 现有权限依赖注入模式]
- [Source: backend/app/services/websocket.py - WebSocket 推送服务]
- [Source: backend/app/models/diagnosis.py - 诊断相关 ORM 模型]

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References

（待实施后填写）

### Completion Notes List

（待实施后填写）

### File List

（待实施后填写）
