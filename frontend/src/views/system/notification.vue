<template>
  <div class="notification-page">
    <el-card shadow="hover" class="main-card">
      <el-tabs v-model="activeTab">
        <!-- Tab 1: 通知策略 (admin only) -->
        <el-tab-pane v-if="isAdmin" label="通知策略" name="policies">
          <div class="toolbar">
            <div class="toolbar-left">
              <el-select v-model="policyFilter.alarm_level" placeholder="告警级别" clearable style="width: 140px;">
                <el-option label="紧急" value="critical" />
                <el-option label="重要" value="major" />
                <el-option label="次要" value="minor" />
                <el-option label="信息" value="info" />
              </el-select>
              <el-button type="primary" @click="loadPolicies">查询</el-button>
            </div>
            <div class="toolbar-right">
              <el-button type="primary" :icon="Plus" @click="handleCreatePolicy">新增策略</el-button>
            </div>
          </div>
          <el-table :data="policyList" stripe border v-loading="policyLoading">
            <el-table-column prop="name" label="策略名称" min-width="140" show-overflow-tooltip />
            <el-table-column prop="alarm_level" label="告警级别" width="100" align="center">
              <template #default="{ row }">
                <el-tag :type="levelTagType(row.alarm_level)" size="small">{{ levelCn[row.alarm_level] || row.alarm_level }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="生效时段" width="140" align="center">
              <template #default="{ row }">
                {{ row.time_range_start && row.time_range_end ? `${row.time_range_start} - ${row.time_range_end}` : '全天' }}
              </template>
            </el-table-column>
            <el-table-column label="通知渠道" min-width="120">
              <template #default="{ row }">
                {{ (row.channels || []).map((c: string) => channelCn[c] || c).join(', ') }}
              </template>
            </el-table-column>
            <el-table-column prop="is_enabled" label="状态" width="80" align="center">
              <template #default="{ row }">
                <el-tag :type="row.is_enabled ? 'success' : 'info'" size="small">{{ row.is_enabled ? '启用' : '禁用' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="is_default" label="默认" width="70" align="center">
              <template #default="{ row }">
                <el-tag v-if="row.is_default" type="warning" size="small">默认</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="160" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link @click="handleEditPolicy(row)">编辑</el-button>
                <el-popconfirm
                  :title="`确定删除策略「${row.name}」吗？`"
                  confirm-button-text="确定"
                  cancel-button-text="取消"
                  @confirm="handleDeletePolicy(row.id)"
                >
                  <template #reference>
                    <el-button type="danger" link>删除</el-button>
                  </template>
                </el-popconfirm>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!policyLoading && policyList.length === 0" description="暂无通知策略" />
        </el-tab-pane>

        <!-- Tab 2: 通知记录 (all users) -->
        <el-tab-pane label="通知记录" name="records">
          <div class="toolbar">
            <div class="toolbar-left">
              <el-select v-model="recordFilter.channel_type" placeholder="渠道" clearable style="width: 120px;">
                <el-option label="短信" value="sms" />
                <el-option label="邮件" value="email" />
                <el-option label="即时通讯" value="im" />
                <el-option label="语音" value="voice" />
              </el-select>
              <el-select v-model="recordFilter.status" placeholder="状态" clearable style="width: 120px;">
                <el-option label="待发送" value="pending" />
                <el-option label="已发送" value="sent" />
                <el-option label="失败" value="failed" />
                <el-option label="重试中" value="retrying" />
              </el-select>
              <el-select v-model="recordFilter.alarm_level" placeholder="告警级别" clearable style="width: 120px;">
                <el-option label="紧急" value="critical" />
                <el-option label="重要" value="major" />
                <el-option label="次要" value="minor" />
                <el-option label="信息" value="info" />
              </el-select>
              <el-date-picker
                v-model="recordTimeRange"
                type="datetimerange"
                range-separator="至"
                start-placeholder="开始时间"
                end-placeholder="结束时间"
                value-format="YYYY-MM-DDTHH:mm:ss"
                style="width: 360px;"
              />
              <el-button type="primary" @click="handleSearchRecords">查询</el-button>
              <el-button @click="handleResetRecords">重置</el-button>
            </div>
          </div>
          <el-table :data="recordList" stripe border v-loading="recordLoading">
            <el-table-column prop="id" label="ID" width="70" align="center" />
            <el-table-column prop="alarm_level" label="告警级别" width="100" align="center">
              <template #default="{ row }">
                <el-tag v-if="row.alarm_level" :type="levelTagType(row.alarm_level)" size="small">{{ levelCn[row.alarm_level] || row.alarm_level }}</el-tag>
                <span v-else>--</span>
              </template>
            </el-table-column>
            <el-table-column prop="channel_type" label="渠道" width="100" align="center">
              <template #default="{ row }">
                {{ channelCn[row.channel_type] || row.channel_type }}
              </template>
            </el-table-column>
            <el-table-column prop="contact_value" label="接收方" min-width="140" show-overflow-tooltip />
            <el-table-column prop="content_summary" label="内容摘要" min-width="180" show-overflow-tooltip />
            <el-table-column prop="status" label="状态" width="90" align="center">
              <template #default="{ row }">
                <el-tag :type="statusTagType(row.status)" size="small">{{ statusCn[row.status] || row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="error_message" label="错误信息" min-width="140" show-overflow-tooltip>
              <template #default="{ row }">
                {{ row.error_message || '--' }}
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="创建时间" width="170">
              <template #default="{ row }">
                {{ formatDateTime(row.created_at) }}
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!recordLoading && recordList.length === 0" description="暂无通知记录" />
          <div class="pagination-wrapper">
            <el-pagination
              v-model:current-page="recordPage"
              v-model:page-size="recordPageSize"
              :page-sizes="[10, 20, 50, 100]"
              :total="recordTotal"
              layout="total, sizes, prev, pager, next, jumper"
              @size-change="loadRecords"
              @current-change="loadRecords"
            />
          </div>
        </el-tab-pane>

        <!-- Tab 3: 渠道状态 (admin only) -->
        <el-tab-pane v-if="isAdmin" label="渠道状态" name="channels">
          <div v-loading="channelLoading" class="channel-grid">
            <el-card v-for="ch in channelList" :key="ch.channel_type" shadow="hover" class="channel-card">
              <div class="channel-header">
                <span class="channel-name">{{ channelCn[ch.channel_type] || ch.channel_type }}</span>
                <el-tag :type="ch.enabled ? 'success' : 'info'" size="small">{{ ch.enabled ? '已启用' : '未启用' }}</el-tag>
              </div>
              <div class="channel-status">
                <span :class="['status-dot', ch.healthy ? 'healthy' : 'unhealthy']"></span>
                <span>{{ ch.healthy ? '健康' : '异常' }}</span>
              </div>
              <el-button type="primary" size="small" style="margin-top: 12px;" @click="handleTestChannel(ch.channel_type)">测试发送</el-button>
            </el-card>
          </div>
          <el-empty v-if="!channelLoading && channelList.length === 0" description="暂无渠道信息" />
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 策略编辑对话框 -->
    <el-dialog
      append-to-body
      v-model="policyDialogVisible"
      :title="policyIsEdit ? '编辑策略' : '新增策略'"
      width="600px"
    >
      <el-form ref="policyFormRef" :model="policyForm" :rules="policyRules" label-width="100px">
        <el-form-item label="策略名称" prop="name">
          <el-input v-model="policyForm.name" placeholder="请输入策略名称" maxlength="100" />
        </el-form-item>
        <el-form-item label="站点" prop="site_id">
          <el-select v-model="policyForm.site_id" placeholder="全局（不限站点）" clearable style="width: 100%;">
            <el-option v-for="s in siteList" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="告警级别" prop="alarm_level">
          <el-select v-model="policyForm.alarm_level" placeholder="请选择" style="width: 100%;">
            <el-option label="紧急" value="critical" />
            <el-option label="重要" value="major" />
            <el-option label="次要" value="minor" />
            <el-option label="信息" value="info" />
          </el-select>
        </el-form-item>
        <el-form-item label="生效时段">
          <div style="display: flex; gap: 8px; align-items: center;">
            <el-time-picker v-model="policyForm.time_range_start" placeholder="开始" format="HH:mm" value-format="HH:mm" style="width: 45%;" />
            <span>至</span>
            <el-time-picker v-model="policyForm.time_range_end" placeholder="结束" format="HH:mm" value-format="HH:mm" style="width: 45%;" />
          </div>
        </el-form-item>
        <el-form-item label="通知渠道" prop="channels">
          <el-checkbox-group v-model="policyForm.channels">
            <el-checkbox label="sms">短信</el-checkbox>
            <el-checkbox label="email">邮件</el-checkbox>
            <el-checkbox label="im">即时通讯</el-checkbox>
            <el-checkbox label="voice">语音</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="通知对象" prop="notify_user_ids">
          <el-select v-model="policyForm.notify_user_ids" multiple placeholder="请选择通知用户" style="width: 100%;">
            <el-option v-for="u in userOptions" :key="u.id" :label="`${u.real_name || u.username} (${u.username})`" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="启用状态">
          <el-switch v-model="policyForm.is_enabled" />
        </el-form-item>
        <el-form-item label="渠道升级">
          <el-switch v-model="policyForm.channel_escalation_enabled" />
        </el-form-item>
        <el-form-item v-if="policyForm.channel_escalation_enabled" label="升级超时" prop="escalation_timeout_minutes">
          <el-input-number v-model="policyForm.escalation_timeout_minutes" :min="1" placeholder="分钟" />
        </el-form-item>
        <el-form-item v-if="policyForm.channel_escalation_enabled" label="升级顺序">
          <el-select v-model="policyForm.escalation_channel_order" multiple placeholder="请选择渠道顺序" style="width: 100%;">
            <el-option label="短信" value="sms" />
            <el-option label="邮件" value="email" />
            <el-option label="即时通讯" value="im" />
            <el-option label="语音" value="voice" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="policyDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="policySubmitting" @click="handleSubmitPolicy">确定</el-button>
      </template>
    </el-dialog>

    <!-- 渠道测试对话框 -->
    <el-dialog append-to-body v-model="testDialogVisible" title="测试发送" width="420px">
      <el-form label-width="80px">
        <el-form-item label="渠道">
          <el-tag>{{ channelCn[testChannelType] || testChannelType }}</el-tag>
        </el-form-item>
        <el-form-item label="接收方">
          <el-input v-model="testContactValue" placeholder="请输入接收联系方式" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="testDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="testSending" @click="handleSubmitTest">发送测试</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { Plus } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { getSites } from '@/api/modules/spatial'
import { getUserList } from '@/api/modules/user'
import {
  getPolicies, createPolicy, updatePolicy, deletePolicy,
  getRecords, getChannelStatus, testChannel,
} from '@/api/modules/notification'
import type {
  NotificationPolicyItem, NotificationPolicyForm,
  NotificationRecordItem, ChannelStatusItem,
} from '@/api/modules/notification'

type FormInstance = InstanceType<typeof import('element-plus')['ElForm']>

const userStore = useUserStore()
const isAdmin = computed(() => userStore.isAdmin)

// 映射表
const levelCn: Record<string, string> = { critical: '紧急', major: '重要', minor: '次要', info: '信息' }
const channelCn: Record<string, string> = { sms: '短信', email: '邮件', im: '即时通讯', voice: '语音' }
const statusCn: Record<string, string> = { pending: '待发送', sent: '已发送', failed: '失败', retrying: '重试中' }

type TagType = 'danger' | 'warning' | 'info' | 'success' | 'primary'
function levelTagType(level: string): TagType {
  const m: Record<string, TagType> = { critical: 'danger', major: 'warning', minor: 'info', info: 'success' }
  return m[level] || 'info'
}
function statusTagType(status: string): TagType {
  const m: Record<string, TagType> = { sent: 'success', failed: 'danger', pending: 'info', retrying: 'warning' }
  return m[status] || 'info'
}
function formatDateTime(dateStr?: string | null): string {
  if (!dateStr) return '--'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

// ===== Tab 控制 =====
const activeTab = ref(isAdmin.value ? 'policies' : 'records')

// ===== 通知策略 =====
const policyLoading = ref(false)
const policyList = ref<NotificationPolicyItem[]>([])
const policyFilter = reactive({ alarm_level: '' })

async function loadPolicies() {
  policyLoading.value = true
  try {
    const params: Record<string, string> = {}
    if (policyFilter.alarm_level) params.alarm_level = policyFilter.alarm_level
    const res = await getPolicies(params)
    policyList.value = (res as any).data || res || []
  } catch (e) {
    console.error('加载策略失败', e)
  } finally {
    policyLoading.value = false
  }
}

// 策略对话框
const policyDialogVisible = ref(false)
const policyIsEdit = ref(false)
const policyEditId = ref<number | null>(null)
const policySubmitting = ref(false)
const policyFormRef = ref<FormInstance>()
const siteList = ref<{ id: number; name: string }[]>([])
const userOptions = ref<{ id: number; username: string; real_name: string }[]>([])

const policyForm = reactive<NotificationPolicyForm>({
  name: '',
  site_id: null,
  alarm_level: '',
  time_range_start: null,
  time_range_end: null,
  channels: [],
  notify_user_ids: [],
  is_enabled: true,
  channel_escalation_enabled: false,
  escalation_timeout_minutes: null,
  escalation_channel_order: null,
})

const policyRules = computed(() => ({
  name: [{ required: true, message: '请输入策略名称', trigger: 'blur' }],
  alarm_level: [{ required: true, message: '请选择告警级别', trigger: 'change' }],
  channels: [{ type: 'array' as const, required: true, message: '请至少选择一个渠道', trigger: 'change' }],
  notify_user_ids: [{ type: 'array' as const, required: true, message: '请至少选择一个通知对象', trigger: 'change' }],
  escalation_timeout_minutes: policyForm.channel_escalation_enabled
    ? [{ required: true, message: '请输入升级超时时间', trigger: 'blur' }]
    : [],
}))

function resetPolicyForm() {
  Object.assign(policyForm, {
    name: '', site_id: null, alarm_level: '', time_range_start: null, time_range_end: null,
    channels: [], notify_user_ids: [], is_enabled: true,
    channel_escalation_enabled: false, escalation_timeout_minutes: null, escalation_channel_order: null,
  })
}

async function loadSitesAndUsers() {
  try {
    const [sitesRes, usersRes] = await Promise.all([
      getSites(),
      getUserList({ page: 1, page_size: 500 }),
    ])
    siteList.value = ((sitesRes as any).data || sitesRes || []).map((s: any) => ({ id: s.id, name: s.name }))
    const usersData = (usersRes as any).items || (usersRes as any).data?.items || []
    userOptions.value = usersData.map((u: any) => ({ id: u.id, username: u.username, real_name: u.real_name || '' }))
  } catch (e) {
    console.error('加载站点/用户列表失败', e)
  }
}

function handleCreatePolicy() {
  policyIsEdit.value = false
  policyEditId.value = null
  resetPolicyForm()
  loadSitesAndUsers()
  policyDialogVisible.value = true
}

function handleEditPolicy(row: NotificationPolicyItem) {
  policyIsEdit.value = true
  policyEditId.value = row.id
  Object.assign(policyForm, {
    name: row.name,
    site_id: row.site_id,
    alarm_level: row.alarm_level,
    time_range_start: row.time_range_start,
    time_range_end: row.time_range_end,
    channels: row.channels || [],
    notify_user_ids: row.notify_user_ids || [],
    is_enabled: row.is_enabled,
    channel_escalation_enabled: row.channel_escalation_enabled,
    escalation_timeout_minutes: row.escalation_timeout_minutes,
    escalation_channel_order: row.escalation_channel_order,
  })
  loadSitesAndUsers()
  policyDialogVisible.value = true
}

async function handleSubmitPolicy() {
  try {
    await policyFormRef.value?.validate()
  } catch { return }

  policySubmitting.value = true
  try {
    if (policyIsEdit.value && policyEditId.value) {
      await updatePolicy(policyEditId.value, { ...policyForm })
      ElMessage.success('更新成功')
    } else {
      await createPolicy({ ...policyForm })
      ElMessage.success('创建成功')
    }
    policyDialogVisible.value = false
    loadPolicies()
  } catch (e) {
    console.error('操作失败', e)
    ElMessage.error('操作失败')
  } finally {
    policySubmitting.value = false
  }
}

async function handleDeletePolicy(id: number) {
  try {
    await deletePolicy(id)
    ElMessage.success('删除成功')
    loadPolicies()
  } catch (e) {
    console.error('删除失败', e)
    ElMessage.error('删除失败')
  }
}

// ===== 通知记录 =====
const recordLoading = ref(false)
const recordList = ref<NotificationRecordItem[]>([])
const recordTotal = ref(0)
const recordPage = ref(1)
const recordPageSize = ref(20)
const recordTimeRange = ref<[string, string] | null>(null)
const recordFilter = reactive({ channel_type: '', status: '', alarm_level: '' })

async function loadRecords() {
  recordLoading.value = true
  try {
    const params: Record<string, any> = {
      page: recordPage.value,
      page_size: recordPageSize.value,
    }
    if (recordFilter.channel_type) params.channel_type = recordFilter.channel_type
    if (recordFilter.status) params.status = recordFilter.status
    if (recordFilter.alarm_level) params.alarm_level = recordFilter.alarm_level
    if (recordTimeRange.value) {
      params.start_time = recordTimeRange.value[0]
      params.end_time = recordTimeRange.value[1]
    }
    const res = await getRecords(params) as any
    recordList.value = res.items || res.data?.items || []
    recordTotal.value = res.total ?? res.data?.total ?? 0
  } catch (e) {
    console.error('加载记录失败', e)
  } finally {
    recordLoading.value = false
  }
}

function handleSearchRecords() {
  recordPage.value = 1
  loadRecords()
}

function handleResetRecords() {
  recordFilter.channel_type = ''
  recordFilter.status = ''
  recordFilter.alarm_level = ''
  recordTimeRange.value = null
  recordPage.value = 1
  loadRecords()
}

// ===== 渠道状态 =====
const channelLoading = ref(false)
const channelList = ref<ChannelStatusItem[]>([])

async function loadChannels() {
  channelLoading.value = true
  try {
    const res = await getChannelStatus() as any
    channelList.value = res.data || res || []
  } catch (e) {
    console.error('加载渠道状态失败', e)
  } finally {
    channelLoading.value = false
  }
}

// 渠道测试
const testDialogVisible = ref(false)
const testChannelType = ref('')
const testContactValue = ref('')
const testSending = ref(false)

function handleTestChannel(channelType: string) {
  testChannelType.value = channelType
  testContactValue.value = ''
  testDialogVisible.value = true
}

async function handleSubmitTest() {
  if (!testContactValue.value) {
    ElMessage.warning('请输入接收联系方式')
    return
  }
  testSending.value = true
  try {
    const res = await testChannel({ channel_type: testChannelType.value, contact_value: testContactValue.value }) as any
    const data = res.data || res
    if (data.success) {
      ElMessage.success('发送成功')
      testDialogVisible.value = false
    } else {
      ElMessage.error(data.error_message || '发送失败')
    }
  } catch (e) {
    console.error('测试发送失败', e)
    ElMessage.error('测试发送失败')
  } finally {
    testSending.value = false
  }
}

// ===== Tab 切换加载 =====
watch(activeTab, (tab) => {
  if (tab === 'policies' && policyList.value.length === 0) loadPolicies()
  if (tab === 'records' && recordList.value.length === 0) loadRecords()
  if (tab === 'channels' && channelList.value.length === 0) loadChannels()
})

// ===== 初始化 =====
onMounted(() => {
  if (activeTab.value === 'policies') {
    loadPolicies()
  } else {
    loadRecords()
  }
})
</script>

<style scoped lang="scss">
@use '@/styles/_mixins-25d' as *;

.notification-page {
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

  .channel-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 16px;
  }

  .channel-card {
    .channel-header {
      display: flex;
      justify-content: space-between;
      align-items: center;

      .channel-name {
        font-weight: 600;
        font-size: 15px;
      }
    }

    .channel-status {
      display: flex;
      align-items: center;
      gap: 6px;
      margin-top: 8px;
      color: var(--text-secondary);

      .status-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;

        &.healthy {
          background: #67c23a;
        }

        &.unhealthy {
          background: #f56c6c;
        }
      }
    }
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

  :deep(.el-dialog) {
    background: var(--bg-card);
    border: 1px solid var(--border-color);

    .el-dialog__header {
      border-bottom: 1px solid var(--border-color);
    }

    .el-dialog__title {
      color: var(--text-primary);
    }

    .el-dialog__footer {
      border-top: 1px solid var(--border-color);
    }
  }
}
</style>
