---
title: 'DCIM 系统菜单重构 — 三区分法'
slug: 'menu-restructure-three-zone'
created: '2026-02-21'
status: 'ready-for-dev'
stepsCompleted: [1, 2, 3, 4]
tech_stack: ['Vue 3', 'TypeScript', 'Element Plus', 'Vue Router', 'Pinia', 'FastAPI', 'SQLAlchemy']
files_to_modify:
  - 'frontend/src/router/index.ts'
  - 'frontend/src/layouts/MainLayout.vue'
  - 'frontend/src/stores/user.ts'
  - 'backend/app/models/user.py'
  - 'backend/app/main.py'
  - 'backend/app/core/security.py'
code_patterns:
  - 'Vue Router RouteRecordRaw 路由定义'
  - 'Element Plus el-menu/el-sub-menu 侧边栏菜单'
  - 'Pinia useUserStore 角色/权限管理'
  - 'FastAPI Depends(get_current_user) 权限检查'
test_patterns: []
---

# Tech-Spec: DCIM 系统菜单重构 — 三区分法

**Created:** 2026-02-21

## Overview

### Problem Statement

当前 DCIM 系统菜单存在以下问题：
1. **层级混乱**：一级菜单既有"域"分类（供配电、制冷）又有独立功能入口（告警、历史、报表），逻辑不统一
2. **功能散落**：设备管理相关的 5 个入口（点位管理、数据源管理、设备模板、设备管理、设备状态看板）平铺在一级菜单
3. **重复路由**：`diagnosis` 路由在 router/index.ts 中定义了两次（第37行和第383行）
4. **归属不清**：用电监控/能耗统计放在"供配电管理"下，配电配置也在供配电下
5. **基础设施过载**：8 个功能全部塞在"基础设施"下
6. **无角色过滤**：MainLayout.vue 中所有菜单对所有角色可见，前端没有做权限控制
7. **权限粒度粗**：后端只有 point/alarm/config/user/log/report 6 个资源域

### Solution

按"监控域/管理域/配置域"三区重组菜单结构，基于华为动环监测 6 大域为监控区骨架，扩展 RBAC 权限粒度，实现前端角色菜单过滤。

### Scope

**In Scope:**
- P0: 路由重构（router/index.ts）— 按新菜单结构调整路由定义，消除重复
- P0: 菜单重构（MainLayout.vue）— 按三区结构重写侧边栏，添加分区标题
- P0: 旧路由兼容重定向
- P1: 权限扩展 — 新增 device/gateway/energy/asset/linkage/diagnosis 等资源域
- P1: 前端角色菜单过滤 — 根据 userStore.role 控制菜单可见性
- P1: 菜单分区视觉 — 监控域/管理域/配置域分组标题样式

**Out of Scope:**
- 新增环境监控子页面（温湿度/水浸/烟雾红外）的具体业务实现（仅预留路由和占位页面）
- 新增安防消防子页面（门禁/消防联动）的具体业务实现（仅预留路由和占位页面）
- 后端 API 路由变更
- 移动端适配
- 大屏页面变更

## Context for Development

### Codebase Patterns

**路由定义模式** — `frontend/src/router/index.ts`:
```typescript
const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    redirect: '/dashboard',
    children: [
      {
        path: 'xxx',
        name: 'Xxx',
        redirect: '/xxx/sub',
        meta: { title: '标题', icon: 'IconName' },
        children: [
          { path: 'sub', name: 'XxxSub', component: () => import('@/views/xxx/sub.vue'), meta: { title: '子标题', icon: 'Icon' } }
        ]
      }
    ]
  }
]
```

**菜单渲染模式** — `frontend/src/layouts/MainLayout.vue`:
```vue
<el-menu :default-active="activeMenu" :collapse="isCollapse" :router="false" @select="handleMenuSelect">
  <el-menu-item index="/path">
    <el-icon><IconName /></el-icon>
    <template #title>标题</template>
  </el-menu-item>
  <el-sub-menu index="/parent">
    <template #title><el-icon><Icon /></el-icon><span>父标题</span></template>
    <el-menu-item index="/parent/child">子项</el-menu-item>
  </el-sub-menu>
</el-menu>
```

**角色体系** — 3 种角色: `admin` / `operator` / `viewer`
- `admin`: 全部权限
- `operator`: point:read/write, alarm:read/ack, report:read/write
- `viewer`: point:read, alarm:read, report:read

