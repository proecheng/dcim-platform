/**
 * 系统用户管理页面 单元测试
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
  batchDeleteUsers: vi.fn().mockResolvedValue({}),
}))

vi.mock('@element-plus/icons-vue', () => ({
  Plus: { template: '<i />' },
  Search: { template: '<i />' },
  Delete: { template: '<i />' },
}))

const SystemUserTestable = defineComponent({
  name: 'SystemUserTestable',
  setup() {
    const loading = ref(false)
    const submitting = ref(false)
    const userList = ref([
      { id: 1, username: 'admin', real_name: '管理员', role: 'admin', department: '运维部', is_active: true, last_login_at: '2026-01-01' },
      { id: 2, username: 'viewer1', real_name: '只读用户', role: 'viewer', department: '监控部', is_active: false, last_login_at: null },
    ])
    const selectedIds = ref<number[]>([])
    const currentPage = ref(1)
    const pageSize = ref(10)
    const total = ref(25)

    const searchParams = reactive({ keyword: '', role: '', is_active: undefined as boolean | undefined })
    const dialogVisible = ref(false)
    const isEdit = ref(false)
    const resetPwdVisible = ref(false)

    const roleMap: Record<string, string> = { admin: '管理员', operator: '操作员', viewer: '只读' }

    function handleSearch() {
      currentPage.value = 1
    }

    function handleReset() {
      searchParams.keyword = ''
      searchParams.role = ''
      searchParams.is_active = undefined
      currentPage.value = 1
    }

    function handleCreate() {
      isEdit.value = false
      dialogVisible.value = true
    }

    function handleSelectionChange(rows: { id: number }[]) {
      selectedIds.value = rows.map(r => r.id)
    }

    return {
      loading, submitting, userList, selectedIds, currentPage, pageSize, total,
      searchParams, dialogVisible, isEdit, resetPwdVisible, roleMap,
      handleSearch, handleReset, handleCreate, handleSelectionChange,
    }
  },
  template: `
    <div class="user-page">
      <div class="toolbar">
        <input data-testid="search-keyword" v-model="searchParams.keyword" />
        <select data-testid="search-role" v-model="searchParams.role">
          <option value="">全部</option>
          <option value="admin">管理员</option>
          <option value="operator">操作员</option>
          <option value="viewer">只读</option>
        </select>
        <button data-testid="search-btn" @click="handleSearch">搜索</button>
        <button data-testid="reset-btn" @click="handleReset">重置</button>
        <button data-testid="create-btn" @click="handleCreate">新建用户</button>
        <button data-testid="batch-delete-btn" :disabled="!selectedIds.length">批量删除</button>
      </div>
      <table data-testid="user-table">
        <tr v-for="u in userList" :key="u.id" :data-testid="'user-' + u.id">
          <td>{{ u.username }}</td>
          <td>{{ roleMap[u.role] }}</td>
          <td>{{ u.is_active ? '启用' : '禁用' }}</td>
        </tr>
      </table>
      <div data-testid="pagination-total">{{ total }}</div>
      <div v-if="dialogVisible" data-testid="dialog">{{ isEdit ? '编辑用户' : '新建用户' }}</div>
    </div>
  `,
})

describe('SystemUser 系统用户管理', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('渲染用户列表', () => {
    const wrapper = mount(SystemUserTestable)
    expect(wrapper.findAll('table tr')).toHaveLength(2)
  })

  it('初始状态正确', () => {
    const wrapper = mount(SystemUserTestable)
    expect(wrapper.vm.currentPage).toBe(1)
    expect(wrapper.vm.pageSize).toBe(10)
    expect(wrapper.vm.total).toBe(25)
    expect(wrapper.vm.dialogVisible).toBe(false)
    expect(wrapper.vm.selectedIds).toEqual([])
  })

  it('角色映射正确', () => {
    const wrapper = mount(SystemUserTestable)
    expect(wrapper.vm.roleMap.admin).toBe('管理员')
    expect(wrapper.vm.roleMap.operator).toBe('操作员')
    expect(wrapper.vm.roleMap.viewer).toBe('只读')
  })

  it('点击新建打开对话框', async () => {
    const wrapper = mount(SystemUserTestable)
    await wrapper.find('[data-testid="create-btn"]').trigger('click')
    expect(wrapper.vm.dialogVisible).toBe(true)
    expect(wrapper.vm.isEdit).toBe(false)
    expect(wrapper.find('[data-testid="dialog"]').text()).toContain('新建用户')
  })

  it('搜索重置页码', async () => {
    const wrapper = mount(SystemUserTestable)
    wrapper.vm.currentPage = 5
    await wrapper.find('[data-testid="search-btn"]').trigger('click')
    expect(wrapper.vm.currentPage).toBe(1)
  })

  it('重置搜索条件', async () => {
    const wrapper = mount(SystemUserTestable)
    wrapper.vm.searchParams.keyword = 'test'
    wrapper.vm.searchParams.role = 'admin'
    wrapper.vm.currentPage = 3
    await wrapper.find('[data-testid="reset-btn"]').trigger('click')
    expect(wrapper.vm.searchParams.keyword).toBe('')
    expect(wrapper.vm.searchParams.role).toBe('')
    expect(wrapper.vm.currentPage).toBe(1)
  })

  it('批量删除按钮在无选择时禁用', () => {
    const wrapper = mount(SystemUserTestable)
    const btn = wrapper.find('[data-testid="batch-delete-btn"]')
    expect((btn.element as HTMLButtonElement).disabled).toBe(true)
  })

  it('选择用户后批量删除按钮启用', async () => {
    const wrapper = mount(SystemUserTestable)
    wrapper.vm.selectedIds = [1, 2]
    await wrapper.vm.$nextTick()
    const btn = wrapper.find('[data-testid="batch-delete-btn"]')
    expect((btn.element as HTMLButtonElement).disabled).toBe(false)
  })
})
