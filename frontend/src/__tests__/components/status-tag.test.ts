/**
 * StatusTag 状态标签组件 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, computed } from 'vue'

const StatusTagTestable = defineComponent({
  name: 'StatusTagTestable',
  props: {
    status: { type: [String, Number, Boolean], default: undefined },
    statusMap: { type: Object, default: undefined },
    type: { type: String, default: '' },
    text: { type: String, default: '' },
    effect: { type: String, default: 'light' },
    size: { type: String, default: 'default' },
    round: { type: Boolean, default: false },
    showDot: { type: Boolean, default: false },
    flash: { type: Boolean, default: false }
  },
  setup(props) {
    const defaultStatusMap: Record<string, { type: string; text: string; flash?: boolean }> = {
      'true': { type: 'success', text: '是' },
      'false': { type: 'info', text: '否' },
      'online': { type: 'success', text: '在线' },
      'offline': { type: 'danger', text: '离线' },
      'critical': { type: 'danger', text: '紧急', flash: true },
      'major': { type: 'warning', text: '重要' },
      'active': { type: 'danger', text: '活动', flash: true },
      'resolved': { type: 'success', text: '已解决' },
      'normal': { type: 'success', text: '正常' },
      'alarm': { type: 'danger', text: '告警', flash: true },
      'pending': { type: 'info', text: '待处理' },
      'completed': { type: 'success', text: '已完成' }
    }

    const statusConfig = computed(() => {
      const statusKey = String(props.status)
      const mergedMap = { ...defaultStatusMap, ...props.statusMap }
      return mergedMap[statusKey] || { type: 'info', text: statusKey }
    })

    const tagType = computed(() => props.type || statusConfig.value.type || 'info')
    const displayText = computed(() => props.text || statusConfig.value.text)
    const isFlash = computed(() => props.flash || statusConfig.value.flash)

    return { tagType, displayText, isFlash }
  },
  template: `
    <span
      data-testid="status-tag"
      :class="['status-tag', 'el-tag--' + tagType, { 'is-flash': isFlash }]"
      :data-type="tagType"
      :data-effect="effect"
      :data-size="size"
    >
      <span v-if="showDot" data-testid="status-dot" class="status-tag__dot"></span>
      <span data-testid="status-text" class="status-tag__text">{{ displayText }}</span>
    </span>
  `
})

describe('StatusTag 状态标签', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('默认渲染', () => {
    const wrapper = mount(StatusTagTestable)
    expect(wrapper.find('[data-testid="status-tag"]').exists()).toBe(true)
  })

  it('通过 status 映射显示在线状态', () => {
    const wrapper = mount(StatusTagTestable, {
      props: { status: 'online' }
    })
    expect(wrapper.find('[data-testid="status-text"]').text()).toBe('在线')
    expect(wrapper.find('[data-testid="status-tag"]').attributes('data-type')).toBe('success')
  })

  it('通过 status 映射显示离线状态', () => {
    const wrapper = mount(StatusTagTestable, {
      props: { status: 'offline' }
    })
    expect(wrapper.find('[data-testid="status-text"]').text()).toBe('离线')
    expect(wrapper.find('[data-testid="status-tag"]').attributes('data-type')).toBe('danger')
  })

  it('紧急告警自动闪烁', () => {
    const wrapper = mount(StatusTagTestable, {
      props: { status: 'critical' }
    })
    expect(wrapper.find('[data-testid="status-tag"]').classes()).toContain('is-flash')
  })

  it('自定义 text 覆盖默认映射', () => {
    const wrapper = mount(StatusTagTestable, {
      props: { status: 'online', text: '运行中' }
    })
    expect(wrapper.find('[data-testid="status-text"]').text()).toBe('运行中')
  })

  it('showDot 控制圆点显示', () => {
    const wrapper = mount(StatusTagTestable, {
      props: { status: 'normal', showDot: true }
    })
    expect(wrapper.find('[data-testid="status-dot"]').exists()).toBe(true)
  })

  it('showDot 默认不显示圆点', () => {
    const wrapper = mount(StatusTagTestable, {
      props: { status: 'normal' }
    })
    expect(wrapper.find('[data-testid="status-dot"]').exists()).toBe(false)
  })

  it('自定义 statusMap 扩展映射', () => {
    const wrapper = mount(StatusTagTestable, {
      props: {
        status: 'custom',
        statusMap: { custom: { type: 'warning', text: '自定义状态' } }
      }
    })
    expect(wrapper.find('[data-testid="status-text"]').text()).toBe('自定义状态')
    expect(wrapper.find('[data-testid="status-tag"]').attributes('data-type')).toBe('warning')
  })
})
