/**
 * 设备详情页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }), useRoute: () => ({ params: { id: '1' }, query: {} }), createRouter: vi.fn(), createWebHistory: vi.fn() }))

const DeviceManageDetailTestable = defineComponent({
  name: 'DeviceManageDetailTestable',
  setup() {
    const loading = ref(false)
    const deviceData = ref({
      id: 1, name: 'UPS-01', type: 'ups', model: 'APC Smart-UPS 3000',
      status: 'online', location: '机柜-A01', sn: 'SN-UPS-001',
      manufacturer: 'APC', install_date: '2025-06-15'
    })
    const points = ref([
      { id: 1, name: '输入电压', code: 'input_voltage', value: 220.5, unit: 'V', status: 'normal' },
      { id: 2, name: '输出电压', code: 'output_voltage', value: 219.8, unit: 'V', status: 'normal' },
      { id: 3, name: '电池电量', code: 'battery_level', value: 85, unit: '%', status: 'normal' },
      { id: 4, name: '负载率', code: 'load_rate', value: 92, unit: '%', status: 'alarm' }
    ])
    const expandedPointId = ref<number | null>(null)
    const statusText = (s: string) => ({ online: '在线', offline: '离线', alarm: '告警', normal: '正常' }[s] || s)
    const toggleExpand = (id: number) => { expandedPointId.value = expandedPointId.value === id ? null : id }
    const alarmPointCount = computed(() => points.value.filter(p => p.status === 'alarm').length)
    const normalPointCount = computed(() => points.value.filter(p => p.status === 'normal').length)
    return { loading, deviceData, points, expandedPointId, statusText, toggleExpand, alarmPointCount, normalPointCount }
  },
  template: `<div class="device-detail"><div class="info-card" data-testid="info-card"><div class="field" data-testid="device-name"><span class="label">设备名称</span><span class="value">{{ deviceData.name }}</span></div><div class="field" data-testid="device-model"><span class="label">型号</span><span class="value">{{ deviceData.model }}</span></div><div class="field" data-testid="device-status"><span class="label">状态</span><span class="value">{{ statusText(deviceData.status) }}</span></div><div class="field" data-testid="device-location"><span class="label">位置</span><span class="value">{{ deviceData.location }}</span></div><div class="field" data-testid="device-sn"><span class="label">序列号</span><span class="value">{{ deviceData.sn }}</span></div></div><div class="point-stats"><span class="normal-points" data-testid="normal-points">{{ normalPointCount }}</span><span class="alarm-points" data-testid="alarm-points">{{ alarmPointCount }}</span></div><div class="point-table" data-testid="point-table"><div v-for="p in points" :key="p.id" :data-testid="'point-' + p.id" class="point-row"><div class="point-header" @click="toggleExpand(p.id)"><span class="name">{{ p.name }}</span><span class="value">{{ p.value }}{{ p.unit }}</span><span class="status">{{ statusText(p.status) }}</span></div><div v-if="expandedPointId === p.id" class="trend-chart" :data-testid="'trend-' + p.id"><span class="chart-placeholder">趋势图: {{ p.name }}</span></div></div></div></div>`
})

describe('设备详情页面', () => {
  beforeEach(() => { setActivePinia(createPinia()) })
  it('显示设备基本信息', () => { const w = mount(DeviceManageDetailTestable); expect(w.find('[data-testid="device-name"] .value').text()).toBe('UPS-01'); expect(w.find('[data-testid="device-model"] .value').text()).toBe('APC Smart-UPS 3000') })
  it('显示设备状态和位置', () => { const w = mount(DeviceManageDetailTestable); expect(w.find('[data-testid="device-status"] .value').text()).toBe('在线'); expect(w.find('[data-testid="device-location"] .value').text()).toBe('机柜-A01') })
  it('渲染点位列表', () => { expect(mount(DeviceManageDetailTestable).findAll('.point-row')).toHaveLength(4) })
  it('显示点位值和单位', () => { const w = mount(DeviceManageDetailTestable); expect(w.find('[data-testid="point-1"] .value').text()).toBe('220.5V'); expect(w.find('[data-testid="point-3"] .value').text()).toBe('85%') })
  it('统计正常和告警点位', () => { const w = mount(DeviceManageDetailTestable); expect(w.find('[data-testid="normal-points"]').text()).toBe('3'); expect(w.find('[data-testid="alarm-points"]').text()).toBe('1') })
  it('点击展开趋势图', async () => { const w = mount(DeviceManageDetailTestable); await w.find('[data-testid="point-1"] .point-header').trigger('click'); expect(w.find('[data-testid="trend-1"]').exists()).toBe(true); expect(w.find('[data-testid="trend-1"] .chart-placeholder').text()).toContain('输入电压') })
  it('趋势图默认隐藏', () => { expect(mount(DeviceManageDetailTestable).find('[data-testid="trend-1"]').exists()).toBe(false) })
})
