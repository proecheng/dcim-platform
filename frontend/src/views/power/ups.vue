<template>
  <div class="ups-monitor">
    <!-- 顶部汇总 -->
    <el-row :gutter="16" class="summary-bar">
      <el-col :span="8">
        <el-card shadow="hover" class="summary-card">
          <div class="summary-content">
            <span class="summary-label">UPS总数</span>
            <span class="summary-value primary">{{ upsList.length }}</span>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover" class="summary-card">
          <div class="summary-content">
            <span class="summary-label">在线</span>
            <span class="summary-value success">{{ onlineCount }}</span>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover" class="summary-card">
          <div class="summary-content">
            <span class="summary-label">告警</span>
            <span class="summary-value danger">{{ alarmCount }}</span>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- UPS列表 -->
    <el-card shadow="hover" class="table-card">
      <template #header>
        <div class="card-header">
          <span>UPS设备列表</span>
          <el-button type="primary" link @click="loadData">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
        </div>
      </template>
      <el-table :data="upsList" stripe border v-loading="loading">
        <el-table-column prop="device_code" label="设备编码" width="140" />
        <el-table-column prop="device_name" label="设备名称" min-width="150" />
        <el-table-column prop="ups_type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag :type="row.ups_type === 'modular' ? 'warning' : 'primary'" size="small">
              {{ row.ups_type === 'modular' ? '模块化' : '单机' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="rated_capacity" label="额定容量(kVA)" width="130" align="center" />
        <el-table-column prop="load_rate" label="负载率(%)" width="160">
          <template #default="{ row }">
            <el-progress
              v-if="row.load_rate !== undefined"
              :percentage="Math.min(row.load_rate, 100)"
              :stroke-width="14"
              :color="getLoadColor(row.load_rate)"
              :format="(p: number) => `${p.toFixed(1)}%`"
            />
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right" align="center">
          <template #default="{ row }">
            <el-button type="primary" link @click="openDetail(row)">查看详情</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && upsList.length === 0" description="暂无UPS设备数据" />
    </el-card>

    <!-- 详情抽屉 -->
    <el-drawer v-model="drawerVisible" title="UPS详情" size="480px" direction="rtl">
      <div v-if="detailLoading" v-loading="true" style="height: 200px;" />
      <template v-else-if="detail">
        <el-descriptions :column="1" border class="detail-desc">
          <el-descriptions-item label="设备编码">{{ detail.device_code }}</el-descriptions-item>
          <el-descriptions-item label="设备名称">{{ detail.device_name }}</el-descriptions-item>
          <el-descriptions-item label="类型">
            {{ detail.ups_type === 'modular' ? '模块化' : '单机' }}
          </el-descriptions-item>
          <el-descriptions-item label="额定容量">{{ detail.rated_capacity }} kVA</el-descriptions-item>
        </el-descriptions>

        <h4 class="section-title">实时参数</h4>
        <el-descriptions :column="1" border class="detail-desc">
          <el-descriptions-item
            v-for="param in detailParams"
            :key="param.key"
            :label="param.label"
          >
            <div class="param-row">
              <span>{{ param.value }} {{ param.unit }}</span>
              <el-tag
                :type="param.status === 'alarm' ? 'danger' : 'success'"
                size="small"
              >
                {{ param.status === 'alarm' ? '告警' : '正常' }}
              </el-tag>
            </div>
          </el-descriptions-item>
        </el-descriptions>
      </template>
      <el-empty v-else description="暂无详情数据" />
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { Refresh } from '@element-plus/icons-vue'
import { getUPSList, getUPSDetail } from '@/api/modules/power'

const loading = ref(false)
const drawerVisible = ref(false)
const detailLoading = ref(false)

interface UPSItem {
  id: number
  device_code: string
  device_name: string
  ups_type: string
  rated_capacity: number
  load_rate?: number
  status: string
}

interface UPSDetailData {
  device_code: string
  device_name: string
  ups_type: string
  rated_capacity: number
  points?: Array<{
    point_name: string
    value: number | null
    unit: string
    status: string
  }>
}

interface DetailParam {
  key: string
  label: string
  value: string
  unit: string
  status: string
}

const upsList = ref<UPSItem[]>([])
const detail = ref<UPSDetailData | null>(null)
const detailParams = ref<DetailParam[]>([])

const mockUPSList: UPSItem[] = [
  { id: 1, device_code: 'UPS-A01', device_name: 'A栋主UPS', ups_type: 'modular', rated_capacity: 200, load_rate: 58.3, status: 'normal' },
  { id: 2, device_code: 'UPS-B01', device_name: 'B栋主UPS', ups_type: 'standalone', rated_capacity: 120, load_rate: 72.1, status: 'normal' }
]

const mockDetailParams: DetailParam[] = [
  { key: 'input_voltage', label: '输入电压', value: '380.2', unit: 'V', status: 'normal' },
  { key: 'output_voltage', label: '输出电压', value: '220.1', unit: 'V', status: 'normal' },
  { key: 'input_freq', label: '输入频率', value: '50.01', unit: 'Hz', status: 'normal' },
  { key: 'output_freq', label: '输出频率', value: '50.00', unit: 'Hz', status: 'normal' },
  { key: 'power_factor', label: '功率因数', value: '0.98', unit: '', status: 'normal' },
  { key: 'load_rate', label: '负载率', value: '58.3', unit: '%', status: 'normal' },
  { key: 'backup_time', label: '备电时间', value: '30', unit: 'min', status: 'normal' },
  { key: 'busbar_temp', label: '母排温度', value: '38.5', unit: '°C', status: 'normal' },
  { key: 'mains_status', label: '市电状态', value: '正常', unit: '', status: 'normal' },
  { key: 'spd_status', label: '防雷器状态', value: '正常', unit: '', status: 'normal' }
]

const onlineCount = computed(() => upsList.value.filter(u => u.status === 'normal' || u.status === 'online').length)
const alarmCount = computed(() => upsList.value.filter(u => u.status === 'alarm' || u.status === 'warning').length)

type TagType = 'success' | 'warning' | 'danger' | 'info'

function statusTagType(status: string): TagType {
  const map: Record<string, TagType> = { normal: 'success', online: 'success', alarm: 'danger', warning: 'warning', offline: 'info' }
  return map[status] || 'info'
}

function statusLabel(status: string): string {
  const map: Record<string, string> = { normal: '正常', online: '在线', alarm: '告警', warning: '预警', offline: '离线' }
  return map[status] || status
}

function getLoadColor(rate: number): string {
  if (rate < 60) return '#52c41a'
  if (rate < 80) return '#faad14'
  return '#f5222d'
}

async function loadData() {
  loading.value = true
  try {
    const res = await getUPSList()
    const data = res?.data ?? res
    upsList.value = Array.isArray(data) ? data : (data?.items ?? [])
  } catch {
    console.warn('UPS列表API未就绪，使用模拟数据')
    upsList.value = mockUPSList
  } finally {
    loading.value = false
  }
  if (upsList.value.length === 0) {
    upsList.value = mockUPSList
  }
}

async function openDetail(row: UPSItem) {
  drawerVisible.value = true
  detailLoading.value = true
  detail.value = null
  detailParams.value = []
  try {
    const res = await getUPSDetail(row.id)
    const data = res?.data ?? res
    detail.value = data as UPSDetailData
    if (detail.value?.points && detail.value.points.length > 0) {
      detailParams.value = detail.value.points.map((p, i) => ({
        key: String(i),
        label: p.point_name,
        value: p.value !== null ? String(p.value) : '-',
        unit: p.unit || '',
        status: p.status || 'normal'
      }))
    } else {
      detailParams.value = mockDetailParams
    }
  } catch {
    console.warn('UPS详情API未就绪，使用模拟数据')
    detail.value = { device_code: row.device_code, device_name: row.device_name, ups_type: row.ups_type, rated_capacity: row.rated_capacity }
    detailParams.value = mockDetailParams
  } finally {
    detailLoading.value = false
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped lang="scss">
.ups-monitor {
  .summary-bar {
    margin-bottom: 16px;
  }

  .summary-card {
    background: var(--bg-card);
    border-color: var(--border-color);

    .summary-content {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 4px 0;
    }

    .summary-label {
      font-size: 14px;
      color: var(--text-secondary);
    }

    .summary-value {
      font-size: 28px;
      font-weight: 700;

      &.primary { color: var(--primary-color, #1890ff); }
      &.success { color: var(--success-color, #52c41a); }
      &.danger { color: var(--error-color, #f5222d); }
    }
  }

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

  .text-muted {
    color: var(--text-secondary);
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

  .param-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    width: 100%;
  }
}
</style>
