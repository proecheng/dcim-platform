<template>
  <div class="sites-page">
    <!-- 概览卡片区 -->
    <el-row :gutter="16" class="stat-cards">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon sites-icon">
            <el-icon :size="28"><OfficeBuilding /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ summaryData?.total_sites ?? 0 }}</div>
            <div class="stat-label">站点总数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon devices-icon">
            <el-icon :size="28"><Monitor /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ summaryData?.total_devices ?? 0 }}</div>
            <div class="stat-label">设备总数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon gateways-icon">
            <el-icon :size="28"><Connection /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ summaryData?.total_gateways ?? 0 }}</div>
            <div class="stat-label">网关总数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon alarms-icon">
            <el-icon :size="28"><Bell /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ summaryData?.total_alarms ?? 0 }}</div>
            <div class="stat-label">活跃告警</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 列表区 -->
    <el-card shadow="hover" class="main-card">
      <!-- 工具栏 -->
      <div class="toolbar">
        <div class="toolbar-left">
          <el-input
            v-model="searchKeyword"
            placeholder="搜索站点名称/编码"
            clearable
            style="width: 220px;"
            @keyup.enter="handleSearch"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
          <el-button type="primary" @click="handleSearch">搜索</el-button>
          <el-button @click="handleReset">重置</el-button>
        </div>
        <div class="toolbar-right">
          <el-button type="primary" :icon="Plus" @click="handleCreate">新建站点</el-button>
        </div>
      </div>

      <!-- 数据表格 -->
      <el-table
        :data="filteredSites"
        stripe
        border
        v-loading="loading"
      >
        <el-table-column prop="site_code" label="站点编码" width="130" show-overflow-tooltip />
        <el-table-column prop="site_name" label="站点名称" min-width="160" show-overflow-tooltip />
        <el-table-column prop="address" label="地址" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ row.address || '--' }}</template>
        </el-table-column>
        <el-table-column prop="contact_person" label="联系人" width="110" show-overflow-tooltip>
          <template #default="{ row }">{{ row.contact_person || '--' }}</template>
        </el-table-column>
        <el-table-column prop="device_count" label="设备数" width="90" align="center" />
        <el-table-column prop="gateway_count" label="网关数" width="90" align="center" />
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button
              type="success"
              link
              @click="handleSwitchSite(row)"
            >
              {{ currentSiteId === row.id ? '当前站点' : '切换' }}
            </el-button>
            <el-button type="primary" link @click="handleEdit(row)">编辑</el-button>
            <el-popconfirm
              :title="`确定删除站点「${row.site_name}」吗？删除后不可恢复。`"
              confirm-button-text="确定"
              cancel-button-text="取消"
              @confirm="handleDelete(row)"
            >
              <template #reference>
                <el-button type="danger" link>删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新建/编辑对话框 -->
    <el-dialog append-to-body
      v-model="dialogVisible"
      :title="isEdit ? '编辑站点' : '新建站点'"
      width="560px"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="formRules"
        label-width="90px"
      >
        <el-form-item label="站点编码" prop="site_code">
          <el-input
            v-model="form.site_code"
            placeholder="请输入站点编码（如 DC-BJ-01）"
            :disabled="isEdit"
          />
        </el-form-item>
        <el-form-item label="站点名称" prop="site_name">
          <el-input v-model="form.site_name" placeholder="请输入站点名称" />
        </el-form-item>
        <el-form-item label="地址" prop="address">
          <el-input v-model="form.address" placeholder="请输入站点地址" />
        </el-form-item>
        <el-form-item label="联系人" prop="contact_person">
          <el-input v-model="form.contact_person" placeholder="请输入联系人" />
        </el-form-item>
        <el-form-item label="联系电话" prop="contact_phone">
          <el-input v-model="form.contact_phone" placeholder="请输入联系电话" />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="3"
            placeholder="请输入站点描述"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { Plus, Search, OfficeBuilding, Monitor, Connection, Bell } from '@element-plus/icons-vue'
import {
  getSites,
  createSite,
  updateSite,
  deleteSite,
  getSiteSummary,
} from '@/api/modules/spatial'
import type { Site, SiteForm, SiteSummaryResponse } from '@/api/modules/spatial'
import { useSiteStore } from '@/stores/site'

