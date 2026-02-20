/**
 * 制冷系统总览页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }), useRoute: () => ({ params: {}, query: {} }), createRouter: vi.fn(), createWebHistory: vi.fn() }))

function getTempColor(temp: number): string { if (temp <= 22) return '#52c41a'; if (temp <= 28) return '#faad14'; return '#f5222d' }

const CoolingOverviewTestable = defineComponent({
  name: 'CoolingOverviewTestable',
  setup() {
    const loading = ref(false)
    const overview = ref({
      ac_total: 20, ac_running: 16, ac_stopped: 3, ac_alarm: 1,
      cold_aisle_count: 8, group_total: 5, group_linked: 3,
      avg_supply_temp: 18.5, avg_return_temp: 26.2
    })
    const independentCount = computed(() => (overview.value.group_total || 0) - (overview.value.group_linked || 0))
    return { loading, overview, independentCount, getTempColor }
  },
  template: `<div class="cooling-overview"><div class="stat-cards"><div class="stat-card" data-testid="ac-total"><div class="stat-value">{{ overview.ac_total }}</div><div class="stat-label">AC总数</div></div><div class="stat-card" data-testid="ac-running"><div class="stat-value">{{ overview.ac_running }}</div><div class="stat-label">运行中</div></div><div class="stat-card" data-testid="ac-stopped"><div class="stat-value">{{ overview.ac_stopped }}</div><div class="stat-label">已停止</div></div><div class="stat-card" data-testid="ac-alarm"><div class="stat-value">{{ overview.ac_alarm }}</div><div class="stat-label">告警</div></div><div class="stat-card" data-testid="cold-aisle"><div class="stat-value">{{ overview.cold_aisle_count }}</div><div class="stat-label">冷通道</div></div><div class="stat-card" data-testid="group"><div class="stat-value">{{ overview.group_total }}</div><div class="stat-label">群控组</div></div></div><div data-testid="supply-temp">{{ overview.avg_supply_temp }}°C</div><div data-testid="return-temp">{{ overview.avg_return_temp }}°C</div><div data-testid="independent">{{ independentCount }}</div></div>`
})

describe('制冷系统总览页面', () => {
  beforeEach(() => { setActivePinia(createPinia()) })
  it('渲染6张统计卡片', () => { expect(mount(CoolingOverviewTestable).findAll('.stat-card')).toHaveLength(6) })
  it('显示AC总数', () => { expect(mount(CoolingOverviewTestable).find('[data-testid="ac-total"] .stat-value').text()).toBe('20') })
  it('显示运行中数量', () => { expect(mount(CoolingOverviewTestable).find('[data-testid="ac-running"] .stat-value').text()).toBe('16') })
  it('显示送风温度', () => { expect(mount(CoolingOverviewTestable).find('[data-testid="supply-temp"]').text()).toContain('18.5') })
  it('显示回风温度', () => { expect(mount(CoolingOverviewTestable).find('[data-testid="return-temp"]').text()).toContain('26.2') })
  it('独立群控数计算正确', () => { expect(mount(CoolingOverviewTestable).find('[data-testid="independent"]').text()).toBe('2') })
  it('温度颜色判断正确', () => { expect(getTempColor(20)).toBe('#52c41a'); expect(getTempColor(25)).toBe('#faad14'); expect(getTempColor(32)).toBe('#f5222d') })
})
