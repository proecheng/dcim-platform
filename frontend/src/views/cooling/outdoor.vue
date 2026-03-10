<template>
  <div class="ac-outdoor-monitor">
    <!-- 顶部汇总 -->
    <el-row :gutter="16" class="summary-bar">
      <el-col :span="8">
        <el-card shadow="hover" class="summary-card">
          <div class="summary-content">
            <span class="summary-label">室外机总数</span>
            <span class="summary-value primary">{{ totalCount }}</span>
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

    <!-- 筛选和设备列表 -->
    <el-card shadow="hover" class="table-card">
      <template #header>
        <div class="card-header">
          <span>室外机设备列表</span>
          <div class="header-actions">
            <el-input
              v-model="searchKeyword"
              placeholder="搜索设备编码/名称"
              clearable
              style="width: 200px; margin-right: 8px;"
              @clear="handleSearch"
              @keyup.enter="handleSearch"
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
            <el-select
              v-model="filterStatus"
              placeholder="状态筛选"
              clearable
              style="width: 120px; margin-right: 8px;"
              @change="handleSearch"
            >
              <el-option label="在线" value="online" />
              <el-option label="离线" value="offline" />
              <el-option label="告警" value="alarm" />
            </el-select>
            <el-button type="primary" link @click="loadData">
              <el-icon><Refresh /></el-icon> 刷新
            </el-button>
          </div>
        </div>
      </template>
      <el-table :data="unitList" stripe border v-loading="loading">
        <el-table-column prop="device_code" label="设备编码" width="140" />
        <el-table-column prop="device_name" label="设备名称" min-width="150" />
        <el-table-column prop="outdoor_temp" label="室外温度" width="120" align="center">
          <template #default="{ row }">
            {{ row.outdoor_temp !== undefined ? `${row.outdoor_temp} ℃` : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="fan_status" label="风机状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.fan_status === '运行' ? 'success' : 'info'" size="small">
              {{ row.fan_status || '-' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="compressor_status" label="压缩机状态" width="120" align="center">
          <template #default="{ row }">
            <el-tag :type="row.compressor_status === '制冷' ? 'success' : 'info'" size="small">
              {{ row.compressor_status || '-' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="high_pressure" label="高压(bar)" width="100" align="center" />
        <el-table-column prop="low_pressure" label="低压(bar)" width="100" align="center" />
        <el-table-column label="操作" width="120" fixed="right" align="center">
          <template #default="{ row }">
            <el-button type="primary" link @click="openDetail(row)">查看详情</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-if="totalCount > 0"
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="totalCount"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="handleSizeChange"
        @current-change="handlePageChange"
        style="margin-top: 16px; justify-content: flex-end;"
      />
      <el-empty v-if="!loading && unitList.length === 0" description="暂无室外机设备数据" />
    </el-card>

    <!-- 详情抽屉 -->
    <el-drawer v-model="drawerVisible" title="室外机详情" size="480px" direction="rtl">
      <div v-if="detailLoading" v-loading="true" style="height: 200px;" />
      <template v-else-if="detail">
        <el-descriptions :column="1" border class="detail-desc">
          <el-descriptions-item label="设备编码">{{ detail.device_code }}</el-descriptions-item>
          <el-descriptions-item label="设备名称">{{ detail.device_name }}</el-descriptions-item>
          <el-descriptions-item label="类型">室外机</el-descriptions-item>
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
import { Refresh, Search } from '@element-plus/icons-vue'
import { getCoolingUnitList, getCoolingUnitDetail } from '@/api/modules/cooling'

const loading = ref(false)
const drawerVisible = ref(false)
const detailLoading = ref(false)
const currentPage = ref(1)
const pageSize = ref(20)
const searchKeyword = ref('')
const filterStatus = ref('')

interface OutdoorUnit {
  id: number
  device_code: string
  device_name: string
  outdoor_temp?: number
  fan_status?: string
  compressor_status?: string
  high_pressure?: number
  low_pressure?: number
  status: string
}

interface OutdoorDetailData {
  device_code: string
  device_name: string
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

const unitList = ref<OutdoorUnit[]>([])
const totalCount = ref(0)  // 总数
const detail = ref<OutdoorDetailData | null>(null)
const detailParams = ref<DetailParam[]>([])

const mockOutdoorList: OutdoorUnit[] = [
  { id: 10, device_code: 'ACO-A01', device_name: 'A区室外机组', outdoor_temp: 28.5, fan_status: '运行', compressor_status: '制冷', high_pressure: 2.5, low_pressure: 0.5, status: 'online' },
]

const mockOutdoorDetailParams: DetailParam[] = [
  { key: 'outdoor_temp', label: '室外环境温度', value: '28.5', unit: '℃', status: 'normal' },
  { key: 'fan_status', label: '风机状态', value: '运行', unit: '', status: 'normal' },
  { key: 'compressor_status', label: '压缩机状态', value: '制冷', unit: '', status: 'normal' },
  { key: 'high_pressure', label: '高压压力', value: '2.5', unit: 'bar', status: 'normal' },
  { key: 'low_pressure', label: '低压压力', value: '0.5', unit: 'bar', status: 'normal' },
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
    const params: Record<string, unknown> = {
      unit_type: 'outdoor',
      page: currentPage.value,
      page_size: pageSize.value
    }
    if (searchKeyword.value) {
      params.keyword = searchKeyword.value
    }
    if (filterStatus.value) {
      params.status = filterStatus.value
    }
    const res = await getCoolingUnitList(params)
    const data = res?.data ?? res
    unitList.value = Array.isArray(data) ? data : (data?.items ?? [])
    totalCount.value = data?.total ?? unitList.value.length
  } catch {
    console.warn('室外机列表API未就绪，使用模拟数据')
    unitList.value = mockOutdoorList
    totalCount.value = mockOutdoorList.length
  } finally {
    loading.value = false
  }
}

async function openDetail(row: OutdoorUnit) {
  drawerVisible.value = true
  detailLoading.value = true
  detail.value = null
  detailParams.value = []
  try {
    const res = await getCoolingUnitDetail(row.id)
    const data = (res as any)?.data ?? res
    // API返回 {unit: {...}, device: {...}, points: [...]}
    const unitData = data?.unit ?? data
    detail.value = {
      device_code: unitData?.device_code ?? row.device_code,
      device_name: unitData?.device_name ?? row.device_name,
      cooling_capacity_kw: unitData?.cooling_capacity_kw ?? row.cooling_capacity_kw,
      points: data?.points ?? unitData?.points ?? []
    }
    if (detail.value.points && detail.value.points.length > 0) {
      detailParams.value = detail.value.points.map((p: any, i: number) => ({
        key: String(i),
        label: p.point_name,
        value: p.value !== null && p.value !== undefined ? String(p.value) : '-',
        unit: p.unit || '',
        status: p.status || 'normal'
      }))
    } else {
      detailParams.value = []
    }
  } catch {
    console.warn('室外机详情API未就绪，使用模拟数据')
    detail.value = { device_code: row.device_code, device_name: row.device_name, cooling_capacity_kw: row.cooling_capacity_kw }
    detailParams.value = mockOutdoorDetailParams
  } finally {
    detailLoading.value = false
  }
}
function handleSearch() {
  currentPage.value = 1
  loadData()
}
function handlePageChange() {
  loadData()
}
function handleSizeChange() {
  currentPage.value = 1
  loadData()
}

onMounted(() => {
  loadData()
})
</script>

<style scoped lang="scss">
@use '@/styles/mixins-25d' as *;

.ac-outdoor-monitor {
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
    .header-actions {
      display: flex;
      align-items: center;
    }
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
