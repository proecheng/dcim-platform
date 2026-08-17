<template>
  <div class="shift-execution-detail">
    <el-page-header @back="$router.back()" title="返回">
      <template #content>
        <span>执行详情 - {{ execution.execution_code }}</span>
      </template>
    </el-page-header>

    <el-card shadow="hover" style="margin-top: 20px" v-loading="loading">
      <template #header>
        <div class="card-header">
          <span>基本信息</span>
          <el-tag :type="getStatusType(execution.status)">{{ getStatusLabel(execution.status) }}</el-tag>
        </div>
      </template>

      <el-descriptions :column="3" border>
        <el-descriptions-item label="执行编号">{{ execution.execution_code }}</el-descriptions-item>
        <el-descriptions-item label="关联计划">
          <el-link type="primary" @click="goToPlan(execution.plan_id)">
            {{ execution.plan_name }}
          </el-link>
        </el-descriptions-item>
        <el-descriptions-item label="执行状态">
          <el-tag :type="getStatusType(execution.status)">{{ getStatusLabel(execution.status) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="开始时间">{{ execution.start_time }}</el-descriptions-item>
        <el-descriptions-item label="结束时间">{{ execution.end_time || '-' }}</el-descriptions-item>
        <el-descriptions-item label="执行时长">{{ getDuration(execution) }}</el-descriptions-item>
        <el-descriptions-item label="目标转移功率">
          {{ execution.target_shift_power?.toFixed(1) || 0 }} kW
        </el-descriptions-item>
        <el-descriptions-item label="实际转移功率">
          {{ execution.actual_shift_power?.toFixed(1) || 0 }} kW
        </el-descriptions-item>
        <el-descriptions-item label="完成率">
          {{ getCompletionRate(execution) }}%
        </el-descriptions-item>
        <el-descriptions-item label="预期成本节省">
          {{ execution.expected_cost_saving?.toFixed(0) || 0 }} 元
        </el-descriptions-item>
        <el-descriptions-item label="实际成本节省">
          {{ execution.actual_cost_saving?.toFixed(0) || 0 }} 元
        </el-descriptions-item>
        <el-descriptions-item label="预期节能量">
          {{ execution.expected_energy_saving?.toFixed(0) || 0 }} kWh
        </el-descriptions-item>
        <el-descriptions-item label="实际节能量">
          {{ execution.actual_energy_saving?.toFixed(0) || 0 }} kWh
        </el-descriptions-item>
        <el-descriptions-item label="执行人">{{ execution.executor_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="备注" :span="3">
          {{ execution.notes || '-' }}
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card shadow="hover" style="margin-top: 20px">
      <template #header>
        <span>执行过程</span>
      </template>
      <el-timeline>
        <el-timeline-item
          v-for="(step, index) in executionSteps"
          :key="index"
          :timestamp="step.timestamp"
          :type="step.type"
          :icon="step.icon"
        >
          <h4>{{ step.title }}</h4>
          <p>{{ step.description }}</p>
        </el-timeline-item>
      </el-timeline>
    </el-card>

    <el-card shadow="hover" style="margin-top: 20px" v-if="execution.device_executions && execution.device_executions.length">
      <template #header>
        <span>设备执行状态 ({{ execution.device_executions.length }})</span>
      </template>
      <el-table :data="execution.device_executions" border>
        <el-table-column type="index" label="#" width="60" />
        <el-table-column prop="device_name" label="设备名称" min-width="180" />
        <el-table-column label="转移动作" width="120">
          <template #default="{ row }">
            {{ row.shift_action || row.action || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="执行前功率 (kW)" width="140" align="right">
          <template #default="{ row }">
            {{ formatPower(row.power_before ?? row.target_power) }}
          </template>
        </el-table-column>
        <el-table-column label="执行后功率 (kW)" width="140" align="right">
          <template #default="{ row }">
            {{ formatPower(row.power_after ?? row.actual_power) }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="执行状态" width="120">
          <template #default="{ row }">
            <el-tag :type="getDeviceStatusType(row.status)">{{ getDeviceStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="开始时间" width="160">
          <template #default="{ row }">
            {{ row.start_time || row.executed_at || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="end_time" label="结束时间" width="160" />
        <el-table-column prop="error_message" label="错误信息" min-width="200" />
      </el-table>
    </el-card>

    <el-card shadow="hover" style="margin-top: 20px" v-if="execution.cooling_linkage">
      <template #header>
        <span>制冷联动数据</span>
      </template>
      <el-descriptions :column="3" border>
        <el-descriptions-item label="联动前制冷功率">
          {{ getCoolingValue(execution.cooling_linkage, 'before_power', 'cooling_power_before', 1) }} kW
        </el-descriptions-item>
        <el-descriptions-item label="联动后制冷功率">
          {{ getCoolingValue(execution.cooling_linkage, 'after_power', 'cooling_power_after', 1) }} kW
        </el-descriptions-item>
        <el-descriptions-item label="制冷功率变化">
          {{ getCoolingPowerChange(execution.cooling_linkage) }} kW
        </el-descriptions-item>
        <el-descriptions-item label="联动前COP">
          {{ getCoolingValue(execution.cooling_linkage, 'before_cop', 'cooling_efficiency_before', 2) }}
        </el-descriptions-item>
        <el-descriptions-item label="联动后COP">
          {{ getCoolingValue(execution.cooling_linkage, 'after_cop', 'cooling_efficiency_after', 2) }}
        </el-descriptions-item>
        <el-descriptions-item label="COP变化">
          {{ getCOPChange(execution.cooling_linkage) }}
        </el-descriptions-item>
        <el-descriptions-item label="联动前供水温度">
          {{ getCoolingValue(execution.cooling_linkage, 'before_supply_temp', 'supply_temp_before', 1) }} °C
        </el-descriptions-item>
        <el-descriptions-item label="联动后供水温度">
          {{ getCoolingValue(execution.cooling_linkage, 'after_supply_temp', 'supply_temp_after', 1) }} °C
        </el-descriptions-item>
        <el-descriptions-item label="联动前回水温度">
          {{ getCoolingValue(execution.cooling_linkage, 'before_return_temp', 'return_temp_before', 1) }} °C
        </el-descriptions-item>
        <el-descriptions-item label="联动后回水温度">
          {{ getCoolingValue(execution.cooling_linkage, 'after_return_temp', 'return_temp_after', 1) }} °C
        </el-descriptions-item>
      </el-descriptions>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getExecutionDetail, type ShiftExecution } from '@/api/modules/shift'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const execution = ref<Partial<ShiftExecution>>({})

const executionSteps = computed(() => {
  const steps = []
  if (execution.value.start_time) {
    steps.push({
      timestamp: execution.value.start_time,
      type: 'primary',
      icon: 'VideoPlay',
      title: '执行开始',
      description: `开始执行负荷转移计划: ${execution.value.plan_name}`
    })
  }
  if (execution.value.device_executions) {
    execution.value.device_executions.forEach((device) => {
      if (device.start_time) {
        steps.push({
          timestamp: device.start_time,
          type: device.status === 'completed' ? 'success' : device.status === 'failed' ? 'danger' : 'info',
          icon: device.status === 'completed' ? 'Check' : device.status === 'failed' ? 'Close' : 'Loading',
          title: `设备 ${device.device_name}`,
          description: `${device.shift_action} - ${device.status === 'completed' ? '执行成功' : device.status === 'failed' ? '执行失败: ' + device.error_message : '执行中'}`
        })
      }
    })
  }
  if (execution.value.end_time) {
    steps.push({
      timestamp: execution.value.end_time,
      type: execution.value.status === 'completed' ? 'success' : 'danger',
      icon: execution.value.status === 'completed' ? 'CircleCheck' : 'CircleClose',
      title: '执行结束',
      description: execution.value.status === 'completed' ? '负荷转移执行完成' : '负荷转移执行失败'
    })
  }
  return steps.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
})

const fetchDetail = async () => {
  loading.value = true
  try {
    const id = Number(route.params.id)
    const res = await getExecutionDetail(id)
    execution.value = res.data
  } catch (error: any) {
    ElMessage.error(error.message || '获取执行详情失败')
  } finally {
    loading.value = false
  }
}

type TagType = 'primary' | 'success' | 'info' | 'warning' | 'danger'

const getStatusType = (status: string): TagType => {
  const map: Record<string, TagType> = {
    pending: 'info',
    executing: 'warning',
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
    running: '执行中',
    completed: '已完成',
    failed: '执行失败',
    cancelled: '已取消',
    reverted: '已回滚'
  }
  return map[status] || status
}

const getDeviceStatusType = (status: string): TagType => {
  const map: Record<string, TagType> = {
    pending: 'info',
    executing: 'warning',
    running: 'warning',
    completed: 'success',
    failed: 'danger'
  }
  return map[status] || 'info'
}

const getDeviceStatusLabel = (status: string) => {
  const map: Record<string, string> = {
    pending: '待执行',
    executing: '执行中',
    running: '执行中',
    completed: '已完成',
    failed: '失败'
  }
  return map[status] || status
}

const getDuration = (exec: Partial<ShiftExecution>) => {
  if (!exec.start_time) return '-'
  const start = new Date(exec.start_time).getTime()
  const end = exec.end_time ? new Date(exec.end_time).getTime() : Date.now()
  const duration = Math.floor((end - start) / 1000 / 60)
  return `${duration} 分钟`
}

const getCompletionRate = (exec: Partial<ShiftExecution>) => {
  if (!exec.target_shift_power || exec.target_shift_power === 0) return 0
  return ((exec.actual_shift_power || 0) / exec.target_shift_power * 100).toFixed(1)
}

const getCoolingPowerChange = (linkage: any) => {
  const after = linkage.after_power ?? linkage.cooling_power_after ?? 0
  const before = linkage.before_power ?? linkage.cooling_power_before ?? 0
  const change = after - before
  return change > 0 ? `+${change.toFixed(1)}` : change.toFixed(1)
}

const getCOPChange = (linkage: any) => {
  const after = linkage.after_cop ?? linkage.cooling_efficiency_after ?? 0
  const before = linkage.before_cop ?? linkage.cooling_efficiency_before ?? 0
  const change = after - before
  return change > 0 ? `+${change.toFixed(2)}` : change.toFixed(2)
}

const formatPower = (value: unknown) =>
  typeof value === 'number' && Number.isFinite(value) ? value.toFixed(1) : '-'

const getCoolingValue = (linkage: any, primaryKey: string, fallbackKey: string, precision: number) => {
  const value = linkage?.[primaryKey] ?? linkage?.[fallbackKey]
  return typeof value === 'number' && Number.isFinite(value) ? value.toFixed(precision) : '-'
}

const goToPlan = (planId: number) => {
  router.push({ name: 'ShiftPlanDetail', params: { id: planId } })
}

onMounted(() => {
  fetchDetail()
})
</script>

<style scoped lang="scss">
.shift-execution-detail {
  padding: 20px;

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
}
</style>
