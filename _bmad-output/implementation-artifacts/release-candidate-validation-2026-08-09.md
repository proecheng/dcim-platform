---
title: V4.4 发布候选版验证报告
date: 2026-08-09
status: software-rc-passed-with-production-conditions
candidate_sha: 67ae905c16b777b87622552d4bf7c90ca20bfe87
ci_run: https://github.com/proecheng/dcim-platform/actions/runs/31275549085
cd_run: https://github.com/proecheng/dcim-platform/actions/runs/31276815014
---

# V4.4 发布候选版验证报告

## 1. 结论

候选提交 `67ae905c16b777b87622552d4bf7c90ca20bfe87` 通过软件 RC 自动化门禁：后端、前端、关键 E2E 及同 SHA 的后端/前端镜像发布均成功。

**发布判定：软件 RC 通过，附生产前置条件。** 本结论不等同于生产上线批准；依赖漏洞处置、真实设备联调、生产配置、迁移演练和现场 UAT 仍需单独签署。

## 2. 远端门禁证据

| 门禁 | 结果 | 证据 |
|---|---|---|
| CI | Success | [CI run 31275549085](https://github.com/proecheng/dcim-platform/actions/runs/31275549085) |
| 后端质量 | Ruff lint、Ruff format、compileall 全部通过 | 后端 Job `93148385649` |
| 后端回归 | 收集 3,347 项；3,337 passed、10 skipped、11 warnings；耗时 1,594.30 秒 | 覆盖率 63%，`coverage.xml` 已上传 |
| 前端质量 | ESLint、TypeScript、生产构建全部通过 | 前端 Job `93148385599` |
| 前端回归 | 162 个测试文件、1,700 个用例全部通过 | Vitest 远端日志 |
| 关键 E2E | Job 成功；13 个唯一用例通过 | E2E Job `93151297235` |
| CD | Success，按 `workflow_run.head_sha` 检出候选提交 | [CD run 31276815014](https://github.com/proecheng/dcim-platform/actions/runs/31276815014) |

关键 E2E 使用专用 SQLite 数据库，并设置测试 HMAC key，同时关闭 Redis、Demo 和 Simulation。管理员认证 setup 首次等待 `/dashboard` 超时，重试后通过，Playwright 将其记录为 1 个 flaky；该波动不改变本次 Job 的成功结论，但保留为后续稳定性改进项。

依赖安全扫描步骤执行成功，但 `pip-audit` 报告 7 个包共 28 个已知漏洞，涉及 `ecdsa`、`fastapi`、`python-dotenv`、`python-jose`、`python-multipart`、`setuptools` 和 `starlette`。当前 CI 将该步骤配置为非阻断项，因此这些漏洞必须在生产批准前完成升级、缓解或风险接受。

## 3. 镜像证据

| 镜像 | 标签 | Digest |
|---|---|---|
| Backend | `ghcr.io/proecheng/dcim-platform/backend:sha-67ae905`、`latest` | `sha256:73cfa550c3a650c3cb0bbdce3063d2934185a97ea404b5165eea881ad1351f56` |
| Frontend | `ghcr.io/proecheng/dcim-platform/frontend:sha-67ae905`、`latest` | `sha256:6ee8623bad903e965403ba4195e88ddb6d825ca242c4b34ea2130549e1e83060` |

两个镜像的 OCI revision 均为完整候选 SHA `67ae905c16b777b87622552d4bf7c90ca20bfe87`。

## 4. 本地补充验证

| 范围 | 结果 |
|---|---|
| 热模型场景 | 10 passed |
| 热模型核心 | 46 passed |
| 预冷域 | 252 passed |
| 配电拓扑服务 | 6 passed |
| CI 根目录过滤集合 | 794 passed、5 skipped |
| E2E 后端启动冒烟 | `/api/health` 返回 200，数据库 connected |
| CI 配置 | YAML 解析成功，Ruff 检查通过 |

所有本地热模型、拓扑和 E2E 冒烟使用隔离数据库；临时数据库和冒烟进程已清理。

## 5. 追溯与关闭

| 要求 | 状态 | 说明 |
|---|---|---|
| NFR-RC01 | Passed | 后端质量检查、完整回归、覆盖率和安全扫描均已执行 |
| NFR-RC02 | Passed | 前端 lint、类型、1,700 用例和生产构建通过 |
| NFR-RC03 | Passed with observation | 关键 E2E Job 成功，保留 1 个认证 setup flaky 观察项 |
| NFR-RC04 | Passed | 同 SHA 双镜像已推送，CI/CD URL 与 digest 可追溯 |
| Epic 38.3 | Done | CI 回归门禁恢复并完成远端验证 |
| Epic 38.4 | Done | E2E、镜像和 RC 证据完成 |

本报告验证的是候选代码 SHA `67ae905`。其后的规划/证据收尾提交不得改变候选业务代码，并须再次通过 master 的 CI/CD。

## 6. 生产前置条件

1. 对 28 个依赖漏洞逐项完成升级、补偿控制或书面风险接受。
2. 消除或接受管理员认证 setup 的首次登录 flaky，并在目标部署环境复跑关键 E2E。
3. 完成真实 Modbus/SNMP 设备和协议转换网关联调。
4. 配置并验证生产 HMAC key、JWT secret、数据库、Redis、MQTT、网络和访问控制。
5. 在生产等价数据库上完成迁移、备份恢复和回滚演练。
6. 完成性能、容量、安全和现场用户验收测试，并取得上线签署。
