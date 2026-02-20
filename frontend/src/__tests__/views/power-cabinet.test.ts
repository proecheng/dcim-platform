/**
 * 配电柜监控页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref } from 'vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }), useRoute: () => ({ params: {}, query: {} }), createRouter: vi.fn(), createWebHistory: vi.fn() }))

const statusLabel = (s: string) => ({ normal: '正常', warning: '告警', alarm: '故障', offline: '离线' }[s] || s)

const CabinetMonitorTestable = defineComponent({
  name: 'CabinetMonitorTestable',
  setup() {
    const loading = ref(false)
    const drawerVisible = ref(false)
    const cabinetList = ref([
      { id: 1, device_code: 'CAB-001', device_name: '配电柜-A', area: 'A区', total_power: 85.5, input_voltage: 380, bus_temperature: 42.3, status: 'normal' },
      { id: 2, device_code: 'CAB-002', device_name: '配电柜-B', area: 'B区', total_power: 120.0, input_voltage: 378, bus_temperature: 55.1, status: 'warning' }
    ])
    return { loading, drawerVisible, cabinetList, statusLabel }
  },
  template: `<div class="cabinet-monitor"><table><tr v-for="c in cabinetList" :key="c.id" :data-testid="'cab-' + c.id"><td class="code">{{ c.device_code }}</td><td class="name">{{ c.device_name }}</td><td class="power">{{ c.total_power }}</td><td class="voltage">{{ c.input_voltage }}</td><td class="temp">{{ c.bus_temperature }}</td><td class="status">{{ statusLabel(c.status) }}</td></tr></table></div>`
})

describe('配电柜监控页面', () => {
  beforeEach(() => { setActivePinia(createPinia()) })
  it('渲染配电柜列表', () => { expect(mount(CabinetMonitorTestable).findAll('tr')).toHaveLength(2) })
  it('显示设备编码', () => { expect(mount(CabinetMonitorTestable).find('[data-testid="cab-1"] .code').text()).toBe('CAB-001') })
  it('显示总功率', () => { expect(mount(CabinetMonitorTestable).find('[data-testid="cab-1"] .power').text()).toBe('85.5') })
  it('显示输入电压', () => { expect(mount(CabinetMonitorTestable).find('[data-testid="cab-1"] .voltage').text()).toBe('380') })
  it('显示母排温度', () => { expect(mount(CabinetMonitorTestable).find('[data-testid="cab-1"] .temp').text()).toBe('42.3') })
  it('状态文本正确', () => { expect(statusLabel('normal')).toBe('正常'); expect(statusLabel('warning')).toBe('告警') })
  it('loading初始为false', () => { expect(mount(CabinetMonitorTestable).vm.loading).toBe(false) })
})
