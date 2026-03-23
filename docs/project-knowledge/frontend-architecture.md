# 前端架构文档 - 算力中心智能监控系统 (DCIM)

## 技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| Vue | 3.4.15 | UI 框架 (Composition API) |
| TypeScript | 5.9.3 | 类型系统 |
| Vite | 5.0.11 | 构建工具 |
| Pinia | 2.1.7 | 状态管理 |
| Vue Router | 4.2.5 | 路由 |
| Element Plus | 2.5.3 | UI 组件库 |
| ECharts | 5.6.0 | 图表可视化 |
| Three.js | 0.182.0 | 3D 渲染 |
| Axios | 1.6.5 | HTTP 客户端 |
| DataV Vue3 | 1.7.4 | 大屏组件 |
| GSAP | 3.14.2 | 动画库 |
| Day.js | 1.11.10 | 日期处理 |

## 应用分层架构

```
┌─────────────────────────────────────┐
│      Views (98个页面视图)             │
│  监控、告警、能源、资产、运维等       │
└─────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────┐
│   Components (90个业务组件)           │
│  通用、图表、大屏、能源、楼层等       │
└─────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────┐
│   Composables (19个组合式函数)        │
│  WebSocket、权限、能源、大屏等        │
└─────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────┐
│   Stores (7个Pinia存储模块)           │
│  用户、应用、告警、实时、能源等       │
└─────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────┐
│   API Layer (18个API模块)             │
│  认证、实时、告警、能源等             │
└─────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────┐
│   Transport Layer                    │
│  Axios HTTP + WebSocket              │
└─────────────────────────────────────┘
```

## 路由结构

### 核心页面

| 路径 | 视图文件 | 功能 |
|------|----------|------|
| `/login` | views/login/index.vue | 用户登录 |
| `/bigscreen` | views/bigscreen/index.vue | 数字孪生大屏 |
| `/dashboard` | views/dashboard/index.vue | 监控仪表盘 |
| `/devices` | views/device/index.vue | 点位管理 |
| `/alarms` | views/alarm/index.vue | 告警管理 |
| `/history` | views/history/index.vue | 历史数据 |
| `/reports` | views/report/index.vue | 报表分析 |
| `/settings` | views/settings/index.vue | 系统设置 |
| `/capacity` | views/capacity/index.vue | 容量管理 |

### 能源管理 (7个页面)

| 路径 | 视图文件 | 功能 |
|------|----------|------|
| `/energy/monitor` | views/energy/monitor.vue | 实时监控 |
| `/energy/statistics` | views/energy/statistics.vue | 能耗统计 |
| `/energy/analysis` | views/energy/analysis.vue | 节能中心 |
| `/energy/config` | views/energy/config.vue | 配电配置 |
| `/energy/topology` | views/energy/topology.vue | 配电拓扑 |
| `/energy/regulation` | views/energy/regulation.vue | 负荷调节 |
| `/energy/execution` | views/energy/execution.vue | 执行管理 |

### 资产与运维

| 路径 | 视图文件 | 功能 |
|------|----------|------|
| `/asset/list` | views/asset/index.vue | 资产台账 |
| `/asset/cabinet` | views/asset/cabinet.vue | 机柜管理 |
| `/operation/workorder` | views/operation/workorder.vue | 工单管理 |
| `/operation/inspection` | views/operation/inspection.vue | 巡检管理 |
| `/operation/knowledge` | views/operation/knowledge.vue | 知识库 |
| `/vpp/analysis` | views/vpp/VPPAnalysis.vue | VPP分析 |

## 状态管理 (Pinia Stores)

### 7个存储模块

| Store | 文件 | 数据来源 | 职责 |
|-------|------|----------|------|
| userStore | stores/user.ts | 登录 API | 用户信息、Token、权限 |
| appStore | stores/app.ts | 本地 | 应用设置（侧边栏、主题） |
| alarmStore | stores/alarm.ts | WebSocket + API | 告警列表、统计 |
| realtimeStore | stores/realtime.ts | WebSocket + API | 实时点位数据 |
| energyStore | stores/energy.ts | API | 能源数据 (功率/PUE/能耗) |
| opportunityStore | stores/opportunity.ts | API | 节能机会 (V2.5) |
| bigscreenStore | stores/bigscreen.ts | API + WebSocket | 大屏场景状态 |

