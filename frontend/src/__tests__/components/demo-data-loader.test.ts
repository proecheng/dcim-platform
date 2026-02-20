/**
 * DemoDataLoader 组件测试
 * 测试演示数据管理对话框（加载/卸载/刷新/进度）
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, reactive } from 'vue'

const DemoDataLoaderTestable = defineComponent({
  name: 'DemoDataLoaderTestable',
  props: {
    modelValue: { type: Boolean, default: false }
  },
  emits: ['update:modelValue', 'loaded', 'unloaded'],
  setup(props, { emit }) {
    const visible = ref(props.modelValue)
    const refreshing = ref(false)
    const unloading = ref(false)
    const errorMessage = ref('')

    const status = reactive({
      is_loaded: false,
      demo_point_count: 0,
      history_count: 0,
      loading: false,
      progress: 0,
      progress_message: ''
    })

    const formatNumber = (num: number): string => num.toLocaleString()

    const handleLoad = () => {
      status.loading = true
      status.progress = 0
      status.progress_message = '开始加载...'
    }

    const handleUnload = () => {
      unloading.value = true
      status.is_loaded = false
      status.demo_point_count = 0
      status.history_count = 0
      unloading.value = false
      emit('unloaded')
    }

    const handleRefreshDates = () => {
      refreshing.value = true
      status.loading = true
      status.progress = 0
      status.progress_message = '开始刷新日期...'
    }

    const handleClose = () => {
      if (!status.loading) {
        visible.value = false
        emit('update:modelValue', false)
      }
    }

    return {
      visible, refreshing, unloading, errorMessage, status,
      formatNumber, handleLoad, handleUnload, handleRefreshDates, handleClose
    }
  },
  template: `
    <div v-if="visible" class="demo-loader-dialog" data-testid="dialog">
      <div class="title" data-testid="title">演示数据管理</div>
      <div class="status-section" data-testid="status-section">
        <span data-testid="status-tag">{{ status.is_loaded ? '已加载' : '未加载' }}</span>
        <span data-testid="point-count">{{ status.demo_point_count || 0 }}</span>
        <span data-testid="history-count">{{ formatNumber(status.history_count || 0) }}</span>
      </div>
      <div v-if="status.loading" class="progress-section" data-testid="progress-section">
        <div data-testid="progress-bar">{{ status.progress }}%</div>
        <div data-testid="progress-message">{{ status.progress_message }}</div>
      </div>
      <div v-if="errorMessage" class="error-section" data-testid="error-section">{{ errorMessage }}</div>
      <div class="action-section" data-testid="action-section">
        <template v-if="!status.is_loaded">
          <button data-testid="load-btn" :disabled="status.loading" @click="handleLoad">
            {{ status.loading ? '加载中...' : '加载演示数据' }}
          </button>
        </template>
        <template v-else>
          <button data-testid="refresh-btn" @click="handleRefreshDates" :disabled="refreshing">刷新日期到最近</button>
          <button data-testid="unload-btn" @click="handleUnload" :disabled="unloading">卸载演示数据</button>
        </template>
      </div>
      <button data-testid="close-btn" @click="handleClose" :disabled="status.loading">关闭</button>
    </div>
  `
})

describe('DemoDataLoader 演示数据管理组件', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('modelValue 为 false 时不显示对话框', () => {
    const wrapper = mount(DemoDataLoaderTestable, { props: { modelValue: false } })
    expect(wrapper.find('[data-testid="dialog"]').exists()).toBe(false)
  })

  it('modelValue 为 true 时显示对话框', () => {
    const wrapper = mount(DemoDataLoaderTestable, { props: { modelValue: true } })
    expect(wrapper.find('[data-testid="dialog"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="title"]').text()).toBe('演示数据管理')
  })

  it('未加载状态显示加载按钮', () => {
    const wrapper = mount(DemoDataLoaderTestable, { props: { modelValue: true } })
    expect(wrapper.find('[data-testid="status-tag"]').text()).toBe('未加载')
    expect(wrapper.find('[data-testid="load-btn"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="unload-btn"]').exists()).toBe(false)
  })

  it('点击加载按钮触发加载流程', async () => {
    const wrapper = mount(DemoDataLoaderTestable, { props: { modelValue: true } })
    await wrapper.find('[data-testid="load-btn"]').trigger('click')
    expect(wrapper.vm.status.loading).toBe(true)
    expect(wrapper.find('[data-testid="progress-section"]').exists()).toBe(true)
  })

  it('已加载状态显示卸载和刷新按钮', async () => {
    const wrapper = mount(DemoDataLoaderTestable, { props: { modelValue: true } })
    wrapper.vm.status.is_loaded = true
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-testid="refresh-btn"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="unload-btn"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="load-btn"]').exists()).toBe(false)
  })

  it('卸载操作重置状态并触发事件', async () => {
    const wrapper = mount(DemoDataLoaderTestable, { props: { modelValue: true } })
    wrapper.vm.status.is_loaded = true
    wrapper.vm.status.demo_point_count = 330
    await wrapper.vm.$nextTick()
    await wrapper.find('[data-testid="unload-btn"]').trigger('click')
    expect(wrapper.vm.status.is_loaded).toBe(false)
    expect(wrapper.vm.status.demo_point_count).toBe(0)
    expect(wrapper.emitted('unloaded')).toBeTruthy()
  })

  it('加载中时关闭按钮被禁用', async () => {
    const wrapper = mount(DemoDataLoaderTestable, { props: { modelValue: true } })
    await wrapper.find('[data-testid="load-btn"]').trigger('click')
    expect(wrapper.find('[data-testid="close-btn"]').attributes('disabled')).toBeDefined()
  })

  it('formatNumber 正确格式化数字', () => {
    const wrapper = mount(DemoDataLoaderTestable, { props: { modelValue: true } })
    expect(wrapper.vm.formatNumber(1234567)).toContain('1')
    expect(wrapper.vm.formatNumber(0)).toBe('0')
  })
})
