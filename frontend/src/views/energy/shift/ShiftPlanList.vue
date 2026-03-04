<template>
  <div class="shift-plan-list">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>负荷转移计划</span>
          <el-button type="primary" @click="handleCreate">新建计划</el-button>
        </div>
      </template>

      <el-form :inline="true" :model="queryForm" class="query-form">
        <el-form-item label="状态">
          <el-select v-model="queryForm.status" placeholder="全部" clearable style="width: 150px">
            <el-option label="草稿" value="draft" />
            <el-option label="待审批" value="pending_approval" />
            <el-option label="已批准" value="approved" />
            <el-option label="执行中" value="executing" />
            <el-option label="已完成" value="completed" />
            <el-option label="已失败" value="failed" />
          </el-select>
        </el-form-item>
        <el-form-item label="转移日期">
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
            style="width: 260px"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadPlans">查询</el-button>
          <el-button @click="resetQuery">重置</el-button>
        </el-form-item>
      </el-form>

      <el-table :data="plans" v-loading="loading" border>
        <el-table-column prop="plan_code" label="计划编号" width="160" />
        <el-table-column prop="plan_name" label="计划名称" min-width="180" />
        <el-table-column label="转移时段" width="180">
          <template #default="{ row }">
            {{ getPeriodLabel(row.shift_from_period) }} → {{ getPeriodLabel(row.shift_to_period) }}
          </template>
        </el-table-column>
        <el-table-column prop="shift_date" label="转移日期" width="120" />
        <el-table-column label="转移功率" width="120" align="right">
          <template #default="{ row }">
            {{ row.target_shift_power?.toFixed(1) || 0 }} kW
          </template>
        </el-table-column>
        <el-table-column label="预期收益" width="120" align="right">
          <template #default="{ row }">
            {{ row.expected_cost_saving?.toFixed(0) || 0 }} 元
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ getStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="handleView(row.id)">详情</el-button>
            <el-button link type="primary" v-if="row.status === 'draft'" @click="handleEdit(row.id)">编辑</el-button>
            <el-button link type="danger" v-if="row.status === 'draft'" @click="handleDelete(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.size"
        :total="pagination.total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="loadPlans"
        @current-change="loadPlans"
        style="margin-top: 16px; justify-content: flex-end"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getShiftPlans, deleteShiftPlan } from '@/api/modules/shift'

const router = useRouter()

const loading = ref(false)
const plans = ref<any[]>([])
const dateRange = ref<string[]>([])

const queryForm = reactive({
  status: '',
})

const pagination = reactive({
  page: 1,
  size: 20,
  total: 0,
})

const periodLabels: Record<string, string> = {
  peak: '尖峰',
  sharp: '高峰',
  flat: '平段',
  valley: '谷段',
}

const statusLabels: Record<string, string> = {
  draft: '草稿',
  pending_approval: '待审批',
  approved: '已批准',
  rejected: '已拒绝',
  executing: '执行中',
  completed: '已完成',
  failed: '已失败',
  cancelled: '已取消',
}

const getPeriodLabel = (period: string) => periodLabels[period] || period
const getStatusLabel = (status: string) => statusLabels[status] || status

const getStatusType = (status: string) => {
  const typeMap: Record<string, any> = {
    draft: 'info',
    pending_approval: 'warning',
    approved: 'success',
    rejected: 'danger',
    executing: 'primary',
    completed: 'success',
    failed: 'danger',
    cancelled: 'info',
  }
  return typeMap[status] || 'info'
}

const loadPlans = async () => {
  loading.value = true
  try {
    const params: any = {
      skip: (pagination.page - 1) * pagination.size,
      limit: pagination.size,
    }
    if (queryForm.status) params.status = queryForm.status
    if (dateRange.value && dateRange.value.length === 2) {
      params.shift_date_from = dateRange.value[0]
      params.shift_date_to = dateRange.value[1]
    }
    const res = await getShiftPlans(params)
    plans.value = res.data || []
    pagination.total = res.total || plans.value.length
  } catch (error: any) {
    ElMessage.error(error.message || '加载计划列表失败')
  } finally {
    loading.value = false
  }
}

const resetQuery = () => {
  queryForm.status = ''
  dateRange.value = []
  pagination.page = 1
  loadPlans()
}

const handleCreate = () => {
  router.push('/energy/shift/create')
}

const handleView = (id: number) => {
  router.push(`/energy/shift/detail/${id}`)
}

const handleEdit = (id: number) => {
  router.push(`/energy/shift/edit/${id}`)
}

const handleDelete = async (id: number) => {
  try {
    await ElMessageBox.confirm('确认删除该计划？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await deleteShiftPlan(id)
    ElMessage.success('删除成功')
    loadPlans()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '删除失败')
    }
  }
}

onMounted(() => {
  loadPlans()
})
</script>

<style scoped lang="scss">
.shift-plan-list {
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .query-form {
    margin-bottom: 16px;
  }
}
</style>
