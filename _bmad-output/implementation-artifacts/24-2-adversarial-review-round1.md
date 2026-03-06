# Story 24.2 对抗性审查报告 - 第一轮

**审查日期**: 2026-03-06
**审查对象**: Story 24.2 - 诊断调度器与并发控制
**审查类型**: 对抗性审查（第一轮）

---

## 审查发现

### 高严重程度问题（Critical）

1. **CancellablePriorityQueue.put() 中的竞态条件**: 在第 92-93 行，先过滤已取消任务再 heapify，但在第 97 行使用 `max()` 查找最低优先级任务时，可能会遍历到已被过滤但尚未从堆中移除的任务。应该在 heapify 后再执行 max 查找，或者在 max 中也过滤 `_cancelled` 任务。

2. **DiagnosisScheduler.start() 硬编码 worker 数量**: 第 216 行硬编码了 10 个 worker，但构造函数接受 `max_workers` 参数。应该使用 `self.max_workers = max_workers` 并在循环中使用该变量，否则参数无效。

3. **全局限流未实现**: 验收标准第 31 行要求"30 次/分钟/全局"限流，但 API 端点第 547 行只实现了用户级限流（10次/分钟/用户），缺少全局限流装饰器。

4. **手动触发时 alarm_id 为 None 导致外键约束冲突**: DiagnosisResult 模型第 465 行定义 `alarm_id` 为 `ForeignKey("alarms.id"), nullable=True`，但手动触发时第 423 行设置 `alarm_id=None`，保存时第 388 行直接传入 None 可能导致外键约束问题（取决于数据库配置）。应明确测试或在迁移脚本中设置外键为 `ON DELETE SET NULL`。

5. **DiagnosisResult 模型缺少反向关系定义**: 第 478-479 行定义了 `alarm` 和 `device` 关系，但 `Alarm` 和 `Device` 模型中需要添加 `back_populates="diagnosis_results"` 的反向关系，否则会导致 SQLAlchemy 关系映射错误。

6. **Redis Pub/Sub 订阅失败后无重连机制**: `_subscribe_alarms()` 方法第 237-260 行，如果 Redis 连接断开或订阅失败，只记录错误日志但不重连，导致调度器永久失效。应实现指数退避重连机制。

### 中严重程度问题（Major）

7. **CancellablePriorityQueue.get() 可能死锁**: 第 115-129 行，如果所有任务都被取消且没有新任务到来，`get()` 会在第 129 行永久等待。虽然理论上不应发生（因为 put 会 set event），但在极端情况下（如所有任务在 get 锁外被取消）可能导致 worker 挂起。

8. **验收标准与实现不一致 - 队列满时的通知**: 验收标准第 27 行要求"通过 WebSocket 通知运维人员"，但实现第 292 行只有 `# TODO: WebSocket 通知运维人员`，未实现。虽然实施注意事项第 698 行说明"暂不实现"，但验收标准应相应调整为"记录日志"而非"通知"。

9. **自动升级逻辑可能导致重复诊断**: 第 350-357 行，L1 未匹配时自动升级到 L2，但没有检查该告警是否已经有 L2 结果。如果 L2 也失败，可能会无限循环（虽然第 352 行检查了 `inference_level == "L1"`，但如果 L2 未匹配是否会再次升级到 L3？规格未明确）。

10. **DiagnosisScheduler.stop() 不等待队列清空**: 第 226-235 行，stop 方法立即取消所有 worker，但队列中可能还有待处理任务。应该先停止接收新任务，等待队列清空后再取消 worker，否则会丢失诊断任务。

11. **API 限流依赖 fastapi_limiter 但未说明初始化**: 第 523 行导入 `fastapi_limiter.depends`，但文档未说明如何初始化 fastapi_limiter（需要 Redis 连接）。应在 FastAPI lifespan 或实施注意事项中补充说明。

12. **手动触发的 task_id 可能重复**: 第 431 行使用 `datetime.utcnow().timestamp()` 生成 task_id，但如果同一设备在同一毫秒内多次触发，会生成相同的 task_id，导致队列中任务被覆盖或取消逻辑失效。应使用 UUID 或添加递增序列号。

13. **缺少 Alarm 和 Device 模型的反向关系修改说明**: 第 478-479 行定义了关系，但文档未说明需要修改 `backend/app/models/alarm.py` 和 `backend/app/models/device.py` 添加 `diagnosis_results = relationship("DiagnosisResult", back_populates="alarm/device")`。

### 低严重程度问题（Minor）

14. **测试策略缺少边界情况**: 单元测试第 608-614 行列出了 6 个测试用例，但缺少关键边界情况：
    - 队列为空时调用 qsize()
    - 取消不存在的 task_id
    - 并发 put 和 cancel 同一任务
    - heapify 后堆不变性验证

15. **性能测试标准模糊**: 第 644-648 行列出了 4 个性能测试场景，但未定义成功标准（如"100 并发告警应在 X 秒内完成"、"吞吐量应 >= Y 任务/秒"、"内存增长应 < Z MB/小时"）。

16. **DiagnosisResult 模型缺少 site_id 字段**: 根据 Epic 13 和 16，系统支持多站点数据隔离，但 DiagnosisResult 表未包含 `site_id` 字段，可能导致跨站点数据泄漏。应添加 `site_id` 外键并在查询时过滤。

17. **日志级别不一致**: 第 291 行使用 `logger.warning` 记录队列满，但第 360 行使用 `logger.error` 记录超时。队列满是预期行为（验收标准明确定义），应使用 `info` 或 `warning`；超时是异常情况，使用 `error` 合理。建议统一日志级别策略。

18. **Alembic 迁移脚本缺少时间戳前缀**: 第 485 行文件名使用 `xxxx_create_diagnosis_results.py`，但 Alembic 要求时间戳前缀（如 `20260306120000_create_diagnosis_results.py`）。应说明使用 `alembic revision` 命令生成。

19. **验收检查清单缺少"更新 Alarm/Device 模型"项**: 第 665-680 行的检查清单未包含"在 Alarm 和 Device 模型中添加反向关系"，但这是必需步骤。

20. **估算工作量未考虑审查和修复时间**: 第 704-707 行估算 3-4 天，但未包含对抗性审查（2 轮）和修复时间（可能 1-2 天），实际工作量可能达到 5-6 天。

---

## 严重程度统计

- **高严重程度**: 6 个
- **中严重程度**: 7 个
- **低严重程度**: 7 个
- **总计**: 20 个

---

## 建议优先修复

1. 修复问题 1（竞态条件）
2. 修复问题 2（硬编码 worker 数量）
3. 修复问题 3（全局限流未实现）
4. 修复问题 5（反向关系定义）
5. 修复问题 6（Redis 重连机制）
6. 调整问题 8（验收标准与实现一致性）
7. 补充问题 13（模型修改说明）

---

## 审查结论

Story 24.2 文档整体结构完整，技术方案合理，但存在多个高严重程度问题需要修复。建议在实施前完成第一轮修复，并进行第二轮审查。
