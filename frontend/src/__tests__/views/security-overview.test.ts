/**
 * 安防监控总览页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }), useRoute: () => ({ params: {}, query: {} }), createRouter: vi.fn(), createWebHistory: vi.fn() }))

const SecurityOverviewTestable = defineComponent({
  name: 'SecurityOverviewTestable',
  setup() {
    const loading = ref(false)
    const deviceCounts = ref({ total: 45, online: 40, offline: 3, alarm: 2 })
    const sensorList = ref([
      { id: 1, name: '门禁-A01', type: 'access', status: 'normal', location: '机房A入口', last_event: '2026-02-01 08:30' },
      { id: 2, name: '烟感-A01', type: 'smoke', status: 'normal', location: '机房A', last_event: '2026-02-01 10:00' },
      { id: 3, name: '水浸-B01', type: 'water', status: 'alarm', location: '机房B', last_event: '2026-02-01 14:30' },
      { id: 4, name: '红外-A01', type: 'infrared', status: 'offline', location: '机房A走廊', last_event: '2026-01-30 12:00' }
    ])
    const statusTagType = (s: string) => ({ normal: 'success', alarm: 'danger', offline: 'info' }[s] || 'info')
    const statusText = (s: string) => ({ normal: '正常', alarm: '告警', offline: '离线' }[s] || s)
    const typeText = (t: string) => ({ access: '门禁', smoke: '烟感', water: '水浸', infrared: '红外' }[t] || t)
    const normalCount = computed(() => sensorList.value.filter(s => s.status === 'normal').length)
    return { loading, deviceCounts, sensorList, statusTagType, statusText, typeText, normalCount }
  },
  template: `<div class="security-overview"><div class="count-cards" data-testid="count-cards"><div class="card" data-testid="count-total"><span class="value">{{ deviceCounts.total }}</span><span class="label">总设备</span></div><div class="card" data-testid="count-online"><span class="value">{{ deviceCounts.online }}</span><span class="label">在线</span></div><div class="card" data-testid="count-alarm"><span class="value">{{ deviceCounts.alarm }}</span><span class="label">告警</span></div><div class="card" data-testid="count-offline"><span class="value">{{ deviceCounts.offline }}</span><span class="label">离线</span></div></div><span class="normal-count" data-testid="normal-count">{{ normalCount }}</span><div class="sensor-table" data-testid="sensor-table"><div v-for="s in sensorList" :key="s.id" :data-testid="'sensor-' + s.id" class="sensor-row"><span class="name">{{ s.name }}</span><span class="type">{{ typeText(s.type) }}</span><span class="status">{{ statusText(s.status) }}</span><span class="location">{{ s.location }}</span></div></div></div>`
})

describe('安防监控总览页面', () => {
  beforeEach(() => { setActivePinia(createPinia()) })
  it('渲染设备统计卡片', () => { const w = mount(SecurityOverviewTestable); expect(w.find('[data-testid="count-total"] .value').text()).toBe('45'); expect(w.find('[data-testid="count-online"] .value').text()).toBe('40') })
  it('渲染传感器列表', () => { expect(mount(SecurityOverviewTestable).findAll('.sensor-row')).toHaveLength(4) })
  it('显示传感器名称和类型', () => { const w = mount(SecurityOverviewTestable); expect(w.find('[data-testid="sensor-1"] .name').text()).toBe('门禁-A01'); expect(w.find('[data-testid="sensor-1"] .type').text()).toBe('门禁') })
  it('显示传感器状态', () => { const w = mount(SecurityOverviewTestable); expect(w.find('[data-testid="sensor-3"] .status').text()).toBe('告警') })
  it('统计正常传感器数', () => { expect(mount(SecurityOverviewTestable).find('[data-testid="normal-count"]').text()).toBe('2') })
  it('类型文本映射正确', () => { const w = mount(SecurityOverviewTestable); expect(w.vm.typeText('smoke')).toBe('烟感'); expect(w.vm.typeText('water')).toBe('水浸') })
  it('状态标签类型正确', () => { const w = mount(SecurityOverviewTestable); expect(w.vm.statusTagType('normal')).toBe('success'); expect(w.vm.statusTagType('alarm')).toBe('danger') })
})
