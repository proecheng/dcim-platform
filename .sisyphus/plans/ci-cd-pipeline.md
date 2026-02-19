# CI/CD 流水线实施方案

## 概述
为 DCIM 项目配置 GitHub Actions CI/CD 流水线，包含 CI（持续集成）和 CD（持续部署）两个独立工作流。

## 文件清单
1. `.github/workflows/ci.yml` — CI 工作流
2. `.github/workflows/cd.yml` — CD 工作流
3. `backend/requirements-ci.txt` — CI 专用依赖（排除 torch/numpy/reportlab）

## CI 工作流设计 (.github/workflows/ci.yml)

### 触发条件
- push 到 master 分支
- PR 到 master 分支

### 并发控制
- PR: cancel-in-progress=true（同分支新推送取消旧运行）
- master push: 不取消（每次推送都要完整运行）

### Job 1: backend-tests（并行）
- runner: ubuntu-latest
- permissions: contents: read
- 步骤:
  1. checkout
  2. setup-python 3.11 + pip cache (cache-dependency-path: backend/requirements-ci.txt)
  3. pip install -r backend/requirements-ci.txt
  4. pytest tests/ --ignore=9个gateway测试 --cov=app --cov-report=xml
  5. upload coverage artifact

### Job 2: frontend-checks（并行）
- runner: ubuntu-latest
- permissions: contents: read
- 步骤:
  1. checkout
  2. setup-node 18 + npm cache (cache-dependency-path: frontend/package-lock.json)
  3. npm ci (在 frontend/ 目录)
  4. npm run build (先构建，生成 auto-imports.d.ts)
  5. npm run typecheck (依赖 build 生成的 .d.ts)

### 关键决策
- 不添加 PostgreSQL/Redis/EMQX 服务 — 测试使用内存 SQLite
- 前端无 vitest 测试文件，暂不运行 vitest（setup.ts 存在但无测试）
- build 必须在 typecheck 之前运行（auto-import 插件生成 .d.ts）

## CD 工作流设计 (.github/workflows/cd.yml)

### 触发条件
- workflow_run: ci.yml 在 master 上成功完成后

### 权限
- packages: write (推送到 ghcr.io)
- contents: read

### Job: build-and-push
- 步骤:
  1. checkout
  2. setup docker buildx
  3. login to ghcr.io (使用 GITHUB_TOKEN)
  4. docker/metadata-action 生成标签 (sha-xxx + latest)
  5. build+push backend image (cache-from/to: type=gha)
  6. build+push frontend image (cache-from/to: type=gha)

### 镜像地址
- `ghcr.io/proecheng/dcim-platform/backend:sha-<commit>`
- `ghcr.io/proecheng/dcim-platform/backend:latest`
- `ghcr.io/proecheng/dcim-platform/frontend:sha-<commit>`
- `ghcr.io/proecheng/dcim-platform/frontend:latest`

## requirements-ci.txt
从 requirements.txt 中排除:
- torch>=2.0.0 (约2GB，CI不需要)
- numpy>=1.24.0 (torch依赖)
- reportlab>=4.0 (PDF生成，CI不需要)

保留所有其他依赖，包括 pytest/pytest-asyncio/pytest-cov。

## 安全考虑
- CI workflow 最小权限: contents: read
- CD workflow 仅在 master push 后触发，不暴露给 fork PR
- 使用 GITHUB_TOKEN（自动提供），无需额外 secrets
- 不使用 pull_request_target（防止 fork 注入）
