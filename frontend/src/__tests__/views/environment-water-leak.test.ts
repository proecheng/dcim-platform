/**
 * 水浸监控页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }), useRoute: () => ({ params: {}, query: {} }), createRouter: vi.fn(), createWebHistory: vi.fn() }))

const WaterLeakTestable = defineComponent({
  name: 'WaterLeakTestable',
  setup() {
    const loading = ref(false)
    const wlSensors = ref([
      { point_id: 1, point_name: '水浸-A01', device_type: 'WL', area_code: 'A区', value: 0, value_text: '正常', status: 'normal', quality: 100, change_count: 0, last_change_at: '2026-02-01T08:00:00', updated_at: '2026-02-01T10:00:00' },
      { point_id: 2, point_name: '水浸-A02', device_type: 'WL', area_code: 'A区', value: 1, value_text: '漏水', status: 'alarm', quality: 100, change_count: 3, last_change_at: '2026-02-01T09:30:00', updated_at: '2026-02-01T10:00:00' },
      { point_id: 3, point_name: '水浸-B01', device_type: 'WL', area_code: 'B区', value: 0, value_text: '正常', status: 'normal', quality: 100, change_count: 1, last_change_at: '2026-02-01T07:00:00', updated_at: '2026-02-01T10:00:00' },
      { point_id: 4, point_name: '水浸-B02', device_type: 'WL', area_code: 'B区', value: null, value_text: '', status: 'offline', quality: 0, change_count: 0, last_change_at: null, updated_at: '2026-02-01T06:00:00' },
    ])

    const totalCount = computed(() => wlSensors.value.length)
    const onlineCount = computed(() => wlSensors.value.filter(d => d.status !== 'offline').length)
    const alarmCount = computed(() => wlSensors.value.filter(d => d.status === 'alarm').length)
    const recentAlarmCount = ref(5)

    const statCards = computed(() => [
      { label: '传感器总数', value: totalCount.value, valueClass: 'primary' },
      { label: '在线数', value: onlineCount.value, valueClass: 'success' },
      { label: '当前漏水告警', value: alarmCount.value, valueClass: 'danger' },
      { label: '24h 告警数', value: recentAlarmCount.value, valueClass: 'warning' },
    ])

    // 筛选
    const filterArea = ref('')
    const filterStatus = ref('')
    const searchKeyword = ref('')

    const areaOptions = computed(() => {
      const areas = new Set(wlSensors.value.map(d => d.area_code))
      return Array.from(areas).sort()
    })

    const filteredTableData = computed(() => {
      let data = wlSensors.value
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
    function statusTagType(status: string): TagType {
      const map: Record<string, TagType> = { normal: 'success', alarm: 'danger', offline: 'info' }
      return map[status] || 'info'
    }
    function statusText(status: string): string {
      const map: Record<string, string> = { normal: '正常', alarm: '漏水', offline: '离线' }
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
    function alarmStatusType(status: string): TagType {
      const map: Record<string, TagType> = { active: 'danger', acknowledged: 'warning', resolved: 'success', ignored: 'info' }
      return map[status] || 'info'
    }
    function alarmStatusText(status: string): string {
      const map: Record<string, string> = { active: '活动', acknowledged: '已确认', resolved: '已解决', ignored: '已忽略' }
      return map[status] || status
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
      loading, wlSensors, statCards, filterArea, filterStatus, searchKeyword,
      areaOptions, filteredTableData, totalCount, onlineCount, alarmCount,
      statusTagType, statusText, alarmLevelType, alarmLevelText,
      alarmStatusType, alarmStatusText, formatTime, tableRowClass,
    }
  },
  template: `<div class="water-leak-monitor">
    <div class="stat-cards" data-testid="stat-cards">
      <div v-for="card in statCards" :key="card.label" class="stat-card" :data-testid="'stat-' + card.label">
        <span class="value" :class="card.valueClass">{{ card.value }}</span>
        <span class="label">{{ card.label }}</span>
      </div>
    </div>
    <div class="sensor-table" data-testid="sensor-table">
      <div v-for="s in filteredTableData" :key="s.point_id" :data-testid="'sensor-' + s.point_id" class="sensor-row">
        <span class="name">{{ s.point_name }}</span>
        <span class="status">{{ statusText(s.status) }}</span>
        <span class="area">{{ s.area_code }}</span>
      </div>
    </div>
  </div>`,
})

describe('水浸监控页面', () => {
  beforeEach(() => { setActivePinia(createPinia()) })

  it('渲染统计卡片: 传感器总数', () => {
    expect(mount(WaterLeakTestable).find('[data-testid="stat-传感器总数"] .value').text()).toBe('4')
  })

  it('渲染统计卡片: 在线数', () => {
    expect(mount(WaterLeakTestable).find('[data-testid="stat-在线数"] .value').text()).toBe('3')
  })

  it('渲染统计卡片: 当前漏水告警', () => {
    expect(mount(WaterLeakTestable).find('[data-testid="stat-当前漏水告警"] .value').text()).toBe('1')
  })

  it('渲染传感器列表', () => {
    expect(mount(WaterLeakTestable).findAll('.sensor-row')).toHaveLength(4)
  })

  it('状态文本: alarm 显示"漏水"', () => {
    const w = mount(WaterLeakTestable)
    expect(w.vm.statusText('alarm')).toBe('漏水')
    expect(w.vm.statusText('normal')).toBe('正常')
    expect(w.vm.statusText('offline')).toBe('离线')
  })

  it('告警级别映射正确', () => {
    const w = mount(WaterLeakTestable)
    expect(w.vm.alarmLevelType('critical')).toBe('danger')
    expect(w.vm.alarmLevelText('major')).toBe('重要')
  })

  it('告警状态映射正确', () => {
    const w = mount(WaterLeakTestable)
    expect(w.vm.alarmStatusType('active')).toBe('danger')
    expect(w.vm.alarmStatusText('acknowledged')).toBe('已确认')
    expect(w.vm.alarmStatusText('resolved')).toBe('已解决')
  })

  it('格式化时间正确', () => {
    const w = mount(WaterLeakTestable)
    expect(w.vm.formatTime('2026-02-01T09:30:00')).toBe('2026-02-01 09:30:00')
    expect(w.vm.formatTime(null)).toBe('--')
  })

  it('表格行样式: alarm 行标记', () => {
    const w = mount(WaterLeakTestable)
    expect(w.vm.tableRowClass({ row: { status: 'alarm' } })).toBe('alarm-row')
    expect(w.vm.tableRowClass({ row: { status: 'normal' } })).toBe('')
  })

  it('筛选: 按区域过滤', async () => {
    const w = mount(WaterLeakTestable)
    w.vm.filterArea = 'B区'
    await w.vm.$nextTick()
    expect(w.vm.filteredTableData).toHaveLength(2)
  })

  it('筛选: 按状态过滤', async () => {
    const w = mount(WaterLeakTestable)
    w.vm.filterStatus = 'alarm'
    await w.vm.$nextTick()
    expect(w.vm.filteredTableData).toHaveLength(1)
    expect(w.vm.filteredTableData[0].point_name).toBe('水浸-A02')
  })

  it('筛选: 按关键字搜索', async () => {
    const w = mount(WaterLeakTestable)
    w.vm.searchKeyword = 'B01'
    await w.vm.$nextTick()
    expect(w.vm.filteredTableData).toHaveLength(1)
  })

  it('区域选项排序正确', () => {
    expect(mount(WaterLeakTestable).vm.areaOptions).toEqual(['A区', 'B区'])
  })
})
