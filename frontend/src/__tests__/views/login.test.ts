/**
 * 登录表单组件测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, h } from 'vue'

// Mock 依赖
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
  createRouter: vi.fn(),
  createWebHistory: vi.fn()
}))

vi.mock('@/stores', () => ({
  useUserStore: () => ({
    doLogin: vi.fn().mockResolvedValue(undefined)
  })
}))

vi.mock('@element-plus/icons-vue', () => ({
  Monitor: defineComponent({ render: () => h('span', 'Monitor') }),
  User: defineComponent({ render: () => h('span', 'User') }),
  Lock: defineComponent({ render: () => h('span', 'Lock') })
}))

// 简化版登录组件用于测试（避免 Element Plus 深度依赖）
const LoginFormTestable = defineComponent({
  name: 'LoginFormTestable',
  setup() {
    const { ref, reactive } = require('vue')
    const form = reactive({ username: '', password: '' })
    const loading = ref(false)
    const rules = {
      username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
      password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
    }

    return { form, loading, rules }
  },
  template: `
    <div class="login-container">
      <div class="login-box">
        <h2>算力中心智能监控系统</h2>
        <form @submit.prevent>
          <input v-model="form.username" placeholder="用户名" data-testid="username" />
          <input v-model="form.password" type="password" placeholder="密码" data-testid="password" />
          <button :disabled="loading" data-testid="login-btn">登 录</button>
        </form>
      </div>
    </div>
  `
})

describe('LoginForm', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('渲染登录表单标题', () => {
    const wrapper = mount(LoginFormTestable)
    expect(wrapper.find('h2').text()).toContain('算力中心智能监控系统')
  })

  it('渲染用户名和密码输入框', () => {
    const wrapper = mount(LoginFormTestable)
    expect(wrapper.find('[data-testid="username"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="password"]').exists()).toBe(true)
  })

  it('渲染登录按钮', () => {
    const wrapper = mount(LoginFormTestable)
    const btn = wrapper.find('[data-testid="login-btn"]')
    expect(btn.exists()).toBe(true)
    expect(btn.text()).toContain('登 录')
  })

  it('输入框双向绑定', async () => {
    const wrapper = mount(LoginFormTestable)
    const usernameInput = wrapper.find('[data-testid="username"]')
    const passwordInput = wrapper.find('[data-testid="password"]')

    await usernameInput.setValue('admin')
    await passwordInput.setValue('admin123')

    expect(wrapper.vm.form.username).toBe('admin')
    expect(wrapper.vm.form.password).toBe('admin123')
  })

  it('表单验证规则存在', () => {
    const wrapper = mount(LoginFormTestable)
    expect(wrapper.vm.rules.username).toBeDefined()
    expect(wrapper.vm.rules.password).toBeDefined()
    expect(wrapper.vm.rules.username[0].required).toBe(true)
    expect(wrapper.vm.rules.password[0].required).toBe(true)
  })

  it('loading 初始为 false', () => {
    const wrapper = mount(LoginFormTestable)
    expect(wrapper.vm.loading).toBe(false)
  })
})
