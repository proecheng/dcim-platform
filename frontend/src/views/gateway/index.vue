<template>
  <div class="gateway-monitor">
    <!-- 顶部统计卡片 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :span="5" v-for="card in statCards" :key="card.label">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" :style="{ background: card.iconBg }">
              <el-icon :size="22"><component :is="card.icon" /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value" :class="card.valueClass">
                {{ card.value }}
              </div>
              <div class="stat-label">{{ card.label }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 网关列表表格 -->
    <el-card shadow="hover" class="table-card">
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <el-icon :size="18"><Monitor /></el-icon>
            <span>网关设备列表</span>
          </div>
          <div class="header-filters">
            <el-select
              v-model="filterStatus"
              placeholder="全部状态"
              clearable
              size="default"
              style="width: 130px;"
              @change="handleSearch"
            >
              <el-option label="在线" value="online" />
              <el-option label="离线" value="offline" />
            </el-select>
            <el-input
              v-model="searchKeyword"
              placeholder="搜索网关名称/IP"
              clearable
              size="default"
              style="width: 200px;"
              :prefix-icon="Search"
              @keyup.enter="handleSearch"
            />
            <el-button type="primary" link @click="handleRefresh">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
            <el-button
              v-if="selectedGateways.length > 0"
              type="warning"
              size="default"
              :loading="batchPushing"
              @click="handleBatchPush"
            >
              <el-icon><Setting /></el-icon>
              批量配置下发 ({{ selectedGateways.length }})
            </el-button>
          </div>
        </div>
      </template>

      <el-table
        :data="tableData"
        stripe
        v-loading="loading"
        :row-class-name="tableRowClass"
        @expand-change="handleExpandChange"
        @selection-change="handleSelectionChange"
        row-key="id"
      >
        <el-table-column type="selection" width="45" />
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="expand-panel" v-loading="expandLoading[row.id]">
              <el-row :gutter="24">
                <!-- 左侧: 基本信息 + 资源使用率 -->
                <el-col :span="10">
                  <div class="expand-section">
                    <div class="section-title">基本信息</div>
                    <div class="info-grid">
                      <div class="info-item">
                        <span class="info-label">网关标识</span>
                        <span class="info-val">{{ row.gateway_id }}</span>
                      </div>
                      <div class="info-item">
                        <span class="info-label">固件版本</span>
                        <span class="info-val">{{ row.version || '--' }}</span>
                      </div>
                      <div class="info-item">
                        <span class="info-label">IP 地址</span>
                        <span class="info-val">{{ row.ip_address || '--' }}</span>
                      </div>
                      <div class="info-item">
                        <span class="info-label">创建时间</span>
                        <span class="info-val">{{ formatTime(row.created_at) }}</span>
                      </div>
                      <div class="info-item">
                        <span class="info-label">数据源数</span>
                        <span class="info-val">{{ expandDetails[row.id]?.datasource_count ?? '--' }}</span>
                      </div>
                      <div class="info-item">
                        <span class="info-label">关联点位</span>
                        <span class="info-val">{{ expandDetails[row.id]?.point_count ?? '--' }}</span>
                      </div>
                    </div>
                  </div>
                  <div class="expand-section">
                    <div class="section-title">资源使用率</div>
                    <div class="resource-bars">
                      <div class="resource-item">
                        <span class="resource-label">CPU</span>
                        <el-progress
                          :percentage="row.cpu_usage ?? 0"
                          :color="progressColor(row.cpu_usage)"
                          :stroke-width="14"
                          :format="formatPercent"
                        />
                      </div>
                      <div class="resource-item">
                        <span class="resource-label">内存</span>
                        <el-progress
                          :percentage="row.memory_usage ?? 0"
                          :color="progressColor(row.memory_usage)"
                          :stroke-width="14"
                          :format="formatPercent"
                        />
                      </div>
                      <div class="resource-item">
                        <span class="resource-label">磁盘</span>
                        <el-progress
                          :percentage="row.disk_usage ?? 0"
                          :color="progressColor(row.disk_usage)"
                          :stroke-width="14"
                          :format="formatPercent"
                        />
                      </div>
                    </div>
                  </div>
                </el-col>
                <!-- 右侧: 24h 事件趋势图 -->
                <el-col :span="14">
                  <div class="expand-section">
                    <div class="section-title">最近 24 小时事件</div>
                    <div :ref="(el) => setChartRef(el, row.id)" class="event-chart" />
                  </div>
                </el-col>
              </el-row>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="name" label="网关名称" min-width="150" show-overflow-tooltip />
        <el-table-column prop="ip_address" label="IP 地址" width="140">
          <template #default="{ row }">
            {{ row.ip_address || '--' }}
          </template>
        </el-table-column>
        <el-table-column label="协议能力" min-width="140">
          <template #default="{ row }">
            <template v-if="row.capabilities && Object.keys(row.capabilities).length">
              <el-tag
                v-for="cap in getCapabilityTags(row.capabilities)"
                :key="cap"
                size="small"
                type="info"
                style="margin-right: 4px;"
              >
                {{ cap }}
              </el-tag>
            </template>
            <span v-else class="text-muted">--</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <div class="status-cell">
              <el-icon v-if="isOfflineAlert(row)" :size="16" color="#f5222d" class="alert-icon">
                <WarningFilled />
              </el-icon>
              <el-tag :type="statusTagType(row.status)" size="small" effect="dark">
                {{ statusText(row.status) }}
              </el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="CPU / 内存" width="130">
          <template #default="{ row }">
            <span v-if="row.cpu_usage != null || row.memory_usage != null">
              {{ row.cpu_usage != null ? row.cpu_usage.toFixed(1) + '%' : '--' }}
              /
              {{ row.memory_usage != null ? row.memory_usage.toFixed(1) + '%' : '--' }}
            </span>
            <span v-else class="text-muted">--</span>
          </template>
        </el-table-column>
        <el-table-column label="最后心跳" width="170">
          <template #default="{ row }">
            {{ formatTime(row.last_heartbeat) }}
          </template>
        </el-table-column>
        <el-table-column prop="is_enabled" label="启用" width="70">
          <template #default="{ row }">
            <el-tag :type="row.is_enabled ? 'success' : 'info'" size="small">
              {{ row.is_enabled ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-tooltip
              :content="row.status !== 'online' ? '网关离线' : !row.is_enabled ? '网关已禁用' : '配置下发'"
              placement="top"
            >
              <el-button
                type="primary"
                link
                size="small"
                :disabled="row.status !== 'online' || !row.is_enabled"
                @click="openConfigDialog(row)"
              >
                <el-icon><Setting /></el-icon>
                配置下发
              </el-button>
            </el-tooltip>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        style="margin-top: 16px; justify-content: flex-end;"
        @size-change="loadData"
        @current-change="loadData"
      />
    </el-card>

    <!-- 配置下发对话框 -->
    <GatewayConfigDialog
      v-model="configDialogVisible"
      :gateway-id="configGatewayId"
      :gateway-name="configGatewayName"
      @pushed="handleRefresh"
    />
  </div>
</template>

<script setup lang="ts">
import * as echarts from 'echarts'
import { Search, Monitor, Refresh, WarningFilled, CircleCheck, CircleClose, DataLine, Setting } from '@element-plus/icons-vue'
import {
  getGatewayList,
  getGatewaySummary,
  getGatewayDetail,
  getGatewayEvents,
  pushGatewayConfig,
  type GatewayInfo,
  type GatewaySummary,
  type GatewayDetail,
  type GatewayEvent,
} from '@/api/modules/gateway'
import { useWebSocket } from '@/composables/useWebSocket'
import GatewayConfigDialog from './GatewayConfigDialog.vue'
import { useDebounceFn } from '@vueuse/core'

// ── 统计数据 ──
const summary = ref<GatewaySummary>({ total: 0, online: 0, offline: 0 })

const statCards = computed(() => [
  {
    label: '网关总数',
    value: summary.value.total,
    icon: Monitor,
    iconBg: 'rgba(24, 144, 255, 0.15)',
    valueClass: 'primary',
  },
  {
    label: '在线数',
    value: summary.value.online,
    icon: CircleCheck,
    iconBg: 'rgba(82, 196, 26, 0.15)',
    valueClass: 'success',
  },
  {
    label: '离线数',
    value: summary.value.offline,
    icon: CircleClose,
    iconBg: 'rgba(245, 34, 45, 0.15)',
    valueClass: 'danger',
  },
  {
    label: '告警网关',
    value: alertCount.value,
    icon: WarningFilled,
    iconBg: 'rgba(230, 162, 60, 0.15)',
    valueClass: 'warning',
  },
  {
    label: '平均 CPU',
    value: avgThroughput.value,
    icon: DataLine,
    iconBg: 'rgba(64, 158, 255, 0.15)',
    valueClass: 'primary',
  },
])

// 告警数: 离线且启用的网关
// ⚠️ 数据映射说明: 后端 GatewayStatusSummary 只有 total/online/offline，无 alarm 字段。
// 前端将"离线且启用"的网关视为告警网关。
const alertCount = computed(() => {
  return tableData.value.filter(g => g.status === 'offline' && g.is_enabled).length
})

// 平均负载: 在线网关的平均 CPU 使用率
// ⚠️ 数据映射说明: 后端 Gateway 模型无"数据吞吐量"字段。
// 前端用 cpu_usage 平均值作为"平均负载"指标替代。
// 相关映射: datasource_count → 关联数据源数, capabilities → 协议能力标签,
//           cpu_usage/memory_usage → 连接质量/负载指标
const avgThroughput = computed(() => {
  const onlineGateways = tableData.value.filter(g => g.status === 'online' && g.cpu_usage != null)
  if (onlineGateways.length === 0) return '--'
  const avg = onlineGateways.reduce((sum, g) => sum + (g.cpu_usage ?? 0), 0) / onlineGateways.length
  return avg.toFixed(1) + '%'
})

// ── 表格数据 ──
const loading = ref(false)
const tableData = ref<GatewayInfo[]>([])
const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0,
})

// ── 筛选 ──
const filterStatus = ref('')
const searchKeyword = ref('')

// ── 展开详情 ──
const expandLoading = reactive<Record<number, boolean>>({})
const expandDetails = reactive<Record<number, GatewayDetail>>({})
const chartRefs: Record<number, HTMLElement | null> = {}
const chartInstances: Record<number, echarts.ECharts> = {}

function setChartRef(el: unknown, id: number) {
  if (el && typeof el === 'object' && '$el' in el) {
    chartRefs[id] = (el as { $el: HTMLElement }).$el
  } else {
    chartRefs[id] = (el as HTMLElement | null)
  }
}

function formatPercent(p: number): string {
  return p.toFixed(1) + '%'
}

// ── 数据加载 ──
async function loadData() {
  loading.value = true
  try {
    const params: Record<string, string | number | boolean> = {
      page: pagination.page,
      page_size: pagination.pageSize,
    }
    if (filterStatus.value) params.status = filterStatus.value
    if (searchKeyword.value) params.keyword = searchKeyword.value

    const res = await getGatewayList(params)
    tableData.value = res.items
    pagination.total = res.total
  } catch (e) {
    console.error('加载网关列表失败', e)
  } finally {
    loading.value = false
  }
}

async function loadSummary() {
  try {
    summary.value = await getGatewaySummary()
  } catch (e) {
    console.error('加载网关汇总失败', e)
  }
}

function handleSearch() {
  pagination.page = 1
  loadData()
}

function handleRefresh() {
  loadData()
  loadSummary()
}

// ── 展开行处理 ──
async function handleExpandChange(row: GatewayInfo, expandedRows: GatewayInfo[]) {
  const isExpanding = expandedRows.some(r => r.id === row.id)
  if (!isExpanding) {
    // 收起时销毁图表
    if (chartInstances[row.id]) {
      chartInstances[row.id].dispose()
      delete chartInstances[row.id]
    }
    return
  }

  expandLoading[row.id] = true
  try {
    // 并行加载详情和事件
    const [detail, eventsRes] = await Promise.all([
      getGatewayDetail(row.id),
      getGatewayEvents(row.id, { page: 1, page_size: 100 }),
    ])
    expandDetails[row.id] = detail

    // 渲染事件趋势图
    await nextTick()
    renderEventChart(row.id, eventsRes.items)
  } catch (e) {
    console.error('加载网关详情失败', e)
  } finally {
    expandLoading[row.id] = false
  }
}

function renderEventChart(gatewayId: number, events: GatewayEvent[]) {
  const el = chartRefs[gatewayId]
  if (!el) return

  if (chartInstances[gatewayId]) {
    chartInstances[gatewayId].dispose()
  }

  const chart = echarts.init(el, 'dark-tech')
  chartInstances[gatewayId] = chart

  if (events.length === 0) {
    chart.setOption({
      title: {
        text: '暂无事件数据',
        left: 'center',
        top: 'center',
        textStyle: { color: '#999', fontSize: 14 },
      },
    })
    return
  }

  // 按时间排序
  const sorted = [...events].sort((a, b) => {
    const ta = a.created_at || ''
    const tb = b.created_at || ''
    return ta.localeCompare(tb)
  })

  const times = sorted.map(e => (e.created_at || '').replace('T', ' ').substring(0, 16))
  const typeMap: Record<string, number> = { status_change: 1, resource_warning: 2 }
  const values = sorted.map(e => typeMap[e.event_type] || 0)
  const colors = sorted.map(e => e.event_type === 'resource_warning' ? '#faad14' : '#1890ff')

  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'axis',
      formatter: (params: unknown) => {
        const p = (params as Array<{ dataIndex: number }>)[0]
        const evt = sorted[p.dataIndex]
        let tip = `<b>${times[p.dataIndex]}</b><br/>`
        tip += `类型: ${evt.event_type === 'status_change' ? '状态变更' : '资源告警'}<br/>`
        if (evt.old_status) tip += `${evt.old_status} → ${evt.new_status}<br/>`
        return tip
      },
    },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '8%', containLabel: true },
    xAxis: {
      type: 'category',
      data: times,
      axisLabel: {
        rotate: 30,
        formatter: (value: string) => value.substring(11, 16),
      },
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 3,
      axisLabel: {
        formatter: (value: number) => {
          const labels: Record<number, string> = { 1: '状态变更', 2: '资源告警' }
          return labels[value] || ''
        },
      },
    },
    series: [{
      type: 'bar',
      data: values.map((v, i) => ({
        value: v,
        itemStyle: { color: colors[i] },
      })),
      barMaxWidth: 20,
    }],
  }

  chart.setOption(option, true)
}

