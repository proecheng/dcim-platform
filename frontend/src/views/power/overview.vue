<template>
  <div class="power-overview">
    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :span="4" v-for="card in statCards" :key="card.key">
        <el-card shadow="hover" class="stat-card" @click="navigateTo(card.route)">
          <div class="stat-content">
            <div class="stat-icon" :style="{ background: card.iconBg }">
              <el-icon :size="22"><component :is="card.icon" /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value" :class="card.valueClass">
                {{ overview[card.key] ?? '-' }}
              </div>
              <div class="stat-label">{{ card.label }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 负载 & 电池健康 -->
    <el-row :gutter="16" class="detail-row">
      <el-col :span="12">
        <el-card shadow="hover" class="detail-card">
          <template #header>
            <div class="card-header">
              <el-icon :size="18"><Odometer /></el-icon>
              <span>总负载</span>
            </div>
          </template>
          <div class="load-section">
            <div class="load-primary">
              <span class="load-value">{{ overview.total_load_kw ?? '-' }}</span>
              <span class="load-unit">kW</span>
            </div>
            <div class="load-rate">
              <span class="rate-label">平均负载率</span>
              <el-progress
                :percentage="overview.avg_load_rate ?? 0"
                :stroke-width="18"
                :color="getLoadColor(overview.avg_load_rate ?? 0)"
                :format="(p: number) => `${p.toFixed(1)}%`"
              />
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="hover" class="detail-card">
          <template #header>
            <div class="card-header">
              <el-icon :size="18"><CircleCheck /></el-icon>
              <span>电池健康</span>
            </div>
          </template>
          <div class="battery-section">
            <div class="battery-metric">
              <span class="metric-label">平均 SOH</span>
              <div class="metric-bar">
                <el-progress
                  :percentage="overview.battery_avg_soh ?? 0"
                  :stroke-width="18"
                  :color="getSohColor(overview.battery_avg_soh ?? 0)"
                  :format="(p: number) => `${p.toFixed(1)}%`"
                />
              </div>
            </div>
            <div class="battery-metric">
              <span class="metric-label">最低 SOC</span>
              <div class="metric-bar">
                <el-progress
                  :percentage="overview.battery_lowest_soc ?? 0"
                  :stroke-width="18"
                  :color="getSocColor(overview.battery_lowest_soc ?? 0)"
                  :format="(p: number) => `${p.toFixed(1)}%`"
                />
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { Odometer, CircleCheck, Monitor, Connection, Coin, Box } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { getPowerOverview, type PowerOverviewSummary } from '@/api/modules/power'

const router = useRouter()
const loading = ref(false)
const overview = ref<Partial<PowerOverviewSummary>>({})

const mockData: PowerOverviewSummary = {
  ups_total: 2,
  ups_online: 2,
  ups_offline: 0,
  ups_alarm: 0,
  battery_total: 4,
  battery_avg_soh: 95.2,
  battery_lowest_soc: 82.5,
  cabinet_total: 2,
  pdu_total: 4,
  total_load_kw: 156.8,
  avg_load_rate: 62.3
}

interface StatCard {
  key: keyof PowerOverviewSummary
  label: string
  icon: typeof Monitor
  iconBg: string
  valueClass: string
  route: string
}

const statCards: StatCard[] = [
  { key: 'ups_total', label: 'UPS总数', icon: Monitor, iconBg: 'rgba(24, 144, 255, 0.15)', valueClass: 'primary', route: '/power/ups' },
  { key: 'ups_online', label: 'UPS在线', icon: CircleCheck, iconBg: 'rgba(82, 196, 26, 0.15)', valueClass: 'success', route: '/power/ups' },
  { key: 'ups_alarm', label: 'UPS告警', icon: Connection, iconBg: 'rgba(245, 34, 45, 0.15)', valueClass: 'danger', route: '/power/ups' },
  { key: 'battery_total', label: '电池组', icon: Coin, iconBg: 'rgba(250, 173, 20, 0.15)', valueClass: 'warning', route: '/power/battery' },
  { key: 'cabinet_total', label: '配电柜', icon: Box, iconBg: 'rgba(114, 46, 209, 0.15)', valueClass: 'purple', route: '/power/cabinet' },
  { key: 'pdu_total', label: 'PDU', icon: Odometer, iconBg: 'rgba(0, 212, 255, 0.15)', valueClass: 'cyan', route: '/power/pdu' }
]

function navigateTo(route: string) {
  router.push(route)
}

function getLoadColor(rate: number): string {
  if (rate < 60) return '#52c41a'
  if (rate < 80) return '#faad14'
  return '#f5222d'
}

function getSohColor(soh: number): string {
  if (soh >= 90) return '#52c41a'
  if (soh >= 70) return '#faad14'
  return '#f5222d'
}

function getSocColor(soc: number): string {
  if (soc >= 60) return '#52c41a'
  if (soc >= 30) return '#faad14'
  return '#f5222d'
}

onMounted(async () => {
  loading.value = true
  try {
    const res = await getPowerOverview()
    if (res && typeof res === 'object') {
      overview.value = (res as Record<string, unknown>).data
        ? ((res as Record<string, unknown>).data as PowerOverviewSummary)
        : (res as PowerOverviewSummary)
    }
  } catch {
    console.warn('供配电总览API未就绪，使用模拟数据')
    overview.value = mockData
  } finally {
    loading.value = false
  }
  // 如果关键字段缺失，回退到模拟数据
  if (overview.value.ups_total === undefined) {
    overview.value = mockData
  }
})
</script>

<style scoped lang="scss">
.power-overview {
  .stat-row {
    margin-bottom: 16px;
  }

  .stat-card {
    cursor: pointer;
    transition: transform 0.2s, box-shadow 0.2s;
    background: var(--bg-card);
    border-color: var(--border-color);

    &:hover {
      transform: translateY(-2px);
      box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
    }

    .stat-content {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 4px 0;
    }

    .stat-icon {
      width: 44px;
      height: 44px;
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }

    .stat-info {
      flex: 1;
      min-width: 0;
    }

    .stat-value {
      font-size: 26px;
      font-weight: 700;
      line-height: 1.2;

      &.primary { color: var(--primary-color, #1890ff); }
      &.success { color: var(--success-color, #52c41a); }
      &.danger { color: var(--error-color, #f5222d); }
      &.warning { color: var(--warning-color, #faad14); }
      &.purple { color: #722ed1; }
      &.cyan { color: #00d4ff; }
    }

    .stat-label {
      font-size: 13px;
      color: var(--text-secondary);
      margin-top: 2px;
    }
  }

  .detail-row {
    margin-bottom: 16px;
  }

  .detail-card {
    background: var(--bg-card);
    border-color: var(--border-color);
    height: 100%;

    .card-header {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 15px;
      font-weight: 600;
      color: var(--text-primary);
    }
  }

  .load-section {
    .load-primary {
      text-align: center;
      margin-bottom: 20px;

      .load-value {
        font-size: 42px;
        font-weight: 700;
        color: var(--primary-color, #1890ff);
      }

      .load-unit {
        font-size: 16px;
        color: var(--text-secondary);
        margin-left: 4px;
      }
    }

    .load-rate {
      .rate-label {
        display: block;
        font-size: 13px;
        color: var(--text-secondary);
        margin-bottom: 8px;
      }
    }
  }

  .battery-section {
    .battery-metric {
      margin-bottom: 20px;

      &:last-child {
        margin-bottom: 0;
      }

      .metric-label {
        display: block;
        font-size: 13px;
        color: var(--text-secondary);
        margin-bottom: 8px;
      }
    }
  }
}
</style>
