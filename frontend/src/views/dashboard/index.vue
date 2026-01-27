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
            <el-button :icon="Refresh" @click="refreshData">
              刷新数据
            </el-button>
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
          navigate-to="/energy/monitor"
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
              <el-button type="primary" link @click="refreshData">刷新</el-button>
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
import { ref, onMounted, onUnmounted } from 'vue'
import { Monitor, CircleCheck, Warning, Remove } from '@element-plus/icons-vue'
import { Lightning, FullScreen, Refresh, Coin } from '@element-plus/icons-vue'
import { getAllRealtimeData, getRealtimeSummary, type RealtimeData } from '@/api/modules/realtime'
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
let timer: number | null = null

onMounted(() => {
  refreshData()
  // 每10秒刷新一次
  timer = window.setInterval(refreshData, 10000)
})

onUnmounted(() => {
  if (timer) {
    clearInterval(timer)
  }
})

async function refreshData() {
  try {
    const [summaryRes, realtimeRes, alarmsRes] = await Promise.all([
      getRealtimeSummary(),
      getAllRealtimeData(),
      getActiveAlarms()
    ])
    // 映射后端字段名到前端期望的字段名
    summary.value = {
      total: summaryRes.total_points || 0,
      normal: summaryRes.online_points || 0,
      alarm: summaryRes.alarm_points || 0,
      offline: summaryRes.offline_points || 0
    }
    realtimeData.value = realtimeRes
    activeAlarms.value = alarmsRes.slice(0, 10)

    // 加载能源仪表盘数据 (V2.3)
    try {
      const energyRes = await getEnergyDashboard()
      if (energyRes.code === 0 && energyRes.data) {
        energyData.value = energyRes.data
      }
    } catch (e) {
      console.warn('能源仪表盘数据加载失败，可能API未就绪', e)
    }
  } catch (e) {
    console.error('刷新数据失败', e)
  }
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
.dashboard {
  .stat-cards {
    margin-bottom: 20px;
  }

  .quick-actions {
    margin-bottom: 20px;

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

  .stat-card {
    background: var(--bg-card);
    border-color: var(--border-color);

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

      // 科技风发光效果
      &[style*="409eff"] {
        box-shadow: 0 0 15px rgba(64, 158, 255, 0.4);
      }
      &[style*="67c23a"] {
        box-shadow: 0 0 15px rgba(82, 196, 26, 0.4);
      }
      &[style*="f56c6c"] {
        box-shadow: 0 0 15px rgba(245, 34, 45, 0.4);
      }
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
      box-shadow: var(--shadow-glow);
    }
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    color: var(--text-primary);
  }

  .chart-row {
    .el-card {
      background: var(--bg-card);
      border-color: var(--border-color);
    }
  }

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
      transition: all var(--transition-fast);

      &:hover {
        background: var(--bg-hover);
      }

      &.level-critical {
        border-color: var(--alarm-critical);
        background: rgba(255, 77, 79, 0.1);

        .alarm-title .el-icon {
          color: var(--alarm-critical);
        }
      }

      &.level-major {
        border-color: var(--alarm-major);
        background: rgba(250, 140, 22, 0.1);

        .alarm-title .el-icon {
          color: var(--alarm-major);
        }
      }

      &.level-minor {
        border-color: var(--alarm-minor);
        background: rgba(250, 173, 20, 0.1);

        .alarm-title .el-icon {
          color: var(--alarm-minor);
        }
      }

      &.level-info {
        border-color: var(--alarm-info);
        background: rgba(24, 144, 255, 0.1);

        .alarm-title .el-icon {
          color: var(--alarm-info);
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

  // V2.3: 能源统计卡片样式
  .energy-cards {
    margin-bottom: 20px;
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
