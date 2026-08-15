---
baseline_commit: 436a8e778037bf6fcf9140b757e9584e669ad33b
story_key: 39-3-postgresql-disaster-recovery-and-failover
decision_register:
  D39-01:
    status: recorded
    owner: proecheng
    recorded_at: '2026-08-14'
---

# Story 39.3: PostgreSQL 灾难恢复与站点故障切换

Status: in-progress

## Story

As a 运维负责人,
I want PostgreSQL 备份、恢复、回滚和故障切换满足已批准目标,
so that 生产数据故障可以在可测量的时间和数据损失边界内恢复。

## Ownership And Traceability

- **实施与证据责任:** `proecheng`（唯一维护者）
- **证据治理:** `single-maintainer`；不要求 Charlie、Dana 或其他 BMAD 虚拟角色审批
- **优先级:** P0 / CRITICAL
- **NFR/行动追溯:** NFR-PR05、C3
- **不可豁免:** 生产 PostgreSQL 无法在 D39-01 目标内恢复
- **决策前置:** D39-01 已于 2026-08-14 记录在本 Story 和 Architecture 26.4
- **完成依赖:** Story 39.7 提供统一备份年龄、归档/复制延迟、告警和受信时间线；在其完成前，本 Story 不得签署 `PASS`
- **下游依赖:** Story 39.4 只有在 39.3、39.6、39.9、39.12 完成后才能执行现场 UAT

`ready-for-dev` 表示备份、连续 WAL、隔离恢复、回滚、温备和证据工具可以开始实施，不表示 39.7 已完成，也不改变 Epic 39 production gate 的 `BLOCKED` 状态。

## Context

当前生产 Compose 只有一个 `timescale/timescaledb:latest-pg16` 服务和本机命名卷。镜像可漂移，没有备份服务、独立仓库、连续 WAL、温备、fencing 或真实 PostgreSQL 恢复演练。应用现有 `/api/v1/system/backup/*` 只复制 SQLite `dcim.db`，配置中的“自动备份”没有调度执行；恢复接口还直接拼接 `backup_name`，存在目录越界风险。

数据库层已包含 PostgreSQL/TimescaleDB 和 Alembic 基础，但生产应用启动执行 `Base.metadata.create_all()`，Compose 没有显式迁移 runner；`TIMESCALEDB_ENABLED` 不能证明扩展、hypertable 或策略真实存在。Story 26.7 只模拟诊断熔断和 Redis 暂存，明确不注入真实数据库故障，不能充当本 Story 的生产恢复证据。

本 Story 必须使用精确 PostgreSQL 16、TimescaleDB 和备份工具版本，在隔离故障域执行真实备份、PITR、迁移/应用回滚和受控故障切换。SQLite 单测、同卷文件复制、容器重启、截图或自报摘要均不能替代正式证据。

## D39-01 Recovery Decision

### Numeric Objectives

| 场景 | RPO | RTO | 完成条件 |
|------|-----|-----|----------|
| 误删、损坏或错误迁移后的 PITR | `<= 5 分钟` | `<= 4 小时` | 完整 cluster 恢复到指定 time/LSN/restore point，数据和 TimescaleDB 对象一致 |
| 计划内主备切换 | `0` | `<= 15 分钟` | replay LSN 追平、旧主隔离、备库提升、应用关键读写恢复 |
| 主库/主机意外故障的温备切换 | `<= 60 秒` | `<= 30 分钟` | 旧主 fenced，备库提升，应用连接恢复，无双写/双主 |
| 整站丢失后的异地恢复 | `<= 5 分钟` | `<= 4 小时` | 独立故障域恢复，readiness、关键读写和一致性检查通过 |
| 受控迁移或应用回滚 | `0` | `<= 60 分钟` | 维护窗口停止写入；可逆迁移或迁移前 restore point + 已验证镜像恢复 |

RTO 从受信 UTC 故障注入/恢复决定时间开始，到应用连续通过 readiness 和关键读写为止。RPO 同时以“恢复后缺失的已确认提交数量”和“最新缺失提交的时间差”计算，不能只比较文件时间。

### Retention, Restore And Failover Scope

- 每周 full、每日 differential/incremental、连续 WAL 归档；至少 35 天 PITR 窗口和 5 个可恢复 full backup set。
- 至少一个加密仓库位于 PostgreSQL 主机与 `postgres-data` 卷之外，仓库失败不能同时摧毁主数据和全部备份。
- 恢复完整 PostgreSQL cluster，包括全局对象、`dcim` schema、业务/审计数据、`alembic_version`、TimescaleDB 扩展、hypertable、chunk、job、压缩/保留策略和序列状态。
- Redis、MQTT、网关缓存和外部附件不属于数据库恢复范围；其恢复由对应 Story/运行手册负责。
- 采用 PostgreSQL 物理流复制温备和受控手工 promotion；旧主必须先 fence，回归时使用 `pg_rewind` 或全量重建。禁止直接把旧主重新作为 primary。
- 不承诺自动故障检测、自动 failover、多主、自动 failback 或完整应用多实例 HA；D39-05/Story 39.10 仍决定正式应用拓扑。
- 每月隔离恢复、每季度主备/站点切换；数据库、TimescaleDB 或备份工具版本变化后追加演练。

## Acceptance Criteria

### AC1: 版本、范围和恢复目标可重现

**Given** 唯一维护者准备实施生产恢复能力
**When** 构建主库、温备、备份仓库和隔离恢复环境
**Then** PostgreSQL 16、TimescaleDB 和 pgBackRest 使用明确版本及镜像摘要，不允许 `latest` 参与正式证据
**And** 主库、备库与恢复环境记录 `SHOW server_version`、TimescaleDB 扩展版本、镜像摘要、配置和脱敏拓扑指纹
**And** D39-01 的每个场景、RTO/RPO、保留、恢复范围和故障切换范围均映射到测试与证据
**And** 测试报告记录数据库大小、WAL 量、存储/网络资源和持续写入速率，不得把小数据集结果外推到未实测容量

### AC2: 自动加密备份、连续 WAL 和保留策略失败关闭

**Given** PostgreSQL 主库正常接收业务写入
**When** 周期备份和 WAL 归档运行
**Then** 使用 pgBackRest 或等价成熟工具执行每周 full、每日 differential/incremental 和连续 WAL 归档，不在 FastAPI 多 worker 中复制调度循环
**And** 备份仓库在独立故障域，制品加密、校验通过、原子发布，密钥只通过 secret 注入且不进入镜像、日志、API 或证据
**And** 至少保持 35 天可验证 PITR 窗口和 5 个完整可恢复 backup set，清理不得删除最新成功恢复链
**And** 并发备份、错误密钥、仓库不可写、归档失败、WAL 缺口、截断/篡改制品和清理失败均失败关闭并留下原始状态
**And** 备份失败、完整性失败、备份年龄、归档延迟、复制延迟和 replication slot/WAL 磁盘风险产出机器可读指标；正式告警闭环由 39.7 消费和验收