type FormInstance = InstanceType<typeof import('element-plus')['ElForm']>
type TagType = 'info' | 'warning' | 'success' | 'danger' | 'primary'

// Store
const siteStore = useSiteStore()
const currentSiteId = computed(() => siteStore.currentSiteId)

// 数据状态
const loading = ref(false)
const submitting = ref(false)
const siteList = ref<Site[]>([])
const summaryData = ref<SiteSummaryResponse | null>(null)
const searchKeyword = ref('')

// 过滤后的站点列表
const filteredSites = computed(() => {
  if (!searchKeyword.value) return siteList.value
  const kw = searchKeyword.value.toLowerCase()
  return siteList.value.filter(
    s => s.site_name.toLowerCase().includes(kw) || s.site_code.toLowerCase().includes(kw)
  )
})

// 对话框
const isEdit = ref(false)
const editingId = ref<number | null>(null)
const dialogVisible = ref(false)
const formRef = ref<FormInstance>()

interface SiteFormData {
  site_code: string
  site_name: string
  address: string
  contact_person: string
  contact_phone: string
  description: string
}

const form = reactive<SiteFormData>({
  site_code: '',
  site_name: '',
  address: '',
  contact_person: '',
  contact_phone: '',
  description: '',
})

const formRules = {
  site_code: [{ required: true, message: '请输入站点编码', trigger: 'blur' }],
  site_name: [{ required: true, message: '请输入站点名称', trigger: 'blur' }],
}

// 状态映射
function statusTagType(status: string): TagType {
  const map: Record<string, TagType> = {
    normal: 'success',
    active: 'success',
    alarm: 'danger',
    warning: 'warning',
    offline: 'info',
  }
  return map[status] || 'info'
}

function statusLabel(status: string): string {
  const map: Record<string, string> = {
    normal: '正常',
    active: '正常',
    alarm: '告警',
    warning: '告警',
    offline: '离线',
  }
  return map[status] || status
}

// 初始化：先加载站点列表，再加载汇总（汇总降级依赖站点列表数据）
onMounted(async () => {
  await loadSites()
  loadSummary()
})

// 加载站点列表
async function loadSites() {
  loading.value = true
  try {
    const res = await getSites()
    // request 拦截器已 unwrap，兼容 {data: []} 和直接数组
    const data = (res as unknown as { data?: Site[] }).data ?? res
    siteList.value = Array.isArray(data) ? data : []
  } catch (e) {
    console.error('加载站点列表失败', e)
    ElMessage.error('加载站点列表失败')
  } finally {
    loading.value = false
  }
}

// 加载汇总数据
async function loadSummary() {
  try {
    const res = await getSiteSummary()
    summaryData.value = (res as unknown as { data?: SiteSummaryResponse }).data ?? res
  } catch (e) {
    console.error('加载站点汇总失败，从站点列表计算', e)
    // 从已加载的站点列表计算汇总数据作为降级方案
    if (siteList.value.length > 0) {
      summaryData.value = {
        total_sites: siteList.value.length,
        total_devices: siteList.value.reduce((sum, s) => sum + (s.device_count || 0), 0),
        total_gateways: siteList.value.reduce((sum, s) => sum + (s.gateway_count || 0), 0),
        total_alarms: 0,
        sites: [],
      }
    }
  }
}

// 搜索（computed 自动过滤，此处保留按钮语义）
function handleSearch() {
  // filteredSites 是 computed，searchKeyword 变化自动过滤
}

// 重置
function handleReset() {
  searchKeyword.value = ''
}

// 新建站点
function handleCreate() {
  isEdit.value = false
  editingId.value = null
  Object.assign(form, {
    site_code: '',
    site_name: '',
    address: '',
    contact_person: '',
    contact_phone: '',
    description: '',
  })
  dialogVisible.value = true
}

// 编辑站点
function handleEdit(row: Site) {
  isEdit.value = true
  editingId.value = row.id
  Object.assign(form, {
    site_code: row.site_code,
    site_name: row.site_name,
    address: row.address || '',
    contact_person: row.contact_person || '',
    contact_phone: row.contact_phone || '',
    description: row.description || '',
  })
  dialogVisible.value = true
}

