<!-- frontend/src/components/bigscreen/panels/RightPanel.vue -->
<template>
  <DraggablePanel
    ref="panelRef"
    title="能耗统计"
    panelId="rightPanel"
    :initialX="initialX"
    :initialY="panelState.y"
    :initialCollapsed="panelState.collapsed"
    @positionChange="handlePositionChange"
    @collapseChange="handleCollapseChange"
  >
    <div class="right-panel-content">
      <!-- 实时功率 -->
      <div class="data-section clickable" @click="navigateTo('/energy/analysis')">
        <h4>实时功率</h4>
        <div class="power-display">
          <div class="power-total">
            <DigitalFlop
              :value="store.energy.totalPower"
              :decimals="1"
              suffix="kW"
              size="large"
            />
          </div>
        </div>
        <div class="chart-container power-chart">
          <PowerDistribution
            :data="powerDistributionData"
            :roseType="'radius'"
            unit="kW"
          />
        </div>
        <div class="nav-hint">点击查看能耗分析 →</div>
      </div>

      <!-- PUE 趋势 -->
      <div class="data-section clickable" @click="navigateTo('/energy/analysis')">
        <h4>PUE 趋势 (7天)</h4>
        <div class="pue-display">
          <div class="pue-current">
            <DigitalFlop
              :value="store.energy.pue"
              :decimals="2"
              size="large"
              :showTrend="true"
              :trend="pueTrend"
            />
          </div>
          <div class="pue-status" :class="getPueClass(store.energy.pue)">
            {{ getPueLabel(store.energy.pue) }}
          </div>
        </div>
        <div class="chart-container">
          <PueTrend :data="pueHistoryData" :targetValue="1.5" />
        </div>
      </div>

      <!-- 今日用电 -->
      <div class="data-section clickable" @click="navigateTo('/energy/statistics')">
        <h4>今日用电</h4>
        <div class="energy-display">
          <div class="energy-info">
            <div class="energy-value">
              <DigitalFlop
                :value="store.energy.todayEnergy"
                :decimals="0"
                suffix="kWh"
                size="medium"
              />
            </div>
            <div class="energy-cost">
              <span class="cost-label">电费约</span>
              <DigitalFlop
                :value="store.energy.todayCost"
                :decimals="0"
                prefix="¥"
                size="small"
              />
            </div>
          </div>
        </div>
        <div class="nav-hint">点击查看能耗统计 →</div>
      </div>

      <!-- 需量状态 -->
      <div class="data-section clickable" @click="navigateTo('/energy/topology')">
        <h4>需量状态</h4>
        <div class="demand-display">
          <div class="demand-bar">
            <div
              class="demand-fill"
              :style="{ width: `${demandRatio}%` }"
              :class="{ warning: demandRatio > 75, danger: demandRatio > 90 }"
            ></div>
          </div>
          <div class="demand-info">
            <span class="demand-value">{{ currentDemand }}/{{ maxDemand }} kW</span>
            <span class="demand-percent" :class="{ warning: demandRatio > 75, danger: demandRatio > 90 }">
              {{ demandRatio }}%
            </span>
          </div>
        </div>
        <div class="nav-hint">点击查看配电拓扑 →</div>
      </div>
    </div>
  </DraggablePanel>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useBigscreenStore } from '@/stores/bigscreen'
import { DraggablePanel, DigitalFlop } from '@/components/bigscreen/ui'
import { PowerDistribution, PueTrend } from '@/components/bigscreen/charts'

const emit = defineEmits<{
  (e: 'navigate', path: string): void
}>()

const store = useBigscreenStore()
const panelRef = ref()

// 从store获取面板状态，右侧面板需要从右边计算位置
const panelState = computed(() => store.panelStates.rightPanel || { x: -300, y: 60, collapsed: false })

// 计算实际X位置（从右边）
const initialX = computed(() => {
  if (panelState.value.x < 0) {
    return window.innerWidth + panelState.value.x
  }
  return panelState.value.x
})

// 模拟 PUE 趋势数据
const pueTrend = ref(-2.1)

const pueHistoryData = computed(() => {
  const days = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
  const baseValue = store.energy.pue
  return days.map((day) => ({
    date: day,
    value: Math.round((baseValue + (Math.random() - 0.5) * 0.1) * 100) / 100
  }))
})

// 功率分布数据
const powerDistributionData = computed(() => [
  { name: 'IT负载', value: store.energy.itPower, color: '#00ccff' },
  { name: '制冷系统', value: store.energy.coolingPower, color: '#00ff88' },
  { name: '照明', value: Math.round(store.energy.totalPower * 0.05), color: '#ffaa00' },
  { name: '其他', value: Math.round(store.energy.totalPower * 0.03), color: '#9254de' }
])

