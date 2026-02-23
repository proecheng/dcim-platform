# Epic 18-23 对抗性代码审查报告

**审查日期**: 2026-02-23
**审查范围**: Epic 18 (环境监控) / Epic 19 (安防消防) / Epic 20 (告警规则) / Epic 21 (网关管理) / Epic 22 (站点管理) / Epic 23 (大屏增强 + OCR)
**审查文件数**: 24 个文件
**审查员**: 对抗性高级开发者

---

## 问题汇总

| 编号 | 严重度 | Epic | 文件 | 问题简述 |
|------|--------|------|------|----------|
| CR-01 | HIGH | 20 | escalation.vue | 升级链 JSON 存入 `description` 字段，语义滥用 |
| CR-02 | HIGH | 20 | compound.vue | 条件树 JSON 存入 `condition_expr` 字段，无后端校验 |
| CR-03 | HIGH | 23 | ocr_service.py | OCR 端点缺少 Content-Type 校验，仅依赖文件扩展名 |
| CR-04 | HIGH | 18/19 | 所有 composables | WebSocket 连接只 connect 不 disconnect，资源泄漏 |
| CR-05 | MEDIUM | 23 | BigscreenFloor3D.vue | Three.js 纹理/渲染器资源清理不完整 |
| CR-06 | MEDIUM | 20 | shield.vue | 编辑操作使用"先删后建"模式，存在数据丢失风险 |
| CR-07 | MEDIUM | 21 | gateway/index.vue | 批量配置下发串行执行，无并发控制和超时处理 |
| CR-08 | MEDIUM | 18 | useWaterLeakData.ts | 24h 告警数查询未按设备类型过滤，数据不准确 |
| CR-09 | MEDIUM | 20 | thresholds.vue | 前端全量加载阈值数据做聚合分页，大数据量下性能隐患 |
| CR-10 | LOW | 23 | BigscreenHistoryDialog.vue | `deviceId` 类型为 string，parseInt 转换存在 fallback 逻辑 |
| CR-11 | LOW | 21 | gateway/index.vue | `datasource_count` 替代吞吐量、`capabilities` 替代协议类型 |
| CR-12 | LOW | 20 | CompoundConditionGroup.vue | 递归深度限制 MAX_DEPTH=2 硬编码，无用户提示 |

---

## 详细问题描述

### CR-01 [HIGH] 升级链 JSON 存入 `description` 字段 — 语义滥用

**文件**: `frontend/src/views/alarm/escalation.vue`
**行号**: 第 382 行 (`getChainLength`)、第 473 行 (`handleEdit` 反序列化)、第 544 行 (`submitForm` 序列化)

**问题描述**:
升级规则的多节点升级链数据（包含 `timeout_minutes`、`notify_method`、`notify_user_ids`、`upgrade_level` 等结构化字段）被 `JSON.stringify` 后存入 `description` 字段。`description` 在数据库模型中是一个文本描述字段，不应承载结构化业务数据。

这导致：
1. 后端无法对升级链数据做 schema 校验，任意 JSON 都能写入
2. 数据库查询无法按升级链内容过滤（如"查找所有包含邮件通知的规则"）
3. `description` 字段的原始语义（人类可读描述）被破坏
4. 第 534-535 行：`allUserIds` 合并所有节点通知人、`firstTimeout` 取第一个节点超时时间作为顶层字段，导致顶层字段与 `description` 中的数据不一致

**建议修复**:
后端新增 `escalation_chain` JSON 字段（或独立关联表 `escalation_chain_nodes`），前端改为写入专用字段。短期可在后端 API 层增加 JSON schema 校验。

---

### CR-02 [HIGH] 条件树 JSON 存入 `condition_expr` 字段，无后端校验

**文件**: `frontend/src/views/alarm/compound.vue`
**行号**: 第 323 行 (`getConditionCount` 反序列化)、第 338-339 行 (`getRelatedPoints`)、第 439 行 (`handleEdit`)、第 459 行 (`submitForm`)

**问题描述**:
复合告警规则的条件树（嵌套的 `ConditionGroup` / `ConditionItem` 结构）被 `JSON.stringify` 后存入 `condition_expr` 字段。虽然字段名暗示可以存表达式，但：

1. 后端没有对 `condition_expr` 的 JSON 结构做任何校验，恶意用户可以通过 API 直接提交任意 JSON
2. 前端多处使用 `JSON.parse` 反序列化并 `try/catch` 静默失败（第 323、338、439 行），如果数据损坏，用户看到的是空白而非错误提示
3. `rule_type` 字段（第 462 行）从 `rootGroup.logic` 推导，但如果条件树有嵌套子组使用不同逻辑，顶层 `rule_type` 无法准确反映实际逻辑

