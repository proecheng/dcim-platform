<template>
  <el-container class="main-layout">
    <!-- 侧边栏 -->
    <el-aside :width="isCollapse ? '64px' : '200px'" class="aside">
      <div class="logo">
        <el-icon :size="24"><Monitor /></el-icon>
        <span v-show="!isCollapse">算力监控</span>
      </div>
      <el-menu
        :default-active="activeMenu"
        :collapse="isCollapse"
        :router="false"
        class="dark-menu"
        @select="handleMenuSelect"
      >
        <!-- ══════ 监控域 ══════ -->
        <li v-show="!isCollapse" class="menu-group-title">监控域</li>

        <el-menu-item index="/dashboard">
          <el-icon><Monitor /></el-icon>
          <template #title>综合概览</template>
        </el-menu-item>

        <el-sub-menu index="/power">
          <template #title>
            <el-icon><Lightning /></el-icon>
            <span>供配电监控</span>
          </template>
          <el-menu-item index="/power/overview">供配电总览</el-menu-item>
          <el-menu-item index="/power/ups">UPS监控</el-menu-item>
          <el-menu-item index="/power/battery">电池组</el-menu-item>
          <el-menu-item index="/power/cabinet">配电柜</el-menu-item>
          <el-menu-item index="/power/pdu">机柜PDU</el-menu-item>
          <el-menu-item index="/power/topology">配电拓扑</el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="/cooling">
          <template #title>
            <el-icon><IceCream /></el-icon>
            <span>制冷监控</span>
          </template>
          <el-menu-item index="/cooling/overview">制冷总览</el-menu-item>
          <el-menu-item index="/cooling/indoor">精密空调</el-menu-item>
          <el-menu-item index="/cooling/outdoor">室外机</el-menu-item>
          <el-menu-item index="/cooling/cold-aisle">冷通道</el-menu-item>
          <el-menu-item index="/cooling/group-control">群控状态</el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="/environment">
          <template #title>
            <el-icon><Sunny /></el-icon>
            <span>环境监控</span>
          </template>
          <el-menu-item index="/environment/overview">环境总览</el-menu-item>
          <el-menu-item index="/environment/temperature">温湿度监测</el-menu-item>
          <el-menu-item index="/environment/water-leak">水浸检测</el-menu-item>
          <el-menu-item index="/environment/smoke-infrared">烟雾/红外检测</el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="/security">
          <template #title>
            <el-icon><Lock /></el-icon>
            <span>安防消防</span>
          </template>
          <el-menu-item index="/security/overview">安防总览</el-menu-item>
          <el-menu-item index="/security/access-control">门禁管理</el-menu-item>
          <el-sub-menu index="/security/video">
            <template #title>视频监控</template>
            <el-menu-item index="/security/video/cameras">摄像头管理</el-menu-item>
            <el-menu-item index="/security/video/control">视频控制</el-menu-item>
            <el-menu-item index="/security/video/playback">告警回放</el-menu-item>
          </el-sub-menu>
          <el-menu-item index="/security/fire-linkage">消防联动</el-menu-item>
        </el-sub-menu>

        <el-menu-item index="/alarms">
          <el-icon><Bell /></el-icon>
          <template #title>告警中心</template>
        </el-menu-item>

        <!-- ══════ 管理域 ══════ -->
        <li v-show="!isCollapse" class="menu-group-title">管理域</li>

        <el-sub-menu index="/energy">
          <template #title>
            <el-icon><Opportunity /></el-icon>
            <span>能效管理</span>
          </template>
          <el-menu-item index="/energy/monitor">用电监控</el-menu-item>
          <el-menu-item index="/energy/statistics">能耗统计</el-menu-item>
          <el-menu-item index="/energy/analysis">节能分析</el-menu-item>
          <el-menu-item index="/energy/regulation">负荷调节</el-menu-item>
          <el-menu-item index="/energy/execution">执行管理</el-menu-item>
          <el-menu-item index="/energy/report">能效报告</el-menu-item>
          <el-sub-menu index="/energy/shift">
            <template #title>负荷转移</template>
            <el-menu-item index="/energy/shift/dashboard">转移仪表盘</el-menu-item>
            <el-menu-item index="/energy/shift/list">计划列表</el-menu-item>
            <el-menu-item index="/energy/shift/create">新建计划</el-menu-item>
            <el-menu-item index="/energy/shift/opportunities">转移机会</el-menu-item>
            <el-menu-item index="/energy/shift/executions">执行记录</el-menu-item>
            <el-menu-item index="/energy/shift/cooling-config">制冷联动配置</el-menu-item>
            <el-menu-item index="/energy/shift/cooling-monitor">制冷状态监控</el-menu-item>
            <el-menu-item index="/energy/shift/constraints">约束管理</el-menu-item>
            <el-menu-item index="/energy/shift/reports">收益报表</el-menu-item>
            <el-menu-item index="/energy/shift/precool-schedule">预冷计划</el-menu-item>
            <el-menu-item index="/energy/shift/deployment">部署管理</el-menu-item>
            <el-menu-item index="/energy/shift/vpp-monitor">VPP集成监控</el-menu-item>
          </el-sub-menu>
        </el-sub-menu>

        <el-sub-menu index="/asset">
          <template #title>
            <el-icon><OfficeBuilding /></el-icon>
            <span>资产与容量</span>
          </template>
          <el-menu-item index="/asset/list">资产台账</el-menu-item>
          <el-menu-item index="/asset/cabinet">机柜管理</el-menu-item>
          <el-menu-item index="/asset/capacity">容量管理</el-menu-item>
          <el-menu-item index="/asset/spatial">空间拓扑</el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="/operation">
          <template #title>
            <el-icon><Tools /></el-icon>
            <span>运维管理</span>
          </template>
          <el-menu-item index="/operation/workorder">工单管理</el-menu-item>
          <el-menu-item index="/operation/inspection">巡检管理</el-menu-item>
          <el-menu-item index="/operation/knowledge">知识库</el-menu-item>
          <el-menu-item index="/operation/reports">报表分析</el-menu-item>
          <el-menu-item index="/operation/history">历史数据</el-menu-item>
          <el-menu-item index="/operation/predictive">预测性维护</el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="/vpp">
          <template #title>
            <el-icon><Connection /></el-icon>
            <span>虚拟电厂</span>
          </template>
          <el-menu-item index="/vpp/analysis">VPP方案分析</el-menu-item>
        </el-sub-menu>

        <!-- ══════ 配置域 ══════ -->
        <template v-if="isOperator">
          <li v-show="!isCollapse" class="menu-group-title">配置域</li>

          <el-sub-menu index="/collection">
            <template #title>
              <el-icon><Connection /></el-icon>
              <span>采集配置</span>
            </template>
            <el-menu-item index="/collection/device-manage">设备管理</el-menu-item>
            <el-menu-item index="/collection/device-status">设备状态看板</el-menu-item>
            <el-menu-item index="/collection/devices">点位管理</el-menu-item>
            <el-menu-item index="/collection/datasources">数据源管理</el-menu-item>
            <el-menu-item index="/collection/device-templates">设备模板</el-menu-item>
            <el-menu-item index="/collection/power-config">配电配置</el-menu-item>
            <el-menu-item index="/collection/gateway">网关管理</el-menu-item>
            <el-menu-item index="/collection/drift">漂移检测</el-menu-item>
          </el-sub-menu>

          <el-sub-menu index="/strategy">
            <template #title>
              <el-icon><SetUp /></el-icon>
              <span>策略引擎</span>
            </template>
            <el-sub-menu v-if="isAdmin" index="/strategy/alarm-rules">
              <template #title>告警规则</template>
              <el-menu-item index="/strategy/alarm-rules/thresholds">阈值配置</el-menu-item>
              <el-menu-item index="/strategy/alarm-rules/compound">复合规则</el-menu-item>
              <el-menu-item index="/strategy/alarm-rules/escalation">升级规则</el-menu-item>
              <el-menu-item index="/strategy/alarm-rules/shield">告警屏蔽</el-menu-item>
            </el-sub-menu>
            <el-sub-menu index="/strategy/linkage">
              <template #title>联动策略</template>
              <el-menu-item index="/strategy/linkage/policy">策略管理</el-menu-item>
              <el-menu-item index="/strategy/linkage/execution">执行日志</el-menu-item>
              <el-menu-item index="/strategy/linkage/recovery">联动恢复</el-menu-item>
              <el-menu-item index="/strategy/linkage/timeline">事件时间线</el-menu-item>
              <el-menu-item index="/strategy/linkage/command">命令管理</el-menu-item>
            </el-sub-menu>
            <el-sub-menu index="/strategy/diagnosis">
              <template #title>智能诊断</template>
              <el-menu-item index="/strategy/diagnosis/results">诊断结果</el-menu-item>
              <el-menu-item v-if="isAdmin" index="/strategy/diagnosis/rules">诊断规则</el-menu-item>
              <el-menu-item index="/strategy/diagnosis/reports">误诊报告</el-menu-item>
              <el-menu-item index="/strategy/diagnosis/time-window-tuning">时间窗口调参</el-menu-item>
              <el-menu-item index="/strategy/diagnosis/probability-tuning">概率调参</el-menu-item>
            </el-sub-menu>
          </el-sub-menu>

          <el-sub-menu v-if="isAdmin" index="/system">
            <template #title>
              <el-icon><Setting /></el-icon>
              <span>系统管理</span>
            </template>
            <el-menu-item index="/system/users">用户管理</el-menu-item>
            <el-menu-item index="/system/sites">站点管理</el-menu-item>
            <el-menu-item index="/system/audit-log">操作审计</el-menu-item>
            <el-menu-item index="/system/notification">通知管理</el-menu-item>
            <el-menu-item index="/system/settings">系统设置</el-menu-item>
            <el-menu-item index="/system/site-selection">智能选址</el-menu-item>
          </el-sub-menu>
        </template>
      </el-menu>
    </el-aside>

    <el-container>
      <!-- 顶部栏 -->
      <el-header class="header">
        <div class="header-left">
          <el-icon
            :size="20"
            class="collapse-btn"
            @click="isCollapse = !isCollapse"
          >
            <component :is="isCollapse ? 'Expand' : 'Fold'" />
          </el-icon>
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item>{{ $route.meta.title }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>

        <div class="header-right">
          <!-- 站点切换 -->
          <SiteSwitcher />

          <!-- 告警声音开关 -->
          <AlarmSoundToggle />

          <!-- 告警提示 -->
          <el-badge :value="alarmStore.alarmCount.total" :max="99" class="alarm-badge">
            <el-button :icon="Bell" circle @click="$router.push('/alarms')" />
          </el-badge>

          <!-- 用户信息 -->
          <el-dropdown @command="handleCommand">
            <span class="user-info">
              <el-avatar :size="32" :icon="UserFilled" />
              <span class="username">{{ userStore.userInfo?.username }}</span>
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="password">修改密码</el-dropdown-item>
                <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <!-- 主内容区 -->
      <el-main class="main">
        <DegradationBanner />
        <router-view />
        <VideoPopup ref="videoPopupRef" />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, provide } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useWebSocketManager } from '@/composables/useWebSocketManager'
