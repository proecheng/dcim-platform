<template>
  <div class="cabinet-monitor">
    <!-- 配电柜列表 -->
    <el-card shadow="hover" class="table-card">
      <template #header>
        <div class="card-header">
          <span>配电柜监控</span>
          <el-button type="primary" link @click="loadData">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
        </div>
      </template>
      <el-table
        :data="cabinetList"
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
        <el-table-column prop="total_power" label="总功率(kW)" width="120" align="center">
          <template #default="{ row }">
            {{ row.total_power?.toFixed(1) ?? '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="input_voltage" label="输入电压(V)" width="120" align="center">
          <template #default="{ row }">
            {{ row.input_voltage?.toFixed(1) ?? '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="output_current" label="输出电流(A)" width="120" align="center">
          <template #default="{ row }">
            {{ row.output_current?.toFixed(1) ?? '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="busbar_temp" label="母排温度(°C)" width="130" align="center">
          <template #default="{ row }">
            <span :class="{ 'temp-warn': (row.busbar_temp ?? 0) > 60 }">
              {{ row.busbar_temp?.toFixed(1) ?? '-' }}
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
      <el-empty v-if="!loading && cabinetList.length === 0" description="暂无配电柜数据" />
    </el-card>

    <!-- 支路详情抽屉 -->
    <el-drawer v-model="drawerVisible" :title="drawerTitle" size="560px" direction="rtl">
      <div v-if="detailLoading" v-loading="true" style="height: 200px;" />
      <template v-else-if="branches.length > 0">
        <h4 class="section-title">支路信息</h4>
        <el-table :data="branches" stripe border size="small">
          <el-table-column prop="branch_name" label="支路名称" min-width="120" />
          <el-table-column prop="current" label="电流(A)" width="90" align="center">
            <template #default="{ row }">
              {{ row.current?.toFixed(1) ?? '-' }}
            </template>
          </el-table-column>
          <el-table-column prop="voltage" label="电压(V)" width="90" align="center">
            <template #default="{ row }">
              {{ row.voltage?.toFixed(1) ?? '-' }}
            </template>
          </el-table-column>
          <el-table-column prop="power" label="功率(kW)" width="90" align="center">
            <template #default="{ row }">
              {{ row.power?.toFixed(2) ?? '-' }}
            </template>
          </el-table-column>
          <el-table-column prop="breaker_status" label="开关状态" width="90" align="center">
            <template #default="{ row }">
              <el-tag :type="row.breaker_status === 'on' ? 'success' : 'danger'" size="small">
                {{ row.breaker_status === 'on' ? '合闸' : '分闸' }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
      </template>
      <el-empty v-else description="该配电柜暂无支路/回路数据，请在配电拓扑中配置回路" />
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { Refresh } from '@element-plus/icons-vue'
import { getCabinetList, getCabinetBranches } from '@/api/modules/power'

const loading = ref(false)
const drawerVisible = ref(false)
const detailLoading = ref(false)
const drawerTitle = ref('配电柜详情')

interface CabinetItem {
  id: number
  device_code: string
  device_name: string
  area: string
  total_power?: number
  input_voltage?: number
  output_current?: number
  busbar_temp?: number
  status: string
  branches?: BranchItem[]
}

interface BranchItem {
  branch_name: string
  current?: number
  voltage?: number
  power?: number
  breaker_status: string
}

const cabinetList = ref<CabinetItem[]>([])
const branches = ref<BranchItem[]>([])

const mockCabinetList: CabinetItem[] = [
  {
    id: 1, device_code: 'PDC-A01', device_name: 'A栋总配电柜', area: 'A栋配电间',
    total_power: 85.6, input_voltage: 380.2, output_current: 132.5, busbar_temp: 42.3, status: 'normal',
    branches: [
      { branch_name: 'UPS-A01进线', current: 65.2, voltage: 380.1, power: 42.8, breaker_status: 'on' },
      { branch_name: 'UPS-A02进线', current: 58.3, voltage: 380.0, power: 38.4, breaker_status: 'on' },
      { branch_name: '照明回路', current: 8.5, voltage: 220.1, power: 1.9, breaker_status: 'on' },
      { branch_name: '备用回路', current: 0, voltage: 380.2, power: 0, breaker_status: 'off' }
    ]
  },
  {
    id: 2, device_code: 'PDC-B01', device_name: 'B栋总配电柜', area: 'B栋配电间',
    total_power: 71.2, input_voltage: 379.8, output_current: 108.3, busbar_temp: 38.7, status: 'normal',
    branches: [
      { branch_name: 'UPS-B01进线', current: 52.1, voltage: 379.9, power: 34.2, breaker_status: 'on' },
      { branch_name: 'UPS-B02进线', current: 48.6, voltage: 379.8, power: 31.9, breaker_status: 'on' },
      { branch_name: '空调回路', current: 12.3, voltage: 380.0, power: 8.1, breaker_status: 'on' }
    ]
  }
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
    const res = await getCabinetList()
    const data = res?.data ?? res
    const rawItems = Array.isArray(data) ? data : (data?.items ?? [])
    // API 返回 {device: {...}, points: {...}} 结构，需要展平为前端所需格式
    cabinetList.value = rawItems.map((item: any) => {
      if (item.device) {
        // 后端返回嵌套结构，展平
        const dev = item.device
        const pts = item.points || {}
        // 从点位中提取关键数值（点位 key 格式: {device_code}_{metric}）
        const totalPower = Object.values(pts).find((p: any) => p.name === '总功率')
        const inputVoltageA = Object.values(pts).find((p: any) => p.name === '输入电压A相')
        const outputCurrentA = Object.values(pts).find((p: any) => p.name === '输出电流A相')
        const busTemp = Object.values(pts).find((p: any) => p.name === '母排温度')
        return {
          id: dev.id,
          device_code: dev.device_code,
          device_name: dev.device_name,
          area: dev.area_code || '',
          total_power: (totalPower as any)?.value ?? null,
          input_voltage: (inputVoltageA as any)?.value ?? null,
          output_current: (outputCurrentA as any)?.value ?? null,
          busbar_temp: (busTemp as any)?.value ?? null,
          status: dev.status === 'online' ? 'normal' : dev.status,
        }
      }
      // 已经是展平格式（mock 数据或其他来源）
      return item
    })
  } catch {
    console.warn('配电柜列表API未就绪，使用模拟数据')
    cabinetList.value = mockCabinetList
  } finally {
    loading.value = false
  }
  if (cabinetList.value.length === 0) {
    cabinetList.value = mockCabinetList
  }
}

function openDetail(row: CabinetItem) {
  drawerTitle.value = `${row.device_name} — 支路详情`
  drawerVisible.value = true
  detailLoading.value = true

  // 从后端获取支路数据
  getCabinetBranches(row.id).then((res: any) => {
    const data = res?.data ?? res
    const apiBranches = data?.branches ?? []
    if (apiBranches.length > 0) {
      branches.value = apiBranches
    } else if (row.branches && row.branches.length > 0) {
      branches.value = row.branches
    } else {
      branches.value = []
    }
    detailLoading.value = false
  }).catch(() => {
    // API 失败时回退到行数据或空
    branches.value = row.branches ?? []
    detailLoading.value = false
  })
}

onMounted(() => {
  loadData()
})
</script>

<style scoped lang="scss">
@use '@/styles/mixins-25d' as *;

.cabinet-monitor {
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
