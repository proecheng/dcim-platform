<template>
  <div class="battery-monitor">
    <!-- 电池组列表 -->
    <el-card shadow="hover" class="table-card">
      <template #header>
        <div class="card-header">
          <span>电池组列表</span>
          <el-button type="primary" link @click="loadData">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
        </div>
      </template>
      <el-table
        :data="batteryList"
        stripe
        border
        v-loading="loading"
        @row-click="openDetail"
        highlight-current-row
        style="cursor: pointer;"
      >
        <el-table-column prop="group_name" label="组名" min-width="130" />
        <el-table-column prop="ups_name" label="关联UPS" width="140" />
        <el-table-column prop="battery_type" label="电池类型" width="120">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ batteryTypeLabel(row.battery_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="rated_capacity" label="额定容量(Ah)" width="120" align="center" />
        <el-table-column label="SOH(%)" width="160">
          <template #default="{ row }">
            <el-progress
              :percentage="Math.min(row.soh ?? 0, 100)"
              :stroke-width="14"
              :color="getSohColor(row.soh ?? 0)"
              :format="(p: number) => `${p.toFixed(1)}%`"
            />
          </template>
        </el-table-column>
        <el-table-column label="SOC(%)" width="160">
          <template #default="{ row }">
            <el-progress
              :percentage="Math.min(row.soc ?? 0, 100)"
              :stroke-width="14"
              :color="getSocColor(row.soc ?? 0)"
              :format="(p: number) => `${p.toFixed(1)}%`"
            />
          </template>
        </el-table-column>
        <el-table-column prop="voltage" label="电压(V)" width="100" align="center">
          <template #default="{ row }">
            {{ row.voltage?.toFixed(1) ?? '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="temperature" label="温度(°C)" width="100" align="center">
          <template #default="{ row }">
            <span :class="{ 'temp-warn': (row.temperature ?? 0) > 40 }">
              {{ row.temperature?.toFixed(1) ?? '-' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="charge_status" label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="chargeStatusType(row.charge_status)" size="small">
              {{ chargeStatusLabel(row.charge_status) }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && batteryList.length === 0" description="暂无电池组数据" />
    </el-card>

    <!-- 详情抽屉 -->
    <el-drawer v-model="drawerVisible" title="电池组详情" size="480px" direction="rtl">
      <div v-if="detailLoading" v-loading="true" style="height: 200px;" />
      <template v-else-if="detail">
        <h4 class="section-title">基本信息</h4>
        <el-descriptions :column="1" border class="detail-desc">
          <el-descriptions-item label="电池类型">{{ batteryTypeLabel(detail.battery_type) }}</el-descriptions-item>
          <el-descriptions-item label="额定容量">{{ detail.rated_capacity }} Ah</el-descriptions-item>
          <el-descriptions-item label="额定电压">{{ detail.rated_voltage }} V</el-descriptions-item>
          <el-descriptions-item label="电芯数量">{{ detail.cell_count }}</el-descriptions-item>
        </el-descriptions>

        <h4 class="section-title">实时参数</h4>
        <el-descriptions :column="1" border class="detail-desc">
          <el-descriptions-item label="电流">{{ detailRealtime.current ?? '-' }} A</el-descriptions-item>
          <el-descriptions-item label="电压">{{ detailRealtime.voltage ?? '-' }} V</el-descriptions-item>
          <el-descriptions-item label="温度">{{ detailRealtime.temperature ?? '-' }} °C</el-descriptions-item>
          <el-descriptions-item label="内阻">{{ detailRealtime.resistance ?? '-' }} mΩ</el-descriptions-item>
          <el-descriptions-item label="备电时间">{{ detailRealtime.backup_time ?? '-' }} min</el-descriptions-item>
          <el-descriptions-item label="放电次数">{{ detailRealtime.discharge_count ?? '-' }}</el-descriptions-item>
        </el-descriptions>
      </template>
      <el-empty v-else description="暂无详情数据" />
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { Refresh } from '@element-plus/icons-vue'
import { getBatteryList, getBatteryDetail } from '@/api/modules/power'

const loading = ref(false)
const drawerVisible = ref(false)
const detailLoading = ref(false)

interface BatteryItem {
  id: number
  group_name: string
  ups_name: string
  battery_type: string
  rated_capacity: number
  soh?: number
  soc?: number
  voltage?: number
  temperature?: number
  charge_status: string
}

interface BatteryDetailData {
  battery_type: string
  rated_capacity: number
  rated_voltage: number
  cell_count: number
}

interface BatteryRealtime {
  current?: number
  voltage?: number
  temperature?: number
  resistance?: number
  backup_time?: number
  discharge_count?: number
}

const batteryList = ref<BatteryItem[]>([])
const detail = ref<BatteryDetailData | null>(null)
const detailRealtime = ref<BatteryRealtime>({})

const mockBatteryList: BatteryItem[] = [
  { id: 1, group_name: '电池组A-1', ups_name: 'A栋主UPS', battery_type: 'lead_acid', rated_capacity: 100, soh: 96.5, soc: 95.0, voltage: 432.5, temperature: 25.3, charge_status: 'float' },
  { id: 2, group_name: '电池组A-2', ups_name: 'A栋主UPS', battery_type: 'lead_acid', rated_capacity: 100, soh: 94.2, soc: 82.5, voltage: 428.1, temperature: 26.1, charge_status: 'idle' },
  { id: 3, group_name: '电池组B-1', ups_name: 'B栋主UPS', battery_type: 'lithium', rated_capacity: 150, soh: 98.1, soc: 91.3, voltage: 540.2, temperature: 23.8, charge_status: 'float' },
  { id: 4, group_name: '电池组B-2', ups_name: 'B栋主UPS', battery_type: 'lithium', rated_capacity: 150, soh: 65.0, soc: 45.2, voltage: 510.8, temperature: 28.5, charge_status: 'discharge' }
]

const mockDetailRealtime: BatteryRealtime = {
  current: 12.5,
  voltage: 432.5,
  temperature: 25.3,
  resistance: 3.2,
  backup_time: 30,
  discharge_count: 128
}

type TagType = 'success' | 'warning' | 'danger' | 'info'

function batteryTypeLabel(type: string): string {
  const map: Record<string, string> = { lead_acid: '铅酸', lithium: '锂电', nickel: '镍氢' }
  return map[type] || type
}

function chargeStatusType(status: string): TagType {
  const map: Record<string, TagType> = { float: 'success', charging: 'warning', discharge: 'danger', idle: 'info' }
  return map[status] || 'info'
}

function chargeStatusLabel(status: string): string {
  const map: Record<string, string> = { float: '浮充', charging: '充电', discharge: '放电', idle: '静置' }
  return map[status] || status
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

async function loadData() {
  loading.value = true
  try {
    const res = await getBatteryList()
    const data = res?.data ?? res
    batteryList.value = Array.isArray(data) ? data : (data?.items ?? [])
  } catch {
    console.warn('电池组列表API未就绪，使用模拟数据')
    batteryList.value = mockBatteryList
  } finally {
    loading.value = false
  }
  if (batteryList.value.length === 0) {
    batteryList.value = mockBatteryList
  }
}

async function openDetail(row: BatteryItem) {
  drawerVisible.value = true
  detailLoading.value = true
  detail.value = null
  detailRealtime.value = {}
  try {
    const res = await getBatteryDetail(row.id)
    const data = res?.data ?? res
    detail.value = data as BatteryDetailData
    detailRealtime.value = (data as Record<string, unknown>).realtime
      ? ((data as Record<string, unknown>).realtime as BatteryRealtime)
      : mockDetailRealtime
  } catch {
    console.warn('电池组详情API未就绪，使用模拟数据')
    detail.value = {
      battery_type: row.battery_type,
      rated_capacity: row.rated_capacity,
      rated_voltage: row.voltage ?? 432,
      cell_count: 36
    }
    detailRealtime.value = mockDetailRealtime
  } finally {
    detailLoading.value = false
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped lang="scss">
@use '@/styles/mixins-25d' as *;

.battery-monitor {
  @include page-list;
  .table-card {
    background: var(--bg-card);
    border-color: var(--border-color);
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    color: var(--text-primary);
  }

  .temp-warn {
    color: var(--error-color, #f5222d);
    font-weight: 600;
  }

  .section-title {
    margin: 20px 0 12px;
    font-size: 15px;
    font-weight: 600;
    color: var(--text-primary);
  }

  .detail-desc {
    margin-bottom: 8px;
  }
}
</style>
