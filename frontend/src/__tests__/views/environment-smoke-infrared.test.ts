/**
 * 烟雾/红外监控页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }), useRoute: () => ({ params: {}, query: {} }), createRouter: vi.fn(), createWebHistory: vi.fn() }))

const SmokeInfraredTestable = defineComponent({
  name: 'SmokeInfraredTestable',
  setup() {
    const loading = ref(false)
    const siSensors = ref([
      { point_id: 1, point_name: '烟雾-A01', device_type: 'SMOKE', area_code: 'A区', status: 'normal', value_text: '正常', quality: 100, change_count: 0, last_change_at: '2026-02-01T08:00:00', updated_at: '2026-02-01T10:00:00' },
      { point_id: 2, point_name: '烟雾-A02', device_type: 'SMOKE', area_code: 'A区', status: 'alarm', value_text: '烟雾告警', quality: 100, change_count: 2, last_change_at: '2026-02-01T09:00:00', updated_at: '2026-02-01T10:00:00' },
      { point_id: 3, point_name: '红外-A01', device_type: 'IR', area_code: 'A区', status: 'normal', value_text: '正常', quality: 100, change_count: 0, last_change_at: '2026-02-01T08:00:00', updated_at: '2026-02-01T10:00:00' },
      { point_id: 4, point_name: '红外-B01', device_type: 'IR', area_code: 'B区', status: 'alarm', value_text: '入侵告警', quality: 100, change_count: 1, last_change_at: '2026-02-01T09:30:00', updated_at: '2026-02-01T10:00:00' },
      { point_id: 5, point_name: '烟雾-B01', device_type: 'SMOKE', area_code: 'B区', status: 'offline', value_text: '', quality: 0, change_count: 0, last_change_at: null, updated_at: '2026-02-01T06:00:00' },
    ])

    const smokeTotal = computed(() => siSensors.value.filter(d => d.device_type === 'SMOKE').length)
    const smokeAlarm = computed(() => siSensors.value.filter(d => d.device_type === 'SMOKE' && d.status === 'alarm').length)
    const irTotal = computed(() => siSensors.value.filter(d => d.device_type === 'IR').length)
    const irAlarm = computed(() => siSensors.value.filter(d => d.device_type === 'IR' && d.status === 'alarm').length)
    const recentAlarmCount = ref(8)

    const statCards = computed(() => [
      { label: '烟雾传感器', value: smokeTotal.value, valueClass: 'warning' },
      { label: '烟雾告警', value: smokeAlarm.value, valueClass: 'danger' },
      { label: '红外传感器', value: irTotal.value, valueClass: 'primary' },
      { label: '红外告警', value: irAlarm.value, valueClass: 'purple' },
      { label: '24h 事件数', value: recentAlarmCount.value, valueClass: 'success' },
    ])

    // 筛选
    const filterType = ref('')
    const filterArea = ref('')
    const filterStatus = ref('')
    const searchKeyword = ref('')

    const areaOptions = computed(() => {
      const areas = new Set(siSensors.value.map(d => d.area_code))
      return Array.from(areas).sort()
    })

    const filteredTableData = computed(() => {
      let data = siSensors.value
      if (filterType.value) data = data.filter(d => d.device_type === filterType.value)
      if (filterArea.value) data = data.filter(d => d.area_code === filterArea.value)
      if (filterStatus.value) data = data.filter(d => d.status === filterStatus.value)
      if (searchKeyword.value) {
        const kw = searchKeyword.value.toLowerCase()
        data = data.filter(d => d.point_name.toLowerCase().includes(kw))
      }
      return data
    })

    // 辅助函数
    type TagType = 'info' | 'warning' | 'success' | 'danger' | 'primary'
    function sensorTypeTagType(deviceType: string): TagType {
      return deviceType === 'SMOKE' ? 'warning' : 'primary'
    }
    function sensorTypeText(deviceType: string): string {
      return deviceType === 'SMOKE' ? '烟雾' : '红外'
    }
    function statusTagType(status: string): TagType {
      const map: Record<string, TagType> = { normal: 'success', alarm: 'danger', offline: 'info' }
      return map[status] || 'info'
    }
    function statusText(status: string, deviceType?: string): string {
      if (status === 'alarm') return deviceType === 'SMOKE' ? '烟雾告警' : '入侵告警'
      const map: Record<string, string> = { normal: '正常', offline: '离线' }
      return map[status] || status
    }
    function alarmLevelType(level: string): TagType {
      const map: Record<string, TagType> = { critical: 'danger', major: 'warning', minor: 'primary', info: 'info' }
      return map[level] || 'info'
    }
    function alarmLevelText(level: string): string {
      const map: Record<string, string> = { critical: '紧急', major: '重要', minor: '次要', info: '提示' }
      return map[level] || level
    }
    function formatTime(t: string | null | undefined): string {
      if (!t) return '--'
      return t.replace('T', ' ').substring(0, 19)
    }
    function tableRowClass({ row }: { row: { status: string } }): string {
      if (row.status === 'alarm') return 'alarm-row'
      return ''
    }

    return {
      loading, siSensors, statCards, filterType, filterArea, filterStatus, searchKeyword,
      areaOptions, filteredTableData, smokeTotal, smokeAlarm, irTotal, irAlarm,
      sensorTypeTagType, sensorTypeText, statusTagType, statusText,
      alarmLevelType, alarmLevelText, formatTime, tableRowClass,
    }
  },
  template: `<div class="smoke-infrared-monitor">
    <div class="stat-cards" data-testid="stat-cards">
      <div v-for="card in statCards" :key="card.label" class="stat-card" :data-testid="'stat-' + card.label">
        <span class="value" :class="card.valueClass">{{ card.value }}</span>
        <span class="label">{{ card.label }}</span>
      </div>
    </div>
    <div class="sensor-table" data-testid="sensor-table">
      <div v-for="s in filteredTableData" :key="s.point_id" :data-testid="'sensor-' + s.point_id" class="sensor-row">
        <span class="name">{{ s.point_name }}</span>
        <span class="type">{{ sensorTypeText(s.device_type) }}</span>
        <span class="status">{{ statusText(s.status, s.device_type) }}</span>
      </div>
    </div>
  </div>`,
})

describe('烟雾/红外监控页面', () => {
  beforeEach(() => { setActivePinia(createPinia()) })

  it('渲染统计卡片: 烟雾传感器数', () => {
    expect(mount(SmokeInfraredTestable).find('[data-testid="stat-烟雾传感器"] .value').text()).toBe('3')
  })

  it('渲染统计卡片: 烟雾告警数', () => {
    expect(mount(SmokeInfraredTestable).find('[data-testid="stat-烟雾告警"] .value').text()).toBe('1')
  })

  it('渲染统计卡片: 红外传感器数', () => {
    expect(mount(SmokeInfraredTestable).find('[data-testid="stat-红外传感器"] .value').text()).toBe('2')
  })

  it('渲染统计卡片: 红外告警数', () => {
    expect(mount(SmokeInfraredTestable).find('[data-testid="stat-红外告警"] .value').text()).toBe('1')
  })

  it('渲染传感器列表', () => {
    expect(mount(SmokeInfraredTestable).findAll('.sensor-row')).toHaveLength(5)
  })

  it('传感器类型文本映射', () => {
    const w = mount(SmokeInfraredTestable)
    expect(w.vm.sensorTypeText('SMOKE')).toBe('烟雾')
    expect(w.vm.sensorTypeText('IR')).toBe('红外')
  })

  it('传感器类型标签类型', () => {
    const w = mount(SmokeInfraredTestable)
    expect(w.vm.sensorTypeTagType('SMOKE')).toBe('warning')
    expect(w.vm.sensorTypeTagType('IR')).toBe('primary')
  })

  it('状态文本: alarm 根据设备类型区分', () => {
    const w = mount(SmokeInfraredTestable)
    expect(w.vm.statusText('alarm', 'SMOKE')).toBe('烟雾告警')
    expect(w.vm.statusText('alarm', 'IR')).toBe('入侵告警')
    expect(w.vm.statusText('normal')).toBe('正常')
    expect(w.vm.statusText('offline')).toBe('离线')
  })

  it('筛选: 按类型过滤', async () => {
    const w = mount(SmokeInfraredTestable)
    w.vm.filterType = 'SMOKE'
    await w.vm.$nextTick()
    expect(w.vm.filteredTableData).toHaveLength(3)
  })

  it('筛选: 按区域过滤', async () => {
    const w = mount(SmokeInfraredTestable)
    w.vm.filterArea = 'B区'
    await w.vm.$nextTick()
    expect(w.vm.filteredTableData).toHaveLength(2)
  })

  it('筛选: 按状态过滤', async () => {
    const w = mount(SmokeInfraredTestable)
    w.vm.filterStatus = 'alarm'
    await w.vm.$nextTick()
    expect(w.vm.filteredTableData).toHaveLength(2)
  })

  it('筛选: 按关键字搜索', async () => {
    const w = mount(SmokeInfraredTestable)
    w.vm.searchKeyword = '红外'
    await w.vm.$nextTick()
    expect(w.vm.filteredTableData).toHaveLength(2)
  })

  it('格式化时间', () => {
    const w = mount(SmokeInfraredTestable)
    expect(w.vm.formatTime('2026-02-01T09:30:00')).toBe('2026-02-01 09:30:00')
    expect(w.vm.formatTime(null)).toBe('--')
  })

  it('表格行样式', () => {
    const w = mount(SmokeInfraredTestable)
    expect(w.vm.tableRowClass({ row: { status: 'alarm' } })).toBe('alarm-row')
    expect(w.vm.tableRowClass({ row: { status: 'normal' } })).toBe('')
  })
})
