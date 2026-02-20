# Epic 5 回顾：告警管理增强

## 完成情况

全部 5 个 Story 完成，实现了 4 级阈值配置、实时告警引擎、告警处理闭环、数据质量防护和告警升级规则。

| Story | 标题 | 后端测试 | 前端构建 |
|-------|------|---------|---------|
| 5-1 | 告警阈值配置增强 | ✅ | ✅ |
| 5-2 | 实时告警触发与通知 | ✅ | ✅ |
| 5-3 | 告警处理闭环 | ✅ | ✅ |
| 5-4 | 数据质量标记与误告警防护 | ✅ | ✅ |
| 5-5 | 告警升级规则与前端管理 | ✅ | ✅ |

## 关键经验教训

### 架构决策

1. **告警引擎内存缓存**：AlarmEngine 启动时从数据库批量加载阈值到内存，按 point_id 分组。每 30 秒检查版本号，版本变化时自动重新加载。避免每次 evaluate 都查库
2. **告警风暴防护**：同一点位 60 秒内重复越限不重复产生告警，通过内存记录每个点位最后告警时间实现
3. **大面积告警检测**：同一 device_type 下 >50% 点位同时越限时，自动标记为"疑似通信异常"，优先检查数据源状态

### 反复出现的模式

1. **数据质量与告警联动**：PointRealtime.quality == 2（坏）时跳过阈值检测，quality == 1（不确定）时检测但消息带前缀。通信中断时自动标记不可靠，恢复后自动解除
2. **WebSocket 实时推送**：告警触发、确认、处理、解除、升级操作后，通过 alarms 通道广播状态变更。前端 useAlarm composable 处理各种 action 类型
3. **Alarm 模型持续扩展**：从基础字段逐步新增 process_remark、processed_by、processed_at、duration_seconds 等字段，每次扩展都需要 Alembic 迁移

### 技术模式沉淀

- **4 级阈值一体化 API**：PUT `/thresholds/point/{id}/four-level` 一次性配置 high_high/high/low/low_low 四级，自动映射 threshold_type → alarm_level
- **按设备类型批量配置**：选择 device_type 后自动查询该类型下所有 AI 点位，批量应用阈值模板
- **死区（dead_band）和延迟触发（delay_seconds）**：防止阈值边界值频繁触发告警
- **告警升级引擎**：后台定时任务每 60 秒扫描超时未处理的 active 告警，匹配升级规则后自动升级告警级别
- **告警引擎质量缓存**：`_point_quality: Dict[int, int]` 内存缓存，通信监控服务标记质量变更时同步更新

### SQLite 限制

- Alembic 迁移中 ALTER TABLE ADD COLUMN 在 SQLite 下有限制，新增字段必须有默认值或允许 NULL
- 告警统计按 device_type 筛选需要 JOIN Point 表，SQLite 下 JOIN 性能可接受但需注意索引

## 下一步

Epic 6: 能源管理 — 5 个 Stories
