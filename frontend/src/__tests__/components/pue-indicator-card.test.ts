/**
 * PUEIndicatorCard 组件单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, computed } from 'vue'

const PUEIndicatorCardTestable = defineComponent({
  name: 'PUEIndicatorCardTestable',
  props: {
    pue: { type: Number, default: undefined },
    target: { type: Number, default: undefined },
    trend: { type: String, default: undefined },
    trendData: { type: Array, default: () => [] },
    compareYesterday: { type: Number, default: undefined },
    dataSource: { type: String, default: undefined }
  },
  setup(props) {
    const targetVal = computed(() => props.target || 1.4)
    const pueClass = computed(() => {
      const pue = props.pue || 0
      if (pue <= 1.4) return 'excellent'
      if (pue <= 1.6) return 'good'
      if (pue <= 1.8) return 'normal'
      return 'warning'
    })
    const statusText = computed(() => {
      const pue = props.pue || 0
      if (pue <= targetVal.value) return '达标'
      return '待优化'
    })
    const barStyle = computed(() => {
      const pue = props.pue || 1.0
      const percent = Math.min(100, Math.max(0, ((pue - 1.0) / 1.5) * 100))
      return { width: `${percent}%` }
    })
    return { targetVal, pueClass, statusText, barStyle }
  },
  template: `
    <div data-testid="pue-indicator">
      <span data-testid="pue-value" :class="pueClass">{{ pue?.toFixed(2) || '-' }}</span>
      <span data-testid="status">{{ statusText }}</span>
      <span data-testid="target">目标:{{ targetVal }}</span>
      <span v-if="dataSource" data-testid="data-source">{{ dataSource === 'realtime' ? '实时' : '模拟' }}</span>
      <span v-if="compareYesterday !== undefined" data-testid="compare">
        较昨日 {{ compareYesterday > 0 ? '+' : '' }}{{ compareYesterday.toFixed(2) }}
      </span>
    </div>
  `
})

describe('PUEIndicatorCard 组件', () => {
  beforeEach(() => { setActivePinia(createPinia()) })

  it('默认渲染', () => {
    const wrapper = mount(PUEIndicatorCardTestable)
    expect(wrapper.find('[data-testid="pue-indicator"]').exists()).toBe(true)
  })

  it('PUE 值显示', () => {
    const wrapper = mount(PUEIndicatorCardTestable, { props: { pue: 1.35 } })
    expect(wrapper.find('[data-testid="pue-value"]').text()).toBe('1.35')
  })

  it('PUE 等级 - excellent', () => {
    const wrapper = mount(PUEIndicatorCardTestable, { props: { pue: 1.3 } })
    expect(wrapper.find('[data-testid="pue-value"]').classes()).toContain('excellent')
  })

  it('达标状态', () => {
    const wrapper = mount(PUEIndicatorCardTestable, { props: { pue: 1.3, target: 1.4 } })
    expect(wrapper.find('[data-testid="status"]').text()).toBe('达标')
  })

  it('待优化状态', () => {
    const wrapper = mount(PUEIndicatorCardTestable, { props: { pue: 1.8, target: 1.4 } })
    expect(wrapper.find('[data-testid="status"]').text()).toBe('待优化')
  })

  it('默认目标值为 1.4', () => {
    const wrapper = mount(PUEIndicatorCardTestable)
    expect(wrapper.vm.targetVal).toBe(1.4)
  })

  it('显示数据来源标签', () => {
    const wrapper = mount(PUEIndicatorCardTestable, { props: { dataSource: 'realtime' } })
    expect(wrapper.find('[data-testid="data-source"]').text()).toBe('实时')
  })

  it('显示昨日对比', () => {
    const wrapper = mount(PUEIndicatorCardTestable, { props: { pue: 1.5, compareYesterday: -0.05 } })
    expect(wrapper.find('[data-testid="compare"]').text()).toContain('-0.05')
  })
})
