---
baseline_commit: 436a8e778037bf6fcf9140b757e9584e669ad33b
---

# Story 39.2: 命令、XSS 与生产凭据加固

Status: done

## Story

As a 安全负责人,
I want 命令审批、不可信内容和生产凭据在默认情况下保持安全,
so that 未分类命令、自审批、存储型脚本和默认凭据不能进入生产路径。

## Ownership And Traceability

- **实施与证据责任:** `proecheng`（唯一维护者）
- **证据治理:** `single-maintainer`；不要求 Charlie、Dana 或其他 BMAD 虚拟角色审批
- **优先级:** P0 / CRITICAL
- **NFR/行动追溯:** NFR-PR02、C2
- **依赖:** Epic 38 已完成；本 Story 无 D39 数值决策前置
- **不可豁免:** 未知命令放行、受保护命令自审批、未净化持久化 HTML 执行、生产默认或占位凭据
- **职责分离说明:** 单维护者治理不取消产品运行时的命令请求人与审批人分离

## Context

当前实现包含四条可直接进入生产路径的安全缺口：

- `command_service.get_risk_level()` 将未知命令回退为 `normal`，风险配置还允许把关键命令降为普通命令；节能执行服务可绕过命令审批服务直接调用设备控制。
- 关键命令审批未比较 `requester_id` 与 `approver_id`，现有测试甚至使用同一管理员提交和批准。
- 诊断报告将持久化 Markdown 经 `marked()` 后直接传入 `v-html`；删除确认框、Three.js 标签和部分 ECharts tooltip 也存在动态 HTML 执行面。
- 后端、默认管理员、网关、数据库和 Docker Compose 保留开发/占位凭据；代理使用 `origin: "*"` 与 `credentials: true`，前端 Nginx 缺少 CSP 和基础安全响应头。

本 Story 必须在执行副作用和网络监听之前失败关闭。开发与测试模式可以保留明确受控的开发默认值，但不得被生产模式接受。

## Acceptance Criteria

### AC1: 命令清单、参数 Schema 与风险分类默认拒绝

**Given** 任一 API、后台任务或服务准备执行设备控制命令
**When** 命令类型、风险分类或参数被解析
**Then** 命令必须存在于唯一、机器可读的显式注册表中，并声明命令 Schema、最低风险等级、是否需要审批、执行入口和自动化测试 ID
**And** 未知类型、缺失/无效分类、无法解析或不符合 Schema 的参数在创建成功审计、审批工单或执行副作用前被拒绝
**And** 运行时配置只能保持或提高命令的最低风险等级，不得把受保护命令降级为普通命令
**And** 所有实际命令执行入口统一调用同一策略校验，不允许 API、批量、计划任务或 `force` 参数旁路
**And** 新增未分类命令或执行入口使清单漂移门禁失败

### AC2: 受保护命令职责分离与不可抵赖审计

**Given** 受保护命令已由活动认证用户提交
**When** 用户批准、拒绝、重复处理或尝试绕过审批
**Then** 请求人和审批人身份只取自可信服务端认证上下文，且批准人必须与请求人不同
**And** 自审批、直接执行、重复批准、过期批准、状态竞争和绕过尝试在同一事务内拒绝，不产生执行副作用
**And** 拒绝、绕过尝试、超时、批准和最终执行结果均留下包含主体、命令、原因、时间与结果的审计记录
**And** 服务层直接调用与 HTTP API 具有相同保护，不能只在路由层校验

### AC3: 所有已知动态 HTML 执行面安全渲染

**Given** 持久化 Markdown、设备名称、组名称、拓扑标签、点位单位或其他不可信字符串进入前端
**When** 页面渲染富文本、确认框、Three.js 标签或 ECharts tooltip
**Then** `marked()` 输出在紧邻 `v-html` 的统一边界由成熟白名单净化器处理
**And** 原始 HTML、事件属性、`javascript:`/危险 `data:` URL、危险 SVG/MathML 与编码绕过不能执行
**And** 删除确认框不再使用 `dangerouslyUseHTMLString` 拼接动态值，普通标签优先使用 `textContent`，tooltip 优先使用 `richText` 或统一转义
**And** 合法标题、列表、表格、代码块和安全链接保持可读，外部链接具备安全的 `rel` 属性
**And** 持久化恶意 Markdown 通过真实报告获取与渲染路径的回归测试