### 认证状态流

```
登录 → userStore.doLogin()
  ├── 保存 token 到 localStorage
  ├── fetchUserInfo() → 用户信息
  └── fetchPermissions() → 权限列表

页面刷新 → initFromStorage()
  └── 从 localStorage 恢复 token

登出 → userStore.logout()
  ├── 清除 localStorage
  └── 重置所有 store
```

## API 层

### HTTP 客户端 (request.ts)

```typescript
const request = axios.create({
    baseURL: '/api/v1',
    timeout: 10000
});

// 请求拦截 - 自动添加 JWT Token
request.interceptors.request.use(config => {
    const token = useUserStore().token;
    if (token) config.headers.Authorization = `Bearer ${token}`;
    return config;
});

// 响应拦截 - 错误处理
request.interceptors.response.use(
    response => response,
    error => {
        if (error.response?.status === 401) {
            userStore.logout();
            router.push('/login');
        }
        ElMessage.error(error.response?.data?.detail || '请求失败');
        return Promise.reject(error);
    }
);
```

### 18个 API 模块

| 模块 | 文件 | 主要方法 |
|------|------|----------|
| auth | modules/auth.ts | login, logout, refreshToken, getUserInfo |
| user | modules/user.ts | getUsers, createUser, updateUser, deleteUser |
| device | modules/device.ts | getDevices, createDevice, updateDevice |
| point | modules/point.ts | getPoints, createPoint, updatePoint |
| realtime | modules/realtime.ts | getRealtimeData, getRealtimeSummary |
| alarm | modules/alarm.ts | getAlarms, acknowledgeAlarm, resolveAlarm |
| history | modules/history.ts | getHistory, exportHistory |
| energy | modules/energy.ts | 2240行，涵盖完整能源管理 API |
| demand | modules/demand.ts | getDemandAnalysis, getDemand15Min |
| dispatch | modules/dispatch.ts | getSchedules, createSchedule |
| optimization | modules/optimization.ts | getResults, runOptimization |
| opportunities | modules/opportunities.ts | getOpportunities, createPlan |
| config | modules/config.ts | getConfig, updateConfig |
| report | modules/report.ts | getReports, exportReport |
| log | modules/log.ts | getOperationLogs, getSystemLogs |
| statistics | modules/statistics.ts | getSystemStats |
| threshold | modules/threshold.ts | getThresholds, updateThreshold |
| vpp | modules/vpp.ts | getVPPAnalysis, getVPPConfig |

## WebSocket 通信

### 客户端封装 (websocket.ts)

```typescript
class WebSocketClient {
    // 核心功能
    connect(): void
    close(): void
    send(data: any): void

    // 订阅模式
    subscribe(options: SubscribeOptions): void
    unsubscribe(channels?: string[]): void

    // 事件路由
    on(type: string, handler: MessageHandler): void
    off(type: string, handler?: MessageHandler): void

    // 特性
    // - 自动重连 (3秒间隔，最多10次)
    // - 心跳检测 (30秒间隔)
    // - 按 message.type 分发
}

// 预创建实例
const realtimeWs = new WebSocketClient({ url: '/ws/realtime' })
const alarmWs = new WebSocketClient({ url: '/ws/alarms' })
const systemWs = new WebSocketClient({ url: '/ws/system' })
```

## 组合式函数 (Composables)

### 实时数据 - useRealtime

```typescript
function useRealtime(options?) {
    return {
        realtimeData, summary, loading, error,
        alarmPoints, offlinePoints, isConnected,
        fetchRealtimeData(), fetchSummary(),
        startPolling(interval?), stopPolling(),
        getPointData(pointId), getDataByType(type)
    }
}
// WebSocket + 轮询混合模式
// WebSocket 连接时减少轮询频率
// 组件卸载时自动清理
```

### 告警管理 - useAlarm

```typescript
function useAlarm(options?) {
    return {
        activeAlarms, alarmCount, loading,
        criticalAlarms, majorAlarms, minorAlarms,
        fetchActiveAlarms(), fetchAlarmCount(),
        ackAlarm(id, remark?), resolveAlarm(id, remark?),
        batchAck(ids[], remark?)
    }
}
// 自动播放告警声音（级别映射）
// Element Plus 通知弹窗
// 紧急告警循环播放声音
```

