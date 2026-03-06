# Story 24.1 对抗性审查 - 第一轮

**审查日期**: 2026-03-06
**审查对象**: 24-1-l1-rule-engine.md
**审查类型**: 对抗性审查（Adversarial Review）

---

## 发现的问题

### 1. 条件匹配逻辑不一致
**严重程度**: 高
**描述**: 代码示例中 `condition` 使用 `point_id`，但 JSON 示例中使用 `point_type`。实际实现时如何从 `point_type` 映射到 `point_id` 完全没有说明。这会导致开发者不知道该用哪个字段。

### 2. Redis 客户端初始化缺失
**严重程度**: 高
**描述**: `L1RuleEngine` 和 `DiagnosisScheduler` 中 `self.redis_client` 初始化为 `None`，但后续直接使用 `await self.redis_client.mget()`。没有说明何时何地注入 Redis 客户端实例，代码会在运行时崩溃。

### 3. JSON 导入缺失
**严重程度**: 中
**描述**: `DiagnosisScheduler.start()` 中使用 `json.loads()` 但没有 `import json`。代码无法运行。

### 4. 数据库迁移不完整
**严重程度**: 中
**描述**: 迁移脚本只有 `upgrade()`，缺少 `downgrade()` 函数。生产环境回滚时会失败，不符合 Alembic 最佳实践。

### 5. 规则索引键可能为 None
**严重程度**: 高
**描述**: `rule.device_type` 和 `rule.alarm_type` 在迁移中定义为 `nullable=True`，但代码中直接用作索引键 `(rule.device_type, rule.alarm_type)`。如果规则没有设置这两个字段，会导致 `(None, None)` 键污染索引，所有通用规则都会被错误地索引到同一个键下。

### 6. Redis 值类型转换缺失
**严重程度**: 高
**描述**: `await self.redis_client.mget(redis_keys)` 返回的是 `bytes` 或 `None`，代码中直接 `float(point_values[point_id])` 会抛出 `TypeError` 或 `ValueError`。需要先解码和类型检查。

### 7. 优先级队列满时的处理逻辑不完整
**严重程度**: 中
**描述**: 代码注释说"尝试移除最低优先级任务"，但实际只有 `pass`，完全没有实现。验收标准要求队列满时的处理策略，但代码是空的。

### 8. 调度器启动方式不明确
**严重程度**: 中
**描述**: `DiagnosisScheduler.start()` 是一个无限循环（`async for message in pubsub.listen()`），但没有说明如何在 FastAPI lifespan 中启动。是用 `asyncio.create_task()` 还是 `background_tasks.add_task()`？

### 9. 规则热更新的触发机制缺失
**严重程度**: 中
**描述**: 文档说管理员修改规则后通过 Redis Pub/Sub 通知，但没有说明谁来发布 `diagnosis:rule_update` 事件。是 API 端点还是数据库触发器？还是需要管理员手动调用？

### 10. 诊断结果保存逻辑完全缺失
**严重程度**: 高
**描述**: `_save_result()` 只有 `pass` 和 TODO 注释，但验收标准明确要求"保存结果"。这是一个关键功能的空洞，Story 无法通过验收。

### 11. Story 范围过大导致边界不清
**严重程度**: 中
**描述**: 这个 Story 同时包含 L1 引擎、调度器、规则管理器三个组件，但 epics.md 中 Story 24.2 是"诊断调度器与并发控制"。这意味着 Story 24.1 和 24.2 的边界不清晰，可能导致重复实现或遗漏。

### 12. 缺少已有表结构的检查
**严重程度**: 中
**描述**: 文档说"复用棕地已有表 `diagnosis_rules`"，但没有说明当前表有哪些字段。如果已有表中已经有 `conditions` 或 `logic` 字段，迁移会失败。需要先检查现有表结构。

### 13. 性能测试标准模糊
**严重程度**: 低
**描述**: "1000 条规则加载时间 < 2 秒"，但没有说明测试环境（CPU、内存、数据库配置），也没有说明如何生成 1000 条测试规则。测试标准不可复现。

### 14. 错误处理不完整
**严重程度**: 中
**描述**: `_evaluate_rule()` 中 `float(point_values[point_id])` 可能抛出 `ValueError`（如果 Redis 返回非数字字符串），但没有 try-except。会导致单个异常点位值让整个推理失败。

### 15. 规则优先级语义不明确
**严重程度**: 低
**描述**: 迁移中 `priority` 默认值是 100，代码中按 `priority.asc()` 排序，但没有说明数字越小优先级越高还是越大优先级越高。容易导致配置错误。

---

## 总结

发现 15 个问题，其中：
- **高严重程度**: 6 个（条件逻辑不一致、Redis 初始化、索引键 None、类型转换、结果保存缺失、表结构检查）
- **中严重程度**: 7 个（JSON 导入、迁移不完整、队列处理、调度器启动、热更新触发、Story 范围、错误处理）
- **低严重程度**: 2 个（性能测试标准、优先级语义）

**建议**: 在实施前必须修复所有高严重程度问题，否则代码无法运行或会产生严重 bug。
