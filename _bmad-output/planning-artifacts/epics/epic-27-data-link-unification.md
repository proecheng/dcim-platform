---
epic: 27
title: 前端数据链路统一
status: in-progress
priority: P0
created: 2026-02-15
updated: 2026-03-10
owner: frontend-team
---

# Epic 27: 前端数据链路统一

## 概述

统一前端数据管理架构，建立 Pinia Store 作为单一事实来源（SSOT），消除数据割裂和不一致问题。

## 背景

当前前端存在多处数据割裂：
- 告警数据在多个页面独立获取和存储
- 实时数据在 composables 中维护独立副本
- 能源数据在 Dashboard 和能源页面使用不同数据源
- WebSocket 连接未统一管理

## 目标

1. 建立统一的数据管理架构（Store 作为 SSOT）
2. 消除数据不一致和同步问题
3. 简化数据流向，提高可维护性
4. 优化性能，减少重复计算

## Stories

### ✅ Story 27.1: 告警数据统一到 AlarmStore
**状态:** done
**完成日期:** 2026-02-20
**说明:** 所有页面的告警数据统一从 AlarmStore 读取，移除局部 ref 和独立 API 调用。

### ✅ Story 27.2: 实时数据统一到 RealtimeStore
**状态:** done
**完成日期:** 2026-02-22
**说明:** useRealtime composable 不再持有独立 Map，完全依赖 RealtimeStore。

### ✅ Story 27.3: 能源数据统一到 EnergyStore
**状态:** done
**完成日期:** 2026-02-25
**说明:** Dashboard 和能源页面使用相同的 EnergyStore 数据源。

### ✅ Story 27.4: WebSocket 连接统一管理
**状态:** done
**完成日期:** 2026-02-28
**说明:** useWebSocketManager 单例化，避免重复连接。

### ✅ Story 27.5: 站点过滤贯穿数据链路
**状态:** done
**完成日期:** 2026-03-01
**说明:** API 请求自动注入 site_id，Store 按站点过滤数据。

### ✅ Story 27.6: 告警声音开关统一到 AppStore
**状态:** done
**完成日期:** 2026-03-05
**说明:** 告警声音开关从 AlarmStore 移到 AppStore，作为全局应用设置。

### ✅ Story 27.7: 数据链路 P0 问题修复
**状态:** done
**完成日期:** 2026-03-10
**工作量:** 8h
**说明:** 修复对抗性审查发现的 3 个 P0 问题：
- P0-1: 温度监控页面告警数据统一
- P0-2: Dashboard 能源数据统一
- P0-3: BigscreenStore energy 和 environment 改为 getter
- P1-4: 移除 Dashboard sessionStorage 缓存

**关键修复:**
- `frontend/src/views/environment/temperature.vue`: 从 AlarmStore 读取告警
- `frontend/src/views/dashboard/index.vue`: 移除 energyData ref 和 sessionStorage 缓存
- `frontend/src/stores/bigscreen.ts`: energy 和 environment 改为 getter
- `frontend/src/composables/bigscreen/useBigscreenData.ts`: 移除 fetchEnvironmentData

**额外修复:**
- `proxy/server.js`: 修正后端端口配置（8083 → 8080）

### 📋 Story 27.8: 环境监控分组逻辑统一
**状态:** ready-for-dev
**优先级:** P1
**预估工作量:** 6h
**说明:** 将 useTemperatureData、useWaterLeakData、useSmokeInfraredData 的分组逻辑统一到 RealtimeStore。

**验收标准:**
- AC1: RealtimeStore 添加 `groupByArea(deviceType?)` 方法
- AC2: useTemperatureData 使用 Store 分组方法
- AC3: useWaterLeakData 使用 Store 分组方法
- AC4: useSmokeInfraredData 使用 Store 分组方法

**影响范围:**
- `frontend/src/stores/realtime.ts`
- `frontend/src/composables/useTemperatureData.ts`
- `frontend/src/composables/useWaterLeakData.ts`
- `frontend/src/composables/useSmokeInfraredData.ts`

### 📋 Story 27.9: Dashboard refreshData 简化
**状态:** ready-for-dev
**优先级:** P1
**预估工作量:** 4h
**说明:** 简化 Dashboard 的 refreshData 逻辑，只调用 Store 的 reload 方法，移除复杂的回退逻辑。