### AC4: 生产凭据与不安全配置在启动最前端失败

**Given** 应用以明确的 `production` 环境启动
**When** 任何数据库初始化、默认用户创建、后台任务、监听器或网络服务启动前执行配置校验
**Then** 缺失的必需凭据、默认值、占位值、示例值、已知开发值、临时随机 JWT 密钥或弱默认管理员密码使进程以非零状态退出
**And** `DEBUG=true`、生产种子/演示/模拟模式、空的生产 MQTT 认证、默认网关密钥和不安全 CORS origin 均被拒绝
**And** 默认管理员只在明确启用 seed 时创建，使用配置注入的密码，不再硬编码 `admin123`
**And** 开发和测试模式仍可显式运行，生产校验错误只报告字段和原因，不打印秘密值
**And** Docker Compose 生产路径不再提供 PostgreSQL、JWT、管理员、MQTT 或网关凭据的弱回退值

### AC5: 后端与实际代理共享显式来源和浏览器安全策略

**Given** 浏览器通过 FastAPI、Node 代理或前端 Nginx 访问部署制品
**When** 发送允许/拒绝来源的普通请求、credentialed 请求和 CORS preflight，或读取 HTML/静态/API 响应
**Then** 后端与 Node 代理使用同一显式 origin allowlist，拒绝 `*`、`null`、含凭据/路径/查询的非法 origin 以及 production localhost
**And** 任何响应都不出现 `Access-Control-Allow-Origin: *` 与 `Access-Control-Allow-Credentials: true` 的组合
**And** 实际前端 Nginx 制品返回已批准的强制 CSP、`X-Content-Type-Options`、`Referrer-Policy`、点击劫持防护和 `Permissions-Policy`
**And** CSP 不允许脚本 `unsafe-inline`；样式兼容性按现有 ECharts/Vue 行为设置最小必要策略
**And** 自动化从实际启动的后端和代理响应验证允许/拒绝来源、preflight、CSP 与安全头，不能只扫描配置文本

### AC6: 阻断性回归与可审计证据有效

**Given** AC1-AC5 已实施
**When** 执行后端、前端、代理、部署制品和证据验证矩阵
**Then** 未知命令、自审批、降级、旁路、恶意 HTML、每个不安全生产配置和恶意 origin 全部被阻断
**And** 正常命令审批、合法 Markdown、开发/测试启动、允许 origin、API/WS 代理与 SPA fallback 保持兼容
**And** 测试结果不依赖跳过、空测试集、重试或固定等待
**And** Story 证据清单通过受信任 Schema、路径、大小、哈希、执行窗口、源码绑定和 AC 双向映射校验
**And** `single-maintainer` Story 门禁可记录 `PASS`，但 Epic 39 生产门禁保持独立，不因本 Story 通过自动解除

## Tasks / Subtasks

