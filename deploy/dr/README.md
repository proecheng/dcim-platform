# PostgreSQL 16 灾备拓扑

该 Compose 只提供可重复的 PostgreSQL/TimescaleDB/pgBackRest 机制环境。正式镜像必须由
`deploy/postgres-backup/Dockerfile` 构建并发布，`DCIM_POSTGRES_IMAGE_REPOSITORY` 填写带版本标签的仓库引用，
`DCIM_POSTGRES_IMAGE_DIGEST` 填写不含 `sha256:` 前缀的 64 位 manifest digest。Compose 会将两者固定组合为
`<repository>@sha256:<digest>`；标签或本地 image ID 不能用于正式证据。

## 故障域

- `postgres-primary-data`、`postgres-standby-data` 和 `postgres-restore-data` 互不复用。
- `pgbackrest-repository` 是预先创建的 external 加密仓库卷。正式演练必须把它放在主库主机和
  `postgres-primary-data` 之外；同机卷只能标记为机制测试。
- 恢复服务只能以只读方式挂载仓库，并位于 `restore-isolated` 网络。
- secret 只通过 Compose secret file 注入。缺失、过短或 placeholder 内容会失败关闭。

## Promotion 前置

任何 promotion 前必须完成并留存旧主 fence 证据：旧主进程已停止，并且其客户端网络或存储写权限
已由外部控制面撤销。只有容器健康检查失败不等于 fence，禁止据此提升备库。本方案不提供
automatic failover，也不声称 PostgreSQL 能自行完成 STONITH。

计划切换必须先等待 replay LSN 追平。意外故障切换必须先确认旧主无法接受写入，再执行
`pg_ctl promote` 或 `SELECT pg_promote()`，随后切换稳定数据库端点并运行关键读写检查。

旧主不得直接重新作为 primary 启动。只有 `pg_rewind` 成功并完成一致性检查后才可作为 standby
回归；任何 `pg_rewind` 失败都要求丢弃目标目录并执行 full rebuild。

`scripts/story_39_3_failover_drill.py` 编排计划切换、意外主库故障和整站恢复机制测试。它只接受带
Story/Compose/role 标签的新隔离项目，持续通过 `postgres-writer` 写入递增探针，先 fence 后
promotion，并在稳定端点连续写入和固定应用镜像读写均恢复后结束 RTO。`--allow-full-rebuild` 会在
再次校验标签后清空该演练项目的旧主数据卷，并将旧主全量重建为追平 replay LSN 的 standby。

该脚本连接单个 Docker daemon，因此输出只能是 `mechanism-only` / `mechanism-pass`。即使提供本地
failure-domain 声明，也不能签署独立故障域正式 `PASS`；正式站点证据必须由真实独立故障域的外部
采集器和后续 Story 39.3 证据门禁验证。

## 备份调度与保留

`backup-scheduler` 只在 `backup` profile 中运行，并且是独立于 FastAPI worker 的单实例作业。
默认按 UTC 在星期日 02:00 执行 full，其他日期 02:00 执行 differential，在 08:00、14:00、
20:00 执行 incremental。可通过 `BACKUP_FULL_WEEKDAY`、`BACKUP_DAILY_HOUR` 和
`BACKUP_INCREMENTAL_HOURS` 调整；非法值会在调度启动前失败。

pgBackRest full retention 使用 35 天时间窗口，WAL 归档保留 6 条 full 链，以覆盖每周 full 的
35 天窗口并高于至少 5 个 full set 的硬下限。自动 expire 已关闭，所有清理必须经过
`retention-guard.sh`：清理前确认 35 天窗口内预计仍保留至少 5 个 full，清理后再次确认 full
数量和最新恢复链未变化，随后运行 pgBackRest `verify`。不足 5 个 full 的仓库仍可继续积累备份，
但不会执行清理。

所有作业使用状态卷中的原子 `mkdir` 互斥；并发请求返回退出码 75。成功只在 pgBackRest check、
backup/expire、verify 和状态快照全部完成后发布 `success/<run-id>.json`。失败记录固定错误码，
不写入命令参数、连接串或 secret 内容。

## 机器状态

`dr-status` 卷包含以下原子发布文件：

- `last-run.json` 和 `runs/<run-id>.json`：操作、步骤、退出码和失败码。
- `pgbackrest-info.json`：pgBackRest 原始仓库状态。
- `postgres-status.json`：归档年龄、复制延迟、slot 保留 WAL 和上限利用率。
- `backup-status.json`：备份年龄、full 总数、35 天窗口 full 数和最近失败码。
- `pgbackrest-info.before-expire.json`、`pgbackrest-info.after-expire.json`：清理保护原始快照。

这些文件是 Story 39.7 的机器可读输入，不代表正式告警、SLO 或生产门禁已经通过。

## 隔离恢复与 PITR

恢复只应显式启动验证服务及其依赖，不要直接启动整个 DR 文件：

```bash
docker compose --env-file .env -f deploy/dr/docker-compose.dr.yml --profile restore up restore-validator
```

`postgres-restore` 只挂载独立的 `postgres-restore-data`、只读仓库、恢复 socket 和状态卷；Compose
中不允许出现 primary/standby 数据卷。运行时还要求 `RESTORE_ISOLATION_ID` 固定 guard，且在任何
仓库读取或 restore 前拒绝符号链接、缺失或非空 `PGDATA`。失败后的部分恢复目录不会被自动清理，
必须保留原始状态并由维护者确认后重建隔离恢复卷。

`RESTORE_TARGET_TYPE` 支持以下严格形式：

- `latest`：`RESTORE_TARGET_VALUE` 必须为空。
- `time`：只接受 UTC `YYYY-MM-DDTHH:MM:SSZ`。
- `lsn`：只接受 PostgreSQL `HEX/HEX` LSN。
- `name`：只接受 1–200 位安全 restore point 名称。

恢复前顺序执行仓库 info、PostgreSQL 16 版本匹配和 pgBackRest verify；错误密钥、空链、损坏
仓库或版本漂移均不会发布 restore staged marker。staged 只表示物理文件已写入，不表示数据库可用；
目标恢复完成后才启动隔离 postmaster，启动
失败写入 `recovery_start_failed`。

`restore-validator` 等待目标 recovery 完成并提升，然后执行 pgBackRest verify、`pg_amcheck --all`、
精确 Alembic head、全局对象、所有 public 表的精确行数和常量内存确定性摘要、约束、序列、事务内
写探针，以及 TimescaleDB 扩展、hypertable、chunk、job、压缩和保留策略查询。结果原子写入
`database-consistency.json`、`timescaledb-status.json`、`pg-amcheck.txt` 和
`restore-validation.json`；任一检查失败都不会生成 validation success marker。

## 版本漂移规则

PostgreSQL、TimescaleDB、pgBackRest、基础镜像 digest 或构建源码校验和发生变化时，必须：

1. 更新 `versions.yaml` 和正式 release image digest。
2. 重跑备份、PITR、迁移回滚、fencing/promotion 和旧主重建矩阵。
3. 记录镜像内 `SHOW server_version`、TimescaleDB 扩展版本和 `pgbackrest version` 原始输出。
4. 在新证据通过前继续使用旧 digest，不允许把浮动标签用于生产或正式证据。
