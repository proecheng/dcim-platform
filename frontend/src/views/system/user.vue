<template>
  <div class="user-page">
    <el-card shadow="hover" class="main-card">
      <!-- 搜索栏 -->
      <div class="toolbar">
        <div class="toolbar-left">
          <el-input
            v-model="searchParams.keyword"
            placeholder="搜索用户名/姓名/邮箱"
            clearable
            style="width: 220px;"
            @keyup.enter="handleSearch"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
          <el-select v-model="searchParams.role" placeholder="全部角色" clearable style="width: 140px;">
            <el-option label="管理员" value="admin" />
            <el-option label="操作员" value="operator" />
            <el-option label="只读" value="viewer" />
          </el-select>
          <el-select v-model="searchParams.is_active" placeholder="全部状态" clearable style="width: 140px;">
            <el-option label="启用" :value="true" />
            <el-option label="禁用" :value="false" />
          </el-select>
          <el-button type="primary" @click="handleSearch">搜索</el-button>
          <el-button @click="handleReset">重置</el-button>
        </div>
        <div class="toolbar-right">
          <el-button type="primary" :icon="Plus" @click="handleCreate">新建用户</el-button>
          <el-button
            type="danger"
            :icon="Delete"
            :disabled="!selectedIds.length"
            @click="handleBatchDelete"
          >
            批量删除
          </el-button>
        </div>
      </div>

      <!-- 数据表格 -->
      <el-table
        ref="tableRef"
        :data="userList"
        stripe
        border
        v-loading="loading"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="50" align="center" />
        <el-table-column prop="username" label="用户名" min-width="120" show-overflow-tooltip />
        <el-table-column prop="real_name" label="真实姓名" min-width="120" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.real_name || '--' }}
          </template>
        </el-table-column>
        <el-table-column prop="role" label="角色" width="110" align="center">
          <template #default="{ row }">
            <el-tag :type="roleTagType(row.role)" size="small">
              {{ roleMap[row.role] || row.role }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="department" label="部门" min-width="120" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.department || '--' }}
          </template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
              {{ row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="last_login_at" label="最后登录" width="170">
          <template #default="{ row }">
            {{ formatDateTime(row.last_login_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="handleEdit(row)">编辑</el-button>
            <el-button type="warning" link @click="handleResetPassword(row)">重置密码</el-button>
            <el-switch
              :model-value="row.is_active"
              size="small"
              inline-prompt
              active-text="启"
              inactive-text="禁"
              style="margin: 0 8px;"
              @change="(val: boolean) => handleToggleStatus(row, val)"
            />
            <el-popconfirm
              :title="`确定删除用户「${row.username}」吗？`"
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

      <!-- 分页 -->
      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="loadUsers"
          @current-change="loadUsers"
        />
      </div>
    </el-card>

    <!-- 新建/编辑对话框 -->
    <el-dialog append-to-body
      v-model="dialogVisible"
      :title="isEdit ? '编辑用户' : '新建用户'"
      :width="isEdit ? '680px' : '520px'"

    >
      <el-tabs v-if="isEdit" v-model="dialogTab">
        <el-tab-pane label="基本信息" name="basic">
          <el-form ref="formRef" :model="form" :rules="formRules" label-width="80px">
            <el-form-item label="用户名" prop="username">
              <el-input v-model="form.username" placeholder="请输入用户名" :disabled="isEdit" />
            </el-form-item>
            <el-form-item label="真实姓名" prop="real_name">
              <el-input v-model="form.real_name" placeholder="请输入真实姓名" />
            </el-form-item>
            <el-form-item label="邮箱" prop="email">
              <el-input v-model="form.email" placeholder="请输入邮箱" />
            </el-form-item>
            <el-form-item label="手机" prop="phone">
              <el-input v-model="form.phone" placeholder="请输入手机号" />
            </el-form-item>
            <el-form-item label="角色" prop="role">
              <el-select v-model="form.role" placeholder="请选择角色" style="width: 100%;">
                <el-option v-for="item in roleOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
            <el-form-item label="部门" prop="department">
              <el-input v-model="form.department" placeholder="请输入部门" />
            </el-form-item>
          </el-form>
        </el-tab-pane>
        <el-tab-pane label="通知联系方式" name="contacts">
          <div class="contacts-toolbar">
            <el-button type="primary" size="small" :icon="Plus" @click="handleCreateContact">新增</el-button>
            <el-button size="small" @click="handleImportContacts">从账户导入</el-button>
          </div>
          <el-table :data="contactList" stripe border v-loading="contactLoading" size="small">
            <el-table-column prop="channel_type" label="渠道" width="100" align="center">
              <template #default="{ row }">
                {{ contactChannelCn[row.channel_type] || row.channel_type }}
              </template>
            </el-table-column>
            <el-table-column prop="platform" label="平台" width="100">
              <template #default="{ row }">{{ row.platform || '--' }}</template>
            </el-table-column>
            <el-table-column prop="contact_value" label="联系方式" min-width="160" show-overflow-tooltip />
            <el-table-column prop="is_enabled" label="状态" width="80" align="center">
              <template #default="{ row }">
                <el-tag :type="row.is_enabled ? 'success' : 'info'" size="small">{{ row.is_enabled ? '启用' : '禁用' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link size="small" @click="handleEditContact(row)">编辑</el-button>
                <el-popconfirm title="确定删除该联系方式？" @confirm="handleDeleteContact(row.id)">
                  <template #reference>
                    <el-button type="danger" link size="small">删除</el-button>
                  </template>
                </el-popconfirm>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!contactLoading && contactList.length === 0" description="暂无联系方式" :image-size="60" />
        </el-tab-pane>
        <el-tab-pane label="站点权限" name="sites">
          <el-alert
            v-if="form.role === 'admin'"
            title="管理员默认拥有全部站点权限，无需单独分配"
            type="info"
            :closable="false"
            show-icon
          />
          <div v-else v-loading="sitePermissionLoading" class="site-permission-panel">
            <div class="site-permission-toolbar">
              <span>已选择 {{ selectedSiteIds.length }} / {{ availableSites.length }} 个站点</span>
              <div>
                <el-button size="small" @click="selectAllSites">全选</el-button>
                <el-button size="small" @click="selectedSiteIds = []">清空</el-button>
              </div>
            </div>
            <el-checkbox-group v-model="selectedSiteIds" class="site-checkbox-group">
              <el-checkbox
                v-for="site in availableSites"
                :key="site.id"
                :value="site.id"
                border
              >
                <span class="site-checkbox-label">
                  <span>{{ site.site_name }}</span>
                  <small>{{ site.site_code }}</small>
                </span>
              </el-checkbox>
            </el-checkbox-group>
            <el-empty
              v-if="!sitePermissionLoading && availableSites.length === 0"
              description="暂无可分配站点"
              :image-size="60"
            />
            <div class="site-permission-actions">
              <el-button type="primary" :loading="sitePermissionSaving" @click="saveSitePermissions">
                保存站点权限
              </el-button>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
      <!-- 新增用户时不显示 Tab，直接显示表单 -->
      <el-form v-if="!isEdit" ref="formRef" :model="form" :rules="formRules" label-width="80px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" placeholder="请输入密码" show-password />
        </el-form-item>
        <el-form-item label="真实姓名" prop="real_name">
          <el-input v-model="form.real_name" placeholder="请输入真实姓名" />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="form.email" placeholder="请输入邮箱" />
        </el-form-item>
        <el-form-item label="手机" prop="phone">
          <el-input v-model="form.phone" placeholder="请输入手机号" />
        </el-form-item>
        <el-form-item label="角色" prop="role">
          <el-select v-model="form.role" placeholder="请选择角色" style="width: 100%;">
            <el-option v-for="item in roleOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="部门" prop="department">
          <el-input v-model="form.department" placeholder="请输入部门" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button v-if="!isEdit || dialogTab === 'basic'" type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 联系方式编辑对话框 -->
    <el-dialog append-to-body v-model="contactDialogVisible" :title="contactIsEdit ? '编辑联系方式' : '新增联系方式'" width="420px">
      <el-form ref="contactFormRef" :model="contactForm" :rules="contactRules" label-width="80px">
        <el-form-item label="渠道" prop="channel_type">
          <el-select v-model="contactForm.channel_type" placeholder="请选择" style="width: 100%;">
            <el-option label="短信" value="sms" />
            <el-option label="邮件" value="email" />
            <el-option label="即时通讯" value="im" />
            <el-option label="语音" value="voice" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="contactForm.channel_type === 'im'" label="平台">
          <el-select v-model="contactForm.platform" placeholder="请选择平台" clearable style="width: 100%;">
            <el-option label="钉钉" value="dingtalk" />
            <el-option label="企业微信" value="wecom" />
          </el-select>
        </el-form-item>
        <el-form-item label="联系方式" prop="contact_value">
          <el-input v-model="contactForm.contact_value" placeholder="请输入联系方式" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="contactForm.is_enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="contactDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="contactSubmitting" @click="handleSubmitContact">确定</el-button>
      </template>
    </el-dialog>

    <!-- 重置密码对话框 -->
    <el-dialog append-to-body
      v-model="resetPwdVisible"
      title="重置密码"
      width="420px"
    >
      <el-form
        ref="resetPwdFormRef"
        :model="resetPwdForm"
        :rules="resetPwdRules"
        label-width="80px"
      >
        <el-form-item label="新密码" prop="new_password">
          <el-input
            v-model="resetPwdForm.new_password"
            type="password"
            placeholder="请输入新密码"
            show-password
          />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirm_password">
          <el-input
            v-model="resetPwdForm.confirm_password"
            type="password"
            placeholder="请再次输入新密码"
            show-password
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetPwdVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitResetPassword">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { Plus, Search, Delete } from '@element-plus/icons-vue'
import {
  getUserList,
  createUser,
  updateUser,
  deleteUser,
  toggleUserStatus,
  resetPassword,
  batchDeleteUsers,
  getUserSites,
  updateUserSites
} from '@/api/modules/user'
import type { UserInfo, UserCreateParams, UserUpdateParams } from '@/api/modules/user'
import { getSites } from '@/api/modules/spatial'
import type { Site } from '@/api/modules/spatial'
import {
  getUserContacts,
  createContact as apiCreateContact,
  updateContact as apiUpdateContact,
  deleteContact as apiDeleteContact,
  importFromProfile,
} from '@/api/modules/notification'
import type { ContactItem, ContactForm } from '@/api/modules/notification'
import { isValidOptionalEmail, isValidOptionalPhone } from '@/utils/userValidation'
import { getApiErrorMessage } from '@/utils/apiErrorMessage'

type FormInstance = InstanceType<typeof import('element-plus')['ElForm']>

function showApiError(error: unknown, fallback: string, logLabel = fallback) {
  const status = (error as any)?.response?.status
  if (status !== 400 && status !== 409) {
    console.error(logLabel, error)
  }
  ElMessage.error(getApiErrorMessage(error, fallback))
}

// 角色映射
const roleMap: Record<string, string> = {
  admin: '管理员',
  operator: '操作员',
  viewer: '只读'
}

const roleOptions = [
  { label: '管理员', value: 'admin' },
  { label: '操作员', value: 'operator' },
  { label: '只读', value: 'viewer' }
]

type TagType = 'info' | 'warning' | 'success' | 'danger' | 'primary'
function roleTagType(role: string): TagType {
  const map: Record<string, TagType> = { admin: 'primary', operator: 'warning', viewer: 'info' }
  return map[role] || 'info'
}

// 数据状态
const loading = ref(false)
const submitting = ref(false)
const userList = ref<UserInfo[]>([])
const selectedIds = ref<number[]>([])

// 分页
const currentPage = ref(1)
const pageSize = ref(10)
const total = ref(0)

// 搜索参数
const searchParams = reactive<{
  keyword: string
  role: string
  is_active: boolean | undefined
}>({
  keyword: '',
  role: '',
  is_active: undefined
})

// 表格引用
const tableRef = ref()

// 新建/编辑对话框
const isEdit = ref(false)
const editingId = ref<number | null>(null)
const dialogVisible = ref(false)
const formRef = ref<FormInstance>()
const form = reactive({
  username: '',
  password: '',
  real_name: '',
  email: '',
  phone: '',
  role: '',
  department: ''
})

function validateOptionalEmail(_rule: unknown, value: string, callback: (error?: Error) => void) {
  if (!isValidOptionalEmail(value)) {
    callback(new Error('请输入正确的邮箱地址'))
    return
  }
  callback()
}

function validateOptionalPhone(_rule: unknown, value: string, callback: (error?: Error) => void) {
  if (!isValidOptionalPhone(value)) {
    callback(new Error('请输入正确的手机号'))
    return
  }
  callback()
}

const formRules = computed(() => ({
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: isEdit.value ? [] : [{ required: true, message: '请输入密码', trigger: 'blur' }],
  email: [{ validator: validateOptionalEmail, trigger: ['blur', 'change'] }],
  phone: [{ validator: validateOptionalPhone, trigger: ['blur', 'change'] }],
  role: [{ required: true, message: '请选择角色', trigger: 'change' }]
}))

// 重置密码对话框
const resetPwdVisible = ref(false)
const resetPwdUserId = ref<number | null>(null)
const resetPwdFormRef = ref<FormInstance>()
const resetPwdForm = reactive({
  new_password: '',
  confirm_password: ''
})

const resetPwdRules = {
  new_password: [{ required: true, message: '请输入新密码', trigger: 'blur' }],
  confirm_password: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    {
      validator: (_rule: unknown, value: string, callback: (err?: Error) => void) => {
        if (value !== resetPwdForm.new_password) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ]
}

// 初始化
onMounted(() => {
  loadUsers()
})

// 加载用户列表
async function loadUsers() {
  loading.value = true
  try {
    const res = await getUserList({
      page: currentPage.value,
      page_size: pageSize.value,
      keyword: searchParams.keyword || undefined,
      role: searchParams.role || undefined,
      is_active: searchParams.is_active
    })
    userList.value = res.items || []
    total.value = res.total || 0
  } catch (e) {
    console.error('加载用户列表失败', e)
    ElMessage.error('加载用户列表失败')
  } finally {
    loading.value = false
  }
}

// 搜索
function handleSearch() {
  currentPage.value = 1
  loadUsers()
}

// 重置搜索
function handleReset() {
  searchParams.keyword = ''
  searchParams.role = ''
  searchParams.is_active = undefined
  currentPage.value = 1
  loadUsers()
}

// 表格选择变化
function handleSelectionChange(rows: UserInfo[]) {
  selectedIds.value = rows.map(r => r.id)
}

// 新建用户
function handleCreate() {
  isEdit.value = false
  editingId.value = null
  Object.assign(form, {
    username: '',
    password: '',
    real_name: '',
    email: '',
    phone: '',
    role: '',
    department: ''
  })
  dialogVisible.value = true
}

// 编辑用户
function handleEdit(row: UserInfo) {
  isEdit.value = true
  editingId.value = row.id
  dialogTab.value = 'basic'
  contactList.value = []
  availableSites.value = []
  selectedSiteIds.value = []
  Object.assign(form, {
    username: row.username,
    password: '',
    real_name: row.real_name || '',
    email: row.email || '',
    phone: row.phone || '',
    role: row.role || '',
    department: row.department || ''
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
    const email = form.email.trim() || undefined
    const phone = form.phone.trim() || undefined
    if (isEdit.value && editingId.value) {
      const payload: UserUpdateParams = {
        real_name: form.real_name || undefined,
        email,
        phone,
        role: form.role || undefined,
        department: form.department || undefined
      }
      await updateUser(editingId.value, payload)
      ElMessage.success('更新成功')
    } else {
      const payload: UserCreateParams = {
        username: form.username,
        password: form.password,
        real_name: form.real_name || undefined,
        email,
        phone,
        role: form.role || undefined,
        department: form.department || undefined
      }
      await createUser(payload)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadUsers()
  } catch (e) {
    showApiError(e, '操作失败')
  } finally {
    submitting.value = false
  }
}

// 删除用户
async function handleDelete(row: UserInfo) {
  try {
    await deleteUser(row.id)
    ElMessage.success('删除成功')
    loadUsers()
  } catch (e) {
    showApiError(e, '删除失败')
  }
}

// 批量删除
async function handleBatchDelete() {
  if (!selectedIds.value.length) return
  try {
    await ElMessageBox.confirm(
      `确定删除选中的 ${selectedIds.value.length} 个用户吗？`,
      '批量删除确认',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    await batchDeleteUsers(selectedIds.value)
    ElMessage.success('批量删除成功')
    selectedIds.value = []
    loadUsers()
  } catch (e) {
    if (e !== 'cancel') {
      showApiError(e, '批量删除失败')
    }
  }
}

// 启用/禁用
async function handleToggleStatus(row: UserInfo, val: boolean) {
  try {
    await toggleUserStatus(row.id, val)
    ElMessage.success(val ? '已启用' : '已禁用')
    loadUsers()
  } catch (e) {
    showApiError(e, '状态切换失败')
  }
}

// 重置密码
function handleResetPassword(row: UserInfo) {
  resetPwdUserId.value = row.id
  resetPwdForm.new_password = ''
  resetPwdForm.confirm_password = ''
  resetPwdVisible.value = true
}

async function submitResetPassword() {
  try {
    await resetPwdFormRef.value?.validate()
  } catch {
    return // 表单校验不通过
  }

  if (!resetPwdUserId.value) return
  submitting.value = true
  try {
    await resetPassword(resetPwdUserId.value, resetPwdForm.new_password)
    ElMessage.success('密码重置成功')
    resetPwdVisible.value = false
  } catch (e) {
    showApiError(e, '密码重置失败')
  } finally {
    submitting.value = false
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
    minute: '2-digit'
  })
}

// ===== 通知联系方式 =====
const dialogTab = ref('basic')
const contactChannelCn: Record<string, string> = { sms: '短信', email: '邮件', im: '即时通讯', voice: '语音' }
const contactLoading = ref(false)
const contactList = ref<ContactItem[]>([])
const sitePermissionLoading = ref(false)
const sitePermissionSaving = ref(false)
const availableSites = ref<Site[]>([])
const selectedSiteIds = ref<number[]>([])

// 联系方式对话框
const contactDialogVisible = ref(false)
const contactIsEdit = ref(false)
const contactEditId = ref<number | null>(null)
const contactSubmitting = ref(false)
const contactFormRef = ref<FormInstance>()
const contactForm = reactive<ContactForm>({
  channel_type: '',
  platform: null,
  contact_value: '',
  is_enabled: true,
})
const contactRules = {
  channel_type: [{ required: true, message: '请选择渠道', trigger: 'change' }],
  contact_value: [{ required: true, message: '请输入联系方式', trigger: 'blur' }],
}

async function loadContacts() {
  if (!editingId.value) return
  contactLoading.value = true
  try {
    const res = await getUserContacts(editingId.value) as any
    contactList.value = res.data || res || []
  } catch (e) {
    console.error('加载联系方式失败', e)
  } finally {
    contactLoading.value = false
  }
}

watch(dialogTab, (tab) => {
  if (tab === 'contacts' && contactList.value.length === 0) {
    loadContacts()
  } else if (tab === 'sites' && form.role !== 'admin' && availableSites.value.length === 0) {
    loadSitePermissions()
  }
})

async function loadSitePermissions() {
  if (!editingId.value) return
  sitePermissionLoading.value = true
  try {
    const [sitesResult, assignedSites] = await Promise.all([
      getSites(),
      getUserSites(editingId.value)
    ])
    const sites = (sitesResult as unknown as { data?: Site[] }).data ?? sitesResult
    availableSites.value = Array.isArray(sites) ? sites : []
    selectedSiteIds.value = assignedSites.map(site => site.site_id)
  } catch (e) {
    showApiError(e, '加载站点权限失败')
  } finally {
    sitePermissionLoading.value = false
  }
}

function selectAllSites() {
  selectedSiteIds.value = availableSites.value.map(site => site.id)
}

async function saveSitePermissions() {
  if (!editingId.value) return
  sitePermissionSaving.value = true
  try {
    const result = await updateUserSites(editingId.value, selectedSiteIds.value)
    ElMessage.success(result.message || '站点权限已保存')
  } catch (e) {
    showApiError(e, '保存站点权限失败')
  } finally {
    sitePermissionSaving.value = false
  }
}

function handleCreateContact() {
  contactIsEdit.value = false
  contactEditId.value = null
  Object.assign(contactForm, { channel_type: '', platform: null, contact_value: '', is_enabled: true })
  contactDialogVisible.value = true
}

function handleEditContact(row: ContactItem) {
  contactIsEdit.value = true
  contactEditId.value = row.id
  Object.assign(contactForm, {
    channel_type: row.channel_type,
    platform: row.platform,
    contact_value: row.contact_value,
    is_enabled: row.is_enabled,
  })
  contactDialogVisible.value = true
}

async function handleSubmitContact() {
  try {
    await contactFormRef.value?.validate()
  } catch { return }

  if (!editingId.value) return
  contactSubmitting.value = true
  try {
    if (contactIsEdit.value && contactEditId.value) {
      await apiUpdateContact(editingId.value, contactEditId.value, { ...contactForm })
      ElMessage.success('更新成功')
    } else {
      await apiCreateContact(editingId.value, { ...contactForm })
      ElMessage.success('创建成功')
    }
    contactDialogVisible.value = false
    loadContacts()
  } catch (e) {
    showApiError(e, '操作失败')
  } finally {
    contactSubmitting.value = false
  }
}

async function handleDeleteContact(contactId: number) {
  if (!editingId.value) return
  try {
    await apiDeleteContact(editingId.value, contactId)
    ElMessage.success('删除成功')
    loadContacts()
  } catch (e) {
    showApiError(e, '删除失败')
  }
}

async function handleImportContacts() {
  if (!editingId.value) return
  try {
    await importFromProfile(editingId.value)
    ElMessage.success('导入成功')
    loadContacts()
  } catch (e) {
    showApiError(e, '导入失败')
  }
}
</script>

<style scoped lang="scss">
@use '@/styles/_mixins-25d' as *;

.user-page {
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

  .contacts-toolbar {
    display: flex;
    gap: 8px;
    margin-bottom: 12px;
  }

  .site-permission-panel {
    min-height: 180px;
  }

  .site-permission-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
    color: var(--text-secondary);
  }

  .site-checkbox-group {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px;

    :deep(.el-checkbox) {
      width: 100%;
      height: auto;
      min-height: 48px;
      margin: 0;
    }
  }

  .site-checkbox-label {
    display: flex;
    flex-direction: column;
    gap: 2px;

    small {
      color: var(--text-secondary);
    }
  }

  .site-permission-actions {
    display: flex;
    justify-content: flex-end;
    margin-top: 20px;
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
