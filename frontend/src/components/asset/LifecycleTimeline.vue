<template>
  <div class="lifecycle-timeline" v-loading="loading">
    <el-timeline v-if="records.length > 0">
      <el-timeline-item
        v-for="record in records"
        :key="record.id"
        :color="getActionColor(record.action)"
        :timestamp="formatTime(record.action_date)"
        placement="top"
      >
        <div class="timeline-content">
          <div class="timeline-header">
            <el-tag :color="getActionColor(record.action)" effect="dark" size="small" style="color: #fff; border: none;">
              {{ getActionLabel(record.action) }}
            </el-tag>
            <span class="timeline-operator" v-if="record.operator">{{ record.operator }}</span>
          </div>
          <div class="timeline-location" v-if="record.from_location || record.to_location">
            <span v-if="record.from_location">{{ record.from_location }}</span>
            <span v-if="record.from_location && record.to_location"> → </span>
            <span v-if="record.to_location">{{ record.to_location }}</span>
          </div>
          <div class="timeline-remark" v-if="record.remark">{{ record.remark }}</div>
        </div>
      </el-timeline-item>
    </el-timeline>
    <el-empty v-else description="暂无生命周期记录" />
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { getAssetLifecycle, type LifecycleRecord } from '@/api/modules/asset'

const props = defineProps<{
  assetId: number
}>()

const loading = ref(false)
const records = ref<LifecycleRecord[]>([])

const actionColorMap: Record<string, string> = {
  purchase: '#67c23a',
  deploy: '#409eff',
  move: '#e6a23c',
  maintain: '#f2c037',
  scrap: '#f56c6c',
  status_change: '#909399',
}

const actionLabelMap: Record<string, string> = {
  purchase: '入库',
  deploy: '部署',
  move: '移动',
  maintain: '维护',
  scrap: '报废',
  status_change: '状态变更',
}

function getActionColor(action: string): string {
  return actionColorMap[action] || '#909399'
}

function getActionLabel(action: string): string {
  return actionLabelMap[action] || action
}

function formatTime(dateStr: string): string {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  const pad = (n: number) => n.toString().padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function loadRecords() {
  if (!props.assetId) return
  loading.value = true
  try {
    const res = await getAssetLifecycle(props.assetId)
    records.value = Array.isArray(res) ? res : (res as any).data || []
  } catch (e) {
    console.error('加载生命周期记录失败', e)
    records.value = []
  } finally {
    loading.value = false
  }
}

watch(() => props.assetId, () => {
  loadRecords()
}, { immediate: true })
</script>

<style scoped lang="scss">
.lifecycle-timeline {
  min-height: 200px;
  max-height: 500px;
  overflow-y: auto;
  padding: 16px;

  .timeline-content {
    .timeline-header {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 4px;

      .timeline-operator {
        font-size: 13px;
        color: #909399;
      }
    }

    .timeline-location {
      font-size: 13px;
      color: #606266;
      margin-bottom: 2px;
    }

    .timeline-remark {
      font-size: 12px;
      color: #909399;
    }
  }
}
</style>
