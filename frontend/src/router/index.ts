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
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/dashboard/index.vue'),
        meta: { title: '监控仪表盘', icon: 'Monitor' }
      },
      {
        path: 'devices',
        name: 'Devices',
        component: () => import('@/views/device/index.vue'),
        meta: { title: '点位管理', icon: 'Cpu' }
      },
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
        path: 'settings',
        name: 'Settings',
        component: () => import('@/views/settings/index.vue'),
        meta: { title: '系统设置', icon: 'Setting' }
      },
      {
        path: 'energy',
        name: 'Energy',
        redirect: '/energy/monitor',
        meta: { title: '用电管理', icon: 'Lightning' },
        children: [
          {
            path: 'monitor',
            name: 'EnergyMonitor',
            component: () => import('@/views/energy/monitor.vue'),
            meta: { title: '用电监控', icon: 'Odometer' }
          },
          {
            path: 'statistics',
            name: 'EnergyStatistics',
            component: () => import('@/views/energy/statistics.vue'),
            meta: { title: '能耗统计', icon: 'TrendCharts' }
          },
          {
            path: 'analysis',
            name: 'EnergyAnalysis',
            component: () => import('@/views/energy/analysis.vue'),
            meta: { title: '节能中心', icon: 'Opportunity' }
          },
          {
            path: 'config',
            name: 'EnergyConfig',
            component: () => import('@/views/energy/config.vue'),
            meta: { title: '配电配置', icon: 'Setting' }
          },
          {
            path: 'topology',
            name: 'EnergyTopology',
            component: () => import('@/views/energy/topology.vue'),
            meta: { title: '配电拓扑', icon: 'Share' }
          },
          {
            path: 'regulation',
            name: 'EnergyRegulation',
            component: () => import('@/views/energy/regulation.vue'),
            meta: { title: '负荷调节', icon: 'Operation' }
          },
          {
            path: 'execution',
            name: 'EnergyExecution',
            component: () => import('@/views/energy/execution.vue'),
            meta: { title: '执行管理', icon: 'VideoPlay' }
          }
        ]
      },
      {
        path: 'asset',
        name: 'Asset',
        redirect: '/asset/list',
        meta: { title: '资产管理', icon: 'Box' },
        children: [
          {
            path: 'list',
            name: 'AssetList',
            component: () => import('@/views/asset/index.vue'),
            meta: { title: '资产台账', icon: 'Document' }
          },
          {
            path: 'cabinet',
            name: 'CabinetManage',
            component: () => import('@/views/asset/cabinet.vue'),
            meta: { title: '机柜管理', icon: 'Grid' }
          }
        ]
      },
      {
        path: 'capacity',
        name: 'Capacity',
        component: () => import('@/views/capacity/index.vue'),
        meta: { title: '容量管理' }
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
      }
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