import {
  Monitor,
  Bell,
  Setting,
  UserFilled,
  ArrowDown,
  Lightning,
  SetUp,
  Opportunity,
  IceCream,
  Sunny,
  Lock,
  OfficeBuilding,
  Tools,
  Connection
} from '@element-plus/icons-vue'
import { storeToRefs } from 'pinia'
import { useUserStore, useAlarmStore, useAppStore } from '@/stores'
import DegradationBanner from '@/components/common/DegradationBanner.vue'
import AlarmSoundToggle from '@/components/common/AlarmSoundToggle.vue'
import VideoPopup from '@/components/video/VideoPopup.vue'
import SiteSwitcher from '@/components/common/SiteSwitcher.vue'
import { useDataQuality } from '@/composables/useDataQuality'
import { useRealtime } from '@/composables/useRealtime'

useDataQuality()
useRealtime()

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const { isAdmin, isOperator } = storeToRefs(userStore)
const alarmStore = useAlarmStore()
const appStore = useAppStore()
const isCollapse = ref(false)
const videoPopupRef = ref<InstanceType<typeof VideoPopup>>()

// 提供视频弹窗引用给子组件
provide('videoPopup', videoPopupRef)

// 当前激活的菜单项
const activeMenu = computed(() => route.path)

// 处理菜单选择 - 优化后的轻量级路由跳转
async function handleMenuSelect(index: string) {
  if (index === route.path) return // 已经在当前页面

  try {
    await router.push(index)
  } catch (e) {
    console.error('路由跳转失败', e)
  }
}