**权限检查模式** — 后端:
```python
async def get_current_admin_user(current_user=Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="权限不足")
```

**前端权限** — `stores/user.ts`:
```typescript
const isAdmin = computed(() => userInfo.value?.role === 'admin')
const isOperator = computed(() => ['admin', 'operator'].includes(userInfo.value?.role || ''))
function hasPermission(permission: string): boolean { return permissions.value.includes(permission) }
```

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `frontend/src/router/index.ts` | 路由定义（532行），需要全面重写 children 部分 |
| `frontend/src/layouts/MainLayout.vue` | 侧边栏菜单（477行），需要重写 el-menu 部分 |
| `frontend/src/stores/user.ts` | 用户状态管理，已有 isAdmin/isOperator/hasPermission |
| `backend/app/models/user.py` | User 模型（role 字段）和 RolePermission 模型 |
| `backend/app/main.py` | 初始化默认权限数据（第75-112行） |
| `backend/app/core/security.py` | get_current_user / get_current_admin_user |

### Technical Decisions

1. **菜单分区用 CSS 分组标题实现**，不改变 el-menu 组件结构，用 `<li class="menu-group-title">` 插入分区标题
2. **角色过滤用 v-if 实现**，基于 `userStore.role` 直接控制菜单项可见性，不引入复杂的权限指令
3. **旧路由全部保留 redirect**，确保书签和外部链接不失效
4. **新增子页面用占位组件**，统一创建 `PlaceholderView.vue` 组件，显示"功能开发中"

## Implementation Plan

### Tasks

#### Task 1: 路由重构 (router/index.ts) [P0]

**文件**: `frontend/src/router/index.ts`

**操作**: 重写 `children` 数组，按新菜单结构组织路由

**1.1** 删除重复的 `diagnosis` 路由定义（第37-54行的第一个定义）

**1.2** 创建占位组件 `frontend/src/views/common/PlaceholderView.vue`:
```vue
<template>
  <div class="placeholder-view">
    <el-empty description="功能开发中">
      <template #image>
        <el-icon :size="64" style="color: var(--el-color-info)"><Setting /></el-icon>
      </template>
    </el-empty>
  </div>
</template>
<script setup lang="ts">
import { Setting } from '@element-plus/icons-vue'
</script>
```

**1.3** 按以下结构重写路由 children（保持所有现有 component 引用不变，仅调整层级和路径）:

```
children: [
  // ══════ 监控域 ══════
  dashboard                          → 不变
  power/                             → 保留，移除 monitor/statistics/config 子路由
    overview, ups, battery, cabinet, pdu, topology
  cooling/                           → 保留全部
    overview, indoor, outdoor, cold-aisle, group-control
  environment/                       → 保留 overview，新增占位子路由
    overview, temperature, water-leak, smoke-infrared
  security/                          → 保留 overview，新增占位子路由，视频监控移入
    overview, access-control, video/ (cameras, control, playback), fire-linkage
  alarms                             → 不变

  // ══════ 管理域 ══════
  energy/                            → 新路径，合并原 power/monitor+statistics 和 energy-saving/*
    monitor, statistics, analysis, regulation, execution, report
  asset/                             → 原 infrastructure 拆分
    list, cabinet, capacity, spatial
  operation/                         → 保留，新增 reports 和 history
    workorder, inspection, knowledge, reports, history
  vpp/                               → 不变
    analysis

  // ══════ 配置域 ══════
  collection/                        → 新路径，归集原散落的设备/采集入口
    gateway, datasources, device-manage, device-status, devices, device-templates, power-config
  strategy/                          → 新路径，归集告警规则+联动+诊断
    alarm-rules/ (thresholds, compound, escalation, shield)
    linkage/ (policy, execution, recovery, timeline, command)
    diagnosis/ (results, rules)
    drift
  system/                            → 扩展
    users, sites, audit-log, settings, site-selection
]
```

