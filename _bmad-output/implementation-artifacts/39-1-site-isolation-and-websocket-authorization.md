---
baseline_commit: a9b872155f8554136f456e6d15116e721270761c
---

# Story 39.1: 站点隔离与 WebSocket 服务端授权

Status: in-progress

## Story

As a 安全负责人,
I want 所有对象访问与实时流都执行完整的服务端站点和会话授权,
so that 跨站点用户无法通过 API、猜测 ID 或 WebSocket 获得未授权数据。

## Ownership And Traceability

- **责任人:** Amelia（开发负责人）
- **证据审批:** Charlie（安全负责人）、Dana（QA 负责人）
- **优先级:** P0 / CRITICAL
- **NFR/行动追溯:** NFR-PR01、C1
- **依赖:** Epic 38 已完成；本 Story 无 D39 数值决策前置，可立即实施
- **不可豁免:** 跨站点访问或 WebSocket 越权不得通过 D39-08 例外放行

## Context

当前系统已经具备 JWT、角色依赖、`UserSession.token_jti`、`UserSite`、`get_user_site_ids()` 和 `require_site_access()`，但这些能力没有贯穿全部对象和实时流：

- HTTP 仅在 JWT 含 `jti` 时检查活动会话，缺少 `jti` 的旧令牌仍可通过受保护接口。
- 设备列表等少数端点应用了站点过滤，但详情、修改、删除、聚合、导入导出和间接对象仍存在跨站点 IDOR。
- `topology.py` 等已挂载路由存在只依赖数据库、未执行认证或站点授权的路径。
- WebSocket 握手只确认用户名存在且用户启用，连接管理器只保存裸 `WebSocket`；角色目标由前端过滤，广播没有站点过滤。
- 登出、并发会话挤出、禁用用户、角色降级和站点收回不会使存量 WebSocket 连接失效。
- 实时采集缓存已经包含 `site_id`，但实时/告警广播载荷没有稳定传播该字段。

本 Story 必须以运行时实际挂载的路由、频道和广播生产者为范围来源。已知漏洞文件只是首批修复入口，不能替代完整盘点。

## Acceptance Criteria

### AC1: 完整、机器可读且默认拒绝的授权清单

**Given** 应用加载全部 HTTP 与 WebSocket 路由
**When** 执行授权清单生成、启动校验或 CI 门禁
**Then** 每个已挂载 HTTP 路由、WebSocket 入口、服务端频道和广播生产者都有唯一的机器可读策略
**And** HTTP 策略至少记录 `method`、规范化路径、`operation_id/name`、访问类型、允许角色、动作、资源类型、站点归属解析器、活动会话要求和自动化测试 ID
**And** 访问类型只能是显式枚举，例如 `PUBLIC`、`GLOBAL`、`SITE_LIST`、`SITE_OBJECT`
**And** 框架内置、健康检查和真正的全局资源也必须显式分类，不得因排除规则而隐式放行
**And** 缺失、重复、未知、残留、没有测试映射或无法解析归属的条目使生产启动校验和 CI 失败
**And** 新增未分类路由、频道或广播生产者时，门禁在同一变更中失败
**And** 清单、运行时路由快照和差异结果作为原始证据发布

### AC2: 所有对象访问在服务端执行角色、活动会话和站点范围校验

**Given** 用户通过受保护 HTTP 接口读取或修改对象
**When** 服务端执行列表、详情、创建、更新、删除、动作、批量、导入导出或聚合查询
**Then** 在返回数据或产生写入副作用前同时验证允许角色、活动 JTI 和对象所属站点
**And** 受保护接口拒绝缺失、伪造、过期、无 `jti` 或已撤销的令牌
**And** 未指定站点的列表只返回用户允许站点的对象；显式请求越权站点返回 `403`
**And** 通过猜测 ID 访问站外对象与访问不存在对象使用一致的 `404` 行为，避免泄露对象是否存在
**And** 批量请求只要包含一个无权对象或无权目标站点，就在产生任何副作用前原子失败
**And** 对象改绑站点时同时校验源站点和目标站点权限
**And** 间接资源通过可信数据库关系解析归属，不信任客户端提交的 `site_id`
**And** 非管理员对 `site_id IS NULL` 或无法解析归属的业务对象默认无权；管理员可访问并修复归属
**And** `admin` 的全站语义继续使用 `site_ids=None`，非管理员空集合明确表示无可访问数据

### AC3: WebSocket 连接绑定服务端授权上下文并由服务端过滤

**Given** 客户端连接 `/ws/realtime`、`/ws/alarms`、`/ws/system` 或清单中其他受支持入口
**When** 首帧认证成功
**Then** 服务端连接上下文绑定 `user_id`、活动 `jti`、当前角色、允许站点集合、频道和已授权订阅
**And** 浏览器不再把原始访问令牌放在 URL query；连接建立后必须在短超时内发送认证帧，认证完成前不处理订阅或发送业务数据
**And** 缺失、畸形、伪造、过期、无 `jti`、已撤销会话或禁用用户以关闭码 `4001` 拒绝
**And** 客户端提交的 `site_id`、`point_ids`、`area_codes` 或频道只能缩小服务端授权集合，不能扩大权限
**And** 每条业务消息都被显式分类为 `site-scoped` 或批准的 `global`；站点消息缺少可验证 `site_id` 时拒绝发送并记录安全事件
**And** 角色和站点过滤完全由服务端执行；不得依赖 `target_roles` 字段或前端隐藏完成授权
**And** 未知频道、越权订阅和畸形过滤器默认拒绝
**And** `/ws/realtime`、`/ws/alarms`、`/ws/system` 路径，现有业务消息 envelope、30 秒心跳和前端重连语义保持兼容