// 需量数据
const currentDemand = ref(125)
const maxDemand = ref(160)

const demandRatio = computed(() => {
  if (maxDemand.value === 0) return 0
  return Math.round((currentDemand.value / maxDemand.value) * 100)
})

function handlePositionChange(data: { id: string; x: number; y: number }) {
  store.updatePanelPosition(data.id, data.x, data.y)
}

function handleCollapseChange(data: { id: string; collapsed: boolean }) {
  store.updatePanelCollapsed(data.id, data.collapsed)
}

function navigateTo(path: string) {
  emit('navigate', path)
}

function getPueClass(pue: number): string {
  if (pue < 1.4) return 'excellent'
  if (pue < 1.6) return 'good'
  if (pue < 1.8) return 'normal'
  return 'poor'
}

function getPueLabel(pue: number): string {
  if (pue < 1.4) return '优秀'
  if (pue < 1.6) return '良好'
  if (pue < 1.8) return '一般'
  return '待优化'
}

onMounted(() => {
  store.loadPanelStates()
})
</script>

<style scoped lang="scss">
.right-panel-content {
  width: 260px;
  padding: 12px;
  max-height: calc(100vh - 200px);
  overflow-y: auto;

  &::-webkit-scrollbar {
    width: 4px;
  }

  &::-webkit-scrollbar-track {
    background: rgba(255, 255, 255, 0.05);
  }

  &::-webkit-scrollbar-thumb {
    background: rgba(0, 136, 255, 0.3);
    border-radius: 2px;
  }
}

.data-section {
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);

  &:last-child {
    margin-bottom: 0;
    padding-bottom: 0;
    border-bottom: none;
  }

  &.clickable {
    cursor: pointer;
    transition: background 0.2s, transform 0.2s;
    border-radius: 6px;
    padding: 10px;
    margin: 0 -10px 12px;

    &:hover {
      background: rgba(0, 136, 255, 0.1);
      transform: translateX(-3px);

      .nav-hint {
        opacity: 1;
        color: #00ccff;
      }
    }
  }

  h4 {
    display: flex;
    align-items: center;
    margin: 0 0 10px;
    font-size: 12px;
    color: #88ccff;
    font-weight: 500;
  }
}

.nav-hint {
  margin-top: 8px;
  text-align: center;
  font-size: 10px;
  color: #556677;
  opacity: 0;
  transition: opacity 0.2s, color 0.2s;
}

.power-display {
  .power-total {
    text-align: center;
    margin-bottom: 8px;
  }
}

.chart-container {
  height: 120px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 6px;
  overflow: hidden;

  &.power-chart {
    height: 140px;
  }
}

.pue-display {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  margin-bottom: 10px;

  .pue-status {
    padding: 4px 10px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;

    &.excellent {
      background: rgba(0, 255, 136, 0.15);
      color: #00ff88;
    }
    &.good {
      background: rgba(0, 204, 255, 0.15);
      color: #00ccff;
    }
    &.normal {
      background: rgba(255, 170, 0, 0.15);
      color: #ffaa00;
    }
    &.poor {
      background: rgba(255, 77, 79, 0.15);
      color: #ff4d4f;
    }
  }
}

.energy-display {
  .energy-info {
    .energy-value {
      margin-bottom: 8px;
      text-align: center;
    }

    .energy-cost {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;

      .cost-label {
        font-size: 11px;
        color: #8899aa;
      }
    }
  }
}

.demand-display {
  .demand-bar {
    height: 8px;
    background: rgba(0, 50, 100, 0.5);
    border-radius: 4px;
    overflow: hidden;
    margin-bottom: 8px;
  }

  .demand-fill {
    height: 100%;
    background: linear-gradient(90deg, #00ff88, #00ccff);
    border-radius: 4px;
    transition: width 0.3s ease;

    &.warning {
      background: linear-gradient(90deg, #ffcc00, #ff9900);
    }
    &.danger {
      background: linear-gradient(90deg, #ff6b6b, #ff4d4f);
    }
  }

  .demand-info {
    display: flex;
    justify-content: space-between;
    font-size: 11px;

    .demand-value {
      color: #8899aa;
    }
    .demand-percent {
      color: #00ff88;
      font-weight: bold;

      &.warning { color: #ffaa00; }
      &.danger { color: #ff4d4f; }
    }
  }
}
</style>
