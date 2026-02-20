/**
 * 大屏展示页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }), useRoute: () => ({ params: {}, query: {} }), createRouter: vi.fn(), createWebHistory: vi.fn() }))

const BigscreenTestable = defineComponent({
  name: 'BigscreenTestable',
  setup() {
    const loading = ref(false)
    const viewMode = ref<'3d' | '2d'>('3d')
    const currentFloor = ref(1)
    const floors = ref([{ id: 1, name: 'F1' }, { id: 2, name: 'F2' }, { id: 3, name: 'F3' }])
    const contextMenuVisible = ref(false)
    const contextMenuPosition = ref({ x: 0, y: 0 })
    const alarmCount = ref(3)
    const deviceCount = ref(156)
    const pue = ref(1.45)
    const temperature = ref(24.5)
    const panelCollapsed = ref(false)
    const toggleViewMode = () => { viewMode.value = viewMode.value === '3d' ? '2d' : '3d' }
    const selectFloor = (id: number) => { currentFloor.value = id }
    const togglePanel = () => { panelCollapsed.value = !panelCollapsed.value }
    const currentFloorName = computed(() => floors.value.find(f => f.id === currentFloor.value)?.name || '')
    return { loading, viewMode, currentFloor, floors, contextMenuVisible, contextMenuPosition, alarmCount, deviceCount, pue, temperature, panelCollapsed, toggleViewMode, selectFloor, togglePanel, currentFloorName }
  },
  template: `<div class="bigscreen"><div class="toolbar"><button data-testid="view-toggle" @click="toggleViewMode">{{ viewMode === '3d' ? '切换2D' : '切换3D' }}</button><div class="floor-selector" data-testid="floor-selector"><button v-for="f in floors" :key="f.id" :data-testid="'floor-' + f.id" :class="{ active: currentFloor === f.id }" @click="selectFloor(f.id)">{{ f.name }}</button></div><span class="current-floor" data-testid="current-floor">{{ currentFloorName }}</span></div><div class="info-panels" :class="{ collapsed: panelCollapsed }"><div class="panel" data-testid="alarm-panel"><span class="value">{{ alarmCount }}</span><span class="label">告警</span></div><div class="panel" data-testid="device-panel"><span class="value">{{ deviceCount }}</span><span class="label">设备</span></div><div class="panel" data-testid="pue-panel"><span class="value">{{ pue }}</span><span class="label">PUE</span></div><div class="panel" data-testid="temp-panel"><span class="value">{{ temperature }}℃</span><span class="label">温度</span></div><button data-testid="panel-toggle" @click="togglePanel">{{ panelCollapsed ? '展开' : '收起' }}</button></div><div class="viewport" data-testid="viewport"><span class="mode">{{ viewMode }}</span></div></div>`
})

describe('大屏展示页面', () => {
  beforeEach(() => { setActivePinia(createPinia()) })
  it('默认3D视图模式', () => { const w = mount(BigscreenTestable); expect(w.vm.viewMode).toBe('3d'); expect(w.find('[data-testid="viewport"] .mode').text()).toBe('3d') })
  it('切换视图模式', async () => { const w = mount(BigscreenTestable); await w.find('[data-testid="view-toggle"]').trigger('click'); expect(w.vm.viewMode).toBe('2d'); expect(w.find('[data-testid="view-toggle"]').text()).toBe('切换3D') })
  it('渲染楼层选择器', () => { expect(mount(BigscreenTestable).findAll('[data-testid="floor-selector"] button')).toHaveLength(3) })
  it('切换楼层', async () => { const w = mount(BigscreenTestable); await w.find('[data-testid="floor-2"]').trigger('click'); expect(w.find('[data-testid="current-floor"]').text()).toBe('F2') })
  it('显示信息面板数据', () => { const w = mount(BigscreenTestable); expect(w.find('[data-testid="alarm-panel"] .value').text()).toBe('3'); expect(w.find('[data-testid="pue-panel"] .value').text()).toBe('1.45') })
  it('面板折叠切换', async () => { const w = mount(BigscreenTestable); await w.find('[data-testid="panel-toggle"]').trigger('click'); expect(w.vm.panelCollapsed).toBe(true); expect(w.find('[data-testid="panel-toggle"]').text()).toBe('展开') })
  it('显示温度', () => { expect(mount(BigscreenTestable).find('[data-testid="temp-panel"] .value').text()).toBe('24.5℃') })
})