**1.4** 添加旧路由兼容重定向:
```typescript
// 旧路由 → 新路由重定向
{ path: 'energy/monitor', redirect: '/energy/monitor' },
{ path: 'energy/statistics', redirect: '/energy/statistics' },
{ path: 'energy/analysis', redirect: '/energy/analysis' },
{ path: 'energy/regulation', redirect: '/energy/regulation' },
{ path: 'energy/execution', redirect: '/energy/execution' },
{ path: 'energy/config', redirect: '/collection/power-config' },
{ path: 'energy/topology', redirect: '/power/topology' },
{ path: 'power/monitor', redirect: '/energy/monitor' },
{ path: 'power/statistics', redirect: '/energy/statistics' },
{ path: 'power/config', redirect: '/collection/power-config' },
{ path: 'energy-saving/analysis', redirect: '/energy/analysis' },
{ path: 'energy-saving/regulation', redirect: '/energy/regulation' },
{ path: 'energy-saving/execution', redirect: '/energy/execution' },
{ path: 'infrastructure/asset', redirect: '/asset/list' },
{ path: 'infrastructure/cabinet', redirect: '/asset/cabinet' },
{ path: 'infrastructure/capacity', redirect: '/asset/capacity' },
{ path: 'infrastructure/spatial', redirect: '/asset/spatial' },
{ path: 'infrastructure/power-topology', redirect: '/collection/power-config' },
{ path: 'infrastructure/cooling-topology', redirect: '/collection/power-config' },
{ path: 'infrastructure/site-selection', redirect: '/system/site-selection' },
{ path: 'infrastructure/fault-impact', redirect: '/asset/capacity' },
{ path: 'asset/list', redirect: '/asset/list' },
{ path: 'asset/cabinet', redirect: '/asset/cabinet' },
{ path: 'devices', redirect: '/collection/devices' },
{ path: 'datasources', redirect: '/collection/datasources' },
{ path: 'device-templates', redirect: '/collection/device-templates' },
{ path: 'device-manage', redirect: '/collection/device-manage' },
{ path: 'device-status', redirect: '/collection/device-status' },
{ path: 'history', redirect: '/operation/history' },
{ path: 'reports', redirect: '/operation/reports' },
{ path: 'settings', redirect: '/system/settings' },
{ path: 'linkage/policy', redirect: '/strategy/linkage/policy' },
{ path: 'linkage/execution', redirect: '/strategy/linkage/execution' },
{ path: 'linkage/recovery', redirect: '/strategy/linkage/recovery' },
{ path: 'linkage/timeline', redirect: '/strategy/linkage/timeline' },
{ path: 'linkage/command', redirect: '/strategy/linkage/command' },
{ path: 'linkage/drift', redirect: '/strategy/drift' },
{ path: 'diagnosis/results', redirect: '/strategy/diagnosis/results' },
{ path: 'diagnosis/rules', redirect: '/strategy/diagnosis/rules' },
{ path: 'video/cameras', redirect: '/security/video/cameras' },
{ path: 'video/control', redirect: '/security/video/control' },
{ path: 'video/playback', redirect: '/security/video/playback' },
```

---

#### Task 2: 菜单重构 (MainLayout.vue) [P0]

**文件**: `frontend/src/layouts/MainLayout.vue`

**操作**: 重写 `<el-menu>` 内容，按三区结构组织，添加分区标题

**2.1** 在 `<el-menu>` 中添加分区标题组件，使用 `<li>` 元素:
```vue
<li v-show="!isCollapse" class="menu-group-title">监控域</li>
```

**2.2** 按新路由结构重写所有菜单项，完整结构:

```
监控域:
  综合概览 (/dashboard)
  供配电监控 (/power) → overview, ups, battery, cabinet, pdu, topology
  制冷监控 (/cooling) → overview, indoor, outdoor, cold-aisle, group-control
  环境监控 (/environment) → overview, temperature, water-leak, smoke-infrared
  安防消防 (/security) → overview, access-control, video/(cameras,control,playback), fire-linkage
  告警中心 (/alarms)

管理域:
  能效管理 (/energy) → monitor, statistics, analysis, regulation, execution, report
  资产与容量 (/asset) → list, cabinet, capacity, spatial
  运维管理 (/operation) → workorder, inspection, knowledge, reports, history
  虚拟电厂 (/vpp) → analysis

配置域 (admin/operator 可见):
  采集配置 (/collection) → gateway, datasources, device-manage, device-status, devices, device-templates, power-config
  策略引擎 (/strategy) → alarm-rules/(thresholds), linkage/(policy,execution,recovery,timeline,command), diagnosis/(results,rules), drift
  系统管理 (/system) → users, sites, audit-log, settings, site-selection  [admin only]
```

**2.3** 添加角色过滤 v-if:
- 配置域整体: `v-if="isOperator"` (admin + operator 可见)
- 系统管理: `v-if="isAdmin"` (仅 admin 可见)
- 策略引擎中的规则配置: `v-if="isAdmin"` (operator 只能看诊断结果)