### 权限控制 - usePermission

```typescript
function usePermission() {
    return {
        hasPermission(permission), hasRole(role),
        isAdmin, isOperator, isViewer,
        canReadUsers, canWriteUsers, canDeleteUsers,
        canReadPoints, canWritePoints, canDeletePoints,
        canReadAlarms, canWriteAlarms, canAckAlarms,
        canReadConfig, canWriteConfig,
        canReadReports, canWriteReports
    }
}
```

### 能源管理 - useEnergy

```typescript
function useEnergy() {
    return {
        loading, error, energyStore,
        loadRealtimePower(), loadPUE(), loadPUETrend(),
        loadEnergySummary(), loadEnergyTrend(),
        loadSuggestions(), loadSavingPotential(),
        loadAllData(),  // 并发加载所有
        startPolling(5000), stopPolling(),
        formatPower(), formatEnergy(), formatCost(), formatPUE(),
        getPUELevel(pue), getLoadRateStatus(rate)
    }
}
```

### 音频播放 - useSound

```typescript
function useSound() {
    return {
        play, stop, pause, resume,
        setVolume, toggleMute,
        playAlarm(level),  // critical/major/minor/info
        playNotification()
    }
}
// 告警声音: critical → 循环播放, major → 一次, minor → 一次
```

### 大屏相关 (8个)

| 函数 | 文件 | 功能 |
|------|------|------|
| useThreeScene | bigscreen/useThreeScene.ts | Three.js 场景初始化 |
| useRaycaster | bigscreen/useRaycaster.ts | 鼠标拾取/点击检测 |
| useCameraAnimation | bigscreen/useCameraAnimation.ts | 相机动画 |
| useSceneMode | bigscreen/useSceneMode.ts | 场景模式切换 |
| useAutoTour | bigscreen/useAutoTour.ts | 自动巡视 |
| useBigscreenData | bigscreen/useBigscreenData.ts | 实时数据加载 |
| useScreenAdapt | bigscreen/useScreenAdapt.ts | 屏幕自适应 |
| useTheme | bigscreen/useTheme.ts | 大屏主题 |

## 组件库 (69个组件)

### 通用组件 (components/common/)

| 组件 | 功能 |
|------|------|
| DataTable.vue | 数据表格（分页、排序、搜索） |
| DateRangePicker.vue | 日期范围选择器 |
| ConfirmDialog.vue | 确认对话框 |
| ExportButton.vue | 导出按钮 |
| SearchForm.vue | 搜索表单 |
| StatusTag.vue | 状态标签 |

### 图表组件 (components/charts/)

| 组件 | 基于 | 用途 |
|------|------|------|
| LineChart.vue | ECharts | 折线图 |
| BarChart.vue | ECharts | 柱状图 |
| PieChart.vue | ECharts | 饼图 |
| GaugeChart.vue | ECharts | 仪表盘 |
| RealtimeChart.vue | ECharts | 实时曲线 |
| Sparkline.vue | ECharts | 迷你图表 |

### 监控组件 (components/monitor/)

PointCard.vue, ValueDisplay.vue, AlarmBadge.vue, StatusPanel.vue

### 能源组件 (components/energy/ - 24个)

InteractivePowerCard, PUEIndicatorCard, DemandDashboard, DemandStatusCard,
DeviceList, DevicePowerCurveChart, DeviceShiftDetailDrawer, DispatchConfig,
EnergySuggestionCard, ExecutionPlanDialog, LoadComparisonChart,
OptimizationOverview, OptimizationReport, ParameterAdjustment,
PowerCard, PUEGauge, ScheduleDashboard, ShiftPlanBuilder,
SuggestionDetailDrawer, SuggestionOverview, SuggestionsCard, CostCard,
CalculationDetails

### 大屏组件 (components/bigscreen/ - 30+)

**核心 3D:**
- ThreeScene.vue - Three.js 场景容器
- DataCenterModel.vue - 数据中心 3D 模型
- HeatmapOverlay.vue - 热力图图层

**UI 面板:**
- DeviceDetailPanel.vue, ContextMenu.vue, DigitalFlop.vue
- DraggablePanel.vue, ThemeSelector.vue

**图表:**
- BaseChart.vue, TemperatureTrend.vue, PowerDistribution.vue
- PueTrend.vue, GaugeChart.vue

