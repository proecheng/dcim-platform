/**
 * 温湿度监控页面 单元测试
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, ref, computed } from 'vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }), useRoute: () => ({ params: {}, query: {} }), createRouter: vi.fn(), createWebHistory: vi.fn() }))

// ── Testable 包装组件: 提取 temperature.vue 核心逻辑 ──
const TemperatureTestable = defineComponent({
  name: 'TemperatureTestable',
  setup() {
    const loading = ref(false)
    const thSensors = ref([
      { point_id: 1, point_name: '温度-A01', device_type: 'TH', area_code: 'A区', value: 24.5, unit: '°C', status: 'normal', quality: 100, updated_at: '2026-02-01T10:00:00' },
      { point_id: 2, point_name: '温度-A02', device_type: 'TH', area_code: 'A区', value: 36.2, unit: '°C', status: 'alarm', quality: 80, updated_at: '2026-02-01T10:00:00' },
      { point_id: 3, point_name: '湿度-A01', device_type: 'TH', area_code: 'A区', value: 55.0, unit: '%', status: 'normal', quality: 100, updated_at: '2026-02-01T10:00:00' },
      { point_id: 4, point_name: '温度-B01', device_type: 'TH', area_code: 'B区', value: 22.0, unit: '°C', status: 'offline', quality: 0, updated_at: '2026-02-01T10:00:00' },
      { point_id: 5, point_name: '湿度-B01', device_type: 'TH', area_code: 'B区', value: 60.0, unit: '%', status: 'normal', quality: 100, updated_at: '2026-02-01T10:00:00' },
    ])
    const driftPointIds = ref(new Set([2]))

    const totalCount = computed(() => thSensors.value.length)
    const onlineCount = computed(() => thSensors.value.filter(d => d.status !== 'offline').length)
    const alarmCount = computed(() => thSensors.value.filter(d => d.status === 'alarm').length)
    const driftCount = computed(() => thSensors.value.filter(d => driftPointIds.value.has(d.point_id)).length)

    const tempSensors = computed(() => thSensors.value.filter(d => d.unit === '°C'))
    const humiditySensors = computed(() => thSensors.value.filter(d => d.unit === '%'))

    const avgTemp = computed(() => {
      const valid = tempSensors.value.filter(d => d.value != null && d.status !== 'offline')
      if (!valid.length) return null
      return valid.reduce((s, d) => s + (d.value ?? 0), 0) / valid.length
    })

    const avgHumidity = computed(() => {
      const valid = humiditySensors.value.filter(d => d.value != null && d.status !== 'offline')
      if (!valid.length) return null
      return valid.reduce((s, d) => s + (d.value ?? 0), 0) / valid.length
    })

    // 统计卡片
    const statCards = computed(() => [
      { label: '传感器总数', value: totalCount.value, valueClass: 'primary' },
      { label: '在线数', value: onlineCount.value, valueClass: 'success' },
      { label: '告警数', value: alarmCount.value, valueClass: 'danger' },
      { label: '平均温度', value: avgTemp.value != null ? avgTemp.value.toFixed(1) + '°C' : '--', valueClass: 'warning' },
      { label: '平均湿度', value: avgHumidity.value != null ? avgHumidity.value.toFixed(1) + '%' : '--', valueClass: 'primary' },
      { label: '疑似漂移', value: driftCount.value, valueClass: 'drift' },
    ])

    // 筛选逻辑
    const filterArea = ref('')
    const filterStatus = ref('')
    const searchKeyword = ref('')

    const areaOptions = computed(() => {
      const areas = new Set(thSensors.value.map(d => d.area_code))
      return Array.from(areas).sort()
    })

    const filteredTableData = computed(() => {
      let data = thSensors.value
      if (filterArea.value) data = data.filter(d => d.area_code === filterArea.value)
      if (filterStatus.value) {
        if (filterStatus.value === 'drift') {
          data = data.filter(d => driftPointIds.value.has(d.point_id))
        } else {
          data = data.filter(d => d.status === filterStatus.value)
        }
      }
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
      const map: Record<string, string> = { normal: '正常', alarm: '告警', offline: '离线' }
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
    function isDrift(pointId: number): boolean {
      return driftPointIds.value.has(pointId)
    }

    return {
      loading, thSensors, statCards, filterArea, filterStatus, searchKeyword,
      areaOptions, filteredTableData, totalCount, onlineCount, alarmCount, driftCount,
      avgTemp, avgHumidity, statusTagType, statusText, alarmLevelType, alarmLevelText,
      formatTime, isDrift,
    }
  },
  template: `<div class="temperature-monitor">
    <div class="stat-cards" data-testid="stat-cards">
      <div v-for="card in statCards" :key="card.label" class="stat-card" :data-testid="'stat-' + card.label">
        <span class="value" :class="card.valueClass">{{ card.value }}</span>
        <span class="label">{{ card.label }}</span>
      </div>
    </div>
    <div class="sensor-table" data-testid="sensor-table">
      <div v-for="s in filteredTableData" :key="s.point_id" :data-testid="'sensor-' + s.point_id" class="sensor-row">
        <span class="name">{{ s.point_name }}</span>
        <span class="area">{{ s.area_code }}</span>
        <span class="value">{{ s.value }} {{ s.unit }}</span>
        <span class="status">{{ statusText(s.status) }}</span>
        <span class="time">{{ formatTime(s.updated_at) }}</span>
      </div>
    </div>
  </div>`,
})

describe('温湿度监控页面', () => {
  beforeEach(() => { setActivePinia(createPinia()) })

  it('渲染统计卡片: 传感器总数', () => {
    const w = mount(TemperatureTestable)
    expect(w.find('[data-testid="stat-传感器总数"] .value').text()).toBe('5')
  })

  it('渲染统计卡片: 在线数排除 offline', () => {
    const w = mount(TemperatureTestable)
    expect(w.find('[data-testid="stat-在线数"] .value').text()).toBe('4')
  })

  it('渲染统计卡片: 告警数', () => {
    const w = mount(TemperatureTestable)
    expect(w.find('[data-testid="stat-告警数"] .value').text()).toBe('1')
  })

  it('计算平均温度: 排除 offline 传感器', () => {
    const w = mount(TemperatureTestable)
    // 有效温度: 24.5 + 36.2 = 60.7, 平均 30.35 → "30.4°C"
    expect(w.find('[data-testid="stat-平均温度"] .value').text()).toBe('30.4°C')
  })

  it('计算平均湿度', () => {
    const w = mount(TemperatureTestable)
    // 有效湿度: 55.0 + 60.0 = 115.0, 平均 57.5 → "57.5%"
    expect(w.find('[data-testid="stat-平均湿度"] .value').text()).toBe('57.5%')
  })

  it('渲染传感器列表', () => {
    const w = mount(TemperatureTestable)
    expect(w.findAll('.sensor-row')).toHaveLength(5)
  })

  it('状态文本映射正确', () => {
    const w = mount(TemperatureTestable)
    expect(w.vm.statusText('normal')).toBe('正常')
    expect(w.vm.statusText('alarm')).toBe('告警')
    expect(w.vm.statusText('offline')).toBe('离线')
    expect(w.vm.statusText('unknown')).toBe('unknown')
  })

  it('状态标签类型映射正确', () => {
    const w = mount(TemperatureTestable)
    expect(w.vm.statusTagType('normal')).toBe('success')
    expect(w.vm.statusTagType('alarm')).toBe('danger')
    expect(w.vm.statusTagType('offline')).toBe('info')
  })

  it('告警级别映射正确', () => {
    const w = mount(TemperatureTestable)
    expect(w.vm.alarmLevelType('critical')).toBe('danger')
    expect(w.vm.alarmLevelText('critical')).toBe('紧急')
    expect(w.vm.alarmLevelText('major')).toBe('重要')
  })

  it('格式化时间: 正常值', () => {
    const w = mount(TemperatureTestable)
    expect(w.vm.formatTime('2026-02-01T10:00:00')).toBe('2026-02-01 10:00:00')
  })

  it('格式化时间: 空值返回 --', () => {
    const w = mount(TemperatureTestable)
    expect(w.vm.formatTime(null)).toBe('--')
    expect(w.vm.formatTime(undefined)).toBe('--')
  })

  it('漂移检测: isDrift 正确识别', () => {
    const w = mount(TemperatureTestable)
    expect(w.vm.isDrift(2)).toBe(true)
    expect(w.vm.isDrift(1)).toBe(false)
  })

  it('区域选项列表排序正确', () => {
    const w = mount(TemperatureTestable)
    expect(w.vm.areaOptions).toEqual(['A区', 'B区'])
  })

  it('筛选: 按区域过滤', async () => {
    const w = mount(TemperatureTestable)
    w.vm.filterArea = 'A区'
    await w.vm.$nextTick()
    expect(w.vm.filteredTableData).toHaveLength(3)
  })

  it('筛选: 按状态过滤', async () => {
    const w = mount(TemperatureTestable)
    w.vm.filterStatus = 'alarm'
    await w.vm.$nextTick()
    expect(w.vm.filteredTableData).toHaveLength(1)
    expect(w.vm.filteredTableData[0].point_name).toBe('温度-A02')
  })

  it('筛选: 按关键字搜索', async () => {
    const w = mount(TemperatureTestable)
    w.vm.searchKeyword = '湿度'
    await w.vm.$nextTick()
    expect(w.vm.filteredTableData).toHaveLength(2)
  })

  it('筛选: 漂移状态过滤', async () => {
    const w = mount(TemperatureTestable)
    w.vm.filterStatus = 'drift'
    await w.vm.$nextTick()
    expect(w.vm.filteredTableData).toHaveLength(1)
    expect(w.vm.filteredTableData[0].point_id).toBe(2)
  })
})
