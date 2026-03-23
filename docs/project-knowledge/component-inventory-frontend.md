# Frontend Component Inventory — Exhaustive Scan

**Generated**: 2026-03-23 | **Scan Level**: Exhaustive | **Source**: `frontend/src/`

---

## Summary

| Category | Count |
|----------|-------|
| Views (页面) | 98 |
| Components (组件) | 90 |
| Stores (状态管理) | 10 |
| API Modules (接口) | 46 |
| Composables (组合函数) | 38 |
| Total Source Files | 487 |

---

## Views — 98 .vue files

按目录分组，对应路由模块：

| Directory | 说明 |
|-----------|------|
| alarm/ | 告警管理/列表/详情/统计/屏蔽/升级 |
| asset/ | 资产台账/机柜/生命周期/盘点 |
| bigscreen/ | 大屏展示 |
| capacity/ | 四维容量规划 |
| common/ | 公共页面(404等) |
| cooling/ | 制冷管理 |
| dashboard/ | 首页仪表盘 |
| datasource/ | 数据源管理 |
| device/ | 设备管理 |
| device-manage/ | 设备管理(扩展) |
| device-status/ | 设备状态 |
| device-template/ | 设备模板 |
| diagnosis/ | 智能诊断 |
| energy/ | 能源管理/PUE/配电/需量 |
| environment/ | 环境监控 |
| gateway/ | 网关管理 |
| history/ | 历史数据 |
| linkage/ | 告警联动 |
| login/ | 登录页 |
| operation/ | 运维管理/工单/巡检/知识库 |
| power/ | 电力管理 |
| report/ | 报表管理 |
| security/ | 安全管理 |
| settings/ | 系统设置 |
| system/ | 系统管理 |
| topology/ | 配电拓扑 |
| video/ | 视频监控 |
| vpp/ | 虚拟电厂 |

---

## Components — 90 .vue files

| Directory | Count | 说明 |
|-----------|-------|------|
| asset/ | — | 资产相关组件 |
| bigscreen/ | — | 大屏组件 (3D场景/数据面板/动画) |
| charts/ | — | ECharts 图表封装 |
| common/ | — | 通用组件 (表格/表单/弹窗/Loading) |
| demand/ | — | 需量管理组件 |
| diagnosis/ | — | 诊断可视化 (故障树/拓扑/DAG) |
| energy/ | — | 能源图表/统计组件 |
| floor-layouts/ | — | 楼层布局/机房平面图 |
| monitor/ | — | 监控面板组件 |
| proposal/ | — | 节能提案组件 |
| video/ | — | 视频播放器/摄像头预览 |

---

## Pinia Stores — 10 files

| Store | File | 说明 |
|-------|------|------|
| user | `user.ts` | 用户认证/角色/权限/Token管理 |
| app | `app.ts` | 应用状态/侧边栏/主题/站点选择 |
| alarm | `alarm.ts` | 告警列表/活跃告警/声音控制 |
| realtime | `realtime.ts` | WebSocket实时数据/点位订阅 |
| energy | `energy.ts` | 电力数据/PUE/汇总/节能建议 |
| opportunity | `opportunity.ts` | 节能机会 |
| bigscreen | `bigscreen.ts` | 大屏数据/3D场景状态 |
| degradation | `degradation.ts` | 设备劣化分析 |
| site | `site.ts` | 站点数据/多站点切换 |
| index | `index.ts` | Store 统一导出 |

---

## API Modules — 46 .ts files

| Module | 说明 |
|--------|------|
| alarm | 告警 CRUD/确认/统计 |
| asset | 资产台账/机柜/盘点 |
| auth | 登录/登出/刷新Token |
| bigscreen | 大屏数据接口 |
| capacity | 容量规划 |
| command | 控制命令/审批 |
| config | 系统配置/字典 |
| cooling | 制冷管理 |
| dataQuality | 数据质量 |
| demand | 需量分析 |
| demo | Demo模式数据 |
| device | 设备管理 |
| diagnosis | 智能诊断 |
| dispatch | 调度管理 |
| drift | 数据漂移 |
| energy | 能源管理 (最大模块) |
| fault-tree | 故障树 |
| floorMap | 楼层地图 |
| gateway | 网关管理 |
| history | 历史数据 |
| linkage | 告警联动 |
| log | 日志查询 |
| monitoring | 监控数据 |
| notification | 通知管理 |
| operation | 运维/工单/巡检 |
| opportunities | 节能机会 |
| optimization | RL优化 |
| ota | OTA升级 |
| point | 点位管理 |
| power | 电力/UPS |
| precool | 预冷调度 |
| predictiveMaintenance | 预测性维护 |
| probability-tuning | 概率调优 |
| realtime | 实时数据 |
| report | 报表 |
| shift | 负荷转移 |
| spatial | 空间管理 |
| statistics | 统计 |
| threshold | 告警阈值 |
| topologyConfig | 拓扑配置 |
| types | 公共类型定义 |
| user | 用户管理 |
| video | 视频监控 |
| vpp | 虚拟电厂 |

---

## Composables — 38 .ts files

| Composable | 说明 |
|-----------|------|
| useAlarm | 告警WebSocket + 声音通知 |
| useEnergy | 能源数据加载/轮询 |
| useRealtime | 实时数据WebSocket订阅 |
| useWebSocket | WebSocket连接管理 |
| useWebSocketManager | 多通道WebSocket统一管理 |
| usePermission | 权限检查 |
| useSiteFilter | 站点过滤器 |
| useDataQuality | 数据质量指示 |
| useTheme | 主题切换 |
| useSound | 声音控制 |
| useAutoTour | 自动导览 |
| useBigscreenData | 大屏数据 |
| useBuildingModel | 3D建筑模型 |
| useCameraAnimation | 摄像头动画 |
| useDAGValidation | DAG图验证 |
| useEntranceAnimation | 入场动画 |
| useFaultTreeEditor | 故障树编辑器 |
| useFireLinkageData | 消防联动数据 |
| useHistoryManager | 撤销/重做管理 |
| useKeyboardShortcuts | 键盘快捷键 |
| useRaycaster | 3D射线检测 |
| useSceneMode | 3D场景模式 |
| useScreenAdapt | 屏幕自适应 |
| useSmokeInfraredData | 烟感/红外数据 |
| useTemperatureData | 温度数据 |
| useThreeScene | Three.js场景管理 |
| useWaterLeakData | 漏水检测数据 |
| useAccessControlData | 门禁数据 |

### 测试文件 (composables)

| Test | 说明 |
|------|------|
| useAlarm.test | 告警composable测试 |
| useEnergy.test | 能源composable测试 |
| usePermission.test | 权限composable测试 |
| useSiteFilter.test | 站点过滤测试 |
| useDAGValidation.spec | DAG验证测试 |
| useFaultTreeEditor.spec | 故障树编辑器测试 |
| useHistoryManager.spec | 历史管理器测试 |
| environment-composables.test | 环境composable测试 |
| security-composables.test | 安全composable测试 |

---

## 技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| Vue | 3.4 | 框架 |
| TypeScript | 5.9 | 类型系统 |
| Vite | 5 | 构建工具 |
| Element Plus | 2.5 | UI组件库 |
| Pinia | 2.1 | 状态管理 |
| ECharts | 5.6 | 图表 |
| Three.js | 0.182 | 3D渲染 |
| DataV | — | 大屏数据可视化 |
| vis-network | — | 网络拓扑图 |
| unplugin-auto-import | — | API自动导入 |
