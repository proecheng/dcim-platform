import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { useUserStore } from '@/stores/user'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/login/index.vue'),
    meta: { requiresAuth: false }
  },
  {
    path: '/bigscreen',
    name: 'Bigscreen',
    component: () => import('@/views/bigscreen/index.vue'),
    meta: {
      title: '数字孪生大屏',
      fullscreen: true,
      requiresAuth: false
    }
  },
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    redirect: '/dashboard',
    children: [
      // ===== 独立入口 =====
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/dashboard/index.vue'),
        meta: { title: '监控仪表盘', icon: 'Monitor' }
      },
      // moved to AFTER linkage
      // diagnosis block moved to AFTER linkage
      {
        path: 'diagnosis',
        name: 'Diagnosis',
        redirect: '/diagnosis/results',
        meta: { title: '智能诊断', icon: 'FirstAidKit' },
        children: [
          {
            path: 'results',
            name: 'DiagnosisResults',
            component: () => import('@/views/diagnosis/results.vue'),
            meta: { title: '诊断结果', icon: 'DataAnalysis' }
          },
          {
            path: 'rules',
            name: 'DiagnosisRules',
            component: () => import('@/views/diagnosis/rules.vue'),
            meta: { title: '诊断规则', icon: 'SetUp' }
          }
        ]
      },
      {
        path: 'devices',
        name: 'Devices',
        component: () => import('@/views/device/index.vue'),
        meta: { title: '点位管理', icon: 'Cpu' }
      },
      {
        path: 'datasources',
        name: 'Datasources',
        component: () => import('@/views/datasource/index.vue'),
        meta: { title: '数据源管理', icon: 'Connection' }
      },
      {
        path: 'device-templates',
        name: 'DeviceTemplates',
        component: () => import('@/views/device-template/index.vue'),
        meta: { title: '设备模板', icon: 'Files' }
      },
      {
        path: 'device-manage',
        name: 'DeviceManage',
        component: () => import('@/views/device-manage/index.vue'),
        meta: { title: '设备管理', icon: 'SetUp' }
      },
      {
        path: 'device-manage/detail/:id',
        name: 'DeviceDetail',
        component: () => import('@/views/device-manage/detail.vue'),
        meta: { title: '设备详情', icon: 'View', hidden: true }
      },
      {
        path: 'device-status',
        name: 'DeviceStatus',
        component: () => import('@/views/device-status/index.vue'),
        meta: { title: '设备状态看板', icon: 'Odometer' }
      },

      // ===== 华为6大域 =====

      // 域1: 供配电管理
      {
        path: 'power',
        name: 'Power',
        redirect: '/power/overview',
        meta: { title: '供配电管理', icon: 'Lightning' },
        children: [
          {
            path: 'overview',
            name: 'PowerOverview',
            component: () => import('@/views/power/overview.vue'),
            meta: { title: '供配电总览', icon: 'DataBoard' }
          },
          {
            path: 'ups',
            name: 'PowerUPS',
            component: () => import('@/views/power/ups.vue'),
            meta: { title: 'UPS监控', icon: 'Lightning' }
          },
          {
            path: 'battery',
            name: 'PowerBattery',
            component: () => import('@/views/power/battery.vue'),
            meta: { title: '电池组', icon: 'Coin' }
          },
          {
            path: 'cabinet',
            name: 'PowerCabinet',
            component: () => import('@/views/power/cabinet.vue'),
            meta: { title: '配电柜', icon: 'Grid' }
          },
          {
            path: 'pdu',
            name: 'PowerPDU',
            component: () => import('@/views/power/pdu.vue'),
            meta: { title: '机柜PDU', icon: 'Menu' }
          },
          {
            path: 'monitor',
            name: 'PowerMonitor',
            component: () => import('@/views/energy/monitor.vue'),
            meta: { title: '用电监控', icon: 'Odometer' }
          },
          {
            path: 'statistics',
            name: 'PowerStatistics',
            component: () => import('@/views/energy/statistics.vue'),
            meta: { title: '能耗统计', icon: 'TrendCharts' }
          },
          {
            path: 'config',
            name: 'PowerConfig',
            component: () => import('@/views/energy/config.vue'),
            meta: { title: '配电配置', icon: 'Setting' }
          },
          {
            path: 'topology',
            name: 'PowerTopology',
            component: () => import('@/views/energy/topology.vue'),
            meta: { title: '配电拓扑', icon: 'Share' }
          }
        ]
      },

      // 域2: 制冷系统
      {
        path: 'cooling',
        name: 'Cooling',
        redirect: '/cooling/overview',
        meta: { title: '制冷系统', icon: 'IceCream' },
        children: [
          {
            path: 'overview',
            name: 'CoolingOverview',
            component: () => import('@/views/cooling/overview.vue'),
            meta: { title: '制冷总览', icon: 'DataBoard' }
          },
          {
            path: 'indoor',
            name: 'CoolingIndoor',
            component: () => import('@/views/cooling/indoor.vue'),
            meta: { title: '精密空调', icon: 'IceCream' }
          },
          {
            path: 'outdoor',
            name: 'CoolingOutdoor',
            component: () => import('@/views/cooling/outdoor.vue'),
            meta: { title: '室外机', icon: 'Sunny' }
          },
          {
            path: 'cold-aisle',
            name: 'CoolingColdAisle',
            component: () => import('@/views/cooling/cold-aisle.vue'),
            meta: { title: '冷通道', icon: 'Box' }
          },
          {
            path: 'group-control',
            name: 'CoolingGroupControl',
            component: () => import('@/views/cooling/group-control.vue'),
            meta: { title: '群控状态', icon: 'Connection' }
          }
        ]
      },

      // 域3: 环境监控
      {
        path: 'environment',
        name: 'Environment',
        redirect: '/environment/overview',
        meta: { title: '环境监控', icon: 'Sunny' },
        children: [
          {
            path: 'overview',
            name: 'EnvironmentOverview',
            component: () => import('@/views/environment/overview.vue'),
            meta: { title: '环境总览', icon: 'DataBoard' }
          }
        ]
      },

      // 域4: 安防消防
      {
        path: 'security',
        name: 'Security',
        redirect: '/security/overview',
        meta: { title: '安防消防', icon: 'Lock' },
        children: [
          {
            path: 'overview',
            name: 'SecurityOverview',
            component: () => import('@/views/security/overview.vue'),
            meta: { title: '安防总览', icon: 'DataBoard' }
          }
        ]
      },

      // 域5: 基础设施
      {
        path: 'infrastructure',
        name: 'Infrastructure',
        redirect: '/infrastructure/asset',
        meta: { title: '基础设施', icon: 'OfficeBuilding' },
        children: [
          {
            path: 'asset',
            name: 'InfraAssetList',
            component: () => import('@/views/asset/index.vue'),
            meta: { title: '资产台账', icon: 'Document' }
          },
          {
            path: 'cabinet',
            name: 'InfraCabinetManage',
            component: () => import('@/views/asset/cabinet.vue'),
            meta: { title: '机柜管理', icon: 'Grid' }
          },
          {
            path: 'capacity',
            name: 'InfraCapacity',
            component: () => import('@/views/capacity/index.vue'),
            meta: { title: '容量管理', icon: 'DataAnalysis' }
          },
          {
            path: 'spatial',
            name: 'InfraSpatial',
            component: () => import('@/views/topology/spatial.vue'),
            meta: { title: '空间拓扑', icon: 'OfficeBuilding' }
          },
          {
            path: 'power-topology',
            name: 'InfraPowerTopology',
            component: () => import('@/views/topology/power.vue'),
            meta: { title: 'PDU 相位配置', icon: 'Connection' }
          },
          {
            path: 'cooling-topology',
            name: 'CoolingTopology',
            component: () => import('@/views/topology/cooling.vue'),
            meta: { title: '制冷区域配置', icon: 'WindPower' }
          },
          {
            path: 'site-selection',
            name: 'InfraSiteSelection',
            component: () => import('@/views/topology/site-selection.vue'),
            meta: { title: '智能选址', icon: 'MapLocation' }
          },
          {
            path: 'fault-impact',
            name: 'InfraFaultImpact',
            component: () => import('@/views/topology/fault-impact.vue'),
            meta: { title: '故障影响分析', icon: 'Warning' }
          }
        ]
      },

      // 域6: 节能中心
      {
        path: 'energy-saving',
        name: 'EnergySaving',
        redirect: '/energy-saving/analysis',
        meta: { title: '节能中心', icon: 'Opportunity' },
        children: [
          {
            path: 'analysis',
            name: 'SavingAnalysis',
            component: () => import('@/views/energy/analysis.vue'),
            meta: { title: '节能分析', icon: 'Opportunity' }
          },
          {
            path: 'regulation',
            name: 'SavingRegulation',
            component: () => import('@/views/energy/regulation.vue'),
            meta: { title: '负荷调节', icon: 'Operation' }
          },
          {
            path: 'execution',
            name: 'SavingExecution',
            component: () => import('@/views/energy/execution.vue'),
            meta: { title: '执行管理', icon: 'VideoPlay' }
          },
          {
            path: 'report',
            name: 'EnergyReport',
            component: () => import('@/views/energy/report.vue'),
            meta: { title: '能效报告', icon: 'Document' }
          }
        ]
      },

      // ===== 独立入口（续） =====
      {
        path: 'alarms',
        name: 'Alarms',
        component: () => import('@/views/alarm/index.vue'),
        meta: { title: '告警管理', icon: 'Bell' }
      },
      {
        path: 'history',
        name: 'History',
        component: () => import('@/views/history/index.vue'),
        meta: { title: '历史数据', icon: 'TrendCharts' }
      },
      {
        path: 'reports',
        name: 'Reports',
        component: () => import('@/views/report/index.vue'),
        meta: { title: '报表分析', icon: 'Document' }
      },
      {
        path: 'operation',
        name: 'Operation',
        redirect: '/operation/workorder',
        meta: { title: '运维管理', icon: 'Tools' },
        children: [
          {
            path: 'workorder',
            name: 'WorkOrder',
            component: () => import('@/views/operation/workorder.vue'),
            meta: { title: '工单管理', icon: 'Tickets' }
          },
          {
            path: 'inspection',
            name: 'Inspection',
            component: () => import('@/views/operation/inspection.vue'),
            meta: { title: '巡检管理', icon: 'List' }
          },
          {
            path: 'knowledge',
            name: 'Knowledge',
            component: () => import('@/views/operation/knowledge.vue'),
            meta: { title: '知识库', icon: 'Reading' }
          }
        ]
      },
      {
        path: 'vpp',
        name: 'VPP',
        redirect: '/vpp/analysis',
        meta: { title: '虚拟电厂', icon: 'Connection' },
        children: [
          {
            path: 'analysis',
            name: 'VPPAnalysis',
            component: () => import('@/views/vpp/VPPAnalysis.vue'),
            meta: { title: 'VPP方案分析', icon: 'DataAnalysis' }
          }
        ]
      },
      {
        path: 'diagnosis',
        name: 'Diagnosis',
        redirect: '/diagnosis/results',
        meta: { title: '智能诊断', icon: 'FirstAidKit' },
        children: [
          {
            path: 'results',
            name: 'DiagnosisResults',
            component: () => import('@/views/diagnosis/results.vue'),
            meta: { title: '诊断结果', icon: 'DataAnalysis' }
          },
          {
            path: 'rules',
            name: 'DiagnosisRules',
            component: () => import('@/views/diagnosis/rules.vue'),
            meta: { title: '诊断规则', icon: 'SetUp' }
          }
        ]
      },
      {
        path: 'linkage',
        name: 'Linkage',
        redirect: '/linkage/policy',
        meta: { title: '联动管理', icon: 'Connection' },
        children: [
          {
            path: 'policy',
            name: 'LinkagePolicy',
            component: () => import('@/views/linkage/policy.vue'),
            meta: { title: '联动策略', icon: 'SetUp' }
          },
          {
            path: 'execution',
            name: 'LinkageExecution',
            component: () => import('@/views/linkage/execution.vue'),
            meta: { title: '执行日志', icon: 'Document' }
          },
          {
            path: 'recovery',
            name: 'LinkageRecovery',
            component: () => import('@/views/linkage/recovery.vue'),
            meta: { title: '联动恢复', icon: 'RefreshRight' }
          },
          {
            path: 'timeline',
            name: 'LinkageTimeline',
            component: () => import('@/views/linkage/timeline.vue'),
            meta: { title: '事件时间线', icon: 'Timer' }
          },
          {
            path: 'command',
            name: 'LinkageCommand',
            component: () => import('@/views/linkage/command.vue'),
            meta: { title: '命令管理', icon: 'Operation' }
          },
          {
            path: 'drift',
            name: 'LinkageDrift',
            component: () => import('@/views/linkage/drift.vue'),
            meta: { title: '漂移检测', icon: 'TrendCharts' }
          }
        ]
      },
      {
        path: 'video',
        name: 'VideoManagement',
        redirect: '/video/cameras',
        meta: { title: '视频监控', icon: 'VideoCamera' },
        children: [
          {
            path: 'cameras',
            name: 'VideoCameras',
            component: () => import('@/views/video/index.vue'),
            meta: { title: '摄像头管理', icon: 'Camera' }
          },
          {
            path: 'control',
            name: 'VideoControl',
            component: () => import('@/views/video/control.vue'),
            meta: { title: '视频控制', icon: 'VideoPlay' }
          },
          {
            path: 'playback',
            name: 'VideoPlayback',
            component: () => import('@/views/video/playback.vue'),
            meta: { title: '告警回放', icon: 'Timer' }
          }
        ]
      },
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('@/views/settings/index.vue'),
        meta: { title: '系统设置', icon: 'Setting' }
      },
      {
        path: 'system',
        name: 'System',
        meta: { title: '系统管理', icon: 'Setting' },
        redirect: '/system/users',
        children: [
          {
            path: 'users',
            name: 'UserManagement',
            component: () => import('@/views/system/user.vue'),
            meta: { title: '用户管理', icon: 'User' }
          },
          {
            path: 'audit-log',
            name: 'AuditLog',
            component: () => import('@/views/system/audit-log.vue'),
            meta: { title: '操作审计', icon: 'Document' }
          }
        ]
      },

      // ===== 旧路由重定向（向后兼容） =====
      { path: 'energy/monitor', redirect: '/power/monitor' },
      { path: 'energy/statistics', redirect: '/power/statistics' },
      { path: 'energy/config', redirect: '/power/config' },
      { path: 'energy/topology', redirect: '/power/topology' },
      { path: 'energy/analysis', redirect: '/energy-saving/analysis' },
      { path: 'energy/regulation', redirect: '/energy-saving/regulation' },
      { path: 'energy/execution', redirect: '/energy-saving/execution' },
      { path: 'energy', redirect: '/power/monitor' },
      { path: 'asset/list', redirect: '/infrastructure/asset' },
      { path: 'asset/cabinet', redirect: '/infrastructure/cabinet' },
      { path: 'asset', redirect: '/infrastructure/asset' },
      { path: 'capacity', name: 'CapacityRedirect', redirect: '/infrastructure/capacity' }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫
router.beforeEach((to, from, next) => {
  const userStore = useUserStore()

  if (to.meta.requiresAuth !== false && !userStore.token) {
    next('/login')
  } else {
    next()
  }
})

export default router
