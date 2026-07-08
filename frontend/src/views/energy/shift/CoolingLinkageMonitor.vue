<template>
  <div class="cooling-linkage-monitor">
    <el-page-header @back="$router.back()" title="返回">
      <template #content>
        <span>制冷联动状态监控</span>
      </template>
    </el-page-header>

    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="制冷总功率" :value="status.total_cooling_power || 0" suffix="kW" :precision="1" />
          <div style="margin-top: 10px; font-size: 12px; color: #909399">
            目标: {{ config.max_cooling_power || 0 }} kW
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="当前 COP" :value="status.current_cop || 0" :precision="2" />
          <div style="margin-top: 10px; font-size: 12px" :style="{ color: getCOPColor(status.current_cop) }">
            目标: {{ config.target_cop || 0 }} ({{ getCOPStatus(status.current_cop) }})
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="供水温度" :value="status.supply_temp || 0" suffix="°C" :precision="1" />
          <div style="margin-top: 10px; font-size: 12px" :style="{ color: getTempColor(status.supply_temp, 'supply') }">
            目标: {{ config.target_supply_temp || 0 }}°C
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="回水温度" :value="status.return_temp || 0" suffix="°C" :precision="1" />
          <div style="margin-top: 10px; font-size: 12px" :style="{ color: getTempColor(status.return_temp, 'return') }">
            目标: {{ config.target_return_temp || 0 }}°C
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 回退保护状态与事件记录 -->
    <el-row :gutter="20" style="margin-top: 20px" v-if="selectedZoneId">
      <el-col :span="8">
        <RollbackStatusCard :zone-id="selectedZoneId" :headroom="currentZoneHeadroom" />
      </el-col>
      <el-col :span="16">
        <RollbackTimeline :zone-id="selectedZoneId" />
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>制冷功率趋势</span>
              <el-button-group>
                <el-button size="small" @click="refreshCharts">刷新</el-button>
                <el-button size="small" @click="toggleAutoRefresh">
                  {{ autoRefresh ? '停止自动刷新' : '开启自动刷新' }}
                </el-button>
              </el-button-group>
            </div>
          </template>
          <div ref="powerChartRef" style="width: 100%; height: 300px"></div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <span>COP 趋势</span>
          </template>
          <div ref="copChartRef" style="width: 100%; height: 300px"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <span>供回水温度趋势</span>
          </template>
          <div ref="tempChartRef" style="width: 100%; height: 300px"></div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <span>联动状态</span>
          </template>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="联动状态">
              <el-tag :type="status.linkage_active ? 'success' : 'info'">
                {{ status.linkage_active ? '运行中' : '未运行' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="上次调整时间">
              {{ status.last_adjust_time || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="调整次数">
              {{ status.adjust_count || 0 }} 次
            </el-descriptions-item>
            <el-descriptions-item label="累计节能">
              {{ status.total_energy_saving?.toFixed(0) || 0 }} kWh
            </el-descriptions-item>
            <el-descriptions-item label="累计成本节省">
              {{ status.total_cost_saving?.toFixed(0) || 0 }} 元
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="24">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>温度预测</span>
              <el-select v-if="zoneList.length > 1" v-model="selectedZoneId" size="small" style="width: 200px" @change="onZoneChange">
                <el-option v-for="zone in zoneList" :key="zone.zone_id" :label="zone.zone_name" :value="zone.zone_id" />
              </el-select>
            </div>
          </template>
          <TemperaturePredictionChart v-if="selectedZoneId" :zone-id="selectedZoneId" :zone-name="selectedZoneName" />
          <el-empty v-else description="暂无制冷区域数据" />
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="hover" style="margin-top: 20px">
      <template #header>
        <span>联动历史记录</span>
      </template>
      <el-table :data="history" border v-loading="loading">
        <el-table-column type="index" label="#" width="60" />
        <el-table-column prop="timestamp" label="时间" width="160" />
        <el-table-column prop="event_type" label="事件类型" width="120">
          <template #default="{ row }">
            <el-tag :type="getEventTypeColor(row.event_type)">{{ getEventTypeLabel(row.event_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="before_power" label="调整前功率 (kW)" width="140" align="right">
          <template #default="{ row }">
            {{ row.before_power?.toFixed(1) || 0 }}
          </template>
        </el-table-column>
        <el-table-column prop="after_power" label="调整后功率 (kW)" width="140" align="right">
          <template #default="{ row }">
            {{ row.after_power?.toFixed(1) || 0 }}
          </template>
        </el-table-column>
        <el-table-column prop="power_change" label="功率变化 (kW)" width="140" align="right">
          <template #default="{ row }">
            <span :style="{ color: row.power_change > 0 ? '#F56C6C' : '#67C23A' }">
              {{ row.power_change > 0 ? '+' : '' }}{{ row.power_change?.toFixed(1) || 0 }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="cop_before" label="调整前 COP" width="120" align="right">
          <template #default="{ row }">
            {{ row.cop_before?.toFixed(2) || 0 }}
          </template>
        </el-table-column>
        <el-table-column prop="cop_after" label="调整后 COP" width="120" align="right">
          <template #default="{ row }">
            {{ row.cop_after?.toFixed(2) || 0 }}
          </template>
        </el-table-column>
        <el-table-column prop="reason" label="调整原因" min-width="200" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getCoolingConfig, getCoolingStatus, getCoolingHistory } from '@/api/modules/shift'
import { getDashboard } from '@/api/modules/precool'
import type { DashboardZone } from '@/api/modules/precool'
import TemperaturePredictionChart from '@/components/energy/TemperaturePredictionChart.vue'
import RollbackStatusCard from '@/components/energy/RollbackStatusCard.vue'
import RollbackTimeline from '@/components/energy/RollbackTimeline.vue'
import * as echarts from 'echarts'

const loading = ref(false)
const config = ref<any>({})
const status = ref<any>({})
const history = ref<any[]>([])
const powerChartRef = ref<HTMLElement>()
const copChartRef = ref<HTMLElement>()
const tempChartRef = ref<HTMLElement>()
const powerChartInstance = ref<echarts.ECharts>()
const copChartInstance = ref<echarts.ECharts>()
const tempChartInstance = ref<echarts.ECharts>()
const autoRefresh = ref(true)
const refreshTimer = ref<number>()
const zoneList = ref<DashboardZone[]>([])
const selectedZoneId = ref<number>(0)
const selectedZoneName = computed(() => {
  const zone = zoneList.value.find(z => z.zone_id === selectedZoneId.value)
  return zone?.zone_name || ''
})

const currentZoneHeadroom = computed(() => {
  const zone = zoneList.value.find(z => z.zone_id === selectedZoneId.value)
  return zone?.headroom ?? null
})

const onZoneChange = (val: number) => {
  selectedZoneId.value = val
}

const fetchZones = async () => {
  try {
    const res = await getDashboard()
    const data = res.data as any
    zoneList.value = data?.zones || []
    if (zoneList.value.length > 0 && !selectedZoneId.value) {
      selectedZoneId.value = zoneList.value[0].zone_id
    }
  } catch {
    // 静默处理，不影响主页面
  }
}

const fetchConfig = async () => {
  try {
    const res = await getCoolingConfig()
    config.value = res.data || {}
  } catch (error: any) {
    ElMessage.error(error.message || '获取配置失败')
  }
}

const fetchStatus = async () => {
  try {
    const res = await getCoolingStatus()
    status.value = res.data || {}
    updateCharts(res.data)
  } catch (error: any) {
    ElMessage.error(error.message || '获取状态失败')
  }
}

const fetchHistory = async () => {
  loading.value = true
  try {
    const res = await getCoolingHistory({ limit: 50 })
    history.value = res.data || []
  } catch (error: any) {
    ElMessage.error(error.message || '获取历史记录失败')
  } finally {
    loading.value = false
  }
}

const initCharts = () => {
  if (powerChartRef.value) {
    powerChartInstance.value = echarts.init(powerChartRef.value)
    powerChartInstance.value.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: ['制冷功率', '目标功率'] },
      xAxis: { type: 'time', boundaryGap: false },
      yAxis: { type: 'value', name: '功率 (kW)' },
      series: [
        { name: '制冷功率', type: 'line', data: [], smooth: true, lineStyle: { color: '#409EFF' } },
        { name: '目标功率', type: 'line', data: [], smooth: true, lineStyle: { color: '#67C23A', type: 'dashed' } }
      ]
    })
  }

  if (copChartRef.value) {
    copChartInstance.value = echarts.init(copChartRef.value)
    copChartInstance.value.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: ['当前 COP', '目标 COP'] },
      xAxis: { type: 'time', boundaryGap: false },
      yAxis: { type: 'value', name: 'COP' },
      series: [
        { name: '当前 COP', type: 'line', data: [], smooth: true, lineStyle: { color: '#E6A23C' } },
        { name: '目标 COP', type: 'line', data: [], smooth: true, lineStyle: { color: '#67C23A', type: 'dashed' } }
      ]
    })
  }

  if (tempChartRef.value) {
    tempChartInstance.value = echarts.init(tempChartRef.value)
    tempChartInstance.value.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: ['供水温度', '回水温度'] },
      xAxis: { type: 'time', boundaryGap: false },
      yAxis: { type: 'value', name: '温度 (°C)' },
      series: [
        { name: '供水温度', type: 'line', data: [], smooth: true, lineStyle: { color: '#409EFF' } },
        { name: '回水温度', type: 'line', data: [], smooth: true, lineStyle: { color: '#F56C6C' } }
      ]
    })
  }
}

