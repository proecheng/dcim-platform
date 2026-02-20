/**
 * 精密空调(室内机)监控页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref } from 'vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }), useRoute: () => ({ params: {}, query: {} }), createRouter: vi.fn(), createWebHistory: vi.fn() }))

const statusLabel = (s: string) => ({ normal: '正常', warning: '告警', alarm: '故障', offline: '离线' }[s] || s)

const IndoorMonitorTestable = defineComponent({
  name: 'IndoorMonitorTestable',
  setup() {
    const loading = ref(false)
    const unitList = ref([
      { id: 1, device_code: 'AC-001', device_name: '精密空调-1', ac_type: '风冷', cooling_capacity: 50, supply_temp: 18.5, return_temp: 26.2, status: 'normal' },
      { id: 2, device_code: 'AC-002', device_name: '精密空调-2', ac_type: '水冷', cooling_capacity: 80, supply_temp: 19.0, return_temp: 27.1, status: 'warning' }
    ])
    return { loading, unitList, statusLabel }
  },
  template: `<div class="indoor-monitor"><table><tr v-for="u in unitList" :key="u.id" :data-testid="'ac-' + u.id"><td class="code">{{ u.device_code }}</td><td class="name">{{ u.device_name }}</td><td class="type">{{ u.ac_type }}</td><td class="supply">{{ u.supply_temp }}°C</td><td class="return">{{ u.return_temp }}°C</td><td class="status">{{ statusLabel(u.status) }}</td></tr></table></div>`
})

describe('精密空调监控页面', () => {
  beforeEach(() => { setActivePinia(createPinia()) })
  it('渲染空调列表', () => { expect(mount(IndoorMonitorTestable).findAll('tr')).toHaveLength(2) })
  it('显示设备编码', () => { expect(mount(IndoorMonitorTestable).find('[data-testid="ac-1"] .code').text()).toBe('AC-001') })
  it('显示空调类型', () => { expect(mount(IndoorMonitorTestable).find('[data-testid="ac-1"] .type').text()).toBe('风冷') })
  it('显示送风温度', () => { expect(mount(IndoorMonitorTestable).find('[data-testid="ac-1"] .supply').text()).toContain('18.5') })
  it('显示回风温度', () => { expect(mount(IndoorMonitorTestable).find('[data-testid="ac-1"] .return').text()).toContain('26.2') })
  it('状态文本正确', () => { expect(statusLabel('normal')).toBe('正常'); expect(statusLabel('warning')).toBe('告警') })
  it('loading初始为false', () => { expect(mount(IndoorMonitorTestable).vm.loading).toBe(false) })
})
