---
stepsCompleted: [requirements-inventory, epic-design, story-creation, coverage-map]
inputDocuments: [_bmad-output/planning-artifacts/prd.md, _bmad-output/planning-artifacts/architecture.md]
---

# DCIM 算力中心智能监控系统 - Epic Breakdown

## Overview

本文档基于 DCIM 系统现有代码库的深度分析，将待完善的需求分解为可实施的 Epic 和 Story。已完成的功能标记为 done，待实现的功能按优先级排列。

## Requirements Inventory

### Functional Requirements

- FR-1: 用户认证与权限管理 (90% done)
- FR-2: 设备与点位管理 (80% done)
- FR-3: 实时监控 (90% done)
- FR-4: 告警管理 (85% done)
- FR-5: 能源管理 (92% done)
- FR-6: 节能优化 (88% done)
- FR-7: 资产管理 (88% done)
- FR-8: 运维管理 (82% done)
- FR-9: 报表统计 (80% done)
- FR-10: 容量管理 (75% done)
- FR-11: VPP 虚拟电厂 (78% done)
- FR-12: 系统管理 (82% done)

### NonFunctional Requirements

- NFR-6: 测试覆盖率 > 80% (当前 ~5%)
- NFR-1: API 响应时间 P95 < 500ms
- 代码质量：修复 100+ 类型错误

### FR Coverage Map

| FR | Epic 1 | Epic 2 | Epic 3 | Epic 4 | Epic 5 | Epic 6 |
|----|--------|--------|--------|--------|--------|--------|
| FR-1 用户认证 | 1.1 | | 3.1 | | | |
| FR-2 设备点位 | 1.2 | | | | | |
| FR-3 实时监控 | | | 3.1(间接) | | | |
| FR-4 告警管理 | 1.3, 1.4 | | 3.2 | | | |
| FR-5 能源管理 | | | 3.3 | | | |
| FR-6 节能优化 | | 2.2 | | | | |
| FR-7 资产管理 | | | 3.4 | | | 6.2 |
| FR-8 运维管理 | | | 3.5 | | 5.1, 5.2 | |
| FR-9 报表统计 | | 2.1 | | | | |
| FR-10 容量管理 | | | | | | 6.1 |
| FR-11 VPP | | | | | | (未规划) |
| FR-12 系统管理 | | 2.3 | | | | |
| NFR-6 测试覆盖 | | | 3.x | | | |
| 类型安全 | | | | 4.x | | |

## Epic List

1. **Epic 1: 缺失 UI 页面补全** — 补全后端 API 已有但前端页面缺失的功能
2. **Epic 2: 功能完善与修复** — 启用禁用功能、补全导出能力、完善管理界面
3. **Epic 3: 测试覆盖补全** — 为核心模块添加自动化测试（依赖 Epic 1、2 完成后执行，避免测试对象变动）
4. **Epic 4: 代码质量提升** — 修复类型错误、改善代码规范（可与 Epic 3 并行）
5. **Epic 5: 运维功能增强** — 巡检自动化、工单增强、知识库升级
6. **Epic 6: 高级功能完善** — 容量预测、VPP 增强、性能优化

### Epic 依赖关系

```
Epic 1 ──> Epic 3（测试需覆盖新增页面）
Epic 2 ──> Epic 3（测试需覆盖启用的功能）
Epic 1,2 可并行
Epic 3,4 可并行
Epic 5,6 可并行，在 Epic 3 之后
```

---

## Epic 1: 缺失 UI 页面补全

**目标:** 补全后端 API 已存在但前端页面缺失或不完整的功能模块。

### Story 1.1: 用户管理页面

As a 系统管理员,
I want 一个独立的用户管理页面,
So that 我可以创建、编辑、禁用和删除用户账户。

**Acceptance Criteria:**

**Given** 管理员已登录系统
**When** 导航到系统设置 > 用户管理
**Then** 显示用户列表（用户名、姓名、角色、部门、状态、最后登录时间）
**And** 支持创建新用户（用户名、密码、角色、部门、邮箱、手机）
**And** 支持编辑用户信息和重置密码
**And** 支持启用/禁用用户
**And** 仅 admin 角色可访问此页面

### Story 1.2: 独立设备管理页面

As a 运维工程师,
I want 一个独立的设备管理页面（与点位管理分离）,
So that 我可以专注于设备的增删改查和状态管理。

**Acceptance Criteria:**

