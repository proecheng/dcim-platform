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

    <!-- 冷通道列表 -->
    <el-card shadow="hover" class="table-card">
      <template #header>
        <div class="card-header">
          <span>冷通道列表</span>
          <el-button type="primary" link @click="loadData">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
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
import { Refresh } from '@element-plus/icons-vue'
import { getColdAisleList, getColdAisleDetail } from '@/api/modules/cooling'

const loading = ref(false)
const drawerVisible = ref(false)
const detailLoading = ref(false)

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
    const res = await getColdAisleList()
    const data = res?.data ?? res
    aisleList.value = Array.isArray(data) ? data : (data?.items ?? [])
    totalCount.value = data?.total ?? aisleList.value.length
  } catch {
    console.warn('冷通道列表API未就绪，使用模拟数据')
    aisleList.value = mockAisleList
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
    const data = res?.data ?? res
    currentAisle.value = data as AisleItem
    skylightList.value = data?.skylights ?? []
  } catch {
    console.warn('冷通道详情API未就绪，使用模拟数据')
    currentAisle.value = row
    skylightList.value = mockSkylights
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