### AC3: 隔离恢复、PITR 和一致性验证完整

**Given** 已存在通过校验的备份链和带 UTC 时间/LSN/递增序号的持续写入探针
**When** 在独立 Compose project、network、volume 或真实异地环境执行最新恢复和指定 time/LSN/restore point 的 PITR
**Then** 恢复过程不挂载、覆盖或修改源主库数据卷和备份仓库
**And** WAL 缺口、错误密钥、空链、损坏 manifest、非空目标目录和版本不兼容均被拒绝，不产生可误认为成功的数据库
**And** 恢复后运行 pgBackRest 校验、`pg_amcheck`、Alembic head、全局对象、表/行清单、关键表确定性摘要、约束/序列和应用关键读写检查
**And** 查询实际 TimescaleDB 扩展、hypertable、chunk、job、压缩和保留策略，不以 `TIMESCALEDB_ENABLED` 或迁移日志替代实物检查
**And** RTO/RPO 按 D39-01 公式从原始时间线重算并满足对应场景目标

### AC4: 迁移和应用回滚保持数据库一致

**Given** 精确发布镜像和当前 Alembic head 已在隔离 PostgreSQL/TimescaleDB 环境部署
**When** 执行成功迁移、可逆迁移故障和不可逆迁移故障场景
**Then** 迁移前创建命名 restore point 并停止业务写入，记录旧/新 revision、schema 和数据不变量
**And** 只对已验证可逆的当前发布 revision 执行 `downgrade -> upgrade`，不得宣称所有历史迁移可逆
**And** 对 `a001_full_schema`、hypertable 等不可逆边界使用迁移前 PITR/物理恢复和上一已验证应用镜像，而不是依赖空 `downgrade()` 或吞掉错误
**And** 回滚后 Alembic revision、TimescaleDB 对象、关键数据摘要、readiness 和应用关键读写一致，满足 D39-01 回滚目标
**And** Story 39.12 负责自动部署回滚机制；本 Story 只定义并验证它必须保持的数据库恢复契约

### AC5: 数据库和站点故障切换可测量且避免双主

**Given** 主库、独立故障域温备、连续写入探针和稳定数据库端点已就绪
**When** 执行计划切换、主库进程故障、主机/网络隔离和整站恢复场景
**Then** 计划切换先等待 replay LSN 追平，任何 promotion 前都确认旧主已经停止或被网络/存储 fence
**And** 提升后切换稳定数据库端点，重建应用连接并验证 readiness、关键读写、序列单调性和无重复/丢失提交
**And** 旧主只通过 `pg_rewind` 成功或全量重建后作为 standby 回归；`pg_rewind` 失败的目标目录不得继续使用
**And** 每个场景保留检测、fencing、promotion、端点切换、应用恢复和旧主重建的 UTC/monotonic 原始时间线
**And** 同一主机上的双容器演练只能标记为机制测试；站点故障切换 `PASS` 必须来自独立故障域

### AC6: 现有备份 API 安全且不虚构 PostgreSQL 能力

**Given** 管理员或查看者访问系统健康与备份 API
**When** 系统运行在 SQLite 开发模式或 PostgreSQL 生产模式
**Then** 保留 `/api/v1/system/health` 和现有 `/backup/config|manual|list|restore` 的权限与开发兼容行为
**And** SQLite 备份使用一致性安全的 SQLite backup API 或停写快照，不再在线复制裸 `.db` 文件
**And** `backup_name` 只接受受信目录中已枚举的制品 ID；规范化路径、符号链接、绝对路径、`..`、错误后缀和竞态替换均被拒绝
**And** 响应不泄露绝对路径、密钥、连接串或仓库凭据
**And** PostgreSQL 生产模式不调用 SQLite 文件复制，也不从 Web 请求直接执行高权限 shell/restore；API 只返回受控状态或触发独立、最小权限的运维作业
**And** 配置导入导出 `/api/v1/config/backup|restore` 保持独立，不得被误称为数据库灾备

### AC7: 证据包可独立重算且门禁保持分离

**Given** AC1-AC6 已实施且 Story 39.7 的正式观测契约可用
**When** 执行备份、损坏/PITR、迁移/应用回滚、主备/站点故障切换和证据验证矩阵
**Then** `_bmad-output/test-artifacts/epic-39/39.3/manifest.yaml` 绑定 Git SHA、changeset、应用/数据库/备份镜像摘要、环境指纹、工具版本、精确命令、UTC 窗口和唯一维护者结论
**And** 原始产物至少包含 D39-01、备份/归档、完整性、隔离恢复、PITR、一致性、回滚、fencing/failover、告警矩阵、质量命令和源码哈希
**And** 受信任 Schema 和独立新进程从原始时间线、探针和数据库查询重算 RTO、RPO、保留窗口、摘要和 AC 映射，拒绝陈旧、空、跳过、重试、自报或越出本次 changeset 的产物
**And** `single-maintainer` Story gate 与 Epic production gate 分离；39.7 未完成、独立故障域未实测或任一目标失败时 Story gate 不能为 `PASS`
**And** Story 通过也不自动解除 Epic 39 的 `BLOCKED`

## Tasks / Subtasks

### Review Findings

- [x] [Review][Patch] 默认 Compose 的 DR 初始化脚本缺少启用门禁，新数据卷会因未提供复制与仓库 secret 而初始化失败 [`docker-compose.yml:6`; `deploy/postgres-backup/Dockerfile:144`; `deploy/postgres-backup/init-primary.sh:4`]
- [x] [Review][Patch] DR Compose 仅要求镜像变量非空，未验证不可变 `@sha256` 引用，正式节点仍可使用漂移标签 [`deploy/dr/docker-compose.dr.yml:3`]
- [x] [Review][Patch] 空仓库首次启动时 retention ready 返回错误并终止调度器，导致首个备份永远不会执行 [`deploy/postgres-backup/retention-guard.sh:105`; `deploy/postgres-backup/backup-scheduler.sh:100`]
- [x] [Review][Patch] 目录锁在容器被强杀后会永久残留，后续所有备份均返回并发冲突，缺少可自动回收的进程锁 [`deploy/postgres-backup/backup-job.sh:92`]
- [x] [Review][Patch] 调度器重启时 stanza 成功会覆盖之前的失败 `last-run.json`，健康检查恢复绿色并隐藏最近一次备份失败 [`deploy/postgres-backup/backup-scheduler.sh:98`; `deploy/postgres-backup/backup-healthcheck.sh:27`]

