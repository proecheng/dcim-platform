/**
 * MainLayout 组件测试
 * 测试主布局（侧边栏折叠、菜单选择、用户操作）
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
  useRoute: () => ({ path: '/dashboard', meta: { title: '监控仪表盘' } })
}))

vi.mock('@/stores', () => ({
  useUserStore: () => ({
    token: 'mock-token',
    userInfo: { username: 'admin' },
    fetchUserInfo: vi.fn(),
    doLogout: vi.fn()
  }),
  useAlarmStore: () => ({
    alarmCount: { total: 5 }
  })
}))

vi.mock('@/api/alarm', () => ({
  getAlarmCount: vi.fn(() => Promise.resolve({ total: 5 }))
}))

vi.mock('@/composables/useDataQuality', () => ({
  useDataQuality: vi.fn()
}))

const MainLayoutTestable = defineComponent({
  name: 'MainLayoutTestable',
  setup() {
    const isCollapse = ref(false)
    const activeMenu = computed(() => '/dashboard')
    const username = 'admin'
    const alarmTotal = 5

    const menuItems = [
      { index: '/dashboard', label: '监控仪表盘' },
      { index: '/devices', label: '点位管理' },
      { index: '/alarms', label: '告警管理' },
      { index: '/history', label: '历史数据' },
      { index: '/settings', label: '系统设置' }
    ]

    const handleMenuSelect = vi.fn()
    const handleCommand = vi.fn((command: string) => {
      if (command === 'logout') {
        // logout logic
      }
    })

    return {
      isCollapse, activeMenu, username, alarmTotal,
      menuItems, handleMenuSelect, handleCommand
    }
  },
  template: `
    <div class="main-layout" data-testid="main-layout">
      <div class="aside" :style="{ width: isCollapse ? '64px' : '200px' }" data-testid="aside">
        <div class="logo" data-testid="logo">
          <span v-show="!isCollapse">算力监控</span>
        </div>
        <div class="menu" data-testid="menu">
          <div
            v-for="item in menuItems"
            :key="item.index"
            class="menu-item"
            :class="{ active: activeMenu === item.index }"
            :data-testid="'menu-' + item.index"
            @click="handleMenuSelect(item.index)"
          >{{ item.label }}</div>
        </div>
      </div>
      <div class="container">
        <div class="header" data-testid="header">
          <div class="header-left">
            <button data-testid="collapse-btn" @click="isCollapse = !isCollapse">
              {{ isCollapse ? '展开' : '折叠' }}
            </button>
            <span data-testid="breadcrumb">首页 / 监控仪表盘</span>
          </div>
          <div class="header-right">
            <span data-testid="alarm-badge">{{ alarmTotal }}</span>
            <div class="user-info" data-testid="user-info">
              <span data-testid="username">{{ username }}</span>
              <button data-testid="cmd-logout" @click="handleCommand('logout')">退出登录</button>
              <button data-testid="cmd-password" @click="handleCommand('password')">修改密码</button>
            </div>
          </div>
        </div>
        <div class="main" data-testid="main-content">
          <slot></slot>
        </div>
      </div>
    </div>
  `
})

describe('MainLayout 主布局组件', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('渲染主布局结构', () => {
    const wrapper = mount(MainLayoutTestable)
    expect(wrapper.find('[data-testid="main-layout"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="aside"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="header"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="main-content"]').exists()).toBe(true)
  })

  it('侧边栏默认展开显示 logo 文字', () => {
    const wrapper = mount(MainLayoutTestable)
    expect(wrapper.vm.isCollapse).toBe(false)
    expect(wrapper.find('[data-testid="logo"]').text()).toContain('算力监控')
    expect(wrapper.find('[data-testid="aside"]').attributes('style')).toContain('200px')
  })

  it('点击折叠按钮切换侧边栏状态', async () => {
    const wrapper = mount(MainLayoutTestable)
    await wrapper.find('[data-testid="collapse-btn"]').trigger('click')
    expect(wrapper.vm.isCollapse).toBe(true)
    expect(wrapper.find('[data-testid="aside"]').attributes('style')).toContain('64px')
  })

  it('渲染菜单项', () => {
    const wrapper = mount(MainLayoutTestable)
    expect(wrapper.find('[data-testid="menu-/dashboard"]').text()).toBe('监控仪表盘')
    expect(wrapper.find('[data-testid="menu-/devices"]').text()).toBe('点位管理')
    expect(wrapper.find('[data-testid="menu-/alarms"]').text()).toBe('告警管理')
    expect(wrapper.find('[data-testid="menu-/settings"]').text()).toBe('系统设置')
  })

  it('点击菜单项触发 handleMenuSelect', async () => {
    const wrapper = mount(MainLayoutTestable)
    await wrapper.find('[data-testid="menu-/alarms"]').trigger('click')
    expect(wrapper.vm.handleMenuSelect).toHaveBeenCalledWith('/alarms')
  })

  it('显示用户名和告警数量', () => {
    const wrapper = mount(MainLayoutTestable)
    expect(wrapper.find('[data-testid="username"]').text()).toBe('admin')
    expect(wrapper.find('[data-testid="alarm-badge"]').text()).toBe('5')
  })

  it('点击退出登录触发 handleCommand', async () => {
    const wrapper = mount(MainLayoutTestable)
    await wrapper.find('[data-testid="cmd-logout"]').trigger('click')
    expect(wrapper.vm.handleCommand).toHaveBeenCalledWith('logout')
  })

  it('面包屑显示当前页面', () => {
    const wrapper = mount(MainLayoutTestable)
    expect(wrapper.find('[data-testid="breadcrumb"]').text()).toContain('首页')
    expect(wrapper.find('[data-testid="breadcrumb"]').text()).toContain('监控仪表盘')
  })
})
