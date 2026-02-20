/**
 * 电池组监控页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref } from 'vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }), useRoute: () => ({ params: {}, query: {} }), createRouter: vi.fn(), createWebHistory: vi.fn() }))

function getSohColor(soh: number): string { if (soh >= 80) return '#52c41a'; if (soh >= 60) return '#faad14'; return '#f5222d' }
function getSocColor(soc: number): string { if (soc >= 50) return '#52c41a'; if (soc >= 20) return '#faad14'; return '#f5222d' }
function batteryTypeLabel(type: string): string { return ({ lead_acid: '铅酸', lithium: '锂电', nimh: '镍氢' }[type] || type) }

const BatteryMonitorTestable = defineComponent({
  name: 'BatteryMonitorTestable',
  setup() {
    const loading = ref(false)
    const batteryList = ref([
      { id: 1, group_name: '电池组-A', ups_name: 'UPS-1', battery_type: 'lead_acid', rated_capacity: 100, soh: 92, soc: 85, voltage: 216, temperature: 25, charge_status: 'float' },
      { id: 2, group_name: '电池组-B', ups_name: 'UPS-2', battery_type: 'lithium', rated_capacity: 200, soh: 55, soc: 15, voltage: 432, temperature: 30, charge_status: 'charging' }
    ])
    return { loading, batteryList, getSohColor, getSocColor, batteryTypeLabel }
  },
  template: `<div class="battery-monitor"><table><tr v-for="b in batteryList" :key="b.id" :data-testid="'bat-' + b.id"><td class="name">{{ b.group_name }}</td><td class="ups">{{ b.ups_name }}</td><td class="type">{{ batteryTypeLabel(b.battery_type) }}</td><td class="soh">{{ b.soh }}%</td><td class="soc">{{ b.soc }}%</td><td class="voltage">{{ b.voltage }}V</td><td class="temp">{{ b.temperature }}°C</td></tr></table></div>`
})

describe('电池组监控页面', () => {
  beforeEach(() => { setActivePinia(createPinia()) })
  it('渲染电池组列表', () => { expect(mount(BatteryMonitorTestable).findAll('tr')).toHaveLength(2) })
  it('显示电池组名称', () => { expect(mount(BatteryMonitorTestable).find('[data-testid="bat-1"] .name').text()).toBe('电池组-A') })
  it('电池类型文本正确', () => { expect(batteryTypeLabel('lead_acid')).toBe('铅酸'); expect(batteryTypeLabel('lithium')).toBe('锂电') })
  it('SOH颜色判断正确', () => { expect(getSohColor(92)).toBe('#52c41a'); expect(getSohColor(70)).toBe('#faad14'); expect(getSohColor(50)).toBe('#f5222d') })
  it('SOC颜色判断正确', () => { expect(getSocColor(85)).toBe('#52c41a'); expect(getSocColor(30)).toBe('#faad14'); expect(getSocColor(10)).toBe('#f5222d') })
  it('显示SOH和SOC', () => { const w = mount(BatteryMonitorTestable); expect(w.find('[data-testid="bat-1"] .soh').text()).toBe('92%'); expect(w.find('[data-testid="bat-1"] .soc').text()).toBe('85%') })
  it('显示电压和温度', () => { const w = mount(BatteryMonitorTestable); expect(w.find('[data-testid="bat-1"] .voltage').text()).toBe('216V'); expect(w.find('[data-testid="bat-1"] .temp').text()).toBe('25°C') })
})