// ── WebSocket 实时更新 ──
const { on, off, isConnected } = useWebSocket({
  url: '/ws/system',
  autoConnect: true,
})

// 节流 loadSummary，避免高频 WebSocket 消息触发大量请求
const debouncedLoadSummary = useDebounceFn(loadSummary, 2000)

function handleGatewayStatusMessage(message: { type: string; data?: { gateway_id?: string; status?: string } }) {
  if (message.type !== 'gateway_status' || !message.data) return
  const { gateway_id, status } = message.data
  if (!gateway_id || !status) return

  // 更新表格中对应网关的状态
  const target = tableData.value.find(g => g.gateway_id === gateway_id)
  if (target) {
    target.status = status as 'online' | 'offline'
    target.last_heartbeat = new Date().toISOString()
  }

  // 节流刷新汇总
  debouncedLoadSummary()
}

// 轮询降级
let pollingTimer: number | null = null

function startPolling() {
  stopPolling()
  pollingTimer = window.setInterval(() => {
    if (!isConnected.value) {
      loadData()
      loadSummary()
    }
  }, 15000)
}

function stopPolling() {
  if (pollingTimer) {
    clearInterval(pollingTimer)
    pollingTimer = null
  }
}

// ── 辅助函数 ──
type TagType = 'info' | 'warning' | 'success' | 'danger' | 'primary'