**建议修复**:
后端增加 Pydantic schema 校验 `condition_expr` 的 JSON 结构。前端反序列化失败时应给用户明确的错误提示而非静默降级。

---

### CR-03 [HIGH] OCR 端点文件类型校验仅依赖扩展名，缺少 Content-Type 和魔数校验

**文件**: `backend/app/services/ocr_service.py`
**行号**: 第 196-205 行 (`recognize_bill` 文件类型校验)

**问题描述**:
OCR 服务的文件类型校验仅检查文件扩展名（`.jpg`, `.jpeg`, `.png`, `.pdf`），未校验：
1. HTTP 请求的 `Content-Type` 头
2. 文件魔数（magic bytes），如 JPEG 的 `FF D8 FF`、PNG 的 `89 50 4E 47`

攻击者可以将恶意文件（如 `.exe`）重命名为 `.jpg` 上传，绕过校验。虽然后续 PaddleOCR 处理时可能会失败，但在 mock 模式下（当前默认模式），文件内容完全不被读取，直接返回 mock 数据，意味着任何文件都能"成功"上传。

此外，`backend/app/api/v1/energy.py` 第 4214 行 `file_bytes = await file.read()` 将整个文件读入内存，虽然 `ocr_service.py` 第 208-209 行有 10MB 限制，但这个检查发生在文件已经完全读入内存之后。应在 FastAPI 层面配置 `max_upload_size` 或使用流式读取。

**建议修复**:
1. 增加文件魔数校验（至少检查前 4 字节）
2. 在 FastAPI 端点层面限制上传大小（使用中间件或 `UploadFile` 的 `max_size` 参数）
3. mock 模式下也应执行文件类型校验

---

### CR-04 [HIGH] WebSocket 连接只 connect 不 disconnect，存在资源泄漏

**文件**:
- `frontend/src/composables/useTemperatureData.ts` 第 187-194 行
- `frontend/src/composables/useWaterLeakData.ts` 第 134-141 行
- `frontend/src/composables/useSmokeInfraredData.ts` 第 158-166 行
- `frontend/src/composables/useAccessControlData.ts` 第 276-283 行

**问题描述**:
所有 4 个环境/安防 composable 在 `onMounted` 中调用 `realtimeWs.connect()`，但在 `onUnmounted` 中只调用 `realtimeWs.off('realtime', handleWsMessage)` 取消事件监听，**从未调用 `realtimeWs.disconnect()`**。

这意味着：
1. 如果用户在温度页面和水浸页面之间切换，每次进入都会调用 `connect()`，但离开时不会 `disconnect()`
2. WebSocket 连接可能被多次建立但从不关闭（取决于 `realtimeWs` 的内部实现是否有引用计数）
3. 即使 `realtimeWs` 内部是单例模式，`off` 只移除了当前组件的监听器，但连接本身保持打开

同样，`useFireLinkageData.ts` 没有使用 WebSocket（使用轮询），但轮询间隔 10 秒，在 `onUnmounted` 中正确清理了。

**建议修复**:
如果 `realtimeWs` 是引用计数模式，应在 `onUnmounted` 中调用 `realtimeWs.disconnect()`。如果是全局单例，应确保文档说明清楚，并在最后一个消费者卸载时自动断开。

---

### CR-05 [MEDIUM] Three.js 资源清理不完整

**文件**: `frontend/src/components/bigscreen/BigscreenFloor3D.vue`
**行号**: 第 607-633 行 (`onUnmounted`)、第 452-482 行 (`clearSceneObjects`)

**问题描述**:
`onUnmounted` 调用了 `clearSceneObjects()` 清理 Mesh 和 LineSegments 的 geometry/material，但存在以下遗漏：

1. **GridHelper 的 material 未 dispose**：第 459 行 `clearSceneObjects` 遍历时匹配了 `THREE.GridHelper`，但只调用 `scene.remove(obj)`，没有 dispose 其 geometry 和 material（GridHelper 继承自 LineSegments，有自己的 geometry/material）
2. **Fog 对象未清理**：第 173 行创建了 `scene.fog = new THREE.Fog(...)`，虽然 Fog 不占用 GPU 资源，但 scene 引用未置空可能导致 GC 延迟
3. **DirectionalLight 的 shadow map 未 dispose**：第 194-201 行创建了带 shadow 的 DirectionalLight，`renderer.dispose()` 会清理大部分资源，但 shadow map 的 render target 可能需要显式清理
4. **`raycaster` 和 `mouse` 在模块作用域创建**（第 486-487 行），不会被 GC 回收直到组件模块被卸载

**建议修复**:
在 `clearSceneObjects` 中对 GridHelper 也执行 geometry/material dispose。考虑在 `onUnmounted` 中将 `scene.fog = null`。

---

