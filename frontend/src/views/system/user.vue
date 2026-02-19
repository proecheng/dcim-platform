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
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑用户' : '新建用户'"
      width="520px"
      destroy-on-close
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="formRules"
        label-width="80px"
      >
        <el-form-item label="用户名" prop="username">
          <el-input
            v-model="form.username"
            placeholder="请输入用户名"
            :disabled="isEdit"
          />
        </el-form-item>
        <el-form-item v-if="!isEdit" label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            show-password
          />
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
            <el-option
              v-for="item in roleOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="部门" prop="department">
          <el-input v-model="form.department" placeholder="请输入部门" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 重置密码对话框 -->
    <el-dialog
      v-model="resetPwdVisible"
      title="重置密码"
      width="420px"
      destroy-on-close
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
  batchDeleteUsers
} from '@/api/modules/user'
import type { UserInfo, UserCreateParams, UserUpdateParams } from '@/api/modules/user'

type FormInstance = InstanceType<typeof import('element-plus')['ElForm']>

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

const formRules = computed(() => ({
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: isEdit.value ? [] : [{ required: true, message: '请输入密码', trigger: 'blur' }],
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
  const valid = await formRef.value?.validate()
  if (!valid) return

  submitting.value = true
  try {
    if (isEdit.value && editingId.value) {
      const payload: UserUpdateParams = {
        real_name: form.real_name || undefined,
        email: form.email || undefined,
        phone: form.phone || undefined,
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
        email: form.email || undefined,
        phone: form.phone || undefined,
        role: form.role || undefined,
        department: form.department || undefined
      }
      await createUser(payload)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadUsers()
  } catch (e) {
    console.error('操作失败', e)
    ElMessage.error('操作失败')
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
    console.error('删除失败', e)
    ElMessage.error('删除失败')
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
      console.error('批量删除失败', e)
      ElMessage.error('批量删除失败')
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
    console.error('状态切换失败', e)
    ElMessage.error('状态切换失败')
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
  const valid = await resetPwdFormRef.value?.validate()
  if (!valid) return

  if (!resetPwdUserId.value) return
  submitting.value = true
  try {
    await resetPassword(resetPwdUserId.value, resetPwdForm.new_password)
    ElMessage.success('密码重置成功')
    resetPwdVisible.value = false
  } catch (e) {
    console.error('密码重置失败', e)
    ElMessage.error('密码重置失败')
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
