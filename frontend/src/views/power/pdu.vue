<template>
  <div class="pdu-monitor">
    <!-- PDU列表 -->
    <el-card shadow="hover" class="table-card">
      <template #header>
        <div class="card-header">
          <span>机柜PDU监控</span>
          <el-button type="primary" link @click="loadData">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
        </div>
      </template>
      <el-table
        :data="pduList"
        stripe
        border
        v-loading="loading"
        @row-click="openDetail"
        highlight-current-row
        style="cursor: pointer;"
      >
        <el-table-column prop="device_code" label="设备编码" width="140" />
        <el-table-column prop="device_name" label="设备名称" min-width="150" />
        <el-table-column prop="area" label="区域" width="120" />
        <el-table-column prop="total_current" label="总电流(A)" width="110" align="center">
          <template #default="{ row }">
            {{ row.total_current?.toFixed(1) ?? '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="temperature" label="温度(°C)" width="100" align="center">
          <template #default="{ row }">
            <span :class="{ 'temp-warn': (row.temperature ?? 0) > 45 }">
              {{ row.temperature?.toFixed(1) ?? '-' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && pduList.length === 0" description="暂无PDU数据" />
    </el-card>

    <!-- 插座详情抽屉 -->
    <el-drawer v-model="drawerVisible" :title="drawerTitle" size="620px" direction="rtl">
      <div v-if="detailLoading" v-loading="true" style="height: 200px;" />
      <template v-else-if="outlets.length > 0">
        <h4 class="section-title">插座信息</h4>
        <el-table :data="outlets" stripe border size="small">
          <el-table-column prop="outlet_no" label="插座编号" width="90" align="center" />
          <el-table-column prop="current" label="电流(A)" width="90" align="center">
            <template #default="{ row }">
              {{ row.current?.toFixed(2) ?? '-' }}
            </template>
          </el-table-column>
          <el-table-column prop="voltage" label="电压(V)" width="90" align="center">
            <template #default="{ row }">
              {{ row.voltage?.toFixed(1) ?? '-' }}
            </template>
          </el-table-column>
          <el-table-column prop="power" label="功率(W)" width="90" align="center">
            <template #default="{ row }">
              {{ row.power?.toFixed(1) ?? '-' }}
            </template>
          </el-table-column>
          <el-table-column prop="energy" label="电度(kWh)" width="100" align="center">
            <template #default="{ row }">
              {{ row.energy?.toFixed(2) ?? '-' }}
            </template>
          </el-table-column>
          <el-table-column label="通断状态" width="100" align="center">
            <template #default="{ row }">
              <el-switch
                :model-value="row.on_off"
                disabled
                active-text="通"
                inactive-text="断"
                inline-prompt
              />
            </template>
          </el-table-column>
        </el-table>
      </template>
      <el-empty v-else description="暂无插座数据" />
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { Refresh } from '@element-plus/icons-vue'
import { getPDUList } from '@/api/modules/power'

const loading = ref(false)
const drawerVisible = ref(false)
const detailLoading = ref(false)
const drawerTitle = ref('PDU详情')

interface PDUItem {
  id: number
  device_code: string
  device_name: string
  area: string
  total_current?: number
  temperature?: number
  status: string
  outlets?: OutletItem[]
}

interface OutletItem {
  outlet_no: string
  current?: number
  voltage?: number
  power?: number
  energy?: number
  on_off: boolean
}

const pduList = ref<PDUItem[]>([])
const outlets = ref<OutletItem[]>([])

function generateMockOutlets(count: number): OutletItem[] {
  return Array.from({ length: count }, (_, i) => ({
    outlet_no: `#${i + 1}`,
    current: Math.random() * 8 + 0.5,
    voltage: 220 + Math.random() * 2 - 1,
    power: Math.random() * 1800 + 100,
    energy: Math.random() * 500 + 50,
    on_off: Math.random() > 0.15
  }))
}

const mockPDUList: PDUItem[] = [
  { id: 1, device_code: 'PDU-A01-L', device_name: 'A01机柜左PDU', area: 'A栋机房', total_current: 24.5, temperature: 32.1, status: 'normal', outlets: generateMockOutlets(8) },
  { id: 2, device_code: 'PDU-A01-R', device_name: 'A01机柜右PDU', area: 'A栋机房', total_current: 22.8, temperature: 31.5, status: 'normal', outlets: generateMockOutlets(8) },
  { id: 3, device_code: 'PDU-B01-L', device_name: 'B01机柜左PDU', area: 'B栋机房', total_current: 18.3, temperature: 29.8, status: 'normal', outlets: generateMockOutlets(6) },
  { id: 4, device_code: 'PDU-B01-R', device_name: 'B01机柜右PDU', area: 'B栋机房', total_current: 19.1, temperature: 30.2, status: 'warning', outlets: generateMockOutlets(6) }
]

type TagType = 'success' | 'warning' | 'danger' | 'info'

function statusTagType(status: string): TagType {
  const map: Record<string, TagType> = { normal: 'success', alarm: 'danger', warning: 'warning', offline: 'info' }
  return map[status] || 'info'
}

function statusLabel(status: string): string {
  const map: Record<string, string> = { normal: '正常', alarm: '告警', warning: '预警', offline: '离线' }
  return map[status] || status
}

async function loadData() {
  loading.value = true
  try {
    const res = await getPDUList()
    const data = res?.data ?? res
    pduList.value = Array.isArray(data) ? data : (data?.items ?? [])
  } catch {
    console.warn('PDU列表API未就绪，使用模拟数据')
    pduList.value = mockPDUList
  } finally {
    loading.value = false
  }
  if (pduList.value.length === 0) {
    pduList.value = mockPDUList
  }
}

function openDetail(row: PDUItem) {
  drawerTitle.value = `${row.device_name} — 插座详情`
  drawerVisible.value = true
  detailLoading.value = true

  setTimeout(() => {
    if (row.outlets && row.outlets.length > 0) {
      outlets.value = row.outlets
    } else {
      const mock = mockPDUList.find(p => p.id === row.id)
      outlets.value = mock?.outlets ?? generateMockOutlets(8)
    }
    detailLoading.value = false
  }, 300)
}

onMounted(() => {
  loadData()
})
</script>

<style scoped lang="scss">
@use '@/styles/mixins-25d' as *;

.pdu-monitor {
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
    margin: 0 0 12px;
    font-size: 15px;
    font-weight: 600;
    color: var(--text-primary);
  }
}
</style>
