<template>
  <el-dialog
    v-model="visible"
    title="演示数据管理"
    width="500px"
    :close-on-click-modal="!status.loading"
    :close-on-press-escape="!status.loading"
    :show-close="!status.loading"
    destroy-on-close
  >
    <div class="demo-loader">
      <!-- 状态显示 -->
      <div class="status-section">
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="数据状态">
            <el-tag :type="status.is_loaded ? 'success' : 'info'">
              {{ status.is_loaded ? '已加载' : '未加载' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="演示点位数">
            {{ status.demo_point_count || 0 }}
          </el-descriptions-item>
          <el-descriptions-item label="历史记录数">
            {{ formatNumber(status.history_count || 0) }}
          </el-descriptions-item>
        </el-descriptions>
      </div>

      <!-- 加载进度 -->
      <div class="progress-section" v-if="status.loading">
        <el-progress
          :percentage="status.progress"
          :stroke-width="20"
          :text-inside="true"
        />
        <div class="progress-message">{{ status.progress_message }}</div>
      </div>

      <!-- 错误提示 -->
      <div class="error-section" v-if="errorMessage">
        <el-alert :title="errorMessage" type="error" show-icon :closable="false" />
      </div>

      <!-- 操作按钮 -->
      <div class="action-section">
        <template v-if="!status.is_loaded">
          <el-button
            type="primary"
            :loading="status.loading"
            :icon="Download"
            @click="handleLoad"
          >
            {{ status.loading ? '加载中...' : '加载演示数据' }}
          </el-button>
          <div class="action-hint">
            加载约330个监控点位和30天历史数据
          </div>
        </template>
        <template v-else>
          <el-button
            type="success"
            :icon="Refresh"
            @click="handleRefreshDates"
            :loading="refreshing"
          >
            刷新日期到最近
          </el-button>
          <el-button
            type="danger"
            :icon="Delete"
            @click="handleUnload"
            :loading="unloading"
          >
            卸载演示数据
          </el-button>
        </template>
      </div>

      <!-- 说明 -->
      <div class="info-section">
        <el-alert type="info" :closable="false">
          <template #title>
            <strong>演示数据说明</strong>
          </template>
          <ul class="info-list">
            <li>演示数据模拟3层算力中心大楼的动环监控系统</li>
            <li>包含B1制冷机房、F1-F2机房区、F3办公监控区</li>
            <li>加载后可体验完整的监控、告警、能耗等功能</li>
            <li>"刷新日期"可将历史数据更新为最近30天</li>
          </ul>
        </el-alert>
      </div>
    </div>

    <!-- 底部按钮 -->
    <template #footer>
      <el-button @click="handleClose" :disabled="status.loading">
        关闭
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, watch, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Download, Delete, Refresh } from '@element-plus/icons-vue'
import { getDemoStatus, loadDemoData, getDemoProgress, unloadDemoData, refreshDemoDataDates } from '@/api/modules/demo'

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits(['update:modelValue', 'loaded', 'unloaded'])

const visible = ref(false)
const refreshing = ref(false)
const unloading = ref(false)
const errorMessage = ref('')
let progressTimer: number | null = null

const status = reactive({
  is_loaded: false,
  demo_point_count: 0,
  history_count: 0,
  loading: false,
  progress: 0,
  progress_message: ''
})

watch(() => props.modelValue, (val) => {
  visible.value = val
  if (val) {
    errorMessage.value = ''
    fetchStatus()
  }
})

watch(visible, (val) => {
  emit('update:modelValue', val)
  if (!val) {
    stopProgressPolling()
  }
})

onMounted(() => {
  if (props.modelValue) {
    fetchStatus()
  }
})

onUnmounted(() => {
  stopProgressPolling()
})

function stopProgressPolling() {
  if (progressTimer) {
    clearInterval(progressTimer)
    progressTimer = null
  }
}

async function fetchStatus() {
  try {
    errorMessage.value = ''
    const res = await getDemoStatus()
    if (res && res.data) {
      Object.assign(status, res.data)
    } else if (res) {
      // 直接返回的数据格式
      Object.assign(status, res)
    }

    // 如果正在加载，启动进度轮询
    if (status.loading && !progressTimer) {
      startProgressPolling()
    }
  } catch (e: any) {
    console.error('获取演示数据状态失败', e)
    errorMessage.value = '获取状态失败：' + (e.message || '网络错误')
  }
}

function startProgressPolling() {
  stopProgressPolling()
  progressTimer = window.setInterval(async () => {
    try {
      const res = await getDemoProgress()
      const data = res?.data || res
      if (data) {
        Object.assign(status, data)

        if (!data.loading) {
          stopProgressPolling()

          if (data.is_loaded) {
            ElMessage.success('演示数据加载完成')
            emit('loaded')
            fetchStatus() // 刷新状态获取最新数据
          }
        }
      }
    } catch (e) {
      console.error('获取进度失败', e)
    }
  }, 2000)
}

async function handleLoad() {
  try {
    errorMessage.value = ''
    const res = await loadDemoData(30)

    // 处理不同的响应格式
    const code = res?.code ?? (res?.success ? 0 : 1)
    const message = res?.message || ''

    if (code === 0) {
      status.loading = true
      status.progress = 0
      status.progress_message = '开始加载...'
      startProgressPolling()
      ElMessage.info('开始加载演示数据，请稍候...')
    } else {
      ElMessage.warning(message || '启动加载失败')
    }
  } catch (e: any) {
    console.error('启动加载失败', e)
    errorMessage.value = '启动加载失败：' + (e.message || '网络错误')
    ElMessage.error('启动加载失败')
  }
}

async function handleUnload() {
  try {
    await ElMessageBox.confirm(
      '确定要卸载演示数据吗？所有演示点位和历史数据将被删除。',
      '确认卸载',
      { type: 'warning' }
    )

    unloading.value = true
    errorMessage.value = ''
    const res = await unloadDemoData()

    const code = res?.code ?? (res?.success ? 0 : 1)

    if (code === 0) {
      ElMessage.success('演示数据已卸载')
      status.is_loaded = false
      status.demo_point_count = 0
      status.history_count = 0
      emit('unloaded')
    } else {
      ElMessage.error(res?.message || '卸载失败')
    }
  } catch (e: any) {
    if (e !== 'cancel') {
      console.error('卸载失败', e)
      errorMessage.value = '卸载失败：' + (e.message || '操作失败')
    }
  } finally {
    unloading.value = false
  }
}

async function handleRefreshDates() {
  refreshing.value = true
  errorMessage.value = ''
  try {
    const res = await refreshDemoDataDates()
    const code = res?.code ?? (res?.success ? 0 : 1)

    if (code === 0) {
      // 启动进度轮询
      status.loading = true
      status.progress = 0
      status.progress_message = '开始刷新日期...'
      startRefreshPolling()
      ElMessage.info('开始刷新日期，请稍候...')
    } else {
      ElMessage.error(res?.message || '刷新日期失败')
      refreshing.value = false
    }
  } catch (e: any) {
    console.error('刷新日期失败', e)
    errorMessage.value = '刷新日期失败：' + (e.message || '网络错误')
    ElMessage.error('刷新日期失败')
    refreshing.value = false
  }
}

function startRefreshPolling() {
  stopProgressPolling()
  progressTimer = window.setInterval(async () => {
    try {
      const res = await getDemoProgress()
      const data = res?.data || res
      if (data) {
        Object.assign(status, data)

        if (!data.loading) {
          stopProgressPolling()
          refreshing.value = false

          if (status.progress === 100) {
            ElMessage.success('日期刷新完成')
            fetchStatus() // 刷新状态
          }
        }
      }
    } catch (e) {
      console.error('获取进度失败', e)
    }
  }, 1000)
}

function handleClose() {
  if (!status.loading) {
    visible.value = false
  }
}

function formatNumber(num: number): string {
  return num.toLocaleString()
}
</script>

<style scoped lang="scss">
.demo-loader {
  .status-section {
    margin-bottom: 20px;
  }

  .progress-section {
    margin-bottom: 20px;

    .progress-message {
      margin-top: 8px;
      text-align: center;
      color: var(--el-text-color-secondary);
      font-size: 13px;
    }
  }

  .action-section {
    text-align: center;
    margin-bottom: 20px;

    .action-hint {
      margin-top: 8px;
      color: var(--el-text-color-secondary);
      font-size: 12px;
    }
  }

  .info-section {
    .info-list {
      margin: 8px 0 0;
      padding-left: 20px;
      font-size: 12px;
      line-height: 1.8;
    }
  }
}
</style>
