# Sprint Change Proposal - 单维护者治理调整

**日期:** 2026-08-12  
**触发 Story:** 39.1 站点隔离与 WebSocket 服务端授权  
**批准记录:** 用户在当前 Codex 任务中明确说明其为项目唯一开发者，并批准取消 Charlie、Dana 或其他 BMAD 虚拟角色的审批要求。

## 1. 问题摘要

Epic 39 原基线假设存在开发、安全、QA、产品和架构等多人角色，并把 Charlie、Dana 等 BMAD 角色的独立签署设为 Story 硬门禁。实际项目由 `proecheng` 单人维护，仓库也只有该账号一个协作者。继续要求不存在的审批人会永久阻塞 Story，诱发代签或虚构记录，反而破坏审计真实性。

## 2. 影响分析

- **Epic 影响:** Epic 39 的技术范围、12 个 Story、依赖关系和生产就绪目标不变。
- **Story 影响:** 所有 Epic 39 Story 取消独立证据审批要求，改由唯一维护者依据机器可读证据作出可审计结论。
- **文档影响:** PRD、Architecture、Epics、Story 39.1、证据 Schema、证据生成器和验证报告需要同步。
- **不受影响:** 应用运行时的关键命令职责分离、故障树/工单审批、现场 UAT、灾备、供应链、安全和性能控制继续有效。
- **生产影响:** Story 39.1 可在自身证据通过后关闭；Epic 39 总体生产门禁仍由其余 Story、NFR 复评和现场 UAT 决定。

## 3. 推荐方案

采用直接调整，工作量低、技术风险低、治理风险降低：

1. 将 Epic 39 的证据治理模式设为 `single-maintainer`。
2. 唯一维护者固定为 GitHub/项目账号 `proecheng`。
3. Story 清单不再包含或校验虚拟审批人签名，Story 结果使用 `PASS/BLOCKED` 而非审批语义。
4. Story 结论必须继续绑定 Git SHA、镜像摘要、原始机器可读测试、路径和哈希校验。
5. 将 Story 门禁与 Epic 39 总体生产门禁分开，防止单个 Story 通过被误读为生产批准。
6. 任何例外、限制或风险接受必须由 `proecheng` 具名记录，不允许静默忽略失败证据。

不采用回滚：现有授权实现和自动化证据有效，回滚不能解决治理模型不匹配。无需缩减产品范围或新增 Epic。

## 4. 具体变更

### PRD / Architecture

- 独立证据审批改为单维护者证据决策。
- D39-01~D39-08 由 `proecheng` 记录，不再要求不存在的角色签署。
- `CONDITIONAL REVIEW` 的风险接受由唯一维护者留痕。
- 保留运行时命令审批、现场 UAT 和全部不可豁免安全控制。

### Epics / Stories

- Epic 39 所有 Story 的实施与证据责任统一为 `proecheng`。
- 删除 Charlie、Dana、Alice、Winston、Amelia 作为强制审批人的配置。
- Story 39.1 Task 8.4 改为验证单维护者治理记录和完整证据，不再等待双人签名。

### Evidence Contract

- Manifest Schema 升级至 v2。
- `ownership` 仅记录 `maintainer: proecheng`。
- `approvals` 替换为 `governance`，明确 `independent_approval_required: false`。
- `production_gate` 拆分为 `story_gate` 与 `epic_production_gate`。

## 5. 实施交接

**范围分类:** Minor，Developer 直接实施。  
**实施者:** `proecheng` / 当前开发代理。  
**成功标准:** 文档和证据契约一致；Story 39.1 证据重新生成并验证；代码审查和 CI 通过；Epic 39 总体门禁不会因 Story 39.1 单独通过而解除。

## 6. Change Navigation Checklist

| ID | 状态 | 结论 |
|---|---|---|
| 1.1-1.3 | Done | Story 39.1 被不存在的双人审批永久阻塞，仓库仅有 `proecheng` 一个协作者 |
| 2.1-2.5 | Done | Epic 39 仍可按原范围完成，不新增/删除/重排 Epic |
| 3.1 | Done | PRD 仅调整交付治理，不改变产品目标 |
| 3.2 | Done | Architecture 需要区分 Story 与 Epic 总体门禁 |
| 3.3 | N/A | 无 UX 文档，且无界面变化 |
| 3.4 | Done | Story、Schema、生成器和证据报告需要同步 |
| 4.1 | Viable | 直接调整，低工作量、低技术风险 |
| 4.2 | Not viable | 回滚实现不能解决治理不匹配 |
| 4.3 | Not required | MVP 和产品范围无需改变 |
| 4.4 | Done | 选择直接调整 |
| 5.1-5.5 | Done | 问题、影响、方案、行动和单维护者责任已明确 |
| 6.1-6.2 | Done | 变更一致且可执行 |
| 6.3 | Done | 用户已明确批准立即修改 |
| 6.4 | N/A | 不新增、删除或重排 Story；状态在证据和审查完成后更新 |
| 6.5 | Done | 由唯一维护者实施、验证和留痕 |
