<template>
  <div class="ac-indoor-monitor">
    <!-- 顶部汇总 -->
    <el-row :gutter="16" class="summary-bar">
      <el-col :span="8">
        <el-card shadow="hover" class="summary-card">
          <div class="summary-content">
            <span class="summary-label">AC总数</span>
            <span class="summary-value primary">{{ unitList.length }}</span>
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

    <!-- 设备列表 -->
    <el-card shadow="hover" class="table-card">
      <template #header>
        <div class="card-header">
          <span>精密空调设备列表</span>
          <el-button type="primary" link @click="loadData">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
        </div>
      </template>
      <el-table :data="unitList" stripe border v-loading="loading">
        <el-table-column prop="device_code" label="设备编码" width="140" />
        <el-table-column prop="device_name" label="设备名称" min-width="150" />
        <el-table-column prop="unit_type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag :type="row.unit_type === 'indoor' ? 'primary' : 'warning'" size="small">
              {{ row.unit_type === 'indoor' ? '室内机' : '室外机' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="cooling_capacity_kw" label="制冷量(kW)" width="120" align="center" />
        <el-table-column prop="supply_temp" label="送风温度" width="120" align="center">
          <template #default="{ row }">
            {{ row.supply_temp !== undefined ? `${row.supply_temp} ℃` : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="return_temp" label="回风温度" width="120" align="center">
          <template #default="{ row }">
            {{ row.return_temp !== undefined ? `${row.return_temp} ℃` : '-' }}
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
      <el-empty v-if="!loading && unitList.length === 0" description="暂无精密空调设备数据" />
    </el-card>

    <!-- 详情抽屉 -->
    <el-drawer v-model="drawerVisible" title="精密空调详情" size="480px" direction="rtl">
      <div v-if="detailLoading" v-loading="true" style="height: 200px;" />
      <template v-else-if="detail">
        <el-descriptions :column="1" border class="detail-desc">
          <el-descriptions-item label="设备编码">{{ detail.device_code }}</el-descriptions-item>
          <el-descriptions-item label="设备名称">{{ detail.device_name }}</el-descriptions-item>
          <el-descriptions-item label="类型">
            {{ detail.unit_type === 'indoor' ? '室内机' : '室外机' }}
          </el-descriptions-item>
          <el-descriptions-item label="制冷量">{{ detail.cooling_capacity_kw }} kW</el-descriptions-item>
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
import { getCoolingUnitList, getCoolingUnitDetail } from '@/api/modules/cooling'

const loading = ref(false)
const drawerVisible = ref(false)
const detailLoading = ref(false)

interface ACUnit {
  id: number
  device_code: string
  device_name: string
  unit_type: string
  cooling_capacity_kw: number
  supply_temp?: number
  return_temp?: number
  status: string
}

interface ACDetailData {
  device_code: string
  device_name: string
  unit_type: string
  cooling_capacity_kw: number
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

const unitList = ref<ACUnit[]>([])
const detail = ref<ACDetailData | null>(null)
const detailParams = ref<DetailParam[]>([])

const mockUnitList: ACUnit[] = [
  { id: 1, device_code: 'AC-A01', device_name: 'A区1号精密空调', unit_type: 'indoor', cooling_capacity_kw: 50, supply_temp: 18.5, return_temp: 32.1, status: 'online' },
  { id: 2, device_code: 'AC-A02', device_name: 'A区2号精密空调', unit_type: 'indoor', cooling_capacity_kw: 50, supply_temp: 19.2, return_temp: 31.8, status: 'online' },
  { id: 3, device_code: 'AC-B01', device_name: 'B区1号精密空调', unit_type: 'indoor', cooling_capacity_kw: 40, supply_temp: 20.1, return_temp: 33.5, status: 'alarm' },
]

const mockDetailParams: DetailParam[] = [
  { key: 'cooling_output', label: '制冷量', value: '35.2', unit: 'kW', status: 'normal' },
  { key: 'supply_temp', label: '送风温度', value: '18.5', unit: '℃', status: 'normal' },
  { key: 'return_temp', label: '回风温度', value: '32.1', unit: '℃', status: 'normal' },
  { key: 'supply_humidity', label: '送风湿度', value: '50.2', unit: '%RH', status: 'normal' },
  { key: 'return_humidity', label: '回风湿度', value: '52.8', unit: '%RH', status: 'normal' },
  { key: 'chilled_supply', label: '冷冻水供水温度', value: '7.2', unit: '℃', status: 'normal' },
  { key: 'chilled_return', label: '冷冻水回水温度', value: '12.1', unit: '℃', status: 'normal' },
  { key: 'cooling_supply', label: '冷却水出水温度', value: '32.5', unit: '℃', status: 'normal' },
  { key: 'cooling_return', label: '冷却水进水温度', value: '28.3', unit: '℃', status: 'normal' },
  { key: 'fan_count', label: '风机数量', value: '2', unit: '台', status: 'normal' },
  { key: 'pressure_diff', label: '平均压差', value: '48.5', unit: 'Pa', status: 'normal' },
  { key: 'compressor_v', label: '压缩机电压', value: '380.2', unit: 'V', status: 'normal' },
  { key: 'compressor_a', label: '压缩机电流', value: '25.3', unit: 'A', status: 'normal' },
  { key: 'humidify', label: '加湿输出', value: '30.5', unit: '%', status: 'normal' },
  { key: 'dehumidify', label: '除湿输出', value: '15.2', unit: '%', status: 'normal' },
  { key: 'on_off', label: '开关机状态', value: '运行', unit: '', status: 'normal' },
  { key: 'filter', label: '过滤器状态', value: '正常', unit: '', status: 'normal' },
  { key: 'fan_status', label: '风机状态', value: '运行', unit: '', status: 'normal' },
  { key: 'compressor_status', label: '压缩机状态', value: '制冷', unit: '', status: 'normal' },
  { key: 'refrigerant', label: '制冷剂泄漏', value: '正常', unit: '', status: 'normal' },
  { key: 'group_ctrl', label: '群控状态', value: '联动', unit: '', status: 'normal' },
]

const onlineCount = computed(() => unitList.value.filter(u => u.status === 'online' || u.status === 'normal').length)
const alarmCount = computed(() => unitList.value.filter(u => u.status === 'alarm').length)

type TagType = 'success' | 'warning' | 'danger' | 'info'

function statusTagType(status: string): TagType {
  const map: Record<string, TagType> = { normal: 'success', online: 'success', alarm: 'danger', warning: 'warning', offline: 'info' }
  return map[status] || 'info'
}

function statusLabel(status: string): string {
  const map: Record<string, string> = { normal: '正常', online: '在线', alarm: '告警', warning: '预警', offline: '离线' }
  return map[status] || status
}

async function loadData() {
  loading.value = true
  try {
    const res = await getCoolingUnitList({ unit_type: 'indoor' })
    const data = res?.data ?? res
    unitList.value = Array.isArray(data) ? data : (data?.items ?? [])
  } catch {
    console.warn('精密空调列表API未就绪，使用模拟数据')
    unitList.value = mockUnitList
  } finally {
    loading.value = false
  }
}

async function openDetail(row: ACUnit) {
  drawerVisible.value = true
  detailLoading.value = true
  detail.value = null
  detailParams.value = []
  try {
    const res = await getCoolingUnitDetail(row.id)
    const data = res?.data ?? res
    detail.value = data as ACDetailData
    if (detail.value?.points && detail.value.points.length > 0) {
      detailParams.value = detail.value.points.map((p, i) => ({
        key: String(i),
        label: p.point_name,
        value: p.value !== null ? String(p.value) : '-',
        unit: p.unit || '',
        status: p.status || 'normal'
      }))
    } else {
      detailParams.value = []
    }
  } catch {
    console.warn('精密空调详情API未就绪，使用模拟数据')
    detail.value = { device_code: row.device_code, device_name: row.device_name, unit_type: row.unit_type, cooling_capacity_kw: row.cooling_capacity_kw }
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
@use '@/styles/mixins-25d' as *;

.ac-indoor-monitor {
  @include page-list;
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
