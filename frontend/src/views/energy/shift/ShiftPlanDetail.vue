<template>
  <div class="shift-plan-detail">
    <el-page-header @back="$router.back()" title="返回">
      <template #content>
        <span>计划详情 - {{ plan.plan_name }}</span>
      </template>
    </el-page-header>

    <el-card shadow="hover" style="margin-top: 20px" v-loading="loading">
      <template #header>
        <div class="card-header">
          <span>基本信息</span>
          <div>
            <el-tag :type="getStatusType(plan.status)">{{ getStatusLabel(plan.status) }}</el-tag>
            <el-button
              v-if="plan.status === 'draft'"
              type="primary"
              size="small"
              style="margin-left: 10px"
              @click="handleSubmit"
            >
              提交审批
            </el-button>
            <el-button
              v-if="plan.status === 'pending_approval'"
              type="success"
              size="small"
              style="margin-left: 10px"
              @click="handleApprove(true)"
            >
              批准
            </el-button>
            <el-button
              v-if="plan.status === 'pending_approval'"
              type="danger"
              size="small"
              @click="handleApprove(false)"
            >
              拒绝
            </el-button>
            <el-button
              v-if="plan.status === 'approved'"
              type="primary"
              size="small"
              style="margin-left: 10px"
              @click="handleExecute"
            >
              开始执行
            </el-button>
          </div>
        </div>
      </template>

      <el-descriptions :column="3" border>
        <el-descriptions-item label="计划编号">{{ plan.plan_code }}</el-descriptions-item>
        <el-descriptions-item label="计划名称">{{ plan.plan_name }}</el-descriptions-item>
        <el-descriptions-item label="转移日期">{{ plan.shift_date }}</el-descriptions-item>
        <el-descriptions-item label="转出时段">{{ getPeriodLabel(plan.shift_from_period) }}</el-descriptions-item>
        <el-descriptions-item label="转入时段">{{ getPeriodLabel(plan.shift_to_period) }}</el-descriptions-item>
        <el-descriptions-item label="转移时间">
          {{ plan.start_time }} - {{ plan.end_time }}
        </el-descriptions-item>
        <el-descriptions-item label="目标转移功率">
          {{ plan.target_shift_power?.toFixed(1) || 0 }} kW
        </el-descriptions-item>
        <el-descriptions-item label="预期成本节省">
          {{ plan.expected_cost_saving?.toFixed(0) || 0 }} 元
        </el-descriptions-item>
        <el-descriptions-item label="预期节能量">
          {{ plan.expected_energy_saving?.toFixed(0) || 0 }} kWh
        </el-descriptions-item>
        <el-descriptions-item label="创建时间" :span="3">
          {{ plan.created_at }}
        </el-descriptions-item>
        <el-descriptions-item label="计划描述" :span="3">
          {{ plan.description || '-' }}
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card shadow="hover" style="margin-top: 20px" v-if="plan.selected_devices && plan.selected_devices.length">
      <template #header>
        <span>选中设备 ({{ plan.selected_devices.length }})</span>
      </template>
      <el-table :data="plan.selected_devices" border>
        <el-table-column type="index" label="#" width="60" />
        <el-table-column prop="device_id" label="设备ID" width="100" />
        <el-table-column prop="device_name" label="设备名称" min-width="180" />
        <el-table-column prop="shift_power" label="转移功率 (kW)" width="140" align="right" />
        <el-table-column prop="shift_action" label="转移动作" width="140" />
      </el-table>
    </el-card>

    <el-card shadow="hover" style="margin-top: 20px" v-if="plan.status !== 'draft'">
      <template #header>
        <span>审批信息</span>
      </template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="审批状态">
          <el-tag :type="plan.approval_status === 'approved' ? 'success' : 'danger'">
            {{ plan.approval_status === 'approved' ? '已批准' : plan.approval_status === 'rejected' ? '已拒绝' : '待审批' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="审批时间">{{ plan.approved_at || '-' }}</el-descriptions-item>
        <el-descriptions-item label="审批意见" :span="2">
          {{ plan.approval_comment || '-' }}
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card shadow="hover" style="margin-top: 20px" v-if="plan.status === 'completed'">
      <template #header>
        <span>执行结果</span>
      </template>
      <el-descriptions :column="3" border>
        <el-descriptions-item label="实际转移功率">
          {{ plan.actual_shift_power?.toFixed(1) || 0 }} kW
        </el-descriptions-item>
        <el-descriptions-item label="实际成本节省">
          {{ plan.actual_cost_saving?.toFixed(0) || 0 }} 元
        </el-descriptions-item>
        <el-descriptions-item label="实际节能量">
          {{ plan.actual_energy_saving?.toFixed(0) || 0 }} kWh
        </el-descriptions-item>
        <el-descriptions-item label="执行时间">{{ plan.executed_at }}</el-descriptions-item>
        <el-descriptions-item label="完成时间">{{ plan.completed_at }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-dialog v-model="approvalDialogVisible" title="审批意见" width="500px">
      <el-form :model="approvalForm" label-width="100px">
        <el-form-item label="审批结果">
          <el-radio-group v-model="approvalForm.approved">
            <el-radio :value="true">批准</el-radio>
            <el-radio :value="false">拒绝</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="审批意见">
          <el-input v-model="approvalForm.comment" type="textarea" :rows="4" placeholder="请输入审批意见" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="approvalDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitApproval">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getShiftPlan, submitShiftPlan, approveShiftPlan, executeShiftPlan } from '@/api/modules/shift'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const plan = reactive<any>({})
const approvalDialogVisible = ref(false)
const approvalForm = reactive({
  approved: true,
  comment: '',
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

const loadPlan = async () => {
  loading.value = true
  try {
    const id = Number(route.params.id)
    const res = await getShiftPlan(id)
    Object.assign(plan, res.data || {})
  } catch (error: any) {
    ElMessage.error(error.message || '加载计划详情失败')
  } finally {
    loading.value = false
  }
}

const handleSubmit = async () => {
  try {
    await ElMessageBox.confirm('确认提交该计划审批？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await submitShiftPlan(plan.id)
    ElMessage.success('提交成功')
    loadPlan()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '提交失败')
    }
  }
}

const handleApprove = (approved: boolean) => {
  approvalForm.approved = approved
  approvalForm.comment = ''
  approvalDialogVisible.value = true
}

const submitApproval = async () => {
  try {
    await approveShiftPlan(plan.id, {
      approval_status: approvalForm.approved ? 'approved' : 'rejected',
      approval_comment: approvalForm.comment,
    })
    ElMessage.success('审批成功')
    approvalDialogVisible.value = false
    loadPlan()
  } catch (error: any) {
    ElMessage.error(error.message || '审批失败')
  }
}

const handleExecute = async () => {
  try {
    await ElMessageBox.confirm('确认开始执行该计划？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await executeShiftPlan(plan.id)
    ElMessage.success('执行已启动')
    loadPlan()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '执行失败')
    }
  }
}

onMounted(() => {
  loadPlan()
})
</script>

<style scoped lang="scss">
.shift-plan-detail {
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
}
</style>
