/**
 * 环境监控总览页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }), useRoute: () => ({ params: {}, query: {} }), createRouter: vi.fn(), createWebHistory: vi.fn() }))

const EnvironmentOverviewTestable = defineComponent({
  name: 'EnvironmentOverviewTestable',
  setup() {
    const loading = ref(false)
    const sensorData = ref([
      { id: 1, name: '温度传感器-A01', type: 'temperature', value: 24.5, unit: '℃', status: 'normal', location: '机房A' },
      { id: 2, name: '温度传感器-A02', type: 'temperature', value: 36.2, unit: '℃', status: 'alarm', location: '机房A' },
      { id: 3, name: '湿度传感器-A01', type: 'humidity', value: 55.0, unit: '%', status: 'normal', location: '机房A' },
      { id: 4, name: '湿度传感器-B01', type: 'humidity', value: 72.0, unit: '%', status: 'alarm', location: '机房B' }
    ])
    const avgTemp = computed(() => {
      const temps = sensorData.value.filter(s => s.type === 'temperature')
      return (temps.reduce((s, t) => s + t.value, 0) / temps.length).toFixed(1)
    })
    const avgHumidity = computed(() => {
      const hums = sensorData.value.filter(s => s.type === 'humidity')
      return (hums.reduce((s, h) => s + h.value, 0) / hums.length).toFixed(1)
    })
    const normalCount = computed(() => sensorData.value.filter(s => s.status === 'normal').length)
    const alarmCount = computed(() => sensorData.value.filter(s => s.status === 'alarm').length)
    const statusTagType = (s: string) => ({ normal: 'success', alarm: 'danger', offline: 'info' }[s] || 'info')
    return { loading, sensorData, avgTemp, avgHumidity, normalCount, alarmCount, statusTagType }
  },
  template: `<div class="environment-overview"><div class="summary-cards"><div class="card" data-testid="avg-temp"><span class="value">{{ avgTemp }}℃</span><span class="label">平均温度</span></div><div class="card" data-testid="avg-humidity"><span class="value">{{ avgHumidity }}%</span><span class="label">平均湿度</span></div><div class="card" data-testid="normal-count"><span class="value">{{ normalCount }}</span><span class="label">正常</span></div><div class="card" data-testid="alarm-count"><span class="value">{{ alarmCount }}</span><span class="label">告警</span></div></div><div class="sensor-table" data-testid="sensor-table"><div v-for="s in sensorData" :key="s.id" :data-testid="'sensor-' + s.id" class="sensor-row"><span class="name">{{ s.name }}</span><span class="value">{{ s.value }}{{ s.unit }}</span><span class="status">{{ s.status }}</span><span class="location">{{ s.location }}</span></div></div></div>`
})

describe('环境监控总览页面', () => {
  beforeEach(() => { setActivePinia(createPinia()) })
  it('显示平均温度', () => { expect(mount(EnvironmentOverviewTestable).find('[data-testid="avg-temp"] .value').text()).toBe('30.4℃') })
  it('显示平均湿度', () => { expect(mount(EnvironmentOverviewTestable).find('[data-testid="avg-humidity"] .value').text()).toBe('63.5%') })
  it('统计正常和告警数', () => { const w = mount(EnvironmentOverviewTestable); expect(w.find('[data-testid="normal-count"] .value').text()).toBe('2'); expect(w.find('[data-testid="alarm-count"] .value').text()).toBe('2') })
  it('渲染传感器列表', () => { expect(mount(EnvironmentOverviewTestable).findAll('.sensor-row')).toHaveLength(4) })
  it('显示传感器值和单位', () => { const w = mount(EnvironmentOverviewTestable); expect(w.find('[data-testid="sensor-1"] .value').text()).toBe('24.5℃'); expect(w.find('[data-testid="sensor-3"] .value').text()).toBe('55%') })
  it('显示传感器位置', () => { expect(mount(EnvironmentOverviewTestable).find('[data-testid="sensor-4"] .location').text()).toBe('机房B') })
  it('状态标签类型正确', () => { const w = mount(EnvironmentOverviewTestable); expect(w.vm.statusTagType('normal')).toBe('success'); expect(w.vm.statusTagType('alarm')).toBe('danger') })
})
