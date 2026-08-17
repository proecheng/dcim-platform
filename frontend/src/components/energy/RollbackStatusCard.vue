<template>
  <el-card shadow="hover">
    <template #header>
      <div class="card-header">
        <span>回退保护状态</span>
        <el-tag :type="statusTagType" effect="dark" size="large">
          {{ statusText }}
        </el-tag>
      </div>
    </template>

    <div v-if="loading" style="text-align: center; padding: 20px">
      <el-icon class="is-loading"><Loading /></el-icon>
    </div>

    <div v-else-if="status?.active_triggers?.length">
      <el-descriptions
        v-for="(trigger, idx) in status.active_triggers"
        :key="idx"
        :column="1"
        border
        size="small"
        style="margin-bottom: 8px"
      >
        <el-descriptions-item :label="triggerTypeMap[trigger.trigger_type] || trigger.trigger_type">
          <el-tag :type="trigger.recovering ? 'warning' : 'danger'" size="small">
            {{ trigger.recovering ? '恢复中' : '触发中' }}
          </el-tag>
          <span v-if="trigger.since" style="margin-left: 8px; color: #909399; font-size: 12px">
            {{ formatTime(trigger.since) }}
          </span>
        </el-descriptions-item>
      </el-descriptions>
    </div>

    <div v-else-if="headroom !== null" style="color: #67c23a; text-align: center; padding: 10px">
      当前未触发回退保护，温度裕度 {{ headroom.toFixed(1) }}°C
    </div>

    <div v-else style="color: #E6A23C; text-align: center; padding: 10px">
      未触发回退事件，但缺少实时温度裕度，无法确认全部约束
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { Loading } from '@element-plus/icons-vue'
import { getRollbackStatus } from '@/api/modules/precool'
import type { RollbackStatusResponse } from '@/api/modules/precool'
import { useWebSocketManager } from '@/composables/useWebSocketManager'

const triggerTypeMap: Record<string, string> = {
  temp_over_limit: '温度超限',
  rate_over_predicted: '温升超预测',
  rate_over_limit: '温变速率超限',
  ac_fault: '空调故障',
  sensor_offline: '传感器离线',
  ups_active: 'UPS 切换',
  humidity_dew_point: '湿度露点风险',
}

const props = defineProps<{
  zoneId: number
  headroom: number | null
}>()

const status = ref<RollbackStatusResponse | null>(null)
const loading = ref(false)
const wsManager = useWebSocketManager()

const statusTagType = computed(() => {
  if (status.value?.has_active_rollback) return 'danger'
  if (props.headroom === null) return 'warning'
  if (props.headroom !== null && props.headroom <= 3) return 'warning'
  return 'success'
})

const statusText = computed(() => {
  if (status.value?.has_active_rollback) return '回退中'
  if (props.headroom === null) return '数据不足'
  if (props.headroom !== null && props.headroom <= 3) return '接近约束'
  return '正常'
})

const formatTime = (iso: string) => {
  try {
    const d = new Date(iso)
    return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
  } catch {
    return iso
  }
}

const fetchStatus = async () => {
  if (!props.zoneId) return
  loading.value = true
  try {
    const res = await getRollbackStatus(props.zoneId)
    const data = (res as any).data ?? res
    if (data.code === 200) {
      status.value = data.data
    }
  } catch {
    // 静默处理
  } finally {
    loading.value = false
  }
}

const handleRollbackMessage = (message: any) => {
  const { action, data } = message
  if (
    (action === 'rollback' || action === 'rollback_recovery') &&
    data?.zone_id === props.zoneId
  ) {
    fetchStatus()
  }
}

watch(() => props.zoneId, () => {
  fetchStatus()
})

onMounted(() => {
  fetchStatus()
  wsManager.on('alarms', 'alarm', handleRollbackMessage)
})

onUnmounted(() => {
  wsManager.off('alarms', 'alarm', handleRollbackMessage)
})

defineExpose({
  statusTagType,
  statusText,
  formatTime,
  triggerTypeMap,
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