### AC4: 会话、角色和站点变更使存量连接失效

**Given** 用户已经建立 WebSocket 连接
**When** 用户登出、JTI 被并发会话限制挤出、会话被撤销、用户被禁用/删除、角色被降级或站点权限被收回
**Then** 该连接在下一条业务消息前不再获得数据并以 `4001` 关闭或被强制重新认证
**And** 角色或站点扩权不能静默扩大旧连接权限，客户端必须重新认证后获得新上下文
**And** 登录、登出和用户管理事务只在数据库提交成功后触发连接失效
**And** 广播前的活动会话校验、显式失效通知和有界周期重验共同覆盖长期连接，不允许只在首次握手时做一次快照

### AC5: 阻断性负向矩阵和生产证据全部有效

**Given** 两个隔离站点、`admin/operator/viewer`、零/单/多站点授权用户和真实活动会话
**When** 执行 HTTP、WebSocket 和端到端授权矩阵
**Then** 跨站点 list/detail/create/update/delete/action/batch/import/export/aggregate/stream 全部按 AC2/AC3 拒绝
**And** Device、Gateway、DataSource、Point、Alarm、Threshold、Realtime/History、空间层级、Cooling/Topology、Video/OTA 等直接或间接对象至少各有代表性正向与负向测试
**And** 猜测 ID、混合站点批量、跨站点改绑、角色降级、禁用用户、登出、并发挤出和撤销会话全部阻断
**And** A/B 站点用户连接同一频道时各自只收到本站数据，角色消息只到达允许角色
**And** 自动化证明客户端过滤被关闭或绕过时仍无法收到未授权数据
**And** Story 证据清单通过 Schema/路径/哈希校验，并由 Charlie 与 Dana 独立审批

## Tasks / Subtasks