**Given** 用户已登录系统
**When** 导航到设备管理页面
**Then** 显示设备列表（编码、名称、类型、区域、状态、厂商、型号）
**And** 支持按类型/区域/状态筛选
**And** 支持设备 CRUD 操作
**And** 路由路径为 `/device-manage`，与点位管理 `/devices` 分离

### Story 1.3: 告警规则管理 UI

As a 运维工程师,
I want 在告警管理中配置告警规则,
So that 我可以自定义告警触发条件和通知方式。

**Acceptance Criteria:**

**Given** 用户在告警管理页面
**When** 切换到"告警规则"标签
**Then** 显示已有告警规则列表
**And** 支持创建/编辑/删除告警规则
**And** 规则包含：触发条件、告警级别、通知方式、生效时间

### Story 1.4: 告警屏蔽管理 UI

As a 运维工程师,
I want 管理告警屏蔽策略,
So that 我可以在维护期间屏蔽特定点位或级别的告警。

**Acceptance Criteria:**

**Given** 用户在告警管理页面
**When** 切换到"告警屏蔽"标签
**Then** 显示已有屏蔽策略列表
**And** 支持按点位/级别/时间段创建屏蔽策略
**And** 支持启用/禁用/删除屏蔽策略

---

## Epic 2: 功能完善与修复

**目标:** 启用被禁用的功能模块，补全缺失的导出能力，完善管理界面。

### Story 2.1: PDF 报表导出

As a 运维主管,
I want 将报表导出为 PDF 格式,
So that 我可以打印或分享给不使用系统的人。

**Acceptance Criteria:**

**Given** 用户在报表页面查看已生成的报表
**When** 点击"导出 PDF"按钮
**Then** 生成包含统计数据和图表的 PDF 文件
**And** PDF 包含报表标题、时间范围、统计表格
**And** 后端添加 PDF 生成依赖（如 weasyprint 或 reportlab）

### Story 2.2: 启用优化路由

As a 能源管理员,
I want 使用优化分析功能,
So that 我可以获得更精确的节能建议。

**Acceptance Criteria:**

**Given** 后端已安装 numpy 依赖
**When** 系统启动时
**Then** optimization 路由正常注册和可用
**And** 在 requirements.txt 中添加 numpy
**And** 取消 optimization.py 路由的注释

### Story 2.3: 操作日志查看器

As a 系统管理员,
I want 在系统设置中查看操作日志和系统日志,
So that 我可以审计用户操作和排查系统问题。

**Acceptance Criteria:**

**Given** 管理员在系统设置页面
**When** 切换到"操作日志"标签
**Then** 显示操作日志列表（时间、用户、操作类型、详情、IP）
**And** 支持按时间范围/用户/操作类型筛选
**And** 支持导出日志

---

## Epic 3: 测试覆盖补全

**目标:** 为核心模块添加自动化测试，将后端核心模块覆盖率从 ~5% 提升到 >80%，前端关键组件有基础测试。

### Story 3.1: 认证模块测试

As a 开发者,
I want 认证模块有完整的测试覆盖,
So that 登录、权限、token 刷新等核心安全功能不会因代码变更而回归。

**Acceptance Criteria:**

**Given** 测试框架已配置（pytest + httpx AsyncClient）
**When** 运行 `pytest tests/api/test_auth.py`
**Then** 覆盖：登录成功/失败、token 刷新、获取当前用户、权限校验
**And** 覆盖：用户禁用后无法登录、错误密码限流
**And** 所有测试通过

### Story 3.2: 告警模块测试

As a 开发者,
I want 告警模块有完整的测试覆盖,
So that 告警的创建、确认、解除、统计等功能稳定可靠。

**Acceptance Criteria:**

**Given** 测试数据库中有预置的告警数据
**When** 运行 `pytest tests/api/test_alarm.py`
**Then** 覆盖：告警列表查询（分页/筛选）、告警确认、告警解除、批量确认
**And** 覆盖：告警统计、趋势分析、CSV 导出
**And** 所有测试通过

### Story 3.3: 能源管理模块测试

As a 开发者,
I want 能源管理核心 API 有测试覆盖,
So that PUE 计算、能耗统计、需量管理等关键功能准确可靠。

**Acceptance Criteria:**

**Given** 测试数据库中有预置的能源数据
**When** 运行 `pytest tests/api/test_energy.py`
**Then** 覆盖：PUE 查询、能耗统计（小时/日/月）、需量历史、电价管理
**And** 覆盖：配电拓扑 CRUD、功率曲线
**And** 所有测试通过

### Story 3.4: 资产管理模块测试

