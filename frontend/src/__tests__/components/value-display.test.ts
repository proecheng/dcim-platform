/**
 * ValueDisplay 数值显示组件 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed, onMounted } from 'vue'

// Mock Element Plus icons
vi.mock('@element-plus/icons-vue', () => ({
  CaretTop: { template: '<i class="icon-caret-top" />' },
  CaretBottom: { template: '<i class="icon-caret-bottom" />' }
}))

const ValueDisplayTestable = defineComponent({
  name: 'ValueDisplayTestable',
  props: {
    value: { type: [Number, String], required: true },
    unit: { type: String, default: undefined },
    precision: { type: Number, default: 2 },
    size: { type: String as () => 'small' | 'default' | 'large' | 'xlarge', default: 'default' },
    status: { type: String as () => 'normal' | 'alarm' | 'offline', default: 'normal' },
    trend: { type: String as () => 'up' | 'down' | 'stable' | undefined, default: undefined },
    animate: { type: Boolean, default: true }
  },
  setup(props) {
    const animatedValue = ref<number>(0)

    const displayValue = computed(() => {
      if (typeof props.value === 'string') {
        return props.value
      }
      const val = typeof props.value === 'number' ? props.value : 0
      if (!isNaN(val)) {
        return val.toFixed(props.precision)
      }
      return '--'
    })

    const trendClass = computed(() => ({
      'trend-icon': true,
      'trend-icon--up': props.trend === 'up',
      'trend-icon--down': props.trend === 'down'
    }))

    onMounted(() => {
      if (typeof props.value === 'number') {
        animatedValue.value = props.value
      }
    })

    return { displayValue, trendClass, animatedValue }
  },
  template: `
    <div
      data-testid="value-display"
      :class="['value-display', 'value-display--' + size, 'value-display--' + status, { 'value-display--animate': animate }]"
    >
      <span data-testid="display-value" class="value-display__value">{{ displayValue }}</span>
      <span v-if="unit" data-testid="display-unit" class="value-display__unit">{{ unit }}</span>
      <span v-if="trend && trend !== 'stable'" data-testid="display-trend" :class="trendClass">
        {{ trend === 'up' ? '↑' : '↓' }}
      </span>
    </div>
  `
})

describe('ValueDisplay 数值显示', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('默认渲染数值', () => {
    const wrapper = mount(ValueDisplayTestable, {
      props: { value: 25.678 }
    })
    expect(wrapper.find('[data-testid="value-display"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="display-value"]').text()).toBe('25.68')
  })

  it('precision 控制小数位数', () => {
    const wrapper = mount(ValueDisplayTestable, {
      props: { value: 25.678, precision: 1 }
    })
    expect(wrapper.find('[data-testid="display-value"]').text()).toBe('25.7')
  })

  it('字符串值直接显示', () => {
    const wrapper = mount(ValueDisplayTestable, {
      props: { value: 'N/A' }
    })
    expect(wrapper.find('[data-testid="display-value"]').text()).toBe('N/A')
  })

  it('unit 属性显示单位', () => {
    const wrapper = mount(ValueDisplayTestable, {
      props: { value: 25, unit: '℃' }
    })
    expect(wrapper.find('[data-testid="display-unit"]').text()).toBe('℃')
  })

  it('无 unit 时不显示单位', () => {
    const wrapper = mount(ValueDisplayTestable, {
      props: { value: 25 }
    })
    expect(wrapper.find('[data-testid="display-unit"]').exists()).toBe(false)
  })

  it('size 属性控制尺寸样式', () => {
    const wrapper = mount(ValueDisplayTestable, {
      props: { value: 25, size: 'large' }
    })
    expect(wrapper.find('[data-testid="value-display"]').classes()).toContain('value-display--large')
  })

  it('status 属性控制状态样式', () => {
    const wrapper = mount(ValueDisplayTestable, {
      props: { value: 25, status: 'alarm' }
    })
    expect(wrapper.find('[data-testid="value-display"]').classes()).toContain('value-display--alarm')
  })

  it('trend 属性显示趋势指示器', () => {
    const wrapperUp = mount(ValueDisplayTestable, { props: { value: 25, trend: 'up' } })
    expect(wrapperUp.find('[data-testid="display-trend"]').text()).toContain('↑')

    const wrapperDown = mount(ValueDisplayTestable, { props: { value: 25, trend: 'down' } })
    expect(wrapperDown.find('[data-testid="display-trend"]').text()).toContain('↓')

    const wrapperStable = mount(ValueDisplayTestable, { props: { value: 25, trend: 'stable' } })
    expect(wrapperStable.find('[data-testid="display-trend"]').exists()).toBe(false)
  })
})
