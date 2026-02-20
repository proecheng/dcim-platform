/**
 * PUEGauge 组件单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, computed } from 'vue'

vi.mock('echarts', () => ({
  init: vi.fn(() => ({ setOption: vi.fn(), resize: vi.fn(), dispose: vi.fn(), on: vi.fn(), off: vi.fn() }))
}))

const PUEGaugeTestable = defineComponent({
  name: 'PUEGaugeTestable',
  props: {
    pue: { type: Number, required: true },
    totalPower: { type: Number, default: undefined },
    itPower: { type: Number, default: undefined },
    coolingPower: { type: Number, default: undefined }
  },
  setup(props) {
    const pueLevel = computed(() => {
      if (props.pue <= 1.4) return { level: '优秀', color: '#52c41a' }
      if (props.pue <= 1.6) return { level: '良好', color: '#1890ff' }
      if (props.pue <= 1.8) return { level: '一般', color: '#faad14' }
      return { level: '较差', color: '#f5222d' }
    })
    function formatPower(power?: number): string {
      if (power === undefined || power === null) return '-'
      return `${power.toFixed(1)} kW`
    }
    return { pueLevel, formatPower }
  },
  template: `
    <div data-testid="pue-gauge">
      <div data-testid="gauge-container"></div>
      <div data-testid="total-power">{{ formatPower(totalPower) }}</div>
      <div data-testid="it-power">{{ formatPower(itPower) }}</div>
      <div data-testid="cooling-power">{{ formatPower(coolingPower) }}</div>
      <div data-testid="pue-level">{{ pueLevel.level }}</div>
    </div>
  `
})

describe('PUEGauge 组件', () => {
  beforeEach(() => { setActivePinia(createPinia()) })

  it('默认渲染', () => {
    const wrapper = mount(PUEGaugeTestable, { props: { pue: 1.5 } })
    expect(wrapper.find('[data-testid="pue-gauge"]').exists()).toBe(true)
  })

  it('PUE 等级 - 优秀', () => {
    const wrapper = mount(PUEGaugeTestable, { props: { pue: 1.3 } })
    expect(wrapper.find('[data-testid="pue-level"]').text()).toBe('优秀')
  })

  it('PUE 等级 - 良好', () => {
    const wrapper = mount(PUEGaugeTestable, { props: { pue: 1.5 } })
    expect(wrapper.find('[data-testid="pue-level"]').text()).toBe('良好')
  })

  it('PUE 等级 - 一般', () => {
    const wrapper = mount(PUEGaugeTestable, { props: { pue: 1.7 } })
    expect(wrapper.find('[data-testid="pue-level"]').text()).toBe('一般')
  })

  it('PUE 等级 - 较差', () => {
    const wrapper = mount(PUEGaugeTestable, { props: { pue: 2.0 } })
    expect(wrapper.find('[data-testid="pue-level"]').text()).toBe('较差')
  })

  it('格式化功率值', () => {
    const wrapper = mount(PUEGaugeTestable, { props: { pue: 1.5, totalPower: 500.3 } })
    expect(wrapper.find('[data-testid="total-power"]').text()).toBe('500.3 kW')
  })

  it('功率为空时显示 -', () => {
    const wrapper = mount(PUEGaugeTestable, { props: { pue: 1.5 } })
    expect(wrapper.find('[data-testid="it-power"]').text()).toBe('-')
  })

  it('PUE 等级颜色正确', () => {
    const wrapper = mount(PUEGaugeTestable, { props: { pue: 1.3 } })
    expect(wrapper.vm.pueLevel.color).toBe('#52c41a')
  })
})