- [x] Task 1: 固化版本、恢复拓扑和安全配置 (AC: #1, #2, #5)
  - [x] 1.1 将 TimescaleDB/PG16 和 pgBackRest 固定到已验证版本与镜像摘要，记录升级/漂移规则
  - [x] 1.2 在独立 DR Compose/profile 中定义主库、温备、加密仓库和隔离恢复目标，不破坏默认一键开发启动
  - [x] 1.3 配置 `wal_level=replica`、归档 push/get、有限 replication slot、复制/归档状态和旧主 fencing
  - [x] 1.4 通过 secret file/运行时 secret 注入仓库密码和复制凭据，拒绝缺失、占位或日志泄露

- [x] Task 2: 实现备份、保留和状态生产端 (AC: #2)
  - [x] 2.1 使用独立单实例备份 sidecar/job 执行 weekly full、daily differential/incremental 和 continuous WAL
  - [x] 2.2 实现 stanza/check、制品校验、原子成功标记、并发互斥和失败退出码
  - [x] 2.3 实现 35 天/5 full set 保留，验证 WAL 依赖链并保护最新成功恢复链
  - [x] 2.4 输出备份年龄、归档/复制延迟、slot/WAL 占用和失败原因的机器可读状态，供 Story 39.7 接入

- [x] Task 3: 建立隔离恢复和一致性检查器 (AC: #3)
  - [x] 3.1 实现最新恢复与 time/LSN/restore point PITR，不允许恢复目标复用源卷
  - [x] 3.2 加入错误密钥、损坏/截断、WAL 缺口、非空目录和版本漂移负向测试
  - [x] 3.3 校验 pgBackRest、`pg_amcheck`、Alembic、全局对象、表/行/摘要、约束/序列和关键读写
  - [x] 3.4 查询并校验 TimescaleDB 扩展、hypertable、chunk、job、压缩和保留策略

- [x] Task 4: 验证迁移和应用回滚契约 (AC: #4)
  - [x] 4.1 盘点当前 release migration，区分可逆 revision 与必须 PITR 的不可逆边界
  - [x] 4.2 在写入冻结和命名 restore point 下执行 upgrade/downgrade/restore 故障矩阵
  - [x] 4.3 验证上一应用镜像对恢复 schema 的兼容性，并为 39.12 输出明确的成功/停止条件
  - [x] 4.4 让迁移吞错、非 head、Timescale 对象缺失或不变量变化直接失败

- [ ] Task 5: 执行受控 failover/failback 演练 (AC: #5)
  - [x] 5.1 建立持续写入探针和受信时间线，覆盖计划切换、意外主库故障和整站恢复
  - [x] 5.2 验证 fencing、promotion、稳定端点切换、应用连接恢复和关键读写
  - [x] 5.3 使用 `pg_rewind` 或全量重建恢复旧主，拒绝未经处理的旧主重新上线
  - [ ] 5.4 分开记录同机机制测试与独立故障域正式证据，按场景重算 RTO/RPO

- [ ] Task 6: 修复现有备份 API 的安全与真实性 (AC: #6)
  - [ ] 6.1 保留路由/RBAC 和开发兼容，使用可靠 SQLite snapshot 替代在线裸文件复制
  - [ ] 6.2 对制品 ID、规范化路径、后缀、符号链接和竞态实施统一目录边界校验
  - [ ] 6.3 移除绝对路径/秘密泄露，生产 PostgreSQL 分支只暴露受控状态或独立作业句柄
  - [ ] 6.4 增加目录穿越、符号链接、竞态、错误数据库类型和权限负向测试

- [ ] Task 7: 生成并独立验证证据包 (AC: #1-#7)
  - [ ] 7.1 为备份、PITR、回滚、failover、告警和质量命令保存原始机器可读结果
  - [ ] 7.2 建立 39.3 专用可信 Schema、必测清单、changeset/镜像/环境绑定和双向 AC 映射
  - [ ] 7.3 等待/消费 39.7 的统一告警与时间线契约，再运行正式门禁，不用本地临时指标冒充
  - [ ] 7.4 由独立新进程重算全部指标并记录 `single-maintainer` 结论；Epic gate 保持独立

## Dev Notes

### Architecture And Tool Decisions

1. **优先成熟物理备份工具。** 使用 pgBackRest 处理 PostgreSQL 物理备份、WAL 和 PITR；不要手写数据库归档格式、加密算法或用 `shutil.copy2()` 复制运行中的数据库。
2. **备份调度独立于 FastAPI worker。** 当前后端容器以多 worker 运行，把任务放入 lifespan 会重复调度。使用单实例 sidecar/job，并通过 pgBackRest 锁或等价互斥保证一次只运行一个任务。
3. **fencing 是 promotion 前置。** PostgreSQL 不负责可靠判断旧主是否死亡；任何自动或手工 promotion 都必须先证明旧主不能继续接受写入。
4. **PITR 是 cluster 级恢复。** 不承诺单表恢复；误删恢复到隔离 cluster 后再按批准 runbook 提取数据，不能直接覆盖生产主库。
5. **TimescaleDB 以实物为准。** 恢复验证查询 `pg_extension` 和 `timescaledb_information`；环境变量、迁移输出或 `SELECT 1` 都不足以证明完整恢复。
6. **容量结论不得外推。** 每次证据绑定数据规模、WAL、存储和网络。超过实测包络的 RTO/RPO 保持未验证，由 39.6/39.10 扩展容量结论。

### Current Files To Read Before Editing

- `docker-compose.yml`: 单 PostgreSQL、单本地卷、`latest-pg16`；必须保留默认生产服务依赖和 Story 39.2 的强凭据注入。
- `.env.example`、`backend/.env.example`: 增加备份/复制/仓库示例字段时只放占位符，不提供可启动的弱默认值。
- `backend/app/api/v1/system_health.py`: 保留健康和备份路由/RBAC；当前仅支持 SQLite 文件复制、泄露绝对路径并存在恢复目录越界。
- `backend/app/core/config.py`: 保留 Story 39.2 production fail-fast；若增加 DR 配置，只在相关 profile 启用时要求，并保持错误脱敏。
- `backend/app/core/database.py`、`backend/app/main.py`: 当前 PostgreSQL 仍走 `create_all()`；不得用它替代 Alembic 或 TimescaleDB 恢复验证。
- `backend/alembic/env.py`、`backend/alembic/versions/a001_full_schema.py`、`a002_timescaledb_hypertable.py`: 盘点可逆性和真实对象，不要假设所有 downgrade 有效。
- `backend/tests/test_backup_health.py`: 保留现有健康、配置、列表和 404 契约，并加入安全/数据库类型分支。
- `backend/app/api/v1/config.py`: 这是配置 JSON 导入导出，不是数据库恢复；不得合并或删除。

### Likely File Structure

建议沿用现有职责边界，最终名称可按实施时最小改动调整：

- `deploy/postgres-backup/`: pgBackRest 配置模板、备份入口、状态输出和 restore 工具。
- `deploy/dr/docker-compose.dr.yml`: 隔离温备、仓库、恢复目标和故障注入环境。
- `backend/app/services/postgres_backup_service.py`: 只负责受控状态/作业适配，不直接持有高权限 shell 字符串。
- `backend/tests/test_story_39_3_backup.py`、`backend/tests/test_story_39_3_evidence.py`: 安全边界、状态和证据单测。
- `scripts/story_39_3_drill.py`: 编排隔离演练并输出原始时间线；危险操作必须校验 Compose project、container、network 和 volume 标签。
- `scripts/story_39_3_evidence.py`、`scripts/story_39_3_governance.py`、`scripts/story_39_3_manifest.schema.json`: 39.3 专用证据生成与独立验证。
- `_bmad-output/test-artifacts/epic-39/39.3/`: 仅放正式机器可读证据，不提交秘密、数据库备份或 WAL。

### Testing Requirements

- 后端聚焦测试覆盖配置、RBAC、路径/符号链接/竞态、SQLite snapshot、PostgreSQL 状态分支和证据验证。
- PostgreSQL/TimescaleDB 集成测试必须使用精确镜像摘要，真实执行 backup/check/restore/PITR、迁移和 `pg_amcheck`；SQLite 不能替代。
- failover 测试使用事件/健康轮询和明确 timeout，不用任意固定 sleep、重试成功或人工修改结果。
- 负向矩阵至少包含错误密钥、损坏/截断制品、WAL 缺口、仓库不可写、过期/失败备份、并发任务、非空恢复目标、目录穿越/符号链接、Timescale 对象缺失、Alembic 非 head 和未 fence promotion。
- 回归至少运行现有 `test_backup_health.py`、生产配置、授权清单、系统 health/readiness、完整后端分片，以及 Compose 配置检查。
- 正式演练结束后只能删除带本 Story 隔离 project 标签的临时容器、网络和卷，不得清理默认开发/生产卷或其他用户工作区资源。

### Evidence Contract

证据目录至少包含：

- `decision-d39-01.yaml`
- `environment-fingerprint.json`
- `backup-archive-results.json`
- `backup-integrity-results.json`
- `restore-pitr-results.json`
- `database-consistency-results.json`
- `migration-rollback-results.json`
- `failover-drill-results.json`
- `alert-matrix-results.json`
- `quality-command-results.json`
- `source-file-hashes.json`
- `manifest.schema.json`
- `manifest.yaml`
- `evidence-validation.json`

Manifest 使用 `single-maintainer`、`maintainer: proecheng`、`independent_approval_required: false`，并分别记录 `story_gate` 与 `epic_production_gate`。证据验证器必须从受信任源码、原始时间线和数据库探针重算，不信任证据包自带的结果字段。数据库备份、WAL、秘密和未脱敏连接信息不得放入 Git 证据目录。

### Previous Story And Git Intelligence

- Story 39.2 建立了生产配置最早 fail-fast、`single-maintainer` v2、源码/changeset/执行窗口/镜像绑定和独立重算模式；39.3 复用原则但重写专用 Schema 和必测集合。
- 39.2 明确把备份恢复目录穿越交给 39.3；本 Story 必须在任何文件读取或恢复副作用前修复。
- Story 26.7 的高精度计时、超时、互斥、`finally` 恢复和报告模式可复用；其 Redis 模拟不构成 PostgreSQL 证据。
- 最近提交建立了 Story 39.1 的授权清单、活动 JTI 和证据可信绑定。新增/改变备份路由时同步 `backend/authz_inventory.yaml`；若保持 operation 不变则避免无谓清单变更。
- 当前 HEAD 为 `436a8e778037bf6fcf9140b757e9584e669ad33b`，工作区还有 Story 39.2 和其他用户变更。实施不得 reset、还原或误纳无关文件；正式证据必须绑定实际 changeset，不能只引用这个旧 HEAD。

### Latest Technical Information

- PostgreSQL 16 当前维护版本为 16.15，支持至 2028-11-09；最终证据以镜像内 `SHOW server_version` 为准。
- TimescaleDB 2.29.1 支持 PostgreSQL 16；将当前 `latest-pg16` 改为验证后的版本和 digest，主/备/恢复环境必须一致。
- pgBackRest 2.59.0 是当前稳定版，可提供物理备份、仓库加密、WAL 归档和 PITR。使用其原生校验与锁，不实现自定义备份格式。
- `pg_rewind` 需要 data checksums 或 `wal_log_hints=on`，且必须保持 `full_page_writes=on`；若 rewind 失败，目标数据目录需全量重建。
- PostgreSQL 自身不提供完整故障检测/通知；正式切换必须以外部监控和 fencing 防止 split-brain。

### Scope Boundaries

- **包含:** PostgreSQL 物理备份、连续 WAL、PITR、保留、完整性、隔离恢复、迁移/应用回滚数据库契约、温备切换、现有备份 API 安全、原始指标和证据。
- **排除:** 39.7 的完整 SLO/告警平台；39.9 的密钥托管/轮换和全局静态加密治理；39.10 的应用多实例状态/fan-out；39.11 的 `alarm_type`/Axios 债务；39.12 的自动部署/OTA 回滚编排；39.4 的真实网关/UAT。
- 不实施大型自动 HA 编排器，不声称同机双容器等于异地容灾，不因本 Story 测试通过自动批准生产。

### References

- [Source: `_bmad-output/planning-artifacts/epics.md` - Epic 39, Story 39.3, Story 39.7, dependency graph]
- [Source: `_bmad-output/planning-artifacts/architecture.md` - 26.4, 26.5, 26.6, 26.8, 26.9]
- [Source: `_bmad-output/planning-artifacts/prd.md` - FR80, FR81, NFR-PR05, production gate matrix]
- [Source: `_bmad-output/planning-artifacts/sprint-change-proposal-2026-08-12.md` - single-maintainer governance]
- [Source: `backend/app/api/v1/system_health.py`]
- [Source: `backend/app/core/database.py`]
- [Source: `backend/alembic/versions/a002_timescaledb_hypertable.py`]
- [Source: `docker-compose.yml`]
- [PostgreSQL 16: Continuous Archiving and PITR](https://www.postgresql.org/docs/16/continuous-archiving.html)
- [PostgreSQL 16: Warm Standby and Failover](https://www.postgresql.org/docs/16/warm-standby.html)
- [PostgreSQL 16: Failover and STONITH](https://www.postgresql.org/docs/16/warm-standby-failover.html)
- [PostgreSQL 16: pg_rewind](https://www.postgresql.org/docs/16/app-pgrewind.html)
- [PostgreSQL 16: pg_amcheck](https://www.postgresql.org/docs/16/app-pgamcheck.html)
- [pgBackRest User Guide](https://pgbackrest.org/user-guide.html)
- [TimescaleDB physical backup](https://docs.tigerdata.com/self-hosted/latest/backup-and-restore/physical/)
- [TimescaleDB PostgreSQL compatibility](https://docs.tigerdata.com/self-hosted/latest/upgrades/upgrade-pg/)

## Definition Of Done

- [ ] D39-01 的每个目标都有正式故障场景、原始时间线、探针和独立重算结果
- [ ] 精确 PG16/TimescaleDB/pgBackRest 镜像在独立故障域完成加密 backup、PITR、回滚和 failover
- [ ] 35 天/5 full set 保留、WAL 连续性、完整性和失败告警矩阵通过
- [ ] 恢复后 Alembic、TimescaleDB、关键数据摘要、约束/序列、readiness 和关键读写一致
- [ ] 目录穿越、符号链接、错误密钥、损坏制品、WAL 缺口和未 fence promotion 全部在副作用前拒绝
- [ ] Story 39.7 的统一观测/告警/时间线契约已完成并被正式演练消费
- [ ] 39.3 manifest 与实际 changeset、镜像、环境和全部原始产物绑定，独立验证为 `PASS`
- [ ] File List 与 Git diff 一致，无秘密/备份/WAL，未包含或还原无关用户变更
- [ ] Story gate 可为 `PASS`，Epic 39 production gate 仍独立计算

## Story Completion Status

- **状态:** in-progress
- **创建日期:** 2026-08-14
- **说明:** D39-01 已由唯一维护者治理记录；实施上下文已完成。39.7 是正式告警、统一时间线和最终 `PASS` 的完成前置，不阻止先行实施备份/恢复基础。

## Dev Agent Record

### Agent Model Used

GPT-5 Codex

### Debug Log References

- 2026-08-14 RED: `pytest -q tests/test_story_39_3_dr_config.py` -> 5 failed，确认浮动镜像、DR Compose、WAL/复制配置和 secret 契约均不存在。
- 2026-08-14 GREEN: 同一目标测试 -> 5 passed；根 Compose 与 DR Compose 均通过 `docker compose config --quiet`，Ruff、Dockerfile `--check` 和 `git diff --check` 通过。
- 2026-08-14 REGRESSION: 4038 个默认收集项按文件分片运行；正式 `backend/tests/` 文件全部覆盖并通过。额外收集的 `app/services/connection_test.py` 会因函数名误收集，顶层 Story 28 seed 脚本与 Story 39.2 的 `SEED_ENABLED=false` 冲突，均为本 Story 变更外的既有基线问题。并行临时数据库导致的 4 个连接测试和 1 个 L1 测试已在默认环境单独重跑为 22 passed、1 passed。
- 2026-08-14 BUILD: 完整镜像构建在拉取固定 ECR 基础层时长期无进度后终止；Dockerfile 解析、基础 manifest digest 查询和 `docker build --check` 已通过，正式发布镜像仍必须以 `@sha256` 注入并由后续演练证据绑定。
- 2026-08-14 TASK 2 RED/GREEN: `pytest -q tests/test_story_39_3_backup_jobs.py` 从 5 failed 转为 5 passed；Task 1 配置回归同步为 5 passed。
- 2026-08-14 TASK 2 RUNTIME: Debian Bash 容器实际验证 weekly/daily/incremental 调度去重、原子 success/last-run、并发退出码 75、少于 5 个 full 时退出码 65、expire 前后最新链保护和三份可解析状态 JSON；真实 PostgreSQL 16 执行 `postgres-status.sql` 并产出合法 JSON。
- 2026-08-14 TASK 2 QUALITY: ShellCheck style、Ruff、根/DR Compose 解析、Dockerfile `--check`、空白检查通过；备份/健康、生产配置、授权清单、降级健康和 39.3 契约相邻回归 75 passed。
- 2026-08-14 TASK 3 RED/GREEN: `pytest -q tests/test_story_39_3_backup_jobs.py tests/test_story_39_3_restore_jobs.py` -> 17 passed；ShellCheck、Compose 解析、Dockerfile `--check` 和空白检查通过。
- 2026-08-14 TASK 3 RUNTIME: 从空主库卷和空仓库卷构建最终环境，使用固定镜像 digest `sha256:e6ca69c005bfba5b30dbb91c58a181874e2c833e0a311ad3998f32d4b497f3e4` 完成 latest、time、LSN 和 restore point 四种真实恢复；PostgreSQL 16.15、TimescaleDB 2.29.1、pgBackRest 2.59.0、Timescale 对象和探针验证通过。
- 2026-08-14 TASK 3 NEGATIVE: 错误密钥、非空目标、版本漂移、截断 manifest 和 WAL 缺口均在目标解包前失败关闭；截断/WAL 缺口目标保持为空，源仓库重新 verify 通过。
- 2026-08-14 TASK 3 REGRESSION: 全部 215 个后端测试文件分为四个有序单进程分片及空间/拓扑/联动隔离分片执行，合计 4033 passed、9 skipped、0 failed。`test_spatial_topology_linkage_coverage.py` 的 reload 用例会在 pytest 返回后因全局 SQLite `aiosqlite` 池未释放而阻止进程退出；显式 `engine.dispose()` 后该文件 130 条断言全部通过，未修改 Story 范围外代码。
- 2026-08-14 TASK 3 GATE REOPENED: Task 4 预检发现最终恢复库只有 `alembic_version`、`point_history` 和 `restore_probe`，`alembic_version=20260707_0100` 不能证明完整应用 schema；撤回 Task 3 完成状态，要求从真实 Alembic 全 schema 主库重新备份并恢复后再验收。
- 2026-08-14 TASK 3 SCHEMA GATE IMAGE: 新增 188 表恢复门禁和受限 Docker build context；从已验证 runtime digest `sha256:e6ca69c005bfba5b30dbb91c58a181874e2c833e0a311ad3998f32d4b497f3e4` 构建增量镜像 `sha256:9453a644830b0a971163d6dcd6cc99953a6ec9bb52ddd76056c4adb3357350fc`。镜像内 PostgreSQL 16.15、pgBackRest 2.59.0、188 表清单和 Shell 语法检查通过；固定应用镜像的 `Base.metadata` 与清单均为 188 表且 SHA256=`81cdd3d0d4d3a4ad5edc128981e383bcfff5f37bc1b9d30f491c1598fc1be6b3`。
- 2026-08-14 TASK 3 FULL SCHEMA HALT: 新隔离项目 `dcim-story-39-3-full` 未复用旧卷。空库执行 `alembic upgrade head` 发现现有 revision 链在 `a001_full_schema` 之前创建依赖 `devices` 的表，不能从零升级；改用精确应用镜像进行当前 schema 引导时，空 pgBackRest 仓库尚未 `stanza-create`，`archive-push` 返回 103 并导致 PostgreSQL 子进程反复终止/崩溃恢复，DDL 事务回滚后 public 表数为 0。连续三次实施失败触发工作流 HALT；已停止新主库容器并保留数据卷、仓库和数据库日志，Task 3 保持未完成。
- 2026-08-15 TASK 3 FULL SCHEMA RESOLVED: 主库 Docker entrypoint 临时 PostgreSQL 阶段先执行 pgBackRest `stanza-create`/`check`，随后固定应用镜像 `ghcr.io/proecheng/dcim-platform/backend@sha256:58bb47905f93872fb4be2817c22d600f10fa60432dcd20f59405a7e149f22bcd` 在空目标库执行受约束 schema bootstrap：验证 Story/Compose 标签、镜像 digest、188 表 manifest 与 `Base.metadata` SHA256 `81cdd3d0d4d3a4ad5edc128981e383bcfff5f37bc1b9d30f491c1598fc1be6b3`，再建立完整 metadata、运行真实 Timescale migration 并到达 Alembic head `20260707_0100`。最终 PostgreSQL schema-gate 镜像为 `dcim-postgres@sha256:c81881c25873714a9425180fbeb321a8b46fa60e278f840d25dca34684796ca2`。
- 2026-08-15 TASK 3 POSITIVE: 从 full backup `20260815-015500F` 分别完成 latest、time `2026-08-15T01:55:40Z`、LSN `0/9002858` 和 restore point `story_39_3_full_schema_target` 恢复，探针行数依次为 24、21、22、23；四种恢复均通过 188 表、`pg_amcheck`、Alembic head、摘要/约束/序列/写探针和 TimescaleDB extension/hypertable/chunk/job/压缩/保留策略门禁。固定应用镜像在 latest 恢复库通过 Unix socket 完成 24 行读写探针。
- 2026-08-15 TASK 3 NEGATIVE FINAL: 错误密钥、版本漂移、非空目标、空恢复链、损坏 manifest 和 WAL 缺口六类场景均在解包前失败关闭；损坏与 WAL 测试仅使用克隆仓库，正式仓库随后重新 `verify` 成功。
- 2026-08-15 TASK 3 REGRESSION FINAL: Story 39.3 专项 31 passed；Ruff、Compose config、Docker 构建层 Shell 语法和 `git diff --check` 通过。完整后端回归覆盖 216 个普通测试文件及独立空间拓扑文件，合计 4047 passed、9 skipped、0 failed；对 pytest 汇总后的既有全局退出等待使用隔离测试进程结束，不修改 Story 范围外源码。
- 2026-08-15 TASK 4 RED/GREEN: 迁移契约测试先以 4 failed 暴露应用 HMAC 未注入、Unix socket 未挂载、上一镜像 schema 未验证和源码 revision 未绑定；补强后 `test_story_39_3_migration_rollback.py` 为 8 passed。所有应用/Alembic 容器只按环境变量名注入 secret，restore socket volume 同时校验 Story/Compose/role 标签。
- 2026-08-15 TASK 4 PREVIOUS IMAGE: release migration `20260707_0100` 的父提交为 `4dfac2df0d80141bd8044f8ccf9ed26de3cd6933`；旧 Dockerfile 直接从 PyPI 构建因约 30 KB/s 下载在 30 分钟后超时，未生成镜像。最终以固定当前运行时镜像为依赖层，清空 `/app` 后覆盖父提交完整后端源码，生成 `ghcr.io/proecheng/dcim-platform/backend@sha256:260c6388f978d614be8c3ae54463312a5bbcf5cfc8bc00d2adb65a5baa462169`；镜像标签、缺失 `20260707_0100`、存在 `20260322_0200` 和四个 release 字段缺失均通过门禁。
- 2026-08-15 TASK 4 REVERSIBLE: 在隔离恢复库、活动应用连接为 0 和命名 restore point `story_39_3_reversible_revision` (`0/1416BC18`) 下，当前镜像成功 downgrade 到 `20260322_0200`，上一镜像完成 ORM/临时写探针，再 upgrade 到 `20260707_0100` 并由当前镜像完成同一探针；22 个步骤全部通过，前后 `power_devices` 摘要一致，TimescaleDB 对象未变化。
- 2026-08-15 TASK 4 NEGATIVE: non-head、Timescale policy 缺失、非空 release 字段、依赖视图导致真实 downgrade 失败、无效冻结令牌、活动应用连接和错误镜像 revision 分别返回 `alembic_not_at_head`、`timescaledb_objects_missing`、`migration_invariant_changed`、`migration_command_failed`、`write_freeze_missing`、`active_application_connections` 和 `application_image_provenance_mismatch`；所有可恢复探针状态均在场景后复原。
- 2026-08-15 TASK 4 PHYSICAL: 独立项目在上一 revision 制作 full backup `20260815-061604F`，创建 restore point `story_39_3_irreversible_final` (`0/7036C48`，WAL switch `0/7036C60`) 并通过 archive check；升级后删除 `point_history` 使 head 仍为当前值但 hypertable/policy 全失，再 fence 源库。命名 PITR 恢复到 `20260322_0200` 后 188 表、hypertable 和两个 policy 全部恢复；上一镜像读写通过，当前镜像因缺少 release 字段按预期停止。
- 2026-08-15 TASK 4 QUALITY: Story 39.3 全部专项 34 passed；Ruff check/format、DR Compose config、21 个 Task 4 JSON 解析和 `git diff --check` 通过。运行时原始结果保存在临时目录的 `migration-*` 子目录，故障源保持 fenced，未删除证据容器、卷或仓库。
- 2026-08-15 TASK 5 RED/GREEN: 新增 failover 契约与编排器，RED 从 4 failed 转为 5 passed；固定 `postgres-writer` 稳定端点、连续写探针、UTC/monotonic 时间线、promotion 前双重 fence、应用镜像读写门禁、RTO/RPO 重算和同机证据失败关闭。单 Docker daemon 即使提供本地独立域声明也只能拒绝，不能签正式 `PASS`。
- 2026-08-15 TASK 5 IMAGE: 以已验证 schema-gate digest `sha256:c81881c25873714a9425180fbeb321a8b46fa60e278f840d25dca34684796ca2` 为来源构建 `dcim-postgres@sha256:ad57905638f480f574c1955bf433e5414ddf8158a4a5f76ad2ee7d5e683e0f76`；镜像内 PostgreSQL 16.15、pgBackRest 2.59.0、188 表清单和 Shell 语法门禁通过。
- 2026-08-15 TASK 5 RUNTIME: 五个全新同机 Compose 项目均使用独立卷和显式 `10.253.50.0/24`–`10.253.73.0/24` 网络；最终计划切换 RTO 25.437 秒、RPO 0、26/26 提交恢复，意外 `SIGKILL` RTO 24.047 秒、整站机制 `SIGKILL` RTO 23.937 秒，后二者均 RPO 0 且 26/26 提交恢复。三类场景均先 fence 后 promotion、稳定端点和固定应用镜像读写通过，旧主被拒绝直接上线并全量重建为 replay LSN 追平的 standby。
- 2026-08-15 TASK 5 QUALITY: Story 39.3 全部专项 39 passed；Ruff、DR Compose、镜像内 Shell 语法和 `git diff --check` 通过。完整后端回归单次 20 分钟和首个 55 文件分片 10 分钟均因命令时限退出且没有可用汇总，未计为通过；Task 3 已验证的完整基线仍为 4047 passed、9 skipped。Task 5 原始 JSON 与全部新容器、卷、网络保留，未清理旧证据资源。
- 2026-08-15 TASK 5.4 PREFLIGHT: `default` 与 `desktop-linux` Docker context 均解析到本机 `docker-desktop` daemon ID `7fd954cc-90bb-4647-a9f3-a82b05630b37` 和同一 `/var/lib/docker`；未配置 `ssh://` context、SSH 远端主机、独立存储或第二站点参数。正式独立故障域演练因缺少第二执行目标而未启动，不能以 WSL、同机 context、本地声明或同机 VM 替代；5.4、Task 5 和 Story 状态保持打开。

### Implementation Plan

- 使用固定 PostgreSQL 16.15 基础 manifest digest，并以固定提交/源码 SHA256 构建 TimescaleDB 2.29.1 与 pgBackRest 2.59.0；开发镜像使用版本化标签，正式 DR Compose 强制要求 registry `@sha256` 引用。
- 将默认单库启动与独立 DR 拓扑分离；DR 拓扑使用主库、温备、备份作业和隔离恢复四个角色，主/备/恢复数据卷及站点网络互不复用，仓库必须是外部卷。
- 通过 pgBackRest wrapper 从 secret file 读取仓库密钥，初始化脚本从 secret file 创建 SCRAM 复制用户和有上限物理 slot；任何 promotion 前由运行手册强制旧主 fence，旧主只允许 `pg_rewind` 或 full rebuild 后回归。
- 使用独立 `backup-scheduler` 按 UTC 槽位执行每周 full、每日 differential 和日内 incremental；所有运维动作通过原子目录锁串行化，只有 check/backup/verify/status 全部成功后才发布 success marker。
- 关闭 pgBackRest 自动 expire，按 35 天 time retention 和 6 条 weekly full WAL 链保留；清理前预测 35 天窗口内至少仍有 5 个 full，清理后验证 full 数与最新链未改变，再运行 pgBackRest `verify`。
- 将 pgBackRest 原始 info、PostgreSQL 归档/复制/slot 查询和备份年龄/失败码分别原子发布到 `dr-status`，仅作为 Story 39.7 的机器输入，不在本 Story 虚构告警闭环。
- 恢复入口只允许空的隔离目标卷，先校验密钥、仓库版本、pgBackRest 文本状态和 WAL 连续性，再执行 latest 或指定 time/LSN/restore point 的 cluster 级恢复；所有失败路径不发布成功标记。
- 恢复后由独立 validator 校验 pgBackRest、`pg_amcheck --install-missing`、Alembic head、全局对象、表/行摘要、约束/序列、写探针及 TimescaleDB 扩展、hypertable、chunk、job、压缩和保留策略。
- 全 schema 主库在产生首个待归档 WAL 前完成 `stanza-create`/`check`；固定应用镜像只在空目标库、标签/镜像/schema hash 全部匹配时执行 188 表 schema 引导、真实 TimescaleDB 转换和 Alembic head 验证，再建立可备份基线。
- 当前 release 仅在四个 flexibility 字段均为空时允许 `20260707_0100 -> 20260322_0200 -> 20260707_0100`；演练前强制写冻结、零活动应用连接、命名 restore point、固定镜像 digest/source revision/schema inventory 和 Unix socket 隔离挂载。
- `a001_full_schema` 与 Timescale hypertable 等不可逆边界不执行伪 downgrade；从迁移前 full backup/连续 WAL 恢复命名 restore point，恢复后只启动上一已验证应用。当前应用在上一 schema 上必须停止，直到数据库重新 upgrade 并完成当前应用探针。
- failover 编排器仅接受 Story/Compose/role 标签一致的新隔离项目；通过稳定端点持续写递增序号，计划切换等待 replay LSN，故障场景注入 `SIGKILL`，所有 promotion 前重复确认旧主停止且离开客户端网络。
- RTO 到稳定端点连续三次写入并由固定应用镜像完成 ORM 读取/事务写入为止；RPO 从全部 client-acknowledged 序列和恢复序列重算。旧主必须显式授权 full rebuild，清空前再次校验唯一项目数据卷，重建后同时验证 in-recovery、replay LSN 追平和探针行数一致。
- 单 Docker daemon 的全部演练固定为 `mechanism-only`；本地声明不能把结果升级为独立故障域证据。5.4 等待真实独立故障域执行与外部采集，因此 Task 5 总项保持打开。

### Completion Notes List

- Task 1 完成：移除 `latest-pg16`，新增可复现 PostgreSQL/TimescaleDB/pgBackRest 镜像定义、版本清单和升级漂移规则。
- Task 1 完成：新增独立 DR Compose，隔离 primary/standby/restore 数据卷、站点网络和外部加密仓库；默认 Compose 仍保持原服务依赖和 Story 39.2 强凭据约束。
- Task 1 完成：配置连续 WAL archive push/get、60 秒 archive timeout、4 个 slot 上限、10GB slot WAL 上限、`wal_log_hints`、`full_page_writes` 和机器可读复制/归档查询。
- Task 1 完成：复制、仓库和 fencing 凭据均由 secret file 注入；缺失、弱值或占位值在副作用前失败关闭，错误输出不包含秘密内容。
- Task 2 完成：新增独立单实例 UTC 备份调度器，支持 full/diff/incr、stanza/check/verify/expire/status，原子互斥、唯一运行记录、success marker 和确定性失败码。
- Task 2 完成：将 35 天 time retention 与 6 条 weekly full WAL 链结合；expire 在副作用前验证 35 天窗口内至少保留 5 个 full，并在清理后保护最新恢复链和执行仓库 verify。
- Task 2 完成：原子输出备份年龄、35 天窗口 full 数、归档年龄、write/flush/replay 延迟、slot WAL 占用/上限比率和失败码，明确由 39.7 后续消费。
- Task 3 完成：新增受标签、固定镜像 digest 和双重 188 表 SHA256 约束的空库 schema bootstrap，修复空仓库首次归档前的 stanza 初始化顺序，并建立完整 Alembic/TimescaleDB 可备份基线。
- Task 3 完成：对 full backup `20260815-015500F` 完成 latest、time、LSN 和 restore point 四种隔离恢复；188 表、pgBackRest、`pg_amcheck`、Alembic、数据不变量、写探针及 TimescaleDB 对象全部通过。
- Task 3 完成：错误密钥、版本漂移、非空目标、空恢复链、损坏 manifest 和 WAL 缺口均在解包前失败关闭；固定应用镜像兼容探针和完整后端回归通过。
- Task 4 完成：将 `20260707_0100` 归类为带“新字段必须为空”不变量的条件可逆 revision，将 `a001_full_schema` 和 Timescale hypertable 归类为必须物理恢复的不可逆边界；镜像 digest、源码 revision 和 schema inventory 均失败关闭。
- Task 4 完成：可逆矩阵在写冻结、零活动连接和命名 restore point 下完成 downgrade、上一应用读写、upgrade、当前应用读写，前后摘要、Alembic head 和 TimescaleDB 对象一致。
- Task 4 完成：独立 full backup/命名 PITR 从删除 hypertable 的故障源恢复上一 schema，上一应用通过且当前应用明确停止；七类迁移/连接/镜像负向场景在副作用前或事务边界失败关闭，供 Story 39.12 直接消费。
- Task 5.1 完成：建立稳定端点连续写探针和受信 UTC/monotonic 时间线，真实覆盖计划切换、意外主库 `SIGKILL` 和整站恢复机制场景，按已确认提交重算 RTO/RPO。
- Task 5.2 完成：所有场景均在 promotion 前验证容器停止与客户端网络断开，提升后切换 `postgres-writer`，连续数据库写入及固定应用镜像 ORM/事务探针通过。
- Task 5.3 完成：未经处理旧主重新上线被明确拒绝；在唯一项目/卷标签校验与显式授权后执行 full rebuild，重建节点以 standby 回归并通过 replay LSN 与完整探针集门禁。
- Task 5.4 部分完成：同机演练明确记录为 `mechanism-only` / `mechanism-pass` 且 `formal_pass=false`；因当前没有真实独立故障域，正式站点证据仍未完成，不勾选 5.4 或 Task 5。
- 第一批代码审查修复完成：默认 Compose 的 DR 初始化改为显式启用，正式 DR 镜像强制组装 `@sha256` 引用，空仓库保留检查正常等待首备，备份互斥改为崩溃可回收的 `flock`，调度器初始化不再覆盖最近失败状态。

### File List

- `.dockerignore`
- `_bmad-output/implementation-artifacts/39-3-postgresql-disaster-recovery-and-failover.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `_bmad-output/planning-artifacts/architecture.md`
- `_bmad-output/planning-artifacts/epics.md`
- `.env.example`
- `docker-compose.yml`
- `backend/tests/test_story_39_3_backup_jobs.py`
- `backend/tests/test_story_39_3_migration_rollback.py`
- `backend/tests/test_story_39_3_restore_jobs.py`
- `backend/tests/test_story_39_3_schema_bootstrap.py`
- `deploy/dr/README.md`
- `deploy/dr/docker-compose.dr.yml`
- `deploy/postgres-backup/Dockerfile`
- `deploy/postgres-backup/Dockerfile.schema-gate`
- `deploy/postgres-backup/backup-healthcheck.sh`
- `deploy/postgres-backup/backup-job.sh`
- `deploy/postgres-backup/backup-scheduler.sh`
- `deploy/postgres-backup/init-primary.sh`
- `deploy/postgres-backup/expected-schema-tables.txt`
- `deploy/postgres-backup/failover-contract.yaml`
- `deploy/postgres-backup/migration-rollback-contract.yaml`
- `deploy/postgres-backup/pgbackrest-wrapper`
- `deploy/postgres-backup/pgbackrest.conf`
- `deploy/postgres-backup/postgres-status.sql`
- `deploy/postgres-backup/postgresql-primary.conf`
- `deploy/postgres-backup/postgresql-standby.conf`
- `deploy/postgres-backup/retention-guard.sh`
- `deploy/postgres-backup/restore-job.sh`
- `deploy/postgres-backup/restore-validate.sh`
- `deploy/postgres-backup/standby-entrypoint.sh`
- `deploy/postgres-backup/status-snapshot.sh`
- `deploy/postgres-backup/validate-secrets.sh`
- `deploy/postgres-backup/versions.yaml`
- `deploy/postgres-backup/wal-continuity-check.sh`
- `backend/tests/test_story_39_3_dr_config.py`
- `backend/tests/test_story_39_3_failover.py`
- `scripts/story_39_3_failover_drill.py`
- `scripts/story_39_3_migration_drill.py`
- `scripts/story_39_3_schema_bootstrap.py`

## Change Log

- 2026-08-14: 记录 D39-01，创建 Story 39.3 实施指南并设为 `ready-for-dev`；明确 39.7 为最终门禁证据的完成前置。
- 2026-08-14: 完成 Task 1，固化数据库组件版本与构建来源，新增隔离 DR 拓扑、WAL/复制配置、secret 失败关闭和 fencing/安全回归契约。
- 2026-08-14: 完成 Task 2，新增独立备份调度、原子作业状态、35 天/至少 5 full 的清理前后保护，以及供 Story 39.7 消费的备份/归档/复制/slot 机器指标。
- 2026-08-14: 为 Task 3 增加完整 188 表恢复门禁和迁移回滚契约；全 schema 重演发现空库 Alembic 链及空仓库 stanza 初始化顺序缺陷，Task 3 保持打开并按三次失败规则 HALT。
- 2026-08-15: 完成 Task 3，修复首次归档前 stanza 初始化并加入受约束的 188 表 schema bootstrap；四种 PITR、六类失败关闭、TimescaleDB/应用兼容探针及完整后端回归通过，Story 保持 `in-progress` 并进入 Task 4。
- 2026-08-15: 完成 Task 4，绑定当前/上一应用镜像 digest、source revision 和 schema inventory；可逆 downgrade/upgrade、七类失败关闭及独立不可逆命名 PITR 通过，为 39.12 固化“上一应用可启动、当前应用必须等待 schema roll-forward”的数据库回滚条件。
- 2026-08-15: 完成 Task 5.1–5.3，新增受控 failover/failback 编排、稳定端点、持续写入和固定应用探针；计划/意外/整站机制演练及旧主全量重建通过。5.4 因缺少真实独立故障域继续打开，Story 保持 `in-progress`。
- 2026-08-15: 完成第一批代码审查修复，关闭默认栈初始化、镜像摘要、空仓库启动、崩溃残留锁和失败状态覆盖五项缺陷；Story 39.3 专项增至 41 passed，状态保持 `in-progress`。
