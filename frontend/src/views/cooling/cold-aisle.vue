<template>
  <div class="cold-aisle-page">
    <!-- 汇总卡片 -->
    <el-row :gutter="16" class="summary-bar">
      <el-col :span="12">
        <el-card shadow="hover" class="summary-card">
          <div class="summary-content">
            <span class="summary-label">冷通道总数</span>
            <span class="summary-value primary">{{ totalCount }}</span>
          </div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="hover" class="summary-card">
          <div class="summary-content">
            <span class="summary-label">天窗开启数</span>
            <span class="summary-value danger">{{ skylightOpenCount }}</span>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 筛选和冷通道列表 -->
    <el-card shadow="hover" class="table-card">
      <template #header>
        <div class="card-header">
          <span>冷通道列表</span>
          <div class="header-actions">
            <el-input
              v-model="searchKeyword"
              placeholder="搜索通道编码/名称"
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
              v-model="filterSkylightStatus"
              placeholder="天窗状态"
              clearable
              style="width: 120px; margin-right: 8px;"
              @change="handleSearch"
            >
              <el-option label="全部关闭" value="closed" />
              <el-option label="有开启" value="open" />
            </el-select>
            <el-button type="primary" link @click="loadData">
              <el-icon><Refresh /></el-icon> 刷新
            </el-button>
          </div>
        </div>
      </template>
      <el-table :data="aisleList" stripe border v-loading="loading">
        <el-table-column prop="aisle_code" label="通道编码" width="140" />
        <el-table-column prop="aisle_name" label="通道名称" min-width="150" />
        <el-table-column prop="skylight_count" label="天窗数量" width="100" align="center" />
        <el-table-column prop="location" label="位置" width="150" />
        <el-table-column prop="skylight_open" label="天窗状态" width="150">
          <template #default="{ row }">
            <span v-if="row.skylight_open === 0" style="color: var(--success-color, #52c41a);">● 全部关闭</span>
            <span v-else style="color: var(--error-color, #f5222d);">● 有开启</span>
          </template>
        </el-table-column>
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
      <el-empty v-if="!loading && aisleList.length === 0" description="暂无冷通道数据" />
    </el-card>

    <!-- 详情抽屉 -->
    <el-drawer v-model="drawerVisible" title="冷通道详情" size="480px" direction="rtl">
      <div v-if="detailLoading" v-loading="true" style="height: 200px;" />
      <template v-else-if="currentAisle">
        <el-descriptions :column="1" border class="detail-desc">
          <el-descriptions-item label="编码">{{ currentAisle.aisle_code }}</el-descriptions-item>
          <el-descriptions-item label="名称">{{ currentAisle.aisle_name }}</el-descriptions-item>
          <el-descriptions-item label="天窗数量">{{ currentAisle.skylight_count }}</el-descriptions-item>
          <el-descriptions-item label="位置">{{ currentAisle.location ?? '-' }}</el-descriptions-item>
        </el-descriptions>

        <h4 class="section-title">天窗状态</h4>
        <div class="skylight-list">
          <div v-for="item in skylightList" :key="item.index" class="skylight-row">
            <span class="skylight-label">天窗 #{{ item.index }}</span>
            <el-tag :type="item.status === 'closed' ? 'success' : 'warning'" size="small">
              {{ item.status === 'closed' ? '关闭' : '开启' }}
            </el-tag>
          </div>
        </div>
      </template>
      <el-empty v-else description="暂无详情数据" />
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { Refresh, Search } from '@element-plus/icons-vue'
import { getColdAisleList, getColdAisleDetail } from '@/api/modules/cooling'

const loading = ref(false)
const drawerVisible = ref(false)
const detailLoading = ref(false)
const currentPage = ref(1)
const pageSize = ref(20)
const searchKeyword = ref('')
const filterSkylightStatus = ref('')

interface AisleItem {
  id: number
  aisle_code: string
  aisle_name: string
  skylight_count: number
  location: string | null
  skylight_open: number
}

