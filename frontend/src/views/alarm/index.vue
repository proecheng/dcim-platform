<template>
  <div class="alarm-page">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>告警管理</span>
          <el-button type="primary" @click="batchAck" :disabled="!selectedIds.length">
            批量确认 ({{ selectedIds.length }})
          </el-button>
        </div>
      </template>

      <!-- 筛选条件 -->
      <el-form :inline="true" class="filter-form">
        <el-form-item label="告警状态">
          <el-select v-model="filters.status" placeholder="全部" clearable>
            <el-option label="活动" value="active" />
            <el-option label="已确认" value="acknowledged" />
            <el-option label="已解决" value="resolved" />
          </el-select>
        </el-form-item>
        <el-form-item label="告警级别">
          <el-select v-model="filters.level" placeholder="全部" clearable>
            <el-option label="紧急" value="critical" />
            <el-option label="重要" value="major" />
            <el-option label="一般" value="minor" />
            <el-option label="提示" value="info" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadAlarms">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- 告警统计 -->
      <div class="alarm-stats">
        <el-tag type="danger" effect="dark">紧急: {{ alarmCount.critical }}</el-tag>
        <el-tag type="warning" effect="dark">重要: {{ alarmCount.major }}</el-tag>
        <el-tag type="primary" effect="dark">一般: {{ alarmCount.minor }}</el-tag>
        <el-tag type="info" effect="dark">提示: {{ alarmCount.info }}</el-tag>
      </div>

      <!-- 告警列表 -->
      <el-table
        :data="alarms"
        stripe
        border
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="55" />
        <el-table-column prop="alarm_level" label="级别" width="80">
          <template #default="{ row }">
            <el-tag :type="getLevelTagType(row.alarm_level)" size="small">
              {{ getLevelText(row.alarm_level) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="point_code" label="点位编码" width="150" />
        <el-table-column prop="point_name" label="点位名称" width="150" />
        <el-table-column prop="alarm_message" label="告警内容" min-width="200" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusTagType(row.status)" size="small">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="告警时间" width="180" />
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'active'"
              type="primary"
              link
              @click="handleAck(row.id)"
            >
              确认
            </el-button>
            <el-button
              v-if="row.status !== 'resolved'"
              type="success"
              link
              @click="handleResolve(row.id)"
            >
              解决
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getAlarms, getAlarmCount, acknowledgeAlarm,
  resolveAlarm, batchAcknowledge
} from '@/api/alarm'

const alarms = ref([])
const alarmCount = ref({ critical: 0, major: 0, minor: 0, info: 0, total: 0 })
const selectedIds = ref<number[]>([])

const filters = reactive({
  status: '',
  level: ''
})

onMounted(() => {
  loadAlarms()
  loadAlarmCount()
})

async function loadAlarms() {
  try {
    const params = { ...filters }
    Object.keys(params).forEach(key => {
      if (!params[key as keyof typeof params]) {
        delete params[key as keyof typeof params]
      }
    })
    const result = await getAlarms(params)
    // 后端返回分页响应，需要取 items（如果是分页对象）或直接使用（如果是数组）
    alarms.value = Array.isArray(result) ? result : (result.items || result)
  } catch (e) {
    console.error('加载告警失败', e)
  }
}

async function loadAlarmCount() {
  try {
    alarmCount.value = await getAlarmCount()
  } catch (e) {
    console.error('获取告警统计失败', e)
  }
}

function resetFilters() {
  filters.status = ''
  filters.level = ''
  loadAlarms()
}

function handleSelectionChange(selection: any[]) {
  selectedIds.value = selection.map(item => item.id)
}

async function handleAck(id: number) {
  try {
    await acknowledgeAlarm(id)
    ElMessage.success('确认成功')
    loadAlarms()
    loadAlarmCount()
  } catch (e) {
    console.error('确认失败', e)
  }
}

async function handleResolve(id: number) {
  try {
    await resolveAlarm(id)
    ElMessage.success('解决成功')
    loadAlarms()
    loadAlarmCount()
  } catch (e) {
    console.error('解决失败', e)
  }
}

async function batchAck() {
  if (selectedIds.value.length === 0) return
  try {
    await batchAcknowledge(selectedIds.value)
    ElMessage.success('批量确认成功')
    loadAlarms()
    loadAlarmCount()
    selectedIds.value = []
  } catch (e) {
    console.error('批量确认失败', e)
  }
}

type TagType = 'success' | 'warning' | 'danger' | 'info' | 'primary'

function getLevelTagType(level: string): TagType {
  const map: Record<string, TagType> = {
    critical: 'danger',
    major: 'warning',
    minor: 'primary',
    info: 'info'
  }
  return map[level] || 'info'
}

function getLevelText(level: string) {
  const map: Record<string, string> = {
    critical: '紧急',
    major: '重要',
    minor: '一般',
    info: '提示'
  }
  return map[level] || level
}

function getStatusTagType(status: string): TagType {
  const map: Record<string, TagType> = {
    active: 'danger',
    acknowledged: 'warning',
    resolved: 'success'
  }
  return map[status] || 'info'
}

function getStatusText(status: string) {
  const map: Record<string, string> = {
    active: '活动',
    acknowledged: '已确认',
    resolved: '已解决'
  }
  return map[status] || status
}
</script>

<style scoped lang="scss">
.alarm-page {
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .filter-form {
    margin-bottom: 20px;
  }

  .alarm-stats {
    margin-bottom: 20px;
    display: flex;
    gap: 10px;
  }
}
</style>