As a 开发者,
I want 资产管理 API 有测试覆盖,
So that 资产台账、机柜管理、生命周期等功能稳定。

**Acceptance Criteria:**

**Given** 测试数据库中有预置的资产和机柜数据
**When** 运行 `pytest tests/api/test_asset.py`
**Then** 覆盖：资产 CRUD、机柜 CRUD（U 位追踪）、生命周期记录、盘点
**And** 覆盖：资产统计、维保记录、保修预警
**And** 所有测试通过

### Story 3.5: 运维模块测试

As a 开发者,
I want 工单和巡检 API 有测试覆盖,
So that 运维工作流不会因代码变更而中断。

**Acceptance Criteria:**

**Given** 测试数据库中有预置的工单和巡检数据
**When** 运行 `pytest tests/api/test_operation.py`
**Then** 覆盖：工单全生命周期（创建→分配→开始→完成）、巡检计划/任务 CRUD
**And** 覆盖：知识库 CRUD、搜索
**And** 所有测试通过

### Story 3.6: 前端组件测试

As a 开发者,
I want 关键前端组件有单元测试,
So that UI 组件的行为和渲染正确。

**Acceptance Criteria:**

**Given** 前端测试框架已配置（Vitest + Vue Test Utils）
**When** 运行 `npm run test`
**Then** 覆盖：登录表单、仪表盘统计卡片、告警列表、能源图表
**And** 覆盖：路由守卫、权限指令、API 拦截器
**And** 所有测试通过

---

## Epic 4: 代码质量提升

**目标:** 修复类型错误，改善代码规范，提升可维护性。

### Story 4.1: 修复后端类型错误

As a 开发者,
I want 修复 LSP 报告的 100+ 类型错误,
So that 代码类型安全，IDE 提示准确。

**Acceptance Criteria:**

**Given** 后端代码中存在 SQLAlchemy Column 与 Python 原生类型不匹配的错误
**When** 修复所有 Pydantic schema 和 API 路由中的类型标注
**Then** `pyright` 或 `mypy` 检查零错误
**And** 不改变任何运行时行为

### Story 4.2: 前端 TypeScript 严格模式

As a 开发者,
I want 前端代码通过 TypeScript 严格检查,
So that 类型错误在编译时被捕获。

**Acceptance Criteria:**

**Given** 运行 `npm run typecheck`
**When** 检查完成
**Then** 零 TypeScript 错误
**And** 所有 API 响应类型与后端 schema 一致

---

## Epic 5: 运维功能增强

**目标:** 提升运维管理模块的实用性和自动化程度。

### Story 5.1: 巡检任务自动生成

As a 运维工程师,
I want 系统根据巡检计划自动生成巡检任务,
So that 我不需要手动创建每次巡检任务。

**Acceptance Criteria:**

**Given** 存在启用状态的巡检计划（频率：每日/每周/每月）
**When** 到达计划的执行时间
**Then** 系统自动创建巡检任务（APScheduler 定时任务）
**And** 任务包含计划中定义的检查项和位置

### Story 5.2: 知识库富文本编辑器

As a 运维工程师,
I want 使用富文本编辑器编写知识库文章,
So that 文章可以包含格式化文本、图片和代码块。

**Acceptance Criteria:**

**Given** 用户在知识库创建/编辑页面
**When** 编辑文章内容
**Then** 提供富文本编辑器（如 TinyMCE 或 WangEditor）
**And** 支持标题、列表、代码块、图片插入
**And** 内容以 HTML 格式存储

---

## Epic 6: 高级功能完善

**目标:** 完善容量管理和 VPP 模块，添加预测和高级分析能力。

### Story 6.1: 容量趋势预测

As a 资产管理员,
I want 查看容量使用趋势和预测,
So that 我可以提前规划扩容。

**Acceptance Criteria:**

**Given** 系统中有历史容量数据
**When** 查看容量管理页面
**Then** 显示空间/电力/制冷容量的历史趋势图
**And** 基于线性回归预测未来 3/6/12 个月的容量使用

### Story 6.2: 资产导入导出

As a 资产管理员,
I want 批量导入和导出资产数据,
So that 我可以与其他系统交换数据或批量初始化。

**Acceptance Criteria:**

**Given** 用户在资产管理页面
**When** 点击"导出"按钮
**Then** 生成包含所有资产信息的 Excel 文件
**And** 点击"导入"按钮可上传 Excel 文件批量创建资产
**And** 导入时验证数据格式并报告错误
