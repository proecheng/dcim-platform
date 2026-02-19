# Story 11-4: 告警自动创建工单

## Story

As a 运维工程师,
I want 重要告警自动创建工单,
So that 关键问题不会被遗漏。

**FR 追溯:** FR67（自动创建部分）

---

## 状态: 已审查

## 设计

### 新增模型: AlarmWorkOrderRule

在 `models/operation.py` 中新增:

```python
class AlarmWorkOrderRule(Base):
    __tablename__ = "alarm_workorder_rules"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="规则名称")
    alarm_level = Column(String(20), nullable=False, comment="告警级别(critical/important)")
    alarm_type = Column(String(20), comment="告警类型过滤(threshold/communication/system, 空=全部)")
    order_type = Column(Enum(WorkOrderType), default=WorkOrderType.fault, comment="工单类型")
    priority = Column(Enum(WorkOrderPriority), default=WorkOrderPriority.high, comment="工单优先级")
    assignee = Column(String(100), comment="自动派单人")
    is_enabled = Column(Boolean, default=True, comment="是否启用")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
```

### 新增 Schema

在 `schemas/operation.py` 中新增:
- AlarmWorkOrderRuleBase/Create/Update/Response

### 新增 API 端点

在 `api/v1/operation.py` 中新增:
- GET /alarm-rules — 获取告警工单规则列表
- POST /alarm-rules — 创建规则
- PUT /alarm-rules/{id} — 更新规则
- DELETE /alarm-rules/{id} — 删除规则
- POST /alarm-rules/check — 根据告警信息检查匹配规则并自动创建工单

### POST /alarm-rules/check 逻辑

接收 `{alarm_id: int, alarm_level: str, alarm_type: str, alarm_message: str}`:
1. 查询所有启用的规则，匹配 alarm_level 和 alarm_type
2. 如果匹配到规则，自动创建工单（标题=告警消息，关联 alarm_id）
3. 如果规则有 assignee，自动派单
4. 返回创建的工单（或 null 如果无匹配规则）

### 前端 API

在 `api/modules/operation.ts` 中新增类型和函数。

### 测试

约 10 个测试用例。

---

## 验收标准

1. ✅ 告警工单规则 CRUD 完整可用
2. ✅ check 端点能根据告警级别匹配规则并自动创建工单
3. ✅ 自动创建的工单关联 alarm_id
4. ✅ 规则有 assignee 时自动派单
5. ✅ 所有新增测试通过，回归 136+ 通过

## 技术约束

- alarm_level 使用英文值（critical/important/minor/info），与 Alarm 模型一致
- WorkOrderType/WorkOrderPriority 枚举值为中文
- 静态路由 /alarm-rules 和 /alarm-rules/check 必须在 /alarm-rules/{id} 之前
