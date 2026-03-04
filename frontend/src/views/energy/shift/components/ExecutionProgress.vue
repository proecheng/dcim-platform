<template>
  <div class="execution-progress">
    <el-steps :active="currentStep" finish-status="success" align-center>
      <el-step title="准备阶段" :description="getStepDesc(0)" />
      <el-step title="设备调整" :description="getStepDesc(1)" />
      <el-step title="制冷联动" :description="getStepDesc(2)" />
      <el-step title="执行完成" :description="getStepDesc(3)" />
    </el-steps>

    <el-card shadow="hover" style="margin-top: 20px">
      <template #header>
        <span>执行详情</span>
      </template>

      <el-descriptions :column="2" border>
        <el-descriptions-item label="执行状态">
          <el-tag :type="getStatusType(execution.status)">
            {{ getStatusLabel(execution.status) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="开始时间">
          {{ execution.start_time || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="当前功率">
          {{ execution.current_power?.toFixed(1) || 0 }} kW
        </el-descriptions-item>
        <el-descriptions-item label="目标功率">
          {{ execution.target_power?.toFixed(1) || 0 }} kW
        </el-descriptions-item>
        <el-descriptions-item label="完成进度" :span="2">
          <el-progress
            :percentage="execution.progress || 0"
            :status="execution.progress >= 100 ? 'success' : undefined"
          />
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card shadow="hover" style="margin-top: 20px" v-if="execution.device_details && execution.device_details.length">
      <template #header>
        <span>设备执行状态</span>
      </template>
      <el-table :data="execution.device_details" border>
        <el-table-column prop="device_name" label="设备名称" min-width="180" />
        <el-table-column label="执行动作" width="120">
          <template #default="{ row }">
            {{ getActionLabel(row.action) }}
          </template>
        </el-table-column>
        <el-table-column label="执行前" width="100" align="right">
          <template #default="{ row }">
            {{ row.before_value?.toFixed(1) || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="执行后" width="100" align="right">
          <template #default="{ row }">
            {{ row.after_value?.toFixed(1) || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="节省功率" width="120" align="right">
          <template #default="{ row }">
            {{ row.power_saved?.toFixed(1) || 0 }} kW
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'success' ? 'success' : row.status === 'failed' ? 'danger' : 'info'" size="small">
              {{ row.status === 'success' ? '成功' : row.status === 'failed' ? '失败' : '执行中' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card shadow="hover" style="margin-top: 20px" v-if="execution.cooling_data">
      <template #header>
        <span>制冷联动数据</span>
      </template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="制冷滞后时间">
          {{ execution.cooling_data.cooling_lag_minutes || 0 }} 分钟
        </el-descriptions-item>
        <el-descriptions-item label="制冷功率变化">
          {{ execution.cooling_data.cooling_power_before?.toFixed(1) || 0 }} →
          {{ execution.cooling_data.cooling_power_after?.toFixed(1) || 0 }} kW
        </el-descriptions-item>
        <el-descriptions-item label="制冷效率变化">
          {{ execution.cooling_data.cooling_efficiency_before?.toFixed(2) || 0 }} →
          {{ execution.cooling_data.cooling_efficiency_after?.toFixed(2) || 0 }}
        </el-descriptions-item>
        <el-descriptions-item label="供水温度变化">
          {{ execution.cooling_data.supply_temp_before?.toFixed(1) || 0 }} →
          {{ execution.cooling_data.supply_temp_after?.toFixed(1) || 0 }} ℃
        </el-descriptions-item>
      </el-descriptions>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  execution: any
}>()

const currentStep = computed(() => {
  const status = props.execution.status
  if (status === 'pending') return 0
  if (status === 'executing') return 1
  if (status === 'cooling') return 2
  if (status === 'completed' || status === 'failed') return 3
  return 0
})

const getStepDesc = (step: number) => {
  const descs = ['准备设备调整', '正在调整设备', '制冷系统联动', '执行完成']
  return descs[step] || ''
}

const getStatusType = (status: string) => {
  const typeMap: Record<string, any> = {
    pending: 'info',
    executing: 'primary',
    cooling: 'warning',
    completed: 'success',
    failed: 'danger',
  }
  return typeMap[status] || 'info'
}

const getStatusLabel = (status: string) => {
  const labelMap: Record<string, string> = {
    pending: '待执行',
    executing: '执行中',
    cooling: '制冷联动中',
    completed: '已完成',
    failed: '执行失败',
  }
  return labelMap[status] || status
}

const getActionLabel = (action: string) => {
  const labelMap: Record<string, string> = {
    reduce_temp: '降低温度',
    stop: '停机',
    reduce_load: '降低负载',
  }
  return labelMap[action] || action
}
</script>

<style scoped lang="scss">
.execution-progress {
  // styles
}
</style>
