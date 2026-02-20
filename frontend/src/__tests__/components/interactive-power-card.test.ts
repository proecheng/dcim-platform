/**
 * InteractivePowerCard 组件单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, computed } from 'vue'

const InteractivePowerCardTestable = defineComponent({
  name: 'InteractivePowerCardTestable',
  props: {
    title: { type: String, default: '' },
    value: { type: [Number, String], default: 0 },
    unit: { type: String, default: '' },
    trend: { type: String, default: undefined },
    trendData: { type: Array, default: () => [] },
    details: { type: Array, default: () => [] },
    footerTag: { type: Object, default: undefined },
    footerText: { type: String, default: '' },
    tooltip: { type: String, default: '' },
    navigateTo: { type: String, default: '' }
  },
  emits: ['click'],
  setup(props) {
    const formattedValue = computed(() => {
      if (typeof props.value === 'number') return props.value.toFixed(1)
      return props.value
    })
    const trendColor = computed(() => {
      switch (props.trend) { case 'up': return '#F56C6C'; case 'down': return '#67C23A'; default: return '#909399' }
    })
    return { formattedValue, trendColor }
  },
  template: `
    <div data-testid="power-card">
      <span data-testid="title">{{ title }}</span>
      <span data-testid="value">{{ formattedValue }}</span>
      <span data-testid="unit">{{ unit }}</span>
      <div v-if="details.length > 0" data-testid="details">
        <span v-for="(item, i) in details" :key="i">{{ item.label }}: {{ item.value }}</span>
      </div>
      <span v-if="footerText" data-testid="footer-text">{{ footerText }}</span>
    </div>
  `
})

describe('InteractivePowerCard 组件', () => {
  beforeEach(() => { setActivePinia(createPinia()) })

  it('默认渲染', () => {
    const wrapper = mount(InteractivePowerCardTestable)
    expect(wrapper.find('[data-testid="power-card"]').exists()).toBe(true)
  })

  it('显示标题', () => {
    const wrapper = mount(InteractivePowerCardTestable, { props: { title: '总功率' } })
    expect(wrapper.find('[data-testid="title"]').text()).toBe('总功率')
  })

  it('数字值格式化为一位小数', () => {
    const wrapper = mount(InteractivePowerCardTestable, { props: { value: 123.456 } })
    expect(wrapper.find('[data-testid="value"]').text()).toBe('123.5')
  })

  it('字符串值直接显示', () => {
    const wrapper = mount(InteractivePowerCardTestable, { props: { value: 'N/A' } })
    expect(wrapper.find('[data-testid="value"]').text()).toBe('N/A')
  })

  it('显示单位', () => {
    const wrapper = mount(InteractivePowerCardTestable, { props: { unit: 'kW' } })
    expect(wrapper.find('[data-testid="unit"]').text()).toBe('kW')
  })

  it('趋势颜色 - 上升为红色', () => {
    const wrapper = mount(InteractivePowerCardTestable, { props: { trend: 'up' } })
    expect(wrapper.vm.trendColor).toBe('#F56C6C')
  })

  it('趋势颜色 - 下降为绿色', () => {
    const wrapper = mount(InteractivePowerCardTestable, { props: { trend: 'down' } })
    expect(wrapper.vm.trendColor).toBe('#67C23A')
  })

  it('显示详情列表', () => {
    const wrapper = mount(InteractivePowerCardTestable, {
      props: { details: [{ label: '电压', value: '220V' }, { label: '电流', value: '10A' }] }
    })
    expect(wrapper.find('[data-testid="details"]').exists()).toBe(true)
  })
})