// 提交表单
async function handleSubmit() {
  try {
    await formRef.value?.validate()
  } catch {
    return // 表单校验不通过
  }

  submitting.value = true
  try {
    // 构建提交数据，包含扩展字段
    const payload = {
      site_code: form.site_code,
      site_name: form.site_name,
      address: form.address || undefined,
      description: form.description || undefined,
      contact_person: form.contact_person || undefined,
      contact_phone: form.contact_phone || undefined,
    }

    if (isEdit.value && editingId.value) {
      await updateSite(editingId.value, payload)
      ElMessage.success('更新成功')
    } else {
      await createSite(payload as SiteForm)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadSites()
    loadSummary()
    // 同步 store
    siteStore.fetchSites()
  } catch (e) {
    console.error('操作失败', e)
    ElMessage.error('操作失败')
  } finally {
    submitting.value = false
  }
}

// 删除站点
async function handleDelete(row: Site) {
  try {
    await deleteSite(row.id)
    ElMessage.success('删除成功')
    loadSites()
    loadSummary()
    siteStore.fetchSites()
    // 如果删除的是当前站点，清除选择
    if (currentSiteId.value === row.id) {
      siteStore.switchSite(null)
    }
  } catch (e) {
    console.error('删除失败', e)
    ElMessage.error('删除失败，可能存在关联数据')
  }
}

// 切换站点
function handleSwitchSite(row: Site) {
  if (currentSiteId.value === row.id) {
    siteStore.switchSite(null)
    ElMessage.info('已切换到全部站点')
  } else {
    siteStore.switchSite(row.id)
    ElMessage.success(`已切换到「${row.site_name}」`)
  }
}

// 格式化时间
function formatDateTime(dateStr?: string): string {
  if (!dateStr) return '--'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}
</script>

<style scoped lang="scss">
@use '@/styles/_mixins-25d' as *;

.sites-page {
  @include perspective-container;
  @include enter-stagger(slideInDepth);

  // 概览卡片区
  .stat-cards {
    margin-bottom: 16px;
    @include stat-cards-arc(4, 2deg);

    .stat-card {
      background: var(--bg-card);
      border-color: var(--border-color);

      :deep(.el-card__body) {
        display: flex;
        align-items: center;
        gap: 16px;
        padding: 20px;
      }

      .stat-icon {
        width: 56px;
        height: 56px;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;

        &.sites-icon {
          background: linear-gradient(135deg, rgba(64, 158, 255, 0.2), rgba(64, 158, 255, 0.05));
          color: #409eff;
        }

        &.devices-icon {
          background: linear-gradient(135deg, rgba(103, 194, 58, 0.2), rgba(103, 194, 58, 0.05));
          color: #67c23a;
        }

        &.gateways-icon {
          background: linear-gradient(135deg, rgba(230, 162, 60, 0.2), rgba(230, 162, 60, 0.05));
          color: #e6a23c;
        }

        &.alarms-icon {
          background: linear-gradient(135deg, rgba(245, 108, 108, 0.2), rgba(245, 108, 108, 0.05));
          color: #f56c6c;
        }
      }

      .stat-info {
        .stat-value {
          font-size: 28px;
          font-weight: 700;
          color: var(--text-primary);
          line-height: 1.2;
        }

        .stat-label {
          font-size: 13px;
          color: var(--text-secondary);
          margin-top: 4px;
        }
      }
    }
  }

  // 列表卡片
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

  // 表格样式（与 user.vue 一致）
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

  // 对话框样式（与 user.vue 一致）
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

  :deep(.el-form-item__label) {
    color: var(--text-secondary);
  }

  :deep(.el-input__wrapper),
  :deep(.el-textarea__inner),
  :deep(.el-select .el-input__wrapper) {
    background: rgba(255, 255, 255, 0.05);
    border-color: var(--border-color);

    &:hover {
      border-color: var(--accent-color);
    }
  }

  :deep(.el-input__inner),
  :deep(.el-textarea__inner) {
    color: var(--text-primary);

    &::placeholder {
      color: var(--text-secondary);
    }
  }
}
</style>