**楼层:**
- FloorB1Layout.vue, FloorF1Layout.vue, FloorF2Layout.vue, FloorF3Layout.vue

## 样式系统

### 设计令牌 (CSS Variables)

```scss
// 背景色
--bg-primary: #0a0a1a;
--bg-secondary: #111429;
--bg-hover: #1a2a4a;

// 文字色
--text-primary: #ffffff;
--text-regular: rgba(255, 255, 255, 0.85);
--text-secondary: rgba(255, 255, 255, 0.65);

// 主题色
--primary-color: #1890ff;
--accent-color: #00d4ff;

// 告警色
--alarm-critical: #f5222d;
--alarm-warning: #e6a23c;
--alarm-info: #409eff;
```

### 主题系统

| 主题 | 文件 | 风格 |
|------|------|------|
| tech-blue | config/themes/tech-blue.ts | 科技蓝 |
| wireframe | config/themes/wireframe.ts | 线框 |
| realistic | config/themes/realistic.ts | 逼真 |
| night | config/themes/night.ts | 夜间 |

### ECharts 深色科技风主题

- 10种调色盘颜色
- 深蓝背景提示框
- 平滑曲线 + 圆形标记
- 多色渐变仪表盘
- 5种渐变预设 (primary/accent/success/warning/error)

## 布局系统

### MainLayout.vue

```
<el-container>
  <el-aside width="200px|64px">     ← 可折叠侧边栏
    Logo + 应用名
    el-menu (导航菜单)
      ├── 监控仪表盘
      ├── 点位管理
      ├── 告警管理
      ├── 历史数据
      ├── 报表分析
      ├── 系统设置
      ├── 用电管理 (子菜单 ×7)
      ├── 资产管理 (子菜单 ×2)
      ├── 容量管理
      └── 运维管理 (子菜单 ×3)

  <el-container>
    <el-header>               ← 顶部栏
      折叠按钮 + 面包屑
      告警徽章 + 用户菜单
    </el-header>
    <el-main>                 ← 主内容区
      <router-view />
    </el-main>
  </el-container>
</el-container>
```

## 构建配置

### Vite 配置

```typescript
// vite.config.ts
export default defineConfig({
    server: {
        port: 3000,
        host: '0.0.0.0',
        proxy: {
            '/api': { target: 'http://localhost:8080' },
            '/ws': { target: 'ws://localhost:8080', ws: true }
        }
    },
    plugins: [
        vue(),
        AutoImport({ resolvers: [ElementPlusResolver()] }),
        Components({ resolvers: [ElementPlusResolver()] })
    ]
});
```

### 构建命令

```bash
npm run dev          # 开发服务器 (端口3000)
npm run build        # 生产构建
npm run build:check  # 类型检查 + 构建
npm run typecheck    # 类型检查
```

## 关键业务流程

### 认证流程

```
用户输入 → login API (OAuth2 表单) → JWT Token
  → localStorage 持久化
  → fetchUserInfo + fetchPermissions
  → 路由守卫验证
  → 所有请求自动携带 Bearer Token
  → 401 → 清除 Token + 跳转登录
```

### 能源数据加载

```
页面 onMounted → useEnergy().loadAllData()
  → 并发: getRealtimePower + getPUE + getSuggestions + ...
  → Pinia 状态更新 → UI 重渲染
  → startPolling(5000)
  → 尝试 WebSocket 连接
    ├── 成功 → 订阅 /ws/realtime，停止轮询
    └── 失败 → 继续 HTTP 轮询
  → 页面 onUnmounted → stopPolling + disconnect
```

### 告警处理

```
WebSocket /ws/alarms → useAlarm() 收到消息
  → critical: 循环播放告警音 + 不自动关闭通知
  → major: 一次告警音 + 5秒自动关闭通知
  → minor: 仅显示通知
  → 用户操作: 确认/解决/批量确认
  → 所有告警解决 → 停止声音
```

## 关键统计

| 指标 | 数量 |
|------|------|
| 页面视图 | 23 |
| 组件 | 69 |
| 组合式函数 | 19 |
| Pinia Store | 7 |
| API 模块 | 18 |
| Three.js 工具 | 7 |
| 主题 | 4 |
| 版本迭代 | V2.8 |

---

*最后更新: 2026-02-01*
