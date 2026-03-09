<template>
  <div class="time-window-tuning-container">
    <el-card class="query-card">
      <template #header>
        <div class="card-header">
          <span>时间窗口调参管理</span>
          <el-button type="primary" @click="handleTriggerAnalysis" :loading="analyzing">
            <el-icon><Refresh /></el-icon>
            触发分析
          </el-button>
        </div>
      </template>

      <el-form :model="queryForm" inline>
        <el-form-item label="设备类型">
          <el-input v-model="queryForm.device_type" placeholder="请输入设备类型" clearable style="width: 200px" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="queryForm.status" placeholder="请选择状态" clearable style="width: 150px">
            <el-option label="待审批" value="pending" />
            <el-option label="已审批" value="approved" />
            <el-option label="已拒绝" value="rejected" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleQuery">查询</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="table-card">
      <el-table :data="tableData" v-loading="loading" border stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="device_type" label="设备类型" width="120" />
        <el-table-column label="当前窗口" width="120">
          <template #default="{ row }">
            {{ row.current_window_minutes }} 分钟
          </template>
        </el-table-column>
        <el-table-column label="建议窗口" width="120">
          <template #default="{ row }">
            {{ row.proposed_window_minutes }} 分钟
          </template>
        </el-table-column>
        <el-table-column label="调整幅度" width="120">
          <template #default="{ row }">
            <el-tag :type="getAdjustmentType(row.adjustment_percent)">
              {{ row.adjustment_percent.toFixed(1) }}%
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="sample_count" label="样本数" width="100" />
        <el-table-column label="P50/P90 (秒)" width="150">
          <template #default="{ row }">
            {{ row.p50_duration_seconds.toFixed(1) }} / {{ row.p90_duration_seconds.toFixed(1) }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="handleViewDetail(row)">详情</el-button>
            <el-button
              v-if="row.status === 'pending'"
              link
              type="success"
              @click="handleApprove(row)"
            >
              审批
            </el-button>
            <el-button
              v-if="row.status === 'pending'"
              link
              type="danger"
              @click="handleReject(row)"
            >
              拒绝
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.page_size"
        :total="pagination.total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="handleQuery"
        @current-change="handleQuery"
        style="margin-top: 20px; justify-content: flex-end"
      />
    </el-card>

    <!-- 详情对话框 -->
    <el-dialog v-model="detailVisible" title="调参详情" width="600px">
      <el-descriptions :column="2" border v-if="currentRow">
        <el-descriptions-item label="设备类型">{{ currentRow.device_type }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusType(currentRow.status)">
            {{ getStatusText(currentRow.status) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="当前窗口">{{ currentRow.current_window_minutes }} 分钟</el-descriptions-item>
        <el-descriptions-item label="建议窗口">{{ currentRow.proposed_window_minutes }} 分钟</el-descriptions-item>
        <el-descriptions-item label="调整幅度">
          <el-tag :type="getAdjustmentType(currentRow.adjustment_percent)">
            {{ currentRow.adjustment_percent.toFixed(1) }}%
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="样本数">{{ currentRow.sample_count }}</el-descriptions-item>
        <el-descriptions-item label="P50 持续时长">{{ currentRow.p50_duration_seconds.toFixed(1) }} 秒</el-descriptions-item>
        <el-descriptions-item label="P90 持续时长">{{ currentRow.p90_duration_seconds.toFixed(1) }} 秒</el-descriptions-item>
        <el-descriptions-item label="创建时间" :span="2">{{ currentRow.created_at }}</el-descriptions-item>
        <el-descriptions-item label="审批人" :span="2" v-if="currentRow.approved_by">
          {{ currentRow.approved_by }}
        </el-descriptions-item>
        <el-descriptions-item label="审批时间" :span="2" v-if="currentRow.approved_at">
          {{ currentRow.approved_at }}
        </el-descriptions-item>
        <el-descriptions-item label="理由" :span="2" v-if="currentRow.reason">
          {{ currentRow.reason }}
        </el-descriptions-item>
      </el-descriptions>
    </el-dialog>

    <!-- 审批对话框 -->
    <el-dialog v-model="approveVisible" title="审批调参" width="500px">
      <el-form :model="approveForm" label-width="80px">
        <el-form-item label="理由">
          <el-input
            v-model="approveForm.reason"
            type="textarea"
            :rows="4"
            placeholder="请输入审批理由（可选）"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="approveVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmApprove" :loading="submitting">确认审批</el-button>
      </template>
    </el-dialog>

    <!-- 拒绝对话框 -->
    <el-dialog v-model="rejectVisible" title="拒绝调参" width="500px">
      <el-form :model="rejectForm" label-width="80px">
        <el-form-item label="理由" required>
          <el-input
            v-model="rejectForm.reason"
            type="textarea"
            :rows="4"
            placeholder="请输入拒绝理由"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="rejectVisible = false">取消</el-button>
        <el-button type="danger" @click="confirmReject" :loading="submitting">确认拒绝</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { getTimeWindowAdjustments, triggerTimeWindowAnalysis, approveTimeWindowAdjustment, rejectTimeWindowAdjustment } from '@/api/modules/diagnosis'
import { useUserStore } from '@/stores/user'

interface TimeWindowAdjustment {
  id: number
  device_type: string
  current_window_minutes: number
  proposed_window_minutes: number
  adjustment_percent: number
  sample_count: number
  p50_duration_seconds: number
  p90_duration_seconds: number
  status: string
  reason?: string
  approved_by?: number
  approved_at?: string
  created_at: string
}

const loading = ref(false)
const analyzing = ref(false)
const submitting = ref(false)
const tableData = ref<TimeWindowAdjustment[]>([])
const detailVisible = ref(false)
const approveVisible = ref(false)
const rejectVisible = ref(false)
const currentRow = ref<TimeWindowAdjustment | null>(null)

// WebSocket 和轮询相关
const userStore = useUserStore()
let wsConnection: WebSocket | null = null
let pollingTimer: number | null = null
const POLLING_INTERVAL = 30000 // 30 秒轮询一次

const queryForm = reactive({
  device_type: '',
  status: ''
})

const pagination = reactive({
  page: 1,
  page_size: 20,
  total: 0
})

const approveForm = reactive({
  reason: ''
})

const rejectForm = reactive({
  reason: ''
})

// 获取调参记录列表
const fetchAdjustments = async () => {
  loading.value = true
  try {
    const params = {
      skip: (pagination.page - 1) * pagination.page_size,
      limit: pagination.page_size,
      device_type: queryForm.device_type || undefined,
      status: queryForm.status || undefined
    }
    const response = await getTimeWindowAdjustments(params)
    tableData.value = response.items
    pagination.total = response.total
  } catch (error) {
    ElMessage.error('获取调参记录失败')
    console.error(error)
  } finally {
    loading.value = false
  }
}

// 触发分析
const handleTriggerAnalysis = async () => {
  try {
    await ElMessageBox.confirm(
      '确认触发时间窗口调参分析？分析将基于最近的诊断数据生成调参建议。',
      '确认操作',
      {
        confirmButtonText: '确认',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    analyzing.value = true
    const response = await triggerTimeWindowAnalysis()
    ElMessage.success(
      `分析完成：分析了 ${response.analyzed_device_types} 个设备类型，生成 ${response.total_adjustments} 条调参建议`
    )
    await fetchAdjustments()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '触发分析失败')
      console.error(error)
    }
  } finally {
    analyzing.value = false
  }
}

// 查询
const handleQuery = () => {
  pagination.page = 1
  fetchAdjustments()
}

// 重置
const handleReset = () => {
  queryForm.device_type = ''
  queryForm.status = ''
  handleQuery()
}

// 查看详情
const handleViewDetail = (row: TimeWindowAdjustment) => {
  currentRow.value = row
  detailVisible.value = true
}

// 审批
const handleApprove = (row: TimeWindowAdjustment) => {
  currentRow.value = row
  approveForm.reason = ''
  approveVisible.value = true
}

// 确认审批
const confirmApprove = async () => {
  if (!currentRow.value) return

  submitting.value = true
  try {
    await approveTimeWindowAdjustment(currentRow.value.id, {
      reason: approveForm.reason || undefined
    })
    ElMessage.success('审批成功')
    approveVisible.value = false
    await fetchAdjustments()
  } catch (error: any) {
    ElMessage.error(error.message || '审批失败')
    console.error(error)
  } finally {
    submitting.value = false
  }
}

// 拒绝
const handleReject = (row: TimeWindowAdjustment) => {
  currentRow.value = row
  rejectForm.reason = ''
  rejectVisible.value = true
}

// 确认拒绝
const confirmReject = async () => {
  if (!currentRow.value) return
  if (!rejectForm.reason.trim()) {
    ElMessage.warning('请输入拒绝理由')
    return
  }

  submitting.value = true
  try {
    await rejectTimeWindowAdjustment(currentRow.value.id, {
      reason: rejectForm.reason
    })
    ElMessage.success('已拒绝')
    rejectVisible.value = false
    await fetchAdjustments()
  } catch (error: any) {
    ElMessage.error(error.message || '拒绝失败')
    console.error(error)
  } finally {
    submitting.value = false
  }
}

// 获取调整幅度标签类型
const getAdjustmentType = (percent: number) => {
  const abs = Math.abs(percent)
  if (abs < 10) return 'info'
  if (abs < 50) return 'success'
  if (abs < 100) return 'warning'
  return 'danger'
}

// 获取状态标签类型
const getStatusType = (status: string) => {
  const map: Record<string, any> = {
    pending: 'warning',
    approved: 'success',
    rejected: 'danger'
  }
  return map[status] || 'info'
}

// 获取状态文本
const getStatusText = (status: string) => {
  const map: Record<string, string> = {
    pending: '待审批',
    approved: '已审批',
    rejected: '已拒绝'
  }
  return map[status] || status
}

// 初始化 WebSocket 连接
const initWebSocket = () => {
  try {
    const token = userStore.token
    if (!token) {
      console.warn('未登录，跳过 WebSocket 连接')
      return
    }

    const wsUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8080/ws'
    const url = `${wsUrl}/system?token=${token}`

    wsConnection = new WebSocket(url)

    wsConnection.onopen = () => {
      console.log('WebSocket 连接成功（时间窗口调参）')
    }

    wsConnection.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)

        // 监听时间窗口调参相关消息
        if (data.type === 'time_window_tuning_approval' ||
            data.type === 'time_window_adjustment_updated') {
          console.log('收到时间窗口调参更新通知，刷新列表')
          ElMessage.info('有新的调参建议或状态更新')
          fetchAdjustments()
        }
      } catch (error) {
        console.error('解析 WebSocket 消息失败:', error)
      }
    }

    wsConnection.onerror = (error) => {
      console.error('WebSocket 连接错误:', error)
    }

    wsConnection.onclose = () => {
      console.log('WebSocket 连接关闭')
      // 连接关闭后，启动轮询作为降级方案
      startPolling()
    }
  } catch (error) {
    console.error('初始化 WebSocket 失败:', error)
    // WebSocket 失败，启动轮询
    startPolling()
  }
}

// 启动定时轮询（降级方案）
const startPolling = () => {
  if (pollingTimer) return // 避免重复启动

  console.log('启动定时轮询（每 30 秒）')
  pollingTimer = window.setInterval(() => {
    // 静默刷新，不显示 loading
    const originalLoading = loading.value
    loading.value = false
    fetchAdjustments().finally(() => {
      loading.value = originalLoading
    })
  }, POLLING_INTERVAL)
}

// 停止定时轮询
const stopPolling = () => {
  if (pollingTimer) {
    clearInterval(pollingTimer)
    pollingTimer = null
    console.log('停止定时轮询')
  }
}

// 关闭 WebSocket 连接
const closeWebSocket = () => {
  if (wsConnection) {
    wsConnection.close()
    wsConnection = null
  }
}

onMounted(() => {
  fetchAdjustments()

  // 尝试建立 WebSocket 连接
  initWebSocket()
})

onUnmounted(() => {
  // 清理资源
  closeWebSocket()
  stopPolling()
})
</script>

<style scoped lang="scss">
.time-window-tuning-container {
  padding: 20px;

  .query-card {
    margin-bottom: 20px;

    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
  }

  .table-card {
    :deep(.el-table) {
      font-size: 14px;
    }
  }
}
</style>
