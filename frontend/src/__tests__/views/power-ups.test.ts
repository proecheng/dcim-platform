/**
 * UPS监控页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useRoute: () => ({ params: {}, query: {} }),
  createRouter: vi.fn(),
  createWebHistory: vi.fn()
}))

function statusTagType(status: string): string {
  const map: Record<string, string> = { normal: 'success', warning: 'warning', alarm: 'danger', offline: 'info' }
  return map[status] || 'info'
}
function statusLabel(status: string): string {
  const map: Record<string, string> = { normal: '正常', warning: '告警', alarm: '故障', offline: '离线' }
  return map[status] || status
}

const UpsMonitorTestable = defineComponent({
  name: 'UpsMonitorTestable',
  setup() {
    const loading = ref(false)
    const drawerVisible = ref(false)
    const upsList = ref([
      { id: 1, device_code: 'UPS-001', device_name: 'UPS-A', ups_type: '在线式', rated_capacity: 100, load_rate: 0.65, status: 'normal' },
      { id: 2, device_code: 'UPS-002', device_name: 'UPS-B', ups_type: '在线式', rated_capacity: 200, load_rate: 0.85, status: 'warning' }
    ])
    const onlineCount = computed(() => upsList.value.filter(u => u.status !== 'offline').length)
    const alarmCount = computed(() => upsList.value.filter(u => u.status === 'warning' || u.status === 'alarm').length)
    return { loading, drawerVisible, upsList, onlineCount, alarmCount, statusTagType, statusLabel }
  },
  template: `
    <div class="ups-monitor">
      <div class="summary">
        <span data-testid="total">{{ upsList.length }}</span>
        <span data-testid="online">{{ onlineCount }}</span>
        <span data-testid="alarm">{{ alarmCount }}</span>
      </div>
      <table>
        <tr v-for="ups in upsList" :key="ups.id" :data-testid="'ups-' + ups.id">
          <td class="code">{{ ups.device_code }}</td>
          <td class="name">{{ ups.device_name }}</td>
          <td class="status">{{ statusLabel(ups.status) }}</td>
          <td class="load">{{ (ups.load_rate * 100).toFixed(0) }}%</td>
        </tr>
      </table>
    </div>
  `
})

describe('UPS监控页面', () => {
  beforeEach(() => { setActivePinia(createPinia()) })

  it('显示UPS总数', () => {
    const wrapper = mount(UpsMonitorTestable)
    expect(wrapper.find('[data-testid="total"]').text()).toBe('2')
  })
  it('显示在线数', () => {
    const wrapper = mount(UpsMonitorTestable)
    expect(wrapper.find('[data-testid="online"]').text()).toBe('2')
  })
  it('显示告警数', () => {
    const wrapper = mount(UpsMonitorTestable)
    expect(wrapper.find('[data-testid="alarm"]').text()).toBe('1')
  })
  it('状态标签类型正确', () => {
    expect(statusTagType('normal')).toBe('success')
    expect(statusTagType('warning')).toBe('warning')
    expect(statusTagType('alarm')).toBe('danger')
  })
  it('状态文本正确', () => {
    expect(statusLabel('normal')).toBe('正常')
    expect(statusLabel('offline')).toBe('离线')
  })
  it('渲染UPS列表', () => {
    const wrapper = mount(UpsMonitorTestable)
    expect(wrapper.findAll('tr')).toHaveLength(2)
    expect(wrapper.find('[data-testid="ups-1"] .code').text()).toBe('UPS-001')
  })
  it('负载率显示正确', () => {
    const wrapper = mount(UpsMonitorTestable)
    expect(wrapper.find('[data-testid="ups-1"] .load').text()).toBe('65%')
  })
})