const updateCharts = (data: any) => {
  const now = new Date()

  if (powerChartInstance.value) {
    const powerData = powerChartInstance.value.getOption().series[0].data || []
    const targetData = powerChartInstance.value.getOption().series[1].data || []
    powerData.push([now, data.total_cooling_power || 0])
    targetData.push([now, config.value.max_cooling_power || 0])
    if (powerData.length > 100) powerData.shift()
    if (targetData.length > 100) targetData.shift()
    powerChartInstance.value.setOption({ series: [{ data: powerData }, { data: targetData }] })
  }

  if (copChartInstance.value) {
    const copData = copChartInstance.value.getOption().series[0].data || []
    const targetCopData = copChartInstance.value.getOption().series[1].data || []
    copData.push([now, data.current_cop || 0])
    targetCopData.push([now, config.value.target_cop || 0])
    if (copData.length > 100) copData.shift()
    if (targetCopData.length > 100) targetCopData.shift()
    copChartInstance.value.setOption({ series: [{ data: copData }, { data: targetCopData }] })
  }

  if (tempChartInstance.value) {
    const supplyData = tempChartInstance.value.getOption().series[0].data || []
    const returnData = tempChartInstance.value.getOption().series[1].data || []
    supplyData.push([now, data.supply_temp || 0])
    returnData.push([now, data.return_temp || 0])
    if (supplyData.length > 100) supplyData.shift()
    if (returnData.length > 100) returnData.shift()
    tempChartInstance.value.setOption({ series: [{ data: supplyData }, { data: returnData }] })
  }
}