### CR-06 [MEDIUM] 屏蔽策略编辑使用"先删后建"模式，存在数据丢失风险

**文件**: `frontend/src/views/alarm/shield.vue`
**行号**: 第 594-597 行 (`submitForm`)、第 612-636 行 (`handleTerminate`)

**问题描述**:
由于后端 API 不支持 `update` 操作，前端编辑屏蔽策略时采用"先删除旧记录，再创建新记录"的方式（第 595-596 行）：

```typescript
if (isEdit.value && editingId.value) {
  await deleteAlarmShield(editingId.value)
}
await createAlarmShield(data)
```

如果 `deleteAlarmShield` 成功但 `createAlarmShield` 失败（网络错误、服务端校验失败等），原始数据将永久丢失。同样的问题存在于 `handleTerminate`（第 620-628 行）。

**建议修复**:
1. 后端增加 `PUT /api/v1/alarm-shields/{id}` 更新端点
2. 短期方案：将删除和创建包装在 try/catch 中，创建失败时尝试恢复（重新创建旧数据）
3. 或使用乐观更新模式：先创建新记录，成功后再删除旧记录

---

### CR-07 [MEDIUM] 批量配置下发串行执行，无并发控制和超时处理

**文件**: `frontend/src/views/gateway/index.vue`
**行号**: 第 646-661 行 (`handleBatchPush`)

**问题描述**:
批量配置下发使用 `for...of` 串行循环调用 `pushGatewayConfig`：

```typescript
for (const gw of onlineEnabled) {
  try {
    await pushGatewayConfig(gw.id)
    successCount++
  } catch {
    failCount++
  }
}
```

问题：
1. 如果选中 50 个网关，且每个下发需要 2 秒，总耗时 100 秒，用户体验极差
2. 没有单次请求超时控制，如果某个网关响应缓慢，会阻塞后续所有网关
3. 没有进度反馈（用户只看到 loading 状态，不知道进度）
4. 注释说"串行下发，避免 MQTT 拥塞"（第 645 行），但没有可配置的并发度

**建议修复**:
使用 `Promise.allSettled` 配合并发限制（如 `p-limit` 或手动实现 3-5 并发），增加进度回调。

---

### CR-08 [MEDIUM] 24h 告警数查询未按设备类型过滤，数据不准确

**文件**: `frontend/src/composables/useWaterLeakData.ts`
**行号**: 第 80-101 行 (`fetchRecentAlarms`)

**问题描述**:
`fetchRecentAlarms` 方法注释说"获取最近 24 小时告警数"，但实际查询没有按水浸传感器的 `point_id` 过滤：

```typescript
const pointIds = wlSensors.value.map(s => s.point_id)
// ... pointIds 被计算但未使用 ...
const res = await getAlarmList({
  start_time: yesterday.toISOString(),
  end_time: now.toISOString(),
  page: 1,
  page_size: 1,
})
recentAlarmCount.value = res.total ?? 0
```

第 84-88 行计算了 `pointIds`，但第 90-95 行的 API 调用完全没有使用它。注释（第 96 行）承认"API 不支持按多个 point_id 批量筛选，使用总告警数作为近似值"。这意味着水浸页面显示的"24h 告警数"实际上是**全系统所有设备**的告警总数，严重误导用户。

同样的问题存在于 `useSmokeInfraredData.ts` 第 96-110 行。

**建议修复**:
后端 API 增加 `device_type` 过滤参数，或前端循环按 `point_id` 查询后求和。

---

### CR-09 [MEDIUM] 前端全量加载阈值数据做聚合分页，大数据量下性能隐患

**文件**: `frontend/src/views/alarm/thresholds.vue`
**行号**: 第 300-327 行 (`loadData`)

**问题描述**:
`loadData` 使用 `do...while` 循环分页加载**全部**阈值数据到前端内存：

```typescript
let allItems: ThresholdInfo[] = []
let page = 1
const pageSize = 100
let total = 0
do {
  const result = await getThresholdList({ ...baseParams, page, page_size: pageSize })
  allItems = allItems.concat(result.items || [])
  total = result.total || 0
  page++
} while (allItems.length < total)
```

然后在前端做聚合（按 `point_id` 分组）和分页（第 329-396 行 `aggregateAndFilter`）。

如果系统有 1000 个点位 × 4 级阈值 = 4000 条记录，需要 40 次 API 请求才能加载完毕。随着系统规模增长，这个方案不可扩展。

**建议修复**:
后端提供聚合 API（按 `point_id` 分组返回 4 级阈值），支持服务端分页和筛选。

---

### CR-10 [LOW] BigscreenHistoryDialog deviceId 类型为 string，parseInt 转换存在 fallback

