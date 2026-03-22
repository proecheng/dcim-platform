# Story 36.3: 维护建议引擎

Status: ready-for-dev

## Story

As a 运维工程师,
I want 设备健康度降至预警等级时收到维护建议，确认后自动转为维护工单,
So that 我能在设备故障前主动安排维护，减少非计划停机。

## Acceptance Criteria

1. **Given** 设备健康度评分≤40（预警/危险） **When** 健康度计算完成 **Then** 生成 MaintenanceAdvice（status=pending），包含劣化原因和建议措施
2. **Given** 同一设备已有 pending 状态的建议 **When** 再次触发 **Then** 不重复创建，更新已有建议的评分和原因
3. **Given** 运维人员点击"确认并创建工单" **When** 调用确认 API **Then** 创建 WorkOrder（type=maintenance），更新建议 status=converted，关联 work_order_id
4. **Given** 运维人员标记为误报并填写原因 **When** 调用拒绝 API **Then** 更新建议 status=rejected，记录 feedback
5. **Given** 设备健康度恢复至≥60（关注或更高） **When** 存在 pending 建议 **Then** 自动关闭建议 status=auto_closed

## Tasks / Subtasks

- [ ] Task 1: MaintenanceAdvice 数据模型 (AC: #1, #2)
  - [ ] 1.1 在 `backend/app/models/report.py` 中新增 MaintenanceAdvice 模型
  - [ ] 1.2 新建 Alembic 迁移脚本
- [ ] Task 2: MaintenanceAdvisor 服务 (AC: #1, #2, #5)
  - [ ] 2.1 新建 `backend/app/services/predictive_maintenance/advisor.py` — MaintenanceAdvisor 类
  - [ ] 2.2 `evaluate()` — 健康度≤40 时生成/更新建议（幂等）
  - [ ] 2.3 `_calc_urgency()` — 评分→紧急度映射
  - [ ] 2.4 `_generate_action()` — 基于劣化因子模板生成建议措施
  - [ ] 2.5 `auto_close_pending()` — 健康度≥60 时自动关闭 pending 建议
- [ ] Task 3: 确认/拒绝 API (AC: #3, #4)
  - [ ] 3.1 `confirm_advice()` — 确认建议 → 创建 WorkOrder
  - [ ] 3.2 `reject_advice()` — 标记误报 + 记录 feedback
- [ ] Task 4: API 端点注册 (AC: #1-#5)
  - [ ] 4.1 新建 `backend/app/api/v1/predictive_maintenance.py` — 4 个端点
  - [ ] 4.2 Pydantic Schema 定义
  - [ ] 4.3 路由注册到 `__init__.py`
- [ ] Task 5: 集成 DeviceHealthScoreCalculator (AC: #1, #5)
  - [ ] 5.1 在 `calculate_all_health_scores()` 中调用 `advisor.evaluate()` 和 `advisor.auto_close_pending()`
- [ ] Task 6: 测试 (AC: #1-#5)
  - [ ] 6.1 evaluate 生成新建议测试
  - [ ] 6.2 evaluate 幂等（更新已有 pending）测试
  - [ ] 6.3 confirm_advice 创建工单测试
  - [ ] 6.4 reject_advice 误报反馈测试
  - [ ] 6.5 auto_close_pending 自动关闭测试
  - [ ] 6.6 urgency 映射测试
  - [ ] 6.7 action 模板生成测试
  - [ ] 6.8 API 端点集成测试（列表+确认+拒绝+权限）
  - [ ] 6.9 健康度恢复后不再生成建议测试
  - [ ] 6.10 calculate_all 集成 advisor 流程测试
  - [ ] 6.11 confirm/reject 对非 pending 状态返回错误测试
  - [ ] 6.12 score=40 边界触发测试 + score=60 边界自动关闭测试

## Dev Notes

### 关键设计决策

**1. MaintenanceAdvice 数据模型：**
```python
# backend/app/models/report.py
class MaintenanceAdvice(Base):
    __tablename__ = "maintenance_advices"
    __table_args__ = (
        Index("ix_maintenance_advices_device_status", "device_id", "status"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False, comment="设备ID")
    device_name = Column(String(100), comment="设备名称")
    device_type = Column(String(50), comment="设备类型")
    health_score = Column(Float, comment="触发时健康度评分")
    urgency = Column(String(20), comment="紧急度: high/medium/low")
    reason = Column(Text, comment="劣化原因描述")
    suggested_action = Column(Text, comment="建议维护措施")
    status = Column(String(20), default="pending", nullable=False,
                    comment="状态: pending/converted/rejected/auto_closed")
    feedback = Column(Text, comment="误报反馈原因")
    work_order_id = Column(Integer, ForeignKey("work_orders.id"), nullable=True, comment="关联工单ID")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    confirmed_at = Column(DateTime, comment="确认时间")
    confirmed_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment="确认人")
```

**2. MaintenanceAdvisor 服务核心逻辑：**

`evaluate(device, health_score, degradation_result)`:
1. 检查该设备是否已有 pending 建议 → `SELECT WHERE device_id=? AND status='pending'`
2. 已有 → 更新 health_score、reason、urgency、suggested_action、updated_at
3. 没有 → 新建 MaintenanceAdvice(status="pending")，调用 `await self.db.flush()` 确保持久化
4. 返回建议对象

`auto_close_pending(device_id)`:
1. 使用条件 UPDATE：`UPDATE maintenance_advices SET status='auto_closed' WHERE device_id=? AND status='pending'`
2. 仅更新 status='pending' 的记录，避免覆盖已 converted/rejected 状态

`auto_close_pending_batch(device_ids)`:
1. 批量版本：`UPDATE ... WHERE device_id IN (...) AND status='pending'`
2. 在 calculate_all 循环结束后一次性调用，减少 N 次 UPDATE 为 1 次

**3. 紧急度映射（score≤40 时触发，所以 score=40 时 urgency=medium）：**
```python
def _calc_urgency(score: float) -> str:
    if score < 20: return "high"
    return "medium"  # 20-40 区间都是 medium（score>40 不会触发建议）
```

**4. 建议措施模板（硬编码默认值，SystemConfig 可覆盖）：**
```python
ACTION_TEMPLATES = {
    "hvac": {
        "cop_trend": "COP 持续下降，建议检查制冷剂充注量、清洗冷凝器、检查压缩机运行参数",
        "compressor_hours": "压缩机累计运行 {compressor_hours} 小时，建议安排预防性维护",
        "return_temp_trend": "回风温度上升趋势明显，建议检查设备性能、清洗过滤网",
        "default": "设备劣化评分偏低，建议安排检查",
    },
    "ups": {
        "battery_soh": "电池健康度降至 {soh}%，建议评估电池更换计划",
        "default": "UPS 设备劣化评分偏低，建议安排检查",
    },
    "pdu": {
        "default": "PDU 设备劣化评分偏低，建议安排检查",
    },
}
```
变量替换：从 `degradation_result.trend_factors` 中提取值，使用 `string.Template(tpl).safe_substitute(trend_factors)` 安全填充（缺失变量保留占位符而非抛出 KeyError）。

`reason` 字段生成：`reason = degradation_result.primary_concern or f"{device_type}设备劣化评分偏低（{health_score:.0f}分）"`

**5. confirm_advice 创建工单流程：**
```python
async def confirm_advice(self, advice_id: int, user_id: int) -> WorkOrder:
    advice = await self.db.get(MaintenanceAdvice, advice_id)
    if not advice:
        raise ValueError("建议不存在")
    if advice.status != "pending":
        raise ValueError(f"建议状态为 {advice.status}，仅 pending 状态可确认")
    # 生成工单编号：MA-YYYYMMDD-NNN（IntegrityError 重试）
    order_no = await self._generate_order_no()
    wo = WorkOrder(
        order_no=order_no,
        title=f"预防性维护: {advice.device_name} - {advice.reason[:50]}",
        description=f"劣化原因: {advice.reason}\n建议措施: {advice.suggested_action}",
        order_type=WorkOrderType.maintenance,
        priority=self._map_urgency_to_priority(advice.urgency),
        device_id=advice.device_id,
        device_name=advice.device_name,
        status=WorkOrderStatus.pending,
        reporter="系统(预测性维护)",
    )
    self.db.add(wo)
    await self.db.flush()  # 获取 wo.id
    advice.status = "converted"
    advice.work_order_id = wo.id
    advice.confirmed_at = datetime.now()
    advice.confirmed_by = user_id
    return wo
```

**工单编号格式：** `MA-YYYYMMDD-NNN`（MA 前缀区分预测性维护工单），使用 `func.count` 查询当天数量。

**紧急度 → 工单优先级映射：**
- `high` → `WorkOrderPriority.critical`（"紧急"）
- `medium` → `WorkOrderPriority.high`（"高"）

**6. API 端点设计：**

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/v1/predictive-maintenance/advices` | 列表查询（支持 status/device_type 筛选） | require_viewer |
| POST | `/api/v1/predictive-maintenance/advices/{id}/confirm` | 确认建议→创建工单 | require_operator |
| POST | `/api/v1/predictive-maintenance/advices/{id}/reject` | 标记误报 | require_operator |
| GET | `/api/v1/predictive-maintenance/advices/{id}` | 建议详情 | require_viewer |

**7. 集成 DeviceHealthScoreCalculator（修改 health_calculator.py）：**

在 `calculate_all_health_scores()` 的设备循环中：
```python
# score ≤ 40 时生成建议
if score <= 40:
    logger.warning(...)
    await advisor.evaluate(device, health_score_record, dr)
# score ≥ 60 时自动关闭
elif score >= 60:
    await advisor.auto_close_pending(device.id)
```
注意：advisor 在循环外创建一次，共享 db session。

**8. Pydantic Schema：**
```python
class MaintenanceAdviceInfo(BaseModel):
    id: int
    device_id: int
    device_name: str | None
    device_type: str | None
    health_score: float | None
    urgency: str | None
    reason: str | None
    suggested_action: str | None
    status: str
    feedback: str | None
    work_order_id: int | None
    created_at: datetime | None
    updated_at: datetime | None
    confirmed_at: datetime | None
    confirmed_by: int | None
    model_config = ConfigDict(from_attributes=True)

class AdviceRejectRequest(BaseModel):
    feedback: str = Field(..., min_length=2, max_length=500)

class AdviceConfirmResponse(BaseModel):
    advice_id: int
    work_order_id: int
    work_order_no: str
    status: str = "converted"
```

### 现有代码关键引用

| 文件 | 说明 | 关键字段/方法 |
|------|------|-------------|
| `app/models/report.py:63-81` | DeviceHealthScore 表 | score, health_level, device_id, score_factors |
| `app/models/operation.py:69-108` | WorkOrder 表 | device_id, status, priority, order_type, order_no |
| `app/models/operation.py:16-25` | WorkOrderStatus 枚举 | pending="待处理", completed="已完成" |
| `app/models/operation.py:29-35` | WorkOrderType 枚举 | maintenance="日常维护" |
| `app/models/operation.py:38-44` | WorkOrderPriority 枚举 | critical="紧急", high="高", medium="中" |
| `app/services/operation.py:40-65` | _generate_order_no() | 日期+序号格式 WO-YYYYMMDD-NNN |
| `app/services/predictive_maintenance/health_calculator.py` | DeviceHealthScoreCalculator | calculate_all_health_scores(), _upsert_health_score() |
| `app/services/predictive_maintenance/base.py` | DegradationResult | score, primary_concern, trend_factors, data_sufficiency |
| `app/services/predictive_maintenance/config.py` | DEVICE_TYPE_MAP | AC/UPS/PDU → hvac/ups/pdu |
| `app/models/device.py:21-34` | Device 表 | device_name, device_type, area_code, site_id |
| `app/api/v1/__init__.py` | 路由注册 | `api_router.include_router(...)` |

### Project Structure Notes

**新建文件清单：**
```
backend/app/services/predictive_maintenance/advisor.py      # MaintenanceAdvisor
backend/app/api/v1/predictive_maintenance.py                # 4 个 API 端点
backend/app/schemas/predictive_maintenance.py               # Pydantic Schema
backend/alembic/versions/20260322_0200_story_36_3_maintenance_advice.py
backend/tests/services/test_maintenance_advisor.py          # 10 个测试
```

**修改文件清单：**
```
backend/app/models/report.py                    # 新增 MaintenanceAdvice 模型
backend/app/services/predictive_maintenance/health_calculator.py  # 集成 advisor
backend/app/api/v1/__init__.py                  # 注册路由
```

### References

- [Source: _bmad-output/planning-artifacts/architecture.md#Section 23.4] — MaintenanceAdvisor 架构
- [Source: _bmad-output/planning-artifacts/epics.md#Story 36.3] — 详细技术规格
- [Source: _bmad-output/planning-artifacts/prd.md#FR-PM04~PM06] — 功能需求

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Completion Notes List

- Story 36.3 依赖 Story 36.1（DegradationResult）+ Story 36.2（DeviceHealthScoreCalculator）
- 不涉及前端仪表盘（36.4 负责）
- WorkOrder 创建使用异步 session（非 operation.py 的同步 _generate_order_no）
- WorkOrderType.maintenance 枚举值为中文 "日常维护"
- WorkOrderStatus.pending 枚举值为中文 "待处理"
- WorkOrderPriority.critical/high/medium 枚举值为中文 "紧急"/"高"/"中"
- Device.site_id 为 nullable，建议不在 MaintenanceAdvice 中冗余 site_id（直接通过 device JOIN 查询）

### File List

**新建：**
- `backend/app/services/predictive_maintenance/advisor.py`
- `backend/app/api/v1/predictive_maintenance.py`
- `backend/app/schemas/predictive_maintenance.py`
- `backend/alembic/versions/20260322_0200_story_36_3_maintenance_advice.py`
- `backend/tests/services/test_maintenance_advisor.py`

**修改：**
- `backend/app/models/report.py` — 新增 MaintenanceAdvice
- `backend/app/services/predictive_maintenance/health_calculator.py` — 集成 advisor
- `backend/app/api/v1/__init__.py` — 注册路由
