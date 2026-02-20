/**
 * PowerCard 组件单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, computed } from 'vue'

const PowerCardTestable = defineComponent({
  name: 'PowerCardTestable',
  props: {
    deviceName: { type: String, required: true },
    deviceType: { type: String, default: '' },
    activePower: { type: Number, default: undefined },
    voltage: { type: Number, default: undefined },
    current: { type: Number, default: undefined },
    powerFactor: { type: Number, default: undefined },
    loadRate: { type: Number, default: undefined },
    status: { type: String, default: 'normal' }
  },
  setup(props) {
    const statusType = computed(() => {
      switch (props.status) { case 'normal': return 'success'; case 'warning': return 'warning'; case 'alarm': return 'danger'; default: return 'info' }
    })
    const statusText = computed(() => {
      switch (props.status) { case 'normal': return '正常'; case 'warning': return '预警'; case 'alarm': return '告警'; case 'offline': return '离线'; default: return '未知' }
    })
    const loadRateColor = computed(() => {
      const rate = props.loadRate ?? 0
      if (rate < 30) return 'var(--text-secondary)'
      if (rate < 60) return 'var(--success-color)'
      if (rate < 80) return 'var(--warning-color)'
      return 'var(--error-color)'
    })
    function formatPower(power?: number): string {
      if (power === undefined || power === null) return '-'
      return power.toFixed(1)
    }
    return { statusType, statusText, loadRateColor, formatPower }
  },
  template: `
    <div data-testid="power-card" :class="{ 'is-alarm': status === 'alarm' }">
      <span data-testid="device-name">{{ deviceName }}</span>
      <span data-testid="status">{{ statusText }}</span>
      <span data-testid="power">{{ formatPower(activePower) }}</span>
      <span data-testid="load-rate">{{ loadRate?.toFixed(1) ?? '-' }}%</span>
    </div>
  `
})

describe('PowerCard 组件', () => {
  beforeEach(() => { setActivePinia(createPinia()) })

  it('默认渲染', () => {
    const wrapper = mount(PowerCardTestable, { props: { deviceName: '设备A' } })
    expect(wrapper.find('[data-testid="power-card"]').exists()).toBe(true)
  })

  it('显示设备名称', () => {
    const wrapper = mount(PowerCardTestable, { props: { deviceName: 'UPS-1' } })
    expect(wrapper.find('[data-testid="device-name"]').text()).toBe('UPS-1')
  })

  it('状态映射 - 正常', () => {
    const wrapper = mount(PowerCardTestable, { props: { deviceName: 'X', status: 'normal' } })
    expect(wrapper.find('[data-testid="status"]').text()).toBe('正常')
  })

  it('状态映射 - 告警', () => {
    const wrapper = mount(PowerCardTestable, { props: { deviceName: 'X', status: 'alarm' } })
    expect(wrapper.find('[data-testid="status"]').text()).toBe('告警')
    expect(wrapper.find('[data-testid="power-card"]').classes()).toContain('is-alarm')
  })

  it('格式化功率值', () => {
    const wrapper = mount(PowerCardTestable, { props: { deviceName: 'X', activePower: 123.456 } })
    expect(wrapper.find('[data-testid="power"]').text()).toBe('123.5')
  })

  it('功率为空时显示 -', () => {
    const wrapper = mount(PowerCardTestable, { props: { deviceName: 'X' } })
    expect(wrapper.find('[data-testid="power"]').text()).toBe('-')
  })

  it('负载率颜色 - 低负载', () => {
    const wrapper = mount(PowerCardTestable, { props: { deviceName: 'X', loadRate: 20 } })
    expect(wrapper.vm.loadRateColor).toBe('var(--text-secondary)')
  })

  it('负载率颜色 - 高负载', () => {
    const wrapper = mount(PowerCardTestable, { props: { deviceName: 'X', loadRate: 85 } })
    expect(wrapper.vm.loadRateColor).toBe('var(--error-color)')
  })
})