const getCOPColor = (cop: number) => {
  if (!cop || !config.value.cop_lower_threshold) return '#909399'
  if (cop < config.value.cop_lower_threshold) return '#F56C6C'
  if (cop > config.value.cop_upper_threshold) return '#E6A23C'
  return '#67C23A'
}

const getCOPStatus = (cop: number) => {
  if (!cop || !config.value.cop_lower_threshold) return '未知'
  if (cop < config.value.cop_lower_threshold) return '偏低'
  if (cop > config.value.cop_upper_threshold) return '偏高'
  return '正常'
}

const getTempColor = (temp: number, type: 'supply' | 'return') => {
  if (!temp) return '#909399'
  const lower = type === 'supply' ? config.value.supply_temp_lower : config.value.return_temp_lower
  const upper = type === 'supply' ? config.value.supply_temp_upper : config.value.return_temp_upper
  if (temp < lower || temp > upper) return '#F56C6C'
  return '#67C23A'
}

type TagType = 'primary' | 'success' | 'info' | 'warning' | 'danger'

const getEventTypeColor = (type: string): TagType => {
  const map: Record<string, TagType> = {
    adjust: 'primary',
    alarm: 'danger',
    recovery: 'success',
    manual: 'warning'
  }
  return map[type] || 'info'
}

const getEventTypeLabel = (type: string) => {
  const map: Record<string, string> = {
    adjust: '自动调整',
    alarm: '告警',
    recovery: '恢复',
    manual: '手动调整'
  }
  return map[type] || type
}

const refreshCharts = async () => {
  await fetchStatus()
  await fetchHistory()
}

const toggleAutoRefresh = () => {
  autoRefresh.value = !autoRefresh.value
  if (autoRefresh.value) {
    startAutoRefresh()
  } else {
    stopAutoRefresh()
  }
}

const startAutoRefresh = () => {
  refreshTimer.value = window.setInterval(() => {
    fetchStatus()
  }, 5000)
}

const stopAutoRefresh = () => {
  if (refreshTimer.value) {
    clearInterval(refreshTimer.value)
    refreshTimer.value = undefined
  }
}

onMounted(async () => {
  await fetchConfig()
  await fetchStatus()
  await fetchHistory()
  await fetchZones()
  initCharts()
  if (autoRefresh.value) {
    startAutoRefresh()
  }
})

onUnmounted(() => {
  stopAutoRefresh()
  if (powerChartInstance.value) powerChartInstance.value.dispose()
  if (copChartInstance.value) copChartInstance.value.dispose()
  if (tempChartInstance.value) tempChartInstance.value.dispose()
})
</script>

<style scoped lang="scss">
.cooling-linkage-monitor {
  padding: 20px;

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
}
</style>