**验收标准:**
- AC1: 简化 refreshData 函数，只调用 Store reload
- AC2: 移除 domainOverview 动态更新逻辑
- AC3: 移除 getDashboardData 导入
- AC4: 移除辅助函数（unwrapApiData、applyDashboardOverviewStat）

**影响范围:**
- `frontend/src/views/dashboard/index.vue`

### 📋 Story 27.10: BigscreenStore activeAlarms 性能优化
**状态:** ready-for-dev
**优先级:** P1
**预估工作量:** 2h
**说明:** 使用 computed 缓存 BigscreenStore 的 activeAlarms getter，避免重复计算。

**验收标准:**
- AC1: 将 activeAlarms getter 改为 computed 属性
- AC2: 验证性能改进（减少重复计算）
- AC3: 保持 API 兼容性

**影响范围:**
- `frontend/src/stores/bigscreen.ts`

**预期性能改进:**
- 告警数量 50 条时：减少 ~50 次 map 操作/秒
- 告警数量 100 条时：减少 ~100 次 map 操作/秒

## 进度总结

**已完成:** 7/10 Stories (70%)
**进行中:** 0/10 Stories
**待开发:** 3/10 Stories (30%)

**P0 问题:** 已全部修复 ✅
**P1 问题:** 3 个待修复（Story 27.8, 27.9, 27.10）
**P2 问题:** 4 个（可延迟到下个 Sprint）
**P3 问题:** 3 个（可选修复）

## 对抗性审查结果

**审查日期:** 2026-03-10
**审查方法:** Adversarial Code Review
**发现问题:** 14 个（3 P0, 4 P1, 4 P2, 3 P3）

**P0 问题（已修复）:**
- ✅ P0-1: 温度监控页面告警数据绕过 Store
- ✅ P0-2: Dashboard 维护独立能源数据副本
- ✅ P0-3: BigscreenStore energy/environment 未改为 getter

**P1 问题（待修复）:**
- 📋 P1-4: Dashboard sessionStorage 缓存（已在 27.7 中修复）
- 📋 P1-5: 环境监控 composables 独立分组逻辑 → Story 27.8
- 📋 P1-6: Dashboard refreshData 逻辑复杂 → Story 27.9
- 📋 P1-7: BigscreenStore activeAlarms 性能问题 → Story 27.10

**详细报告:** `_bmad-output/implementation-artifacts/epic-27-adversarial-review-2026-03-10.md`

## 下一步行动

### 本周（2026-03-10 ~ 2026-03-16）
1. ✅ 完成 Story 27.7（P0 修复）
2. ✅ 修复 proxy 端口配置问题
3. ✅ 进行回归测试验证
4. ✅ 规划 P1 问题修复（Story 27.8, 27.9, 27.10）

### 下个 Sprint（2026-03-17 ~ 2026-03-30）
1. 实施 Story 27.8: 环境监控分组统一（6h）
2. 实施 Story 27.9: Dashboard refreshData 简化（4h）
3. 实施 Story 27.10: BigscreenStore 性能优化（2h）
4. 进行全面回归测试
5. 考虑是否修复 P2 问题

### 长期优化（可选）
- P2-8: WebSocket 重连机制改进
- P2-9: site_id 注入逻辑统一
- P2-10: AlarmStore fetchVersion 竞态保护
- P2-11: useRealtime 轮询逻辑优化
- P3-12: localStorage 迁移逻辑改进
- P3-13: RealtimeStore Map 更新模式
- P3-14: 增加自动化测试

## 技术债务

1. **测试覆盖不足:** 缺少自动化测试验证数据链路统一性
2. **类型定义不完整:** 部分 Store 的类型定义可以更严格
3. **文档待更新:** 需要更新开发文档说明新的数据流向

## 相关文档

- 架构文档: `docs/architecture.md` Section 19
- 数据流审查: `docs/data-flow-audit.md`
- 对抗性审查: `_bmad-output/implementation-artifacts/epic-27-adversarial-review-2026-03-10.md`
- Story 详情: `_bmad-output/implementation-artifacts/stories/story-27-*.md`

## 成功指标

- ✅ 所有页面的数据来自统一的 Store
- ✅ 不同页面显示的相同数据完全一致
- ✅ WebSocket 推送能同步更新所有页面
- ✅ 站点切换时所有数据正确过滤
- 🔄 代码重复度降低 30%（待 Story 27.8 完成后测量）
- 🔄 大屏页面性能提升 10%（待 Story 27.10 完成后测量）

---

**最后更新:** 2026-03-10
**更新人:** Claude (Adversarial Review + P1 Planning)
