<template>
  <div class="user-management">
    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value">{{ stats.total }}</div>
          <div class="stat-label">总用户数</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value active">{{ stats.active }}</div>
          <div class="stat-label">活跃用户</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value admin">{{ stats.adminCount }}</div>
          <div class="stat-label">管理员</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value today">{{ stats.todayLogin }}</div>
          <div class="stat-label">今日登录</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 搜索和操作栏 -->
    <div class="toolbar">
      <el-form :inline="true" class="filter-form">
        <el-form-item>
          <el-input
            v-model="filters.keyword"
            placeholder="搜索用户名/姓名"
            clearable
            style="width: 200px;"
            @keyup.enter="handleSearch"
          />
        </el-form-item>
        <el-form-item>
          <el-select v-model="filters.role" placeholder="全部角色" clearable style="width: 130px;">
            <el-option label="管理员" value="admin" />
            <el-option label="操作员" value="operator" />
            <el-option label="观察者" value="viewer" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-select v-model="filters.is_active" placeholder="全部状态" clearable style="width: 130px;">
            <el-option label="启用" :value="true" />
            <el-option label="禁用" :value="false" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">搜索</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
      <el-button type="primary" :icon="Plus" @click="handleAdd">新增用户</el-button>
    </div>

    <!-- 用户表格 -->
    <el-table :data="tableData" stripe border v-loading="loading" style="width: 100%;">
      <el-table-column prop="username" label="用户名" width="120" />
      <el-table-column prop="real_name" label="姓名" width="100" />
      <el-table-column prop="role" label="角色" width="100">
        <template #default="{ row }">
          <el-tag :type="roleTagType[row.role]" size="small">
            {{ roleText[row.role] }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="department" label="部门" width="120" />
      <el-table-column prop="email" label="邮箱" min-width="180" />
      <el-table-column prop="is_active" label="状态" width="80">
        <template #default="{ row }">
          <el-switch
            :model-value="row.is_active"
            :disabled="row.id === currentUserId"
            :before-change="() => handleToggleStatus(row)"
          />
        </template>
      </el-table-column>
      <el-table-column prop="last_login_at" label="最后登录" width="170">
        <template #default="{ row }">
          {{ row.last_login_at || '-' }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" link @click="handleEdit(row)">编辑</el-button>
          <el-button type="warning" link @click="handleResetPwd(row)">重置密码</el-button>
          <el-button
            v-if="row.id !== currentUserId"
            type="danger"
            link
            @click="handleDelete(row)"
          >删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页 -->
    <el-pagination
      v-model:current-page="pagination.page"
      v-model:page-size="pagination.pageSize"
      :total="pagination.total"
      :page-sizes="[10, 20, 50]"
      layout="total, sizes, prev, pager, next"
      style="margin-top: 16px; justify-content: flex-end;"
      @size-change="loadData"
      @current-change="loadData"
    />

    <!-- 新增/编辑用户对话框 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑用户' : '新增用户'" width="520px" @closed="resetForm">
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="80px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" :disabled="isEdit" placeholder="3-50个字符" />
        </el-form-item>
        <template v-if="!isEdit">
          <el-form-item label="密码" prop="password">
            <el-input v-model="form.password" type="password" show-password placeholder="≥8位，含大小写+数字+特殊字符" />
          </el-form-item>
          <el-form-item label="确认密码" prop="confirmPassword">
            <el-input v-model="form.confirmPassword" type="password" show-password placeholder="再次输入密码" />
          </el-form-item>
        </template>
        <el-form-item label="姓名" prop="real_name">
          <el-input v-model="form.real_name" placeholder="请输入姓名" />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="form.email" placeholder="请输入邮箱" />
        </el-form-item>
        <el-form-item label="手机" prop="phone">
          <el-input v-model="form.phone" placeholder="请输入手机号" />
        </el-form-item>
        <el-form-item label="角色" prop="role">
          <el-select v-model="form.role" style="width: 100%;">
            <el-option label="管理员" value="admin" />
            <el-option label="操作员" value="operator" />
            <el-option label="观察者" value="viewer" />
          </el-select>
        </el-form-item>
        <el-form-item label="部门" prop="department">
          <el-input v-model="form.department" placeholder="请输入部门" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 重置密码对话框 -->
    <el-dialog v-model="resetPwdVisible" title="重置密码" width="420px" @closed="handleResetPwdClose">
      <el-form ref="resetPwdFormRef" :model="pwdForm" :rules="pwdRules" label-width="80px">
        <el-form-item label="新密码" prop="password">
          <el-input v-model="pwdForm.password" type="password" show-password placeholder="≥8位，含大小写+数字+特殊字符" />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input v-model="pwdForm.confirmPassword" type="password" show-password placeholder="再次输入密码" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetPwdVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleSubmitResetPwd">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
// Removed explicit imports in favor of auto-imports; kept Plus icon import
import { Plus } from '@element-plus/icons-vue'
import {
  getUserList, createUser, updateUser, deleteUser,
  toggleUserStatus, resetPassword,
  type UserInfo, type UserCreateParams, type UserUpdateParams
} from '@/api/modules/user'
import { useUserStore } from '@/stores/user'

// 当前登录用户ID，用于保护自身账户
const userStore = useUserStore()
const currentUserId = computed(() => userStore.userInfo?.id)

// ===== 统计数据 =====
const stats = reactive({
  total: 0,
  active: 0,
  adminCount: 0,
  todayLogin: 0
})

// ===== 筛选条件 =====
const filters = reactive({
  keyword: '',
  role: '',
  is_active: undefined as boolean | undefined
})

// ===== 表格数据 =====
const loading = ref(false)
const tableData = ref<UserInfo[]>([])
const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

// ===== 角色映射 =====
type TagType = 'success' | 'warning' | 'danger' | 'info' | 'primary'
const roleText: Record<string, string> = {
  admin: '管理员',
  operator: '操作员',
  viewer: '观察者'
}
const roleTagType: Record<string, TagType> = {
  admin: 'danger',
  operator: 'warning',
  viewer: 'info'
}

// ===== 新增/编辑对话框 =====
const dialogVisible = ref(false)
const isEdit = ref(false)
const submitLoading = ref(false)
const formRef = ref()
const editingId = ref(0)

const form = reactive({
  username: '',
  password: '',
  confirmPassword: '',
  real_name: '',
  email: '',
  phone: '',
  role: 'operator',
  department: ''
})

// 密码复杂度校验
const validatePassword = (_: any, value: string, callback: any) => {
  if (!value) {
    callback(new Error('请输入密码'))
    return
  }
  if (value.length < 8) {
    callback(new Error('密码长度不能少于8位'))
    return
  }
  if (!/[A-Z]/.test(value)) {
    callback(new Error('密码需包含大写字母'))
    return
  }
  if (!/[a-z]/.test(value)) {
    callback(new Error('密码需包含小写字母'))
    return
  }
  if (!/[0-9]/.test(value)) {
    callback(new Error('密码需包含数字'))
    return
  }
  if (!/[!@#$%^&*(),.?":{}|<>]/.test(value)) {
    callback(new Error('密码需包含特殊字符'))
    return
  }
  callback()
}

const validateConfirmPassword = (_: any, value: string, callback: any) => {
  if (!value) {
    callback(new Error('请确认密码'))
  } else if (value !== form.password) {
    callback(new Error('两次密码不一致'))
  } else {
    callback()
  }
}

const formRules = computed(() => ({
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 50, message: '用户名长度3-50个字符', trigger: 'blur' }
  ],
  password: isEdit.value ? [] : [
    { required: true, validator: validatePassword, trigger: 'blur' }
  ],
  confirmPassword: isEdit.value ? [] : [
    { required: true, validator: validateConfirmPassword, trigger: 'blur' }
  ],
  email: [
    { type: 'email' as const, message: '请输入正确的邮箱格式', trigger: 'blur' }
  ],
  phone: [
    { pattern: /^1[3-9]\d{9}$/, message: '请输入正确的手机号', trigger: 'blur' }
  ],
  role: [
    { required: true, message: '请选择角色', trigger: 'change' }
  ]
}))

// ===== 重置密码对话框 =====
const resetPwdVisible = ref(false)
const resetPwdFormRef = ref()
const resetPwdUserId = ref(0)

const pwdForm = reactive({
  password: '',
  confirmPassword: ''
})

const validatePwdConfirm = (_: any, value: string, callback: any) => {
  if (!value) {
    callback(new Error('请确认密码'))
  } else if (value !== pwdForm.password) {
    callback(new Error('两次密码不一致'))
  } else {
    callback()
  }
}

const pwdRules = {
  password: [
    { required: true, validator: validatePassword, trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, validator: validatePwdConfirm, trigger: 'blur' }
  ]
}

// ===== 数据加载 =====
async function loadData() {
  loading.value = true
  try {
    const params: any = {
      page: pagination.page,
      page_size: pagination.pageSize
    }
    if (filters.keyword) params.keyword = filters.keyword
    if (filters.role) params.role = filters.role
    if (typeof filters.is_active === 'boolean') {
      params.is_active = filters.is_active
    }

    const res = await getUserList(params)
    tableData.value = res.items
    pagination.total = res.total
  } catch (e) {
    console.error('加载用户列表失败', e)
  } finally {
    loading.value = false
  }
}

// Lightweight parallel statistics loading
async function loadStats() {
  try {
    const [allRes, activeRes, adminRes] = await Promise.all([
      getUserList({ page: 1, page_size: 1 }),
      getUserList({ page: 1, page_size: 1, is_active: true }),
      getUserList({ page: 1, page_size: 1, role: 'admin' })
    ])
    stats.total = allRes.total
    stats.active = activeRes.total
    stats.adminCount = adminRes.total
    // 今日登录无法通过现有 API 筛选，暂设为 0
    stats.todayLogin = 0
  } catch (e) {
    console.error('加载统计数据失败', e)
  }
}

// ===== 搜索/重置 =====
function handleSearch() {
  pagination.page = 1
  loadData()
}

function handleReset() {
  filters.keyword = ''
  filters.role = ''
  filters.is_active = undefined
  pagination.page = 1
  loadData()
  loadStats()
}

// ===== 新增 =====
function handleAdd() {
  isEdit.value = false
  editingId.value = 0
  resetForm()
  dialogVisible.value = true
}

// ===== 编辑 =====
function handleEdit(row: UserInfo) {
  isEdit.value = true
  editingId.value = row.id
  Object.assign(form, {
    username: row.username,
    password: '',
    confirmPassword: '',
    real_name: row.real_name || '',
    email: row.email || '',
    phone: row.phone || '',
    role: row.role,
    department: row.department || ''
  })
  dialogVisible.value = true
}

// ===== 提交新增/编辑 =====
async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  submitLoading.value = true
  try {
    if (isEdit.value) {
      // 空字符串转 undefined，避免后端 Pydantic 验证空邮箱/手机报错
      const updateData: UserUpdateParams = {
        real_name: form.real_name || undefined,
        email: form.email || undefined,
        phone: form.phone || undefined,
        role: form.role,
        department: form.department || undefined
      }
      await updateUser(editingId.value, updateData)
      ElMessage.success('更新成功')
    } else {
      const createData: UserCreateParams = {
        username: form.username,
        password: form.password,
        real_name: form.real_name || undefined,
        email: form.email || undefined,
        phone: form.phone || undefined,
        role: form.role,
        department: form.department || undefined
      }
      await createUser(createData)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadData()
    loadStats()
  } catch (e: any) {
    const msg = e?.response?.data?.detail || '操作失败'
    ElMessage.error(msg)
  } finally {
    submitLoading.value = false
  }
}

// ===== 切换状态 =====
async function handleToggleStatus(row: UserInfo): Promise<boolean> {
  if (row.id === currentUserId.value) {
    ElMessage.warning('不能禁用自己的账户')
    return false
  }
  const newStatus = !row.is_active
  try {
    await toggleUserStatus(row.id, newStatus)
    row.is_active = newStatus
    ElMessage.success(newStatus ? '已启用' : '已禁用')
    loadStats()
    return true
  } catch (e) {
    ElMessage.error('操作失败')
    return false
  }
}

// ===== 删除 =====
async function handleDelete(row: UserInfo) {
  if (row.id === currentUserId.value) {
    ElMessage.warning('不能删除自己的账户')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确定删除用户「${row.username}」？此操作不可恢复。`,
      '确认删除',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
    await deleteUser(row.id)
    ElMessage.success('删除成功')
    loadData()
    loadStats()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

// ===== 重置密码 =====
function handleResetPwd(row: UserInfo) {
  resetPwdUserId.value = row.id
  pwdForm.password = ''
  pwdForm.confirmPassword = ''
  resetPwdVisible.value = true
}

async function handleSubmitResetPwd() {
  const valid = await resetPwdFormRef.value?.validate().catch(() => false)
  if (!valid) return

  submitLoading.value = true
  try {
    await resetPassword(resetPwdUserId.value, pwdForm.password)
    ElMessage.success('密码重置成功')
    resetPwdVisible.value = false
  } catch (e: any) {
    const msg = e?.response?.data?.detail || '重置失败'
    ElMessage.error(msg)
  } finally {
    submitLoading.value = false
  }
}

// ===== 表单重置 =====
function resetForm() {
  Object.assign(form, {
    username: '',
    password: '',
    confirmPassword: '',
    real_name: '',
    email: '',
    phone: '',
    role: 'operator',
    department: ''
  })
  formRef.value?.clearValidate()
}

function handleResetPwdClose() {
  pwdForm.password = ''
  pwdForm.confirmPassword = ''
  resetPwdFormRef.value?.clearValidate()
}

// ===== 初始化 =====
onMounted(() => {
  loadData()
  loadStats()
})
</script>

<style scoped lang="scss">
@use '@/styles/mixins-25d' as *;

.user-management {
  @include page-dashboard(4);
  .stat-row {
    margin-bottom: 16px;
  }

  .stat-card {
    text-align: center;

    :deep(.el-card__body) {
      padding: 16px;
    }

    .stat-value {
      font-size: 28px;
      font-weight: 600;
      color: var(--text-primary);
      line-height: 1.4;

      &.active { color: #67c23a; }
      &.admin { color: #e6a23c; }
      &.today { color: #409eff; }
    }

    .stat-label {
      font-size: 13px;
      color: var(--text-secondary);
      margin-top: 4px;
    }
  }

  .toolbar {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 16px;

    .filter-form {
      margin-bottom: 0;
    }
  }
}
</style>