**2.4** 添加分区标题 CSS 样式

**2.5** 导入新增的 Element Plus 图标

---

#### Task 3: 权限扩展 (后端) [P1]

**文件**: `backend/app/main.py`

**操作**: 在 `init_default_data()` 中扩展默认权限

**3.1** 新增权限资源域:
```python
# 新增 admin 权限
("admin", "device:read"), ("admin", "device:write"), ("admin", "device:delete"),
("admin", "gateway:read"), ("admin", "gateway:write"),
("admin", "energy:read"), ("admin", "energy:write"),
("admin", "asset:read"), ("admin", "asset:write"), ("admin", "asset:delete"),
("admin", "linkage:read"), ("admin", "linkage:write"),
("admin", "diagnosis:read"), ("admin", "diagnosis:write"),
("admin", "video:read"), ("admin", "video:write"),
("admin", "site:read"), ("admin", "site:write"),

# 新增 operator 权限
("operator", "device:read"),
("operator", "energy:read"), ("operator", "energy:write"),
("operator", "asset:read"), ("operator", "asset:write"),
("operator", "linkage:read"),
("operator", "diagnosis:read"),
("operator", "video:read"),
("operator", "site:read"),

# 新增 viewer 权限
("viewer", "device:read"),
("viewer", "energy:read"),
("viewer", "asset:read"),
("viewer", "video:read"),
("viewer", "site:read"),
```

---

#### Task 4: 前端权限加载 [P1]

**文件**: `frontend/src/stores/user.ts`

**操作**: 确保 `isAdmin` 和 `isOperator` computed 属性已正确定义（已存在，无需修改）

---

#### Task 5: 占位页面创建 [P1]

**文件**: 新建以下占位页面（使用 PlaceholderView 组件）

- `frontend/src/views/environment/temperature.vue`
- `frontend/src/views/environment/water-leak.vue`
- `frontend/src/views/environment/smoke-infrared.vue`
- `frontend/src/views/security/access-control.vue`
- `frontend/src/views/security/fire-linkage.vue`
- `frontend/src/views/topology/site-management.vue`（如不存在）

每个文件内容相同:
```vue
<template>
  <PlaceholderView />
</template>
<script setup lang="ts">
import PlaceholderView from '@/views/common/PlaceholderView.vue'
</script>
```

### Acceptance Criteria

**AC1: 路由结构正确**
- Given 用户访问系统
- When 浏览侧边栏菜单
- Then 看到三区分组（监控域/管理域/配置域），每区有分组标题
- And 所有现有页面可正常访问

**AC2: 旧路由兼容**
- Given 用户使用旧书签 `/power/monitor`
- When 访问该 URL
- Then 自动重定向到 `/energy/monitor`
- And 页面正常显示

**AC3: 角色过滤生效**
- Given viewer 角色用户登录
- When 查看侧边栏
- Then 看不到"配置域"分区（采集配置、策略引擎、系统管理）
- And 可以看到"监控域"和"管理域"所有菜单

**AC4: admin 专属菜单**
- Given admin 角色用户登录
- When 查看侧边栏
- Then 可以看到所有三个分区的全部菜单
- And "系统管理"菜单仅 admin 可见

**AC5: 无重复路由**
- Given 路由配置
- When 检查 router/index.ts
- Then diagnosis 路由只定义一次
- And 无 Vue Router 警告

**AC6: 占位页面可访问**
- Given 用户点击"温湿度监测"等新增菜单
- When 页面加载
- Then 显示"功能开发中"占位页面

## Additional Context

### Dependencies

- 无新增依赖，全部使用现有技术栈
- Element Plus 图标可能需要新增导入（如 Thermometer, Droplet 等）

### Testing Strategy

- 手动验证：逐一点击所有菜单项，确认路由跳转正确
- 手动验证：分别用 admin/operator/viewer 登录，确认菜单可见性
- 前端 typecheck: `npm run typecheck` 确保无类型错误
- 旧路由重定向：逐一测试旧 URL 是否正确跳转

### Notes

- 数据依赖链（配置顺序）: Site → Gateway → DataSource → Device → Point → Threshold → LinkagePolicy
- 系统管理员接管配置清单已在方案中定义（14 步）
- 故障影响分析不再有独立菜单入口，集成在容量管理或告警详情中
- 配电拓扑保留在供配电监控下（属于配电可视化）
- 能效报告从节能中心移入能效管理
