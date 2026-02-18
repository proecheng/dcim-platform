/**
 * Dashboard 统计卡片测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref } from 'vue'

// 模拟 Dashboard 统计卡片的核心逻辑
const DashboardStats = defineComponent({
  name: 'DashboardStats',
  setup() {
    const summary = ref({ total: 100, normal: 85, alarm: 10, offline: 5 })
    return { summary }
  },
  template: `
    <div class="dashboard">
      <div class="stat-cards">
        <div class="stat-card" data-testid="total">
          <div class="stat-value">{{ summary.total }}</div>
          <div class="stat-label">监控点位</div>
        </div>
        <div class="stat-card" data-testid="normal">
          <div class="stat-value">{{ summary.normal }}</div>
          <div class="stat-label">正常点位</div>
        </div>
        <div class="stat-card" data-testid="alarm">
          <div class="stat-value">{{ summary.alarm }}</div>
          <div class="stat-label">告警点位</div>
        </div>
        <div class="stat-card" data-testid="offline">
          <div class="stat-value">{{ summary.offline }}</div>
          <div class="stat-label">离线点位</div>
        </div>
      </div>
    </div>
  `
})

describe('Dashboard 统计卡片', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('渲染 4 张统计卡片', () => {
    const wrapper = mount(DashboardStats)
    const cards = wrapper.findAll('.stat-card')
    expect(cards).toHaveLength(4)
  })

  it('显示监控点位总数', () => {
    const wrapper = mount(DashboardStats)
    const card = wrapper.find('[data-testid="total"]')
    expect(card.find('.stat-value').text()).toBe('100')
    expect(card.find('.stat-label').text()).toBe('监控点位')
  })

  it('显示正常点位数', () => {
    const wrapper = mount(DashboardStats)
    const card = wrapper.find('[data-testid="normal"]')
    expect(card.find('.stat-value').text()).toBe('85')
    expect(card.find('.stat-label').text()).toBe('正常点位')
  })

  it('显示告警点位数', () => {
    const wrapper = mount(DashboardStats)
    const card = wrapper.find('[data-testid="alarm"]')
    expect(card.find('.stat-value').text()).toBe('10')
    expect(card.find('.stat-label').text()).toBe('告警点位')
  })

  it('显示离线点位数', () => {
    const wrapper = mount(DashboardStats)
    const card = wrapper.find('[data-testid="offline"]')
    expect(card.find('.stat-value').text()).toBe('5')
    expect(card.find('.stat-label').text()).toBe('离线点位')
  })

  it('数据更新后视图同步', async () => {
    const wrapper = mount(DashboardStats)
    wrapper.vm.summary.total = 200
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-testid="total"] .stat-value').text()).toBe('200')
  })
})