interface SkylightItem {
  index: number
  status: string
}

const aisleList = ref<AisleItem[]>([])
const totalCount = ref(0)  // 总数
const currentAisle = ref<AisleItem | null>(null)
const skylightList = ref<SkylightItem[]>([])

const mockAisleList: AisleItem[] = [
  { id: 1, aisle_code: 'CA-A01', aisle_name: 'A区冷通道', skylight_count: 4, location: 'A区机房', skylight_open: 0 },
  { id: 2, aisle_code: 'CA-B01', aisle_name: 'B区冷通道', skylight_count: 3, location: 'B区机房', skylight_open: 1 },
]

const mockSkylights: SkylightItem[] = [
  { index: 1, status: 'closed' },
  { index: 2, status: 'closed' },
  { index: 3, status: 'closed' },
  { index: 4, status: 'open' },
]

const skylightOpenCount = computed(() =>
  aisleList.value.reduce((sum, a) => sum + (a.skylight_open || 0), 0)
)

async function loadData() {
  loading.value = true
  try {
    const params: Record<string, unknown> = {
      page: currentPage.value,
      page_size: pageSize.value
    }
    if (searchKeyword.value) {
      params.keyword = searchKeyword.value
    }
    if (filterSkylightStatus.value) {
      params.skylight_status = filterSkylightStatus.value
    }
    const res = await getColdAisleList(params)
    const data = res?.data ?? res
    aisleList.value = Array.isArray(data) ? data : (data?.items ?? [])
    totalCount.value = data?.total ?? aisleList.value.length
  } catch {
    console.warn('冷通道列表API未就绪，使用模拟数据')
    aisleList.value = mockAisleList
    totalCount.value = mockAisleList.length
  } finally {
    loading.value = false
  }
}

async function openDetail(row: AisleItem) {
  drawerVisible.value = true
  detailLoading.value = true
  currentAisle.value = null
  skylightList.value = []
  try {
    const res = await getColdAisleDetail(row.id)
    const data = (res as any)?.data ?? res
    // API返回 {aisle: {...}, device: {...}, points: [...]}
    const aisleData = data?.aisle ?? data
    currentAisle.value = {
      id: aisleData?.id ?? row.id,
      aisle_code: aisleData?.aisle_code ?? aisleData?.device_code ?? row.aisle_code,
      aisle_name: aisleData?.aisle_name ?? aisleData?.device_name ?? row.aisle_name,
      skylight_count: aisleData?.skylight_count ?? row.skylight_count,
      location: aisleData?.location ?? row.location,
      skylight_open: aisleData?.skylight_open ?? row.skylight_open
    }
    // 点位数据来自 points 字段，转换为天窗状态展示
    const points = data?.points ?? aisleData?.points ?? []
    if (points.length > 0) {
      skylightList.value = points.map((p: any, i: number) => ({
        index: i + 1,
        status: p.value !== null && p.value !== undefined && Number(p.value) > 0 ? 'open' : 'closed'
      }))
    } else {
      // 如果没有点位数据，根据 skylight_count 和 skylight_open 模拟
      const count = currentAisle.value.skylight_count || 0
      const openCount = currentAisle.value.skylight_open || 0
      skylightList.value = Array.from({ length: count }, (_, i) => ({
        index: i + 1,
        status: i < (count - openCount) ? 'closed' : 'open'
      }))
    }
  } catch {
    console.warn('冷通道详情API未就绪，使用模拟数据')
    currentAisle.value = row
    skylightList.value = mockSkylights
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

.cold-aisle-page {
  @include page-dashboard(2);
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

  .section-title {
    margin: 20px 0 12px;
    font-size: 15px;
    font-weight: 600;
    color: var(--text-primary);
  }

  .detail-desc {
    margin-bottom: 8px;
  }

  .skylight-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .skylight-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 12px;
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: 4px;
  }

  .skylight-label {
    font-size: 14px;
    color: var(--text-primary);
  }
}
</style>
