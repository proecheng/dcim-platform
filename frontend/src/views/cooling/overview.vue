<template>
  <div class="cooling-overview">
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

    <!-- 温度 & 群控状态 -->
    <el-row :gutter="16" class="detail-row">
      <el-col :span="12">
        <el-card shadow="hover" class="detail-card">
          <template #header>
            <div class="card-header">
              <el-icon :size="18"><Odometer /></el-icon>
              <span>送回风温度</span>
            </div>
          </template>
          <div class="temp-section">
            <div class="temp-metric">
              <span class="metric-label">平均送风温度</span>
              <div class="metric-bar">
                <el-progress
                  :percentage="tempToPercent(overview.avg_supply_temp ?? 0)"
                  :stroke-width="18"
                  :color="getTempColor(overview.avg_supply_temp ?? 0)"
                  :format="() => `${(overview.avg_supply_temp ?? 0).toFixed(1)}°C`"
                />
              </div>
            </div>
            <div class="temp-metric">
              <span class="metric-label">平均回风温度</span>
              <div class="metric-bar">
                <el-progress
                  :percentage="tempToPercent(overview.avg_return_temp ?? 0)"
                  :stroke-width="18"
                  :color="getTempColor(overview.avg_return_temp ?? 0)"
                  :format="() => `${(overview.avg_return_temp ?? 0).toFixed(1)}°C`"
                />
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="hover" class="detail-card">
          <template #header>
            <div class="card-header">
              <el-icon :size="18"><Connection /></el-icon>
              <span>群控状态</span>
            </div>
          </template>
          <div class="group-section">
            <div class="group-metric">
              <span class="metric-label">联动群控</span>
              <div class="metric-value linked">{{ overview.group_linked ?? 0 }}</div>
            </div>
            <div class="group-metric">
              <span class="metric-label">独立运行</span>
              <div class="metric-value independent">{{ independentCount }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { IceCream, CircleCheck, SwitchButton, WarningFilled, Box, Connection, Odometer } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { getCoolingOverview, type CoolingOverviewSummary } from '@/api/modules/cooling'

const router = useRouter()
const loading = ref(false)
const overview = ref<Partial<CoolingOverviewSummary>>({})

const mockData: CoolingOverviewSummary = {
  ac_total: 4,
  ac_running: 3,
  ac_stopped: 0,
  ac_alarm: 1,
  avg_supply_temp: 19.5,
  avg_return_temp: 31.8,
  cold_aisle_total: 2,
  group_total: 2,
  group_linked: 1
}

interface StatCard {
  key: keyof CoolingOverviewSummary
  label: string
  icon: typeof IceCream
  iconBg: string
  valueClass: string
  route: string
}

const statCards: StatCard[] = [
  { key: 'ac_total', label: 'AC总数', icon: IceCream, iconBg: 'rgba(24, 144, 255, 0.15)', valueClass: 'primary', route: '/cooling/indoor' },
  { key: 'ac_running', label: '运行中', icon: CircleCheck, iconBg: 'rgba(82, 196, 26, 0.15)', valueClass: 'success', route: '/cooling/indoor' },
  { key: 'ac_stopped', label: '已停止', icon: SwitchButton, iconBg: 'rgba(144, 147, 153, 0.15)', valueClass: 'info', route: '/cooling/indoor' },
  { key: 'ac_alarm', label: '告警', icon: WarningFilled, iconBg: 'rgba(245, 34, 45, 0.15)', valueClass: 'danger', route: '/cooling/indoor' },
  { key: 'cold_aisle_total', label: '冷通道', icon: Box, iconBg: 'rgba(114, 46, 209, 0.15)', valueClass: 'purple', route: '/cooling/cold-aisle' },
  { key: 'group_total', label: '群控组', icon: Connection, iconBg: 'rgba(0, 212, 255, 0.15)', valueClass: 'cyan', route: '/cooling/group-control' },
]

/** 独立运行群控组数量 */
const independentCount = computed(() => {
  const total = overview.value.group_total ?? 0
  const linked = overview.value.group_linked ?? 0
  return total - linked
})

function navigateTo(route: string) {
  router.push(route)
}

/** 温度颜色阈值：<22°C 蓝色，22-26°C 绿色，>26°C 红色 */
function getTempColor(temp: number): string {
  if (temp < 22) return '#1890ff'
  if (temp <= 26) return '#52c41a'
  return '#f5222d'
}

/** 将温度映射为进度条百分比（0~50°C → 0~100%） */
function tempToPercent(temp: number): number {
  return Math.min(100, Math.max(0, (temp / 50) * 100))
}

onMounted(async () => {
  loading.value = true
  try {
    const res = await getCoolingOverview()
    if (res && typeof res === 'object') {
      const resAny = res as unknown as Record<string, unknown>
      overview.value = resAny.data
        ? (resAny.data as CoolingOverviewSummary)
        : (res as CoolingOverviewSummary)
    }
  } catch {
    console.warn('制冷系统总览API未就绪，使用模拟数据')
    overview.value = mockData
  } finally {
    loading.value = false
  }
})
</script>

<style scoped lang="scss">
@use '@/styles/mixins-25d' as *;

.cooling-overview {
  @include page-dashboard(6);
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
      &.info { color: var(--info-color, #909399); }
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

  .temp-section {
    .temp-metric {
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

  .group-section {
    display: flex;
    gap: 40px;
    justify-content: center;
    padding: 12px 0;

    .group-metric {
      text-align: center;

      .metric-label {
        display: block;
        font-size: 13px;
        color: var(--text-secondary);
        margin-bottom: 8px;
      }

      .metric-value {
        font-size: 36px;
        font-weight: 700;
        line-height: 1.2;

        &.linked { color: var(--primary-color, #1890ff); }
        &.independent { color: var(--info-color, #909399); }
      }
    }
  }
}
</style>