onMounted(async () => {
  // 初始化应用设置（包含 localStorage 迁移逻辑）
  appStore.initFromStorage()

  // 初始化 WebSocket 管理器，预连接常用通道
  const wsManager = useWebSocketManager()
  wsManager.connect('alarms')
  wsManager.connect('realtime')

  // 获取用户信息
  if (userStore.token && !userStore.userInfo) {
    await userStore.fetchUserInfo()
  }

  // 通过 AlarmStore 统一加载告警数据
  try {
    await alarmStore.fetchActiveAlarms()
  } catch (e) {
    console.error('获取告警数据失败', e)
  }
})

function handleCommand(command: string) {
  if (command === 'logout') {
    userStore.doLogout()
    router.push('/login')
  } else if (command === 'password') {
    // 打开修改密码对话框
  }
}
</script>

<style scoped lang="scss">
.main-layout {
  height: 100vh;
  background: var(--bg-primary);
}

.aside {
  background: var(--bg-secondary);
  transition: width 0.3s;
  overflow: hidden;
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;

  .logo {
    height: var(--header-height);
    min-height: var(--header-height);
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    color: var(--accent-color);
    font-size: 16px;
    font-weight: bold;
    border-bottom: 1px solid var(--border-color);
    text-shadow: 0 0 10px var(--accent-glow);

    .el-icon {
      color: var(--accent-color);
    }
  }

  .dark-menu {
    border-right: none;
    background-color: transparent;
    flex: 1;
    overflow-y: auto;
    overflow-x: hidden;

    &::-webkit-scrollbar {
      width: 4px;
    }

    &::-webkit-scrollbar-thumb {
      background: var(--border-color);
      border-radius: 2px;
    }

    &::-webkit-scrollbar-track {
      background: transparent;
    }
  }
}

