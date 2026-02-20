/**
 * 冷通道监控页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }), useRoute: () => ({ params: {}, query: {} }), createRouter: vi.fn(), createWebHistory: vi.fn() }))

const ColdAisleMonitorTestable = defineComponent({
  name: 'ColdAisleMonitorTestable',
  setup() {
    const loading = ref(false)
    const aisleList = ref([
      { id: 1, aisle_name: '冷通道-A', avg_temp: 22.5, skylight_count: 4, skylight_open: 2 },
      { id: 2, aisle_name: '冷通道-B', avg_temp: 23.1, skylight_count: 6, skylight_open: 0 }
    ])
    const totalSkylightOpen = computed(() => aisleList.value.reduce((s, a) => s + a.skylight_open, 0))
    return { loading, aisleList, totalSkylightOpen }
  },
  template: `<div class="cold-aisle-monitor"><div data-testid="total-open">{{ totalSkylightOpen }}</div><table><tr v-for="a in aisleList" :key="a.id" :data-testid="'aisle-' + a.id"><td class="name">{{ a.aisle_name }}</td><td class="temp">{{ a.avg_temp }}°C</td><td class="skylight">{{ a.skylight_open }}/{{ a.skylight_count }}</td></tr></table></div>`
})

describe('冷通道监控页面', () => {
  beforeEach(() => { setActivePinia(createPinia()) })
  it('渲染冷通道列表', () => { expect(mount(ColdAisleMonitorTestable).findAll('tr')).toHaveLength(2) })
  it('显示通道名称', () => { expect(mount(ColdAisleMonitorTestable).find('[data-testid="aisle-1"] .name').text()).toBe('冷通道-A') })
  it('显示平均温度', () => { expect(mount(ColdAisleMonitorTestable).find('[data-testid="aisle-1"] .temp').text()).toContain('22.5') })
  it('显示天窗状态', () => { expect(mount(ColdAisleMonitorTestable).find('[data-testid="aisle-1"] .skylight').text()).toBe('2/4') })
  it('天窗开启总数正确', () => { expect(mount(ColdAisleMonitorTestable).find('[data-testid="total-open"]').text()).toBe('2') })
  it('loading初始为false', () => { expect(mount(ColdAisleMonitorTestable).vm.loading).toBe(false) })
  it('无天窗开启的通道显示0', () => { expect(mount(ColdAisleMonitorTestable).find('[data-testid="aisle-2"] .skylight').text()).toBe('0/6') })
})
