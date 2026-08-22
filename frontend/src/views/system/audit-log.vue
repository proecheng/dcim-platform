<template>
  <div class="audit-log-page">
    <el-card shadow="hover" class="main-card">
      <el-tabs v-model="activeTab" @tab-change="handleTabChange">
        <!-- 操作日志 -->
        <el-tab-pane label="操作日志" name="operation">
          <div class="toolbar">
            <div class="toolbar-left">
              <el-date-picker
                v-model="opFilter.timeRange"
                type="daterange"
                range-separator="至"
                start-placeholder="开始日期"
                end-placeholder="结束日期"
                value-format="YYYY-MM-DD"
                style="width: 260px;"
              />
              <el-input
                v-model="opFilter.username"
                placeholder="用户"
                clearable
                style="width: 130px;"
                @keyup.enter="handleSearch"
              />
              <el-select v-model="opFilter.module" placeholder="全部模块" clearable style="width: 130px;">
                <el-option label="全部" value="" />
                <el-option label="用户" value="user" />
                <el-option label="点位" value="point" />
                <el-option label="告警" value="alarm" />
                <el-option label="配置" value="config" />
                <el-option label="报表" value="report" />
                <el-option label="能源管理" value="energy" />
                <el-option label="数据源" value="datasource" />
                <el-option label="认证" value="auth" />
              </el-select>
              <el-select v-model="opFilter.action" placeholder="全部操作" clearable style="width: 130px;">
                <el-option label="全部" value="" />
                <el-option label="新建" value="create" />
                <el-option label="更新" value="update" />
                <el-option label="删除" value="delete" />
                <el-option label="查询" value="query" />
                <el-option label="导出" value="export" />
                <el-option label="安全事件" value="jwt_tamper_detected" />
              </el-select>
              <el-input
                v-model="opFilter.keyword"
                placeholder="关键词"
                clearable
                style="width: 150px;"
                @keyup.enter="handleSearch"
              />
              <el-button type="primary" @click="handleSearch">搜索</el-button>
              <el-button @click="handleReset">重置</el-button>
            </div>
            <div class="toolbar-right">
              <el-button type="success" @click="handleExport">导出</el-button>
            </div>
          </div>

          <el-table :data="opList" stripe border v-loading="loading">
            <el-table-column prop="created_at" label="时间" width="170">
              <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column prop="username" label="用户" width="120" show-overflow-tooltip />
            <el-table-column prop="module" label="模块" width="100" show-overflow-tooltip />
            <el-table-column prop="action" label="操作" width="100" show-overflow-tooltip />
            <el-table-column prop="target_name" label="目标" min-width="160" show-overflow-tooltip />
            <el-table-column prop="ip_address" label="IP地址" width="140" show-overflow-tooltip />
            <el-table-column prop="remark" label="备注" min-width="180" show-overflow-tooltip>
              <template #default="{ row }">{{ row.remark || '--' }}</template>
            </el-table-column>
          </el-table>

          <div class="pagination-wrapper">
            <el-pagination
              v-model:current-page="opPage"
              v-model:page-size="opPageSize"
              :page-sizes="[10, 20, 50, 100]"
              :total="opTotal"
              layout="total, sizes, prev, pager, next, jumper"
              @size-change="loadOperationLogs"
              @current-change="loadOperationLogs"
            />
          </div>
        </el-tab-pane>

        <!-- 系统日志 -->
        <el-tab-pane label="系统日志" name="system">
          <div class="toolbar">
            <div class="toolbar-left">
              <el-date-picker
                v-model="sysFilter.timeRange"
                type="daterange"
                range-separator="至"
                start-placeholder="开始日期"
                end-placeholder="结束日期"
                value-format="YYYY-MM-DD"
                style="width: 260px;"
              />
              <el-select v-model="sysFilter.log_level" placeholder="全部级别" clearable style="width: 130px;">
                <el-option label="全部" value="" />
                <el-option label="Debug" value="debug" />
                <el-option label="Info" value="info" />
                <el-option label="Warning" value="warning" />
                <el-option label="Error" value="error" />
                <el-option label="Critical" value="critical" />
              </el-select>
              <el-input
                v-model="sysFilter.module"
                placeholder="模块"
                clearable
                style="width: 130px;"
                @keyup.enter="handleSearch"
              />
              <el-input
                v-model="sysFilter.keyword"
                placeholder="关键词"
                clearable
                style="width: 150px;"
                @keyup.enter="handleSearch"
              />
              <el-button type="primary" @click="handleSearch">搜索</el-button>
              <el-button @click="handleReset">重置</el-button>
            </div>
            <div class="toolbar-right">
              <el-button type="success" @click="handleExport">导出</el-button>
            </div>
          </div>

          <el-table :data="sysList" stripe border v-loading="loading">
            <el-table-column prop="created_at" label="时间" width="170">
              <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column prop="log_level" label="级别" width="100" align="center">
              <template #default="{ row }">
                <el-tag :type="levelTagType(row.log_level)" size="small">
                  {{ row.log_level }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="module" label="模块" width="160" show-overflow-tooltip />
            <el-table-column prop="message" label="消息" min-width="300" show-overflow-tooltip />
          </el-table>

          <div class="pagination-wrapper">
            <el-pagination
              v-model:current-page="sysPage"
              v-model:page-size="sysPageSize"
              :page-sizes="[10, 20, 50, 100]"
              :total="sysTotal"
              layout="total, sizes, prev, pager, next, jumper"
              @size-change="loadSystemLogs"
              @current-change="loadSystemLogs"
            />
          </div>
        </el-tab-pane>

        <!-- 通讯日志 -->
        <el-tab-pane label="通讯日志" name="communication">
          <div class="toolbar">
            <div class="toolbar-left">
              <el-date-picker
                v-model="commFilter.timeRange"
                type="daterange"
                range-separator="至"
                start-placeholder="开始日期"
                end-placeholder="结束日期"
                value-format="YYYY-MM-DD"
                style="width: 260px;"
              />
              <el-input-number
                v-model="commFilter.device_id"
                :min="1"
                :precision="0"
                placeholder="正整数设备ID"
                controls-position="right"
                style="width: 130px;"
                @keyup.enter="handleSearch"
              />
              <el-select v-model="commFilter.status" placeholder="全部状态" clearable style="width: 130px;">
                <el-option label="全部" value="" />
                <el-option label="成功" value="success" />
                <el-option label="失败" value="failed" />
                <el-option label="超时" value="timeout" />
              </el-select>
              <el-button type="primary" @click="handleSearch">搜索</el-button>
              <el-button @click="handleReset">重置</el-button>
            </div>
            <div class="toolbar-right">
              <el-button type="success" @click="handleExport">导出</el-button>
            </div>
          </div>

          <el-table :data="commList" stripe border v-loading="loading">
            <el-table-column prop="created_at" label="时间" width="170">
              <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column prop="device_id" label="设备ID" width="100" />
            <el-table-column prop="comm_type" label="类型" width="100" show-overflow-tooltip />
            <el-table-column prop="protocol" label="协议" width="100" show-overflow-tooltip />
            <el-table-column prop="status" label="状态" width="100" align="center">
              <template #default="{ row }">
                <el-tag :type="commStatusTagType(row.status)" size="small">
                  {{ commStatusLabel(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="duration_ms" label="耗时(ms)" width="110" align="right">
              <template #default="{ row }">{{ row.duration_ms ?? '--' }}</template>
            </el-table-column>
          </el-table>

          <div class="pagination-wrapper">
            <el-pagination
              v-model:current-page="commPage"
              v-model:page-size="commPageSize"
              :page-sizes="[10, 20, 50, 100]"
              :total="commTotal"
              layout="total, sizes, prev, pager, next, jumper"
              @size-change="loadCommunicationLogs"
              @current-change="loadCommunicationLogs"
            />
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import {
  getOperationLogs,
  getSystemLogs,
  getCommunicationLogs,
  exportLogs,
} from '@/api/modules/log'
import type { OperationLog, SystemLog, CommunicationLog } from '@/api/modules/log'

// 当前标签
const activeTab = ref<'operation' | 'system' | 'communication'>('operation')
const loading = ref(false)

// ── 操作日志 ──────────────────────────────────────────
const opList = ref<OperationLog[]>([])
const opPage = ref(1)
const opPageSize = ref(20)
const opTotal = ref(0)
const opFilter = reactive({
  timeRange: null as [string, string] | null,
  username: '',
  module: '',
  action: '',
  keyword: '',
})

async function loadOperationLogs() {
  loading.value = true
  try {
    const res = await getOperationLogs({
      page: opPage.value,
      page_size: opPageSize.value,
      start_time: opFilter.timeRange?.[0] || undefined,
      end_time: opFilter.timeRange?.[1] || undefined,
      username: opFilter.username || undefined,
      keyword: opFilter.keyword || undefined,
      module: opFilter.module || undefined,
      action: opFilter.action || undefined,
    })
    opList.value = res.items || []
    opTotal.value = res.total || 0
  } catch (e) {
    console.error('加载操作日志失败', e)
    ElMessage.error('加载操作日志失败')
  } finally {
    loading.value = false
  }
}

// ── 系统日志 ──────────────────────────────────────────
const sysList = ref<SystemLog[]>([])
const sysPage = ref(1)
const sysPageSize = ref(20)
const sysTotal = ref(0)
const sysFilter = reactive({
  timeRange: null as [string, string] | null,
  log_level: '',
  module: '',
  keyword: '',
})

async function loadSystemLogs() {
  loading.value = true
  try {
    const res = await getSystemLogs({
      page: sysPage.value,
      page_size: sysPageSize.value,
      start_time: sysFilter.timeRange?.[0] || undefined,
      end_time: sysFilter.timeRange?.[1] || undefined,
      log_level: sysFilter.log_level || undefined,
      module: sysFilter.module || undefined,
      keyword: sysFilter.keyword || undefined,
    })
    sysList.value = res.items || []
    sysTotal.value = res.total || 0
  } catch (e) {
    console.error('加载系统日志失败', e)
    ElMessage.error('加载系统日志失败')
  } finally {
    loading.value = false
  }
}

// ── 通讯日志 ──────────────────────────────────────────
const commList = ref<CommunicationLog[]>([])
const commPage = ref(1)
const commPageSize = ref(20)
const commTotal = ref(0)
const commFilter = reactive({
  timeRange: null as [string, string] | null,
  device_id: null as number | null,
  status: '',
})

async function loadCommunicationLogs() {
  loading.value = true
  try {
    const res = await getCommunicationLogs({
      page: commPage.value,
      page_size: commPageSize.value,
      start_time: commFilter.timeRange?.[0] || undefined,
      end_time: commFilter.timeRange?.[1] || undefined,
      device_id: commFilter.device_id || undefined,
      status: commFilter.status || undefined,
    })
    commList.value = res.items || []
    commTotal.value = res.total || 0
  } catch (e) {
    console.error('加载通讯日志失败', e)
    ElMessage.error('加载通讯日志失败')
  } finally {
    loading.value = false
  }
}

// ── 通用操作 ──────────────────────────────────────────
function handleTabChange() {
  loadCurrentTab()
}

function loadCurrentTab() {
  if (activeTab.value === 'operation') loadOperationLogs()
  else if (activeTab.value === 'system') loadSystemLogs()
  else loadCommunicationLogs()
}

function handleSearch() {
  if (activeTab.value === 'operation') opPage.value = 1
  else if (activeTab.value === 'system') sysPage.value = 1
  else commPage.value = 1
  loadCurrentTab()
}

function handleReset() {
  if (activeTab.value === 'operation') {
    opFilter.timeRange = null
    opFilter.username = ''
    opFilter.module = ''
    opFilter.action = ''
    opFilter.keyword = ''
    opPage.value = 1
  } else if (activeTab.value === 'system') {
    sysFilter.timeRange = null
    sysFilter.log_level = ''
    sysFilter.module = ''
    sysFilter.keyword = ''
    sysPage.value = 1
  } else {
    commFilter.timeRange = null
    commFilter.device_id = null
    commFilter.status = ''
    commPage.value = 1
  }
  loadCurrentTab()
}

async function handleExport() {
  const logTypeMap = {
    operation: 'operation',
    system: 'system',
    communication: 'communication',
  } as const

  try {
    const blob = await exportLogs({
      log_type: logTypeMap[activeTab.value],
    })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${activeTab.value}_logs_${Date.now()}.csv`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch (e) {
    console.error('导出失败', e)
    ElMessage.error('导出失败')
  }
}

// ── 辅助函数 ──────────────────────────────────────────
type TagType = 'info' | 'warning' | 'success' | 'danger' | 'primary'

function levelTagType(level: string): TagType {
  const map: Record<string, TagType> = {
    debug: 'info',
    info: 'success',
    warning: 'warning',
    error: 'danger',
    critical: 'danger',
  }
  return map[level] || 'info'
}

function commStatusTagType(status: string): TagType {
  const map: Record<string, TagType> = {
    success: 'success',
    failed: 'danger',
    timeout: 'warning',
  }
  return map[status] || 'info'
}

function commStatusLabel(status: string): string {
  const map: Record<string, string> = {
    success: '成功',
    failed: '失败',
    timeout: '超时',
  }
  return map[status] || status
}

function formatDateTime(dateStr?: string): string {
  if (!dateStr) return '--'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

// ── 初始化 ────────────────────────────────────────────
onMounted(() => {
  loadOperationLogs()
})
</script>

<style scoped lang="scss">
@use '@/styles/_mixins-25d' as *;

.audit-log-page {
  @include page-list;

  .main-card {
    background: var(--bg-card);
    border-color: var(--border-color);
  }

  .toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
    flex-wrap: wrap;
    gap: 12px;

    .toolbar-left {
      display: flex;
      gap: 12px;
      align-items: center;
      flex-wrap: wrap;
    }

    .toolbar-right {
      display: flex;
      gap: 12px;
    }
  }

  .pagination-wrapper {
    display: flex;
    justify-content: flex-end;
    margin-top: 16px;
  }

  :deep(.el-tabs__header) {
    margin-bottom: 16px;
  }

  :deep(.el-table) {
    background: transparent;

    th.el-table__cell {
      background: var(--bg-card);
      color: var(--text-primary);
      border-color: var(--border-color);
    }

    td.el-table__cell {
      border-color: var(--border-color);
    }

    tr {
      background: var(--bg-card);

      &:hover > td.el-table__cell {
        background: rgba(255, 255, 255, 0.05);
      }
    }

    .el-table__body tr.el-table__row--striped td.el-table__cell {
      background: rgba(255, 255, 255, 0.02);
    }
  }

  :deep(.el-input__wrapper),
  :deep(.el-select .el-input__wrapper) {
    background: rgba(255, 255, 255, 0.05);
    border-color: var(--border-color);

    &:hover {
      border-color: var(--accent-color);
    }
  }

  :deep(.el-input__inner) {
    color: var(--text-primary);

    &::placeholder {
      color: var(--text-secondary);
    }
  }
}
</style>
