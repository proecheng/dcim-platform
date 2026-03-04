<template>
  <div class="shift-opportunity-list">
    <el-card class="filter-card">
      <el-form :inline="true" :model="filterForm">
        <el-form-item label="状态">
          <el-select v-model="filterForm.status" placeholder="全部状态" clearable style="width: 150px">
            <el-option label="待处理" value="pending" />
            <el-option label="已转换" value="converted" />
            <el-option label="已拒绝" value="rejected" />
            <el-option label="已过期" value="expired" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="filterForm.priority" placeholder="全部优先级" clearable style="width: 150px">
            <el-option label="高" value="high" />
            <el-option label="中" value="medium" />
            <el-option label="低" value="low" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleQuery">查询</el-button>
          <el-button @click="handleReset">重置</el-button>
          <el-button type="success" @click="handleAnalyze" :loading="analyzing">
            <el-icon><Refresh /></el-icon>
            触发分析
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="table-card">
      <el-table :data="opportunityList" v-loading="loading" stripe>
        <el-table-column prop="opportunity_code" label="机会编号" width="180" />
        <el-table-column prop="opportunity_name" label="机会名称" min-width="200" />
        <el-table-column label="转移方向" width="150">
          <template #default="{ row }">
            {{ row.recommended_shift_from }} → {{ row.recommended_shift_to }}
          </template>
        </el-table-column>
        <el-table-column prop="recommended_shift_power" label="推荐功率(kW)" width="120" align="right">
          <template #default="{ row }">
            {{ row.recommended_shift_power.toFixed(1) }}
          </template>
        </el-table-column>
        <el-table-column prop="predicted_cost_saving" label="预期节省(元)" width="120" align="right">
          <template #default="{ row }">
            {{ row.predicted_cost_saving.toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column label="置信度" width="100" align="center">
          <template #default="{ row }">
            <el-progress
              :percentage="row.confidence_score * 100"
              :color="getConfidenceColor(row.confidence_score)"
              :stroke-width="8"
            />
          </template>
        </el-table-column>
        <el-table-column label="优先级" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getPriorityType(row.priority)">
              {{ getPriorityLabel(row.priority) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ getStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="analysis_date" label="分析日期" width="120" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="handleView(row)">详情</el-button>
            <el-button
              link
              type="success"
              @click="handleConvert(row)"
              :disabled="row.status !== 'pending'"
            >
              转为计划
            </el-button>
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

    <!-- 分析对话框 -->
    <el-dialog v-model="analyzeDialogVisible" title="触发机会分析" width="500px">
      <el-form :model="analyzeForm" label-width="120px">
        <el-form-item label="分析日期">
          <el-date-picker
            v-model="analyzeForm.analysis_date"
            type="date"
            placeholder="选择日期"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="回溯天数">
          <el-input-number
            v-model="analyzeForm.lookback_days"
            :min="7"
            :max="90"
            style="width: 100%"
          />
          <div class="form-tip">用于计算典型负荷曲线，建议 30 天</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="analyzeDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleConfirmAnalyze" :loading="analyzing">
          开始分析
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getOpportunities, analyzeOpportunities, convertOpportunityToPlan } from '@/api/modules/shift'

const router = useRouter()

const loading = ref(false)
const analyzing = ref(false)
const opportunityList = ref([])

const filterForm = reactive({
  status: '',
  priority: ''
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const analyzeDialogVisible = ref(false)
const analyzeForm = reactive({
  analysis_date: new Date(),
  lookback_days: 30
})

onMounted(() => {
  fetchOpportunities()
})

const fetchOpportunities = async () => {
  loading.value = true
  try {
    const params = {
      skip: (pagination.page - 1) * pagination.pageSize,
      limit: pagination.pageSize,
      status: filterForm.status || undefined,
      priority: filterForm.priority || undefined
    }
    const res = await getOpportunities(params)
    opportunityList.value = res.data || []
    pagination.total = res.total || opportunityList.value.length
  } catch (error) {
    ElMessage.error('获取机会列表失败')
  } finally {
    loading.value = false
  }
}

const handleQuery = () => {
  pagination.page = 1
  fetchOpportunities()
}

const handleReset = () => {
  filterForm.status = ''
  filterForm.priority = ''
  handleQuery()
}

const handleAnalyze = () => {
  analyzeDialogVisible.value = true
}

const handleConfirmAnalyze = async () => {
  analyzing.value = true
  try {
    const params = {
      analysis_date: analyzeForm.analysis_date.toISOString().split('T')[0],
      lookback_days: analyzeForm.lookback_days
    }
    const res = await analyzeOpportunities(params)
    ElMessage.success(`分析完成，发现 ${res.data.opportunities_found} 个机会`)
    analyzeDialogVisible.value = false
    fetchOpportunities()
  } catch (error) {
    ElMessage.error('机会分析失败')
  } finally {
    analyzing.value = false
  }
}

const handleView = (row: any) => {
  router.push(`/energy/shift/opportunity/${row.id}`)
}

const handleConvert = async (row: any) => {
  try {
    await ElMessageBox.confirm(
      `确认将机会 "${row.opportunity_name}" 转换为转移计划？`,
      '转换确认',
      {
        confirmButtonText: '确认',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    const res = await convertOpportunityToPlan(row.id)
    ElMessage.success('转换成功')
    router.push(`/energy/shift/detail/${res.data.id}`)
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error('转换失败')
    }
  }
}

const getConfidenceColor = (score: number) => {
  if (score >= 0.8) return '#67c23a'
  if (score >= 0.6) return '#e6a23c'
  return '#f56c6c'
}

const getPriorityType = (priority: string) => {
  const map: Record<string, any> = {
    high: 'danger',
    medium: 'warning',
    low: 'info'
  }
  return map[priority] || 'info'
}

const getPriorityLabel = (priority: string) => {
  const map: Record<string, string> = {
    high: '高',
    medium: '中',
    low: '低'
  }
  return map[priority] || priority
}

const getStatusType = (status: string) => {
  const map: Record<string, any> = {
    pending: '',
    converted: 'success',
    rejected: 'danger',
    expired: 'info'
  }
  return map[status] || ''
}

const getStatusLabel = (status: string) => {
  const map: Record<string, string> = {
    pending: '待处理',
    converted: '已转换',
    rejected: '已拒绝',
    expired: '已过期'
  }
  return map[status] || status
}
</script>

<style scoped lang="scss">
.shift-opportunity-list {
  padding: 20px;

  .filter-card {
    margin-bottom: 20px;
  }

  .form-tip {
    font-size: 12px;
    color: #909399;
    margin-top: 5px;
  }
}
</style>