function statusTagType(status: string): TagType {
  const map: Record<string, TagType> = { online: 'success', offline: 'danger' }
  return map[status] || 'info'
}

function statusText(status: string): string {
  const map: Record<string, string> = { online: '在线', offline: '离线' }
  return map[status] || status
}

function formatTime(t: string | null | undefined): string {
  if (!t) return '--'
  return t.replace('T', ' ').substring(0, 19)
}

/** 离线超过 5 分钟标红告警 */
function isOfflineAlert(row: GatewayInfo): boolean {
  if (row.status !== 'offline' || !row.is_enabled) return false
  if (!row.last_heartbeat) return true
  const diff = Date.now() - new Date(row.last_heartbeat).getTime()
  return diff > 5 * 60 * 1000
}

function tableRowClass({ row }: { row: GatewayInfo }): string {
  if (isOfflineAlert(row)) return 'offline-alert-row'
  if (row.status === 'offline') return 'offline-row'
  return ''
}

function progressColor(value: number | null): string {
  if (value == null) return '#909399'
  if (value >= 90) return '#f5222d'
  if (value >= 70) return '#faad14'
  return '#52c41a'
}

function getCapabilityTags(capabilities: Record<string, unknown>): string[] {
  if (Array.isArray(capabilities)) return capabilities.map(String).slice(0, 3)
  return Object.keys(capabilities).slice(0, 3)
}

