<template>
  <el-dialog
    v-model="visible"
    :title="dialogTitle"
    width="720px"
    destroy-on-close
    @closed="handleClose"
  >
    <el-tabs v-model="activeTab">
      <!-- 配置下发标签页 -->
      <el-tab-pane label="配置下发" name="push">
        <div v-if="detailLoading" v-loading="true" style="min-height: 200px;" />
        <template v-else-if="gatewayDetail">
          <div class="config-section">
            <div class="section-title">
              <el-icon><Setting /></el-icon>
              <span>当前网关配置</span>
            </div>
            <div class="config-grid">
              <div class="config-item">
                <span class="config-label">网关标识</span>
                <span class="config-val">{{ gatewayDetail.gateway_id }}</span>
              </div>
              <div class="config-item">
                <span class="config-label">网关名称</span>
                <span class="config-val">{{ gatewayDetail.name }}</span>
              </div>
              <div class="config-item">
                <span class="config-label">IP 地址</span>
                <span class="config-val">{{ gatewayDetail.ip_address || '--' }}</span>
              </div>
              <div class="config-item">
                <span class="config-label">固件版本</span>
                <span class="config-val">{{ gatewayDetail.version || '--' }}</span>
              </div>
              <div class="config-item">
                <span class="config-label">数据源数</span>
                <span class="config-val">{{ gatewayDetail.datasource_count }}</span>
              </div>
              <div class="config-item">
                <span class="config-label">关联点位</span>
                <span class="config-val">{{ gatewayDetail.point_count }}</span>
              </div>
              <div class="config-item">
                <span class="config-label">状态</span>
                <span class="config-val">
                  <el-tag :type="gatewayDetail.status === 'online' ? 'success' : 'danger'" size="small" effect="dark">
                    {{ gatewayDetail.status === 'online' ? '在线' : '离线' }}
                  </el-tag>
                </span>
              </div>
              <div class="config-item">
                <span class="config-label">启用</span>
                <span class="config-val">
                  <el-tag :type="gatewayDetail.is_enabled ? 'success' : 'info'" size="small">
                    {{ gatewayDetail.is_enabled ? '是' : '否' }}
                  </el-tag>
                </span>
              </div>
            </div>
          </div>

          <!-- 最近下发状态 -->
          <div v-if="lastPushResult" class="push-result">
            <div class="section-title">
              <el-icon><Bell /></el-icon>
              <span>最近下发结果</span>
            </div>
            <el-alert
              :title="pushResultTitle"
              :type="pushResultAlertType"
              :description="lastPushResult.error_message || undefined"
              show-icon
              :closable="false"
            />
            <el-button
              v-if="lastPushResult.status === 'failed'"
              type="warning"
              size="small"
              style="margin-top: 8px;"
              :loading="pushing"
              @click="handlePush"
            >
              <el-icon><RefreshRight /></el-icon>
              重试下发
            </el-button>
          </div>
        </template>
      </el-tab-pane>

      <!-- 历史记录标签页 -->
      <el-tab-pane label="历史记录" name="history">
        <el-table :data="historyList" v-loading="historyLoading" stripe size="small">
          <el-table-column label="下发时间" width="170">
            <template #default="{ row }">
              {{ formatTime(row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column label="配置摘要" min-width="200" show-overflow-tooltip>
            <template #default="{ row }">
              {{ formatConfigSnapshot(row.config_snapshot) }}
            </template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="statusTagType(row.status)" size="small" effect="dark">
                {{ statusText(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="错误信息" min-width="150" show-overflow-tooltip>
            <template #default="{ row }">
              <span v-if="row.error_message" class="error-text">{{ row.error_message }}</span>
              <span v-else class="text-muted">--</span>
            </template>
          </el-table-column>
        </el-table>
        <el-pagination
          v-model:current-page="historyPage"
          v-model:page-size="historyPageSize"
          :total="historyTotal"
          :page-sizes="[10, 20]"
          layout="total, sizes, prev, pager, next"
          style="margin-top: 12px; justify-content: flex-end;"
          @size-change="loadHistory"
          @current-change="loadHistory"
        />
      </el-tab-pane>
    </el-tabs>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="visible = false">关闭</el-button>
        <el-button
          v-if="activeTab === 'push'"
          type="primary"
          :loading="pushing"
          :disabled="!canPush"
          @click="handlePush"
        >
          <el-icon><Upload /></el-icon>
          下发配置
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { Setting, Bell, RefreshRight, Upload } from '@element-plus/icons-vue'
import {
  getGatewayDetail,
  pushGatewayConfig,
  getConfigHistory,
  type GatewayDetail,
  type ConfigPushResponse,
  type ConfigPushRecord,
} from '@/api/modules/gateway'

type TagType = 'info' | 'warning' | 'success' | 'danger' | 'primary'

const props = defineProps<{
  modelValue: boolean
  gatewayId: number | null
  gatewayName?: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
  (e: 'pushed'): void
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (val: boolean) => emit('update:modelValue', val),
})

const dialogTitle = computed(() => {
  return props.gatewayName ? `配置下发 — ${props.gatewayName}` : '配置下发'
})

// ── 标签页 ──
const activeTab = ref('push')

// ── 网关详情 ──
const detailLoading = ref(false)
const gatewayDetail = ref<GatewayDetail | null>(null)

// ── 下发状态 ──
const pushing = ref(false)
const lastPushResult = ref<ConfigPushResponse | null>(null)

const canPush = computed(() => {
  if (!gatewayDetail.value) return false
  return gatewayDetail.value.status === 'online' && gatewayDetail.value.is_enabled
})

const pushResultTitle = computed(() => {
  if (!lastPushResult.value) return ''
  const map: Record<string, string> = {
    pending: '配置下发中...',
    delivered: '配置已生效',
    failed: '配置下发失败',
  }
  return map[lastPushResult.value.status] || lastPushResult.value.status
})

const pushResultAlertType = computed<'info' | 'success' | 'warning' | 'error'>(() => {
  if (!lastPushResult.value) return 'info'
  const map: Record<string, 'info' | 'success' | 'warning' | 'error'> = {
    pending: 'info',
    delivered: 'success',
    failed: 'error',
  }
  return map[lastPushResult.value.status] || 'info'
})

// ── 历史记录 ──
const historyLoading = ref(false)
const historyList = ref<ConfigPushRecord[]>([])
const historyPage = ref(1)
const historyPageSize = ref(10)
const historyTotal = ref(0)

// ── 数据加载 ──
async function loadDetail() {
  if (!props.gatewayId) return
  detailLoading.value = true
  try {
    gatewayDetail.value = await getGatewayDetail(props.gatewayId)
  } catch (e) {
    console.error('加载网关详情失败', e)
    ElMessage.error('加载网关详情失败')
  } finally {
    detailLoading.value = false
  }
}

async function loadHistory() {
  if (!props.gatewayId) return
  historyLoading.value = true
  try {
    const res = await getConfigHistory(props.gatewayId, {
      page: historyPage.value,
      page_size: historyPageSize.value,
    })
    historyList.value = res.items
    historyTotal.value = res.total
  } catch (e) {
    console.error('加载配置历史失败', e)
  } finally {
    historyLoading.value = false
  }
}

async function handlePush() {
  if (!props.gatewayId) return
  pushing.value = true
  lastPushResult.value = null
  try {
    const res = await pushGatewayConfig(props.gatewayId)
    lastPushResult.value = res
    if (res.status === 'failed') {
      ElMessage.warning('配置下发失败: ' + (res.error_message || '未知错误'))
    } else {
      ElMessage.success('配置下发成功')
      emit('pushed')
    }
    // 刷新历史
    loadHistory()
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } }; message?: string }
    const msg = err.response?.data?.detail || err.message || '下发请求失败'
    ElMessage.error(msg)
    lastPushResult.value = {
      id: 0,
      gateway_id: '',
      status: 'failed',
      error_message: msg,
      created_at: null,
    }
  } finally {
    pushing.value = false
  }
}

function handleClose() {
  lastPushResult.value = null
  activeTab.value = 'push'
  historyPage.value = 1
}

// ── 辅助函数 ──
function formatTime(t: string | null | undefined): string {
  if (!t) return '--'
  return t.replace('T', ' ').substring(0, 19)
}

function formatConfigSnapshot(snapshot: Record<string, unknown>): string {
  if (!snapshot) return '--'
  const keys = Object.keys(snapshot)
  if (keys.length === 0) return '--'
  // 展示前几个关键字段
  const parts: string[] = []
  for (const key of keys.slice(0, 3)) {
    const val = snapshot[key]
    if (typeof val === 'object' && val !== null) {
      parts.push(`${key}: [${Object.keys(val as Record<string, unknown>).length}项]`)
    } else {
      parts.push(`${key}: ${val}`)
    }
  }
  if (keys.length > 3) parts.push(`...+${keys.length - 3}`)
  return parts.join(', ')
}

function statusTagType(status: string): TagType {
  const map: Record<string, TagType> = {
    pending: 'warning',
    delivered: 'success',
    failed: 'danger',
  }
  return map[status] || 'info'
}

function statusText(status: string): string {
  const map: Record<string, string> = {
    pending: '下发中',
    delivered: '已生效',
    failed: '失败',
  }
  return map[status] || status
}

// ── 监听打开 ──
watch(() => props.modelValue, (val) => {
  if (val && props.gatewayId) {
    loadDetail()
    loadHistory()
  }
})
</script>

<style scoped lang="scss">
@use '@/styles/mixins-25d' as *;

.config-section {
  margin-bottom: 20px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 12px;
  padding-left: 8px;
  border-left: 3px solid #1890ff;
}

.config-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px 16px;

  .config-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 12px;
    background: rgba(255, 255, 255, 0.03);
    border-radius: 6px;
    border: 1px solid var(--border-color, rgba(255, 255, 255, 0.06));
    transition: all 0.25s ease;

    &:hover {
      background: rgba(24, 144, 255, 0.06);
      border-color: rgba(24, 144, 255, 0.2);
      transform: translateY(-1px);
    }

    .config-label {
      font-size: 13px;
      color: var(--text-secondary);
    }

    .config-val {
      font-size: 13px;
      font-weight: 500;
      color: var(--text-primary);
    }
  }
}

.push-result {
  margin-top: 16px;
}

.error-text {
  color: var(--error-color, #f5222d);
  font-size: 12px;
}

.text-muted {
  color: var(--text-secondary);
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

// 暗色主题对话框样式
:deep(.el-dialog) {
  background: var(--bg-card, #1a1a2e);
  border: 1px solid var(--border-color, rgba(255, 255, 255, 0.08));

  .el-dialog__header {
    border-bottom: 1px solid var(--border-color, rgba(255, 255, 255, 0.08));
  }

  .el-dialog__title {
    color: var(--text-primary);
  }

  .el-dialog__footer {
    border-top: 1px solid var(--border-color, rgba(255, 255, 255, 0.08));
  }
}

:deep(.el-tabs__item) {
  font-size: 14px;
}
</style>