.menu-group-title {
  padding: 12px 20px 4px;
  font-size: 11px;
  font-weight: 600;
  color: var(--el-text-color-placeholder);
  text-transform: uppercase;
  letter-spacing: 1px;
  list-style: none;
  user-select: none;
}

.header {
  background: var(--bg-secondary);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  border-bottom: 1px solid var(--border-color);
  height: var(--header-height);

  .header-left {
    display: flex;
    align-items: center;
    gap: 16px;

    .collapse-btn {
      cursor: pointer;
      color: var(--text-secondary);
      transition: color var(--transition-fast);

      &:hover {
        color: var(--accent-color);
      }
    }
  }

  .header-right {
    display: flex;
    align-items: center;
    gap: 20px;

    .alarm-badge {
      margin-right: 10px;

      :deep(.el-badge__content) {
        background-color: var(--alarm-critical);
      }
    }

    .user-info {
      display: flex;
      align-items: center;
      gap: 8px;
      cursor: pointer;
      padding: 4px 8px;
      border-radius: var(--radius-base);
      transition: background-color var(--transition-fast);

      &:hover {
        background-color: var(--bg-hover);
      }

      .username {
        color: var(--text-regular);
      }

      .el-icon {
        color: var(--text-secondary);
      }
    }
  }
}

.main {
  background: var(--bg-primary);
  padding: 20px;
  overflow-y: auto;
}

// 头部按钮深色样式
:deep(.header-right .el-button) {
  background-color: transparent;
  border-color: var(--border-color);
  color: var(--text-secondary);

  &:hover {
    background-color: var(--bg-hover);
    border-color: var(--primary-color);
    color: var(--primary-color);
  }
}
</style>