// ── 配置下发对话框 ──
const configDialogVisible = ref(false)
const configGatewayId = ref<number | null>(null)
const configGatewayName = ref('')

function openConfigDialog(row: GatewayInfo) {
  configGatewayId.value = row.id
  configGatewayName.value = row.name
  configDialogVisible.value = true
}

// ── 多选 & 批量下发 ──
const selectedGateways = ref<GatewayInfo[]>([])
const batchPushing = ref(false)

function handleSelectionChange(rows: GatewayInfo[]) {
  selectedGateways.value = rows
}

async function handleBatchPush() {
  const onlineEnabled = selectedGateways.value.filter(
    g => g.status === 'online' && g.is_enabled
  )
  if (onlineEnabled.length === 0) {
    ElMessage.warning('所选网关中没有在线且启用的网关')
    return
  }

  try {
    await ElMessageBox.confirm(
      `将对 ${onlineEnabled.length} 个在线网关下发配置，是否继续？`,
      '批量配置下发',
      { confirmButtonText: '确认下发', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }

  batchPushing.value = true
  let successCount = 0
  let failCount = 0

  // 并发下发（限制 3 并发，避免 MQTT 拥塞）
  const CONCURRENCY = 3
  const queue = [...onlineEnabled]
  const executing = new Set<Promise<void>>()

  for (const gw of queue) {
    const task = pushGatewayConfig(gw.id)
      .then(() => { successCount++ })
      .catch(() => { failCount++ })
      .finally(() => { executing.delete(task) })
    executing.add(task)
    if (executing.size >= CONCURRENCY) {
      await Promise.race(executing)
    }
  }
  await Promise.all(executing)

  batchPushing.value = false

  if (failCount === 0) {
    ElMessage.success(`全部 ${successCount} 个网关配置下发成功`)
  } else {
    ElMessage.warning(`成功 ${successCount} 个，失败 ${failCount} 个`)
  }
}

// ── 生命周期 ──
onMounted(() => {
  loadData()
  loadSummary()
  on('gateway_status', handleGatewayStatusMessage)
  startPolling()
})

onUnmounted(() => {
  stopPolling()
  off('gateway_status', handleGatewayStatusMessage)
  // 销毁所有图表
  Object.values(chartInstances).forEach(c => c.dispose())
})
</script>

<style scoped lang="scss">
@use '@/styles/mixins-25d' as *;

.gateway-monitor {
  @include page-dashboard(5);

  .stat-row {
    margin-bottom: 16px;
  }

  .stat-card {
    background: var(--bg-card);
    border-color: var(--border-color);
    transition: transform 0.2s, box-shadow 0.2s;

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
    }

    .stat-label {
      font-size: 13px;
      color: var(--text-secondary);
      margin-top: 2px;
    }
  }

  // ── 表格卡片 ──
  .table-card {
    background: var(--bg-card);
    border-color: var(--border-color);

    .card-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 8px;

      .header-left {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 15px;
        font-weight: 600;
        color: var(--text-primary);
      }

      .header-filters {
        display: flex;
        align-items: center;
        gap: 8px;
      }
    }
  }

  .text-muted {
    color: var(--text-secondary);
  }

  .status-cell {
    display: flex;
    align-items: center;
    gap: 4px;

    .alert-icon {
      animation: pulse-alert 1.5s ease-in-out infinite;
    }
  }

  // ── 展开面板 ──
  .expand-panel {
    padding: 16px 24px;

    .expand-section {
      margin-bottom: 20px;

      &:last-child {
        margin-bottom: 0;
      }
    }

    .section-title {
      font-size: 14px;
      font-weight: 600;
      color: var(--text-primary);
      margin-bottom: 12px;
      padding-left: 8px;
      border-left: 3px solid #1890ff;
    }

    .info-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px 16px;

      .info-item {
        display: flex;
        justify-content: space-between;
        padding: 4px 0;
        border-bottom: 1px solid var(--border-color, rgba(255, 255, 255, 0.06));

        .info-label {
          font-size: 13px;
          color: var(--text-secondary);
        }

        .info-val {
          font-size: 13px;
          font-weight: 500;
          color: var(--text-primary);
        }
      }
    }

    .resource-bars {
      .resource-item {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 8px;

        .resource-label {
          width: 32px;
          font-size: 13px;
          color: var(--text-secondary);
          flex-shrink: 0;
        }

        .el-progress {
          flex: 1;
        }
      }
    }

    .event-chart {
      width: 100%;
      height: 260px;
    }
  }

  // ── 行状态样式 ──
  :deep(.offline-alert-row) {
    background-color: rgba(245, 34, 45, 0.08) !important;
  }

  :deep(.offline-row) {
    background-color: rgba(245, 34, 45, 0.04) !important;
  }
}

@keyframes pulse-alert {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
</style>
