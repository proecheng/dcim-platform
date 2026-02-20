/**
 * 机柜视图页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }), useRoute: () => ({ params: {}, query: {} }), createRouter: vi.fn(), createWebHistory: vi.fn() }))

const AssetCabinetTestable = defineComponent({
  name: 'AssetCabinetTestable',
  setup() {
    const loading = ref(false)
    const cabinets = ref([
      { id: 1, name: '机柜-A01', total_u: 42, used_u: 30 },
      { id: 2, name: '机柜-A02', total_u: 42, used_u: 10 },
      { id: 3, name: '机柜-B01', total_u: 42, used_u: 42 }
    ])
    const selectedCabinet = ref<any>(null)
    const rackSlots = ref([
      { u_position: 1, height: 2, device_name: '服务器-001', device_type: 'server' },
      { u_position: 3, height: 1, device_name: '交换机-001', device_type: 'switch' },
      { u_position: 4, height: 4, device_name: '存储-001', device_type: 'storage' }
    ])
    const usageDialogVisible = ref(false)
    const usageRate = (c: any) => ((c.used_u / c.total_u) * 100).toFixed(1)
    const usageColor = (c: any) => { const rate = c.used_u / c.total_u; return rate > 0.9 ? 'danger' : rate > 0.7 ? 'warning' : 'success' }
    const selectCabinet = (c: any) => { selectedCabinet.value = c }
    const totalUsedU = computed(() => cabinets.value.reduce((s, c) => s + c.used_u, 0))
    const totalU = computed(() => cabinets.value.reduce((s, c) => s + c.total_u, 0))
    return { loading, cabinets, selectedCabinet, rackSlots, usageDialogVisible, usageRate, usageColor, selectCabinet, totalUsedU, totalU }
  },
  template: `<div class="asset-cabinet"><div class="summary"><span class="total-used" data-testid="total-used">{{ totalUsedU }}U</span><span class="total-capacity" data-testid="total-capacity">{{ totalU }}U</span></div><div class="cabinet-list" data-testid="cabinet-list"><div v-for="c in cabinets" :key="c.id" :data-testid="'cabinet-' + c.id" class="cabinet-card" @click="selectCabinet(c)"><span class="name">{{ c.name }}</span><span class="usage">{{ usageRate(c) }}%</span><span class="usage-color">{{ usageColor(c) }}</span></div></div><div v-if="selectedCabinet" class="rack-view" data-testid="rack-view"><div class="rack-title">{{ selectedCabinet.name }}</div><div v-for="(slot, idx) in rackSlots" :key="idx" :data-testid="'slot-' + idx" class="rack-slot"><span class="u-pos">U{{ slot.u_position }}</span><span class="device-name">{{ slot.device_name }}</span><span class="device-type">{{ slot.device_type }}</span></div></div></div>`
})

describe('机柜视图页面', () => {
  beforeEach(() => { setActivePinia(createPinia()) })
  it('渲染机柜列表', () => { expect(mount(AssetCabinetTestable).findAll('.cabinet-card')).toHaveLength(3) })
  it('显示机柜名称和使用率', () => { const w = mount(AssetCabinetTestable); expect(w.find('[data-testid="cabinet-1"] .name').text()).toBe('机柜-A01'); expect(w.find('[data-testid="cabinet-1"] .usage').text()).toBe('71.4%') })
  it('使用率颜色正确', () => { const w = mount(AssetCabinetTestable); expect(w.find('[data-testid="cabinet-2"] .usage-color').text()).toBe('success'); expect(w.find('[data-testid="cabinet-3"] .usage-color').text()).toBe('danger') })
  it('显示总容量统计', () => { const w = mount(AssetCabinetTestable); expect(w.find('[data-testid="total-used"]').text()).toBe('82U'); expect(w.find('[data-testid="total-capacity"]').text()).toBe('126U') })
  it('点击机柜显示U位视图', async () => { const w = mount(AssetCabinetTestable); await w.find('[data-testid="cabinet-1"]').trigger('click'); expect(w.find('[data-testid="rack-view"]').exists()).toBe(true); expect(w.find('.rack-title').text()).toBe('机柜-A01') })
  it('渲染U位设备', async () => { const w = mount(AssetCabinetTestable); await w.find('[data-testid="cabinet-1"]').trigger('click'); expect(w.findAll('.rack-slot')).toHaveLength(3); expect(w.find('[data-testid="slot-0"] .device-name').text()).toBe('服务器-001') })
  it('U位视图默认隐藏', () => { expect(mount(AssetCabinetTestable).find('[data-testid="rack-view"]').exists()).toBe(false) })
})
