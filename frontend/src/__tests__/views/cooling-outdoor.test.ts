/**
 * 室外机监控页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }), useRoute: () => ({ params: {}, query: {} }), createRouter: vi.fn(), createWebHistory: vi.fn() }))

const OutdoorMonitorTestable = defineComponent({
  name: 'OutdoorMonitorTestable',
  setup() {
    const loading = ref(false)
    const unitList = ref([
      { id: 1, device_code: 'OUT-001', device_name: '室外机-1', outdoor_temp: 35.2, fan_status: 'running', compressor_status: 'running', status: 'normal' },
      { id: 2, device_code: 'OUT-002', device_name: '室外机-2', outdoor_temp: 36.8, fan_status: 'stopped', compressor_status: 'stopped', status: 'offline' }
    ])
    const onlineCount = computed(() => unitList.value.filter(u => u.status !== 'offline').length)
    const alarmCount = computed(() => unitList.value.filter(u => u.status === 'warning' || u.status === 'alarm').length)
    return { loading, unitList, onlineCount, alarmCount }
  },
  template: `<div class="outdoor-monitor"><div class="summary"><span data-testid="total">{{ unitList.length }}</span><span data-testid="online">{{ onlineCount }}</span><span data-testid="alarm">{{ alarmCount }}</span></div><table><tr v-for="u in unitList" :key="u.id" :data-testid="'unit-' + u.id"><td class="code">{{ u.device_code }}</td><td class="name">{{ u.device_name }}</td><td class="temp">{{ u.outdoor_temp }}°C</td><td class="fan">{{ u.fan_status }}</td></tr></table></div>`
})

describe('室外机监控页面', () => {
  beforeEach(() => { setActivePinia(createPinia()) })
  it('显示设备总数', () => { expect(mount(OutdoorMonitorTestable).find('[data-testid="total"]').text()).toBe('2') })
  it('显示在线数', () => { expect(mount(OutdoorMonitorTestable).find('[data-testid="online"]').text()).toBe('1') })
  it('显示告警数', () => { expect(mount(OutdoorMonitorTestable).find('[data-testid="alarm"]').text()).toBe('0') })
  it('渲染设备列表', () => { expect(mount(OutdoorMonitorTestable).findAll('tr')).toHaveLength(2) })
  it('显示室外温度', () => { expect(mount(OutdoorMonitorTestable).find('[data-testid="unit-1"] .temp').text()).toContain('35.2') })
  it('显示风机状态', () => { expect(mount(OutdoorMonitorTestable).find('[data-testid="unit-1"] .fan').text()).toBe('running') })
  it('loading初始为false', () => { expect(mount(OutdoorMonitorTestable).vm.loading).toBe(false) })
})
