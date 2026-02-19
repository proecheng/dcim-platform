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
        <!-- 监控仪表盘 -->
        <el-menu-item index="/dashboard">
          <el-icon><Monitor /></el-icon>
          <template #title>监控仪表盘</template>
        </el-menu-item>

        <!-- 点位管理 -->
        <el-menu-item index="/devices">
          <el-icon><Cpu /></el-icon>
          <template #title>点位管理</template>
        </el-menu-item>

        <!-- 设备管理 -->
        <el-menu-item index="/device-manage">
          <el-icon><SetUp /></el-icon>
          <template #title>设备管理</template>
        </el-menu-item>

        <!-- ===== 华为6大域 ===== -->

        <!-- 域1: 供配电管理 -->
        <el-sub-menu index="/power">
          <template #title>
            <el-icon><Lightning /></el-icon>
            <span>供配电管理</span>
          </template>
          <el-menu-item index="/power/overview">
            <el-icon><DataBoard /></el-icon>
            <template #title>供配电总览</template>
          </el-menu-item>
          <el-menu-item index="/power/ups">
            <el-icon><Lightning /></el-icon>
            <template #title>UPS监控</template>
          </el-menu-item>
          <el-menu-item index="/power/battery">
            <el-icon><Coin /></el-icon>
            <template #title>电池组</template>
          </el-menu-item>
          <el-menu-item index="/power/cabinet">
            <el-icon><Grid /></el-icon>
            <template #title>配电柜</template>
          </el-menu-item>
          <el-menu-item index="/power/pdu">
            <el-icon><Menu /></el-icon>
            <template #title>机柜PDU</template>
          </el-menu-item>
          <el-menu-item index="/power/monitor">
            <el-icon><Odometer /></el-icon>
            <template #title>用电监控</template>
          </el-menu-item>
          <el-menu-item index="/power/statistics">
            <el-icon><TrendCharts /></el-icon>
            <template #title>能耗统计</template>
          </el-menu-item>
          <el-menu-item index="/power/config">
            <el-icon><Setting /></el-icon>
            <template #title>配电配置</template>
          </el-menu-item>
          <el-menu-item index="/power/topology">
            <el-icon><Share /></el-icon>
            <template #title>配电拓扑</template>
          </el-menu-item>
        </el-sub-menu>

        <!-- 域2: 制冷系统 -->
        <el-sub-menu index="/cooling">
          <template #title>
            <el-icon><IceCream /></el-icon>
            <span>制冷系统</span>
          </template>
          <el-menu-item index="/cooling/overview">
            <el-icon><DataBoard /></el-icon>
            <template #title>制冷总览</template>
          </el-menu-item>
        </el-sub-menu>

        <!-- 域3: 环境监控 -->
        <el-sub-menu index="/environment">
          <template #title>
            <el-icon><Sunny /></el-icon>
            <span>环境监控</span>
          </template>
          <el-menu-item index="/environment/overview">
            <el-icon><DataBoard /></el-icon>
            <template #title>环境总览</template>
          </el-menu-item>
        </el-sub-menu>

        <!-- 域4: 安防消防 -->
        <el-sub-menu index="/security">
          <template #title>
            <el-icon><Lock /></el-icon>
            <span>安防消防</span>
          </template>
          <el-menu-item index="/security/overview">
            <el-icon><DataBoard /></el-icon>
            <template #title>安防总览</template>
          </el-menu-item>
        </el-sub-menu>

        <!-- 域5: 基础设施 -->
        <el-sub-menu index="/infrastructure">
          <template #title>
            <el-icon><OfficeBuilding /></el-icon>
            <span>基础设施</span>
          </template>
          <el-menu-item index="/infrastructure/asset">
            <el-icon><Document /></el-icon>
            <template #title>资产台账</template>
          </el-menu-item>
          <el-menu-item index="/infrastructure/cabinet">
            <el-icon><Grid /></el-icon>
            <template #title>机柜管理</template>
          </el-menu-item>
          <el-menu-item index="/infrastructure/capacity">
            <el-icon><DataAnalysis /></el-icon>
            <template #title>容量管理</template>
          </el-menu-item>
        </el-sub-menu>

        <!-- 域6: 节能中心 -->
        <el-sub-menu index="/energy-saving">
          <template #title>
            <el-icon><Opportunity /></el-icon>
            <span>节能中心</span>
          </template>
          <el-menu-item index="/energy-saving/analysis">
            <el-icon><Opportunity /></el-icon>
            <template #title>节能分析</template>
          </el-menu-item>
          <el-menu-item index="/energy-saving/regulation">
            <el-icon><Operation /></el-icon>
            <template #title>负荷调节</template>
          </el-menu-item>
          <el-menu-item index="/energy-saving/execution">
            <el-icon><VideoPlay /></el-icon>
            <template #title>执行管理</template>
          </el-menu-item>
        </el-sub-menu>

        <!-- ===== 独立入口 ===== -->

        <!-- 告警管理 -->
        <el-menu-item index="/alarms">
          <el-icon><Bell /></el-icon>
          <template #title>告警管理</template>
        </el-menu-item>

        <!-- 历史数据 -->
        <el-menu-item index="/history">
          <el-icon><TrendCharts /></el-icon>
          <template #title>历史数据</template>
        </el-menu-item>

        <!-- 报表分析 -->
        <el-menu-item index="/reports">
          <el-icon><Document /></el-icon>
          <template #title>报表分析</template>
        </el-menu-item>

        <!-- 运维管理 -->
        <el-sub-menu index="/operation">
          <template #title>
            <el-icon><Tools /></el-icon>
            <span>运维管理</span>
          </template>
          <el-menu-item index="/operation/workorder">
            <el-icon><Tickets /></el-icon>
            <template #title>工单管理</template>
          </el-menu-item>
          <el-menu-item index="/operation/inspection">
            <el-icon><List /></el-icon>
            <template #title>巡检管理</template>
          </el-menu-item>
          <el-menu-item index="/operation/knowledge">
            <el-icon><Reading /></el-icon>
            <template #title>知识库</template>
          </el-menu-item>
        </el-sub-menu>

        <!-- 虚拟电厂 -->
        <el-sub-menu index="/vpp">
          <template #title>
            <el-icon><Connection /></el-icon>
            <span>虚拟电厂</span>
          </template>
          <el-menu-item index="/vpp/analysis">
            <el-icon><DataAnalysis /></el-icon>
            <template #title>VPP方案分析</template>
          </el-menu-item>
        </el-sub-menu>

        <!-- 系统设置 -->
        <el-menu-item index="/settings">
          <el-icon><Setting /></el-icon>
          <template #title>系统设置</template>
        </el-menu-item>
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
import {
  Monitor, Cpu, Bell, TrendCharts, Setting, Document,
  Expand, Fold, UserFilled, ArrowDown,
  Lightning, Odometer, Share, DataAnalysis,
  Grid, SetUp, Tickets, List, Reading,
  Opportunity, Operation, VideoPlay,
  IceCream, Sunny, Lock, OfficeBuilding, DataBoard, Tools, Connection,
  Coin, Menu
} from '@element-plus/icons-vue'
import { useUserStore, useAlarmStore } from '@/stores'
import { getAlarmCount } from '@/api/alarm'
import DegradationBanner from '@/components/common/DegradationBanner.vue'
import AlarmSoundToggle from '@/components/common/AlarmSoundToggle.vue'
import VideoPopup from '@/components/video/VideoPopup.vue'
import SiteSwitcher from '@/components/common/SiteSwitcher.vue'
import { useDataQuality } from '@/composables/useDataQuality'

useDataQuality()

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const alarmStore = useAlarmStore()
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
  // 获取用户信息
  if (userStore.token && !userStore.userInfo) {
    await userStore.fetchUserInfo()
  }

  // 获取告警数量
  try {
    const count = await getAlarmCount()
    alarmStore.alarmCount = count
  } catch (e) {
    console.error('获取告警数量失败', e)
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

  .logo {
    height: var(--header-height);
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
  }
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
