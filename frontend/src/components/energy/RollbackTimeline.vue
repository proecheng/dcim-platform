<template>
  <el-card shadow="hover">
    <template #header>
      <div class="card-header">
        <span>回退事件记录</span>
        <el-radio-group v-model="statusFilter" size="small" @change="refresh">
          <el-radio-button value="">全部</el-radio-button>
          <el-radio-button value="active">进行中</el-radio-button>
          <el-radio-button value="resolved">已恢复</el-radio-button>
        </el-radio-group>
      </div>
    </template>

    <div v-if="loading" style="text-align: center; padding: 20px">
      <el-icon class="is-loading"><Loading /></el-icon>
    </div>

    <el-empty v-else-if="!events.length" description="暂无回退事件" />

    <el-timeline v-else>
      <el-timeline-item
        v-for="event in events"
        :key="event.id"
        :type="event.status === 'active' ? 'danger' : 'success'"
        :timestamp="formatTime(event.created_at)"
        placement="top"
      >
        <div class="timeline-event">
          <div>
            <el-tag :type="event.status === 'active' ? 'danger' : 'success'" size="small">
              {{ event.status === 'active' ? '进行中' : '已恢复' }}
            </el-tag>
            <span style="margin-left: 8px; font-weight: bold">
              {{ triggerTypeMap[event.trigger_type] || event.trigger_type }}
            </span>
          </div>
          <div style="margin-top: 4px; font-size: 13px; color: #606266">
            {{ event.action }}
          </div>
          <div v-if="event.trigger_value != null" style="margin-top: 4px; font-size: 12px; color: #909399">
            触发值: {{ event.trigger_value }} / 阈值: {{ event.threshold }}
          </div>
          <div v-if="event.resolved_at" style="margin-top: 4px; font-size: 12px; color: #67c23a">
            恢复时间: {{ formatTime(event.resolved_at) }}
          </div>
        </div>
      </el-timeline-item>
    </el-timeline>

    <el-pagination
      v-if="total > pageSize"
      layout="prev, pager, next"
      :total="total"
      :page-size="pageSize"
      :current-page="currentPage"
      @current-change="handlePageChange"
      style="margin-top: 16px; display: flex; justify-content: center"
    />
  </el-card>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { Loading } from '@element-plus/icons-vue'
import { getRollbackHistory } from '@/api/modules/precool'
import type { RollbackEventItem } from '@/api/modules/precool'
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
}>()

const events = ref<RollbackEventItem[]>([])
const total = ref(0)
const loading = ref(false)
const statusFilter = ref<string>('')
const currentPage = ref(1)
const pageSize = 10
const wsManager = useWebSocketManager()

const formatTime = (iso: string | null) => {
  if (!iso) return '-'
  try {
    const d = new Date(iso)
    return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`
  } catch {
    return iso
  }
}

const fetchEvents = async () => {
  if (!props.zoneId) return
  loading.value = true
  try {
    const params: Record<string, any> = {
      skip: (currentPage.value - 1) * pageSize,
      limit: pageSize,
    }
    if (statusFilter.value) {
      params.status = statusFilter.value
    }
    const res = await getRollbackHistory(props.zoneId, params)
    const data = (res as any).data ?? res
    if (data.code === 200) {
      events.value = data.data.items
      total.value = data.data.total
    }
  } catch {
    // 静默处理
  } finally {
    loading.value = false
  }
}

const refresh = () => {
  currentPage.value = 1
  fetchEvents()
}

const handlePageChange = (page: number) => {
  currentPage.value = page
  fetchEvents()
}

const handleRollbackMessage = (message: any) => {
  const { action, data } = message
  if (
    (action === 'rollback' || action === 'rollback_recovery') &&
    data?.zone_id === props.zoneId
  ) {
    // 有新事件，回到第一页刷新
    currentPage.value = 1
    fetchEvents()
  }
}

watch(() => props.zoneId, () => {
  currentPage.value = 1
  fetchEvents()
})

onMounted(() => {
  fetchEvents()
  wsManager.on('alarms', 'alarm', handleRollbackMessage)
})

onUnmounted(() => {
  wsManager.off('alarms', 'alarm', handleRollbackMessage)
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.timeline-event {
  padding: 4px 0;
}
</style>