**文件**: `frontend/src/components/bigscreen/BigscreenHistoryDialog.vue`
**行号**: 第 97 行 (props 定义)、第 191-198 行 (`loadDeviceInfo`)

**问题描述**:
`deviceId` prop 类型为 `string`，但 `getDeviceDetail` API 需要 `number` 类型的 ID。第 191 行使用 `parseInt(props.deviceId, 10)` 转换，如果 `deviceId` 是非数字字符串（如机柜编码 "A-01"），则 fallback 到字符串显示模式（第 193-198 行），此时无法加载任何历史数据。

这是一个已知的技术债务，但 fallback 逻辑过于静默——用户看到的是空白图表而非"该设备不支持历史数据查看"的明确提示。

**建议修复**:
当 `deviceId` 无法解析为数字时，显示明确的提示信息而非空白状态。考虑统一 `deviceId` 类型为 `number`，在调用方做转换。

---

### CR-11 [LOW] 网关管理页面数据映射替代

**文件**: `frontend/src/views/gateway/index.vue`
**行号**: 第 106 行 (`datasource_count`)、第 167-169 行 (`capabilities`)、第 326-333 行 (`avgThroughput`)

**问题描述**:
已知技术债务，注释已标注（第 318-328 行）：
1. `datasource_count` 替代"数据吞吐量"显示
2. `capabilities` 对象的 keys 替代"协议类型"标签
3. `cpu_usage` 平均值替代"平均负载"指标

这些替代虽然有注释说明，但用户界面上的标签（"平均负载"、"能力标签"）与实际数据含义不完全匹配，可能误导运维人员。

**建议修复**:
后端 `GatewaySummary` 增加 `alarm_count` 和 `avg_throughput` 字段。短期可将前端标签改为更准确的描述（如"平均 CPU"而非"平均负载"）。

---

### CR-12 [LOW] 递归组件深度限制硬编码，无用户提示

**文件**: `frontend/src/views/alarm/CompoundConditionGroup.vue`
**行号**: 第 142 行 (`MAX_DEPTH = 2`)、第 20 行 (模板中 `v-if="depth < MAX_DEPTH"`)

**问题描述**:
递归条件组编辑器的最大嵌套深度硬编码为 `MAX_DEPTH = 2`（即最多 3 层）。当达到最大深度时，"添加子组"按钮被隐藏（`v-if="depth < MAX_DEPTH"`），但没有任何视觉提示告知用户为什么按钮消失了。

此外，`MAX_DEPTH` 是组件内部常量，无法通过 props 配置，降低了组件的复用性。

**建议修复**:
1. 达到最大深度时显示 tooltip 或禁用按钮（而非隐藏），提示"已达最大嵌套层数"
2. 将 `MAX_DEPTH` 改为可选 prop，默认值为 2

---

## 已确认的技术债务（来自回顾文档）

以下问题在回顾文档中已记录，本次审查确认其仍然存在：

| 债务项 | 状态 | 影响评估 |
|--------|------|----------|
| Epic 20 `description` 字段语义滥用 | ✅ 确认存在 (CR-01) | HIGH - 数据完整性风险 |
| Epic 20 `condition_expr` 字段无后端校验 | ✅ 确认存在 (CR-02) | HIGH - 安全性风险 |
| Epic 21 数据映射替代 | ✅ 确认存在 (CR-11) | LOW - 用户体验 |
| Epic 23 deviceId 类型不匹配 | ✅ 确认存在 (CR-10) | LOW - 功能降级 |
| Epic 23 OCR mock 模式 | ✅ 确认存在 | LOW - 功能限制（已有 TODO 标记） |
| 所有 Epic 缺少前端单元测试 | ✅ 确认 | MEDIUM - 回归风险 |
| 无后端 OCR 测试 | ✅ 确认 | MEDIUM - 回归风险 |

---

## 审查结论

本次审查发现 **12 个问题**（4 HIGH / 5 MEDIUM / 3 LOW）。

**HIGH 优先级问题**需要在下一个迭代中修复：
- CR-01/CR-02：字段语义滥用是架构级问题，随着数据量增长会越来越难修复
- CR-03：OCR 文件校验不足是安全漏洞
- CR-04：WebSocket 连接泄漏在长时间使用后会导致性能下降

**MEDIUM 优先级问题**建议在 2-3 个迭代内修复：
- CR-06 的"先删后建"模式是数据丢失的定时炸弹
- CR-08 的告警数不准确会误导运维决策
- CR-09 的全量加载在系统扩展时会成为瓶颈

**代码质量总体评价**：代码结构清晰，组件拆分合理，composable 模式使用得当。主要问题集中在数据层（字段滥用、校验缺失）和资源管理（WebSocket/Three.js 清理）。建议优先补充后端 schema 校验和资源清理逻辑。
