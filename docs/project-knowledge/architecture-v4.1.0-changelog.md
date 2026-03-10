# 架构文档 V4.1.0 变更日志

**发布日期:** 2026-03-10
**上一版本:** V4.0.0
**变更类型:** 质量改进（对抗性审查 P1 修复）

---

## 概述

V4.1.0 版本主要完成了对抗性代码审查发现的 P1 问题修复，提升了系统并发安全性、数据准确性和可靠性。本次更新不涉及架构变更，仅修复核心模块的实现缺陷。

---

## 修复的 P1 问题（7/26+）

### Epic 6: 能源管理 - PUE 监控

#### P1-1: PUE 历史写入并发冲突 ✅
- **问题**: `write_pue_history()` 两个并发请求可能同时插入相同分钟的记录，导致数据库唯一约束冲突
- **修复**: 使用 UPSERT 逻辑（先查询是否存在，存在则更新，不存在则插入）
- **影响**: 数据一致性
- **文件**: `backend/app/services/pue_calculator.py`

#### P1-2: PUE 计算 UPS 效率异常 ✅
- **问题**: `ups_loss = max(0, ups_total - it_power)` 假设 UPS 总功率 > IT 功率，但如果 UPS 点位配置错误或缺失，会得到 0 损耗，导致 PUE 计算不准确
- **修复**: 使用 UPS 效率模型作为降级策略
  - 如果 `ups_total > it_power`，使用实际值
  - 否则使用效率模型估算：`ups_loss = it_power * (1/0.95 - 1)`
  - 如果有 UPS 数据但不合理，记录警告日志
- **影响**: 数据准确性
- **文件**: `backend/app/services/pue_calculator.py`

---

### Epic 24-26: 智能诊断系统

#### P1-1: 条件解析器递归深度限制 ✅
- **问题**: `condition_parser.py` 递归下降解析器无递归深度限制，恶意表达式可能导致栈溢出
- **修复**: 添加 `MAX_RECURSION_DEPTH = 20` 限制，超过则抛出 `ValueError`
- **影响**: 系统稳定性
- **文件**: `backend/app/services/diagnosis/condition_parser.py`

#### P1-2: 误诊报告生成并发冲突 ✅
- **问题**: `generate_monthly_report()` 两个并发请求可能同时通过"报告不存在"检查，导致数据库唯一约束冲突
- **修复**: 使用 UPSERT 逻辑（先尝试插入，如果冲突则查询返回现有记录）
- **影响**: 数据一致性
- **文件**: `backend/app/services/diagnosis/misdiagnosis_report_service.py`

#### P1-3: 混沌演练断路器恢复失败 ✅
- **问题**: `CircuitBreaker.reset()` 是同步方法，但在异步上下文中调用，且无锁保护，可能与其他异步操作产生竞态条件
- **修复**:
  - 将 `reset()` 改为异步方法 `async def reset()`
  - 添加 `asyncio.Lock` 保护
  - 所有调用点改为 `await breaker.reset()`
- **影响**: 系统可靠性
- **文件**:
  - `backend/app/services/diagnosis/circuit_breaker.py`
  - `backend/app/services/diagnosis/chaos_drill_service.py`
  - `backend/tests/test_story_24_7.py`

#### P1-4: Redis 降级存储连接失败处理 ✅
- **问题**: `DiagnosisFallbackStore.save_to_redis()` 如果 Redis 连接失败，会抛出异常，导致诊断结果丢失
- **修复**:
  - 添加 1 秒超时控制
  - Redis 写入失败时降级到本地文件 `logs/diagnosis_fallback_redis_unavailable.log`
  - 返回 `"local_file"` 标识
- **影响**: 数据可靠性
- **文件**: `backend/app/services/diagnosis/fallback_store.py`

#### P1-6: 诊断引擎动态去重窗口 ✅
- **问题**: 诊断引擎使用固定 60 秒去重窗口，对于 critical 告警可能过短，对于 info 告警可能过长
- **修复**: 根据告警级别动态调整去重窗口
  - critical: 300 秒（5 分钟）
  - major: 180 秒（3 分钟）
  - warning: 120 秒（2 分钟）
  - info: 60 秒（1 分钟）
- **影响**: 诊断准确性
- **文件**: `backend/app/engines/diagnosis_engine.py`

---

## 待修复的 P1 问题（19+）

### Epic 6: 能源管理
- P1-3: 能耗统计查询未处理时区
- P1-4: 配电拓扑未计算负载汇总

### Epic 7: 节能优化
- P1-2: 插件管理器线程安全

### Epic 24-26: 智能诊断系统
- P1-5: 故障树缓存版本变更处理

### 其他 Epic
- 详见 `_bmad-output/implementation-artifacts/adversarial-review-summary.md`

---

## 技术债务

### 并发安全模式
- ✅ 所有单例模式已使用 `asyncio.Lock` 保护
- ✅ 所有异步操作已设置超时
- ⏳ 部分资源清理逻辑待完善

### 数据验证
- ⏳ JSON 字段使用 Pydantic schema 校验
- ⏳ 文件上传增加魔数校验
- ⏳ 拓扑数据增加完整性检查

### 性能监控
- ⏳ 记录插件执行时间
- ⏳ 记录故障树推理性能
- ⏳ 记录 WebSocket 连接数

---

## 测试覆盖率

### 单元测试
- Epic 6: PUE 计算 ✅
- Epic 24-26: 诊断引擎 ✅
- Epic 24-26: 断路器 ✅
- Epic 24-26: 条件解析器 ✅

### 集成测试
- Epic 24-26: 混沌演练 ✅
- Epic 24-26: Redis 降级存储 ✅

---

## 性能影响

### 改进
- 诊断引擎去重窗口优化：减少 critical 告警的重复诊断次数
- PUE 计算效率模型：提升数据准确性

### 无影响
- 所有修复均为逻辑优化，无性能回退

---

## 兼容性

### 向后兼容
- ✅ 所有 API 接口保持不变
- ✅ 数据库 schema 无变更
- ✅ 前端无需修改

### 升级路径
- 无需数据迁移
- 重启后端服务即可生效

---

## 下一步计划

1. **继续修复 P1 问题** - 目标 100% 完成（当前 27%）
2. **建立并发安全检查清单** - 防止新代码引入类似问题
3. **增强数据验证** - 提升系统健壮性
4. **性能监控埋点** - 提升可观测性

---

## 参考文档

- [对抗性审查总结报告](../../_bmad-output/implementation-artifacts/adversarial-review-summary.md)
- [Epic 6 对抗性审查报告](../../_bmad-output/implementation-artifacts/epic-6-adversarial-review.md)
- [Epic 24-26 对抗性审查报告](../../_bmad-output/implementation-artifacts/epic-24-26-adversarial-review.md)

---

**审查人:** Claude Opus 4.6
**发布日期:** 2026-03-10
