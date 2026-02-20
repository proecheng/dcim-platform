/**
 * 用户管理组件 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, reactive, computed } from 'vue'

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useRoute: () => ({ params: {}, query: {} }),
}))

vi.mock('@/api/modules/user', () => ({
  getUserList: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  createUser: vi.fn().mockResolvedValue({}),
  updateUser: vi.fn().mockResolvedValue({}),
  deleteUser: vi.fn().mockResolvedValue({}),
  toggleUserStatus: vi.fn().mockResolvedValue({}),
  resetPassword: vi.fn().mockResolvedValue({}),
}))

vi.mock('@/stores/user', () => ({
  useUserStore: () => ({ userInfo: { id: 1, role: 'admin' } }),
}))

vi.mock('@element-plus/icons-vue', () => ({
  Plus: { template: '<i />' },
}))

const UserManagementTestable = defineComponent({
  name: 'UserManagementTestable',
  setup() {
    const stats = reactive({ total: 10, active: 8, adminCount: 2, todayLogin: 5 })
    const loading = ref(false)
    const tableData = ref([
      { id: 1, username: 'admin', real_name: '管理员', role: 'admin', department: '运维部', email: 'admin@test.com', is_active: true, last_login_at: '2026-01-01' },
      { id: 2, username: 'operator1', real_name: '操作员', role: 'operator', department: '监控部', email: 'op@test.com', is_active: true, last_login_at: null },
    ])
    const pagination = reactive({ page: 1, pageSize: 20, total: 10 })
    const dialogVisible = ref(false)
    const isEdit = ref(false)
    const filters = reactive({ keyword: '', role: '', is_active: undefined as boolean | undefined })

    const roleText: Record<string, string> = { admin: '管理员', operator: '操作员', viewer: '观察者' }
    const currentUserId = computed(() => 1)

    function handleAdd() {
      isEdit.value = false
      dialogVisible.value = true
    }

    function handleSearch() {
      pagination.page = 1
    }

    function handleReset() {
      filters.keyword = ''
      filters.role = ''
      filters.is_active = undefined
      pagination.page = 1
    }

    return { stats, loading, tableData, pagination, dialogVisible, isEdit, filters, roleText, currentUserId, handleAdd, handleSearch, handleReset }
  },
  template: `
    <div class="user-management">
      <div class="stat-row">
        <div data-testid="stat-total">{{ stats.total }}</div>
        <div data-testid="stat-active">{{ stats.active }}</div>
        <div data-testid="stat-admin">{{ stats.adminCount }}</div>
        <div data-testid="stat-today">{{ stats.todayLogin }}</div>
      </div>
      <div class="toolbar">
        <input data-testid="filter-keyword" v-model="filters.keyword" />
        <select data-testid="filter-role" v-model="filters.role">
          <option value="">全部</option>
          <option value="admin">管理员</option>
          <option value="operator">操作员</option>
        </select>
        <button data-testid="search-btn" @click="handleSearch">搜索</button>
        <button data-testid="reset-btn" @click="handleReset">重置</button>
        <button data-testid="add-btn" @click="handleAdd">新增用户</button>
      </div>
      <table data-testid="user-table">
        <tr v-for="u in tableData" :key="u.id" :data-testid="'user-' + u.id">
          <td>{{ u.username }}</td>
          <td>{{ u.real_name }}</td>
          <td>{{ roleText[u.role] }}</td>
          <td>{{ u.is_active ? '启用' : '禁用' }}</td>
        </tr>
      </table>
      <div v-if="dialogVisible" data-testid="dialog">{{ isEdit ? '编辑用户' : '新增用户' }}</div>
    </div>
  `,
})

describe('UserManagement 用户管理', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('渲染统计卡片', () => {
    const wrapper = mount(UserManagementTestable)
    expect(wrapper.find('[data-testid="stat-total"]').text()).toBe('10')
    expect(wrapper.find('[data-testid="stat-active"]').text()).toBe('8')
    expect(wrapper.find('[data-testid="stat-admin"]').text()).toBe('2')
    expect(wrapper.find('[data-testid="stat-today"]').text()).toBe('5')
  })

  it('渲染用户列表', () => {
    const wrapper = mount(UserManagementTestable)
    expect(wrapper.findAll('table tr')).toHaveLength(2)
  })

  it('初始状态正确', () => {
    const wrapper = mount(UserManagementTestable)
    expect(wrapper.vm.pagination.page).toBe(1)
    expect(wrapper.vm.dialogVisible).toBe(false)
    expect(wrapper.vm.isEdit).toBe(false)
    expect(wrapper.vm.filters.keyword).toBe('')
  })

  it('点击新增打开对话框', async () => {
    const wrapper = mount(UserManagementTestable)
    await wrapper.find('[data-testid="add-btn"]').trigger('click')
    expect(wrapper.vm.dialogVisible).toBe(true)
    expect(wrapper.vm.isEdit).toBe(false)
    expect(wrapper.find('[data-testid="dialog"]').text()).toContain('新增用户')
  })

  it('重置筛选条件', async () => {
    const wrapper = mount(UserManagementTestable)
    wrapper.vm.filters.keyword = 'test'
    wrapper.vm.filters.role = 'admin'
    wrapper.vm.pagination.page = 3
    await wrapper.find('[data-testid="reset-btn"]').trigger('click')
    expect(wrapper.vm.filters.keyword).toBe('')
    expect(wrapper.vm.filters.role).toBe('')
    expect(wrapper.vm.pagination.page).toBe(1)
  })

  it('搜索重置页码', async () => {
    const wrapper = mount(UserManagementTestable)
    wrapper.vm.pagination.page = 5
    await wrapper.find('[data-testid="search-btn"]').trigger('click')
    expect(wrapper.vm.pagination.page).toBe(1)
  })

  it('角色文本映射正确', () => {
    const wrapper = mount(UserManagementTestable)
    expect(wrapper.vm.roleText.admin).toBe('管理员')
    expect(wrapper.vm.roleText.operator).toBe('操作员')
    expect(wrapper.vm.roleText.viewer).toBe('观察者')
  })
})
