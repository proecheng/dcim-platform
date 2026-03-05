<template>
  <div class="group-control-page">
    <!-- 汇总卡片 -->
    <el-row :gutter="16" class="summary-bar">
      <el-col :span="8">
        <el-card shadow="hover" class="summary-card">
          <div class="summary-content">
            <span class="summary-label">群控组总数</span>
            <span class="summary-value primary">{{ totalCount }}</span>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover" class="summary-card">
          <div class="summary-content">
            <span class="summary-label">联动模式</span>
            <span class="summary-value success">{{ linkedCount }}</span>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover" class="summary-card">
          <div class="summary-content">
            <span class="summary-label">独立模式</span>
            <span class="summary-value danger">{{ independentCount }}</span>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 筛选和群控组列表 -->
    <el-card shadow="hover" class="table-card">
      <template #header>
        <div class="card-header">
          <span>群控组列表</span>
          <div class="header-actions">
            <el-input
              v-model="searchKeyword"
              placeholder="搜索组名称"
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
              v-model="filterMode"
              placeholder="模式筛选"
              clearable
              style="width: 120px; margin-right: 8px;"
              @change="handleSearch"
            >
              <el-option label="联动" value="linked" />
              <el-option label="独立" value="independent" />
            </el-select>
            <el-button type="primary" link @click="loadData">
              <el-icon><Refresh /></el-icon> 刷新
            </el-button>
          </div>
        </div>
      </template>
      <el-table :data="groupList" stripe border v-loading="loading">
        <el-table-column prop="group_name" label="组名称" min-width="150" />
        <el-table-column prop="group_mode" label="模式" width="120">
          <template #default="{ row }">
            <el-tag :type="row.group_mode === 'linked' ? 'success' : 'info'" size="small">
              {{ row.group_mode === 'linked' ? '联动' : '独立' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="unit_count" label="空调数量" width="100" align="center" />
        <el-table-column prop="description" label="描述" min-width="200" />
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
      <el-empty v-if="!loading && groupList.length === 0" description="暂无群控组数据" />
    </el-card>

    <!-- 详情抽屉 -->
    <el-drawer v-model="drawerVisible" title="群控组详情" size="480px" direction="rtl">
      <div v-if="detailLoading" v-loading="true" style="height: 200px;" />
      <template v-else-if="currentGroup">
        <el-descriptions :column="1" border class="detail-desc">
          <el-descriptions-item label="名称">{{ currentGroup.group_name }}</el-descriptions-item>
          <el-descriptions-item label="模式">
            <el-tag :type="currentGroup.group_mode === 'linked' ? 'success' : 'info'" size="small">
              {{ currentGroup.group_mode === 'linked' ? '联动' : '独立' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="描述">{{ currentGroup.description ?? '-' }}</el-descriptions-item>
        </el-descriptions>

        <h4 class="section-title">组内空调</h4>
        <el-table :data="memberUnits" stripe border size="small">
          <el-table-column prop="device_code" label="设备编码" width="140" />
          <el-table-column prop="device_name" label="名称" min-width="150" />
          <el-table-column prop="status" label="状态" width="90" align="center">
            <template #default="{ row }">
              <el-tag :type="row.status === 'online' ? 'success' : 'info'" size="small">
                {{ row.status === 'online' ? '在线' : '离线' }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
      </template>
      <el-empty v-else description="暂无详情数据" />
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { Refresh, Search } from '@element-plus/icons-vue'
import { getCoolingGroupList, getCoolingUnitList } from '@/api/modules/cooling'

const loading = ref(false)
const drawerVisible = ref(false)
const detailLoading = ref(false)
const currentPage = ref(1)
const pageSize = ref(20)
const searchKeyword = ref('')
const filterMode = ref('')

interface GroupItem {
  id: number
  group_name: string
  group_mode: string
  unit_count: number
  description: string | null
}

interface MemberUnit {
  device_code: string
  device_name: string
  status: string
}

const groupList = ref<GroupItem[]>([])
const totalCount = ref(0)  // 总数
const currentGroup = ref<GroupItem | null>(null)
const memberUnits = ref<MemberUnit[]>([])

const mockGroupList: GroupItem[] = [
  { id: 1, group_name: 'A区群控组', group_mode: 'linked', unit_count: 2, description: 'A区精密空调联动控制' },
  { id: 2, group_name: 'B区群控组', group_mode: 'independent', unit_count: 1, description: 'B区独立运行' },
]

const mockMemberUnits: MemberUnit[] = [
  { device_code: 'AC-A01', device_name: 'A区1号精密空调', status: 'online' },
  { device_code: 'AC-A02', device_name: 'A区2号精密空调', status: 'online' },
]

const linkedCount = computed(() =>
  groupList.value.filter(g => g.group_mode === 'linked').length
)
const independentCount = computed(() =>
  groupList.value.filter(g => g.group_mode === 'independent').length
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
    if (filterMode.value) {
      params.group_mode = filterMode.value
    }
    const res = await getCoolingGroupList(params)
    const data = res?.data ?? res
    groupList.value = Array.isArray(data) ? data : (data?.items ?? [])
    totalCount.value = data?.total ?? groupList.value.length
  } catch {
    console.warn('群控组列表API未就绪，使用模拟数据')
    groupList.value = mockGroupList
    totalCount.value = mockGroupList.length
  } finally {
    loading.value = false
  }
}

async function openDetail(row: GroupItem) {
  drawerVisible.value = true
  detailLoading.value = true
  currentGroup.value = null
  memberUnits.value = []
  try {
    const res = await getCoolingUnitList({ group_id: row.id })
    const data = res?.data ?? res
    currentGroup.value = row
    memberUnits.value = Array.isArray(data) ? data : (data?.items ?? [])
  } catch {
    console.warn('群控组详情API未就绪，使用模拟数据')
    currentGroup.value = row
    memberUnits.value = mockMemberUnits
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

.group-control-page {
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