- [x] Task 1: 建立授权策略唯一来源和清单门禁 (AC: #1)
  - [x] 1.1 从 FastAPI 运行时路由表枚举所有已挂载 HTTP/WebSocket 入口，规范化 `method + path template + operation_id/name`
  - [x] 1.2 新建机器可读授权策略，逐项声明访问类型、角色、动作、资源、归属解析器、活动会话和测试映射
  - [x] 1.3 清点服务端 `realtime/alarms/control/system/linkage` 频道、前端频道和全部广播调用点；对未挂载/未使用频道明确删除、映射或安全接入结论
  - [x] 1.4 新增清单校验器与测试：缺项、重复、未知枚举、残留项、无测试 ID、未分类生产者全部失败
  - [x] 1.5 在生产启动路径执行同一校验；测试/开发环境也不得把缺失策略解释为允许访问

- [x] Task 2: 统一 HTTP 身份与站点授权上下文 (AC: #2, #4)
  - [x] 2.1 在现有 `deps.py`/授权模块上建立请求级 `SiteAccessContext`，包含 `user_id/role/jti/site_ids`
  - [x] 2.2 收紧 `get_current_user`：所有受保护请求必须有活动 JTI；移除无 JTI 旧 token 的放行分支
  - [x] 2.3 复用并增强 `get_user_site_ids()`、`require_site_access()`，提供列表 scope 和对象归属解析的统一 helper
  - [x] 2.4 为直接资源和间接资源实现可测试的站点解析器，禁止各端点复制不一致的临时查询
  - [x] 2.5 统一状态码和空站点语义：显式越权过滤 `403`、站外对象 ID `404`、非管理员未归属对象默认拒绝

- [x] Task 3: 按清单关闭全部 HTTP 对象授权缺口 (AC: #1, #2, #5)
  - [x] 3.1 修复已确认的 P0 面：`topology.py` 全路由认证，以及 Device/Gateway/DataSource/Spatial 的详情、变更、动作、导入导出和聚合
  - [x] 3.2 修复间接对象面：Point、Alarm、Threshold、Realtime、History、Cooling、TopologyConfig、Precool
  - [x] 3.3 审核 Power、Report、Statistics、DataQuality、FloorMap、PredictiveMaintenance、Video、OTA 及清单发现的其余已挂载路由
  - [x] 3.4 列表查询将请求过滤与服务端允许站点求交；对象查询在同一 SQL 或副作用前完成站点约束，避免先读/写后检查
  - [x] 3.5 批量和改绑操作预先解析全部源/目标归属，并在一个事务内原子拒绝混合越权请求

- [x] Task 4: 实现 WebSocket 服务端连接上下文和发送过滤 (AC: #3, #4)
  - [x] 4.1 将 `verify_websocket_token() -> bool` 替换为返回完整授权上下文的验证器，并严格检查活动 JTI
  - [x] 4.2 将连接管理器从裸 socket 列表改为连接上下文集合，同时保持心跳、断连清理和连接计数
  - [x] 4.3 使用短超时首帧认证替代 URL query 中的原始 JWT；认证完成后才确认连接可订阅
  - [x] 4.4 解析并验证 `subscribe/unsubscribe/ping/pong`；未知 action、频道或越权过滤器默认拒绝
  - [x] 4.5 让所有广播 API 显式接收作用域、可信 `site_id` 和可选角色目标；站点消息缺归属时不发送
  - [x] 4.6 更新全部生产者传播站点归属，优先复用采集管道已有 `_point_meta_cache.site_id`
  - [x] 4.7 广播使用连接快照并安全清理失败连接，避免遍历时修改集合；不得对每个连接逐消息执行数据库 N+1

- [x] Task 5: 将会话和权限变更接入连接失效 (AC: #4)
  - [x] 5.1 登出成功后按 JTI 断开连接；并发会话限制提交后断开被挤出的 JTI
  - [x] 5.2 用户禁用/删除、角色修改和站点权限替换提交后按用户断开或强制重新认证
  - [x] 5.3 增加广播前活动会话检查和有界周期重验，确保长期连接不会无限持有过期上下文
  - [x] 5.4 对失效失败记录结构化安全日志，不得因通知失败回滚已提交的授权变更

- [x] Task 6: 更新前端认证与订阅兼容层 (AC: #3, #4)
  - [x] 6.1 `WebSocketClient` 连接后发送认证帧，不再把 token 拼入 URL
  - [x] 6.2 收到认证成功响应后才恢复订阅；认证失败不进入业务 connected 状态
  - [x] 6.3 保持每频道单连接、指数退避、最多 10 次重连、降级标志、心跳和站点切换后订阅恢复
  - [x] 6.4 `currentSiteId=null` 仅代表当前用户全部授权站点；任何客户端筛选都只能缩小服务端上下文
  - [x] 6.5 为认证帧、失败关闭、重连重认证和站点切换补充 Vitest 覆盖

- [x] Task 7: 建立阻断性自动化矩阵 (AC: #1-#5)
  - [x] 7.1 新增授权清单测试，并添加“新增未分类 HTTP/WS 路由、频道或生产者时必失败”的突变场景
  - [x] 7.2 扩展后端双站点对象矩阵，使用真实 JWT/JTI 和真实依赖链，不用直接 override 站点列表代替端到端授权
  - [x] 7.3 使用 FastAPI/Starlette WebSocket 测试客户端覆盖首帧认证、站点/角色过滤、畸形订阅和存量连接撤销
  - [x] 7.4 扩展 Playwright 授权矩阵，覆盖双站点 list/detail/mutation/stream、猜测 ID、角色降级和会话撤销
  - [x] 7.5 测试不依赖任意固定等待或重试；通过可观察消息、关闭事件和服务端状态断言同步
  - [x] 7.6 回归现有站点管理、认证会话、设备/点位、告警、诊断消息格式和前端 Story 27.6 测试

- [ ] Task 8: 发布可审计证据 (AC: #5)
  - [x] 8.1 在 `_bmad-output/test-artifacts/epic-39/39.1/` 生成授权清单、差异、HTTP/WS 矩阵、生产者清单、JUnit、Playwright 和 OpenAPI 快照
  - [x] 8.2 创建 `manifest.yaml`，记录 Git SHA、前后端镜像摘要、环境指纹、工具版本、精确命令、UTC 时间、原始产物、指标、AC 映射、限制和责任人
  - [x] 8.3 对清单引用文件执行存在性与哈希校验；截图和文字摘要只能作为补充
  - [ ] 8.4 由 Charlie 和 Dana 独立签署证据；任何缺失、失败或跨站点残余风险保持生产门禁 `BLOCKED`

## Dev Notes

### Security Decisions

1. **严格活动会话:** HTTP 与 WebSocket 都必须要求 `jti`，并验证 `UserSession.user_id`、`token_jti`、`is_active=True` 与 token 用户一致。不能只按全局唯一 JTI 查会话而不核对用户。
2. **首帧认证:** 浏览器 WebSocket 不能可靠设置 Bearer header。本 Story 采用 WSS 连接后的首帧认证，避免原始 JWT 进入 URL、反向代理访问日志和浏览器历史。认证前只允许认证帧，超时或失败关闭 `4001`。
3. **服务端是授权事实来源:** 前端 `site_id`、`target_roles` 和订阅过滤仅是 UX/流量优化，不能成为权限依据。
4. **默认拒绝:** 未分类路由、未知频道、缺失站点归属、解析失败和缺少测试映射都不能降级为全局广播或全站访问。
5. **枚举保护:** 明确请求无权 `site_id` 返回 `403`；通过对象 ID 猜测站外对象返回 `404`。测试必须固定这一契约，避免端点各自选择。
6. **管理员语义:** 延续现有 `None = all sites`，但连接上下文和清单序列化必须明确区分 `None` 与空集合。

### Authorization Inventory Contract

建议新建 `backend/authz_inventory.yaml` 作为审计制品和策略索引，并由代码中的类型化枚举/解析器驱动校验。至少包括：

```yaml
http:
  - key: "GET /api/v1/devices/{device_id}::get_device"
    access: SITE_OBJECT
    roles: [admin, operator, viewer]
    action: read
    resource: device
    resolver: device.site_id
    active_session: true
    tests: [AUTHZ-DEVICE-DETAIL-01]
websocket:
  endpoints: []
  channels: []
  producers: []
```

门禁以 `app.routes` 中实际挂载的运行时集合为准，而不是只统计源文件装饰器。自动生成的 `HEAD/OPTIONS`、docs/openapi、健康检查等需要确定且显式的框架策略；禁止用过宽 glob 静默排除。

### Trusted Ownership Paths

| 资源族 | 可信站点归属路径 | 关键约束 |
|---|---|---|
| Device / Gateway / DataSource / Site | 对象直接 `site_id` 或 Site 自身 ID | 请求参数不得覆盖数据库归属 |
| Point | `Point.device_id -> Device.site_id` | 无设备或无站点时非管理员拒绝 |
| Realtime / History / Threshold / Alarm | 业务对象 `-> Point -> Device -> Site` | 聚合和导出同样应用 scope |
| Floor / Room / Row / Cabinet | `Cabinet -> Row -> Room -> Floor -> Site`（按实际模型核实） | 任一断链默认拒绝 |
| Cooling / Topology / Precool | 通过其设备、区域或空间外键解析 | 不得把 `area_code` 当作站点授权 |
| OTA / Gateway action | `Task/Action -> Gateway -> Site` | 下发前检查源对象和目标站点 |

清单过程中发现的新资源族必须补充一个可信解析器和至少一组正/负测试。禁止以 `hasattr(site_id)` 或客户端字段作为通用授权捷径。

### Current Code And Required Changes

- `backend/app/api/deps.py`
  - 当前：HTTP JWT 校验、用户启用检查；仅当 `jti` 存在时检查会话；已有角色和站点 helper。
  - 修改：严格活动 JTI、请求级上下文、统一列表 scope 与对象解析 helper。
  - 保留：OAuth2 Bearer、现有角色语义和 admin 全站语义。
- `backend/app/main.py`
  - 当前：`verify_websocket_token()` 只返回 bool；三个 WS 入口从 query 取 token；路由循环只接收文本。
  - 修改：首帧认证、完整上下文、订阅解析、撤销关闭和启动授权清单校验。
  - 保留：现有路径、`4001`、应用生命周期和心跳启停。
- `backend/app/services/websocket.py`
  - 当前：每频道裸 socket 列表；所有广播全员发送；`broadcast_to_role()` 仅写 `target_roles`。
  - 修改：连接上下文、服务端站点/角色/订阅过滤、会话重验、用户/JTI 失效 API 和并发安全清理。
  - 保留：实时 `{type,data}`、告警 `{type:"alarm",action,data}`、诊断走 alarms、ping/pong 和连接指标。
- `backend/app/api/v1/device.py`
  - 当前：仅列表使用 `get_user_site_ids`；tree、summary、status-board、详情、点位、聚合详情、修改和删除未统一过滤。
  - 修改：所有读写和聚合按服务端站点 scope；创建/改绑验证目标站点。
- `backend/app/api/v1/point.py`
  - 当前：列表、详情、创建、修改、删除、启停、导入导出和设备关联均无站点 scope。
  - 修改：全部通过 `Point -> Device -> Site` 或目标 Device 归属授权；跨站点关联原子拒绝。
- `backend/app/api/v1/__init__.py` 与全部已挂载 v1 模块
  - 当前：约 60 个模块集中挂载，没有统一授权清单门禁；故障树详情等内联路由也必须分类。
  - 修改：运行时逐路由登记并修复清单发现的缺口；尤其处理当前未鉴权的 topology 面。
- `backend/app/services/ingest_pipeline.py` 及全部广播生产者
  - 当前：点位元数据缓存已有 `site_id`，但实时和告警 WS 载荷未稳定传递；27 个已知调用点跨多个 engine/service/api 文件。
  - 修改：传播可信站点归属并调用强类型广播 API；global 消息只能来自明确 allowlist。
- `backend/app/api/v1/auth.py`、`backend/app/api/v1/user.py`
  - 当前：会话/用户/角色/站点数据库状态会变更，但不会同步失效 WS 连接。
  - 修改：事务提交后按 JTI 或用户通知连接管理器，失败记录安全日志。
- `frontend/src/api/websocket.ts`、`frontend/src/composables/useWebSocketManager.ts`
  - 当前：URL query 拼接 JWT；支持心跳、指数退避、单连接、订阅记录和切站重连。
  - 修改：首帧认证与认证成功后恢复订阅。
  - 保留：单连接、最多 10 次重连、降级标志和 `null = 当前用户全部授权站点`。

### WebSocket Protocol Guardrails

认证帧与成功响应应使用稳定 Schema，例如：

```json
{"action":"authenticate","token":"<access-token>"}
{"type":"authenticated"}
```

- 认证成功响应不得回显 token、JTI、完整站点列表或其他敏感上下文。
- 认证帧、异常、关闭原因、访问日志和测试报告不得记录原始 token；所有诊断输出必须脱敏。
- 认证前收到非认证帧、重复认证、未知 action 或超限 payload 时默认关闭或返回不泄露权限细节的错误。
- 业务 envelope 保持不变；`site_id` 可以作为服务端路由元数据，不要求暴露给不需要它的前端展示层。
- `target_roles` 可为兼容保留，但服务端必须在发送前执行角色过滤。
- `system` 全局消息必须有显式 allowlist；不能把缺失 `site_id` 自动当作 global。
- 广播遍历使用稳定快照，发送失败和撤销连接在遍历后统一清理。

### Revocation And Scalability Guardrails

- API 内的 logout、session kick、user status/role/site mutation 提供提交后立即失效，确保本进程下一条业务消息前阻断。
- 长连接还需有界周期重验活动会话。实现可按唯一 JTI 批量查询或短期缓存，禁止逐连接逐消息 N+1。
- 角色/站点变更应让旧连接重新认证，不在旧上下文上做静默扩权。
- Story 39.10 将决定生产单/多实例拓扑和跨实例 fan-out。本 Story 不应私自引入未经批准的消息代理架构，但必须把跨实例失效接口边界和当前限制写入证据。

### Framework And Dependency Constraints

- 复用仓库现有 FastAPI/Starlette WebSocket、SQLAlchemy AsyncSession、python-jose、Pydantic、pytest/httpx、Vue、Vitest 和 Playwright 能力。
- 不为本 Story 引入第二套认证框架、WebSocket 服务或策略引擎；授权唯一来源必须与现有依赖注入和路由挂载方式集成。
- 机器可读清单使用现有 YAML/结构化解析能力，禁止通过正则或字符串拼接解析 YAML。
- 本 Story 不需要升级框架或依赖版本。若实现确实需要新增或升级包，必须单独说明安全原因、锁文件影响和完整回归范围，不能作为隐含改动带入。

### Testing Requirements

后端至少运行：

```powershell
Set-Location backend
pytest -q tests/test_authorization_inventory.py tests/test_story_39_1.py tests/test_auth_session.py tests/test_site_isolation.py tests/test_site_management.py tests/test_device_detail.py tests/test_point_data.py
```

前端至少运行：

```powershell
Set-Location frontend
npm run test -- src/__tests__/story-27-6-site-filter.test.ts src/__tests__/composables/useWebSocket.test.ts
npm run typecheck
```

端到端至少运行新授权矩阵与现有角色矩阵。测试数据必须隔离，且不得通过固定 `waitForTimeout()` 或重试掩盖授权竞态。

### Evidence Contract

目录：`_bmad-output/test-artifacts/epic-39/39.1/`

必需原始产物：

- `authorization-inventory.yaml` 或等价规范化清单
- `authorization-inventory-diff.json`
- `openapi-authz-snapshot.json`
- `websocket-producer-inventory.json`
- `http-authz-matrix-results.json`
- `websocket-authz-matrix-results.json`
- `pytest-authz.xml`
- `playwright-authz-results.json`
- `manifest.yaml`

`manifest.yaml` 必须满足 Architecture 26.8 的字段要求，并为每个 AC 指向原始产物。清单不得预填不存在的 Git SHA、镜像摘要、签署或 PASS 结论。

### Scope Boundaries

- 本 Story 关闭服务端授权和会话隔离，不负责生产密钥托管/TLS 基线（Story 39.9）、供应链扫描（39.5）、性能容量（39.6）或最终多实例拓扑（39.10）。
- 为避免 URL 泄露而调整 WebSocket 认证传输属于本 Story；JWT/HMAC 密钥保管仍属于 39.9。
- 不新增产品功能、页面或业务频道。对 `control/linkage` 等不一致频道只做安全分类、移除死配置或接入既有业务路径。
- 不以“当前前端不会调用”作为后端越权路径的关闭理由。

### Project Structure Notes

**预期新增：**

- `backend/authz_inventory.yaml`
- `backend/app/core/authorization.py`（若现有 `deps.py` 无法保持清晰边界）
- `backend/tests/test_authorization_inventory.py`
- `backend/tests/test_story_39_1.py`
- `e2e/site-isolation-websocket-authorization.spec.ts`
- `_bmad-output/test-artifacts/epic-39/39.1/manifest.yaml` 及原始证据产物

**预期更新：**

- `backend/app/api/deps.py`
- `backend/app/main.py`
- `backend/app/services/websocket.py`
- `backend/app/api/v1/auth.py`
- `backend/app/api/v1/user.py`
- `backend/app/api/v1/__init__.py`
- 清单识别出的所有站点资源路由和全部 WS 广播生产者
- `frontend/src/api/websocket.ts`
- `frontend/src/composables/useWebSocketManager.ts`
- 对应后端、前端和 E2E 测试

不要为每个路由复制一套授权逻辑；复用统一上下文、scope helper 和资源解析器。实际 File List 以完成后的 Git diff 与授权清单为准，不得只列已知高风险文件。

### Previous Work And Git Intelligence

- Story 13.2 已建立 JTI 会话和并发会话限制；扩展它，不要另建平行会话表。
- Story 13.5 已建立 `UserSite`、Device.site_id、`get_user_site_ids()` 和 `require_site_access()`；统一并补全这些模式。
- Story 27.6 已建立前端 `siteEvents`、站点切换重连和订阅恢复；保持该交互契约。
- 网关列表已有“显式越权 site_id 先校验再过滤并返回 403”的可复用模式。
- `broadcast_to_role()` 当前注释明确为客户端过滤临时实现；本 Story 必须移除该安全依赖。
- 最近提交已完成 Epic 37/38 软件 RC 收口，但不构成生产授权通过证据。

### References

- [Source: `_bmad-output/planning-artifacts/epics.md` - Epic 39 / Story 39.1 / 统一证据契约]
- [Source: `_bmad-output/planning-artifacts/prd.md` - NFR-PR01 与不可豁免控制]
- [Source: `_bmad-output/planning-artifacts/architecture.md` - Sections 26.1, 26.8, 26.9]
- [Source: `_bmad-output/test-artifacts/nfr-assessment.md` - Security Assessment / C1]
- [Source: `backend/app/api/deps.py` - 当前 HTTP 身份、角色和站点依赖]
- [Source: `backend/app/main.py` - 当前 WebSocket token 验证与入口]
- [Source: `backend/app/services/websocket.py` - 当前连接和广播模型]
- [Source: `backend/app/api/v1/device.py`, `point.py`, `topology.py` - 已确认对象授权缺口]
- [Source: `backend/app/services/ingest_pipeline.py` - 可信点位/站点元数据与广播生产者]
- [Source: `frontend/src/api/websocket.ts`, `frontend/src/composables/useWebSocketManager.ts` - 现有认证、心跳、重连和订阅恢复]
- [Source: `backend/tests/test_auth_session.py`, `test_site_isolation.py`, `test_site_management.py` - 现有会话和站点测试基线]
- [Source: `e2e/authorization-matrix.spec.ts` - 现有角色矩阵及跨站点覆盖缺口]

## Definition Of Done

- [ ] AC1-AC5 全部有自动化测试和原始机器可读证据，且无跳过、重试通过或人工客户端过滤替代项
- [ ] 运行时全部 HTTP/WS 路由、频道和广播生产者均已分类，授权清单门禁通过
- [ ] 已确认的跨站点 IDOR、未鉴权 topology 路由和 WebSocket 全员广播路径全部关闭
- [ ] 后端聚焦回归、前端 Vitest/typecheck 和 Playwright 授权矩阵零失败
- [ ] `manifest.yaml` 引用文件存在、哈希有效、AC 映射完整，Charlie 与 Dana 已独立审批
- [ ] 实际 File List 与 Git diff 一致，未把 Story 39.5/39.6/39.9/39.10 的工作静默并入

## Story Completion Status

- **状态:** ready-for-dev
- **创建日期:** 2026-08-10
- **说明:** 已完成代码面、测试面、Git 历史和 NFR 对抗性分析；开发所需授权边界、默认拒绝规则、回归约束和证据契约已明确。

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- Task 1 red: `pytest -q tests/test_authorization_inventory.py` failed with missing `app.core.authorization`.
- Task 1 green: 9 inventory gate tests passed; runtime validation reported HTTP=856, WebSocket=3, channels=5, producers=29; Ruff passed.
- Task 2 red: Story tests failed to import the missing site context and resolver API.
- Task 2 green: 61 Story/auth/session/site tests passed; Ruff passed.
- Task 3 red: Cross-domain HTTP regression exposed orphan Point/Device/Diagnosis fixtures, non-atomic legacy batch expectations, Redis-dependent skips, and a leaked dynamic-threshold test database worker.
- Task 3 green: Runtime inventory policies match every reviewed YAML HTTP row; broad Ruff passed; the 34-file HTTP authorization regression passed 742 tests in 709.70 seconds.
- Task 4 red: 15 WebSocket tests exposed payload-derived site trust, missing producer scope arguments, stale-snapshot sends after revocation, and the HTTP policy dependency blocking WebSocket handshakes.
- Task 4 green: 33 focused WebSocket tests and an 86-test producer regression passed; all 29 producers now declare explicit SITE/GLOBAL/USER runtime scope and Ruff passed.
- Task 5 red: Real transaction tests required an injectable revalidation session factory and exposed login-rate-limiter state leaking across authentication tests.
- Task 5 green: 81 authentication/session/revocation tests passed, including logout, concurrent eviction, role/site changes, disable/delete, pre-send revalidation, and notification-failure commit preservation.
- Task 6 red: Vitest exposed automatic reconnect dropping the authenticated subscription and site switching replaying the original unscoped filters.
- Task 6 green: 38 focused WebSocket/Story 27.6 tests, 1,706 full frontend tests, TypeScript typecheck, and focused ESLint passed.
- Task 7 red: Running both browser matrices exposed shared-IP login-rate-limit contention; retries stayed disabled and the run failed with HTTP 429 instead of masking the issue.
- Task 7 green: Reused the original session plus `/auth/refresh`, then passed 197 backend matrix/regression tests and 12 zero-retry Playwright executions.
- Task 8 red: Evidence generation exposed oversized Docker contexts, unreachable default package CDNs, backend settings loading from the wrong working directory, and Windows `.cmd` tool-version discovery failures.
- Task 8 green: Built both local evidence images, generated the complete raw artifact set, and passed Schema, path, size, hash, inventory-drift, and test-result validation for 12 manifest artifacts while keeping approvals pending and the production gate blocked.
- PR CI red: The remote backend job rejected 22 Story application files at the pinned Ruff 0.15.2 format gate; a clean CI environment also resolved unbounded httpx to 0.28.1, which is incompatible with Starlette 0.35.1 `TestClient`.
- PR CI green: Formatted the 22 Story application files with Ruff 0.15.2, constrained httpx to `<0.28.0`, and passed Ruff check/format, Python compile, and all 197 authorization regression tests in the CI-compatible environment.
- Broad backend regression red: Strict active-session authorization exposed 24 legacy test files that used unauthenticated clients, synthetic IDs, or pre-Story role expectations; the linkage API test also opened the application database during policy reload and left a non-daemon `aiosqlite` worker alive after pytest reported success.
- Broad backend regression green: Updated all 24 tests to use real users, active JTI sessions, trusted site ownership, and current role policies; isolated the linkage policy reload in its test fixture. Split regressions passed 503 API tests, 136 root tests with 4 skips, 26 maintenance-advisor tests, 296 remaining service tests, and 99 tail tests. Ruff, application format, compile, and changed-file diff checks passed. The monolithic Windows coverage command exceeded the 30-minute outer runner limit without triggering `--maxfail=1`, so no full-suite summary was claimed.

### Implementation Plan

- Task 6: Keep the active subscription inside each client for transport reconnects; keep site-neutral business filters in the singleton manager and derive `site_ids` from each site-change event before reconnecting.

### Completion Notes List

- Task 1: Added a checked-in YAML policy inventory, deterministic runtime/code discovery, mutation-tested drift validation, and fail-closed lifespan validation before background services start.
- Task 2: Enforced active JTI ownership for every protected dependency and added immutable request site context, SQL scoping, trusted ownership resolvers, and consistent 403/404 helpers.
- Task 3: Closed direct and indirect HTTP authorization gaps across all mounted resource families, enforced preflight ownership for batches/rebinding, aligned mixed global policies with the reviewed inventory, and converted legacy coverage to real trusted ownership chains.
- Task 4: Added first-frame active-session authentication, server-owned connection contexts, site/role/subscription filtering, batched pre-send revalidation, stale-snapshot suppression, and explicit trusted scope propagation across every inventoried producer.
- Task 5: Connected committed session and user-authorization changes to immediate JTI/user invalidation, added batched periodic and pre-send database revalidation, and emitted structured security logs without coupling notification failures to transaction rollback.
- Task 6: Moved authentication to the first WebSocket frame, delayed connected/subscription state until authentication succeeds, restored subscriptions after every reauthentication, and made selected-site filters narrowing-only with `null` omitting `site_ids`.
- Task 7: Completed fail-closed inventory mutations for HTTP/WS/channel/producer drift and added a live double-site matrix for list/detail/mutation/stream, guessed IDs, logout revocation, and role downgrade without fixed waits or retries.
- Task 8.1-8.3: Published the auditable evidence package with real local image IDs, sanitized environment/tool fingerprints, exact commands, raw pytest/Playwright/Vitest results, AC mappings, and validated SHA-256 references. Charlie/Dana approval remains pending, so Task 8.4 and the production gate remain blocked.
- PR CI follow-up: Aligned Story application formatting with the repository-pinned Ruff version and bounded httpx to the Starlette-compatible test client range without changing authorization behavior.
- Broad regression follow-up: Repaired 24 legacy backend tests to exercise the strict active-session and site-ownership contract without weakening production authorization. Removed the linkage test's application-database side effect so split pytest runs exit cleanly; all regression partitions and quality gates passed, while the production gate remains blocked pending independent Charlie/Dana approval.

### File List

- `backend/.dockerignore`
- `backend/Dockerfile`
- `backend/requirements.txt`
- `backend/authz_inventory.yaml`
- `backend/app/core/authorization.py`
- `backend/app/main.py`
- `backend/app/api/deps.py`
- `backend/tests/test_authorization_inventory.py`
- `backend/tests/test_story_39_1.py`
- `backend/app/api/v1/alarm.py`
- `backend/app/api/v1/asset.py`
- `backend/app/api/v1/auth.py`
- `backend/app/api/v1/command.py`
- `backend/app/api/v1/cooling.py`
- `backend/app/api/v1/data_quality.py`
- `backend/app/api/v1/datasources.py`
- `backend/app/api/v1/device.py`
- `backend/app/api/v1/diagnosis.py`
- `backend/app/api/v1/drift.py`
- `backend/app/api/v1/floor_map.py`
- `backend/app/api/v1/gateways.py`
- `backend/app/api/v1/history.py`
- `backend/app/api/v1/operation.py`
- `backend/app/api/v1/ota.py`
- `backend/app/api/v1/point.py`
- `backend/app/api/v1/power.py`
- `backend/app/api/v1/power_redundancy.py`
- `backend/app/api/v1/probability_tuning.py`
- `backend/app/api/v1/precool.py`
- `backend/app/api/v1/predictive_maintenance.py`
- `backend/app/api/v1/realtime.py`
- `backend/app/api/v1/report.py`
- `backend/app/api/v1/sensor_metadata.py`
- `backend/app/api/v1/spatial.py`
- `backend/app/api/v1/statistics.py`
- `backend/app/api/v1/threshold.py`
- `backend/app/api/v1/topology_config.py`
- `backend/app/api/v1/user.py`
- `backend/app/api/v1/video.py`
- `backend/app/services/diagnosis/annotation_service.py`
- `backend/app/services/diagnosis/push_service.py`
- `backend/app/services/diagnosis/scheduler.py`
- `backend/app/services/communication_monitor.py`
- `backend/app/services/drift_detection.py`
- `backend/app/services/gateway_monitor.py`
- `backend/app/services/ingest_pipeline.py`
- `backend/app/services/precool/rollback_manager.py`
- `backend/app/services/video_service.py`
- `backend/app/services/websocket.py`
- `backend/app/engines/action_handlers.py`
- `backend/app/engines/diagnosis_engine.py`
- `backend/app/engines/escalation_engine.py`
- `backend/app/engines/linkage_engine.py`
- `backend/app/engines/recovery_engine.py`
- `backend/tests/api/test_alarm_coverage.py`
- `backend/tests/api/test_core_modules_coverage.py`
- `backend/tests/api/test_data_quality.py`
- `backend/tests/api/test_diagnosis_annotation.py`
- `backend/tests/api/test_diagnosis_battery_soh.py`
- `backend/tests/api/test_diagnosis_counterfactual.py`
- `backend/tests/api/test_energy_history_demand_power_cooling_coverage.py`
- `backend/tests/api/test_gateway_video_ota_coverage.py`
- `backend/tests/api/test_precool.py`
- `backend/tests/api/test_precool_config_api.py`
- `backend/tests/api/test_precool_management.py`
- `backend/tests/api/test_precool_rollback.py`
- `backend/tests/api/test_precool_schedule_api.py`
- `backend/tests/api/test_sensor_metadata.py`
- `backend/tests/api/test_audit_fix_coverage.py`
- `backend/tests/api/test_device_coverage.py`
- `backend/tests/api/test_operation_coverage.py`
- `backend/tests/api/test_shift_opportunities_coverage.py`
- `backend/tests/api/test_small_modules_coverage.py`
- `backend/tests/api/test_spatial_topology_linkage_coverage.py`
- `backend/tests/api/test_time_window_tuning.py`
- `backend/tests/api/test_vpp_dispatch.py`
- `backend/tests/services/test_counterfactual_boundary.py`
- `backend/tests/demo/test_integration_flow.py`
- `backend/tests/test_alarm_api.py`
- `backend/tests/test_alarm_workorder_rule.py`
- `backend/tests/test_auth_session.py`
- `backend/tests/test_audit_log.py`
- `backend/tests/test_asset_import.py`
- `backend/tests/test_asset_lifecycle_warranty.py`
- `backend/tests/test_backup_health.py`
- `backend/tests/test_capacity_trend.py`
- `backend/tests/test_command.py`
- `backend/tests/test_data_quality.py`
- `backend/tests/test_device_detail.py`
- `backend/tests/test_diagnosis.py`
- `backend/tests/test_drift.py`
- `backend/tests/test_effect_tracker.py`
- `backend/tests/test_escalation.py`
- `backend/tests/test_fire_protection.py`
- `backend/tests/test_graceful_degradation.py`
- `backend/tests/test_inspection.py`
- `backend/tests/test_knowledge.py`
- `backend/tests/test_linkage.py`
- `backend/tests/test_opportunity_detector.py`
- `backend/tests/test_racking_recommendation.py`
- `backend/tests/test_recovery.py`
- `backend/tests/test_report_auto.py`
- `backend/tests/test_site_isolation.py`
- `backend/tests/test_smart_site_selection.py`
- `backend/tests/test_spatial.py`
- `backend/tests/test_timeline.py`
- `backend/tests/test_topology_config.py`
- `backend/tests/test_user_management.py`
- `backend/tests/test_video.py`
- `backend/tests/test_story_24_6.py`
- `backend/tests/test_story_24_7.py`
- `backend/tests/test_work_order.py`
- `backend/tests/test_work_order_approval.py`
- `backend/tests/test_websocket_authorization.py`
- `frontend/src/api/websocket.ts`
- `frontend/src/composables/useWebSocket.ts`
- `frontend/src/composables/useWebSocketManager.ts`
- `frontend/src/__tests__/api/websocket-auth.test.ts`
- `e2e/site-isolation-websocket-authorization.spec.ts`
- `playwright.config.ts`
- `scripts/story_39_1_evidence.py`
- `scripts/story_39_1_manifest.schema.json`
- `_bmad-output/test-artifacts/epic-39/39.1/authorization-inventory.yaml`
- `_bmad-output/test-artifacts/epic-39/39.1/authorization-inventory-diff.json`
- `_bmad-output/test-artifacts/epic-39/39.1/openapi-authz-snapshot.json`
- `_bmad-output/test-artifacts/epic-39/39.1/websocket-producer-inventory.json`
- `_bmad-output/test-artifacts/epic-39/39.1/http-authz-matrix-results.json`
- `_bmad-output/test-artifacts/epic-39/39.1/websocket-authz-matrix-results.json`
- `_bmad-output/test-artifacts/epic-39/39.1/pytest-authz.xml`
- `_bmad-output/test-artifacts/epic-39/39.1/playwright-authz-results.json`
- `_bmad-output/test-artifacts/epic-39/39.1/vitest-websocket-results.json`
- `_bmad-output/test-artifacts/epic-39/39.1/source-file-hashes.json`
- `_bmad-output/test-artifacts/epic-39/39.1/environment-fingerprint.json`
- `_bmad-output/test-artifacts/epic-39/39.1/manifest.schema.json`
- `_bmad-output/test-artifacts/epic-39/39.1/manifest.yaml`
- `_bmad-output/test-artifacts/epic-39/39.1/evidence-validation.json`

## Change Log

- 2026-08-11: Completed automatable evidence publication and validation for Task 8.1-8.3; Task 8.4 remains pending Charlie/Dana approval and the production gate remains `BLOCKED`.
- 2026-08-11: Resolved PR CI format and Starlette/httpx compatibility gates; 197 authorization regression tests pass in the pinned CI toolchain.
- 2026-08-11: Aligned 24 legacy backend tests with strict active-session/site authorization, removed a linkage-test database connection leak, and passed all split backend regression and quality gates; Task 8.4 remains pending and `BLOCKED`.