- [x] Task 1: 建立命令注册表和默认拒绝门禁 (AC: #1)
  - [x] 1.1 定义类型化命令注册表，记录参数 Schema、最低风险、审批要求、执行入口和测试 ID
  - [x] 1.2 将未知命令、无效分类和参数解析失败改为显式拒绝，并记录拒绝审计
  - [x] 1.3 限制风险配置只能作用于已注册命令且不得低于最低风险等级
  - [x] 1.4 盘点 `command_service`、`DeviceControlService`、`ExecutionService` 和批量/计划入口，统一执行前校验
  - [x] 1.5 增加注册表与运行时入口漂移测试，新增未分类命令或执行入口时失败

- [x] Task 2: 强制职责分离和审批状态原子性 (AC: #2)
  - [x] 2.1 在 service/事务层阻止 `approver_id == requester_id`，API 仅负责映射安全错误
  - [x] 2.2 对批准/拒绝使用条件更新或等效锁定，保证重复和并发状态转换只成功一次
  - [x] 2.3 为自批、绕过、重复、过期、拒绝和执行结果建立追加式安全审计事件
  - [x] 2.4 更新测试 fixture，使用真实且不同的请求人/审批人，不再固化自审批

- [x] Task 3: 建立统一安全富文本边界并关闭动态 HTML sink (AC: #3)
  - [x] 3.1 引入与 Vue 3/Vitest 兼容的成熟 sanitizer，集中配置允许标签、属性和 URL 协议
  - [x] 3.2 将诊断报告改为统一的安全 Markdown/富文本组件，唯一边界执行 `marked -> sanitize -> v-html`
  - [x] 3.3 移除五处删除确认框的 `dangerouslyUseHTMLString`，动态名称作为文本节点渲染
  - [x] 3.4 将 Three.js 标签改为 DOM/text API，并将不可信 ECharts tooltip 改为 rich text 或统一转义
  - [x] 3.5 增加持久化 Markdown、URL/Unicode 绕过、确认框名称、标签和 tooltip 的恶意/合法回归
  - [x] 3.6 增加静态门禁，禁止在批准的安全封装之外新增 `v-html`、动态 `innerHTML` 或 `dangerouslyUseHTMLString`

- [x] Task 4: 实现生产配置 fail-fast (AC: #4)
  - [x] 4.1 增加明确、类型化的应用环境配置；不得仅用 `debug=false` 推断 production
  - [x] 4.2 建立生产必需凭据及已知不安全值清单，提供集中且脱敏的校验函数
  - [x] 4.3 在 FastAPI lifespan 的任何数据库、seed、监听器和后台任务之前执行校验
  - [x] 4.4 让默认管理员遵守 `seed_enabled` 并使用 `settings.default_admin_password`；生产 seed 要求显式强密码
  - [x] 4.5 移除 Docker Compose 生产路径弱回退值，显式传递应用环境、管理员和网关/MQTT 凭据
  - [x] 4.6 覆盖每个拒绝字段、多个错误聚合、自定义安全配置和日志不泄密

- [x] Task 5: 收敛 CORS、CSP 和安全响应头 (AC: #5)
  - [x] 5.1 实现严格 origin 解析与生产校验，FastAPI 与 Node 代理消费同一 `CORS_ORIGINS` 契约
  - [x] 5.2 Node 代理按请求 origin 返回允许策略并拒绝恶意 preflight，移除通配来源与凭据组合
  - [x] 5.3 在前端 Nginx 的所有 location 保持一致安全头，处理 `add_header` 继承与 `always` 语义
  - [x] 5.4 配置可运行的强制 CSP，并回归核心页面、ECharts、Three.js、API、WebSocket 和下载
  - [x] 5.5 对实际启动的 FastAPI、Node 代理和 Nginx 制品运行允许/拒绝 origin、preflight 和响应头集成测试

- [x] Task 6: 回归和发布证据 (AC: #1-#6)
  - [x] 6.1 运行后端聚焦测试、命令/API 回归、生产启动矩阵、Ruff 和 Python compile
  - [x] 6.2 运行前端聚焦 Vitest、完整 Vitest、TypeScript、ESLint 和生产构建
  - [x] 6.3 运行 Node 代理与 Nginx 实例级 CORS/CSP/安全头检查，保持 API/WS/SPA 行为
  - [x] 6.4 在 `_bmad-output/test-artifacts/epic-39/39.2/` 生成原始结果、环境指纹、源码哈希、Schema、manifest 和独立验证结果
  - [x] 6.5 记录 `single-maintainer` Story 结论，明确未执行生产部署且 Epic 生产门禁仍为 `BLOCKED`

## Dev Notes

### Security Decisions

1. **默认拒绝发生在共享服务层。** 路由校验不能保护后台任务或直接 service 调用；任何最终执行函数必须要求已验证的类型化命令对象或调用统一策略入口。
2. **最低风险不可降级。** 数据库配置可以把命令从普通提升为关键，但不能把注册表声明的关键命令降为普通。
3. **运行时职责分离独立于项目治理。** `proecheng` 可独立完成 Story 证据决策，但产品中的受保护命令仍必须由不同用户批准。
4. **成熟 sanitizer 优先。** 不手写 HTML 解析器或用正则清理 HTML；使用当前 Vue/Vitest/jsdom 可支持的维护中库，并锁定依赖。
5. **明确 production。** 新增 `APP_ENV` 或项目等价枚举；开发默认不等于生产许可，生产配置在任何副作用前集中校验。
6. **origin 是结构化值。** 只允许完整的 `http(s)://host[:port]` origin；拒绝路径、查询、片段、用户信息、`null` 和通配符。
7. **安全头以实际响应为准。** Nginx `add_header` 在子 location 中会覆盖父级继承，测试必须覆盖 HTML、静态资源和代理响应。

### Command Registry Contract

建议在 `backend/app/services/command_registry.py` 建立类型化单一来源，至少包含：

```python
COMMAND_DEFINITIONS = {
    "ac_temp_set": CommandDefinition(schema=AcTempSetParams, minimum_risk="normal", protected=False),
    "power_off": CommandDefinition(schema=PowerOffParams, minimum_risk="critical", protected=True),
}
```

不要维护相互漂移的白名单、风险表和参数校验表。风险配置接口只接受注册表中的键；未知命令拒绝时也要写 `result="rejected"` 的审计记录，不能返回成功或 `normal`。

`DeviceControlService` 和 `ExecutionService` 当前是实际旁路。实施时应选择一个稳定契约：把它们的动作映射到已注册命令并统一提交，或让底层执行器只接受不可伪造的已验证命令对象。不要仅在 `/api/v1/commands/submit` 修复。

### Rich Text Contract

- 建议集中在 `frontend/src/security/html.ts` 和 `frontend/src/components/common/SafeRichText.vue`。
- 唯一允许 `v-html` 的组件接收原始 Markdown，由组件内部完成解析和净化；不要让调用方传入自称“已净化”的普通字符串。
- 外链只允许 `http`、`https`、`mailto`，补 `target/rel` 时保持 `noopener noreferrer`。
- `CabinetLabels.vue` 当前使用 `textContent`，应保留该安全模式。
- ECharts formatter 优先 `renderMode: "richText"`；必须使用 HTML 时，动态字段逐项经过统一 `escapeHtml()`。

### Production Configuration Contract

生产校验至少覆盖：

- `APP_ENV=production` 且 `DEBUG=false`
- 显式稳定的 `SECRET_KEY`，拒绝运行时自动生成和 `change-this-*`
- `DEFAULT_ADMIN_PASSWORD` 在启用 seed 时显式且非 `admin123`
- `DATABASE_URL`/`POSTGRES_PASSWORD` 不含 `dcim_password` 等已知开发值
- `VPP_API_KEY`、`GATEWAY_SECRET_KEY` 非默认/占位值
- MQTT 启用时用户名和密码均非空；Demo/Simulation 在 production 关闭
- CORS origin 通过严格解析且不包含 localhost/loopback、`*` 或 `null`

不得把秘密值写入异常、结构化日志、健康检查、环境指纹或证据包。凭据托管、轮换、TLS 和静态加密属于 Story 39.9，不在本 Story 宣称完成。

### Testing Requirements

- 后端：未知/空/大小写变体命令、无效参数、关键降级、自审批、重复/并发审批、过期审批、服务直调、计划/批量旁路和审计完整性。
- 前端：`script`、事件属性、SVG/MathML、混合大小写/控制字符 URL、HTML 实体/双重编码、合法 Markdown、确认框与 tooltip 动态字段。
- 配置：对每个不安全值单独参数化，并覆盖多个错误聚合、安全配置通过、生产监听前失败、开发/测试兼容和日志脱敏。
- 部署：允许/恶意/无 Origin、simple/preflight、credentials，以及 HTML/静态/API/错误响应的安全头；测试运行中的服务或容器。
- 回归：保留 Story 39.1 活动 JTI 与站点授权、命令超时、API/WS 代理、SPA fallback、ECharts/Three.js 页面和前端完整构建。

### Evidence Contract

证据目录：`_bmad-output/test-artifacts/epic-39/39.2/`。至少包含：

- 命令注册表快照和漂移结果
- 后端命令/审批与生产启动 JUnit
- 前端 XSS Vitest 原始结果
- 代理 CORS/CSP/安全头原始扫描结果
- 质量命令结果、环境指纹和 Story 源文件哈希
- `manifest.schema.json`、`manifest.yaml`、`evidence-validation.json`

Manifest 使用 `single-maintainer`、`maintainer: proecheng`、`independent_approval_required: false`，并分别记录 `story_gate` 和 `epic_production_gate`。证据校验必须从受信任仓库契约重算结果，拒绝陈旧、空、跳过、自报或与当前 changeset 不一致的产物；39.1 Schema 写死 Story ID，不得原样复制。

### Scope Boundaries

- **包含:** 命令默认拒绝/最低风险/职责分离/旁路，所有已发现动态 HTML sink，生产启动凭据校验，FastAPI/Node/Nginx CORS、CSP 与安全头。
- **排除:** Story 39.1 站点/WebSocket 授权；39.3 PostgreSQL 灾备；39.5 SBOM/漏洞扫描；39.9 密钥托管/轮换、TLS、静态加密和审计保留；39.12 OTA A/B、部署冒烟和自动回滚。
- 本 Story 不执行生产部署，不因软件测试通过宣称已获得生产批准。
- 审查发现的 OTA 状态签名、备份恢复路径穿越和 EMQX ACL 缺口另行进入对应安全/恢复 Story，不静默扩入本 Story。

### Project Structure Notes

- 后端沿用 `backend/app/core` 配置、`backend/app/services` 业务规则、`backend/app/api/v1` HTTP 映射和 `backend/tests` 测试结构。
- 前端沿用 Vue 3 Composition API、Vitest、Element Plus、ECharts 与 Three.js；共享安全组件放在 `frontend/src/components/common`，纯函数放在 `frontend/src/security`。
- Node 代理保留 `proxy/server.js`，Nginx 容器配置保留 `frontend/nginx.conf`；若增加测试，放在各自现有测试/脚本结构中，不复制生产配置。
- 保留 39.1 的活动会话、站点授权、WebSocket 首帧认证及证据可信绑定；不得通过降低授权策略让新测试通过。

### Previous Work And Git Intelligence

- Story 39.1 建立了 `single-maintainer` v2 证据合同、严格活动 JTI、站点授权、实际运行时清单和 SHA 绑定验证；39.2 应复用通用证据思路，但不能复制写死 `39.1` 的 Schema。
- 39.1 对抗审查证明静态源码扫描、自报派生产物、陈旧报告、跳过/空测试集和未绑定镜像摘要都可能产生假绿；39.2 验证器必须重算稳定结果。
- 当前基线为 `436a8e778037bf6fcf9140b757e9584e669ad33b`。Story 39.1 正式证据包在工作区有刷新但未提交的变更，39.2 分支、暂存和提交不得包含或还原这些文件。

### References

- [Source: `_bmad-output/planning-artifacts/epics.md` - Story 39.2]
- [Source: `_bmad-output/planning-artifacts/architecture.md` - 26.2, 26.3, 26.8, 26.9]
- [Source: `_bmad-output/planning-artifacts/prd.md` - NFR-PR02]
- [Source: `_bmad-output/planning-artifacts/sprint-change-proposal-2026-08-12.md` - single-maintainer governance]
- [Source: `backend/app/services/command_service.py`]
- [Source: `backend/app/services/device_control_service.py`]
- [Source: `backend/app/services/execution_service.py`]
- [Source: `backend/app/core/config.py`]
- [Source: `backend/app/main.py`]
- [Source: `frontend/src/views/diagnosis/Reports.vue`]
- [Source: `frontend/src/utils/three/labelRenderer.ts`]
- [Source: `proxy/server.js`]
- [Source: `frontend/nginx.conf`]
- [Source: `docker-compose.yml`]

## Definition Of Done

- [x] AC1-AC6 均有正向、负向自动化和原始机器可读证据，零跳过、零重试依赖、零空测试集
- [x] 未知命令、无效参数、关键降级、所有已知执行旁路和自审批均在副作用前拒绝并审计
- [x] 所有已知动态 HTML sink 已删除、文本化或集中净化，持久化恶意载荷不能执行
- [x] 每个不安全生产配置在任何初始化/监听前失败，安全配置可启动且日志/证据不泄密
- [x] FastAPI、Node 代理和 Nginx 的实际响应通过 CORS、CSP 与安全头矩阵
- [x] 后端/前端聚焦与回归质量门禁通过，API/WS/SPA 和 Story 39.1 授权无回归
- [x] 39.2 manifest 与当前 SHA/源码/原始结果绑定，并记录单维护者 Story 结论和独立 Epic 生产门禁
- [x] File List 与 Git diff 一致，未包含或还原 Story 39.1 证据包和其他用户工作区变更

## Story Completion Status

- **状态:** done
- **创建日期:** 2026-08-13
- **完成日期:** 2026-08-14
- **说明:** 四批对抗审查的 HIGH/MEDIUM 问题已全部修复，完整回归、正式证据生成和独立复验均通过；Story gate 为 `PASS`，Epic 39 production gate 仍为 `BLOCKED`。

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- 2026-08-13：后端最终全量回归 `3991 passed, 9 skipped`；前端完整 Vitest、TypeScript、ESLint、生产构建、Node 代理和 `git diff --check` 全部通过。
- 2026-08-14：正式证据执行窗口 `2026-08-14T02:41:38Z` 至 `2026-08-14T02:44:01Z`；独立复验于 `2026-08-14T02:46:40Z` 完成。
- 证据校验：`artifact_count=11`，源码快照 `145af4adf8115752805e85e97feb6e71f34e073bf414fd143b4c8b41918ac2a6`，manifest `d12a1b1ee8dc99e3f2dfe14bfd9af7ff1f2de24617cec3ae1b48552271534aad`。
- 2026-08-14：审查后端全量分片回归 `4016 passed, 9 skipped`；前端完整 Vitest、TypeScript、ESLint、生产构建和 Node 代理均通过。
- 2026-08-14：审查后正式证据窗口 `2026-08-14T05:09:46Z` 至 `2026-08-14T05:13:24Z`；独立新进程复验于 `2026-08-14T05:15:46Z` 完成。
- 审查后证据校验：`artifact_count=11`，源码快照 `d5b7f09ab861346ae8ba2dbc9383820dae610a3ea05dce7c5936ab6658a016c4`，manifest `eaf38ccec47c070ba5b15dc73b4ee9853d8cb32c6cb4a2ed32421ee0581192fe`。

### Implementation Plan

1. 以类型化命令注册表统一命令参数、最低风险、审批规则和执行入口，并在共享服务层默认拒绝。
2. 以条件更新和追加审计保证关键命令职责分离、过期处理和并发状态转换原子性。
3. 以 DOMPurify 和 `SafeRichText` 建立唯一富文本边界，清理确认框、Three.js 和 ECharts 动态 HTML sink。
4. 在 FastAPI 启动副作用前集中校验生产配置，并收敛 Docker Compose 的凭据注入。
5. 统一 FastAPI、Node 和 Nginx 的严格 origin、CSP 与安全头契约，并验证实际运行制品。
6. 生成绑定源码、镜像、环境、原始测试和治理结论的机器可读证据包，再由独立进程复验。

### Completion Notes List

- 建立 7 条命令、8 个入口的单一注册表，未知命令、无效参数、风险降级、服务直调和批量旁路均在副作用前拒绝。
- 关键命令禁止请求人自批，批准、拒绝和超时状态使用条件更新；并发批准测试证明只成功一次且只写一条成功审计。
- 持久化 Markdown 通过 `marked -> DOMPurify -> v-html` 唯一边界，其他动态 sink 已文本化或转义；静态门禁覆盖整个前端源码树。
- 生产配置在数据库、seed、后台任务和监听前 fail-fast；FastAPI、Node WebSocket/HTTP 与 Nginx 实际响应通过来源和安全头矩阵。
- 删除被强制 CSP 阻止且在离线环境不可靠的 Google Fonts 远程导入，保留本地和系统字体回退。
- 加固证据工具的无副作用注册表加载、Windows UTF-8 子进程解码、Node 24 测试摘要解析和严格 manifest 字段投影。
- 正式证据结果：后端 `151/151`、前端 `28/28`、代理 `5/5`、浏览器 `1/1`、质量命令 `6/6`；AC1-AC6 均为 `PASS`。
- 治理结论为 `single-maintainer`，维护者 `proecheng`，不要求虚拟角色审批；Story gate 为 `PASS`，Epic 39 production gate 仍为 `BLOCKED`。
- 四批对抗审查修复了命令副作用前校验、富文本与 tooltip、生产凭据/CORS、同源 WebSocket 首帧认证，以及证据 changeset/CSP/Schema 绑定问题；无 HIGH/MEDIUM 遗留。

### File List

- `.env.example`
- `_bmad-output/implementation-artifacts/39-2-command-xss-and-production-credential-hardening.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `_bmad-output/test-artifacts/epic-39/39.2/backend-cors-runtime-results.json`
- `_bmad-output/test-artifacts/epic-39/39.2/command-registry-snapshot.json`
- `_bmad-output/test-artifacts/epic-39/39.2/environment-fingerprint.json`
- `_bmad-output/test-artifacts/epic-39/39.2/evidence-validation.json`
- `_bmad-output/test-artifacts/epic-39/39.2/manifest.schema.json`
- `_bmad-output/test-artifacts/epic-39/39.2/manifest.yaml`
- `_bmad-output/test-artifacts/epic-39/39.2/nginx-browser-results.json`
- `_bmad-output/test-artifacts/epic-39/39.2/nginx-security-results.json`
- `_bmad-output/test-artifacts/epic-39/39.2/proxy-security-results.json`
- `_bmad-output/test-artifacts/epic-39/39.2/pytest-security.xml`
- `_bmad-output/test-artifacts/epic-39/39.2/quality-command-results.json`
- `_bmad-output/test-artifacts/epic-39/39.2/source-file-hashes.json`
- `_bmad-output/test-artifacts/epic-39/39.2/vitest-xss-results.json`
- `backend/.env.example`
- `backend/app/api/v1/command.py`
- `backend/app/core/config.py`
- `backend/app/main.py`
- `backend/app/seeds/minimal_seed.py`
- `backend/app/services/command_registry.py`
- `backend/app/services/command_service.py`
- `backend/app/services/device_control_service.py`
- `backend/app/services/execution_service.py`
- `backend/gateway/status_reporter.py`
- `backend/tests/api/test_energy_ocr.py`
- `backend/tests/services/test_device_control.py`
- `backend/tests/services/test_execution_service.py`
- `backend/tests/services/test_ocr_service.py`
- `backend/tests/test_bacnet_ip_adapter.py`
- `backend/tests/test_cabinet_usage.py`
- `backend/tests/test_command.py`
- `backend/tests/test_communication_monitor.py`
- `backend/tests/test_config_push.py`
- `backend/tests/test_connection_test.py`
- `backend/tests/test_device_status_board.py`
- `backend/tests/test_dry_contact.py`
- `backend/tests/test_gateway.py`
- `backend/tests/test_gateway_api.py`
- `backend/tests/test_gateway_registration.py`
- `backend/tests/test_http_rest_adapter.py`
- `backend/tests/test_mqtt_adapter.py`
- `backend/tests/test_opc_ua_adapter.py`
- `backend/tests/test_password_policy.py`
- `backend/tests/test_point_import.py`
- `backend/tests/test_story_39_2_commands.py`
- `backend/tests/test_story_39_2_cors.py`
- `backend/tests/test_story_39_2_evidence.py`
- `backend/tests/test_story_39_2_production_config.py`
- `deploy/nginx/dcim.conf`
- `docker-compose.yml`
- `e2e/story-39-2-nginx-security.spec.ts`
- `e2e/story-39-2.playwright.config.ts`
- `frontend/Dockerfile`
- `frontend/nginx.conf`
- `frontend/package-lock.json`
- `frontend/package.json`
- `frontend/src/components.d.ts`
- `frontend/src/components/bigscreen/CabinetLabels.vue`
- `frontend/src/components/bigscreen/charts/PowerDistribution.vue`
- `frontend/src/components/bigscreen/charts/PueTrend.vue`
- `frontend/src/components/bigscreen/charts/TemperatureTrend.vue`
- `frontend/src/components/charts/PieChart.vue`
- `frontend/src/components/charts/RealtimeChart.vue`
- `frontend/src/components/common/SafeRichText.test.ts`
- `frontend/src/components/common/SafeRichText.vue`
- `frontend/src/components/common/index.ts`
- `frontend/src/components/demand/DemandCurveMini.vue`
- `frontend/src/components/demand/LoadPeriodChart.vue`
- `frontend/src/components/energy/DemandDashboard.vue`
- `frontend/src/components/energy/DeviceShiftDetailDrawer.vue`
- `frontend/src/components/energy/PrecoolTimeline.vue`
- `frontend/src/components/energy/ScheduleDashboard.vue`
- `frontend/src/components/energy/TemperaturePredictionChart.vue`
- `frontend/src/security/html-sink-policy.test.ts`
- `frontend/src/security/html.test.ts`
- `frontend/src/security/html.ts`
- `frontend/src/styles/index.scss`
- `frontend/src/utils/three/labelRenderer.test.ts`
- `frontend/src/utils/three/labelRenderer.ts`
- `frontend/src/views/alarm/shield.vue`
- `frontend/src/views/capacity/index.vue`
- `frontend/src/views/diagnosis/ProbabilityTuning.vue`
- `frontend/src/views/diagnosis/Reports.test.ts`
- `frontend/src/views/diagnosis/Reports.vue`
- `frontend/src/views/diagnosis/TimeWindowTuning.vue`
- `frontend/src/views/energy/analysis.vue`
- `frontend/src/views/energy/monitor.vue`
- `frontend/src/views/energy/topology.vue`
- `frontend/src/views/gateway/index.vue`
- `frontend/src/views/history/index.vue`
- `frontend/src/views/login/index.vue`
- `frontend/src/views/power/battery.vue`
- `frontend/src/views/power/cabinet.vue`
- `frontend/src/views/power/pdu.vue`
- `frontend/src/views/power/ups.vue`
- `proxy/package.json`
- `proxy/server-temp.js`
- `proxy/server.js`
- `proxy/server.test.js`
- `scripts/story_39_2_evidence.py`
- `scripts/story_39_2_governance.py`
- `scripts/story_39_2_manifest.schema.json`

## Senior Developer Review (AI)

- **Reviewer:** GPT-5 Codex
- **Date:** 2026-08-14
- **Outcome:** Approve
- **Review mode:** 四批对抗审查，用户选择自动修复全部 HIGH/MEDIUM 问题
- **Findings:** 17 High、7 Medium，全部修复；0 个 HIGH/MEDIUM 遗留
- **命令与审批:** 修复 `force` 边界绕过、批量/自动任务部分执行、未知任务默认映射、审计设备名伪造和服务层审批旁路。
- **前端安全:** 清理全部已发现 HTML tooltip，收紧安全链接协议和外链属性，增加真实报告路径回归，并让诊断 WebSocket 使用同源首帧认证且不再把 token 放入 URL。
- **生产配置:** 生产数据库限定 `postgresql+asyncpg`，拒绝编码弱密码、短密码、空白 MQTT 用户名、loopback CORS 和未规范化环境值；最小种子直调也强制 `SEED_ENABLED`。
- **证据可信度:** 必测集合加入 `ExecutionService`、真实报告和 WebSocket 认证回归；manifest changeset、artifact 唯一性、强 CSP 指令和 Schema 副本均与受信任源码重算绑定。
- **Verification:** 后端 `4016 passed, 9 skipped`；前端完整 Vitest 通过；正式门禁后端 `151/151`、前端 `28/28`、Node `5/5`、Playwright `1/1`、质量命令 `6/6`；独立证据复验 `PASS`。
- **Governance:** `single-maintainer`，维护者 `proecheng`，无审批记录且不要求独立审批；Story gate `PASS`，Epic 39 production gate `BLOCKED`。

## Change Log

- 2026-08-13: 创建 Story 39.2，状态设为 `ready-for-dev`。
- 2026-08-14: 完成命令、XSS、生产配置和浏览器安全加固；生成并独立校验证据包，状态设为 `review`。
- 2026-08-14: 完成四批对抗审查并修复全部 HIGH/MEDIUM 问题；重跑完整回归、重新生成和独立验证证据包，状态设为 `done`。
