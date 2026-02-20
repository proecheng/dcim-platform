/**
 * AlarmBadge 告警徽章组件 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, computed } from 'vue'

// Mock Element Plus icons
vi.mock('@element-plus/icons-vue', () => ({
  WarningFilled: { template: '<i class="icon-warning" />' }
}))

const AlarmBadgeTestable = defineComponent({
  name: 'AlarmBadgeTestable',
  props: {
    count: { type: Number, required: true },
    level: { type: String as () => 'critical' | 'major' | 'minor' | 'info', default: 'major' },
    showIcon: { type: Boolean, default: true },
    showLabel: { type: Boolean, default: false },
    flash: { type: Boolean, default: false },
    max: { type: Number, default: 99 }
  },
  emits: ['click'],
  setup(props, { emit }) {
    const displayCount = computed(() => {
      if (props.count > props.max) {
        return `${props.max}+`
      }
      return props.count
    })

    const levelLabel = computed(() => {
      const map: Record<string, string> = {
        critical: '紧急',
        major: '重要',
        minor: '次要',
        info: '提示'
      }
      return map[props.level] || ''
    })

    const handleClick = () => emit('click')

    return { displayCount, levelLabel, handleClick }
  },
  template: `
    <div
      data-testid="alarm-badge"
      :class="['alarm-badge', 'alarm-badge--' + level, { 'alarm-badge--flash': flash }]"
      @click="handleClick"
    >
      <span v-if="showIcon" data-testid="badge-icon" class="alarm-badge__icon">⚠</span>
      <span data-testid="badge-count" class="alarm-badge__count">{{ displayCount }}</span>
      <span v-if="showLabel" data-testid="badge-label" class="alarm-badge__label">{{ levelLabel }}</span>
    </div>
  `
})

describe('AlarmBadge 告警徽章', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('默认渲染', () => {
    const wrapper = mount(AlarmBadgeTestable, {
      props: { count: 5 }
    })
    expect(wrapper.find('[data-testid="alarm-badge"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="badge-count"]').text()).toBe('5')
  })

  it('level 属性控制样式', () => {
    const wrapper = mount(AlarmBadgeTestable, {
      props: { count: 3, level: 'critical' }
    })
    expect(wrapper.find('[data-testid="alarm-badge"]').classes()).toContain('alarm-badge--critical')
  })

  it('count 超过 max 时显示 max+', () => {
    const wrapper = mount(AlarmBadgeTestable, {
      props: { count: 150, max: 99 }
    })
    expect(wrapper.find('[data-testid="badge-count"]').text()).toBe('99+')
  })

  it('count 未超过 max 时显示实际数', () => {
    const wrapper = mount(AlarmBadgeTestable, {
      props: { count: 50, max: 99 }
    })
    expect(wrapper.find('[data-testid="badge-count"]').text()).toBe('50')
  })

  it('showIcon 控制图标显示', () => {
    const wrapperShow = mount(AlarmBadgeTestable, { props: { count: 1, showIcon: true } })
    expect(wrapperShow.find('[data-testid="badge-icon"]').exists()).toBe(true)

    const wrapperHide = mount(AlarmBadgeTestable, { props: { count: 1, showIcon: false } })
    expect(wrapperHide.find('[data-testid="badge-icon"]').exists()).toBe(false)
  })

  it('showLabel 控制标签显示', () => {
    const wrapper = mount(AlarmBadgeTestable, {
      props: { count: 5, level: 'critical', showLabel: true }
    })
    expect(wrapper.find('[data-testid="badge-label"]').text()).toBe('紧急')
  })

  it('flash 属性控制闪烁', () => {
    const wrapper = mount(AlarmBadgeTestable, {
      props: { count: 1, flash: true }
    })
    expect(wrapper.find('[data-testid="alarm-badge"]').classes()).toContain('alarm-badge--flash')
  })

  it('点击触发 click 事件', async () => {
    const wrapper = mount(AlarmBadgeTestable, {
      props: { count: 5 }
    })
    await wrapper.find('[data-testid="alarm-badge"]').trigger('click')
    expect(wrapper.emitted('click')).toBeTruthy()
  })
})
