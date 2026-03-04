<template>
  <div class="dashboard">
    <!-- 统计卡片 -->
    <el-row :gutter="20" class="stat-cards">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" style="background: #409eff;">
            <el-icon :size="32"><Monitor /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ summary.total }}</div>
            <div class="stat-label">监控点位</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" style="background: #67c23a;">
            <el-icon :size="32"><CircleCheck /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ summary.normal }}</div>
            <div class="stat-label">正常点位</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" style="background: #f56c6c;">
            <el-icon :size="32"><Warning /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ summary.alarm }}</div>
            <div class="stat-label">告警点位</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" style="background: #909399;">
            <el-icon :size="32"><Remove /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ summary.offline }}</div>
            <div class="stat-label">离线点位</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 快捷操作栏 -->
    <el-row class="quick-actions">
      <el-col :span="24">
        <el-card shadow="hover">
          <div class="actions-content">
            <span class="actions-title">快捷操作</span>
            <el-button type="primary" :icon="FullScreen" @click="openBigscreen">
              打开数字孪生大屏
            </el-button>
            <el-button :icon="Coin" @click="showDemoLoader = true">
              演示数据
            </el-button>
            <el-button :icon="Refresh" @click="handleManualRefresh">
              刷新数据
            </el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 6大域概览卡片 -->
    <el-row :gutter="16" class="domain-cards">
      <el-col :span="4" v-for="domain in domainOverview" :key="domain.path">
        <el-card
          shadow="hover"
          class="domain-card"
          :style="{ '--domain-color': domain.color }"
          @click="$router.push(domain.path)"
        >
          <div class="domain-icon">
            <el-icon :size="28"><component :is="domain.icon" /></el-icon>
          </div>
          <div class="domain-info">
            <div class="domain-name">{{ domain.name }}</div>
            <div class="domain-stat">{{ domain.stat }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 能源统计卡片 (V2.3 Enhanced) -->
    <el-row :gutter="20" class="energy-cards" v-if="energyData">
      <el-col :span="5">
        <InteractivePowerCard
          title="实时功率"
          :value="energyData.realtime?.total_power || 0"
          unit="kW"
          :icon="Lightning"
          icon-color="#409EFF"
          :trend-data="energyData.trends?.power_1h || []"
          sparkline-color="#409EFF"
          :details="[
            { label: 'IT', value: `${energyData.realtime?.it_power?.toFixed(1) || 0} kW` },
            { label: '制冷', value: `${energyData.realtime?.cooling_power?.toFixed(1) || 0} kW` }
          ]"
          navigate-to="/power/monitor"
          tooltip="数据中心总功率消耗，包括IT设备和基础设施"
        />
      </el-col>

      <el-col :span="5">
        <PUEIndicatorCard
          :pue="energyData.efficiency?.pue"
          :target="energyData.efficiency?.pue_target"
          :trend="energyData.efficiency?.pue_trend"
          :trend-data="energyData.trends?.pue_24h || []"
          :compare-yesterday="(energyData.efficiency?.pue || 1.5) - 1.5"
        />
      </el-col>

      <el-col :span="5">
        <DemandStatusCard
          :current-demand="energyData.demand?.current_demand"
          :declared-demand="energyData.demand?.declared_demand"
          :trend-data="energyData.trends?.demand_24h || []"
          :over-declared-risk="energyData.demand?.over_declared_risk"
        />
      </el-col>

      <el-col :span="5">
        <CostCard
          :today-cost="energyData.cost?.today_cost"
          :month-cost="energyData.cost?.month_cost"
          :avg-price="energyData.cost?.avg_price"
          :peak-ratio="energyData.cost?.peak_ratio"
          :valley-ratio="energyData.cost?.valley_ratio"
          :flat-ratio="100 - (energyData.cost?.peak_ratio || 0) - (energyData.cost?.valley_ratio || 0)"
        />
      </el-col>

      <el-col :span="4">
        <SuggestionsCard
          :pending-count="energyData.suggestions?.pending_count"
          :high-priority-count="energyData.suggestions?.high_priority_count"
          :potential-saving="energyData.suggestions?.potential_saving_cost"
        />
      </el-col>
    </el-row>

    <!-- 图表和数据 -->
    <el-row :gutter="20" class="chart-row">
      <el-col :span="16">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>实时数据</span>
              <el-button type="primary" link @click="handleManualRefresh">刷新</el-button>
            </div>
          </template>
          <el-table :data="realtimeData" height="400" stripe>
            <el-table-column prop="point_code" label="点位编码" width="150" />
            <el-table-column prop="point_name" label="点位名称" width="180" />
            <el-table-column prop="point_type" label="类型" width="80">
              <template #default="{ row }">
                <el-tag :type="getTypeTagType(row.point_type)" size="small">
                  {{ row.point_type }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="当前值" width="120">
              <template #default="{ row }">
                <span>{{ row.value ?? '-' }} {{ row.unit || '' }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="getStatusTagType(row.status)" size="small">
                  {{ getStatusText(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="updated_at" label="更新时间" />
          </el-table>
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card shadow="hover" class="alarm-card">
          <template #header>
            <div class="card-header">
              <span>最新告警</span>
              <el-button type="primary" link @click="$router.push('/alarms')">查看全部</el-button>
            </div>
          </template>
          <div class="alarm-list">
            <div
              v-for="alarm in activeAlarms"
              :key="alarm.id"
              class="alarm-item"
              :class="'level-' + alarm.alarm_level"
            >
              <div class="alarm-title">
                <el-icon><Warning /></el-icon>
                <span>{{ alarm.point_name }}</span>
              </div>
              <div class="alarm-message">{{ alarm.alarm_message }}</div>
              <div class="alarm-time">{{ alarm.created_at }}</div>
            </div>
            <el-empty v-if="activeAlarms.length === 0" description="暂无告警" />
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 演示数据加载对话框 -->
    <DemoDataLoader v-model="showDemoLoader" @loaded="refreshData" @unloaded="refreshData" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, onActivated, onDeactivated, markRaw } from 'vue'
import { Monitor, CircleCheck, Warning, Remove } from '@element-plus/icons-vue'
import { Lightning, FullScreen, Refresh, Coin } from '@element-plus/icons-vue'
import { IceCream, Sunny, Lock, OfficeBuilding, Opportunity } from '@element-plus/icons-vue'
import { getAllRealtimeData, getRealtimeSummary, getDashboardData, type RealtimeData } from '@/api/modules/realtime'
import { getActiveAlarms } from '@/api/modules/alarm'
import { getEnergyDashboard, type EnergyDashboardData } from '@/api/modules/energy'
// V2.3 增强版能源卡片组件
import InteractivePowerCard from '@/components/energy/InteractivePowerCard.vue'
import PUEIndicatorCard from '@/components/energy/PUEIndicatorCard.vue'
import DemandStatusCard from '@/components/energy/DemandStatusCard.vue'
import CostCard from '@/components/energy/CostCard.vue'
import SuggestionsCard from '@/components/energy/SuggestionsCard.vue'
// 演示数据加载组件
import DemoDataLoader from '@/components/DemoDataLoader.vue'

interface AlarmItem {
  id: number
  alarm_level: string
  point_name: string
  alarm_message: string
  created_at: string
}

const summary = ref({ total: 0, normal: 0, alarm: 0, offline: 0 })
const realtimeData = ref<RealtimeData[]>([])
const activeAlarms = ref<AlarmItem[]>([])
const energyData = ref<EnergyDashboardData | null>(null)
const showDemoLoader = ref(false)
const isRefreshing = ref(false)
let timer: number | null = null
let isPageVisible = true

const DASHBOARD_REFRESH_INTERVAL_MS = 15000
const DASHBOARD_CACHE_TTL_MS = 20000
const MAX_REALTIME_ROWS = 200
const DASHBOARD_CACHE_KEY = 'dcim:dashboard:cache:v2'

interface DashboardCachePayload {
  savedAt: number
  summary: { total: number; normal: number; alarm: number; offline: number }
  realtimeData: RealtimeData[]
  activeAlarms: AlarmItem[]
  energyData: EnergyDashboardData | null
  domainStats: string[]
}

type DashboardRaw = Awaited<ReturnType<typeof getDashboardData>>
type SummaryRaw = Awaited<ReturnType<typeof getRealtimeSummary>>

function unwrapApiData<T>(payload: unknown): T {
  const maybeObj = payload as { data?: T }
  if (maybeObj && typeof maybeObj === 'object' && 'data' in maybeObj && maybeObj.data !== undefined) {
    return maybeObj.data
  }
  return payload as T
}

// 6大域概览数据
const domainOverview = ref([
  { name: '供配电', icon: markRaw(Lightning), path: '/power/overview', color: '#409EFF', stat: '运行中' },
  { name: '制冷系统', icon: markRaw(IceCream), path: '/cooling/overview', color: '#67C23A', stat: '运行中' },
  { name: '环境监控', icon: markRaw(Sunny), path: '/environment/overview', color: '#E6A23C', stat: '运行中' },
  { name: '安防消防', icon: markRaw(Lock), path: '/security/overview', color: '#F56C6C', stat: '运行中' },
  { name: '基础设施', icon: markRaw(OfficeBuilding), path: '/infrastructure/asset', color: '#909399', stat: '运行中' },
  { name: '节能中心', icon: markRaw(Opportunity), path: '/energy-saving/analysis', color: '#00D1B2', stat: '运行中' }
])

onMounted(() => {
  applyCachedDashboardData()
  refreshData({ force: true })
  startAutoRefresh()
  document.addEventListener('visibilitychange', handleVisibilityChange)
})

onActivated(() => {
  if (isPageVisible) {
    refreshData({ force: false })
    startAutoRefresh()
  }
})

onDeactivated(() => {
  stopAutoRefresh()
})

onUnmounted(() => {
  stopAutoRefresh()
  document.removeEventListener('visibilitychange', handleVisibilityChange)
})

function startAutoRefresh() {
  stopAutoRefresh()
  if (!isPageVisible) return
  timer = window.setInterval(() => {
    refreshData({ force: false })
  }, DASHBOARD_REFRESH_INTERVAL_MS)
}

function stopAutoRefresh() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}

function handleVisibilityChange() {
  isPageVisible = document.visibilityState === 'visible'
  if (isPageVisible) {
    refreshData({ force: false })
    startAutoRefresh()
  } else {
    stopAutoRefresh()
  }
}

function applyDashboardOverviewStat(dashRes: DashboardRaw) {
  const ov = dashRes?.overview
  if (!ov) return

  const alarmCount = ov.alarm_count || 0
  domainOverview.value[0].stat = ov.power != null ? `${ov.power}kW` : '运行中'
  domainOverview.value[1].stat = `${ov.ac_running || 0}台运行`
  domainOverview.value[2].stat = ov.temperature != null ? `${ov.temperature}°C` : '运行中'
  domainOverview.value[3].stat = alarmCount > 0 ? `${alarmCount}条告警` : '正常'

  const ds = dashRes.device_status || {}
  const totalDevices = Object.values(ds).reduce((sum: number, value) => sum + Number(value || 0), 0)
  domainOverview.value[4].stat = totalDevices > 0 ? `${totalDevices}台设备` : '运行中'
}

function mapSummaryData(summaryRes: SummaryRaw) {
  const raw = unwrapApiData<Record<string, unknown>>(summaryRes)

  const total = Number(raw?.total_points ?? raw?.total ?? 0)
  const normal = Number(raw?.online_points ?? raw?.normal_count ?? raw?.normal ?? 0)
  const alarm = Number(raw?.alarm_points ?? raw?.alarm_count ?? raw?.alarm ?? 0)
  const offline = Number(raw?.offline_points ?? raw?.offline_count ?? raw?.offline ?? 0)

  summary.value = {
    total,
    normal,
    alarm,
    offline
  }
}

function loadDashboardCache(): DashboardCachePayload | null {
  try {
    const cacheRaw = sessionStorage.getItem(DASHBOARD_CACHE_KEY)
    if (!cacheRaw) return null
    const cache = JSON.parse(cacheRaw) as DashboardCachePayload
    if (!cache?.savedAt) return null
    if (Date.now() - cache.savedAt > DASHBOARD_CACHE_TTL_MS) return null
    return cache
  } catch {
    return null
  }
}

function saveDashboardCache() {
  try {
    const payload: DashboardCachePayload = {
      savedAt: Date.now(),
      summary: { ...summary.value },
      realtimeData: [...realtimeData.value],
      activeAlarms: [...activeAlarms.value],
      energyData: energyData.value,
      domainStats: domainOverview.value.map(item => item.stat)
    }
    sessionStorage.setItem(DASHBOARD_CACHE_KEY, JSON.stringify(payload))
  } catch {
    // 忽略缓存写入失败，避免影响主流程
  }
}

function applyCachedDashboardData() {
  const cache = loadDashboardCache()
  if (!cache) return

  summary.value = cache.summary
  realtimeData.value = cache.realtimeData.slice(0, MAX_REALTIME_ROWS)
  activeAlarms.value = cache.activeAlarms.slice(0, 10)
  energyData.value = cache.energyData
  cache.domainStats.forEach((stat, index) => {
    if (domainOverview.value[index]) {
      domainOverview.value[index].stat = stat
    }
  })
}

async function refreshData(options: { force?: boolean } = {}) {
  const forceRefresh = options.force === true
  if (isRefreshing.value) return
  if (!forceRefresh && !isPageVisible) return

  isRefreshing.value = true
  try {
    const [summaryRes, realtimeRes, alarmsRes, dashboardRes, energyRes] = await Promise.allSettled([
      getRealtimeSummary(),
      getAllRealtimeData(),
      getActiveAlarms(),
      getDashboardData(),
      getEnergyDashboard()
    ])

    if (summaryRes.status === 'fulfilled') {
      mapSummaryData(summaryRes.value)
    }

    if (realtimeRes.status === 'fulfilled') {
      const realtimePayload = unwrapApiData<RealtimeData[]>(realtimeRes.value)
      realtimeData.value = (Array.isArray(realtimePayload) ? realtimePayload : []).slice(0, MAX_REALTIME_ROWS)
    }

    if (alarmsRes.status === 'fulfilled') {
      const alarmPayload = unwrapApiData<AlarmItem[]>(alarmsRes.value)
      activeAlarms.value = (Array.isArray(alarmPayload) ? alarmPayload : []).slice(0, 10)
    }

    if (dashboardRes.status === 'fulfilled') {
      const dashData = unwrapApiData<DashboardRaw>(dashboardRes.value)
      applyDashboardOverviewStat(dashData)

      if (summary.value.total === 0 && dashData?.overview?.total_points) {
        summary.value = {
          total: dashData.overview.total_points || 0,
          normal: dashData.overview.online_points || 0,
          alarm: dashData.overview.alarm_count || 0,
          offline: Math.max(0, (dashData.overview.total_points || 0) - (dashData.overview.online_points || 0))
        }
      }

      if (realtimeData.value.length === 0 && Array.isArray(dashData?.realtime)) {
        realtimeData.value = dashData.realtime.slice(0, MAX_REALTIME_ROWS)
      }

      if (activeAlarms.value.length === 0 && Array.isArray(dashData?.alarms)) {
        activeAlarms.value = dashData.alarms.slice(0, 10)
      }
    }

    if (energyRes.status === 'fulfilled') {
      const energyPayload = unwrapApiData<EnergyDashboardData>(energyRes.value)
      if (energyPayload) {
        energyData.value = energyPayload
      }
      const pue = energyData.value?.efficiency?.pue
      domainOverview.value[5].stat = pue != null ? `PUE ${pue.toFixed(2)}` : '运行中'
    }

    saveDashboardCache()
  } catch (e) {
    console.error('刷新数据失败', e)
  } finally {
    isRefreshing.value = false
  }
}

function handleManualRefresh() {
  refreshData({ force: true })
}

type TagType = 'success' | 'warning' | 'info' | 'primary' | 'danger'

function getTypeTagType(type: string): TagType {
  const map: Record<string, TagType> = {
    AI: 'primary',
    DI: 'success',
    AO: 'warning',
    DO: 'danger'
  }
  return map[type] || 'info'
}

function getStatusTagType(status: string): TagType {
  const map: Record<string, TagType> = {
    normal: 'success',
    alarm: 'danger',
    offline: 'info'
  }
  return map[status] || 'info'
}

function getStatusText(status: string) {
  const map: Record<string, string> = {
    normal: '正常',
    alarm: '告警',
    offline: '离线'
  }
  return map[status] || status
}

// V2.3: PUE 等级颜色
function getPueClass(pue: number | undefined) {
  if (!pue) return ''
  if (pue <= 1.4) return 'pue-excellent'
  if (pue <= 1.6) return 'pue-good'
  if (pue <= 1.8) return 'pue-normal'
  return 'pue-warning'
}

function openBigscreen() {
  window.open('/bigscreen', '_blank')
}
</script>

<style scoped lang="scss">
@use '@/styles/mixins-25d' as *;

.dashboard {
  // 使用 mixin 系统的基础设施
  @include perspective-container;

  // 统计卡片 — 使用 mixin 弧形倾斜
  .stat-cards {
    @include stat-cards-arc(4, 2deg);
    margin-bottom: 20px;
  }

  // 图表+告警行 — 使用 mixin 景深差
  .chart-row {
    @include chart-depth-split;

    .el-card {
      background: var(--bg-card);
      border-color: var(--border-color);
    }
  }

  // ============================================================
  // 快捷操作栏 — 扁平浮起（dashboard 特有）
  // ============================================================
  .quick-actions {
    margin-bottom: 20px;

    :deep(.el-card) {
      transform: translateZ(5px);
      will-change: transform;
      position: relative;
      transition: all 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94);

      &::after {
        content: '';
        position: absolute;
        bottom: 0;
        left: 10%;
        right: 10%;
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(0, 212, 255, 0.3), rgba(64, 158, 255, 0.5), rgba(0, 212, 255, 0.3), transparent);
        border-radius: 1px;
      }

      &:hover {
        transform: translateZ(8px) translateY(-2px);
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.3), 0 0 12px rgba(0, 212, 255, 0.06);
      }
    }

    .actions-content {
      display: flex;
      align-items: center;
      gap: 16px;

      .actions-title {
        font-weight: 600;
        color: var(--text-primary);
        margin-right: 8px;
      }
    }
  }

  // ============================================================
  // 统计卡片视觉样式（dashboard 特有增强）
  // ============================================================
  .stat-card {
    background: var(--bg-card);
    border-color: var(--border-color);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4), 0 0 15px rgba(0, 212, 255, 0.08);

    :deep(.el-card__body) {
      display: flex;
      align-items: center;
      gap: 20px;
    }

    .stat-icon {
      width: 64px;
      height: 64px;
      border-radius: var(--radius-lg);
      display: flex;
      align-items: center;
      justify-content: center;
      color: #fff;
      box-shadow: var(--shadow-sm);

      &[style*="409eff"] { box-shadow: 0 0 15px rgba(64, 158, 255, 0.4); }
      &[style*="67c23a"] { box-shadow: 0 0 15px rgba(82, 196, 26, 0.4); }
      &[style*="f56c6c"] { box-shadow: 0 0 15px rgba(245, 34, 45, 0.4); }
    }

    .stat-info {
      .stat-value {
        font-size: 28px;
        font-weight: bold;
        color: var(--text-primary);
      }
      .stat-label {
        font-size: 14px;
        color: var(--text-secondary);
      }
    }

    &:hover {
      border-color: var(--border-active);
      box-shadow: var(--shadow-glow), 0 12px 32px rgba(0, 0, 0, 0.5), 0 0 20px rgba(0, 212, 255, 0.12);
    }
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    color: var(--text-primary);
  }

  // ============================================================
  // 告警卡片 + 6. 告警列表项层叠卡片效果
  // ============================================================
  .alarm-card {
    background: var(--bg-card);
    border-color: var(--border-color);

    .alarm-list {
      max-height: 400px;
      overflow-y: auto;
    }

    .alarm-item {
      padding: 12px;
      border-left: 3px solid;
      margin-bottom: 10px;
      background: var(--bg-tertiary);
      border-radius: var(--radius-base);
      // 2.5D: 微倾斜 + 左侧发光
      transform: perspective(400px) rotateX(0.5deg);
      will-change: transform;
      transition: all 0.35s cubic-bezier(0.25, 0.46, 0.45, 0.94);
      position: relative;

      // 左侧发光边框效果
      &::before {
        content: '';
        position: absolute;
        left: 0;
        top: 20%;
        bottom: 20%;
        width: 3px;
        border-radius: 2px;
        opacity: 0;
        transition: opacity 0.35s ease;
      }

      &:hover {
        background: var(--bg-hover);
        // 2.5D: 弹出效果
        transform: perspective(400px) rotateX(0deg) translateX(4px) scale(1.01);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);

        &::before {
          opacity: 1;
        }
      }

      &.level-critical {
        border-color: var(--alarm-critical);
        background: rgba(255, 77, 79, 0.1);

        .alarm-title .el-icon {
          color: var(--alarm-critical);
        }

        &::before {
          background: var(--alarm-critical);
          box-shadow: 0 0 8px var(--alarm-critical);
        }
      }

      &.level-major {
        border-color: var(--alarm-major);
        background: rgba(250, 140, 22, 0.1);

        .alarm-title .el-icon {
          color: var(--alarm-major);
        }

        &::before {
          background: var(--alarm-major);
          box-shadow: 0 0 8px var(--alarm-major);
        }
      }

      &.level-minor {
        border-color: var(--alarm-minor);
        background: rgba(250, 173, 20, 0.1);

        .alarm-title .el-icon {
          color: var(--alarm-minor);
        }

        &::before {
          background: var(--alarm-minor);
          box-shadow: 0 0 8px var(--alarm-minor);
        }
      }

      &.level-info {
        border-color: var(--alarm-info);
        background: rgba(24, 144, 255, 0.1);

        .alarm-title .el-icon {
          color: var(--alarm-info);
        }

        &::before {
          background: var(--alarm-info);
          box-shadow: 0 0 8px var(--alarm-info);
        }
      }

      .alarm-title {
        display: flex;
        align-items: center;
        gap: 8px;
        font-weight: bold;
        margin-bottom: 4px;
        color: var(--text-primary);
      }

      .alarm-message {
        font-size: 13px;
        color: var(--text-secondary);
        margin-bottom: 4px;
      }

      .alarm-time {
        font-size: 12px;
        color: var(--text-placeholder);
      }
    }
  }

  // ============================================================
  // 4. 能源统计卡片行 — 层次化深度
  // ============================================================
  .energy-cards {
    margin-bottom: 20px;
    transform: perspective(1000px) rotateX(1deg);
    transform-style: preserve-3d;
    animation: slideInDepth 0.6s ease-out 0.3s both;

    // 每个 el-col 内的卡片组件 hover 抬起
    :deep(.el-col) {
      > * {
        transition: all 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94);
        will-change: transform;

        &:hover {
          transform: translateY(-4px) translateZ(8px);
          box-shadow: 0 10px 28px rgba(0, 0, 0, 0.4), 0 0 12px rgba(0, 212, 255, 0.08);
        }
      }
    }
  }

  // ============================================================
  // 3. 6大域概览卡片 — 等距排列 + 翻转效果
  // ============================================================
  .domain-cards {
    margin-bottom: 20px;
    animation: slideInDepth 0.6s ease-out 0.2s both;

    .domain-card {
      cursor: pointer;
      background: var(--bg-card);
      border-color: var(--border-color);
      // 2.5D: 默认微倾斜
      transform: perspective(600px) rotateX(2deg) translateZ(0);
      transform-style: preserve-3d;
      will-change: transform;
      transition: all 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94);
      position: relative;

      // 底部发光线
      border-bottom: 2px solid color-mix(in srgb, var(--domain-color) 40%, transparent);

      :deep(.el-card__body) {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 16px;
      }

      .domain-icon {
        width: 48px;
        height: 48px;
        border-radius: var(--radius-base);
        display: flex;
        align-items: center;
        justify-content: center;
        background: color-mix(in srgb, var(--domain-color) 15%, transparent);
        color: var(--domain-color);
        flex-shrink: 0;
      }

      .domain-info {
        min-width: 0;

        .domain-name {
          font-size: 14px;
          font-weight: 600;
          color: var(--text-primary);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .domain-stat {
          font-size: 12px;
          color: var(--text-secondary);
          margin-top: 2px;
        }
      }

      &:hover {
        border-color: var(--domain-color);
        box-shadow: 0 0 12px color-mix(in srgb, var(--domain-color) 30%, transparent),
                    0 8px 20px rgba(0, 0, 0, 0.3);
        // 2.5D: 翻转 + 抬起 + 前移
        transform: perspective(600px) rotateX(-2deg) translateY(-4px) translateZ(10px);
        border-bottom-color: var(--domain-color);
      }
    }
  }

  .energy-card {
    background: var(--bg-card);
    border-color: var(--border-color);

    :deep(.el-card__body) {
      padding: 16px;
    }

    .energy-header {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 14px;
      color: var(--text-secondary);
      margin-bottom: 12px;
    }

    .energy-main {
      display: flex;
      align-items: baseline;
      gap: 4px;
      margin-bottom: 8px;

      .energy-value {
        font-size: 28px;
        font-weight: bold;
        color: var(--text-primary);

        &.pue-excellent {
          color: var(--success-color);
          text-shadow: 0 0 10px rgba(82, 196, 26, 0.4);
        }
        &.pue-good {
          color: var(--primary-color);
          text-shadow: 0 0 10px rgba(24, 144, 255, 0.4);
        }
        &.pue-normal {
          color: var(--warning-color);
          text-shadow: 0 0 10px rgba(250, 173, 20, 0.4);
        }
        &.pue-warning {
          color: var(--error-color);
          text-shadow: 0 0 10px rgba(245, 34, 45, 0.4);
        }
      }

      .energy-unit {
        font-size: 14px;
        color: var(--text-placeholder);
      }
    }

    .energy-detail {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      font-size: 12px;
      color: var(--text-placeholder);
    }

    &.suggestion-card {
      cursor: pointer;
      transition: all var(--transition-fast);

      &:hover {
        transform: translateY(-2px);
        border-color: var(--border-active);
        box-shadow: var(--shadow-glow);
      }
    }
  }
}
</style>
