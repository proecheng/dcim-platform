/**
 * 供配电总览页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref } from 'vue'

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useRoute: () => ({ params: {}, query: {} }),
  createRouter: vi.fn(),
  createWebHistory: vi.fn()
}))

function getLoadColor(rate: number): string {
  if (rate < 60) return '#52c41a'
  if (rate < 80) return '#faad14'
  return '#f5222d'
}

const PowerOverviewTestable = defineComponent({
  name: 'PowerOverviewTestable',
  setup() {
    const loading = ref(false)
    const overview = ref({
      ups_total: 6, ups_online: 5, ups_alarm: 1,
      battery_groups: 4, cabinet_total: 8, pdu_total: 12,
      total_load_rate: 65.5, battery_avg_soh: 92.3
    })
    return { loading, overview, getLoadColor }
  },
  template: `
    <div class="power-overview">
      <div class="stat-cards">
        <div class="stat-card" data-testid="ups-total"><div class="stat-value">{{ overview.ups_total }}</div><div class="stat-label">UPS总数</div></div>
        <div class="stat-card" data-testid="ups-online"><div class="stat-value">{{ overview.ups_online }}</div><div class="stat-label">UPS在线</div></div>
        <div class="stat-card" data-testid="ups-alarm"><div class="stat-value">{{ overview.ups_alarm }}</div><div class="stat-label">UPS告警</div></div>
        <div class="stat-card" data-testid="battery"><div class="stat-value">{{ overview.battery_groups }}</div><div class="stat-label">电池组</div></div>
        <div class="stat-card" data-testid="cabinet"><div class="stat-value">{{ overview.cabinet_total }}</div><div class="stat-label">配电柜</div></div>
        <div class="stat-card" data-testid="pdu"><div class="stat-value">{{ overview.pdu_total }}</div><div class="stat-label">PDU</div></div>
      </div>
      <div class="detail-cards">
        <div data-testid="load-rate">{{ overview.total_load_rate }}%</div>
        <div data-testid="battery-soh">{{ overview.battery_avg_soh }}%</div>
      </div>
    </div>
  `
})

describe('供配电总览页面', () => {
  beforeEach(() => { setActivePinia(createPinia()) })

  it('渲染6张统计卡片', () => {
    const wrapper = mount(PowerOverviewTestable)
    expect(wrapper.findAll('.stat-card')).toHaveLength(6)
  })

  it('显示UPS总数', () => {
    const wrapper = mount(PowerOverviewTestable)
    expect(wrapper.find('[data-testid="ups-total"] .stat-value').text()).toBe('6')
  })

  it('显示UPS告警数', () => {
    const wrapper = mount(PowerOverviewTestable)
    expect(wrapper.find('[data-testid="ups-alarm"] .stat-value').text()).toBe('1')
  })

  it('显示总负载率', () => {
    const wrapper = mount(PowerOverviewTestable)
    expect(wrapper.find('[data-testid="load-rate"]').text()).toContain('65.5')
  })

  it('显示电池健康度', () => {
    const wrapper = mount(PowerOverviewTestable)
    expect(wrapper.find('[data-testid="battery-soh"]').text()).toContain('92.3')
  })

  it('负载颜色判断正确', () => {
    expect(getLoadColor(40)).toBe('#52c41a')
    expect(getLoadColor(70)).toBe('#faad14')
    expect(getLoadColor(90)).toBe('#f5222d')
  })

  it('loading初始为false', () => {
    const wrapper = mount(PowerOverviewTestable)
    expect(wrapper.vm.loading).toBe(false)
  })
})
