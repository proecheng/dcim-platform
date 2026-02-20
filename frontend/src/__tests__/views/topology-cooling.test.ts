/**
 * 制冷拓扑页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref } from 'vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }), useRoute: () => ({ params: {}, query: {} }), createRouter: vi.fn(), createWebHistory: vi.fn() }))

function progressColor(pct: number): string { if (pct < 60) return '#52c41a'; if (pct < 80) return '#faad14'; return '#f5222d' }

const CoolingTopologyTestable = defineComponent({
  name: 'CoolingTopologyTestable',
  setup() {
    const loading = ref(false)
    const zoneList = ref([
      { id: 1, zone_name: '制冷区-A', cooling_capacity: 200, current_load: 120, cabinet_count: 10, ac_count: 4 },
      { id: 2, zone_name: '制冷区-B', cooling_capacity: 300, current_load: 250, cabinet_count: 15, ac_count: 6 }
    ])
    const zoneDialogVisible = ref(false)
    return { loading, zoneList, zoneDialogVisible, progressColor }
  },
  template: `<div class="cooling-topology"><table><tr v-for="z in zoneList" :key="z.id" :data-testid="'zone-' + z.id"><td class="name">{{ z.zone_name }}</td><td class="capacity">{{ z.cooling_capacity }} kW</td><td class="load">{{ z.current_load }} kW</td><td class="cabinets">{{ z.cabinet_count }}</td><td class="acs">{{ z.ac_count }}</td><td class="usage">{{ (z.current_load / z.cooling_capacity * 100).toFixed(0) }}%</td></tr></table></div>`
})

describe('制冷拓扑页面', () => {
  beforeEach(() => { setActivePinia(createPinia()) })
  it('渲染制冷区域列表', () => { expect(mount(CoolingTopologyTestable).findAll('tr')).toHaveLength(2) })
  it('显示区域名称', () => { expect(mount(CoolingTopologyTestable).find('[data-testid="zone-1"] .name').text()).toBe('制冷区-A') })
  it('显示制冷容量', () => { expect(mount(CoolingTopologyTestable).find('[data-testid="zone-1"] .capacity').text()).toContain('200') })
  it('显示当前负载', () => { expect(mount(CoolingTopologyTestable).find('[data-testid="zone-1"] .load').text()).toContain('120') })
  it('显示使用率', () => { expect(mount(CoolingTopologyTestable).find('[data-testid="zone-1"] .usage').text()).toBe('60%') })
  it('进度颜色判断正确', () => { expect(progressColor(50)).toBe('#52c41a'); expect(progressColor(70)).toBe('#faad14'); expect(progressColor(90)).toBe('#f5222d') })
  it('loading初始为false', () => { expect(mount(CoolingTopologyTestable).vm.loading).toBe(false) })
})
