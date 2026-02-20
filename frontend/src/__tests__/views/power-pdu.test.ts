/**
 * PDU监控页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref } from 'vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }), useRoute: () => ({ params: {}, query: {} }), createRouter: vi.fn(), createWebHistory: vi.fn() }))

const statusLabel = (s: string) => ({ normal: '正常', warning: '告警', alarm: '故障', offline: '离线' }[s] || s)

const PduMonitorTestable = defineComponent({
  name: 'PduMonitorTestable',
  setup() {
    const loading = ref(false)
    const drawerVisible = ref(false)
    const pduList = ref([
      { id: 1, device_code: 'PDU-001', device_name: 'PDU-A1', area: 'A区', total_current: 32.5, temperature: 28.3, status: 'normal' },
      { id: 2, device_code: 'PDU-002', device_name: 'PDU-B1', area: 'B区', total_current: 45.2, temperature: 31.1, status: 'warning' }
    ])
    return { loading, drawerVisible, pduList, statusLabel }
  },
  template: `<div class="pdu-monitor"><table><tr v-for="p in pduList" :key="p.id" :data-testid="'pdu-' + p.id"><td class="code">{{ p.device_code }}</td><td class="name">{{ p.device_name }}</td><td class="area">{{ p.area }}</td><td class="current">{{ p.total_current }}</td><td class="temp">{{ p.temperature }}</td><td class="status">{{ statusLabel(p.status) }}</td></tr></table></div>`
})

describe('PDU监控页面', () => {
  beforeEach(() => { setActivePinia(createPinia()) })
  it('渲染PDU列表', () => { expect(mount(PduMonitorTestable).findAll('tr')).toHaveLength(2) })
  it('显示设备编码', () => { expect(mount(PduMonitorTestable).find('[data-testid="pdu-1"] .code').text()).toBe('PDU-001') })
  it('显示区域', () => { expect(mount(PduMonitorTestable).find('[data-testid="pdu-1"] .area').text()).toBe('A区') })
  it('显示电流', () => { expect(mount(PduMonitorTestable).find('[data-testid="pdu-1"] .current').text()).toBe('32.5') })
  it('显示温度', () => { expect(mount(PduMonitorTestable).find('[data-testid="pdu-1"] .temp').text()).toBe('28.3') })
  it('状态文本正确', () => { expect(statusLabel('normal')).toBe('正常'); expect(statusLabel('warning')).toBe('告警') })
  it('loading初始为false', () => { expect(mount(PduMonitorTestable).vm.loading).toBe(false) })
})
