<template>
  <div class="shift-execution-list">
    <el-card class="filter-card">
      <el-form :inline="true" :model="filterForm">
        <el-form-item label="执行状态">
          <el-select v-model="filterForm.status" placeholder="全部状态" clearable style="width: 150px">
            <el-option label="待执行" value="pending" />
            <el-option label="执行中" value="executing" />
            <el-option label="已完成" value="completed" />
            <el-option label="失败" value="failed" />
            <el-option label="已取消" value="cancelled" />
            <el-option label="已回滚" value="reverted" />
          </el-select>
        </el-form-item>
        <el-form-item label="日期范围">
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            style="width: 240px"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleQuery">查询</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="table-card">
      <el-table :data="executionList" v-loading="loading" stripe>
        <el-table-column prop="execution_code" label="执行编号" width="180" />
        <el-table-column prop="plan_name" label="计划名称" min-width="200" />
        <el-table-column label="执行时间" width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.start_time) }}
          </template>
        </el-table-column>
        <el-table-column prop="actual_shift_power" label="实际功率(kW)" width="120" align="right">
          <template #default="{ row }">
            {{ row.actual_shift_power?.toFixed(1) || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="actual_cost_saving" label="实际节省(元)" width="120" align="right">
          <template #default="{ row }">
            {{ row.actual_cost_saving?.toFixed(2) || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="成功率" width="100" align="center">
          <template #default="{ row }">
            <el-progress
              v-if="row.success_rate !== null"
              :percentage="row.success_rate * 100"
              :color="getSuccessRateColor(row.success_rate)"
              :stroke-width="8"
            />
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ getStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="handleView(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="handleQuery"
        @current-change="handleQuery"
        style="margin-top: 20px; justify-content: flex-end"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getExecutions, type ShiftExecution, type ShiftExecutionQuery } from '@/api/modules/shift'

const router = useRouter()

const loading = ref(false)
const executionList = ref<ShiftExecution[]>([])
const dateRange = ref<Date[]>([])

const filterForm = reactive({
  status: ''
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

onMounted(() => {
  fetchExecutions()
})

const fetchExecutions = async () => {
  loading.value = true
  try {
    const params: ShiftExecutionQuery = {
      skip: (pagination.page - 1) * pagination.pageSize,
      limit: pagination.pageSize
    }
    
    if (filterForm.status) {
      params.status = filterForm.status
    }
    
    if (dateRange.value && dateRange.value.length === 2) {
      params.start_date = dateRange.value[0].toISOString().split('T')[0]
      params.end_date = dateRange.value[1].toISOString().split('T')[0]
    }
    
    const res = await getExecutions(params)
    executionList.value = res.data || []
    pagination.total = res.total || executionList.value.length
  } catch {
    ElMessage.error('获取执行记录失败')
  } finally {
    loading.value = false
  }
}

const handleQuery = () => {
  pagination.page = 1
  fetchExecutions()
}

const handleReset = () => {
  filterForm.status = ''
  dateRange.value = []
  handleQuery()
}

const handleView = (row: ShiftExecution) => {
  router.push(`/energy/shift/execution/${row.id}`)
}

const formatDateTime = (datetime: string) => {
  if (!datetime) return '-'
  return datetime.replace('T', ' ').substring(0, 16)
}

const getSuccessRateColor = (rate: number) => {
  if (rate >= 0.9) return '#67c23a'
  if (rate >= 0.7) return '#e6a23c'
  return '#f56c6c'
}

type TagType = 'primary' | 'success' | 'info' | 'warning' | 'danger'

const getStatusType = (status: string): TagType => {
  const map: Record<string, TagType> = {
    pending: 'info',
    executing: 'warning',
    not_started: 'info',
    in_progress: 'warning',
    running: 'warning',
    completed: 'success',
    failed: 'danger',
    cancelled: 'info',
    reverted: 'warning'
  }
  return map[status] || 'info'
}

const getStatusLabel = (status: string) => {
  const map: Record<string, string> = {
    pending: '待执行',
    executing: '执行中',
    not_started: '待执行',
    in_progress: '执行中',
    running: '执行中',
    completed: '已完成',
    failed: '失败',
    cancelled: '已取消',
    reverted: '已回滚'
  }
  return map[status] || status
}
</script>

<style scoped lang="scss">
.shift-execution-list {
  padding: 20px;

  .filter-card {
    margin-bottom: 20px;
  }
}
</style>
